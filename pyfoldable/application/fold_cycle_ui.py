"""Streamlit workspace for the complete opening–closing cycle and the loads carried by the folding connection."""
from __future__ import annotations

import json
import math
import os
from dataclasses import replace
from pathlib import Path

import streamlit as st

from pyfoldable.dynamics import fold_cycle as fc
from pyfoldable.dynamics import pin_lug as pl
from pyfoldable.visualization import blade_surface as bs
from pyfoldable.visualization import fold_interference as fi

from . import figure_style
from . import fold_cycle_views as views
from . import research_ui as rui

CYCLES_ENV = "PYFOLDABLE_CYCLES"
ACTIVE = "_fold_cycle_active"
KIND = "Açılma–kapanma çevrimi"
MODES = {
    "mechanical_cycle_explicit_aero": ("Tam çevrim · mekanik dinamik model + açık aerodinamik model",
                                       "Katlanma hareketi öngörülür (dinamik), mil devri tanımlıdır. Aerodinamik yükler keşif amaçlı "
                                       "yarı-durağan şerit modelinden gelir (indüksiyon yok, saklanan polar verisi değil)."),
    "mechanical_cycle_no_aero": ("Tam çevrim · yalnız mekanik dinamik model",
                                 "Katlanma hareketi öngörülür; aerodinamik yük yok (yalnız atalet, yay, stop, mandal, aktüatör)."),
}
PRESETS = {
    "spring": "Yay geri dönüşlü (merkezkaç açar, yay kapatır)",
    "passive": "Pasif (yay yok) · kapanma beklenmez",
    "latch_actuator": "Pasif + açık mandal + aktüatörle geri katlama",
}


def cycles_root() -> Path:
    return Path(os.environ.get(CYCLES_ENV) or Path(__file__).resolve().parents[2] / "outputs" / "fold_cycles")


def store(row) -> Path:
    folder = cycles_root()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{row['result_sha256']}.json"
    if not path.exists():
        tmp = path.with_name(f"{path.stem}.{os.getpid()}.{os.urandom(4).hex()}.tmp")
        tmp.write_text(json.dumps(row, separators=(",", ":"), ensure_ascii=False, allow_nan=False), encoding="utf-8")
        tmp.replace(path)
    return path


_SAVED: dict = {}


def saved(limit=30) -> list:
    """Validated summaries of the saved cycles (newest first); tampered or foreign files are skipped."""
    folder = cycles_root()
    out = []
    for path in sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit] if folder.is_dir() else []:
        try:
            st_ = path.stat()
        except OSError:
            continue
        key = (str(path), st_.st_mtime_ns, st_.st_size)
        if key not in _SAVED:
            try:
                row = fc.verify(json.loads(path.read_text(encoding="utf-8")))
                g = row.get("geometry", {})
                _SAVED[key] = {"path": path, "sha": row["result_sha256"], "saved": st_.st_mtime,
                               "profile": g.get("profile_id", "?"), "mode": row["analysis_mode"],
                               "rpm": row["case"]["schedule"]["operating_rpm"], "offset_mm": row["case"]["mechanism"]["axial_offset_m"] * 1000,
                               "returned": row["outcome"]["returned_to_stowed"], "preset": row.get("preset", "?")}
            except (OSError, ValueError, KeyError, TypeError):
                _SAVED[key] = None
        if _SAVED[key] is not None:
            out.append(_SAVED[key])
    return out


_ROWS: dict = {}


def _read(path):
    """Verified record, memoised per (path, mtime, size) like saved(): a rerun does not re-verify an unchanged file.
    Raises OSError/ValueError/KeyError/TypeError when the file is gone or no longer verifies."""
    s = Path(path).stat()
    key = (str(path), s.st_mtime_ns, s.st_size)
    if key not in _ROWS:
        if len(_ROWS) >= 2:                             # the active record and one comparison
            _ROWS.pop(next(iter(_ROWS), None), None)    # another session may evict concurrently
        _ROWS[key] = fc.verify(json.loads(Path(path).read_text(encoding="utf-8")))
    return _ROWS[key]


def active_row():
    path = st.session_state.get(ACTIVE)
    if not path:
        return None
    try:
        return _read(path)
    except (OSError, ValueError, KeyError, TypeError):
        st.session_state.pop(ACTIVE, None)
        return None


def _open(path):
    st.session_state[ACTIVE] = str(path)
    st.session_state["research_results_kind"] = KIND
    rui._navigate("Sonuçlar")


# ------------------------------------------------------------------------------------------------- Analiz
def _preset_values(preset, design):
    stow = design["stow_deg"]
    base = {"cycle_mass_g": 30.0, "cycle_cg_mm": 55.0, "cycle_inertia_gcm2": 300.0, "cycle_offset_mm": 0.0,
            "cycle_k": 0.05, "cycle_preload": 0.30, "cycle_damping": 3.0e-3, "cycle_coulomb": 0.0,
            "cycle_kc": 200.0, "cycle_e": 0.5, "cycle_latch": False, "cycle_latch_release": 1.0,
            "cycle_act": 0.0, "cycle_act_start": 1.0, "cycle_act_end": 2.4, "cycle_stowed": stow, "cycle_capture": 0.0,
            "cycle_itz": 0.0}
    if preset in ("passive", "latch_actuator"):
        base.update(cycle_k=0.0, cycle_preload=0.0)
    if preset == "latch_actuator":
        # the aerodynamic pin moment holds the blade ≈0.5° short of the open stop, so a stop-only latch never engages
        base.update(cycle_latch=True, cycle_act=-0.3, cycle_capture=1.0)
    return base


def _design_of(active):
    foil = next(f for f in active.design.airfoils if f.id == active.inputs.profile)
    return {"spec": bs.spec_from_design(active, foil), "rpm": active.inputs.rpm, "inflow": active.inputs.inflow_m_s,
            "density": active.inputs.density_kg_m3, "stow_deg": max(-179.0, active.inputs.stow_limit_deg),
            "stow_limit_deg": active.inputs.stow_limit_deg}


