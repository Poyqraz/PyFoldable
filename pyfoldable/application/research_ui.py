"""Normal research workspace. All numerical execution is user-initiated."""
from dataclasses import dataclass, replace
import json
import math
from pathlib import Path

import streamlit as st

from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS, load_project_airfoil

from . import provider_design_analysis as managed, research_design as research, research_views as views

_HISTORY = "research_saved_results"
_ACTIVE = "research_active"
_PAGE = "research_page"
_PAGES = ("Tasarım", "Analiz", "Sonuçlar", "Karşılaştırma / kayıtlar")
_MAX_HISTORY = 12
_TEMPLATE_LABELS = {
    "axial_800": "800 mm eksenel referans · iki uzunluk sırası",
    "project_250": "250 mm proje şablonu · proksimal daha uzun",
}


def _fmt(number, digits=2):
    return "—" if number is None else f"{number:.{digits}f}".replace(".", ",")


def _seed(key, fallback, shape=None):
    """Widget defaults remain stable while visible (including Streamlit 1.40).

    The separate values map survives native widget cleanup on other pages.
    """
    seeds = st.session_state.setdefault("_research_widget_seeds", {})
    values = st.session_state.setdefault("_research_control_values", {})
    if key not in st.session_state or key not in seeds or seeds[key][0] != shape:
        seeds[key] = (shape, values.get(key, fallback))
    return seeds[key][1]


def _remember(key, value):
    st.session_state["_research_control_values"][key] = value
    return value


def _choice(control, label, options, *, key, default, display=str, **kwargs):
    labels = tuple(display(v) for v in options)
    value = _seed(key, default, labels)
    index = options.index(value) if value in options else options.index(default)
    return _remember(key, control(label, options, index=index, key=key, format_func=display, **kwargs))


def _field(control, label, key, default, **kwargs):
    return _remember(key, control(label, value=_seed(key, default), key=key, **kwargs))


def _repository():
    try:
        return managed.application_provider_repository(), None
    except (ValueError, OSError) as exc:
        return managed.ManagedProviderRepository(), str(exc)


def _families(repository, profile, coordinate):
    return {f.stored_version.content_sha256: f for f in repository.families
            if f.stored_version and f.requests and f.requests[0].airfoil.id == profile
            and airfoil_coordinate_sha256(f.requests[0].airfoil) == coordinate}


def _inventory(repository, error, profile):
    count = len(_families(repository, profile, airfoil_coordinate_sha256(load_project_airfoil(profile))))
    if error:
        return "Depo okunamadı"
    return f"{count} saklanan sürüm · kapsam Analiz’de" if count else "Eşleşen veri yok"


def _plot(fig, key):
    st.plotly_chart(fig, use_container_width=True, key=key,
                    config={"displaylogo": False, "scrollZoom": False})


def _reset_camera():
    revision = st.session_state.get("_research_camera_revision", 0)
    key = f"research_camera_{revision}"
    st.session_state["_research_control_values"].pop(key, None)
    st.session_state["_research_widget_seeds"].pop(key, None)
    st.session_state["_research_camera_revision"] = revision + 1


def _geometry(active):
    d, i = active.design, active.inputs
    result = research.geometry_result(active)
    audit = result["centerline"]
    st.subheader("Geometri önizlemesi")
    if active.length_order_policy == "proximal_longer" and result["proximal_longer"] is not True:
        st.warning("250 mm proje şablonu için kök beyan edin ve iç parçayı dış parçadan uzun tutun.")
    view = _choice(st.radio, "Görünüm", ("Plan", "3B", "Profil"), horizontal=True,
                   key="research_preview", default="Plan")
    foil = next(f for f in d.airfoils if f.id == i.profile)
    if view == "Profil":
        st.caption(f"{i.profile} · Katalog kesiti, iki eksen aynı kord ölçeğinde.")
        _plot(views.airfoil_figure(foil), "research_airfoil")
    else:
        st.caption(f"Gösterilen katlanma pozu: {_fmt(i.fold_deg, 1)}°. BEM, ana kanadı tam açık (0°) çözer.")
        try:
            if view == "3B":
                revision = st.session_state.get("_research_camera_revision", 0)
                controls, reset = st.columns((1.5, 1), vertical_alignment="bottom")
                camera = _choice(controls.selectbox, "Kamera", tuple(views.CAMERAS),
                                 key=f"research_camera_{revision}", default="İzometrik")
                reset.button("Kamerayı sıfırla", on_click=_reset_camera)
                _plot(views.surface_figure(active, foil, camera, revision), "research_surface")
                st.caption("3B için tarayıcıda WebGL gerekir. Plan ve profil görünümleri WebGL gerektirmez.")
            else:
                _plot(views.plan_figure(active, foil), "research_plan")
        except ValueError as exc:
            st.warning("Bu konumda saklanan istasyonlardan yüzey çizilemiyor. Menteşe ve istasyon açıklığını kontrol edin.")
            with st.expander("Önizleme teknik ayrıntısı"):
                st.text(str(exc))
    st.markdown(
        f"**İç parça — proksimal:** {_fmt(1000 * result['proximal_m'] if active.root else None, 1)} mm  \n"
        f"**Dış parça — distal:** {_fmt(1000 * result['distal_m'], 1)} mm"
    )
    st.caption(
        f"Göbek {_fmt(i.hub_mm, 1)} mm · fiziksel kök {_fmt(i.root_mm, 1)} mm · "
        f"ilk aero istasyonu {_fmt(1000*result['first_aerodynamic_station_m'], 1)} mm. "
        "Üçü ayrı radyal konumdur."
    )
    st.caption(
        f"Bu pozdaki merkez çizgisi zarfı: {_fmt(1000*audit['centerline_envelope_diameter_m'], 1)} mm · "
        f"beyan edilen alt sınırdaki zarf: {_fmt(1000*result['declared_stow_limit_centerline_envelope_m'], 1)} mm. "
        "Kesikli gri çizgiler yüzey verisi olmayan aralıkları gösterir. Bu bir açıklık veya temas hesabı değildir."
    )
    with st.expander("Kord ve burulma istasyonları"):
        st.dataframe([{"Yarıçap [mm]": 1000*s.r_over_R*d.blade.radius_m, "r/R": s.r_over_R,
                       "Kord [mm]": 1000*s.chord_m, "Burulma [°]": math.degrees(s.twist_rad)}
                      for s in d.blade.stations], hide_index=True, use_container_width=True)


