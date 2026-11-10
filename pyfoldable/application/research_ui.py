"""Turkish single-screen research flow. Provider acquisition is operator-only."""
from dataclasses import replace
import json
import math
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS, load_project_airfoil
from pyfoldable.visualization.propeller_25d import (
    PreviewBladeStation, PropellerPreviewSpec, build_propeller_preview_mesh,
)
from . import provider_design_analysis as managed, research_design as research

_HISTORY = "research_saved_results"
_ACTIVE = "research_active"
_MAX_HISTORY = 12


def _geometry(active):
    d, i = active.design, active.inputs
    result = research.geometry_result(active)
    audit = result["centerline"]
    a, b, c = st.columns(3)
    p = result["proximal_m"]
    a.metric("Proksimal [mm]", "Kök beyanı yok" if p is None else f"{1000*p:.2f}")
    b.metric("Distal [mm]", f"{1000*result['distal_m']:.2f}")
    c.metric("Katlı merkez çizgisi zarfı [mm]", f"{1000*audit['centerline_envelope_diameter_m']:.2f}")
    st.caption(f"Göbek {1000*d.blade.hub_radius_m:.2f} mm · ilk aero istasyonu "
               f"{1000*result['first_aerodynamic_station_m']:.2f} mm · "
               f"merkez çizgisi hedef payı {1000*audit['current_requirement_margin_m']:.2f} mm. "
               "Bu ölçüler yüzey açıklığı veya çarpışmasız hareket kanıtı değildir.")
    st.caption(f"Beyan edilen {i.stow_limit_deg:g}° alt sınırdaki merkez çizgisi zarfı: "
               f"{1000*result['declared_stow_limit_centerline_envelope_m']:.2f} mm. "
               "Eski denetimin tam katlanma minimumları varsayımsal −180° hareket içindir.")
    if active.length_order_policy == "proximal_longer" and result["proximal_longer"] is not True:
        st.warning("250 mm proje şablonu: beyan edilen kökten menteşeye olan parça daha uzun olmalı.")
    with st.expander("Profil, planform ve katlı yüzey önizlemesi", expanded=True):
        foil = load_project_airfoil(i.profile)
        try:
            mesh = build_propeller_preview_mesh(
                PropellerPreviewSpec(d.blade.diameter_m, d.blade.hub_radius_m, d.blade.blade_count,
                                     d.hinge.radius_m, i.fold_deg, i.profile, airfoil_definition=foil),
                tuple(PreviewBladeStation(s.r_over_R, s.chord_m, math.degrees(s.twist_rad)) for s in d.blade.stations),
            )
            x, y, z = zip(*mesh.vertices)
            f0, f1, f2 = zip(*mesh.faces)
            fig = go.Figure(go.Mesh3d(x=x, y=y, z=z, i=f0, j=f1, k=f2, color="#168c91"))
            fig.update_layout(height=335, scene_aspectmode="data", margin=dict(l=0, r=0, t=5, b=0),
                              scene=dict(xaxis_title="x [m]", yaxis_title="y [m]", zaxis_title="z [m]"))
            st.plotly_chart(fig, use_container_width=True, key="research_mesh")
        except ValueError as exc:
            st.warning(f"Yüzey önizlemesi kullanılamıyor: {exc}")
        st.caption(f"{i.profile} · koordinat SHA-256 {active.coordinate_sha256}. Görsel, imalat veya temas modeli değildir.")
        st.dataframe([{"r/R": s.r_over_R, "kord [mm]": 1000*s.chord_m,
                       "burulma [°]": math.degrees(s.twist_rad)} for s in d.blade.stations], hide_index=True)