def _reset(key, value):
    """Set a remembered field value (rui._seed) so the widget shows it on its next render."""
    st.session_state.setdefault("_research_control_values", {})[key] = value
    st.session_state.get("_research_widget_seeds", {}).pop(key, None)
    st.session_state.pop(key, None)


def _follow(key, design_value):
    """The field follows the design value until the user sets another one: a remembered value still equal to the
    previous design value is replaced when the design changes."""
    seen = st.session_state.setdefault("_cycle_design_seen", {})
    old = seen.get(key)
    if old is not None and old != design_value and st.session_state.get("_research_control_values", {}).get(key, old) == old:
        _reset(key, design_value)
    seen[key] = design_value
    return design_value


def analysis_section(active):
    st.markdown("**Tam açılma–kapanma çevrimi ve bağlantı yükleri**")
    st.caption("Kapalıdan başlar: mil hızlanır, kanat açılır ve açık stopa gelir, çalışma devrinde yük taşır, mil yavaşlar ve "
               "seçilen mekanizma kanadı yeniden katlar. Katlanma hareketi her an menteşe dengesinden öngörülür (dinamik); "
               "mil devri tanımlı bir profildir. Ters oynatılan bir açılma değildir; devrin düşmesi kendiliğinden katlanma demek değildir.")
    try:
        design = _design_of(active)
    except (ValueError, StopIteration) as exc:
        st.warning("Bu tasarım için 3B kanat geometrisi kurulamadı: " + str(exc))
        return
    spec = design["spec"]
    st.dataframe([{"Mod": label, "Ne hesaplanır": text} for label, text in MODES.values()]
                 + [{"Mod": "Bağlaşık DUST–MBDyn–preCICE (aşağıda, ayrı)",
                     "Ne hesaplanır": "Girdap izi ve kesit yükleri zamana bağlı çözülür; gösterilen aralık küçük katlanmadan açılmadır "
                                      "(−23°’ye kadar; test edilen ≥1600 RPM (NACA2412 deploy-v3); tahmini taban ≈1500 RPM, test "
                                      "edilmedi). Kapanma ve tam katlanma bu modun veri ve geometri kapsamı dışındadır."}],
                 hide_index=True, **figure_style.dataframe_width_kwargs())
    preset = rui._choice(st.selectbox, "Mekanizma yapılandırması", tuple(PRESETS), key="cycle_preset", default="spring",
                         display=PRESETS.__getitem__)
    vals = _preset_values(preset, design)
    # widgets keyed per preset: switching presets shows that preset's own values (the browser keeps widget values,
    # so overwriting shared widgets from a callback would be undone by the next interaction)
    pk = lambda name: f"{name}__{preset}"  # noqa: E731
    with st.expander("Mekanizma ve bağlantı parametreleri (keşif varsayımı — değiştirilebilir)", expanded=False):
        a, b, c = st.columns(3)
        mass = rui._field(a.number_input, "Dış parça kütlesi [g]", pk("cycle_mass_g"), vals["cycle_mass_g"], min_value=1.0, max_value=500.0)
        cg = rui._field(b.number_input, "Kütle merkezi, menteşeden [mm]", pk("cycle_cg_mm"), vals["cycle_cg_mm"], min_value=1.0, max_value=500.0)
        inertia = rui._field(c.number_input, "CG ataleti [g·cm²]", pk("cycle_inertia_gcm2"), vals["cycle_inertia_gcm2"],
                             min_value=1.0, max_value=1e5) * 1e-7      # 1 g·cm² = 1e-7 kg·m²
        offset = rui._field(a.number_input, "Eksenel kaydırma δ (pim–kulak) [mm]", pk("cycle_offset_mm"), vals["cycle_offset_mm"],
                            min_value=0.0, max_value=60.0, help="Dış parça ve dili pim boyunca yukarı kaydırılır; 0: analizlerin tek düzlemi.")
        stowed = rui._field(b.number_input, "Kapalı stop açısı [°]", pk("cycle_stowed"), _follow(pk("cycle_stowed"), vals["cycle_stowed"]),
                            min_value=-179.0, max_value=-5.0)
        k = rui._field(c.number_input, "Geri dönüş yayı [N·m/rad]", pk("cycle_k"), vals["cycle_k"], min_value=0.0, max_value=10.0, format="%.3f")
        pre = rui._field(a.number_input, "Yay ön yükü (kapalıda) [N·m]", pk("cycle_preload"), vals["cycle_preload"], min_value=0.0, max_value=20.0)
        damp = rui._field(b.number_input, "Sönüm [N·m·s/rad]", pk("cycle_damping"), vals["cycle_damping"], min_value=0.0, max_value=1.0, format="%.4f")
        coul = rui._field(c.number_input, "Coulomb sürtünmesi [N·m]", pk("cycle_coulomb"), vals["cycle_coulomb"], min_value=0.0, max_value=5.0)
        kc = rui._field(a.number_input, "Stop rijitliği [N·m/rad]", pk("cycle_kc"), vals["cycle_kc"], min_value=1.0, max_value=1e5)
        e = rui._field(b.number_input, "Stop geri sekme katsayısı", pk("cycle_e"), vals["cycle_e"], min_value=0.05, max_value=1.0)
        latch = rui._field(c.checkbox, "Açık mandal (stopta kilitlenir)", pk("cycle_latch"), vals["cycle_latch"])
        rel = rui._field(a.number_input, "Mandal bırakma zamanı [s]", pk("cycle_latch_release"), vals["cycle_latch_release"], min_value=0.0,
                         max_value=fc.MAX_CYCLE_DURATION_S)
        act = rui._field(b.number_input, "Aktüatör momenti [N·m] (− katlar)", pk("cycle_act"), vals["cycle_act"], min_value=-5.0, max_value=5.0)
        cap = rui._field(c.number_input, "Mandal yakalama bandı [°]", pk("cycle_capture"), vals["cycle_capture"], min_value=0.0, max_value=10.0,
                         help="Mandal, kanat açık stopun bu kadar altına ulaştığında kilitlenir (0: yalnız stopta).")
        a2, b2, c2 = st.columns(3)
        act0 = rui._field(a2.number_input, "Aktüatör başlangıç [s]", pk("cycle_act_start"), vals["cycle_act_start"], min_value=0.0,
                          max_value=fc.MAX_CYCLE_DURATION_S)
        act1 = rui._field(b2.number_input, "Aktüatör bitiş [s]", pk("cycle_act_end"), vals["cycle_act_end"], min_value=0.0,
                          max_value=fc.MAX_CYCLE_DURATION_S)
        itz = rui._field(c2.number_input, "I_tz çarpım ataleti [g·cm²] (beyan edilen değer)", pk("cycle_itz"), vals["cycle_itz"],
                         min_value=-1e5, max_value=1e5, help="Kütle merkezine göre e_t–e_z çarpım ataleti; loft geometrisinden "
                         "türetilmez. Pim ekseni hareketini değiştirmez, eğilme ve burulma tepkilerine girer.") * 1e-7
    with st.expander("Mil devri profili, aerodinamik ve yerçekimi", expanded=False):
        st.caption(f"Toplam çevrim süresi en çok {fc.MAX_CYCLE_DURATION_S:.0f} s: çözüm uygulama içinde beklenir ve kayıt boyutu "
                   "sınırlı tutulur.")
        a, b, c = st.columns(3)
        rpm = rui._field(a.number_input, "Çalışma devri [RPM]", "cycle_rpm", _follow("cycle_rpm", float(design["rpm"])),
                         min_value=100.0, max_value=20000.0)
        rest = rui._field(b.number_input, "Başta bekleme [s]", "cycle_rest", 0.1, min_value=0.0, max_value=fc.MAX_CYCLE_DURATION_S)
        up = rui._field(c.number_input, "Hızlanma süresi [s]", "cycle_up", 0.3, min_value=0.01, max_value=fc.MAX_CYCLE_DURATION_S)
        hold = rui._field(a.number_input, "Çalışma süresi [s]", "cycle_hold", 0.6, min_value=0.0, max_value=fc.MAX_CYCLE_DURATION_S)
        down = rui._field(b.number_input, "Yavaşlama süresi [s]", "cycle_down", 0.8, min_value=0.01, max_value=fc.MAX_CYCLE_DURATION_S)
        end = rui._field(c.number_input, "Sonda bekleme [s]", "cycle_end", 0.6, min_value=0.0, max_value=fc.MAX_CYCLE_DURATION_S)
        final = rui._field(a.number_input, "Son devir [RPM]", "cycle_final_rpm", 0.0, min_value=0.0, max_value=20000.0,
                           help="Yavaşlama bu devire iner; 0: mil durur.")
        aero = rui._choice(st.radio, "Aerodinamik model", ("plate", "off"), key="cycle_aero", default="plate", horizontal=True,
                           display={"plate": "Açık şerit modeli (keşif)", "off": "Kapalı (yalnız mekanik)"}.__getitem__)
        rest_inflow = rui._choice(st.radio, "Durağanda serbest akım (Ω = 0)", ("design", "zero"), key="cycle_rest_inflow",
                                  default="design", horizontal=True,
                                  display={"design": "var (tasarım akımı)", "zero": "yok"}.__getitem__)
        grav = rui._choice(st.radio, "Yerçekimi", ("off", "shaft_vertical", "shaft_horizontal"), key="cycle_gravity", default="off",
                           horizontal=True, display={"off": "Yok", "shaft_vertical": "Mil düşey", "shaft_horizontal": "Mil yatay"}.__getitem__)
    if rpm != design["rpm"]:
        st.warning(f"Çevrim devri {rpm:.0f} RPM, güncel tasarım devri {design['rpm']:.0f} RPM.")
        st.button("Devri tasarımdan al", key="cycle_rpm_from_design", on_click=_reset, args=("cycle_rpm", float(design["rpm"])))
    if stowed < design["stow_limit_deg"] - 1e-9:
        st.warning(f"Kapalı stop {stowed:.1f}°, tasarımda beyan edilen katlanma sınırının ({design['stow_limit_deg']:.1f}°) ötesinde.")
    try:
        mech = fc.FoldMechanism(mass_kg=mass / 1000, cg_from_hinge_m=cg / 1000, inertia_cg_kg_m2=inertia, axial_offset_m=offset / 1000,
                                spring_nm_per_rad=k, spring_preload_nm=pre, damping_nm_s_per_rad=damp, coulomb_nm=coul,
                                stowed_stop_rad=math.radians(stowed), stop_stiffness_nm_per_rad=kc, stop_restitution=e,
                                open_latch=bool(latch), latch_release_s=rel, actuator_nm=act, actuator_start_s=act0, actuator_end_s=act1,
                                latch_capture_rad=math.radians(cap), inertia_tz_kg_m2=itz)
        sched = fc.ShaftSchedule(operating_rpm=rpm, rest_s=rest, spinup_s=up, hold_s=hold, spindown_s=down, end_rest_s=end,
                                 final_rpm=final)
        strips = fc.strips_from_stations(spec.stations, spec.hinge_radius_m)
        case = fc.CycleCase(spec.hinge_radius_m, spec.blade_count, sched, mech,
                            fc.AeroModel(model=aero, inflow_m_s=design["inflow"], density_kg_m3=design["density"],
                                         strips=strips if aero == "plate" else (), rest_inflow=rest_inflow),
                            gravity=grav)
        problem = None
    except ValueError as exc:
        case, problem = None, str(exc)
    if problem:
        st.error("Çevrim girdileri geçersiz: " + problem)
    st.caption(f"Geometri: {spec.profile_id}, menteşe {spec.hinge_radius_m * 1000:.0f} mm, uç {spec.tip_radius_m * 1000:.0f} mm, "
               f"{spec.blade_count} kanat. Mekanizma değerleri keşif varsayımıdır; donanım ölçümü değildir.")
    sens = rui._field(st.checkbox, "Temas duyarlılığını da hesapla (üç ek çözüm)", "cycle_sensitivity", False)
    duration = rest + up + hold + down + end
    # the case is built from this render's widget values: a callback would solve the previous render's case
    if st.button("Çevrimi çalıştır", key="cycle_run", disabled=case is None, type="primary",
                 help=f"Yüzey teması taranır ve {duration:.2f} s’lik çevrim çözülür; süre çevrim süresi ve kanat sayısıyla, "
                      "temas duyarlılığı seçiliyse belirgin biçimde uzar. Sonuçlar açılır."):
        path = _run(case, preset, replace(spec, distal_axial_offset_m=offset / 1000), stowed, sens)
        if path is not None:
            _open(path)
            st.rerun()