def _edit_design(root, repository, store_error):
    st.subheader("Tasarım")
    profile = _choice(st.selectbox, "Katalog profili", PROJECT_AIRFOIL_IDS,
                      key="research_profile", default="NACA2412")
    st.caption(f"**{profile}:** {_inventory(repository, store_error, profile)}.")
    with st.expander("Tüm profillerin veri durumu"):
        st.dataframe([{"Profil": name, "Depodaki durum": _inventory(repository, store_error, name)}
                      for name in PROJECT_AIRFOIL_IDS], hide_index=True, use_container_width=True)
        st.caption("Bu liste kayıt envanteridir. Seçilen sürüm ve girdiler Analiz’de denetlenir.")
    template = _choice(st.selectbox, "Kord / burulma şablonu", tuple(research.TEMPLATES),
                       key="research_template", default="axial_800", display=_TEMPLATE_LABELS.__getitem__)
    d = research.defaults(root, template)
    prefix = f"research_{template}_"
    previous = st.session_state.setdefault("_research_last_geometry", {})
    last = previous.get(template, d)
    modes = st.session_state.setdefault("_research_geometry_epochs", {})
    mode = _choice(st.radio, "Geometri giriş biçimi", ("radii", "segments"), key=f"research_geometry_mode_{template}",
                   default="radii", horizontal=True,
                   display={"radii": "Açık çap ve menteşe", "segments": "Parça uzunlukları"}.__getitem__)
    old_mode, epoch = modes.get(template, (mode, 0))
    if mode != old_mode:
        epoch += 1
    modes[template] = (mode, epoch)

    def number(col, label, name, lo, hi, **kwargs):
        return _field(col.number_input, label, prefix + name, getattr(d, name),
                      min_value=lo, max_value=hi, **kwargs)

    left, right = st.columns(2)
    root_mm = number(left, "Kök konumu [mm]", "root_mm", 0., 999.,
                     help="Mil ekseninden fiziksel kanat başlangıcına. Göbek veya ilk aero istasyonu yerine kullanılmaz.")
    hub = number(right, "Göbek yarıçapı [mm]", "hub_mm", .01, 999.,
                 help="Mil ekseninden göbek dış sınırına; bağımsız boyut.")
    left, right = st.columns(2)

    def dimension(col, label, name, default, lo, hi, help_text):
        return _field(col.number_input, label, f"{prefix}{mode}_{epoch}_{name}", default,
                      min_value=lo, max_value=hi, help=help_text)

    if mode == "segments":
        p = dimension(left, "İç parça — proksimal [mm]", "proximal",
                      None if last.root_mm is None else last.hinge_mm-last.root_mm, .01, 999.,
                      "Fiziksel kökten menteşeye ölçülür.")
        q = dimension(right, "Dış parça — distal [mm]", "distal", last.diameter_mm/2-last.hinge_mm, .01, 999.,
                      "Menteşeden açık kanat ucuna ölçülür.")
        hinge = None if root_mm is None or p is None else root_mm+p
        diameter = None if hinge is None or q is None else 2*(hinge+q)
        st.caption(f"Türetilen menteşe konumu: {_fmt(hinge, 1)} mm · açık çap: {_fmt(diameter, 1)} mm.")
    else:
        diameter = dimension(left, "Açık çap [mm]", "diameter", last.diameter_mm, 50., 2000.,
                             "Tam açık pervane uç çapı. Kanat ucu yarıçapı bu değerin yarısıdır.")
        hinge = dimension(right, "Menteşe konumu [mm]", "hinge", last.hinge_mm, .01, 999.,
                          "Mil ekseninden menteşe eksenine.")
    with st.expander("Kök beyanı ve planform"):
        root_kind = _choice(st.selectbox, "Kök beyan türü", ("study_assumption", "declared_geometry"),
                            key=prefix+"root_kind", default=d.root_kind,
                            display={"study_assumption": "Çalışma varsayımı",
                                     "declared_geometry": "Beyan edilen geometri"}.__getitem__)
        meaning = _field(st.text_input, "Kökün fiziksel anlamı", prefix+"root_meaning", d.root_meaning, max_chars=240)
        source = _field(st.text_input, "Kökün kaynağı / beyanı", prefix+"root_source", d.root_source, max_chars=240)
        a, b, c = st.columns(3)
        blades = number(a, "Kanat sayısı", "blade_count", 1, 8)
        chord = number(b, "Kord çarpanı", "chord_scale", .05, 5.)
        twist = number(c, "Burulma çarpanı", "twist_scale", 0., 5.)
    a, b = st.columns(2)
    rpm = number(a, "Devir [RPM]", "rpm", 1., 20000.)
    inflow = number(b, "Eksenel giriş hızı [m/s]", "inflow_m_s", 0., 100.)
    st.button("Analize geç", on_click=_navigate, args=("Analiz",))
    with st.expander("Katlanma ve hedef"):
        a, b = st.columns(2)
        fold = number(a, "Önizleme açısı [°]", "fold_deg", -180., 0.,
                      help="Görüntülenen poz ve istenirse mekanizmanın başlangıç açısı. BEM her zaman 0°.")
        stow = number(b, "Alt katlanma sınırı [°]", "stow_limit_deg", -180., -.01)
        target = number(st, "Merkez çizgisi çap hedefi [mm]", "stowed_target_mm", 1., 2000.)
    with st.expander("Gelişmiş · akışkan ve sayısal ayarlar"):
        a, b = st.columns(2)
        rho = number(a, "Yoğunluk [kg/m³]", "density_kg_m3", .01, 10.)
        mu = number(b, "Dinamik viskozite [Pa·s]", "viscosity_pa_s", 1e-7, .001, format="%.8f")
        temp = number(a, "Sıcaklık [K]", "temperature_k", 100., 800.)
        pressure = number(b, "Basınç [Pa]", "pressure_pa", 1000., 500000.)
        annuli = number(a, "Radyal eleman sayısı", "annulus_count", 4, 80)
    inputs = replace(d, profile=profile, diameter_mm=diameter, hub_mm=hub, hinge_mm=hinge, root_mm=root_mm,
                     root_meaning=meaning, root_source=source, root_kind=root_kind, blade_count=blades,
                     rpm=rpm, inflow_m_s=inflow, fold_deg=fold, stow_limit_deg=stow, stowed_target_mm=target,
                     chord_scale=chord, twist_scale=twist, density_kg_m3=rho, viscosity_pa_s=mu, temperature_k=temp,
                     pressure_pa=pressure, annulus_count=annuli)
    if hinge is None or diameter is None:
        return inputs, None, "Parça uzunluklarından hesaplamak için kökü ve iki uzunluğu girin."
    if not 50. <= diameter <= 2000. or not hub < hinge < diameter/2:
        return inputs, None, "Açık çapı ve radyal sırayı kontrol edin: göbek < menteşe < uç."
    if root_mm is not None and not 0 <= root_mm < hinge:
        return inputs, None, "Fiziksel kök menteşenin içinde kalmalı."
    if fold < stow:
        return inputs, None, "Önizleme açısı, beyan edilen alt katlanma sınırından küçük olamaz."
    cached = st.session_state.get("_research_design_cache")
    try:
        active = cached if cached is not None and cached.inputs == inputs else research.build_research_design(root, inputs)
    except (TypeError, ValueError, OSError) as exc:
        with st.expander("Tasarım teknik ayrıntısı"):
            st.text(str(exc))
        return inputs, None, "Tasarım hazırlanamadı. Geometriyi ve şablonun istasyonlarını kontrol edin."
    previous[template] = inputs
    st.session_state["_research_design_cache"] = active
    return inputs, active, None