def _mechanics():
    with st.expander("İsteğe bağlı mekanizma girdileri"):
        st.caption("Tek rijit dış parça, düzlemsel +z menteşe, beyan edilen doğrusal RPM rampası. "
                   "İlk stop temasında durur; aerodinamik yük, geri besleme, temas tepkisi ve dayanım hesaplanmaz.")
        if not st.checkbox("Mekanizma hesabını da çalıştır", key="research_mechanics_on"):
            return None
        cols = st.columns(3)
        mass = cols[0].number_input("Dış parça kütlesi [g]", min_value=0.001, value=None, key="mech_mass")
        cg = cols[1].number_input("Menteşeden CG [mm]", min_value=0., value=None, key="mech_cg")
        inertia = cols[2].number_input("CG etrafı atalet [kg·m²]", min_value=0., value=None, format="%.9f", key="mech_inertia")
        source = st.text_input("Mekanik girdi kaynağı / varsayım beyanı", key="mech_source", max_chars=240)
        start = cols[0].number_input("Rampa başlangıcı [RPM]", 0., 20000., 0., key="mech_rpm")
        duration = cols[1].number_input("Rampa süresi [s]", 0.01, 5., .5, key="mech_duration")
        velocity = cols[2].number_input("İlk açısal hız [rad/s]", -1000., 1000., 0., key="mech_velocity")
        spring = cols[0].number_input("Yay [N·m/rad]", 0., 100., 0., key="mech_spring")
        rest = cols[1].number_input("Yay denge açısı [°]", -180., 0., 0., key="mech_rest")
        damping = cols[2].number_input("Viskoz sönüm [N·m·s/rad]", 0., 100., 0., key="mech_damping")
        torque = cols[0].number_input("Uygulanan sabit menteşe momenti [N·m]", -100., 100., 0., key="mech_torque")
        friction = cols[1].selectbox("Kuru sürtünme modeli", ("none", "regularized_coulomb"), key="mech_friction")
        coulomb = transition = 0.
        if friction != "none":
            coulomb = cols[0].number_input("Coulomb momenti [N·m]", 0.000001, 100., .001, format="%.6f")
            transition = cols[1].number_input("Düzenleme hızı [rad/s]", .001, 100., .1)
        if None in (mass, cg, inertia) or not source.strip():
            st.info("Kütle, CG, atalet ve kaynak beyanı eksik. Geometri ve BEM bağımsız çalışabilir.")
        return research.MechanismInputs(mass, cg, inertia, source, start, duration, velocity,
                                        spring, rest, damping, torque, friction, coulomb, transition)


def _family(active, root):
    try:
        repo = managed.application_provider_repository()
    except (ValueError, OSError) as exc:
        st.warning(f"Polar deposu: {exc}")
        return None, managed.ManagedProviderRepository(), str(exc), None
    families = {f.stored_version.content_sha256: f for f in repo.families if f.stored_version and f.requests}
    initial = research.initial_query_ranges(active)
    with st.expander("Altı profil için polar veri durumu", expanded=True):
        rows = []
        for profile in PROJECT_AIRFOIL_IDS:
            matched = [f for f in families.values() if f.requests[0].airfoil.id == profile]
            if not matched:
                rows.append({"Profil": profile, "Kayıt": "Eşleşen veri yok", "Re": None, "Mach": None, "α [°]": None,
                             "İlk sorgu aralığı": "Veri yok"})
            for f in matched:
                re = [r.reynolds for r in f.requests]
                ma = [r.mach for r in f.requests]
                alpha = [math.degrees(a) for r in f.requests for a in r.alpha_rad]
                try:
                    candidate = active if profile == active.inputs.profile else research.build_research_design(
                        root, replace(active.inputs, profile=profile))
                    research.prepare_aero(candidate, f, repo)
                    admission_status = "Tam kayıt adayı · bilimsel doğrulama değil"
                except (ValueError, OSError) as exc:
                    admission_status = f"Eksik / reddedildi: {exc}"
                rows.append({"Profil": profile, "Kayıt": f.stored_version.version_label + " · " + admission_status,
                             "Re": f"{min(re):g}…{max(re):g}", "Mach": f"{min(ma):g}…{max(ma):g}",
                             "α [°]": f"{min(alpha):g}…{max(alpha):g}",
                             "İlk sorgu aralığı": "Izgara içinde; tam yol garanti değil"
                             if research.declared_grid_covers_initial(f, initial) else "Izgara dışında"})
        st.dataframe(rows, hide_index=True)
        st.caption(f"Bu girdilerin koşullu ilk annulus sorguları: α "
                   f"{math.degrees(initial[0][0]):.2f}…{math.degrees(initial[0][1]):.2f}°; "
                   f"Re {initial[1][0]:.0f}…{initial[1][1]:.0f}; "
                   f"Mach {initial[2][0]:.3f}…{initial[2][1]:.3f}. Henüz çözücü gözlemi değildir.")
    profile = active.inputs.profile
    candidates = {k: f for k, f in families.items() if f.requests[0].airfoil.id == profile}
    key = f"research_version_{profile}"
    previous = st.session_state.get(key)
    if previous is not None and previous not in candidates:
        st.session_state[key] = None
        st.warning("Önceki sürüm bulunamadı. Başka kayıt seçilmedi.")
    if not candidates:
        st.info(f"{profile}: geometri seçilebilir; eşleşen kayıt yok. BEM sonucu üretilmez.")
        return None, repo, None, None
    chosen = st.selectbox("Saklanan polar sürümü", (None, *candidates), key=key,
                         format_func=lambda k: "Sürüm seçin" if k is None else f"{candidates[k].family_id} · {k[:12]}")
    if chosen is None:
        return None, repo, None, None
    family = candidates[chosen]
    try:
        prepared = research.prepare_aero(active, family, repo)
    except (ValueError, OSError) as exc:
        st.warning(f"Sayısal hazırlık engellendi: {exc}")
        return family, repo, None, None
    st.caption(f"{profile}: {len(family.requests)} hücre kabul edildi · {family.evidence_class}. "
               "Gerçek deneme sorgularının kapsamı, sınır hatasıyla duran BEM sırasında denetlenir.")
    return family, repo, None, prepared.request_sha256