def _run(case, preset, geo_spec, stowed, sensitivity):
    """Explicit action: scan, solve, seal and store; the stored path, or None after showing the error."""
    with st.status("Çevrim hesaplanıyor…", expanded=True) as status:
        try:
            st.write("Yüzey teması taranıyor…")
            rep = fi.fold_contacts(geo_spec, joint="plane" if geo_spec.distal_axial_offset_m > 0 else "relief",
                                   fold_min_deg=max(-180.0, stowed - 2.0))
            st.write("Çevrim çözülüyor" + (" ve temas duyarlılığı hesaplanıyor…" if sensitivity else "…"))
            row = fc.run_cycle(case, sensitivity=sensitivity, extra={
                "preset": preset, "geometry": views.spec_payload(geo_spec),
                "geometry_check": {"joint": "pin_lug_axial_offset" if geo_spec.distal_axial_offset_m > 0 else "display_relief_zone",
                                   "interference_free_deg": rep.interference_free_deg,
                                   "consistent_with_stowed_stop": bool(rep.interference_free_deg <= stowed + 1e-6),
                                   "contacts": [{"a": c.a, "b": c.b, "status": c.status, "first_contact_deg": c.first_contact_deg}
                                                for c in rep.contacts]}})
            path = store(row)
        except (OSError, ValueError, RuntimeError) as exc:
            status.update(label="Çevrim çözülemedi", state="error")
            st.error("Çevrim çözülemedi veya kaydedilemedi: " + str(exc))
            return None
        status.update(label="Çevrim hazır", state="complete")
    return path