@dataclass(frozen=True)
class _Readiness:
    status: str
    request_sha256: str | None = None
    diagnostic: str | None = None


def _inspect_family(active, family, repository, initial):
    cache_key = (active.identity, family.stored_version)
    cached = st.session_state.get("_research_preflight")
    if cached is not None and cached[0] == cache_key:
        return cached[1]
    try:
        prepared = research.prepare_aero(active, family, repository)
    except (ValueError, OSError) as exc:
        status = _Readiness("rejected", diagnostic=str(exc))
    else:
        status = (_Readiness("ready", prepared.request_sha256)
                  if research.declared_grid_covers_initial(family, initial) else _Readiness("outside"))
    st.session_state["_research_preflight"] = (cache_key, status)
    return status


def _ranges(ranges):
    alpha, reynolds, mach = ranges
    return (f"α {_fmt(math.degrees(alpha[0]), 2)}…{_fmt(math.degrees(alpha[1]), 2)}° · "
            f"Re {_fmt(reynolds[0], 0)}…{_fmt(reynolds[1], 0)} · Mach {_fmt(mach[0], 3)}…{_fmt(mach[1], 3)}")


def _rejection_message(diagnostic):
    return {
        "missing_root_declaration": "Kök konumunu, anlamını ve kaynağını Tasarım’da beyan edin.",
        "invalid_root_declaration": "Kök beyanını, anlamını ve kaynağını kontrol edin.",
        "aerodynamic_station_before_physical_root": "İlk aero istasyonu fiziksel kökün içinde kalıyor. Şablon ve kök konumunu kontrol edin.",
        "longer_proximal_required": "Bu şablonda iç parça dış parçadan uzun olmalı.",
        "missing_applicable_family": "Profil ve koordinatla eşleşen kullanılabilir sürümü seçin.",
        "stale_active_state": "Seçili tasarım veya veri değişti. Analiz hazırlığını tekrar kontrol edin.",
    }.get((diagnostic or "").partition(":")[0],
          "Sürümün nokta kapsamı, koordinatları veya kayıt kanıtı kabul edilmedi. Teknik ayrıntıyı operatörle inceleyin.")