def _render_result(row):
    aero = row["aerodynamics"]
    if aero["status"] == "success":
        a, b, c = st.columns(3)
        a.metric("İtki [N]", f"{aero['thrust_n']:.6g}")
        b.metric("Şaft torku [N·m]", f"{aero['torque_nm']:.6g}")
        c.metric("Şaft gücü [W]", f"{aero['shaft_power_w']:.6g}")
        st.success(f"{aero['airfoil_id']} · BEM tamamlandı · {aero['evidence_class']}")
        st.caption(f"Tam açık ana kanat · {1000*aero['inner_radius_m']:.1f}–{1000*aero['outer_radius_m']:.1f} mm istasyon kapsamı · "
                   "eklem kaybı, kısmi açılma, motor/elektrik modeli yok. Menteşe yeri tek başına bu ideal BEM yükünü değiştirmez.")
        radial = research.radial_rows(row)
        with st.expander("Radyal yükler, α / Re / Mach ve sorgu kapsamı", expanded=True):
            st.dataframe(radial, column_order=("element", "radius_m", "alpha_deg", "reynolds", "mach",
                                               "thrust_n", "torque_nm", "dthrust_n_per_m", "dtorque_nm_per_m"), hide_index=True)
            st.json(aero["polar_query_envelope"], expanded=False)
        st.download_button("Radyal yükleri CSV indir", research.records_csv(radial),
                           f"{aero['airfoil_id']}_radial.csv", "text/csv", key="research_radial_csv")
    else:
        st.warning(f"BEM sonucu yok: {aero['failure_reason']}")
    mech = row["mechanism"]
    if mech["status"] == "computed":
        result = json.loads(mech["report_text"])["result"]
        with st.expander("Mekanizma hareket geçmişi", expanded=True):
            st.caption("Beyan edilen sürüş altında tek rijit parçanın ilk temasa kadar hareketi.")
            st.dataframe(result["samples"], column_order=("time_s", "angle_rad", "rpm", "centrifugal_torque_nm",
                                                         "euler_torque_nm", "dry_friction_torque_nm"), hide_index=True)
            st.json({k: v for k, v in result.items() if "contact" in k or "termination" in k}, expanded=False)
    elif mech["status"] == "missing_inputs":
        st.caption("Mekanizma: ayrı kütle/CG/atalet ve sürüş girdileri verilmedi.")
    else:
        st.warning(f"Mekanizma durumu: {mech['reason']}")
    st.download_button("Tam sonucu JSON indir", research.saved_result_json(row),
                       "pyfoldable_research_result.json", "application/json", key="research_active_json")


def _save(row, *, imported=False):
    history = st.session_state.setdefault(_HISTORY, ())
    if any(json.loads(raw)["result_sha256"] == row["result_sha256"] for raw, _ in history):
        return
    if len(history) >= _MAX_HISTORY:
        st.warning("Oturumda en fazla 12 kayıt tutulur. Önceki kayıtları dışa aktarabilirsiniz.")
        return
    st.session_state[_HISTORY] = (*history, (research.saved_result_json(row), imported))