# ------------------------------------------------------------------------------------------------ Sonuçlar
def _fmt(x, n=2):
    return rui._fmt(x, n)


def _goto_event(index_of):
    ev = st.session_state.get("cycle_event")
    if ev in index_of:
        st.session_state["cycle_index"] = int(index_of[ev])          # the event's own sample, not a snapped time
    st.session_state["cycle_event"] = "—"


def render_result(row):
    a = views.arrays(row)
    spec = views.spec_from_payload(row["geometry"])
    label, text = MODES[row["analysis_mode"]]
    st.markdown(f"**{label}**")
    st.caption(text + " Hareket öngörülen (dinamik) harekettir, tanımlı bir canlandırma değildir.")
    mech, sch = row["case"]["mechanism"], row["case"]["schedule"]
    st.caption(f"Saklanan çevrim kaydı (güncel tasarımdan bağımsız): {spec.profile_id} · {sch['operating_rpm']:.0f} RPM · "
               f"çap {spec.tip_radius_m * 2000:.0f} mm · δ = {mech['axial_offset_m'] * 1000:.0f} mm · {spec.blade_count} kanat.")
    nb = row["case"]["blade_count"]
    if "events_by_blade" in row:              # in-plane gravity: the blades differ and every blade is stored
        blade = rui._choice(st.radio, "Kanat", tuple(range(nb)), key="cycle_blade", default=0, horizontal=True,
                            display=lambda b: f"Kanat {b + 1}")
    else:
        blade = 0
        st.caption("Kanatlar özdeş (yerçekimi dönme düzleminde değil): kanat 1 hepsini temsil eder.")
    out, geo = row["outcome"], row.get("geometry_check", {})
    final = (out.get("final_theta_deg_by_blade") or [out["final_theta_deg"]] * nb)[blade]
    c = st.columns(4)
    c[0].metric("Açıldı mı", "evet" if out["open_reached"] else "hayır")
    c[1].metric("Kapalıya döndü mü", "evet" if out["returned_to_stowed"] else "hayır")
    c[2].metric("Çalışmada θ [°]", _fmt(out["operating_theta_deg"], 2) if out["operating_theta_deg"] is not None else "—")
    c[3].metric(f"Son θ [°] (kanat {blade + 1})", _fmt(final, 1))
    if not out["returned_to_stowed"] and sch.get("final_rpm", 0.0) > 0:
        st.warning(f"Kanat kapalı konuma dönmedi: mil son devirde ({sch['final_rpm']:.0f} RPM) dönmeyi sürdürür ve merkezkaç "
                   "momenti kanadı açık yönde tutar.")
    elif not out["returned_to_stowed"]:
        st.warning("Bu mekanizma kanadı kapalı konuma döndürmedi: mil durduğunda merkezkaç momenti kaybolur ama kanadı geri "
                   "katlayan bir moment yoktur (mili yavaşlatmak kanadı açık stopa iter). Geri dönüş için yay, aktüatör veya mandal + "
                   "aktüatör tanımlayın.")
    if mech["open_latch"] and not any(e["kind"] == "latch_engaged" for e in row.get("latch_events", ())):
        st.warning("Açık mandal hiç kilitlenmedi: kanat bırakma zamanından önce açık stopa ulaşmadı (mandal yalnız stopta "
                   "kilitlenir). Geri katlama yalnız aktüatör ve diğer elemanlarla gerçekleşti.")
    if out["operating_theta_deg"] is not None and out["operating_theta_deg"] < -0.3 and out["open_reached"]:
        cause = ("geri dönüş yayı açık konumda da çeker" if (mech["spring_nm_per_rad"] > 0 or mech["spring_preload_nm"] > 0)
                 else "dış parçanın aerodinamik pim momenti kanadı geriye iter")
        st.info(f"Çalışma devrinde kanat açık stopa oturmuyor: θ ≈ {_fmt(out['operating_theta_deg'], 2)}°. Neden: {cause}; merkezkaç "
                "momenti θ → 0’da sıfıra gider. Stopa oturtmak için mandal (veya açıkta torku sıfırlanan bir yay) gerekir.")
    if geo and not geo.get("consistent_with_stowed_stop", True):
        st.warning(f"Tanımlı kanat yüzeyleri {_fmt(geo['interference_free_deg'], 1)}°’den sonra temas eder; kapalı stop "
                   f"({_fmt(math.degrees(row['case']['mechanism']['stowed_stop_rad']), 1)}°) bu açının ötesindedir. Mekanik model bunu "
                   "engellemez; fiziksel olarak dış parçanın iç parçanın üzerinden geçmesi için eksenel kaydırma δ (pim–kulak) gerekir.")
    elif geo:
        st.caption(f"Yüzey taraması ({'pim–kulak, δ = ' + _fmt(row['case']['mechanism']['axial_offset_m'] * 1000, 0) + ' mm' if geo['joint'] == 'pin_lug_axial_offset' else 'gösterim eklem bölgesi'}): "
                   f"tanımlı yüzeyler {_fmt(geo['interference_free_deg'], 1)}°’ye kadar temassız. Bağlantı parçaları (pim, plakalar) taranmadı.")
    # ---- the selected physical state
    events = views.events_of(row, blade)
    t = a["time_s"]
    by = {e["key"]: e for e in events}
    a1, a2 = st.columns((1, 2))
    # an action selector: the callback jumps and resets it, so choosing the same event again jumps again
    a1.selectbox("Olaya git", ("—", *by), key="cycle_event", on_change=_goto_event, args=({k: e["index"] for k, e in by.items()},),
                 format_func=lambda k: "Olay seçin" if k == "—" else f"{by[k]['label']} · {by[k]['time_s']:.4f} s")
    sha = row["result_sha256"]
    if st.session_state.get("_cycle_state_record") != sha:          # a different record starts at its first sample
        st.session_state["_cycle_state_record"] = sha
        st.session_state["cycle_index"] = 0
    if not isinstance(st.session_state.get("cycle_index"), int) or not 0 <= st.session_state["cycle_index"] < len(t):
        st.session_state["cycle_index"] = 0
    i = a2.slider("Örnek (zaman sırasında; ince örnekleme temas çevresinde)", 0, len(t) - 1, key="cycle_index")
    a2.caption(f"Seçili durum: t = {t[i]:.5f} s")
    frame = rui._choice(st.radio, "Görünüm çerçevesi", tuple(views.FRAMES), key="cycle_frame", default="rotor", horizontal=True,
                        display=views.FRAMES.__getitem__)
    left, right = st.columns((1.35, 1))
    with left:
        rui._plot(views.scene_figure(row, spec, i, frame), "cycle_scene")
        st.caption("Kırmızı ok: iç parçanın kanat 1 dış parçasına uyguladığı kuvvet; mor ok: moment vektörü (sağ el kuralı). Gri ve "
                   "turuncu saydam kanat: açık ve kapalı sınırlar. Renkler yük değildir; yapısal gerilme çözülmedi.")
    with right:
        b = blade
        L = {k: float(a[f"load_{k}"][i][b]) for k in views.LOADS}
        st.markdown(f"**t = {t[i]:.4f} s** · {a['rpm'][i]:.0f} RPM · dΩ/dt = {a['omega_dot_rad_s2'][i]:.0f} rad/s²")
        st.markdown(f"θ = {a['theta_deg'][i][b]:.2f}° · θ̇ = {a['theta_rate_rad_s'][i][b]:.2f} rad/s · θ̈ = {a['theta_acc_rad_s2'][i][b]:.0f} rad/s²")
        st.dataframe([{f"Bileşen (kanat {b + 1}, dil orta düzlemi)": f"{views.LOADS[k][0]} [{views.LOADS[k][1]}]", "Değer": round(L[k], 4),
                       "Mafsal": ("eleman (yay/stop/mandal)" if k == "M_pin" else "kısıt tepkisi")} for k in views.LOADS],
                     hide_index=True, **figure_style.dataframe_width_kwargs())
        st.dataframe([{"Pim ekseni momenti kaynağı": views.ELEMENT_LABEL[k], "N·m": round(float(a[f"hinge_{k}_nm"][i][b]), 4)}
                      for k in views.ELEMENT_LABEL if abs(float(a[f"hinge_{k}_nm"][i][b])) > 1e-9] or
                     [{"Pim ekseni momenti kaynağı": "—", "N·m": 0.0}], hide_index=True, **figure_style.dataframe_width_kwargs())
        st.caption(f"Dış parça itkisi {a['aero_thrust_n'][i][b]:.2f} N · aero pim momenti {a['aero_pin_torque_nm'][i][b]:.3f} N·m · "
                   f"bu kanadın dış parçası için mil torku {a['drive_torque_nm'][i][b]:.3f} N·m (rotor şaft torku değildir; "
                   "rijit, sonsuz katı tanımlı mil varsayımıyla gösterimseldir, stop temaslarındaki tepeler stop yasasına bağlıdır).")
    with st.expander("Çerçeveler, işaretler ve kısıtlanan bileşenler"):
        for k, v in row["frames"].items():
            st.markdown(f"- **{k}**: {v}")
    rui._plot(views.timeline_figure(row, i, blade), "cycle_timeline")
    st.caption("Kırmızı dikey çizgi seçili durumu gösterir; numaralı noktalar olaylardır (birbirine çok yakın olaylar tek numarada "
               "toplanır, adları üzerine gelince görünür). Tüm görünümler aynı örnek indeksine bağlıdır.")
    k1, k2 = st.columns(2)
    key = rui._choice(k1.selectbox, "Bileşen", tuple(views.LOADS), key="cycle_component", default="N_tension",
                      display=lambda k: f"{views.LOADS[k][0]} [{views.LOADS[k][1]}]")
    focus = rui._choice(k2.radio, "Dikey eksen", ("whole", "operating"), key="cycle_focus", default="whole", horizontal=True,
                        display={"whole": "Tüm çevrim", "operating": "Çalışma evresi (temas dışı)"}.__getitem__)
    with k1:
        rui._plot(views.angle_figure(row, key, blade), "cycle_angle")
    with k2:
        rui._plot(views.element_figure(row, i, blade, focus), "cycle_elements")
    rui._plot(views.contribution_figure(row, key, i, blade, focus), "cycle_contrib")   # full width: long legend names
    st.caption("Kuvvet ve eğilme/burulma, ideal döner mafsalın kısıt tepkileridir; pim ekseni momentini yalnız yay, sönüm, sürtünme, "
               "stop, mandal ve aktüatör taşır. Katkılar ayrıştırmadır: toplamı (kesikli çizgi) bağlantıdan geçen yüktür, ayrıca "
               "eklenmez.")
    st.markdown(f"**Olaylar (kanat {blade + 1}) ve en büyük yükler (tüm kanatlar)**")
    st.dataframe([{"Olay": e["label"], "t [s]": round(e["time_s"], 4), "θ [°]": round(float(a["theta_deg"][e["index"]][blade]), 2),
                   "Devir [RPM]": round(float(a["rpm"][e["index"]]))} for e in events], hide_index=True,
                 **figure_style.dataframe_width_kwargs())
    st.dataframe([{"Büyüklük": p["label"], "Değer": round(p["value"], 3), "Birim": views.unit_of(p["key"]),
                   "Kanat": p.get("blade", 0) + 1, "t [s]": round(p["time_s"], 4), "θ [°]": round(p["theta_deg"], 2),
                   "Devir [RPM]": round(p["rpm"])} for p in row["peaks"]], hide_index=True, **figure_style.dataframe_width_kwargs())
    st.caption("En büyük yükler varsayılan stop yasasına (Kelvin–Voigt, ayrılmadan önce kısa çekme) ve rijit, ideal mafsala "
               "bağlıdır; gösterimseldir, donanım ölçümü değildir.")
    contacts = [c_ for c_ in row["contacts"] if c_["blade"] == blade]
    if contacts:
        st.markdown(f"**Stop temasları (kanat {blade + 1})**")
        period = math.pi * math.sqrt(row["derived"]["hinge_inertia_kg_m2"] / row["case"]["mechanism"]["stop_stiffness_nm_per_rad"])
        st.dataframe([{"Stop": "açık" if c_["stop"] == "open" else "kapalı", "Giriş [s]": round(c_["t_in_s"], 4),
                       "Süre [ms]": round(c_["duration_s"] * 1000, 2),
                       "Tür": "darbe" if c_["duration_s"] < 5 * period else "kalıcı temas (dayanma)",
                       "Tepe stop momenti [N·m]": round(c_["peak_torque_nm"], 3), "İmpuls [N·m·s]": round(c_["impulse_nm_s"], 5),
                       "Giriş hızı [rad/s]": round(c_["rate_in_rad_s"], 2),
                       "Etkin e": None if c_["effective_restitution"] is None else round(c_["effective_restitution"], 3)}
                      for c_ in contacts[:20]], hide_index=True, **figure_style.dataframe_width_kwargs())
    sens = row.get("sensitivity", {})
    if sens.get("available"):
        st.markdown("**İlk açık stop teması: sayısal ve parametre duyarlılığı**")
        st.dataframe([{"Varyant": r["variant"], "Tepe [N·m]": r.get("peak_torque_nm") and round(r["peak_torque_nm"], 3),
                       "İmpuls [N·m·s]": r.get("impulse_nm_s") and round(r["impulse_nm_s"], 5),
                       "Süre [ms]": r.get("duration_s") and round(r["duration_s"] * 1000, 2)} for r in sens["rows"]],
                     hide_index=True, **figure_style.dataframe_width_kwargs())
        st.caption(sens["reading"])
    elif "sensitivity" not in row:
        st.caption("Temas duyarlılığı hesaplanmadı (Analiz’de isteğe bağlı seçenek).")
    with st.expander("Enerji dengesi"):
        rui._plot(views.energy_figure(row, blade), "cycle_energy")
        st.caption("Mil işi (bağlantı üzerinden) + aerodinamik + yerçekimi + aktüatör işi − sönümlenen enerji = kinetik + yay/stop "
                   "enerjisi değişimi. Durağan sürtünme sürekli güç olarak görünmez (sürtünme gücü −T_f·θ̇).")
    with st.expander("Denetimler"):
        st.dataframe([{"Denetim": c_["meaning"], "Değer": c_["value"], "Sınır": c_["limit"],
                       "Sonuç": "—" if c_["passed"] is None else ("geçti" if c_["passed"] else "kaldı")} for c_ in row["checks"]],
                     hide_index=True, **figure_style.dataframe_width_kwargs())
    _connection(row, a)
    with st.expander("Oynatma (sunum hızı; fiziksel zaman çerçeve yazısında)"):
        if st.button("Oynatma hazırla", key="cycle_playback_build"):
            st.session_state["_cycle_playback"] = row["result_sha256"]
        if st.session_state.get("_cycle_playback") == row["result_sha256"]:
            rui._plot(views.playback(row, spec, frame), "cycle_playback")
            st.caption("Hız düğmeleri yalnız gösterim hızını değiştirir. Olay düğmeleri ilgili duruma atlar.")
    _compare(row)
    # the payloads are large (MB): built only on request, not on every slider or event step
    if st.button("İndirmeleri hazırla", key="cycle_downloads_build"):
        st.session_state["_cycle_downloads"] = row["result_sha256"]
    if st.session_state.get("_cycle_downloads") == row["result_sha256"]:
        name = f"pyfoldable_cevrim_{row['result_sha256'][:8]}"
        d1, d2, d3 = st.columns(3)
        d1.download_button("Zaman serisi CSV", views.series_csv(row), name + ".csv", "text/csv")
        d2.download_button("Kayıt JSON", json.dumps(row, ensure_ascii=False), name + ".json", "application/json")
        if st.session_state.get("_cycle_playback") == row["result_sha256"]:
            d3.download_button("Oynatma HTML (çevrimdışı açılır)", views.playback(row, spec, frame).to_html(include_plotlyjs=True),
                               name + ".html", "text/html")