def _readiness(active, repository, store_error):
    profile = active.inputs.profile
    selected = st.session_state.setdefault("_research_selected_versions", {})
    candidates = _families(repository, profile, active.coordinate_sha256)
    initial = research.initial_query_ranges(active)
    previous = selected.get(profile)
    choices = (None, *candidates)
    if previous is not None and previous not in candidates:
        choices += (previous,)
    if store_error:
        st.warning("Polar deposu okunamadı. Operatörün veri deposunu kontrol etmesi gerekiyor.")
        with st.expander("Depo teknik ayrıntısı"):
            st.text(store_error)
        return None, _Readiness("store")
    key = f"research_version_{profile}"
    first_check = None
    if profile not in selected and len(candidates) == 1:
        only, = candidates
        first_check = _inspect_family(active, candidates[only], repository, initial)
        if first_check.status == "ready":
            selected[profile] = only
            st.session_state.pop(key, None)
            st.session_state["_research_control_values"][key] = only
    if not candidates and previous is None:
        st.warning(f"Eşleşen veri yok: {profile} için bu katalog geometrisine bağlı polar sürümü bulunamadı.")
        st.caption("Geometriyi inceleyebilir veya uygun bir profil seçebilirsiniz. Yeni veri kaydını operatör ekler.")
        return None, _Readiness("missing")

    def display(key):
        if key is None:
            return "Sürüm seçilmedi"
        if key not in candidates:
            return "Önceki sürüm artık bulunamıyor"
        f = candidates[key]
        label = f"{f.stored_version.version_label} · {f.provider.backend_name} {f.provider.backend_version}"
        return f"{label} · {key[:8]}" if len(candidates) > 1 else label

    def remember_choice():
        selected[profile] = st.session_state[key]

    chosen = _choice(st.selectbox, "Saklanan polar sürümü", choices, key=key,
                     default=selected.get(profile), display=display, on_change=remember_choice)
    if chosen is not None:
        selected[profile] = chosen
    family = candidates.get(chosen)
    if chosen is not None and family is None:
        st.warning("Önceki sürüm kullanılamıyor. Sürüm kendiliğinden değiştirilmedi; varsa bir kayıt seçin.")
        return None, _Readiness("removed")
    if family is None:
        st.info("Sürüm seçilmedi. BEM için yukarıdan bir sürüm seçin.")
        status = first_check or _Readiness("unselected")
    else:
        status = _inspect_family(active, family, repository, initial)
        source_summary = ("800 mm eksenel referansın saklanan sağlayıcı çıktıları"
                          if family.family_id.startswith("research_axial_800_attached_xfoil_v1:")
                          else family.source_identity.split(";")[0][:110])
        st.caption(f"Kaynak: {source_summary} · {len(family.requests)} hücre")
        if family.evidence_class == "inert_fixture":
            st.warning("Test kaydı: katsayılar mühendislik sonucu olarak kullanılamaz.")
    if status.status == "outside":
        st.warning("Girdiler veri kapsamı dışında. Devir, giriş hızı veya şablonu Tasarım’da kontrol edin.")
    elif status.status == "rejected":
        st.warning("Hazırlık reddedildi. " + _rejection_message(status.diagnostic))
    elif status.status == "ready":
        st.success("Hazırlık tamamlandı. BEM’i siz başlatabilirsiniz.")
    return family, status


def _analysis_scope(active, family, readiness):
    st.markdown("**Kapsam ve model**")
    st.caption("Tam açık ana kanat (0°), eklem kaybı yok. Aynı ana kanat ve koşullarda menteşe konumu, ideal BEM yükünü değiştirmez.")
    if family is not None:
        requests = family.requests
        angles = tuple(set.intersection(*(set(r.alpha_rad) for r in requests)))
        if angles:
            re, ma = [r.reynolds for r in requests], [r.mach for r in requests]
            domain = ((min(angles), max(angles)), (min(re), max(re)), (min(ma), max(ma)))
            st.caption("Beyan edilen ortak veri aralığı: " + _ranges(domain))
    st.caption("Koşullu ilk sorgular: " + _ranges(research.initial_query_ranges(active)) +
               ". Kapsanması, yakınsamayı veya tüm denemelerin kapsanacağını göstermez.")
    if family is not None or readiness.diagnostic:
        with st.expander("Hazırlık teknik ayrıntısı"):
            if family is not None:
                st.text(family.source_identity)
                st.text(family.stored_version.content_sha256)
            if readiness.diagnostic:
                st.text(readiness.diagnostic)


