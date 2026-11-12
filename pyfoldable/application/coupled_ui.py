"""Streamlit sections for the optional dynamic aero-mechanical analysis (Turkish UI).

Integrated into the research workspace: same design, profile and stored
provider version as the BEM route. Runs only on an explicit action, in a
detached supervisor; this module polls status, never blocks on a solver.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import math
from pathlib import Path

import streamlit as st

from pyfoldable.coupled import toolchain as tcmod
from pyfoldable.coupled.model import CoupledControls, CoupledMechanics

from . import coupled_analysis as svc, coupled_views as views

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
}
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
               "Şaft devri sabit tutulur; tahrik torku bir çıktıdır.")
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


def _controls_inputs():
    rui = _rui()
    defaults = CoupledControls()
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
                           aitken_initial_relaxation=aitken, max_wake_particles=int(particles), wall_timeout_s=timeout)


def _token(active, family, mech, ctrl):
    return json.dumps([active.identity, None if family is None else family.stored_version.content_sha256,
                       None if mech is None else asdict(mech), asdict(ctrl)], sort_keys=True)


def render_analysis(active, family, readiness_status, repository, root: Path):
    """Analiz page section."""
    st.markdown("**Dinamik aero-mekanik analiz · DUST–MBDyn–preCICE (isteğe bağlı)**")
    st.caption("Sabit şaft devri, rijit iç ve dış parça, eksene paralel ideal katlanma menteşesi, beyan edilen yay/sönüm/stop yasası. "
               "Aerodinamik yükler BEM ile aynı saklanan polar sürümünden DUST kaldırma çizgisiyle hesaplanır. "
               "CFD, FEA, eklem dayanımı veya yorulma değildir.")
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
    if run_state is not None and run_state["token"] != token and svc.poll(Path(run_state["run_dir"])).get("state") not in ("queued", "running"):
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
    revs = prep.case.n_steps * prep.case.dt_s * prep.case.omega_rad_s / (2 * math.pi)
    after = max(0.0, prep.case.n_steps * prep.case.dt_s - prep.case.mechanics.release_time_s) * prep.case.omega_rad_s / (2 * math.pi)
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
    if mech.declaration_kind == "demonstration_assumption":
        st.caption("Mekanik değerler gösterim varsayımıdır; sonuç ölçülmüş donanımı temsil etmez.")
    busy = run_state is not None and svc.poll(Path(run_state["run_dir"])).get("state") in ("queued", "running")
    if st.button("Dinamik analizi başlat", type="primary", key="coupled_start", disabled=busy):
        run = svc.start_run(prep, root)
        st.session_state[RUN] = {"run_dir": str(run), "token": token}
        st.rerun()
    if st.session_state.get(RUN):
        _progress()


@st.fragment(run_every=2.0)
def _progress():
    run_state = st.session_state.get(RUN)
    if not run_state:
        return
    run = Path(run_state["run_dir"])
    status = svc.poll(run)
    state = status.get("state", "unknown")
    n, k = status.get("n_windows") or 1, status.get("windows_accepted") or 0
    if state in ("queued", "running"):
        st.progress(min(1.0, k / n), text=f"Çalışıyor · {k}/{n} pencere · {status.get('elapsed_s', 0)} s · aşama {status.get('phase', '…')}")
        if st.button("Durdur", key="coupled_cancel"):
            svc.cancel(run)
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
    elif not status.get("result_available"):
        st.error(f"Çalıştırma {state} durumunda sonuçsuz bitti: {status.get('message', '')}. Ham çıktılar: {run}")


def _archive(row) -> bytes:
    """Compressed record, computed once per record and session (not on every rerun)."""
    cache = st.session_state.setdefault("_coupled_archive_cache", {})
    key = row["result_sha256"]
    if key not in cache:
        cache.clear()
        cache[key] = svc.record_archive_bytes(row)
    return cache[key]


def save(row, *, imported=False):
    history = st.session_state.setdefault(HISTORY, ())
    if any(json.loads(raw)["result_sha256"] == row["result_sha256"] for raw, _ in history):
        return "duplicate"
    if len(history) >= MAX_HISTORY:
        history = history[1:]
    st.session_state[HISTORY] = (*history, (views.saved_json(row), imported))
    return "saved"


def retained():
    return {json.loads(raw)["result_sha256"]: (json.loads(raw), imp) for raw, imp in st.session_state.get(HISTORY, ())}


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


def render_result(row, *, imported=False):
    rui = _rui()
    ex = row["execution"]
    i = row["request"]["research"]["inputs"]
    kind, text = _STATUS_TEXT.get(ex["status"], ("warning", ex["status"]))
    getattr(st, kind)(text)
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
        to_rev = cs["omega_rad_s"] / (2 * math.pi)
        st.caption(f"Kısa analiz penceresi: {t_end * to_rev:.1f} devir, serbest bırakmadan sonra "
                   f"{max(0.0, t_end - m['release_time_s']) * to_rev:.1f} devir ({t_end:.4f} s). Son pencere değerleri "
                   "uzun süreli oturmuş performans değildir; ortalamalar için tam devir pencerelerini kullanın.")
        st.caption(f"Kabul edilen pencereler {ex['windows_accepted']}/{ex['windows_planned']} · geçerli önek {ex['valid_prefix_windows']} · "
                   f"stop teması {'oluştu' if contact else 'oluşmadı'} · bağlaşım iterasyonu "
                   f"{min(r['coupling_iterations'] for r in valid)}–{max(r['coupling_iterations'] for r in valid)}.")
    a, b, c, d = st.columns(4)
    name = f"pyfoldable_dinamik_{i['profile']}_{row['result_sha256'][:8]}"
    a.download_button("Sonuç JSON’u", views.saved_json(row), name + ".json", "application/json")
    a.download_button("Sıkıştırılmış kayıt (.json.gz)", _archive(row), name + ".json.gz", "application/gzip",
                      help="Aynı mühürlü kaydın kayıpsız gzip hâli; Karşılaştırma / kayıtlar sayfasından açılabilir.")
    if row["series"]:
        b.download_button("Zaman serisi CSV", views.series_csv(row), name + "_zaman.csv", "text/csv")
        c.download_button("Radyal CSV", views.radial_csv(row), name + "_radyal.csv", "text/csv")
        d.download_button("ParaView (VTK)", views.vtk_zip(row), name + "_vtk.zip", "application/zip",
                          help="Kabul edilen MBDyn durumlarında rijit parça yüzeyleri ve .pvd zaman listesi.")
    if not row["series"]:
        _details(row)
        return
    tab = rui._choice(st.radio, "Grafik", ("Menteşe", "Yükler", "Güç", "Kapsam ve yakınsama", "Radyal", "3B oynatma"),
                      key="coupled_tab", default="Menteşe", horizontal=True)
    if tab == "Menteşe":
        rui._plot(views.time_figure(row, (("theta_deg", "θ"),), "Katlanma açısı θ [°]", per_blade=True), "coupled_theta")
        rui._plot(views.time_figure(row, (("theta_rate_rad_s", "θ̇"),), "Menteşe açısal hızı [rad/s]", per_blade=True), "coupled_rate")
        rui._plot(views.time_figure(row, (("hinge_aero_torque_nm", "Aerodinamik"), ("hinge_law_torque_nm", "Yay+sönüm+stop"),
                                          ("centrifugal_hinge_moment_derived_nm", "Merkezkaç (türetilmiş tanı)")),
                                    "Dış parçaya menteşe momenti [N·m]", per_blade=True), "coupled_hinge_m")
        st.caption("Merkezkaç momenti modele ayrıca eklenmez; dönen çerçevede −mΩ²r_h c_g sinθ olarak türetilmiş bir tanıdır. "
                   "Stop teması penaltı yasasıdır; açının 0°’yi aşması tanımlı esneme (penetrasyon) miktarıdır.")
    elif tab == "Yükler":
        rui._plot(views.time_figure(row, (("thrust_n", "İtki"),), "İtki [N]"), "coupled_thrust")
        rui._plot(views.time_figure(row, (("aero_shaft_torque_nm", "Aerodinamik şaft torku"), ("drive_torque_nm", "Tahrik (tepki) torku")),
                                    "Tork [N·m]"), "coupled_torque")
        st.caption("Tahrik torku, sabit devri koruyan MBDyn tepki torkudur; katlanma sırasında atalet etkilerini de içerir ve "
                   "aerodinamik torktan ayrıdır. Başlangıç ve kilit açılışında kısa süreli sayısal geçiş görülebilir.")
    elif tab == "Güç":
        rui._plot(views.time_figure(row, (("aero_power_absorbed_w", "Aerodinamik güç (havaya aktarılan)"), ("drive_power_w", "Tahrik gücü")),
                                    "Güç [W]"), "coupled_power")
    elif tab == "Kapsam ve yakınsama":
        for q in ("alpha", "re", "mach"):
            rui._plot(views.coverage_figure(row, q), "coupled_cov_" + q)
        rui._plot(views.iterations_figure(row), "coupled_iters")
        st.caption("Sorgulanan değerler, her kabul edilen pencerede kaldırma çizgisinin son iterasyonundaki kesit durumlarıdır. "
                   "DUST tablo dışı α veya Mach’ta durur; Reynolds dışına doğrusal ekstrapolasyon yapar ve burada denetlenir.")
    elif tab == "Radyal":
        windows = [r["window"] for r in row["series"]]
        w = st.select_slider("Pencere", options=windows, value=windows[-1], key="coupled_radial_window")
        rows = views.radial_rows(row, w)
        field = rui._choice(st.radio, "Büyüklük", ("alpha_deg", "reynolds", "mach", "cl", "dFz_n"), key="coupled_radial_field",
                            default="alpha_deg", horizontal=True,
                            display={"alpha_deg": "α", "reynolds": "Re", "mach": "Mach", "cl": "cl", "dFz_n": "Eleman itkisi"}.__getitem__)
        rui._plot(views.radial_figure(rows, field, field), "coupled_radial_plot")
        with st.expander("Radyal veri tablosu"):
            st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        fig = views.playback_figure(row)
        if fig is not None:
            rui._plot(fig, "coupled_playback")  # scroll zoom disabled, like the other workspace figures
        st.caption("Kabul edilen MBDyn durumlarında rijit parça yüzeyleri (katalog kesiti, beyan edilen istasyonlar). "
                   "Basınç veya gerilme alanı çözülmediği için gösterilmez. 3B için WebGL gerekir.")
    _details(row)


def _details(row):
    with st.expander("Teknik ayrıntılar · denetimler, kimlikler, sürümler"):
        st.dataframe([{"Denetim": c["name"], "Değer": c["value"], "Sınır": c["limit"], "Geçti": c["passed"], "Anlamı": c["meaning"]}
                      for c in row["checks"]], hide_index=True, use_container_width=True)
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


def render_history(root: Path | None = None):
    records = retained()
    st.markdown("**Dinamik bağlaşık kayıtlar**")
    local = _local_runs(root) if root is not None else []
    if local:
        with st.expander("Yerel çalıştırma klasöründen aç"):
            st.caption("Bu bilgisayardaki çalıştırma klasörlerinin mühürlü sonuçları. İç tutarlılık denetlenir, çözücü çalışmaz.")
            names = tuple(p.name for p in local)
            chosen_run = _rui()._choice(st.selectbox, "Çalıştırma", names, key="coupled_local_run", default=names[0])
            if st.button("Kayıtlara ekle", key="coupled_local_open"):
                try:
                    status = save(svc.load_result(svc.runs_root(root) / chosen_run))
                except (ValueError, OSError) as exc:
                    st.error("Sonuç doğrulanamadı: " + str(exc))
                else:
                    st.success("Kayıt eklendi." if status == "saved" else "Bu kayıt zaten oturumda.")
                    records = retained()
    if not records:
        st.caption("Henüz dinamik kayıt yok.")
        return
    options = list(records)

    def display(key):
        row = records[key][0]
        i = row["request"]["research"]["inputs"]
        return f"{i['profile']} · {row['execution']['status']} · {row['execution']['windows_accepted']} pencere · {key[:8]}"
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