def _connection(row, a):
    with st.expander("Bağlantı ön kontrolü (pim–kulak, çatal–dil)"):
        st.caption("Bağlantı yük geçmişinden el formülleriyle ön tahmin. Ölçü ve malzeme izin verilen gerilmeleri girilmeden kontrol "
                   "yapılmaz. Gerilme alanı değildir; parça niteliklendirmesi değildir.")
        c = st.columns(3)
        num = lambda col, label, key: rui._field(col.number_input, label, key, 0.0, min_value=0.0)  # noqa: E731
        d = num(c[0], "Pim çapı [mm]", "cycle_pin_d")
        tt = num(c[1], "Dil kalınlığı [mm]", "cycle_tang_t")
        tp = num(c[2], "Çatal plaka kalınlığı [mm]", "cycle_plate_t")
        gap = num(c[0], "Boşluk (her yan) [mm]", "cycle_gap")
        w = num(c[1], "Dil genişliği [mm] (0: yok)", "cycle_tang_w")
        ed = num(c[2], "Pim merkezi–dil ucu [mm] (0: yok)", "cycle_tang_e")
        al = st.columns(3)
        allow = {k: num(al[n % 3], lbl, f"cycle_allow_{k}")
                 for n, (k, lbl) in enumerate((("pin_shear_pa", "Pim kesme izni [MPa]"), ("pin_bending_pa", "Pim eğilme izni [MPa]"),
                                               ("tang_bearing_pa", "Dil yatak izni [MPa]"), ("plate_bearing_pa", "Plaka yatak izni [MPa]"),
                                               ("tang_tension_pa", "Dil çekme izni [MPa]"), ("tang_shear_pa", "Dil kesme izni [MPa]")))}
        source = rui._field(st.text_input, "İzin değerlerinin kaynağı (malzeme verisi, standart veya test)", "cycle_allow_source", "",
                            help="Kaynak girilmeden izin değerleri pay veya yeterlilik sonucu vermez.")
        if min(d, tt, tp) <= 0:
            st.info("Pim çapı, dil ve plaka kalınlığı girilmeden ön kontrol yapılmaz (bağlantı ölçüleri tasarımda tanımlı değil).")
            return
        try:
            geom = pl.PinLugGeometry(d / 1000, tt / 1000, tp / 1000, gap / 1000, (w / 1000) or None, (ed / 1000) or None)
        except ValueError as exc:
            st.error(str(exc))
            return
        allowables = pl.Allowables(**{k: (v * 1e6) or None for k, v in allow.items()}, source=source)
        # every stored blade is checked and each row shows its governing blade (identical blades: blade 1 only)
        blades = range(row["case"]["blade_count"] if "events_by_blade" in row else 1)
        res = [pl.connection_checks({k: a[f"load_{k}"][:, b] for k in ("N_tension", "V_inplane", "V_axial", "M_torsion", "M_bending")},
                                    geom, allowables, a["time_s"]) for b in blades]
        worst = [max(((b, rs["rows"][j]) for b, rs in enumerate(res)), key=lambda br: br[1]["peak_pa"])
                 for j in range(len(res[0]["rows"]))]                  # same geometry: same rows in the same order
        st.dataframe([{"Kontrol": r["label"], "Kanat": b + 1, "Tepe gerilme [MPa]": round(r["peak_pa"] / 1e6, 2),
                       "t [s]": r["time_s"] and round(r["time_s"], 4), "İzin [MPa]": r["allowable_pa"] and round(r["allowable_pa"] / 1e6, 1),
                       "Pay (izin/gerilme − 1)": None if r["margin"] is None else round(r["margin"], 2), "Durum": r["status"]}
                      for b, r in worst], hide_index=True, **figure_style.dataframe_width_kwargs())
        first = res[0]
        st.caption(first["scope"] + f" Plaka eksen aralığı {first['plate_spacing_m'] * 1000:.1f} mm; pim boyunca kuvvet (en büyük "
                   f"{max(abs(x) for rs in res for x in rs['pin_axial_force_n']):.2f} N) pim başı/omuz ile taşınır, kontrol edilmedi."
                   + (f" Eksik ölçüler: {', '.join(first['unavailable_checks'])}." if first["unavailable_checks"] else ""))