def _mechanics(active):
    with st.expander("Mekanizma · isteğe bağlı"):
        on = _field(st.checkbox, "Mekanizma girdilerini aç", "research_mechanics_on", False)
        if not on:
            return None, False, None
        st.caption("Tek rijit dış parça ve beyan edilen devir rampası. İlk stop temasında durur. "
                   "Aerodinamik menteşe yükü, temas tepkisi ve dayanım hesaplanmaz.")
        a, b = st.columns(2)

        def number(col, label, key, value, lo, hi, **kwargs):
            return _field(col.number_input, label, "research_mech_"+key, value,
                          min_value=lo, max_value=hi, **kwargs)

        mass = number(a, "Dış parça kütlesi [g]", "mass", None, .001, 1e5)
        cg = number(b, "Menteşeden kütle merkezi [mm]", "cg", None, 0., 999.)
        inertia = number(a, "Kütle merkezi ataleti [kg·m²]", "inertia", None, 0., 100., format="%.9f")
        source = _field(b.text_input, "Mekanik girdi kaynağı / varsayımı", "research_mech_source", "", max_chars=240)
        start = number(a, "Rampa başlangıcı [RPM]", "rpm", 0., 0., 20000.)
        duration = number(b, "Rampa süresi [s]", "duration", .5, .01, 5.)
        velocity = number(a, "İlk açısal hız [rad/s]", "velocity", 0., -1000., 1000.)
        spring = number(b, "Yay [N·m/rad]", "spring", 0., 0., 100.)
        rest = number(a, "Yay denge açısı [°]", "rest", 0., -180., 0.)
        damping = number(b, "Viskoz sönüm [N·m·s/rad]", "damping", 0., 0., 100.)
        torque = number(a, "Uygulanan menteşe momenti [N·m]", "torque", 0., -100., 100.)
        friction = _choice(b.selectbox, "Kuru sürtünme modeli", ("none", "regularized_coulomb"),
                           key="research_mech_friction", default="none",
                           display={"none": "Kapalı", "regularized_coulomb": "Düzenlenmiş Coulomb"}.__getitem__)
        coulomb = transition = 0.
        if friction != "none":
            coulomb = number(a, "Coulomb momenti [N·m]", "coulomb", .001, .000001, 100., format="%.6f")
            transition = number(b, "Düzenleme hızı [rad/s]", "transition", .1, .001, 100.)
        options = research.MechanismInputs(mass, cg, inertia, source, start, duration, velocity,
                                           spring, rest, damping, torque, friction, coulomb, transition)
        if None in (mass, cg, inertia) or not source.strip():
            st.info("Kütle, kütle merkezi, atalet ve kaynak girilince mekanizma hazırlanabilir. BEM bağımsızdır.")
            return options, False, None
        try:
            research._bind_mechanics(active, options)
        except (ValueError, TypeError, OSError, ArithmeticError) as exc:
            st.warning("Mekanizma hazırlanamadı. Kök beyanını, parça uzunluğunu, kütle dağılımını ve başlangıç pozunu kontrol edin.")
            return options, False, str(exc)
        st.caption(f"İlk açı {_fmt(active.inputs.fold_deg, 1)}° · hedef devir {_fmt(active.inputs.rpm, 0)} RPM.")
        return options, True, None


def _save(row, *, imported=False):
    history = st.session_state.setdefault(_HISTORY, ())
    if any(json.loads(raw)["result_sha256"] == row["result_sha256"] for raw, _ in history):
        return "duplicate"
    if len(history) >= _MAX_HISTORY:
        return "full"
    st.session_state[_HISTORY] = (*history, (research.saved_result_json(row), imported))
    return "saved"


def _navigate(page):
    st.session_state["_research_next_page"] = page


def _show_run(row, token):
    st.session_state[_ACTIVE] = (token, research.saved_result_json(row))
    st.session_state["_research_result_view"] = None
    status = _save(row)
    if status == "full":
        st.session_state["_research_history_full"] = True
    if row["aerodynamics"] and row["aerodynamics"]["failure_stage"] == "preflight_rejection" and status != "full":
        # A race-time rejection remains inspectable even when the selected
        # version cannot remain active after the fresh store read.
        st.session_state["_research_result_view"] = row["result_sha256"]
    _navigate("Sonuçlar")
    st.rerun()


def _bem_run_button(ready):
    # The documented st.container(key=...) CSS scope exists in Streamlit 1.40.
    # Theme palettes can change; limit the contrast override to this enabled action.
    st.html("""
        <style>
        .st-key-research_bem_action button:enabled {
            color: #fff;
            background-color: #0b6170;
            border-color: #0b6170;
        }
        .st-key-research_bem_action button:enabled:is(:hover, :focus-visible) {
            color: #fff;
            background-color: #084d59;
            border-color: #084d59;
        }
        .st-key-research_bem_action button:enabled:focus-visible {
            outline: 3px solid #08778a;
            outline-offset: 3px;
        }
        </style>
    """)
    with st.container(key="research_bem_action"):
        return st.button("BEM’i çalıştır", type="primary", key="research_run", disabled=not ready)


def _analysis(active, repository, store_error):
    st.subheader("Analiz")
    if active is None:
        st.info("Önce Tasarım’da geçerli bir geometri hazırlayın.")
        return
    primary, scope = st.columns((1.1, 1), gap="large")
    with primary:
        st.markdown("**Aerodinamik · ideal tam açık BEM**")
        family, readiness = _readiness(active, repository, store_error)
        ready = family is not None and readiness.status == "ready"
        clicked = _bem_run_button(ready)
    with scope:
        _analysis_scope(active, family, readiness)
    if clicked and ready:
        with st.spinner("Seçili sürüm yeniden denetleniyor ve BEM çalışıyor…"):
            fresh, error = _repository()
            row = research.run_research(active, family, fresh, None, unavailable_reason=error,
                                        expected_preparation_sha256=readiness.request_sha256)
        _show_run(row, ("aero", active.identity, family.stored_version))
    st.divider()
    options, can_run, mechanism_error = _mechanics(active)
    if options is None:
        st.caption("Mekanizma: Kapalı.")
    if mechanism_error:
        with st.expander("Mekanizma teknik ayrıntısı"):
            st.text(mechanism_error)
    st.session_state["_research_mechanics"] = options
    if options is not None and st.button("Mekanizmayı çalıştır", key="research_run_mechanism", disabled=not can_run) and can_run:
        with st.spinner("Mekanizma hesabı çalışıyor…"):
            row = research.run_mechanics_only(active, options)
        _show_run(row, ("mechanics", active.identity, options))


