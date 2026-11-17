"""Streamlit sections for the optional dynamic aero-mechanical analysis (Turkish UI).

Integrated into the research workspace: same design, profile and stored
provider version as the BEM route. Runs only on an explicit action, in a
detached supervisor; this module polls status, never blocks on a solver.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import re

import streamlit as st

from pyfoldable.coupled import toolchain as tcmod
from pyfoldable.coupled.model import CoupledControls, CoupledMechanics

from . import coupled_analysis as svc, coupled_views as views, figure_style

RUN = "_coupled_run"
HISTORY = "research_coupled_results"
ACTIVE = "_coupled_active"
MAX_HISTORY = 6
_STATUS_TEXT = {
    "completed": ("success", "Tamamlandı: tüm bağlaşım pencereleri yakınsadı ve sorgulanan kesit durumları kabul edilen tablo içinde kaldı."),
    "failed_aero_coverage": ("warning", "Aerodinamik kapsam aşıldı: bir kesit durumu kabul edilen polar tablosunun dışına çıktı. "
                             "Kapsam içindeki ilk aralık ayrıca gösterilir; sonrası tamamlanmış sonuç değildir."),
    "failed_unconverged_coupling": ("warning", "Bağlaşım yakınsamadı: preCICE bir pencereyi en fazla iterasyonda kabul etti. "
                                    "Önceki pencereler kısmi geçmiş olarak saklandı."),
    "failed_solver": ("error", "Bir çözücü hata ile durdu. Ham çıktılar ve kayıtlar saklandı; teknik ayrıntıya bakın."),
    "failed_incomplete": ("warning", "Planlanan pencerelerin tamamı kabul edilmedi; kısmi geçmiş saklandı."),
    "cancelled": ("info", "Kullanıcı tarafından durduruldu; kabul edilen pencereler kısmi geçmiş olarak saklandı."),
    "timeout": ("warning", "Süre bütçesi aşıldı; kabul edilen pencereler kısmi geçmiş olarak saklandı."),
    "failed_geometry_envelope": ("warning", "Katlanma geometri sınırı aşıldı: bir kanadın katlanma açısı sürekli kaldırma "
                                           "çizgisinin geometri sınırının ötesine geçti. Sınır içindeki ilk aralık geçerli "
                                           "önek olarak gösterilir; sonrası tamamlanmış sonuç değildir."),
}
_STATUS_SHORT = {k: re.split(r"[:;.]", text, maxsplit=1)[0] for k, (_, text) in _STATUS_TEXT.items()}
_PREP_TEXT = {
    "inert_fixture_tables": "seçilen polar kaydı bir yazılım test kaydıdır; mühendislik analizinde kullanılamaz.",
    "aero_admission_rejected": "saklanan polar sürümü bu tasarım için kabul edilmedi (BEM hazırlığıyla aynı denetim).",
    "hinge_outside_aero_span": "menteşe, beyan edilen aerodinamik istasyon aralığının içinde olmalı.",
    "aerodynamic_station_before_physical_root": "göbek ≤ fiziksel kök ≤ ilk aero istasyonu sırası sağlanmalı.",
    "longer_proximal_required": "bu şablonda iç parça dış parçadan uzun olmalı.",
    "unsupported_hinge_axis": "bu sürüm yalnız şafta paralel, açıklık çizgisinden geçen menteşe eksenini destekler.",
    "invalid_pose": "katlanma sınırı < başlangıç açısı ≤ açık stop (0°) olmalı.",
    "missing_source": "mekanik girdilerin kaynağını ve niteliğini beyan edin.",
    "unsupported_blade_count": "bu sürüm 1–4 kanadı destekler.",
    "toolchain_invalid": "araç zinciri bildirimi doğrulanamadı.",
    "fold_outside_geometry_envelope": "başlangıç katlanması sürekli kaldırma çizgisinin geometri sınırının ötesinde "
                                      "(RBF menteşe geçişi ve dış parça süpürmesi); daha küçük bir açı seçin. Bu, "
                                      "aerodinamik temsilin seçilen toleranslarla sınırıdır, mekanizma stroku değildir.",
    "outside_admitted_reynolds": "planlanan devir aralığı saklanan polar verisinin Reynolds aralığından çıkıyor; "
                                 "düşük devirli kalkış bu veriyle desteklenmez.",
    "outside_admitted_mach": "planlanan devir/katlanma aralığı saklanan polar verisinin Mach aralığından çıkıyor.",
    "invalid_controls": "çözücü veya şaft hız profili ayarı geçersiz (rampa tasarım devrinin altından başlamalı ve "
                        "simülasyon süresi içinde bitmeli).",
}
DEMO_SOURCE = ("Gösterim varsayımı: 30 g dış parça, menteşeden 55 mm kütle merkezi, 3e-5 kg·m² CG ataleti; "
               "esnek (penaltı) stop. Sahibin pervanesinin ölçülmüş özelliği değildir.")


def _rui():
    from . import research_ui
    return research_ui


def _fmt(x, d=2):
    return _rui()._fmt(x, d)


def readiness_cached(refresh=False):
    key = "_coupled_readiness"
    if refresh or key not in st.session_state:
        st.session_state[key] = tcmod.readiness(hash_executables=False)
    return st.session_state[key]


def _fill_demo():
    """Button callback: runs before the rerun, so widgets are created with these states."""
    values = st.session_state.setdefault("_research_control_values", {})
    for key, value in (("mass", 30.0), ("cg", 55.0), ("inertia", 3.0e-5), ("source", DEMO_SOURCE),
                       ("kind", "demonstration_assumption")):
        st.session_state["coupled_" + key] = value
        values["coupled_" + key] = value


def _mechanics_inputs():
    rui = _rui()

    def num(col, label, key, default, lo, hi, **kw):
        return rui._field(col.number_input, label, "coupled_" + key, default, min_value=lo, max_value=hi, **kw)

    st.button("Gösterim varsayımlarını doldur", key="coupled_fill_demo", on_click=_fill_demo,
              help="Eksik donanım özelliklerini açıkça etiketlenmiş gösterim varsayımlarıyla doldurur.")
    a, b = st.columns(2)
    mass = num(a, "Dış parça kütlesi [g]", "mass", None, .001, 1e5)
    cg = num(b, "Menteşeden kütle merkezi [mm]", "cg", None, 0., 999.)
    inertia = num(a, "Kütle merkezi ataleti, menteşe eksenine paralel [kg·m²]", "inertia", None, 0., 10., format="%.9f")
    kind = rui._choice(b.selectbox, "Değerlerin niteliği", ("demonstration_assumption", "declared_hardware_property"),
                       key="coupled_kind", default="demonstration_assumption",
                       display={"demonstration_assumption": "Gösterim varsayımı",
                                "declared_hardware_property": "Beyan edilen donanım özelliği"}.__getitem__)
    source = rui._field(st.text_input, "Mekanik girdi kaynağı", "coupled_source", "", max_chars=300)
    a, b = st.columns(2)
    fold = num(a, "Başlangıç katlanma açısı [°]", "fold", -5.0, -170., 0.,
               help="Negatif: geriye katlı. 0: tam açık stop. Serbest bırakılana kadar kilitlenir.")
    release = num(b, "Kilidin açılma zamanı [s]", "release", .05, 0., 5.,
                  help="Bu süre boyunca menteşe kilitli kalır (iz gelişimi). 0: başlangıçta serbest.")
    spring = num(a, "Yay [N·m/rad]", "spring", 0., 0., 1e4)
    rest = num(b, "Yay denge açısı [°]", "rest", 0., -180., 180.)
    damping = num(a, "Viskoz menteşe sönümü [N·m·s/rad]", "damping", 0., 0., 1e3, format="%.6f")
    kc = num(b, "Açık stop rijitliği [N·m/rad]", "stop_k", 250., 1e-3, 1e7,
             help="Tek yönlü doğrusal yay–sönümleyici temas yasası (penaltı). Ölçülmüş temas değildir.")
    e = num(a, "Stop geri sekme katsayısı [-]", "stop_e", .5, .01, 1.0)
    st.caption("Kuru sürtünme ve menteşe tahrik momenti bu sürümde dinamik analizde desteklenmez (0 kabul edilir). "
               "Şaft devri öngörülür (sabit veya rampa, aşağıda); tahrik torku bir çıktıdır.")
    if None in (mass, cg, inertia) or not source.strip():
        return None, "Kütle, kütle merkezi, atalet ve kaynak girildiğinde hazırlanabilir."
    try:
        return CoupledMechanics(distal_mass_kg=mass / 1000, distal_cg_from_hinge_m=cg / 1000,
                                distal_inertia_cg_kg_m2=inertia, spring_nm_per_rad=spring,
                                spring_rest_rad=math.radians(rest), hinge_damping_nm_s_per_rad=damping,
                                stop_stiffness_nm_per_rad=kc, stop_restitution=e,
                                initial_fold_rad=math.radians(fold), release_time_s=release,
                                source=source, declaration_kind=kind), None
    except (TypeError, ValueError) as exc:
        return None, str(exc)


def _drive_inputs():
    """Shaft speed history: constant design speed or a prescribed smooth ramp to it."""
    rui = _rui()
    st.markdown("**Şaft hız profili**")
    profile = rui._choice(st.radio, "Profil", ("constant", "ramp"), key="coupled_drive_profile", default="constant",
                          horizontal=True, display={"constant": "Sabit tasarım devri",
                                                    "ramp": "Öngörülen rampa (yumuşak, yarım kosinüs)"}.__getitem__)
    if profile != "ramp":
        return {"drive_profile": "constant"}
    a, b, c = st.columns(3)

    def num(col, label, key, default, lo, hi, **kw):
        return rui._field(col.number_input, label, "coupled_drive_" + key, default, min_value=lo, max_value=hi, **kw)
    rpm0 = num(a, "Rampa başlangıç devri [RPM]", "rpm0", 2200., 1., 1e5)
    t0 = num(b, "Rampa başlangıcı [s]", "t0", .05, 0., 2.)
    T = num(c, "Rampa süresi [s]", "T", .05, .001, 2.)
    st.caption("Devir geçmişi öngörülür (kinematik sınır koşulu); tahrik torku bu geçmişin gerektirdiği tork olarak "
               "çıkar. Motor yasası (tork–devir eğrisi, rotor ataleti) bu sürümde yoktur: ölçülmüş motor verisi gerekir.")
    return {"drive_profile": "ramp", "ramp_start_rpm": rpm0, "ramp_start_s": t0, "ramp_duration_s": T}


def _controls_inputs():
    rui = _rui()
    defaults = CoupledControls()
    drive = _drive_inputs()
    with st.expander("Gelişmiş · çözücü ayarları"):
        a, b = st.columns(2)

        def num(col, label, key, default, lo, hi, **kw):
            return rui._field(col.number_input, label, "coupled_ctl_" + key, default, min_value=lo, max_value=hi, **kw)

        duration = num(a, "Simülasyon süresi [s]", "duration", .125, .001, 2.)
        step = num(b, "Azimut adımı [°]", "step", defaults.azimuth_step_deg, .1, 30.,
                   help="Zaman adımı = adım / Ω. 5° ve altı önerilir (MBDyn büyük dönme adımı hatası).")
        nel = num(a, "Parça başına açıklık elemanı", "nel", defaults.elements_per_segment, 2, 40)
        iters = num(b, "En fazla bağlaşım iterasyonu", "iters", defaults.coupling_max_iterations, 2, 200)
        tol = num(a, "Konum/dönme yakınsama sınırı [m, rad]", "tol", defaults.coupling_position_tol_m, 1e-12, 1e-2, format="%.2e")
        aitken = num(b, "Aitken başlangıç gevşetmesi [-]", "aitken", defaults.aitken_initial_relaxation, .01, 1.)
        particles = num(a, "En fazla iz parçacığı", "particles", defaults.max_wake_particles, 1000, 500000)
        timeout = num(b, "Süre bütçesi [s]", "timeout", defaults.wall_timeout_s, 10., 21600.)
    return CoupledControls(azimuth_step_deg=step, duration_s=duration, elements_per_segment=int(nel),
                           coupling_max_iterations=int(iters), coupling_position_tol_m=tol, coupling_rotation_tol_rad=tol,
                           aitken_initial_relaxation=aitken, max_wake_particles=int(particles), wall_timeout_s=timeout,
                           **drive)


def _token(active, family, mech, ctrl):
    return json.dumps([active.identity, None if family is None else family.stored_version.content_sha256,
                       None if mech is None else asdict(mech), asdict(ctrl)], sort_keys=True)


def render_analysis(active, family, readiness_status, repository, root: Path):
    """Analiz page section."""
    st.markdown("**Dinamik aero-mekanik analiz · DUST–MBDyn–preCICE (isteğe bağlı)**")
    st.caption("Öngörülen şaft devri (sabit veya rampa), rijit iç ve dış parça, eksene paralel ideal katlanma menteşesi, beyan edilen yay/sönüm/stop yasası. "
               "Aerodinamik yükler BEM ile aynı saklanan polar sürümünden DUST kaldırma çizgisiyle hesaplanır. "
               "CFD, FEA, eklem dayanımı veya yorulma değildir.")
    # Before every early return: a fragment not called in a full run stops, and with it progress and 'Durdur'.
    monitor(show_failure=True)
    ready = readiness_cached()
    if ready.status != "ready":
        st.info(ready.message)
        if st.button("Araç zincirini yeniden denetle", key="coupled_recheck"):
            readiness_cached(refresh=True)
            st.rerun()
        return
    st.caption("Araç zinciri: DUST " + ready.identity["versions"]["dust_revision"][:8] + " · MBDyn "
               + ready.identity["versions"]["mbdyn_revision"][:8] + " · preCICE " + ready.identity["versions"]["precice_version"])
    mech, mech_problem = _mechanics_inputs()
    ctrl = _controls_inputs()
    token = _token(active, family, mech, ctrl)
    run_state = st.session_state.get(RUN)
    if run_state is not None and run_state["token"] != token and _poll(Path(run_state["run_dir"])).get("state") not in ("queued", "running"):
        st.session_state.pop(RUN, None)
        run_state = None
    if family is None or readiness_status != "ready":
        st.info("Dinamik analiz, BEM için seçilen ve hazırlığı tamamlanan saklanan polar sürümünü kullanır. Önce yukarıda bir sürüm seçin.")
        return
    if mech_problem:
        st.info(mech_problem)
        return
    try:
        prep = svc.prepare(active, family, repository, mech, ctrl, readiness=tcmod.readiness(hash_executables=True))
    except svc.CoupledPreparationError as exc:
        detail = str(exc).split(": ", 1)[-1] if exc.code == "result_too_large" else None
        st.warning("Dinamik analiz hazırlanamadı: " + (detail or _PREP_TEXT.get(exc.code, "girdileri ve şablonu kontrol edin.")))
        with st.expander("Hazırlık teknik ayrıntısı"):
            st.text(str(exc))
        return
    env = prep.request["c81"]["envelope"]
    pre = prep.request["preflight_no_induction_ranges"]
    lim = svc.supported_duration(prep.case)
    from pyfoldable.coupled.model import shaft_speed
    turns = [shaft_speed(prep.case, (k + 0.5) * prep.case.dt_s)[0] * prep.case.dt_s / (2 * math.pi) for k in range(prep.case.n_steps)]
    revs = sum(turns)
    after = sum(t for k, t in enumerate(turns) if (k + 1) * prep.case.dt_s > prep.case.mechanics.release_time_s)
    st.caption(f"Simülasyon {revs:.1f} devir (serbest bırakmadan sonra {after:.1f} devir) · kayıt tahmini "
               f"{svc.estimated_result_bytes(prep.case) / 2**20:.1f} / {lim['limit_bytes'] / 2**20:.0f} MiB · bu adım ve eleman "
               f"sayısıyla desteklenen en uzun süre {lim['duration_s']:.3f} s ({lim['revolutions']:.1f} devir). "
               + ("Bu bir kayıt boyutu sınırıdır" if lim["limited_by"] == "record_size" else "Bu, süre ayarının üst sınırıdır")
               + ", fiziksel oturma süresi değildir; her kabul edilen pencere saklanır.")
    st.caption(f"Pencere sayısı {prep.case.n_steps} · zaman adımı {prep.case.dt_s * 1000:.4f} ms · "
               f"menteşe ekseni ataleti {prep.case.mechanics.hinge_inertia_kg_m2:.3e} kg·m² · stop sönümü "
               f"{prep.case.mechanics.stop_damping_nm_s_per_rad:.4f} N·m·s/rad.")
    st.caption(f"Tablo kapsamı: α {env['alpha_deg'][0]:.0f}…{env['alpha_deg'][1]:.0f}° · Re {env['reynolds'][0]:.0f}…"
               f"{env['reynolds'][1]:.0f} · Mach {env['mach'][0]:.2f}…{env['mach'][1]:.2f}. İndüksiyonsuz ön tahmin: "
               f"α {pre['alpha_deg'][0]:.2f}…{pre['alpha_deg'][1]:.2f}° · Mach {pre['mach'][0]:.3f}…{pre['mach'][1]:.3f}. "
               "Katlanma hızı uç Mach sayısını artırır; her kabul edilen adım tabloya göre denetlenir.")
    from pyfoldable.coupled import envelope as envmod
    fe = envmod.fold_envelope(prep.case)
    appl = svc.trajectory_applicability(prep.case, env)
    st.caption(envelope_caption(fe, appl))
    sw = appl.get("swing")
    if sw and not (sw["mach_ok"] and sw["reynolds_ok"]):
        st.warning(f"Açılma salınımı uyarısı: dış parça en çok ≈ {appl['fold_rate_bound_rad_s']:.0f} rad/s ile öne savrulabilir "
                   f"(enerji sınırı, aero momenti ihmal); uçta Mach ≤ {sw['mach'][1]:.3f}, Re ≤ {sw['reynolds'][1]:.3g} olabilir — "
                   f"tablo üst sınırı Mach {env['mach'][1]:.2f}, Re {env['reynolds'][1]:.3g}. Tahmin muhafazakârdır; aşılırsa DUST "
                   "durur ve kabul edilen önek kısmi geçmiş olarak saklanır.")
    if mech.declaration_kind == "demonstration_assumption":
        st.caption("Mekanik değerler gösterim varsayımıdır; sonuç ölçülmüş donanımı temsil etmez.")
    busy = run_state is not None and _poll(Path(run_state["run_dir"])).get("state") in ("queued", "running")
    if st.button("Dinamik analizi başlat", type="primary", key="coupled_start", disabled=busy):
        run = svc.start_run(prep, root)
        st.session_state[RUN] = {"run_dir": str(run), "token": token}
        st.rerun()


def _alive(pid) -> bool:
    """Whether the supervisor process named in status.json still exists.
    shortcut: a missing pid (queued, supervisor not started yet) counts as alive and a recycled pid after a reboot
    as alive; 'İzlemeyi bırak' clears such a monitor. Windows os.kill(pid, 0) would terminate the process, so no probe there."""
    if pid is None or os.name != "posix":
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _poll(run: Path) -> dict:
    """svc.poll, but a queued/running run whose supervisor is gone (killed, out of memory, reboot) reads as interrupted."""
    status = svc.poll(run)
    if status.get("state") in ("queued", "running") and not _alive(status.get("supervisor_pid")):
        return {**status, "state": "interrupted", "message": "denetleyici süreç artık çalışmıyor, çalıştırma yarıda kaldı"}
    return status


def monitor(*, show_failure=False):
    """Progress, 'Durdur' and loading of the attached run. A run that ended without a result is reported on Analiz
    only (show_failure), not under every record; a finished, handled run stops the 2 s fragment on other pages."""
    run_state = st.session_state.get(RUN)
    if not run_state:
        return
    if not show_failure:
        status = _poll(Path(run_state["run_dir"]))
        if status.get("state") not in ("queued", "running") and (run_state.get("loaded") or not status.get("result_available")):
            return
    _progress(show_failure)


@st.fragment(run_every=2.0)
def _progress(show_failure=True):
    run_state = st.session_state.get(RUN)
    if not run_state:
        return
    run = Path(run_state["run_dir"])
    status = _poll(run)
    state = status.get("state", "unknown")
    n, k = status.get("n_windows") or 1, status.get("windows_accepted") or 0
    if state in ("queued", "running"):
        st.progress(min(1.0, k / n), text=f"Çalışıyor · {k}/{n} pencere · {status.get('elapsed_s', 0)} s · aşama {status.get('phase', '…')}")
        a, b = st.columns(2)
        if a.button("Durdur", key="coupled_cancel"):
            svc.cancel(run)
        b.button("İzlemeyi bırak", key="coupled_detach", on_click=st.session_state.pop, args=(RUN, None),
                 help="Çalıştırma sürer; ilerleme bu oturumda artık gösterilmez. Kayıtlar sayfasından yeniden izlenebilir.")
        return
    if status.get("result_available") and not run_state.get("loaded"):
        try:
            row = svc.load_result(run)
        except (ValueError, OSError) as exc:
            st.error("Sonuç dosyası doğrulanamadı: " + str(exc))
            run_state["loaded"] = True
            return
        save(row)
        st.session_state[ACTIVE] = (run_state["token"], row["result_sha256"])
        run_state["loaded"] = True
        st.session_state["_research_next_page"] = "Sonuçlar"
        st.session_state["research_results_kind"] = "Dinamik bağlaşık"
        st.rerun(scope="app")
    elif not status.get("result_available") and show_failure:
        st.error(f"Çalıştırma {state} durumunda sonuçsuz bitti: {status.get('message', '')}. Ham çıktılar: {run}")


def _archive(row) -> bytes:
    """Compressed record, computed once per record and session (not on every rerun)."""
    cache = st.session_state.setdefault("_coupled_archive_cache", {})
    key = row["result_sha256"]
    if key not in cache:
        cache.clear()
        cache[key] = svc.record_archive_bytes(row)
    return cache[key]


def _xz_export(col, row, name):
    """Denser .json.xz archive, encoded only on request (seconds) and kept for this record."""
    cache = st.session_state.setdefault("_coupled_xz_cache", {})
    key = row["result_sha256"]
    if key not in cache:
        slot = col.empty()  # the request button disappears in the same run once the archive exists
        if slot.button("Daha küçük arşivi hazırla (.json.xz)", key="coupled_prepare_xz",
                       help="Aynı mühürlü kaydın kayıpsız xz hâli; gzip’ten ~%20 küçük. Hazırlanması birkaç saniye sürer."):
            with st.spinner("xz arşivi hazırlanıyor…"):
                cache.clear()
                cache[key] = svc.record_xz_bytes(row)
            slot.empty()
        else:
            return
    data = cache[key]
    col.download_button("Sıkıştırılmış kayıt (.json.xz)", data, name + ".json.xz", "application/x-xz")
    limit = _rui().restore_upload_limit_bytes()
    col.caption(f".json.xz {len(data) / 1e6:.2f} MB · yükleme sınırı {limit / 2**20:.0f} MB (sunucu ayarı)"
                + (" · yüklenebilir" if _rui().restore_archive_fits(len(data))
                   else " · sınırı aşıyor: yerel çalıştırma klasöründen açın"))


def _exports(cols, row, name):
    """JSON, CSVs and the VTK zip take seconds on long records (VTK 8-18 s): built on request, kept for this record."""
    b, c, d = cols
    cache = st.session_state.setdefault("_coupled_export_cache", {})
    key = row["result_sha256"]
    if key not in cache:
        slot = b.empty()
        if not slot.button("Dışa aktarma dosyalarını hazırla", key="coupled_prepare_exports",
                           help="Sonuç JSON’u, zaman serisi ve radyal CSV, ParaView (VTK) paketi. Uzun kayıtlarda "
                                "birkaç saniye sürer; bu kayıt için bir kez hazırlanır."):
            return
        with st.spinner("Dışa aktarma dosyaları hazırlanıyor…"):
            cache.clear()
            cache[key] = {"json": views.saved_json(row)}
            if row["series"]:
                cache[key].update(series=views.series_csv(row), radial=views.radial_csv(row), vtk=views.vtk_zip(row))
        slot.empty()
    files = cache[key]
    b.download_button("Sonuç JSON’u", files["json"], name + ".json", "application/json")
    if "vtk" in files:
        b.download_button("Zaman serisi CSV", files["series"], name + "_zaman.csv", "text/csv")
        c.download_button("Radyal CSV", files["radial"], name + "_radyal.csv", "text/csv")
        d.download_button("ParaView (VTK)", files["vtk"], name + "_vtk.zip", "application/zip",
                          help="Kabul edilen MBDyn durumlarında rijit parça yüzeyleri ve .pvd zaman listesi; geçerli "
                               "önek dışındaki pencereler dosya başlığında ve README’de işaretlidir.")


def save(row, *, imported=False):
    history = st.session_state.setdefault(HISTORY, ())
    if row["result_sha256"] in retained():
        return "duplicate"
    if len(history) >= MAX_HISTORY:
        history = history[1:]
    st.session_state[HISTORY] = (*history, (views.saved_json(row), imported))
    return "saved"


def retained():
    """History records parsed once each (records reach tens of MB); the raw strings key the cache, and a str
    keeps its hash, so later lookups are cheap. Callers must not mutate the returned rows.
    shortcut: all MAX_HISTORY parsed records stay in memory (a few hundred MB for six 720-window records); cache only
    the active record if MAX_HISTORY grows or memory hurts."""
    history = st.session_state.get(HISTORY, ())
    cache = st.session_state.get("_coupled_parsed", {})
    parsed = {raw: cache[raw] if raw in cache else json.loads(raw) for raw, _ in history}
    st.session_state["_coupled_parsed"] = parsed
    return {parsed[raw]["result_sha256"]: (parsed[raw], imp) for raw, imp in history}


def invalidate(active, family):
    """Called on every render: input changes clear the active coupled result, never history."""
    current = st.session_state.get(ACTIVE)
    if current is None or current[0] is None:  # opened from history: never relabelled or cleared by edits
        return
    token_identity = json.loads(current[0])[:2]
    now = [None if active is None else active.identity, None if family is None else family.stored_version.content_sha256]
    if token_identity != now:
        st.session_state.pop(ACTIVE, None)


def active_result():
    current = st.session_state.get(ACTIVE)
    if current is None:
        return None
    rec = retained().get(current[1])
    return None if rec is None else rec[0]


_RANGE_NOTE = ("Eksen aralıkları ilk çeyrek turdan sonraki verilere göre seçilir: kaldırma çizgisi izinin ani başlangıç "
               "geçişi çizilir ama ölçeği belirlemez; noktalı çizgiler geçerli önek dışındaki pencerelerdir.")
_RADIAL_LABELS = {"alpha_deg": "α [°]", "reynolds": "Re [-]", "mach": "Mach [-]", "cl": "c_l [-]",
                  "dFz_n": "Eleman itkisi dF_z [N] (eleman başına)"}


def _radial_window(row):
    """Radial window slider. Its widget state is dropped on other tabs and pages, so the last choice per record is
    mirrored outside it (rui._choice passes index=, which select_slider does not take). Opens at the last valid window."""
    key, last_valid = "coupled_radial_window", row["execution"]["valid_prefix_windows"]
    windows = [r["window"] for r in row["series"]]
    memory = st.session_state.get("_coupled_radial_memory", (None, None))
    if st.session_state.get(key) not in windows:
        st.session_state[key] = memory[1] if memory[0] == row["result_sha256"] and memory[1] in windows else \
            max([w for w in windows if w <= last_valid], default=windows[0])
    w = st.select_slider("Pencere", options=windows, key=key,
                         format_func=lambda v: f"{v} (geçerli önek dışı)" if v > last_valid else str(v))
    st.session_state["_coupled_radial_memory"] = (row["result_sha256"], w)
    return w


def render_result(row, *, imported=False, root: Path | None = None):
    rui = _rui()
    ex = row["execution"]
    i = row["request"]["research"]["inputs"]
    kind, text = _STATUS_TEXT.get(ex["status"], ("warning", ex["status"]))
    failed = [c for c in row["checks"] if c["passed"] is False]  # None means not assessed, not failed
    getattr(st, "warning" if failed and kind == "success" else kind)(text)
    if failed:
        st.warning("Kaydın kendi sayısal denetimlerinden geçmeyenler: "
                   + "; ".join(f"{c['name']} = {_num(c['value'])} (sınır {_num(c['limit'])})" for c in failed)
                   + ". Ayrıntı: Teknik ayrıntılar.")
    st.markdown(f"**{i['profile']} · {_fmt(i['rpm'], 0)} RPM · {_fmt(i['inflow_m_s'], 2)} m/s · dinamik bağlaşık analiz**")
    if imported:
        st.caption("Dosyadan açılan kayıt · çözücü yeniden çalıştırılmadı; iç tutarlılık denetlendi.")
    m = row["request"]["mechanics"]
    if m["declaration_kind"] == "demonstration_assumption":
        st.caption("Mekanik girdiler gösterim varsayımıdır: " + m["source"])
    valid = row["series"][:ex["valid_prefix_windows"]]
    if valid:
        th = [r["theta_deg"][0] for r in valid]
        cs0 = row["run_definition"]["case"]
        per_rev = max(1, int(round(2 * math.pi / (cs0["omega_rad_s"] * cs0["dt_s"]))))
        # one full revolution averages out the azimuthal ripple; shorter histories show the last window
        span = valid[-per_rev:] if len(valid) >= per_rev else valid[-1:]
        tag = "Son tam devir ort." if len(valid) >= per_rev else "Son pencere"

        def mean(key):
            return sum(r[key] for r in span) / len(span)
        a, b, c, d = st.columns(4)
        a.metric(f"{tag} itki [N]", _fmt(mean("thrust_n"), 3))
        b.metric(f"{tag} aero şaft torku [N·m]", _fmt(mean("aero_shaft_torque_nm"), 3))
        c.metric(f"{tag} tahrik torku [N·m]", _fmt(mean("drive_torque_nm"), 3))
        d.metric("θ en küçük / en büyük [°]", f"{_fmt(min(th), 1)} / {_fmt(max(th), 1)}")
        contact = any(any(r["contact_active"]) for r in valid)
        cs = row["run_definition"]["case"]
        t_end = ex["valid_prefix_windows"] * cs["dt_s"]
        turns = [r["rpm"] / 60.0 * cs["dt_s"] for r in valid]  # accepted speed history (constant or ramp)
        after_rel = sum(t for r, t in zip(valid, turns) if r["time_s"] > m["release_time_s"])
        st.caption(f"Kısa analiz penceresi: {sum(turns):.1f} devir, serbest bırakmadan sonra "
                   f"{after_rel:.1f} devir ({t_end:.4f} s). Son pencere değerleri "
                   "uzun süreli oturmuş performans değildir; ortalamalar için tam devir pencerelerini kullanın.")
        st.caption(f"Kabul edilen pencereler {ex['windows_accepted']}/{ex['windows_planned']} · geçerli önek {ex['valid_prefix_windows']} · "
                   f"stop teması {'oluştu' if contact else 'oluşmadı'} · bağlaşım iterasyonu "
                   f"{min(r['coupling_iterations'] for r in valid)}–{max(r['coupling_iterations'] for r in valid)}.")
    a, b, c, d = st.columns(4)
    name = f"pyfoldable_dinamik_{i['profile']}_{row['result_sha256'][:8]}"
    a.download_button("Sıkıştırılmış kayıt (.json.gz)", _archive(row), name + ".json.gz", "application/gzip",
                      help="Aynı mühürlü kaydın kayıpsız gzip hâli; Karşılaştırma / kayıtlar sayfasından açılabilir.")
    _xz_export(a, row, name)
    _exports((b, c, d), row, name)
    if not row["series"]:
        _details(row)
        return
    tab = rui._choice(st.radio, "Grafik", ("Menteşe", "Yükler", "Güç", "Kapsam ve yakınsama", "Radyal", "3B oynatma",
                                           "Akış ve tepki", "Bağlantı yükleri", "Mühendislik değerlendirmesi"),
                      key="coupled_tab", default="Menteşe", horizontal=True)
    if tab == "Menteşe":
        rui._plot(views.time_figure(row, (("theta_deg", "θ"),), "Katlanma açısı θ [°]", per_blade=True), "coupled_theta")
        rui._plot(views.time_figure(row, (("theta_rate_rad_s", "θ̇"),), "Menteşe açısal hızı [rad/s]", per_blade=True), "coupled_rate")
        rui._plot(views.time_figure(row, (("hinge_aero_torque_nm", "Aerodinamik"), ("hinge_law_torque_nm", "Yay+sönüm+stop"),
                                          ("centrifugal_hinge_moment_derived_nm", "Merkezkaç (türetilmiş tanı)")),
                                    "Dış parçaya menteşe momenti [N·m]", per_blade=True), "coupled_hinge_m")
        st.caption("Merkezkaç momenti modele ayrıca eklenmez; dönen çerçevede −mΩ²r_h c_g sinθ olarak türetilmiş bir tanıdır. "
                   "Stop teması penaltı yasasıdır; açının 0°’yi aşması tanımlı esneme (penetrasyon) miktarıdır. "
                   "Düz, kesikli ve noktalı-kesikli çizgiler kanatları ayırır. " + _RANGE_NOTE)
    elif tab == "Yükler":
        rui._plot(views.time_figure(row, (("thrust_n", "İtki"),), "İtki [N]"), "coupled_thrust")
        rui._plot(views.time_figure(row, (("aero_shaft_torque_nm", "Aerodinamik şaft torku"), ("drive_torque_nm", "Tahrik (tepki) torku")),
                                    "Tork [N·m]", split=True), "coupled_torque")
        st.caption("Tahrik torku, sabit devri koruyan MBDyn tepki torkudur; katlanma sırasında atalet etkilerini de içerir ve "
                   "aerodinamik torktan ayrıdır; stop darbesi sıçramaları aerodinamik torktan iki mertebe büyük olduğu "
                   "için ayrı eksende çizilir. " + _RANGE_NOTE)
    elif tab == "Güç":
        rui._plot(views.time_figure(row, (("aero_power_absorbed_w", "Aerodinamik güç (havaya aktarılan)"), ("drive_power_w", "Tahrik gücü")),
                                    "Güç [W]", split=True), "coupled_power")
        st.caption("Aerodinamik güç ve tahrik gücü ayrı eksenlerdedir. " + _RANGE_NOTE)
    elif tab == "Kapsam ve yakınsama":
        for q in ("alpha", "re", "mach"):
            rui._plot(views.coverage_figure(row, q), "coupled_cov_" + q)
        rui._plot(views.iterations_figure(row), "coupled_iters")
        st.caption("Sorgulanan değerler, her kabul edilen pencerede kaldırma çizgisinin son iterasyonundaki kesit durumlarıdır. "
                   "DUST tablo dışı α veya Mach’ta durur; Reynolds dışına doğrusal ekstrapolasyon yapar ve burada denetlenir.")
    elif tab == "Radyal":
        w = _radial_window(row)
        if w > ex["valid_prefix_windows"]:
            st.warning(f"Pencere {w} geçerli önek dışı (kapsam, yakınsama veya katlanma sınırı aşıldıktan sonra); "
                       "değerleri tamamlanmış sonuç değildir.")
        rows = views.radial_rows(row, w)
        field = rui._choice(st.radio, "Büyüklük", ("alpha_deg", "reynolds", "mach", "cl", "dFz_n"), key="coupled_radial_field",
                            default="alpha_deg", horizontal=True,
                            display={"alpha_deg": "α", "reynolds": "Re", "mach": "Mach", "cl": "cl", "dFz_n": "Eleman itkisi"}.__getitem__)
        rui._plot(views.radial_figure(rows, field, _RADIAL_LABELS[field]), "coupled_radial_plot")
        with st.expander("Radyal veri tablosu"):
            st.dataframe(rows, hide_index=True, **figure_style.dataframe_width_kwargs())
    elif tab == "Akış ve tepki":
        _flow_tab(row, root)
    elif tab == "Mühendislik değerlendirmesi":
        _assessment_tab(row)
    elif tab == "Bağlantı yükleri":
        from . import fold_cycle_ui
        fold_cycle_ui.coupled_loads_tab(row, root)
    else:
        from . import blade_ui
        blade_ui.coupled_blade_tab(row, root)
        with st.expander("Eski hızlı oynatma (renksiz, 24 noktalı kesit)"):
            # an expander body always runs; the toggle keeps the costly playback out of every rerun
            fig = views.playback_figure(row) if st.toggle("Eski oynatmayı oluştur", key="coupled_legacy_playback") else None
            if fig is not None:
                rui._plot(fig, "coupled_playback")  # scroll zoom disabled, like the other workspace figures
        st.caption("Kabul edilen MBDyn durumlarında rijit parça yüzeyleri (katalog kesiti, beyan edilen istasyonlar). "
                   "Basınç veya gerilme alanı çözülmediği için gösterilmez. 3B için WebGL gerekir.")
    _details(row)


def envelope_caption(fe, appl) -> str:
    """Fold limit of the aerodynamic representation (not the mechanism's travel) and the trajectory check."""
    reason = "RBF menteşe geçişinde kiriş kısalması ≤ %2" if fe["limited_by"] == "junction_chord" else "dış parça süpürmesi ≤ 25°"
    return (f"Aerodinamik temsil sınırı (katlanma): {fe['fold_limit_deg']:.1f}° ({reason}); bu, sürekli kaldırma "
            "çizgisinin seçilen toleranslarla sınırıdır, mekanizma stroku değildir. Bu sınırın ötesindeki pencereler geçerli "
            "öneki sonlandırır. Yörünge (başlangıç devrinden tasarım devrine, başlangıç katlanmasından açığa) için "
            f"indüksiyonsuz durum: Re {'tablo içinde' if appl['reynolds_ok'] else 'tablo dışında'} · Mach "
            f"{'tablo içinde' if appl['mach_ok'] else 'tablo dışında'} · α "
            f"{'tablo içinde' if appl['alpha_ok'] else 'tablo dışında olabilir (indüksiyon değiştirir; çalışma denetler)'}.")


_CLASS_LABEL = {"comparative": "Karşılaştırmalı", "preliminary": "Ön karar", "illustrative": "Gösterim",
                "numerical_check": "Sayısal denetim"}


def _num(value):
    if value is None:
        return "—"
    mag = abs(value)
    text = f"{value:.1f}" if mag >= 100 else f"{value:.3f}" if mag >= 1 else f"{value:.4g}"
    return text.replace(".", ",")


def _assessment_tab(row):
    """What this record can support: comparative, preliminary (scales with declared mechanics), illustrative."""
    from pyfoldable.coupled import assessment
    rows = assessment.output_classes(row)
    st.markdown("**Bu kayıt neyi destekler?** Her çıktı, onu neyin belirlediğine göre sınıflandırılır. "
                "Fiziksel nitelendirme yoktur; sınıflar sayısal ve model güvenilirliğini ayırır.")
    if row["request"]["mechanics"]["declaration_kind"] == "demonstration_assumption":
        st.caption("Mekanik girdiler gösterim varsayımıdır: “Ön karar” satırları ölçeklenme ilişkisini ve büyüklük "
                   "mertebesini gösterir; boyutlandırma değeri için ölçülmüş kütle, kütle merkezi, atalet, stop ve tahrik "
                   "özellikleri gerekir (ölçüm planı: docs/prototype_measurement_plan.md).")
    if not rows:
        st.info("Bu kayıtta değerlendirilecek geçerli pencere yok.")
        return
    st.dataframe([{"Çıktı": r["label"], "Değer": _num(r["value"]), "Birim": r["unit"], "Sınıf": _CLASS_LABEL[r["class"]],
                   "Belirleyen": r["governed_by"]} for r in rows], hide_index=True, **figure_style.dataframe_width_kwargs())
    st.caption(" · ".join(f"**{_CLASS_LABEL[k]}:** {v.split(': ', 1)[1]}" for k, v in assessment.CLASSES.items()))
    ev = assessment.contact_events(row)
    sh = assessment.shaft_exchange(row)
    if ev:
        e = ev[0]
        res = e["impulse_balance_relative_residual"]
        resolved = res is not None and res < 0.02
        st.caption(f"Temas boyunca itme dengesi J_hΔθ̇ = ∫ΣM dt kalıntısı {_num(res)} (kanat 1). "
                   + ("Noktasal temas fazı kalıntısı ise merkezi farkı türevlenemeyen stop yasasının sıçraması üzerinden "
                      "aldığı için büyük olabilir; itme dengesi temasın bu kayıtta çözüldüğünü gösterir. " if resolved else
                      "İtme dengesi de büyük: temas fazı bu kayıtta yetersiz çözülmüş olabilir; temas yüklerini kullanmayın. ")
                   + f"Çarpma enerjisi merkezkaç sınırının {_num(e['energy_ratio'])} katı: enerji J_h’den bağımsızdır, "
                   "statik moment m·c_g ve Ω belirler.")
    if sh:
        st.caption(f"Açılma salınımında mile {_num(sh['swing_impulse_n_m_s'])} N·m·s ({_num(sh['swing_duration_s'] * 1000)} ms), "
                   f"temas boyunca {_num(sh['angular_impulse_n_m_s'])} N·m·s ({_num(sh['exchange_duration_s'] * 1000)} ms; "
                   f"eşdeğer ortalama {_num(sh['equivalent_mean_torque_nm'])} N·m) açısal itme aktarılır; ikisi zıt işaretlidir. "
                   "Tepe tahrik torku sonsuz rijit öngörülen devrin ve varsayılan stopun sonucudur; gerçek tahrikte bu itmeler, "
                   "rotor ataleti ve mil burulma rijitliğine göre devir değişimine ve burulma yüküne dönüşür.")


FLOW_CACHE = "_coupled_flow_cache"
FLOW_WINDOW = "coupled_flow_window"
_FLOW_HELP = (
    "**Hesaplanan (DUST):** girdap parçacıklarının konumu ve şiddeti (α), örtük panel izinin ilk sırası ve "
    "y = 0 düzlemindeki hız — dust_post’un DUST çekirdekleriyle kaldırma çizgileri, panel izi ve parçacıklardan "
    "hesapladığı indüklenmiş hız artı serbest akım; bir girdap modeli hızıdır, CFD alanı değildir. "
    "**Yeniden oluşturulan:** kanat yüzeyleri (katalog kesiti, MBDyn durumlarında); DUST’un kaldırma çizgisi paneli "
    "çeyrek kirişten bir kiriş boyu geride biter; ilk iz sırası çizilen firar kenarının 0,25 kiriş arkasındadır (ölçüldü). "
    "**Çözülmeyen:** sınır tabakası, yüzey basıncı, parçacık çekirdeğinden küçük girdap yapısı, göbek/menteşe "
    "aralığı akışı, yapısal şekil değiştirme.")
_RBF_NOTE = ("Bilinen RBF farkı (sürekli kaldırma çizgisi, continuous_rbf): DUST’un rbf kolu kaldırma çizgisi gövde "
             "hızını kiriş başı çizgisinde değerlendirir; kilitli-açık 5° karşılaştırmada itki bağımsız DUST’tan −%1,4 "
             "düşüktür ve kök bölgesinde bağlı dolaşım birkaç yüzde zayıftır. Belirli bir durumdaki kanat geometrisi "
             "kesindir; iz şiddeti ve indüklenmiş hız bu yanlılığı taşır, parçacık konumları da (bu hızla taşındıkları "
             "için) dolaylı etkilenir. Katlanma sırasındaki büyüklüğü ölçülmedi.")
_SPLIT_NOTE = ("Bu kayıt eski iki çizgili düzendedir (split_rigid): her kanat parçasının serbest uç girdapları menteşede "
               "buluşur ve sıfırdan farklı katlanmada sahte bir girdap çifti bırakır; serbest bırakma sonrası itki artışı "
               "bu düzenin hatasıdır (tasarım belgesi §9). Yakın iz grafiğinde menteşe bandına bakın.")


def _flow(row, root):
    """Verified flow companion of this record (cached per record and file version in the session)."""
    from pyfoldable.coupled import flow
    d = svc.local_run_dir(root, row) if root is not None else None
    if d is None:
        raise flow.FlowCompanionError("no_run_folder", "Bu kaydın çalıştırma klasörü bu bilgisayarda yok; akış verisi ham "
                                                       "DUST çıktılarından üretilir ve sonuç dosyasıyla taşınmaz.")
    npz, man = flow.companion_dir(d) / "flow_companion.npz", flow.companion_dir(d) / "flow_companion.json"
    stamp = ((row["result_sha256"], npz.stat().st_mtime_ns, npz.stat().st_size, man.stat().st_mtime_ns, man.stat().st_size)
             if npz.is_file() and man.is_file() else None)
    cache = st.session_state.setdefault(FLOW_CACHE, {})
    if stamp is not None and cache.get("stamp") == stamp:
        return cache["fc"]
    fc = svc.load_flow(root, row)
    cache.clear()
    cache.update(stamp=stamp, fc=fc)
    return fc


def _flow_build(row, root, label, key):
    """Explicit extraction (or re-extraction) of the flow companion; the regular-stride frame count is bounded by
    the companion size limit (build_flow refuses more), the dense release span and the events are always added."""
    from pyfoldable.coupled import flow
    ready = readiness_cached()
    if ready.status != "ready":
        st.caption("Akış verisini hazırlamak için DUST araç zinciri gerekir: " + ready.message)
        return
    last = max(2, int(row["execution"]["valid_prefix_windows"]))
    top = max(2, min(last, flow.MAX_INFLATED_BYTES // svc.flow_frame_bytes_bound(row)))
    frames = st.number_input("Düzenli adımlı kare sayısı (salınım bölgesinin sık kareleri ve olaylar ayrıca eklenir)",
                             min_value=2, max_value=top, value=min(81, top), step=10,
                             key="coupled_flow_frames_" + row["result_sha256"][:12])
    if st.button(label, key=key, help="Seçilen pencerelerde girdap parçacıklarını ve panel izini okur, dust_post ile "
                                      "y = 0 düzleminde hızı hesaplar; 81 karede ana koşu için ≈ 35 s ve ≈ 35 MB, "
                                      "süre ve boyut kare sayısıyla artar."):
        with st.spinner("Akış verisi çıkarılıyor…"):
            try:
                svc.build_flow(root, row, max_frames=int(frames), readiness=tcmod.readiness(hash_executables=True))
            except (flow.FlowCompanionError, OSError, ValueError) as err:
                st.error("Akış verisi hazırlanamadı: " + str(err))
                return
        st.session_state.pop(FLOW_CACHE, None)
        st.rerun()


def _flow_tab(row, root):
    from pyfoldable.coupled import flow
    st.caption(_FLOW_HELP)
    try:
        fc = _flow(row, root)
    except flow.FlowCompanionError as exc:
        if exc.code in ("missing", "checksum", "malformed", "source_mismatch", "other_record", "unsupported", "too_large"):
            (st.info if exc.code == "missing" else st.error)(str(exc).split(": ", 1)[-1])
            _flow_build(row, root, "Akış verisini hazırla (kayıtlı DUST çıktılarından; çözücü çalışmaz)", "coupled_flow_build")
        else:
            st.info(str(exc).split(": ", 1)[-1])
        return
    ev = flow.events(row)
    windows = fc.windows.tolist()
    valid = row["series"][:row["execution"]["valid_prefix_windows"]]
    by_w = {r["window"]: r for r in valid}
    if st.session_state.get(FLOW_WINDOW) not in windows:
        st.session_state[FLOW_WINDOW] = flow.nearest_frame(fc, ev.get("first_contact", windows[-1]))

    def jump():
        key = st.session_state.get("coupled_flow_event")
        if key in ev:
            st.session_state[FLOW_WINDOW] = flow.nearest_frame(fc, ev[key])
        st.session_state["coupled_flow_event"] = None  # the same event can be chosen again later
    names = {k: f"{views.EVENT_LABELS[k]} · pencere {w}" for k, w in ev.items()}
    a, b = st.columns([1, 3])
    a.selectbox("Olaya git", list(names), format_func=names.__getitem__, key="coupled_flow_event", on_change=jump,
                index=None, placeholder="Olay seçin")
    w = b.select_slider("Pencere (akış verisi olan kabul edilmiş pencereler)", options=windows, key=FLOW_WINDOW)
    r = by_w[w]
    phase = ("kilitli (serbest bırakma öncesi)" if r["latch_active"] else
             "stop temasında" if any(r["contact_active"]) else "serbest salınım")
    p, _, _ = fc.particles(w)
    m = st.columns(5)
    m[0].metric("Zaman [s]", f"{r['time_s']:.4f}")
    m[1].metric("θ [°]", " / ".join(_fmt(x, 2) for x in r["theta_deg"]))
    m[2].metric("İtki [N]", _fmt(r["thrust_n"], 2))
    m[3].metric("Menteşe aero momenti [N·m]", _fmt(r["hinge_aero_torque_nm"][0], 3))
    m[4].metric("Girdap parçacığı", f"{len(p)}")
    st.caption(f"Durum: {phase} · θ̇ {_fmt(r['theta_rate_rad_s'][0], 1)} rad/s · aero şaft torku "
               f"{_fmt(r['aero_shaft_torque_nm'], 3)} N·m · tahrik torku {_fmt(r['drive_torque_nm'], 3)} N·m.")
    show_plane = st.toggle("Hız düzlemini 3B sahnede göster", value=True, key="coupled_flow_plane")
    rui = _rui()
    from . import blade_ui
    try:
        _, mesh = blade_ui.coupled_spec_mesh(row)
        fields, crange, frame = blade_ui.field_controls(row, "coupled_flow", w, allow_none=True)
        rui._plot(views.flow_blade_scene(row, fc, w, mesh, fields=fields, crange=crange, rotor_fixed=frame == "rotor",
                                         show_plane=show_plane), "coupled_flow_scene")
        st.caption("Kanatlar (MBDyn gövde durumları), kanattaki renk (DUST elemanları), girdap parçacıkları, panel izi ve "
                   "hız düzlemi aynı kabul edilen pencereye aittir. Kanat renk ölçeği ve hız düzleminin ölçeği "
                   "(indüklenmiş eksenel hız −w−V∞, aşağıdaki 2B eksenel grafikle aynı renk aralığı) tüm pencerelerde "
                   "sabittir. "
                   + ("Rotorla birlikte görünümde iz ve düzlem de rotor açısı kadar döndürülür." if frame == "rotor" else
                      "Dönen görünüm laboratuvar çerçevesidir."))
    except (ValueError, KeyError) as exc:
        st.caption("Kanat yüzeyi bu kayıttan oluşturulamadı (" + str(exc) + "); eski sahne gösteriliyor.")
        rui._plot(views.flow_scene_figure(row, fc, w, show_plane=show_plane), "coupled_flow_scene")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Hız, y = 0 düzlemi (dust_post)**")
        comp = rui._choice(st.radio, "Bileşen", tuple(views.PLANE_COMPONENTS), key="coupled_flow_component",
                           default="axial", horizontal=True,
                           display={"axial": "Eksenel", "swirl": "Dönme (swirl)", "radial": "Radyal"}.__getitem__)
        a, b = st.columns(2)
        vectors = a.toggle("Hız vektörleri", value=False, key="coupled_flow_vectors")
        lines = b.toggle("Akım çizgileri", value=False, key="coupled_flow_streamlines")
        rui._plot(views.flow_plane_figure(row, fc, w, component=comp, vectors=vectors, streamlines=lines),
                  "coupled_flow_plane_fig")
        st.caption("dust_post’un DUST girdap modelinden hesapladığı hız (CFD değildir). Eksenel: serbest akım çıkarılmış "
                   "indüklenmiş hız −w−V∞ (aşağı, itkiye ters +); dönme: +Ω yönündeki teğetsel hız; radyal: dışa. Renk "
                   "ölçeği sıfırda ortalanır ve bu kaydın tüm akış karelerinde aynıdır. Düzlem laboratuvar çerçevesinde sabittir; "
                   "kanatlar her yarım turda içinden geçer. Vektörler ve akım çizgileri yalnız düzlem içi (v_x, v_z) "
                   "bileşenleriyle, anlık hız alanından çizilir; 3B parçacık yörüngesi değildir. Kanat çizgisine çok "
                   "yakın noktalarda çekirdek düzenlemesi etkilidir.")
    with c2:
        st.markdown("**Yakın iz şiddeti, yarıçapa göre**")
        ref = flow.nearest_frame(fc, ev["release"] - 1) if "release" in ev else windows[0]
        rui._plot(views.wake_radial_figure(row, fc, w, ref), "coupled_flow_radial")
        st.caption("Diskin yarım uç yarıçapı altına kadar parçacık şiddeti toplamı (Σ|α|): kanadın girdap bıraktığı "
                   "yarıçaplar (uç ve kök girdapları; menteşe yarıçapı işaretli). Referans son kilitli karedir; iz o anda "
                   "hâlâ gelişmektedir, bu yüzden fark yalnız serbest bırakmanın etkisi değildir.")
    rui._plot(views.response_timeline_figure(row, w, ev), "coupled_flow_timeline")
    st.caption("Camgöbeği çizgi seçili pencere; noktalı çizgiler olaylardır. Eksen aralıkları ilk çeyrek turdan sonraki "
               "verilere göre seçilir: kaldırma çizgisi izinin ani başlangıç geçişi (ilk pencereler) çizilir ama ölçeği "
               "belirlemez. Tork ve menteşe satırları %1–99 aralığına ölçeklenir; stop darbesindeki kısa tepki "
               "sıçramaları çizilir ama eksenden taşar. Tahrik torku sıçraması, devri öngörülen (sonsuz rijit) "
               "şaftın darbeye tepkisidir ve zaman adımına bağlıdır; şaft yükü tahmini değildir.")
    topology = row["run_definition"]["case"]["controls"].get("aero_topology", "split_rigid")
    st.caption(_RBF_NOTE if topology == "continuous_rbf" else _SPLIT_NOTE)
    with st.expander("Akış verisi kimliği ve ParaView"):
        st.json({"windows": len(windows), "particles_total": fc.manifest["particles_total"],
                 "npz_sha256": fc.manifest["npz"]["sha256"], "dust_post_sha256": fc.manifest["dust_post"]["sha256"],
                 "result_sha256": fc.manifest["result_sha256"], "plane": fc.manifest["plane"]}, expanded=False)
        cache = st.session_state.setdefault("_coupled_flow_vtk", {})
        key = fc.manifest["npz"]["sha256"]
        if key not in cache:
            if st.button("ParaView akış paketini hazırla", key="coupled_flow_vtk_prepare",
                         help="Parçacıklar, hız düzlemi ve kanat yüzeyleri; .pvd zaman koleksiyonları (≈ 40 MB)."):
                with st.spinner("ParaView paketi hazırlanıyor…"):
                    cache.clear()
                    cache[key] = views.flow_vtk_zip(row, fc)
        if key in cache:
            st.download_button("ParaView akış paketi (.zip)", cache[key],
                               f"pyfoldable_akis_{row['result_sha256'][:8]}.zip", "application/zip")
        st.caption(f"Akış verisi {len(windows)} kabul edilmiş pencerede var; aradaki pencereler için kare sayısını "
                   "artırıp yeniden hazırlayın (mevcut akış verisinin yerine geçer).")
        _flow_build(row, root, "Akış verisini bu kare sayısıyla yeniden hazırla", "coupled_flow_rebuild")


def _details(row):
    with st.expander("Teknik ayrıntılar · denetimler, kimlikler, sürümler"):
        st.dataframe([{"Denetim": c["name"], "Değer": c["value"], "Sınır": c["limit"], "Geçti": c["passed"], "Anlamı": c["meaning"]}
                      for c in row["checks"]], hide_index=True, **figure_style.dataframe_width_kwargs())
        st.json({"execution": row["execution"], "toolchain": row["request"]["toolchain"],
                 "aero_admission": {k: v for k, v in row["request"]["aero_admission"].items() if k != "tables"},
                 "c81": {k: v for k, v in row["request"]["c81"].items() if k != "text"},
                 "case": row["run_definition"]["case"], "deck": row["request"]["deck"],
                 "raw_outputs_run_id": row["raw_outputs"]["run_id"], "scope": row["scope"],
                 "physical_qualification": row["physical_qualification"]}, expanded=False)


def _local_runs(root: Path, limit=12):
    base = svc.runs_root(root)
    if not base.is_dir():
        return []
    runs = sorted((p for p in base.iterdir() if (p / "result.json").is_file()), key=lambda p: p.name, reverse=True)
    return runs[:limit]


def _attach(run_dir):
    """Button callback: monitor a detached run again; token None treats its result like one opened from history."""
    st.session_state[RUN] = {"run_dir": run_dir, "token": None}


def render_history(root: Path | None = None):
    records = retained()
    st.markdown("**Dinamik bağlaşık sonuçlar (zamana bağlı DUST–MBDyn–preCICE)**")
    summaries = svc.local_run_summaries(root) if root is not None else []
    for r in summaries:
        if r["state"] not in ("queued", "running"):  # detached supervisors survive reloads; RUN lives only in the session
            continue
        run_dir = svc.runs_root(root) / r["run_id"]
        line = f"{r['profile']} · {r['started'][:16].replace('T', ' ')} · {r['windows'] or 0}/{r['planned'] or '?'} pencere"
        if _poll(run_dir).get("state") == "interrupted":
            st.caption(f"Yarıda kaldı (denetleyici süreç yok, sonuç yazılmadı): {line} · ham çıktılar: {run_dir}")
            continue
        st.caption("Süren çalıştırma: " + line)
        st.button("İlerlemeyi göster / durdur", key="coupled_attach_" + r["run_id"], on_click=_attach, args=(str(run_dir),))
    monitor()
    local = [r for r in summaries if r["result_available"]]
    if local:
        rui = _rui()
        st.caption("Bu bilgisayardaki tamamlanmış veya kısmi çalıştırmalar. Açmak çözücüyü çalıştırmaz; mühürlü kayıt "
                   "doğrulanır ve dönen kanat, yükler ve akış görünümleri açılır. Bugünkü kodla doğrulanamayan kayıtlar "
                   "(ör. eski üretici sürümü) nedeniyle listelenir ama açılamaz.")
        state = _STATUS_SHORT
        st.dataframe([{"Başlangıç": r["started"][:16].replace("T", " "), "Profil": r["profile"],
                       "Katlanma [°]": rui._fmt(r["fold_deg"], 1),
                       "Devir": (f"{rui._fmt(r['ramp_start_rpm'], 0)}→{rui._fmt(r['rpm'], 0)} RPM" if r["drive"] == "ramp"
                                 else f"{rui._fmt(r['rpm'], 0)} RPM"),
                       "Durum": state.get(r["state"], r["state"]), "Pencere": f"{r['windows']}/{r['planned']}",
                       "Akış verisi": "var" if r["flow"] else "hazırlanabilir",
                       "Mekanik": "gösterim varsayımı" if r["mechanics_kind"] == "demonstration_assumption" else "beyan edilen",
                       "Açılabilir": "evet" if r["restorable"] else "hayır — " + (r["restore_error"] or "doğrulanamadı")}
                      for r in local], hide_index=True, **figure_style.dataframe_width_kwargs())
        by = {r["run_id"]: r for r in local if r["restorable"]}
    if local and not by:
        st.caption("Listelenen çalıştırmaların hiçbiri bugünkü kodla doğrulanamıyor; açılabilir kayıt yok.")
    elif local:
        chosen_run = rui._choice(st.selectbox, "Açılacak dinamik sonuç", tuple(by), key="coupled_local_run",
                                 default=next(iter(by)),
                                 display=lambda k: (f"{by[k]['profile']} · {rui._fmt(by[k]['fold_deg'], 1)}° · "
                                                    f"{state.get(by[k]['state'], by[k]['state'])} · {by[k]['started'][:16]}"))
        if st.button("Dinamik sonucu aç (yeniden hesaplanmaz)", key="coupled_local_open"):
            try:
                row = svc.load_result(svc.runs_root(root) / chosen_run)
            except (ValueError, OSError) as exc:
                st.error("Sonuç doğrulanamadı: " + str(exc))
            else:
                save(row)
                st.session_state[ACTIVE] = (None, row["result_sha256"])
                st.session_state["_coupled_view_imported"] = False
                st.session_state["research_results_kind"] = "Dinamik bağlaşık"
                st.session_state["_research_next_page"] = "Sonuçlar"
                st.rerun()
    if not records:
        if not local:
            st.caption("Henüz dinamik sonuç yok. Analiz sayfasındaki “Dinamik aero-mekanik analiz” bölümünden "
                       "başlatılabilir (araç zinciri gerekir).")
        return
    options = list(records)

    def display(key):
        row = records[key][0]
        i = row["request"]["research"]["inputs"]
        status = row["execution"]["status"]
        return f"{i['profile']} · {_STATUS_SHORT.get(status, status)} · {row['execution']['windows_accepted']} pencere · {key[:8]}"
    chosen = _rui()._choice(st.selectbox, "Dinamik kayıt", tuple(options), key="coupled_history_choice",
                            default=options[-1], display=display)
    if st.button("Dinamik kaydı Sonuçlar’da aç", key="coupled_open"):
        st.session_state[ACTIVE] = (None, chosen)
        st.session_state["_coupled_view_imported"] = records[chosen][1]
        st.session_state["research_results_kind"] = "Dinamik bağlaşık"
        st.session_state["_research_next_page"] = "Sonuçlar"
        st.rerun()


def import_bytes(raw: bytes):
    row = svc.read_saved_coupled_result(raw)
    return save(row, imported=True)