def _compare(row):
    others = [s for s in saved() if s["sha"] != row["result_sha256"]]
    with st.expander("Başka bir çevrimle karşılaştır"):
        if not others:
            st.caption("Karşılaştırma için en az iki kaydedilmiş çevrim gerekir.")
            return
        by = {s["sha"]: s for s in others}
        pick = rui._choice(st.selectbox, "Karşılaştırılacak çevrim", tuple(by), key="cycle_compare", default=tuple(by)[0],
                           display=lambda k: f"{by[k]['profile']} · {by[k]['rpm']:.0f} RPM · δ {by[k]['offset_mm']:.0f} mm · {PRESETS.get(by[k]['preset'], by[k]['preset'])}")
        try:
            other = _read(by[pick]["path"])
        except (OSError, ValueError, KeyError, TypeError):            # removed or changed after it was listed
            st.warning("Karşılaştırılacak çevrim doğrulanamadı (dosya silinmiş veya değişmiş olabilir).")
            return
        key = st.session_state.get("cycle_component", "N_tension")
        rui._plot(views.compare_figure([other, row], key), "cycle_compare_fig")
        diff = []
        for group in ("schedule", "mechanism", "aero"):
            for k, v in row["case"][group].items():
                o = other["case"][group].get(k)
                if k != "strips" and o != v:
                    diff.append({"Alan": f"{group}.{k}", "Ç1": str(o), "Ç2 (bu)": str(v)})
        if other.get("geometry", {}).get("profile_id") != row.get("geometry", {}).get("profile_id"):
            diff.append({"Alan": "profil", "Ç1": other["geometry"]["profile_id"], "Ç2 (bu)": row["geometry"]["profile_id"]})
        st.dataframe(diff or [{"Alan": "—", "Ç1": "aynı", "Ç2 (bu)": "aynı"}], hide_index=True, **figure_style.dataframe_width_kwargs())
        st.caption("Farklı devir profilleri, aerodinamik model veya mekanizma varsayımları karşılaştırmanın koşuludur; tabloda görünür.")