def _invalidate(active, repository):
    current = st.session_state.get(_ACTIVE)
    if current is None:
        return
    kind, identity, selected = current[0]
    if active is None or active.identity != identity:
        st.session_state.pop(_ACTIVE, None)
        return
    if kind == "aero":
        key = st.session_state.get("_research_selected_versions", {}).get(active.inputs.profile)
        family = _families(repository, active.inputs.profile, active.coordinate_sha256).get(key)
        # A rejected race-time request is still saved; stale data never stays active.
        if family is None or family.stored_version != selected:
            st.session_state.pop(_ACTIVE, None)
    elif st.session_state.get("_research_mechanics") != selected:
        st.session_state.pop(_ACTIVE, None)


_RADIAL_COLUMNS = {
    "element": ("Eleman", 0), "radius_m": ("Orta yarıçap [mm]", 1),
    "thrust_n": ("Eleman itkisi [N]", 3), "torque_nm": ("Eleman torku [N·m]", 4),
    "dthrust_n_per_m": ("İtki yoğunluğu [N/m]", 2), "dtorque_nm_per_m": ("Tork yoğunluğu [N·m/m]", 3),
    "alpha_deg": ("α [°]", 2), "reynolds": ("Re", 0), "mach": ("Mach", 4),
}


def _radial(rows):
    plot = _choice(st.radio, "Radyal grafik", ("Eleman yükü", "Birim yarıçap başına", "α / Re / Mach"),
                   key="research_radial_plot", default="Eleman yükü", horizontal=True)
    if plot == "Eleman yükü":
        specs = (("thrust_n", "N"), ("torque_nm", "N·m"))
        st.caption("Her nokta bir radyal elemanın toplam katkısıdır.")
    elif plot == "Birim yarıçap başına":
        specs = (("dthrust_n_per_m", "N/m"), ("dtorque_nm_per_m", "N·m/m"))
        st.caption("Her nokta birim yarıçap başına yüktür; eleman toplamı değildir.")
    else:
        specs = (("alpha_deg", "°"), ("reynolds", "boyutsuz"), ("mach", "boyutsuz"))
        st.caption("Son çözümdeki hücum açısı, Reynolds ve Mach. Tüm ara denemeler teknik ayrıntıda özetlenir.")
    columns = st.columns(len(specs)) if len(specs) == 2 else (st,)*len(specs)
    for col, (field, unit) in zip(columns, specs):
        label, digits = _RADIAL_COLUMNS[field]
        with col.container():
            st.markdown(f"**{label}**")
            _plot(views.radial_figure(rows, ((field, label.split(" [")[0], digits),), unit), "research_plot_"+field)
    with st.expander("Radyal veri tablosu"):
        table = [{label: (1000*r[field] if field == "radius_m" else r[field])
                  for field, (label, _) in _RADIAL_COLUMNS.items()} for r in rows]
        st.dataframe(table, hide_index=True, use_container_width=True, column_config={
            label: st.column_config.NumberColumn(format=f"%.{digits}f")
            for label, digits in _RADIAL_COLUMNS.values()})


def _failure_summary(aero):
    if aero["failure_stage"] == "solver_invocation":
        return "Çözücü tamamlanamadı; kısmi toplam yayımlanmadı."
    return "Hazırlık reddedildi. " + _rejection_message(aero.get("failure_reason"))