def _history():
    st.subheader("Saklanan sonuçlar ve profil karşılaştırması")
    with st.expander("Önceki uygulama sonucunu aç (isteğe bağlı)"):
        st.caption("Yalnız bu ekranın indirdiği sonuç JSON dosyası. İçe aktarma bir hesap başlatmaz; içerik kimliği doğrulanır.")
        uploaded = st.file_uploader("Sonuç JSON", type=("json",), key="research_restore")
        if st.button("Sonucu geçmişe ekle", disabled=uploaded is None):
            try:
                _save(research.read_saved_result(uploaded.getvalue()), imported=True)
            except (ValueError, OSError) as exc:
                st.error(f"Sonuç açılamadı: {exc}")
    retained = [(json.loads(raw), imported) for raw, imported in st.session_state.get(_HISTORY, ())]
    if not retained:
        return
    records = {r["result_sha256"]: (r, imported) for r, imported in retained}
    summary = [{"profile": r["aerodynamics"]["airfoil_id"], "status": r["aerodynamics"]["status"],
                "result_sha256": r["result_sha256"], "coordinate_sha256": r["aerodynamics"]["airfoil_coordinate_sha256"],
                "thrust_n": r["aerodynamics"]["thrust_n"], "torque_nm": r["aerodynamics"]["torque_nm"],
                "shaft_power_w": r["aerodynamics"]["shaft_power_w"], "imported": imported}
               for r, imported in retained]
    st.dataframe(summary, hide_index=True)
    chosen = st.multiselect("Karşılaştırılacak iki kayıt", tuple(records), max_selections=2,
        format_func=lambda k: f"{records[k][0]['aerodynamics']['airfoil_id']} · {k[:12]}", key="research_compare")
    chosen_records = [records[k][0] for k in chosen]
    if len(chosen_records) == 2:
        comparison = research.compare_results(chosen_records)
        if comparison["matched_numerical_comparison"]:
            st.success("Farklı koordinatlar, eş planform/koşul ve eş polar/BEM politikası: eşleştirilmiş sayısal sonuçlar.")
        else:
            st.info("Kontrollü sayısal çift oluşmadı: " +
                    ", ".join(comparison["mismatch_reasons"] + comparison["profile_reasons"]) +
                    ("; sağlayıcı sözleşmesi farklı/eksik" if not comparison["matching_retained_provider_contract"] else ""))
        st.download_button("Karşılaştırmayı JSON indir", json.dumps({
            "schema_version": 1, "artifact_class": "pyfoldable_research_comparison",
            "assessment": comparison, "results": chosen_records,
        }, indent=2, ensure_ascii=False, allow_nan=False), "research_comparison.json", "application/json")
        st.download_button("Karşılaştırmayı CSV indir", research.records_csv([r for r in summary if r["result_sha256"] in chosen]),
                           "research_comparison.csv", "text/csv")
    saved = st.selectbox("Arşivden indirilecek sonuç", tuple(records),
        format_func=lambda k: f"{records[k][0]['aerodynamics']['airfoil_id']} · {k[:12]}")
    st.download_button("Arşivdeki sonucu JSON indir", research.saved_result_json(records[saved][0]),
                       "pyfoldable_saved_result.json", "application/json", key="research_saved_json")