# ---------------------------------------------------------------------------------------------- kayıtlar
def saved_panel():
    items = saved()
    st.markdown("**Kaydedilen açılma–kapanma çevrimleri**")
    if not items:
        st.caption(f"Henüz yok. Analiz’de “Çevrimi çalıştır” ile oluşan her çevrim {cycles_root()} klasörüne yazılır.")
        return
    import datetime
    st.dataframe([{"Kaydedildi": datetime.datetime.fromtimestamp(s["saved"]).strftime("%Y-%m-%d %H:%M"), "Profil": s["profile"],
                   "Mekanizma": PRESETS.get(s["preset"], s["preset"]), "Devir": round(s["rpm"]), "δ [mm]": round(s["offset_mm"], 1),
                   "Kapalıya döndü": "evet" if s["returned"] else "hayır", "Mod": MODES[s["mode"]][0]} for s in items],
                 hide_index=True, **figure_style.dataframe_width_kwargs())
    by = {s["sha"]: s for s in items}
    pick = rui._choice(st.selectbox, "Açılacak çevrim", tuple(by), key="cycle_saved_pick", default=tuple(by)[0],
                       display=lambda k: f"{by[k]['profile']} · {PRESETS.get(by[k]['preset'], by[k]['preset'])} · {by[k]['rpm']:.0f} RPM")
    st.button("Çevrimi aç (yeniden hesaplanmaz)", key="cycle_saved_open", on_click=_open, args=(by[pick]["path"],))