def _results(row, *, archived=False, imported=False):
    st.subheader("Sonuçlar")
    if row is None:
        st.info("Etkin sonuç yok. Analiz’den bir hesap başlatın veya kayıtlardan önceki bir sonucu açın.")
        return
    i, aero = row["inputs"], row["aerodynamics"]
    st.markdown(f"**{i['profile']} · {_fmt(i['rpm'], 0)} RPM · {_fmt(i['inflow_m_s'], 2)} m/s**")
    if archived:
        st.caption("Dosyadan açılan kayıt · hesap yeniden çalışmadı." if imported else
                   "Saklanan oturum kaydı · güncel tasarım ayarlarından bağımsız.")
    if st.session_state.pop("_research_history_full", False):
        st.warning("Oturum geçmişi dolu. Bu sonucu kaybetmemek için JSON’u indirin.")
    radial = []
    if aero is None:
        st.caption("Aerodinamik: Bu kayıtta çalıştırılmadı.")
    elif aero["status"] == "success":
        a, b, c = st.columns(3)
        a.metric("İtki [N]", _fmt(aero["thrust_n"], 3))
        b.metric("Şaft torku [N·m]", _fmt(aero["torque_nm"], 3))
        c.metric("Şaft gücü [W]", _fmt(aero["shaft_power_w"], 3))
        st.caption(
            f"İdeal tam açık BEM · modellenen radyal aralık "
            f"{_fmt(1000*aero['inner_radius_m'], 1)}–{_fmt(1000*aero['outer_radius_m'], 1)} mm · "
            f"{aero['annulus_count']} eleman. Eklem kaybı modellenmedi; deneysel referans uyumu değerlendirilmedi."
        )
        if aero["evidence_class"] == "inert_fixture":
            st.warning("Yazılım test kaydı · sayısal kanıt olarak kullanılamaz.")
        else:
            st.caption(f"Çözüm tamamlandı; {aero['polar_query_envelope']['query_count']} deneme sorgusu. "
                       "Dışa taşma ve ekstrapolasyon kapalı.")
        radial = research.radial_rows(row)
    else:
        st.warning(_failure_summary(aero))
    a, b = st.columns(2)
    name = f"pyfoldable_{i['profile']}_{row['result_sha256'][:8]}"
    a.download_button("Sonuç JSON’u indir", research.saved_result_json(row), name+".json", "application/json",
                      help="Bu dosyayı daha sonra Karşılaştırma / kayıtlar ekranında açabilirsiniz.")
    if radial:
        b.download_button("Radyal CSV indir", research.records_csv(radial), name+"_radyal.csv", "text/csv")
        _radial(radial)
    mech = row["mechanism"]
    if mech["status"] == "computed":
        doc = json.loads(mech["report_text"])["result"]
        st.markdown("**Mekanizma · tek rijit dış parça**")
        st.caption("İlk stop temasına veya beyan edilen rampanın sonuna kadar. Aerodinamik geri besleme ve temas tepkisi yok.")
        st.dataframe([{"Zaman [s]": s["time_s"], "Açı [°]": math.degrees(s["angle_rad"]), "Devir [RPM]": s["rpm"],
                       "Merkezkaç momenti [N·m]": s["centrifugal_torque_nm"],
                       "Euler momenti [N·m]": s["euler_torque_nm"],
                       "Kuru sürtünme [N·m]": s["dry_friction_torque_nm"]} for s in doc["samples"]],
                     hide_index=True, use_container_width=True)
    elif mech["status"] == "blocked_or_failed":
        st.warning("Mekanizma tamamlanamadı. Girdi ve tanıyı teknik ayrıntıda inceleyin.")
    elif mech.get("requested", "inputs" in mech):
        st.caption("Mekanizma: Eksik girdiler nedeniyle çalışmadı.")
    else:
        st.caption("Mekanizma: Kapalı.")
    with st.expander("Teknik ayrıntılar · tam kimlikler, sorgu kapsamı ve kanıtlar"):
        if aero is not None and aero["report_text"]:
            st.json(json.loads(aero["report_text"]), expanded=False)
        if mech.get("report_text"):
            st.json(json.loads(mech["report_text"]), expanded=False)
        st.json(row, expanded=False)


def _retained():
    return {row["result_sha256"]: (row, imported) for row, imported in
            ((json.loads(raw), imported) for raw, imported in st.session_state.get(_HISTORY, ()))}