def render_research(root: Path):
    st.title("PyFoldable · Araştırma tasarımı")
    st.caption("Profil → geometri ve akış → açık çalıştırma → sonuç → karşılaştırma. "
               "Tasarım veya polar dosyası gerekmez. Sayısal tahmin; deneysel uyum değerlendirilmedi, fiziksel yeterlilik yok.")
    template = st.selectbox("Kord / burulma şablonu", tuple(research.TEMPLATES), key="research_template",
        format_func=lambda v: {"axial_800": "800 mm eksenel araştırma referansı · iki uzunluk sırası",
                               "project_250": "250 mm / 7100 RPM proje örneği · proksimal uzun"}[v])
    d = research.defaults(root, template)
    profile = st.selectbox("Katalog profili", PROJECT_AIRFOIL_IDS, index=1, key="research_profile")
    c = st.columns(3)

    def number(index, label, field, minimum, maximum, **kwargs):
        return c[index].number_input(label, min_value=minimum, max_value=maximum,
            value=getattr(d, field), key=f"research_{template}_{field}", **kwargs)

    diameter = number(0, "Çap [mm]", "diameter_mm", 50., 2000.)
    hub = number(1, "Göbek yarıçapı [mm]", "hub_mm", 0.01, 999.)
    hinge = number(2, "Menteşe yarıçapı [mm]", "hinge_mm", .01, 999.)
    root_mm = number(0, "Fiziksel kanat kökü r_root [mm]", "root_mm", 0., 999.)
    root_meaning = c[1].text_input("Kökün anlamı", d.root_meaning, max_chars=240, key=f"root_meaning_{template}")
    root_source = c[2].text_input("Kökün kaynak / beyan kimliği", d.root_source, max_chars=240, key=f"root_source_{template}")
    root_kind = c[0].selectbox("Kök beyan türü", ("study_assumption", "declared_geometry"),
                             format_func=lambda k: "Çalışma varsayımı" if k == "study_assumption" else "Beyan edilen geometri")
    rpm = number(1, "Devir [RPM]", "rpm", 1., 20000.)
    inflow = number(2, "Eksenel giriş hızı [m/s]", "inflow_m_s", 0., 100.)
    fold = number(0, "Katlı önizleme açısı [°]", "fold_deg", -180., 0.)
    stow = number(1, "Alt katlanma sınırı [°]", "stow_limit_deg", -180., -.01)
    target = number(2, "Merkez çizgisi çap hedefi [mm]", "stowed_target_mm", 1., 2000.)
    with st.expander("Planform ölçekleri ve akışkan girdileri"):
        c = st.columns(3)
        blades = number(0, "Kanat sayısı", "blade_count", 1, 8)
        chord = number(1, "Kord çarpanı", "chord_scale", .05, 5.)
        twist = number(2, "Burulma çarpanı", "twist_scale", 0., 5.)
        rho = number(0, "Yoğunluk [kg/m³]", "density_kg_m3", .01, 10.)
        mu = number(1, "Dinamik viskozite [Pa·s]", "viscosity_pa_s", 1e-7, .001, format="%.8f")
        temp = number(2, "Sıcaklık [K]", "temperature_k", 100., 800.)
        pressure = number(0, "Basınç [Pa]", "pressure_pa", 1000., 500000.)
        annuli = number(1, "Radyal annulus sayısı", "annulus_count", 4, 80)
    inputs = replace(d, profile=profile, diameter_mm=diameter, hub_mm=hub, hinge_mm=hinge, root_mm=root_mm,
        root_meaning=root_meaning, root_source=root_source, root_kind=root_kind, blade_count=blades,
        rpm=rpm, inflow_m_s=inflow, fold_deg=fold, stow_limit_deg=stow, stowed_target_mm=target,
        chord_scale=chord, twist_scale=twist, density_kg_m3=rho, viscosity_pa_s=mu, temperature_k=temp,
        pressure_pa=pressure, annulus_count=annuli)
    try:
        active = research.build_research_design(root, inputs)
        _geometry(active)
    except (TypeError, ValueError, OSError) as exc:
        st.session_state.pop(_ACTIVE, None)
        st.error(f"Tasarım hazırlanamadı: {exc}")
        _history()
        return
    family, repository, reason, prepared_identity = _family(active, root)
    mechanics = _mechanics()
    view_id = (active.identity, mechanics, prepared_identity,
               None if family is None else family.stored_version.content_sha256, reason)
    current = st.session_state.get(_ACTIVE)
    if current is not None and current[0] != view_id:
        st.session_state.pop(_ACTIVE, None)
    if st.button("Analizi çalıştır", type="primary", key="research_run"):
        with st.spinner("Seçilen kapsamlar hesaplanıyor…"):
            row = research.run_research(active, family, repository, mechanics, unavailable_reason=reason)
            st.session_state[_ACTIVE] = (view_id, research.saved_result_json(row))
            _save(row)
    current = st.session_state.get(_ACTIVE)
    if current is not None:
        _render_result(json.loads(current[1]))
    _history()