# ------------------------------------------------------------------------------------- bağlaşık kayıt yükleri
def coupled_loads_tab(row, root):
    from pyfoldable.coupled import hinge_loads

    from . import coupled_analysis
    st.caption("MBDyn’in kendi mafsal tepkileri: ideal döner mafsal (kuvvetler, eğilme, burulma) + menteşe yasası ve mandal (pim "
               "ekseni). Dış parça Newton–Euler dengesi ile bağımsız denetlenir. Örnekleme pencere başına birdir; temas tepeleri "
               "penaltı stopunun pencere örnekleridir. Momentler pim üzerindeki menteşe noktasına göredir (bağlaşık model eksenel "
               "kaydırma içermez); mekanik çevrimde dil orta düzlemine göre raporlanır.")
    run_dir = coupled_analysis.local_run_dir(root, row) if root is not None else None
    if run_dir is None:
        st.info("Bu kaydın çalıştırma klasörü bu bilgisayarda yok; bağlantı yükleri ham MBDyn çıktısından türetilir.")
        return
    if not (run_dir / "structure" / "out.jnt").is_file():
        st.info("Bu çalıştırma klasöründe ham MBDyn mafsal çıktısı (structure/out.jnt) yok; bağlantı yükleri türetilemez.")
        return
    comp = hinge_loads.load(run_dir, row)
    if comp is None:
        if not st.button("Bağlantı yüklerini türet (çözücü çalışmaz)", key="coupled_hinge_loads_build"):
            return
        with st.spinner("MBDyn mafsal çıktısı okunuyor ve denge denetleniyor…"):
            try:
                comp = hinge_loads.extract(run_dir, row)
                hinge_loads.store(run_dir, comp)
            except (OSError, ValueError, KeyError) as exc:
                st.error("Bağlantı yükleri türetilemedi: " + str(exc))
                return
    nb = len(comp["blades"])
    blade = rui._choice(st.radio, "Kanat", tuple(range(nb)), key="coupled_hinge_blade", default=0, horizontal=True,
                        display=lambda b: f"Kanat {b + 1}") if nb > 1 else 0
    rui._plot(views.coupled_figure(comp, row, blade), "coupled_hinge_loads_fig")
    k0 = comp["startup_transient_windows"]
    st.caption(f"Kırmızı bölge: ilk {k0} pencere — MBDyn kısıt tepkilerinin başlangıç sayısal geçişi; tepe ve denetimlerden "
               "hariç. Turuncu çizgiler stop temas pencereleri.")
    if overlaps := comp.get("startup_overlaps"):
        names = {"release": "mandal bırakma", "first_contact": "ilk stop teması"}
        whose = lambda o: "" if o["blade"] is None else f" (kanat {o['blade'] + 1})"  # noqa: E731
        st.warning("Başlangıç geçişi içinde kalan olaylar; yükleri tepe ve denetimlerde yoktur: " + "; ".join(
            f"{names.get(o['event'], o['event'])}{whose(o)} · pencere {o['window']} · t = {o['time_s']:.4f} s" for o in overlaps) + ".")
    st.markdown("**En büyük yükler (tüm kanatlar)**")
    st.dataframe([{"Büyüklük": p["label"], "Değer": round(p["value"], 3), "Birim": views.unit_of(p["key"]), "Kanat": p.get("blade", 0) + 1,
                   "Pencere": p["window"], "t [s]": round(p["time_s"], 5), "θ [°]": round(p["theta_deg"], 2),
                   "Temasta": "evet" if p["in_contact"] else "hayır"} for p in comp["peaks"]],
                 hide_index=True, **figure_style.dataframe_width_kwargs())
    if not comp["checks"]:
        st.info("Newton–Euler denetimi yapılmadı. " + (comp.get("checks_skipped_reason") or ""))
        return
    st.dataframe([{"Denetim": c["meaning"], "Değer": round(c["value"], 4), "Sınır": c["limit"], "Sonuç": "geçti" if c["passed"] else "kaldı"}
                  for c in comp["checks"]], hide_index=True, **figure_style.dataframe_width_kwargs())