def _history():
    st.subheader("Karşılaştırma / kayıtlar")
    st.caption("Oturum kapanınca bu liste saklanmaz. Sonuç JSON’unu indirin; daha sonra buradan açabilirsiniz.")
    restore_error = None
    with st.expander("Önceki sonuç JSON’unu aç"):
        st.caption("Uygulamanın dışa aktardığı sonuç dosyası. İçerik tutarlılığı denetlenir, hesap başlatılmaz.")
        uploaded = st.file_uploader("Sonuç JSON dosyası", type=("json",), key="research_restore")
        if st.button("Sonucu oturuma ekle", disabled=uploaded is None) and uploaded is not None:
            try:
                status = _save(research.read_saved_result(uploaded.getvalue()), imported=True)
            except (ValueError, OSError) as exc:
                message = getattr(exc, "user_message",
                                  "Dosya eksik veya saklanan tasarım ve çalışma girdileriyle tutarsız.")
                st.error(f"Sonuç dosyası açılamadı. {message} Kayıt geçmişe eklenmedi.")
                restore_error = str(exc)
            else:
                if status == "full":
                    st.warning("Oturum en fazla 12 kayıt alır.")
                else:
                    st.success("Dosya kayıtlara eklendi." if status == "saved" else "Bu dosya zaten oturumda.")
    if restore_error:
        with st.expander("İçe aktarma teknik ayrıntısı"):
            st.text(restore_error)
    records = _retained()
    if not records:
        st.info("Henüz kayıt yok. Analiz çalıştırabilir veya önceki bir sonucu açabilirsiniz.")
        return

    numbers = {key: index for index, key in enumerate(records, start=1)}

    def display(key):
        if key is None:
            return "Kayıt seçin"
        i = records[key][0]["inputs"]
        return f"K{numbers[key]:02d} · {i['profile']} · {_fmt(i['rpm'], 0)} RPM · {_fmt(i['inflow_m_s'], 1)} m/s"

    successes = tuple(k for k, (r, _) in records.items() if r["aerodynamics"] and r["aerodynamics"]["status"] == "success")
    failures = tuple(k for k, (r, _) in records.items() if r["aerodynamics"] and r["aerodynamics"]["status"] == "failure")
    mechanisms = tuple(k for k, (r, _) in records.items() if r["aerodynamics"] is None)
    st.markdown("**Tamamlanan BEM kayıtları**")
    if len(successes) < 2:
        st.info(f"{len(successes)} tamamlanmış BEM kaydı var. Karşılaştırma için iki farklı profil kaydı gerekir.")
    else:
        a, b = st.columns(2)
        first = _choice(a.selectbox, "Birinci BEM kaydı", (None, *successes), key="research_compare_first",
                        default=None, display=display)
        second = _choice(b.selectbox, "İkinci BEM kaydı", (None, *(k for k in successes if k != first)),
                         key="research_compare_second", default=None, display=display)
        if first is not None and second is not None:
            chosen = (first, second)
            rows = [records[k][0] for k in chosen]
            result = research.compare_results(rows)
            if result["matched_numerical_comparison"]:
                st.success("Eşleştirilmiş sayısal karşılaştırma · farklı koordinatlar, aynı planform, koşul ve yöntem.")
            else:
                st.info("Eşleştirilmiş sayısal çift oluşmadı. Profil koordinatları farklı; planform, koşul ve sayısal yöntem eş olmalı.")
                with st.expander("Karşılaştırma teknik ayrıntısı"):
                    st.json(result, expanded=False)
            summary = [{"Kayıt": display(k), "İtki [N]": _fmt(r["aerodynamics"]["thrust_n"], 3),
                        "Şaft torku [N·m]": _fmt(r["aerodynamics"]["torque_nm"], 3),
                        "Şaft gücü [W]": _fmt(r["aerodynamics"]["shaft_power_w"], 3)} for k, r in zip(chosen, rows)]
            st.dataframe(summary, hide_index=True, use_container_width=True)
            a, b = st.columns(2)
            a.download_button("Karşılaştırma JSON’u", json.dumps({
                "schema_version": 1, "artifact_class": "pyfoldable_research_comparison",
                "assessment": result, "results": rows,
            }, ensure_ascii=False, allow_nan=False), "research_comparison.json", "application/json")
            csv_rows = [{
                "result_sha256": r["result_sha256"], "profile": r["inputs"]["profile"],
                "rpm": r["inputs"]["rpm"], "inflow_m_s": r["inputs"]["inflow_m_s"],
                "matched_numerical_comparison": result["matched_numerical_comparison"],
                **{field: r["aerodynamics"][field] for field in
                   ("airfoil_coordinate_sha256", "report_sha256", "thrust_n", "torque_nm", "shaft_power_w",
                    "inner_radius_m", "outer_radius_m")},
            } for r in rows]
            b.download_button("Karşılaştırma CSV’si", research.records_csv(csv_rows), "research_comparison.csv", "text/csv")
    st.caption("Eşit devir ve giriş hızı, eşit şaft gücü demek değildir. Eşit güç için başka çalışma noktaları gerekir. "
               "Bu karşılaştırma tasarım seçmez veya fiziksel yeterlilik göstermez.")
    if failures:
        with st.expander(f"Tamamlanmayan BEM denemeleri ({len(failures)})"):
            for key in failures:
                st.markdown("**" + display(key) + "**")
                st.caption(_failure_summary(records[key][0]["aerodynamics"]))
    if mechanisms:
        st.caption(f"{len(mechanisms)} bağımsız mekanizma kaydı karşılaştırma dışında tutuluyor.")
    chosen = _choice(st.selectbox, "İncelenecek oturum kaydı", (None, *records), key="research_archive_choice",
                     default=None, display=display)
    if st.button("Kaydı Sonuçlar’da aç", disabled=chosen is None) and chosen is not None:
        st.session_state["_research_result_view"] = chosen
        _navigate("Sonuçlar")
        st.rerun()


def render_research(root: Path):
    st.title("PyFoldable Araştırma")
    st.caption("Katalogdan tasarlayın, sayısal analizi başlatın, sonuçları karşılaştırıp dışa aktarın.")
    next_page = st.session_state.pop("_research_next_page", None)
    if next_page is not None:
        st.session_state[_PAGE] = next_page
    page = st.radio("Çalışma alanı", _PAGES, horizontal=True, key=_PAGE)
    context = st.empty()
    repository, store_error = _repository()
    if page == "Tasarım" or "_research_design_state" not in st.session_state:
        if page == "Tasarım":
            form, preview = st.columns((1, 1.18), gap="large")
            with form:
                inputs, active, problem = _edit_design(root, repository, store_error)
            with preview:
                if active is not None:
                    _geometry(active)
                else:
                    st.warning(problem)
        else:
            inputs = research.defaults(root)
            active, problem = research.build_research_design(root, inputs), None
        st.session_state["_research_design_state"] = (inputs, active, problem)
    inputs, active, problem = st.session_state["_research_design_state"]
    context.caption(f"**Güncel tasarım:** {inputs.profile} · {_fmt(inputs.diameter_mm, 1)} mm · "
               f"{_fmt(inputs.rpm, 0)} RPM · {_fmt(inputs.inflow_m_s, 2)} m/s · "
               + ("geometri hazır" if active is not None else "girdileri kontrol edin"))
    _invalidate(active, repository)
    if page == "Analiz":
        _analysis(active, repository, store_error)
        _invalidate(active, repository)  # A version or mechanical input could have changed in this render.
    elif page == "Sonuçlar":
        archive_key = st.session_state.get("_research_result_view")
        record = _retained().get(archive_key) if archive_key is not None else None
        current = st.session_state.get(_ACTIVE)
        if record is not None:
            _results(record[0], archived=True, imported=record[1])
        else:
            _results(None if current is None else json.loads(current[1]))
    elif page == "Karşılaştırma / kayıtlar":
        _history()
