"""Streamlit entrypoint for the evidence-first PyFoldable workspace."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pyfoldable.application.dashboard import EvidenceState, load_dashboard_snapshot
from pyfoldable.application.analysis_run import (
    PR06D_ANALYSIS_ID,
    AnalysisRunArtifact,
    AnalysisRunError,
    get_analysis_recipe,
    run_analysis,
)
from pyfoldable.application.design_draft import (
    DesignDraftArtifact,
    DesignDraftInputs,
    DraftUnitSelection,
    build_design_draft,
)
from pyfoldable.application.design_analysis import DesignAnalysisArtifact, DesignAnalysisError, prepare_design_analysis
from pyfoldable.application.polar_upload import MAX_POLAR_UPLOAD_BYTES, PolarRunRequest, prepare_polar_run, run_polar_run
from pyfoldable.application.active_design_search import prepare_active_search, run_active_search
from pyfoldable.application.design_search import SearchError
from pyfoldable.application.evidence_import import (
    EvidenceImportError,
    MAX_EVIDENCE_UPLOAD_BYTES,
    inspect_evidence_upload,
)
from pyfoldable.application.folding_mechanism import (
    MechanismGeometryAudit,
    MechanismGeometryInputs,
    build_mechanism_geometry_audit,
    build_mechanism_physics_fixture,
)
from pyfoldable.application.opening_sensitivity import load_opening_sensitivity
from pyfoldable.application.mechanism_transient import (
    MechanismTransientArtifact,
    MechanismTransientError,
    MechanismTransientRequest,
    prepare_mechanism_transient,
    run_mechanism_transient,
)
from pyfoldable.dynamics.mechanism_transient import (
    DriveHistory,
    MechanismParameters,
    SolverControls,
    TransientRequest,
)
from pyfoldable.application.ui_render import build_markdown_table
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS, load_project_airfoil
from pyfoldable.visualization.propeller_25d import (
    PreviewBladeStation,
    PropellerPreviewSpec,
    build_propeller_preview_mesh,
)


PAGES = (
    "Genel Bakış",
    "Tasarım Geometrisi",
    "Çalışma Koşulları",
    "Analiz Çalıştırma",
    "Performans Sonuçları",
    "Mekanizma Geçişi",
    "Katlanma Davranışı",
    "Motor–Pervane",
    "CFD / FEA / Deney",
    "Doğrulama ve Kanıtlar",
    "Raporlar",
)

STATE_ICONS = {
    EvidenceState.QUALIFIED: "✅",
    EvidenceState.SCREENING_ONLY: "🔎",
    EvidenceState.PENDING: "⏳",
    EvidenceState.FAILED: "✖",
    EvidenceState.BLOCKED: "⛔",
}

ANALYSIS_RESULT_KEY = "ui04_analysis_result"
ANALYSIS_REQUEST_KEY = "ui04_analysis_request"
POLAR_RESULT_KEY = "py03_polar_result"
POLAR_REQUEST_KEY = "py03_polar_request"
EVIDENCE_KIND_BY_LABEL = {
    "Yayımlanmış CFD referans fixture'ı": "cfd_reference",
    "PR-09 FEA sözleşme raporu": "fea_contract_report",
    "PR-10 deney sözleşme raporu": "experiment_contract_report",
}
TRANSIENT_RESULT_KEY = "py05_transient_result"
TRANSIENT_REQUEST_KEY = "py05_transient_request"


def _render_markdown_table(rows: list[dict[str, object]]) -> None:
    """Render small read-only tables without Streamlit's Arrow bridge."""
    table = build_markdown_table(rows)
    if not table:
        st.caption("Gösterilecek kayıt yok.")
        return
    st.markdown(table)


def _circle_xy(radius_m: float, *, point_count: int = 97) -> tuple[list[float], list[float]]:
    angles = [2.0 * math.pi * index / (point_count - 1) for index in range(point_count)]
    return (
        [radius_m * math.cos(angle) for angle in angles],
        [radius_m * math.sin(angle) for angle in angles],
    )


def _clear_search_result() -> None:
    st.session_state.pop("py04_search_result", None)
    st.session_state.pop("py04_search_request", None)


def _clear_polar_result(*, clear_search: bool = True) -> None:
    st.session_state.pop(POLAR_RESULT_KEY, None)
    st.session_state.pop(POLAR_REQUEST_KEY, None)
    if clear_search:
        _clear_search_result()


def _render_active_search(base: PolarRunRequest) -> None:
    st.subheader("Aktif tasarım · Sınırlı chord/twist taraması")
    st.caption(
        "Her aday güncel taslağın chord/twist değerlerini çarpar; çap, RPM ve profil sabittir. "
        "İlk yöntem sonlu ızgara taramasıdır; sürekli/global optimum veya fiziksel tasarım önermez."
    )
    options = (.8, .9, 1., 1.1, 1.2)
    chord = st.multiselect("Tarama chord çarpanları", options, default=(.9, 1., 1.1))
    twist = st.multiselect("Tarama twist çarpanları", options, default=(.9, 1., 1.1))
    minimum = st.number_input("Tarama minimum itki [N]", min_value=0., max_value=10000., value=0., step=.1)
    st.caption(
        "İtki alt sınırı kullanıcıya ait tarama ölçütüdür, 85% proje hedefinin yerine geçmez. "
        "En fazla 25 aday, aday başına 40 ve toplam 400 annulus; hedef şaft gücünü azaltmaktır."
    )
    try:
        request = prepare_active_search(base, chord_scales=tuple(chord), twist_scales=tuple(twist), minimum_thrust_n=minimum)
    except (SearchError, DesignAnalysisError, OSError) as exc:
        _clear_search_result()
        st.warning("Tasarım taraması hazırlanamadı.")
        st.text(str(exc))
        return
    if st.session_state.get("py04_search_request") != request.request_sha256:
        _clear_search_result()
    if st.button("Aktif taslak ızgarasını tara"):
        _clear_search_result()
        with st.spinner("Sınırlı tasarım ızgarası taranıyor…"):
            try:
                result = run_active_search(request)
            except (SearchError, DesignAnalysisError, OSError) as exc:
                st.error("Tasarım taraması durduruldu.")
                st.text(str(exc))
            else:
                st.session_state["py04_search_result"] = result
                st.session_state["py04_search_request"] = request.request_sha256
    result = st.session_state.get("py04_search_result")
    if not isinstance(result, DesignAnalysisArtifact):
        return
    document = json.loads(result.report_json)
    st.warning(
        "Fiziksel/yapısal kısıtlar doğrulanmadığı için uygun aday önerilmiyor. "
        "Aşağıdaki sayılar yalnız aday karşılaştırmasıdır; physical_qualification=false."
    )
    st.caption(f"Tarama rapor SHA-256: {result.report_sha256}")
    _render_markdown_table([
        {"Chord ×": row["parameters"]["chord_scale"], "Twist ×": row["parameters"]["twist_scale"],
         "Durum": row["status"], "İtki [N]": row["details"].get("rotor", {}).get("thrust_n"),
         "Şaft gücü [W]": row["objective"]} for row in document["candidates"]
    ])
    with st.expander("Tarama kısıtları ve hata kaydı"):
        st.text("\n".join(f"{row['index']}: {row['constraints']} {row['error'] or ''}" for row in document["candidates"]))
    st.download_button("Tasarım taramasını JSON indir", data=result.report_json,
        file_name=result.filename, mime="application/json")


def _render_active_polar_run(draft: DesignDraftArtifact) -> None:
    st.subheader("Aktif tasarım · Polar yükleme ve BEM")
    st.warning(
        "Bu hesap yalnız tam açık taslağın tarama analizidir. Yüklenen polarlar "
        "doğrulanmış deney/ANSYS kanıtı sayılmaz; physical_qualification=false. "
        "140 mm katlanma uyumsuzluğu ve yapısal doğrulama kapıları değişmez."
    )
    uploaded = st.file_uploader(
        "Polar JSON dosyası", type=("json",), key="py03_polar_upload",
        help="active_design_polar_bundle v1; en fazla 2 MiB, 64 tablo, tablo başına 721 nokta. "
             "Her tabloda seçili profilin koordinat SHA-256 kimliği gereklidir.",
    )
    annuli = st.number_input("Aktif BEM annulus sayısı", min_value=4, max_value=80, value=40, step=4)
    st.caption(
        "Polar şeması: docs/py03_active_design_polar_ui.md. alpha_rad radyan; "
        "Reynolds, Mach ve Cl/Cd/Cm boyutsuzdur. Dosya/polar sınırı dışında "
        "clamp, extrapolasyon veya otomatik provider/proxy yoktur."
    )
    if uploaded is None:
        _clear_polar_result()
        st.info("Aktif taslağı çalıştırmak için koordinat kimliği eşleşen polar JSON yükleyin.")
        return
    if uploaded.size > MAX_POLAR_UPLOAD_BYTES:
        _clear_polar_result()
        st.error("Polar reddedildi: dosya 2 MiB sınırını aşıyor.")
        return
    try:
        request = prepare_polar_run(draft, uploaded.getvalue(), annulus_count=annuli)
    except (DesignAnalysisError, OSError) as exc:
        _clear_polar_result()
        st.error(f"Polar/aktif taslak reddedildi: {exc}")
        return
    if st.session_state.get(POLAR_REQUEST_KEY) != request.request_sha256:
        _clear_polar_result(clear_search=False)
    summary = json.loads(request.summary_json)
    st.caption(
        f"Polar sözleşmesi doğrulandı · {summary['airfoil_id']} · "
        f"{summary['table_count']} tablo / {summary['point_count']} nokta · "
        f"Yüklenen dosya SHA-256: {summary['source_sha256']}"
    )
    _render_markdown_table([
        {"Re": row["reynolds"], "Mach": row["mach"],
         "α alt [deg]": math.degrees(row["alpha_min_rad"]),
         "α üst [deg]": math.degrees(row["alpha_max_rad"])}
        for row in summary["tables"]
    ])
    with st.expander("Beyan edilen polar kaynakları"):
        st.text("\n".join(dict.fromkeys(row["source"] for row in summary["tables"])))
    st.caption(
        "Tablo aralıkları tam BEM sorgu kapsamını kanıtlamaz. Çözücü kapsam dışına "
        "çıkarsa toplam veya kısmi performans sonucu yayımlanmaz."
    )
    if st.button("Aktif taslağı BEM ile çalıştır", type="primary"):
        _clear_polar_result(clear_search=False)
        with st.spinner("Aktif taslak, yüklenen polarlarla çözülüyor…"):
            try:
                result = run_polar_run(request)
            except (DesignAnalysisError, OSError) as exc:
                st.error(f"Aktif BEM kapalı biçimde durduruldu: {exc}")
            else:
                st.session_state[POLAR_RESULT_KEY] = result
                st.session_state[POLAR_REQUEST_KEY] = request.request_sha256
    _render_active_search(request)
    result = st.session_state.get(POLAR_RESULT_KEY)
    if not isinstance(result, DesignAnalysisArtifact):
        return
    doc = json.loads(result.report_json)
    rotor = doc["rotor"]
    st.subheader("Aktif taslağın tarama sonucu")
    thrust, torque, power = st.columns(3)
    thrust.metric("Aktif itki [N]", f"{rotor['thrust_n']:.6g}")
    torque.metric("Aktif şaft torku [N·m]", f"{rotor['torque_nm']:.6g}")
    power.metric("Aktif şaft gücü [W]", f"{rotor['shaft_power_w']:.6g}")
    st.caption(
        f"{doc['artifact_class']} · {doc['qualification']} · physical_qualification=false · "
        f"station_span: {rotor['inner_radius_m']:.5g}–{rotor['outer_radius_m']:.5g} m"
    )
    st.caption(f"Aktif BEM rapor SHA-256: {result.report_sha256}")
    st.download_button("Aktif BEM sonucunu JSON indir", data=result.report_json,
        file_name=result.filename, mime="application/json")


def _render_design_preparation(draft: DesignDraftArtifact) -> None:
    st.subheader("Aktif tasarım · Python analiz hazırlığı")
    st.caption(
        "İndirilen taslakla aynı geometri ve ilk çalışma koşulu kullanılır. "
        "Bu hazırlık BEM çalıştırmaz; indüksiyon/swirl içermez ve polarların "
        "tüm solver sorgularını kapsadığını doğrulamaz."
    )
    try:
        artifact = prepare_design_analysis(draft)
    except DesignAnalysisError as exc:
        _clear_polar_result()
        st.warning(f"Analiz hazırlığı yapılamadı: {exc}")
        return
    document = json.loads(artifact.report_json)
    preparation = document["preparation"]
    st.caption(
        f"Aktif açık çap · {preparation['diameter_m'] * 1000:.1f} mm · "
        "active_design_analysis_preparation · physical_qualification=false"
    )
    if abs(preparation["preview_fold_angle_rad"]) > 1e-12:
        st.warning(
            "Aşağıdaki değerler açık kanat içindir; seçili katlanmış pozun "
            "aerodinamik sonucu değildir. Aktif tasarım BEM servisi bu dilimde "
            "yalnız tam açık pozu kabul eder."
        )
    _render_markdown_table([
        {
            "r/R": row["r_over_R"],
            "Aktif chord [mm]": row["chord_m"] * 1000,
            "Profil": row["airfoil_id"],
            "Nominal Re": row["reynolds"],
            "Nominal Mach": row["mach"],
            "Nominal α [deg]": math.degrees(row["alpha_rad"]),
        }
        for row in preparation["stations"]
    ])
    st.caption(f"Hazırlık istek SHA-256 · {artifact.request_sha256}")
    st.download_button(
        "Analiz hazırlığını JSON indir", data=artifact.report_json,
        file_name=artifact.filename, mime="application/json",
    )
    st.info(
        "Python BEM servisi açıkça sağlanan polar ailelerini kullanır; eksik veri "
        "yerine proxy üretmez. Arayüzdeki 254 mm referans benchmark'ı ayrıdır. "
        "Aşağıdaki polar yükleme ve çalıştırma alanı bu aktif taslağı kullanır."
    )
    _render_active_polar_run(draft)


def _render_geometry_compatibility(audit: MechanismGeometryAudit) -> None:
    if not audit.minimum_requirement_reachable:
        st.error(
            f"{audit.stowed_requirement_m * 1000:.0f} mm katlanmış zarf hedefi bu "
            f"topolojiyle göbeğe temas etmeden erişilemiyor. Çarpışmasız katlanma yolu "
            f"en az {audit.collision_free_minimum_envelope_diameter_m * 1000:.1f} mm "
            "merkez-hat zarfı gerektiriyor."
        )
    elif not audit.current_envelope_requirement_met:
        st.warning(
            f"Hedef katlanma yolu üzerinde erişilebilir, ancak seçili "
            f"{audit.fold_angle_deg:.0f}° açıda merkez-hat zarfı hedefi "
            f"{-audit.current_requirement_margin_m * 1000:.1f} mm aşıyor."
        )
    if audit.full_stow_path_hub_clearance_m < 0.0:
        st.error(
            "Tam 0°→−180° katlanma yolu göbek zarfıyla kesişiyor; en kötü "
            f"merkez-hat girişimi {-audit.full_stow_path_hub_clearance_m * 1000:.1f} mm."
        )
    if not audit.station_span_complete:
        if audit.root_surface_gap_m >= 0.0:
            root_finding = (
                f"göbek–ilk istasyon boşluğu {audit.root_surface_gap_m * 1000:.1f} mm"
            )
        else:
            root_finding = (
                "ilk istasyon göbek yarıçapının "
                f"{-audit.root_surface_gap_m * 1000:.1f} mm içine giriyor"
            )
        hinge_finding = (
            " Menteşe tanımlı station aralığının dışında."
            if not audit.hinge_station_covered
            else ""
        )
        st.warning(
            "Girilen nominal ölçüler ile çizilen kanat yüzeyi tam örtüşmüyor: "
            f"{root_finding}, "
            f"son istasyon–nominal uç boşluğu {audit.tip_surface_gap_m * 1000:.1f} mm. "
            f"Mesh yalnız tanımlı station aralığını temsil eder.{hinge_finding}"
        )
    if audit.hub_centerline_clearance_m < 0.0:
        st.error("Seçili açıda katlanan uç segment merkez hattı göbek zarfıyla kesişiyor.")
    if audit.screening_checks_passed:
        st.success(
            "Tanımlı merkez-hat ve station tarama kontrolleri geçti; bu sonuç CAD "
            "temas/kalınlık uyumluluğu veya fiziksel yeterlilik değildir."
        )


def _render_overview() -> None:
    snapshot = load_dashboard_snapshot(REPO_ROOT)
    geometry_audit = build_mechanism_geometry_audit(
        MechanismGeometryInputs(
            diameter_m=snapshot.open_diameter_m,
            hub_radius_m=snapshot.hub_radius_m,
            hinge_radius_m=snapshot.hinge_radius_m,
            fold_angle_deg=-180.0,
            stowed_requirement_m=snapshot.stowed_envelope_m,
        ),
        tuple(station.r_over_R for station in snapshot.blade_stations),
    )

    st.title("PyFoldable Engineering Workspace")
    st.caption(f"Aktif tasarım · {snapshot.design_id}")
    st.markdown(f"`Manifest SHA-256 · {snapshot.manifest_sha256}`")
    st.warning(snapshot.qualification_warning, icon="⚠️")

    diameter, envelope, checkpoint = st.columns(3)
    diameter.metric("Açık çap", f"{snapshot.open_diameter_m * 1000:.0f} mm")
    envelope.metric(
        "Katlanmış zarf hedefi",
        f"{snapshot.stowed_envelope_m * 1000:.0f} mm",
        delta=(
            "çarpışmasız minimum "
            f"{geometry_audit.collision_free_minimum_envelope_diameter_m * 1000:.0f} mm"
        ),
        delta_color="inverse",
    )
    checkpoint.metric("Kontrol noktası", f"{snapshot.checkpoint_rpm:.0f} rpm")
    if not geometry_audit.minimum_requirement_reachable:
        st.error(
            "Katlanmış zarf değeri bir gereksinimdir, elde edilmiş sonuç değildir: "
            "mevcut düzlemsel uç-mafsal geometrisinin çarpışmasız minimum merkez-hat "
            f"zarfı {geometry_audit.collision_free_minimum_envelope_diameter_m * 1000:.0f} mm'dir."
        )

    st.subheader("Doğrulama kapıları")
    for left_index in range(0, len(snapshot.gates), 2):
        columns = st.columns(2)
        for column, gate in zip(columns, snapshot.gates[left_index : left_index + 2]):
            with column.container(border=True):
                st.markdown(f"### {gate.id} · {gate.title}")
                st.markdown(f"**{STATE_ICONS[gate.state]} {gate.state.label_tr}**")
                st.write(gate.summary)
                st.caption(f"Kanıt: {gate.evidence_path.relative_to(REPO_ROOT)}")
                st.caption(f"SHA-256: {gate.evidence_sha256}")

    st.subheader("Kanıt envanteri")
    _render_markdown_table(
        [
            {
                "Kapı": gate.id,
                "Durum": gate.state.label_tr,
                "Karar": gate.decision,
                "Kanıt dosyası": str(gate.evidence_path.relative_to(REPO_ROOT)),
            }
            for gate in snapshot.gates
        ]
    )


def _render_planned_page(page: str) -> None:
    st.title(page)
    st.info(
        "Bu ekran henüz analiz çalıştırmaz. Mevcut kanıt sözleşmesine bağlanmadan "
        "örnek değer veya mühendislik sonucu üretmez.",
        icon="ℹ️",
    )
    st.caption("UI-00/01 güvenli kabuk · Sonraki artımlarda test-first etkinleştirilecek.")


def _render_design_geometry() -> None:
    snapshot = load_dashboard_snapshot(REPO_ROOT)
    st.title("Tasarım Geometrisi")
    st.warning(
        "Etkileşimli model bir geometri önizlemesidir; CAD katısı, CFD/FEA ağı veya "
        "doğrulanmış performans sonucu değildir. Değişiklikler kanonik config dosyasına "
        "kaydedilmez.",
        icon="⚠️",
    )
    st.markdown(f"### {snapshot.design_id}")
    st.caption(snapshot.design_description)
    diameter, blades, hinge = st.columns(3)
    diameter.metric("Açık çap", f"{snapshot.open_diameter_m * 1000:.0f} mm")
    blades.metric("Kanat sayısı", str(snapshot.blade_count))
    hinge.metric("Menteşe yarıçapı", f"{snapshot.hinge_radius_m * 1000:.0f} mm")

    st.subheader("Etkileşimli 2.5D önizleme")
    dimension_columns = st.columns(4)
    diameter_mm = dimension_columns[0].number_input(
        "Açık çap [mm]",
        min_value=20.0,
        max_value=1000.0,
        value=float(snapshot.open_diameter_m * 1000.0),
        step=5.0,
    )
    hub_radius_mm = dimension_columns[1].number_input(
        "Göbek yarıçapı [mm]",
        min_value=1.0,
        max_value=250.0,
        value=float(snapshot.hub_radius_m * 1000.0),
        step=1.0,
    )
    hinge_radius_mm = dimension_columns[2].number_input(
        "Menteşe yarıçapı [mm]",
        min_value=2.0,
        max_value=500.0,
        value=float(snapshot.hinge_radius_m * 1000.0),
        step=2.0,
    )
    blade_count = dimension_columns[3].number_input(
        "Kanat sayısı",
        min_value=1,
        max_value=8,
        value=int(snapshot.blade_count),
        step=1,
    )

    model_columns = st.columns(4)
    airfoil_id = model_columns[0].selectbox(
        "Kesit modeli",
        PROJECT_AIRFOIL_IDS,
        index=PROJECT_AIRFOIL_IDS.index("NACA2412"),
    )
    chord_scale = model_columns[1].slider(
        "Chord ölçeği",
        min_value=0.50,
        max_value=1.50,
        value=1.00,
        step=0.05,
    )
    twist_scale = model_columns[2].slider(
        "Twist ölçeği",
        min_value=0.00,
        max_value=1.50,
        value=1.00,
        step=0.05,
    )
    fold_angle_deg = model_columns[3].slider(
        "Katlanma açısı [deg]",
        min_value=-180,
        max_value=0,
        value=0,
        step=5,
    )

    st.subheader("Taslak çalışma koşulu")
    st.caption(
        "Bu alan yalnız indirilebilir taslağın ilk çalışma koşulunu düzenler; analiz "
        "çalıştırmaz ve kanonik config'e yazmaz."
    )
    condition = snapshot.operating_conditions[0]
    condition_columns = st.columns(3)
    rpm = condition_columns[0].number_input(
        "RPM",
        min_value=0.0,
        max_value=100000.0,
        value=float(condition.rpm),
        step=100.0,
    )
    forward_speed_m_s = condition_columns[1].number_input(
        "V∞ [m/s]",
        min_value=-200.0,
        max_value=200.0,
        value=float(condition.forward_speed_m_s),
        step=1.0,
    )
    air_density_kg_m3 = condition_columns[2].number_input(
        "ρ [kg/m³]",
        min_value=0.01,
        max_value=5.0,
        value=float(condition.air_density_kg_m3),
        step=0.01,
        format="%.4f",
    )
    atmosphere_columns = st.columns(3)
    dynamic_viscosity_pa_s = atmosphere_columns[0].number_input(
        "μ [Pa·s]",
        min_value=1.0e-7,
        max_value=1.0e-3,
        value=float(condition.dynamic_viscosity_pa_s),
        step=1.0e-7,
        format="%.7g",
    )
    temperature_k = atmosphere_columns[1].number_input(
        "T [K]",
        min_value=1.0,
        max_value=1000.0,
        value=float(condition.temperature_k),
        step=1.0,
    )
    pressure_pa = atmosphere_columns[2].number_input(
        "p [Pa]",
        min_value=1.0,
        max_value=2_000_000.0,
        value=float(condition.pressure_pa),
        step=100.0,
    )

    with st.expander("Taslak çıktı birimleri"):
        unit_columns = st.columns(3)
        length_unit = unit_columns[0].selectbox("Uzunluk", ("mm", "m", "cm", "in"))
        angle_unit = unit_columns[1].selectbox("Açı", ("deg", "rad"))
        angular_speed_unit = unit_columns[2].selectbox(
            "Açısal hız",
            ("rpm", "rad/s"),
        )
        second_unit_columns = st.columns(3)
        speed_unit = second_unit_columns[0].selectbox("İleri hız", ("m/s", "km/h"))
        temperature_unit = second_unit_columns[1].selectbox("Sıcaklık", ("K", "degC"))
        pressure_unit = second_unit_columns[2].selectbox(
            "Basınç",
            ("Pa", "kPa", "MPa"),
        )

    try:
        selected_airfoil = load_project_airfoil(airfoil_id)
        preview_spec = PropellerPreviewSpec(
            diameter_m=diameter_mm / 1000.0,
            hub_radius_m=hub_radius_mm / 1000.0,
            blade_count=int(blade_count),
            hinge_radius_m=hinge_radius_mm / 1000.0,
            fold_angle_deg=float(fold_angle_deg),
            airfoil_id=airfoil_id,
            airfoil_definition=selected_airfoil,
            chord_scale=float(chord_scale),
            twist_scale=float(twist_scale),
        )
        diameter_scale = preview_spec.diameter_m / snapshot.open_diameter_m
        preview_mesh = build_propeller_preview_mesh(
            preview_spec,
            tuple(
                PreviewBladeStation(
                    r_over_R=station.r_over_R,
                    chord_m=station.chord_m * diameter_scale,
                    twist_deg=station.twist_deg,
                )
                for station in snapshot.blade_stations
            ),
        )
        geometry_audit = build_mechanism_geometry_audit(
            MechanismGeometryInputs(
                diameter_m=preview_spec.diameter_m,
                hub_radius_m=preview_spec.hub_radius_m,
                hinge_radius_m=preview_spec.hinge_radius_m,
                fold_angle_deg=preview_spec.fold_angle_deg,
                stowed_requirement_m=snapshot.stowed_envelope_m,
            ),
            tuple(station.r_over_R for station in snapshot.blade_stations),
        )
        draft = build_design_draft(
            snapshot.design_path,
            DesignDraftInputs(
                diameter=f"{diameter_mm} mm",
                hub_radius=f"{hub_radius_mm} mm",
                hinge_radius=f"{hinge_radius_mm} mm",
                blade_count=int(blade_count),
                airfoil_id=airfoil_id,
                chord_scale=float(chord_scale),
                twist_scale=float(twist_scale),
                preview_fold_angle=f"{fold_angle_deg} deg",
                angular_speed=f"{rpm} rpm",
                forward_speed=f"{forward_speed_m_s} m/s",
                air_density=f"{air_density_kg_m3} kg/m^3",
                dynamic_viscosity=f"{dynamic_viscosity_pa_s} Pa*s",
                temperature=f"{temperature_k} K",
                pressure=f"{pressure_pa} Pa",
            ),
            airfoil_definition=selected_airfoil,
            units=DraftUnitSelection(
                length=length_unit,
                angle=angle_unit,
                angular_speed=angular_speed_unit,
                speed=speed_unit,
                temperature=temperature_unit,
                pressure=pressure_unit,
            ),
        )
    except (TypeError, ValueError) as exc:
        _clear_polar_result()
        st.error(f"Önizleme girdisi geçersiz: {exc}")
    else:
        x_coords, y_coords, z_coords = zip(*preview_mesh.vertices)
        i_faces, j_faces, k_faces = zip(*preview_mesh.faces)
        figure = go.Figure(
            data=[
                go.Mesh3d(
                    x=x_coords,
                    y=y_coords,
                    z=z_coords,
                    i=i_faces,
                    j=j_faces,
                    k=k_faces,
                    name="Kanat yüzeyi",
                    color="#16A3B6",
                    opacity=0.96,
                    flatshading=False,
                    lighting={
                        "ambient": 0.45,
                        "diffuse": 0.75,
                        "specular": 0.35,
                        "roughness": 0.55,
                    },
                    hovertemplate="x=%{x:.4f} m<br>y=%{y:.4f} m<br>z=%{z:.4f} m<extra></extra>",
                )
            ]
        )
        hub_angles = [2.0 * math.pi * index / 32 for index in range(33)]
        hub_half_height = max(0.003, preview_spec.hub_radius_m * 0.18)
        figure.add_trace(
            go.Surface(
                x=[
                    [preview_spec.hub_radius_m * math.cos(angle) for angle in hub_angles],
                    [preview_spec.hub_radius_m * math.cos(angle) for angle in hub_angles],
                ],
                y=[
                    [preview_spec.hub_radius_m * math.sin(angle) for angle in hub_angles],
                    [preview_spec.hub_radius_m * math.sin(angle) for angle in hub_angles],
                ],
                z=[
                    [-hub_half_height for _ in hub_angles],
                    [hub_half_height for _ in hub_angles],
                ],
                name="Göbek",
                colorscale=[[0.0, "#263746"], [1.0, "#526575"]],
                showscale=False,
                hoverinfo="skip",
            )
        )
        for guide_radius, guide_name, guide_color in (
            (preview_spec.diameter_m / 2.0, "Nominal açık çap", "#64748B"),
            (preview_spec.hinge_radius_m, "Menteşe yarıçapı", "#F59E0B"),
        ):
            guide_x, guide_y = _circle_xy(guide_radius)
            figure.add_trace(
                go.Scatter3d(
                    x=guide_x,
                    y=guide_y,
                    z=[0.0 for _ in guide_x],
                    mode="lines",
                    name=guide_name,
                    line={"color": guide_color, "dash": "dot", "width": 3},
                    hoverinfo="skip",
                )
            )
        view_span = preview_spec.diameter_m * 0.58
        figure.update_layout(
            height=620,
            margin={"l": 0, "r": 0, "t": 42, "b": 0},
            title={
                "text": f"{airfoil_id} · {int(blade_count)} kanat · θ = {fold_angle_deg}°",
                "x": 0.02,
            },
            paper_bgcolor="rgba(0,0,0,0)",
            scene={
                "aspectmode": "data",
                "xaxis": {"title": "x [m]", "range": [-view_span, view_span]},
                "yaxis": {"title": "y [m]", "range": [-view_span, view_span]},
                "zaxis": {"title": "z [m]"},
                "camera": {"eye": {"x": 1.15, "y": 1.15, "z": 1.45}},
            },
            showlegend=True,
        )
        st.plotly_chart(
            figure,
            use_container_width=True,
            config={"displaylogo": False},
        )
        preview_metrics = st.columns(4)
        preview_metrics[0].metric(
            "Düzlemsel radyal projeksiyon çapı",
            f"{2.0 * preview_mesh.effective_radius_m * 1000:.1f} mm",
        )
        preview_metrics[1].metric(
            "Merkez-hat zarf çapı",
            f"{2.0 * preview_mesh.centerline_envelope_radius_m * 1000:.1f} mm",
        )
        preview_metrics[2].metric(
            "Mesh zarf çapı",
            f"{2.0 * preview_mesh.mesh_envelope_radius_m * 1000:.1f} mm",
        )
        preview_metrics[3].metric("Nominal açık çap", f"{preview_spec.diameter_m * 1000:.1f} mm")
        st.caption(
            f"Önizleme modeli {airfoil_id} · {len(preview_mesh.faces):,} yüzey üçgeni · "
            f"qualification={preview_mesh.qualification}"
        )
        st.caption(
            f"Profil koordinat SHA-256: {preview_mesh.airfoil_coordinate_sha256} · "
            f"Kaynak: {selected_airfoil.source} · "
            f"Kesit çevresi: {preview_mesh.section_vertex_count} nokta"
        )
        st.caption(
            "Önizleme, taslak ve polar kimliği aynı örneklenmiş referans koordinatlarına "
            "bağlıdır. Katalog üretim CAD'i veya ölçülmüş kanat değildir; nokta "
            "çözünürlüğü ve profil adı aerodinamik doğruluk ya da fiziksel yeterlilik sağlamaz."
        )
        st.caption(
            "Rotor düzlemi x–y, eksenel yön z'dir. Menteşe dışı yüzey negatif açıyla "
            "ayrı bir seam üzerinden rijit döndürülür. Düzlemsel radyal projeksiyon "
            "yalnız bu görselleştirmenin izdüşümüdür ve PR-06D performans hesabı "
            "değildir; merkez-hat zarfı eksene gerçek uzaklığı, mesh zarfı "
            "ise chord dahil çizilen yüzeyi ölçer. Hiçbiri CFD/BEM sonucu değildir."
        )
        _render_geometry_compatibility(geometry_audit)

        st.subheader("Doğrulanmış taslak config")
        st.caption("Niteliksiz tasarım taslağı")
        st.success("Config yükleyicisi round-trip doğrulamasını geçti.")
        st.markdown(f"`Kanonik kaynak SHA-256 · {draft.source_sha256}`")
        st.markdown(f"`Taslak SHA-256 · {draft.draft_sha256}`")
        st.download_button(
            "Taslak TOML indir",
            data=draft.toml,
            file_name=draft.filename,
            mime="application/toml",
        )
        st.info(
            "İndirilen dosya `unqualified_design_draft` olarak işaretlidir. Kanonik "
            "dosyaya dönüş ancak ayrı review ve doğrulama adımıyla yapılabilir."
        )
        _render_design_preparation(draft)

    st.subheader("Kanat istasyonları")
    _render_markdown_table(
        [
            {
                "r/R": station.r_over_R,
                "Chord [mm]": round(station.chord_m * 1000.0, 3),
                "Twist [deg]": round(station.twist_deg, 3),
                "Airfoil": station.airfoil_id,
            }
            for station in snapshot.blade_stations
        ]
    )
    st.info(
        "İstasyon tablosu kanonik girdiyi salt okunur gösterir; önizleme kontrolleri "
        "yalnız tarayıcı oturumu içindir."
    )


def _render_operating_conditions() -> None:
    snapshot = load_dashboard_snapshot(REPO_ROOT)
    st.title("Çalışma Koşulları")
    _render_markdown_table(
        [
            {
                "Kimlik": condition.id,
                "RPM": round(condition.rpm, 3),
                "V∞ [m/s]": condition.forward_speed_m_s,
                "ρ [kg/m³]": condition.air_density_kg_m3,
                "μ [Pa·s]": condition.dynamic_viscosity_pa_s,
                "T [K]": condition.temperature_k,
                "p [Pa]": condition.pressure_pa,
            }
            for condition in snapshot.operating_conditions
        ]
    )
    st.info("Gösterilen değerler kanonik TOML dosyasından SI birimlerinde okunur.")


def _render_mechanism_transient() -> None:
    st.subheader("PY-05A · Reçeteli dönüş mekanizma geçişi")
    st.warning(
        "Bu bağımsız tek rijit-cisim örneği aktif kanat taslağı veya prototip ölçümü değildir. "
        "Kuru sürtünme, temas tepkisi/sekme, aerodinamik yük, BEM ve motor bağlaşımı yoktur; "
        "physical_qualification=false."
    )
    columns = st.columns(4)
    mass = columns[0].number_input("Geçiş kütlesi [kg]", min_value=0.0001, value=0.20, format="%.4f")
    cg = columns[1].number_input("Geçiş CG mesafesi [m]", min_value=0.0, value=0.05, format="%.4f")
    inertia = columns[2].number_input("Geçiş menteşe ataleti [kg m²]", min_value=0.000001, value=0.0006, format="%.6f")
    radius = columns[3].number_input("Geçiş menteşe yarıçapı [m]", min_value=0.0, value=0.10, format="%.4f")
    columns = st.columns(4)
    stiffness = columns[0].number_input("Geçiş yay katsayısı [N m/rad]", min_value=0.0, value=0.02, format="%.4f")
    damping = columns[1].number_input("Geçiş viskoz sönüm [N m s/rad]", min_value=0.0, value=0.001, format="%.4f")
    initial_deg = columns[2].number_input("Başlangıç açısı [deg]", value=-60.0, min_value=-179.0, max_value=179.0)
    target_rpm = columns[3].number_input("Hedef RPM", min_value=0.0, value=1200.0, step=100.0)
    duration = st.number_input("Geçiş süresi [s]", min_value=0.02, max_value=10.0, value=0.5, step=0.05)
    try:
        parameters = MechanismParameters(
            mass, cg, inertia, radius, stiffness, 0.0, damping,
            math.radians(-179.5), math.radians(179.5),
        )
        transient = TransientRequest(
            parameters, DriveHistory((0.0, duration), (0.0, target_rpm), (0.0, 0.0)),
            math.radians(initial_deg), 0.0, SolverControls(max_step_s=min(0.002, duration / 20)),
        )
        parameter_sources = {name: "user_declared_unqualified" for name in vars(parameters)}
        request = MechanismTransientRequest(transient, {
            "classification": "user_declared_mechanism_workbench",
            "prototype_measurement": False,
            "input_sources": {
                "parameters": parameter_sources,
                "drive": {name: "user_declared_unqualified" for name in vars(transient.drive)},
                "initial_state": {"initial_angle_rad": "user_declared_unqualified",
                                  "initial_angular_velocity_rad_s": "user_declared_unqualified"},
                "controls": {name: "software_numerical_policy" for name in vars(transient.controls)},
            },
            "references": [],
            "limitations": ["Values are explicit user inputs, not active-draft or prototype measurements."],
        })
        prepared = prepare_mechanism_transient(request)
    except (ValueError, MechanismTransientError, OSError) as exc:
        st.session_state.pop(TRANSIENT_RESULT_KEY, None)
        st.session_state.pop(TRANSIENT_REQUEST_KEY, None)
        st.error(f"Geçiş girdisi kapalı biçimde reddedildi: {exc}")
        return
    if st.session_state.get(TRANSIENT_REQUEST_KEY) != prepared.request_sha256:
        st.session_state.pop(TRANSIENT_RESULT_KEY, None)
        st.session_state.pop(TRANSIENT_REQUEST_KEY, None)
    if st.button("Mekanizma geçişini çalıştır", type="primary"):
        try:
            artifact = run_mechanism_transient(request, expected_request_sha256=prepared.request_sha256)
        except (MechanismTransientError, OSError) as exc:
            st.error(f"Geçiş çözümü tamamlanmadı: {exc}")
        else:
            st.session_state[TRANSIENT_RESULT_KEY] = artifact
            st.session_state[TRANSIENT_REQUEST_KEY] = prepared.request_sha256
    artifact = st.session_state.get(TRANSIENT_RESULT_KEY)
    if not isinstance(artifact, MechanismTransientArtifact) or artifact.report_json is None:
        return
    document = json.loads(artifact.report_json)
    result = document["result"]
    st.caption(f"Durum: {result['status']} · örnek: {len(result['time_s'])} · SHA-256: {artifact.report_sha256}")
    if result["contact"]:
        st.info(f"İlk {result['contact']['stop']} durdurucu teması: {result['contact']['time_s']:.6g} s; "
                f"temas öncesi hız {result['contact']['preimpact_angular_velocity_rad_s']:.6g} rad/s")
    figure = go.Figure(go.Scatter(x=result["time_s"], y=result["angle_rad"], mode="lines", name="θ [rad]"))
    figure.update_layout(xaxis_title="t [s]", yaxis_title="θ [rad]")
    st.plotly_chart(figure, use_container_width=True)
    st.download_button("Geçiş sonucunu JSON indir", data=artifact.report_json,
                       file_name=artifact.filename, mime="application/json")


def _render_folding_mechanism() -> None:
    snapshot = load_dashboard_snapshot(REPO_ROOT)
    st.title("Katlanma Davranışı")
    st.warning(
        "Bu ekran rijit uç-segment düzlemsel kinematiğini ve sürümlü V02 yazılım "
        "fixture'ının moment ayrıştırmasını gösterir. CAD temas modeli, ANSYS gerilmesi, "
        "yorulma ömrü veya fiziksel yeterlilik değildir.",
        icon="🔎",
    )


    st.subheader("Geometri ve mekanizma girdileri")
    st.caption(
        "Bu sayfa bağımsız bir mekanizma senaryosudur; Tasarım Geometrisi sayfasındaki "
        "widget durumunu devralmaz. Varsayılanlar aynı kanonik snapshot'tan gelir."
    )
    dimension_columns = st.columns(5)
    diameter_mm = dimension_columns[0].number_input(
        "Mekanizma açık çapı [mm]",
        min_value=50.0,
        max_value=1000.0,
        value=float(snapshot.open_diameter_m * 1000.0),
        step=1.0,
    )
    hub_radius_mm = dimension_columns[1].number_input(
        "Mekanizma göbek yarıçapı [mm]",
        min_value=1.0,
        max_value=200.0,
        value=float(snapshot.hub_radius_m * 1000.0),
        step=1.0,
    )
    hinge_radius_mm = dimension_columns[2].number_input(
        "Mekanizma menteşe yarıçapı [mm]",
        min_value=2.0,
        max_value=400.0,
        value=float(snapshot.hinge_radius_m * 1000.0),
        step=1.0,
    )
    stowed_target_mm = dimension_columns[3].number_input(
        "Katlanmış zarf hedefi [mm]",
        min_value=1.0,
        max_value=1000.0,
        value=float(snapshot.stowed_envelope_m * 1000.0),
        step=1.0,
    )
    fold_angle_deg = dimension_columns[4].slider(
        "Mekanizma açısı [deg]",
        min_value=-180,
        max_value=0,
        value=-180,
        step=5,
    )
    rpm = st.slider(
        "V02 moment fixture RPM",
        min_value=0,
        max_value=12000,
        value=int(round(snapshot.checkpoint_rpm)),
        step=100,
    )

    try:
        audit = build_mechanism_geometry_audit(
            MechanismGeometryInputs(
                diameter_m=diameter_mm / 1000.0,
                hub_radius_m=hub_radius_mm / 1000.0,
                hinge_radius_m=hinge_radius_mm / 1000.0,
                fold_angle_deg=float(fold_angle_deg),
                stowed_requirement_m=stowed_target_mm / 1000.0,
            ),
            tuple(station.r_over_R for station in snapshot.blade_stations),
        )
        fixture = build_mechanism_physics_fixture(
            REPO_ROOT / "configs/foldable/TIP_HINGED_250_V02.json",
            rpm=float(rpm),
            theta_deg=float(fold_angle_deg),
        )
    except (OSError, TypeError, ValueError) as exc:
        st.error(f"Mekanizma girdisi kapalı biçimde reddedildi: {exc}")
        return

    geometry_figure = go.Figure()
    for radius_m, name, color, dash in (
        (audit.diameter_m / 2.0, "Nominal açık çap", "#64748B", "dot"),
        (audit.stowed_requirement_m / 2.0, "Katlanmış zarf hedefi", "#EF4444", "dash"),
        (
            audit.centerline_envelope_diameter_m / 2.0,
            "Mevcut merkez-hat zarfı",
            "#22D3EE",
            "solid",
        ),
    ):
        x_circle, y_circle = _circle_xy(radius_m)
        geometry_figure.add_trace(
            go.Scatter(
                x=x_circle,
                y=y_circle,
                mode="lines",
                name=name,
                line={"color": color, "dash": dash, "width": 2},
                hoverinfo="skip",
            )
        )

    for blade_index in range(snapshot.blade_count):
        azimuth = 2.0 * math.pi * blade_index / snapshot.blade_count
        cosine = math.cos(azimuth)
        sine = math.sin(azimuth)

        def rotate(x_coord: float, y_coord: float) -> tuple[float, float]:
            return (
                x_coord * cosine - y_coord * sine,
                x_coord * sine + y_coord * cosine,
            )

        hub_point = rotate(audit.hub_radius_m, 0.0)
        hinge_point = rotate(audit.hinge_radius_m, 0.0)
        tip_point = rotate(audit.tip_center_x_m, audit.tip_center_y_m)
        geometry_figure.add_trace(
            go.Scatter(
                x=[hub_point[0], hinge_point[0]],
                y=[hub_point[1], hinge_point[1]],
                mode="lines+markers",
                name="Sabit kök" if blade_index == 0 else None,
                showlegend=blade_index == 0,
                line={"color": "#CBD5E1", "width": 9},
                marker={"size": 7},
            )
        )
        geometry_figure.add_trace(
            go.Scatter(
                x=[hinge_point[0], tip_point[0]],
                y=[hinge_point[1], tip_point[1]],
                mode="lines+markers",
                name="Katlanan uç" if blade_index == 0 else None,
                showlegend=blade_index == 0,
                line={"color": "#16A3B6", "width": 9},
                marker={"size": 8},
            )
        )
        path_angles = [
            math.radians(float(fold_angle_deg) * index / 36.0) for index in range(37)
        ]
        local_path = [
            (
                audit.hinge_radius_m + audit.tip_segment_length_m * math.cos(angle),
                audit.tip_segment_length_m * math.sin(angle),
            )
            for angle in path_angles
        ]
        rotated_path = [rotate(*point) for point in local_path]
        geometry_figure.add_trace(
            go.Scatter(
                x=[point[0] for point in rotated_path],
                y=[point[1] for point in rotated_path],
                mode="lines",
                name="Uç yolu" if blade_index == 0 else None,
                showlegend=blade_index == 0,
                line={"color": "#F59E0B", "dash": "dot", "width": 1},
                hoverinfo="skip",
            )
        )

    hub_x, hub_y = _circle_xy(audit.hub_radius_m)
    geometry_figure.add_trace(
        go.Scatter(
            x=hub_x,
            y=hub_y,
            mode="lines",
            name="Göbek",
            fill="toself",
            fillcolor="rgba(71,85,105,0.45)",
            line={"color": "#94A3B8"},
        )
    )
    view_radius = max(audit.diameter_m, audit.centerline_envelope_diameter_m) * 0.56
    geometry_figure.update_layout(
        height=570,
        margin={"l": 10, "r": 10, "t": 45, "b": 10},
        title="Düzlemsel rijit uç-segment kinematiği",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"title": "x [m]", "range": [-view_radius, view_radius]},
        yaxis={
            "title": "y [m]",
            "range": [-view_radius, view_radius],
            "scaleanchor": "x",
            "scaleratio": 1,
        },
        legend={"orientation": "h"},
    )
    st.plotly_chart(geometry_figure, use_container_width=True, config={"displaylogo": False})

    metrics = st.columns(4)
    metrics[0].metric(
        "Mevcut merkez-hat zarfı",
        f"{audit.centerline_envelope_diameter_m * 1000:.1f} mm",
    )
    metrics[1].metric(
        "Çarpışmasız minimum zarf",
        f"{audit.collision_free_minimum_envelope_diameter_m * 1000:.1f} mm",
    )
    metrics[2].metric("Zarf hedefi", f"{audit.stowed_requirement_m * 1000:.1f} mm")
    metrics[3].metric(
        "Göbek merkez-hat açıklığı",
        f"{audit.hub_centerline_clearance_m * 1000:.1f} mm",
    )
    st.markdown(f"`Sınıflandırma · {audit.classification}`")
    st.markdown("`Physical qualification · false`")
    st.caption(
        f"Saf kinematik teorik minimum {audit.minimum_centerline_envelope_diameter_m * 1000:.1f} mm; "
        f"tam katlanma yolu göbek açıklığı {audit.full_stow_path_hub_clearance_m * 1000:.1f} mm."
    )
    _render_geometry_compatibility(audit)

    st.subheader("V02 yazılım fixture moment ayrıştırması")
    st.warning(
        "Bu bölüm sürümlü TIP_HINGED_250_V02 sentetik parametreleriyle öngörülmüş "
        "açılarda statik moment ayrıştırmasıdır; hareket veya açılma tahmini değildir. "
        "θ̇=0 olduğundan sönüm, tip thrust=0 olduğundan aerodinamik menteşe yükü "
        "yoktur; sonuç fiziksel tasarım yükü değildir."
    )
    fixture_matches = (
        math.isclose(audit.diameter_m, fixture.diameter_m, abs_tol=1e-12)
        and math.isclose(audit.hinge_radius_m, fixture.hinge_radius_m, abs_tol=1e-12)
        and snapshot.blade_count == fixture.blade_count
    )
    st.markdown(f"`Fixture · {fixture.fixture_id}`")
    st.markdown(f"`Fixture SHA-256 · {fixture.source_sha256}`")
    st.markdown(f"`Sınıflandırma · {fixture.classification}`")
    if not fixture_matches:
        st.info(
            "Girilen çap/menteşe ölçüleri V02 fixture geometrisinden ayrıldığı için "
            "moment eğrisi gösterilmedi. Yeni fizik parametreleri varsayılmadı."
        )
        return

    moment_figure = go.Figure()
    for field, label, color in (
        ("centrifugal_moment_nm", "Merkezkaç", "#22D3EE"),
        ("stiffness_moment_nm", "Yay direnci", "#F59E0B"),
        ("friction_moment_nm", "Sürtünme", "#A78BFA"),
        ("net_moment_nm", "Net", "#34D399"),
    ):
        moment_figure.add_trace(
            go.Scatter(
                x=[point.theta_deg for point in fixture.curve],
                y=[getattr(point, field) for point in fixture.curve],
                mode="lines",
                name=label,
                line={"color": color},
            )
        )
    moment_figure.update_layout(
        height=430,
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        xaxis_title="Menteşe açısı [deg]",
        yaxis_title="Moment [N·m]",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend={"orientation": "h"},
    )
    st.plotly_chart(moment_figure, use_container_width=True, config={"displaylogo": False})
    selected_metrics = st.columns(4)
    selected_metrics[0].metric(
        "Merkezkaç momenti", f"{fixture.selected.centrifugal_moment_nm:.6f} N·m"
    )
    selected_metrics[1].metric(
        "Yay momenti", f"{fixture.selected.stiffness_moment_nm:.6f} N·m"
    )
    selected_metrics[2].metric(
        "Sürtünme momenti", f"{fixture.selected.friction_moment_nm:.6f} N·m"
    )
    selected_metrics[3].metric("Net fixture momenti", f"{fixture.selected.net_moment_nm:.6f} N·m")


def _opening_result_rows(rows) -> list[dict[str, float]]:
    return [
        {
            "Açı [deg]": row.angle_from_deployed_deg,
            "D_eff [mm]": row.effective_diameter_m * 1000.0,
            "Statik T/T₀": row.static_thrust_ratio_median,
            "Statik Q/Q₀": row.static_torque_ratio_median,
            "İleri T/T₀": row.forward_thrust_ratio_median,
            "İleri Q/Q₀": row.forward_torque_ratio_median,
        }
        for row in rows
    ]


def _render_opening_chart(rows: list[dict[str, float]]) -> None:
    """Render screening ratios through Plotly without Arrow/Pandas conversion."""
    if not rows:
        st.caption("Grafik için tarama sonucu yok.")
        return
    figure = go.Figure()
    for column in ("Statik T/T₀", "Statik Q/Q₀", "İleri T/T₀", "İleri Q/Q₀"):
        figure.add_trace(
            go.Scatter(
                x=[row["Açı [deg]"] for row in rows],
                y=[row[column] for row in rows],
                mode="lines+markers",
                name=column,
            )
        )
    figure.update_layout(
        xaxis_title="Açı [deg]",
        yaxis_title="Boyutsuz oran",
        legend_title="Tarama metriği",
        margin=dict(l=20, r=20, t=30, b=20),
    )
    st.plotly_chart(
        figure,
        use_container_width=True,
        config={"displayModeBar": False},
    )


def _render_session_analysis_result(artifact: AnalysisRunArtifact) -> None:
    st.subheader("Bu oturumda üretilen sonuç")
    st.success("Yeni koşum sürümlü arşiv raporuyla birebir eşleşti.")
    st.markdown(f"`Artifact class · {artifact.artifact_class}`")
    st.markdown(f"`Qualification · {artifact.qualification}`")
    st.markdown("`Physical qualification · false`")

    cases, conditions, states, duration = st.columns(4)
    cases.metric("Yeni koşum vakası", str(artifact.case_count))
    conditions.metric("Çalışma noktası", str(artifact.condition_count))
    states.metric("Açılma durumu", str(artifact.state_count))
    duration.metric("Koşum süresi", f"{artifact.duration_seconds:.1f} s")

    rows = _opening_result_rows(artifact.rows)
    _render_opening_chart(rows)
    _render_markdown_table(rows)
    st.markdown(f"`İstek SHA-256 · {artifact.request_sha256}`")
    st.markdown(f"`Hesap politikası SHA-256 · {artifact.policy_sha256}`")
    st.markdown(f"`Fixture SHA-256 · {artifact.fixture_sha256}`")
    st.markdown(f"`Oturum raporu SHA-256 · {artifact.report_sha256}`")
    st.markdown(f"`Arşiv raporu SHA-256 · {artifact.archived_report_sha256}`")
    st.markdown(f"`Oturum manifesti SHA-256 · {artifact.manifest_sha256}`")
    st.download_button(
        "Oturum manifestini JSON indir",
        data=artifact.manifest_json,
        file_name=artifact.filename,
        mime="application/json",
    )


def _render_analysis_run() -> None:
    st.title("Analiz Çalıştırma")
    try:
        recipe = get_analysis_recipe(REPO_ROOT, PR06D_ANALYSIS_ID)
    except (AnalysisRunError, OSError) as exc:
        st.error(f"Analiz tarifi kapalı biçimde yüklenemedi: {exc}")
        return
    request_identity = (
        f"{recipe.id}:{recipe.fixture_sha256}:{recipe.archived_report_sha256}:"
        f"{recipe.policy_sha256}"
    )
    stored_identity = st.session_state.get(ANALYSIS_REQUEST_KEY)
    if stored_identity is not None and stored_identity != request_identity:
        st.session_state.pop(ANALYSIS_RESULT_KEY, None)
        st.session_state.pop(ANALYSIS_REQUEST_KEY, None)

    st.warning(
        "Bu recipe, aktif 250 mm taslak tasarımı çözmez. Sürümdeki 254 mm UIUC APC 10×4.7 "
        "fixture'ını analitik proxy ile yeniden hesaplar; sonuç yalnız tarama amaçlıdır "
        "ve fiziksel yeterlilik oluşturmaz.",
        icon="🔎",
    )
    st.selectbox("İzinli analiz tarifi", (recipe.title,), disabled=True)
    st.caption(
        "Açık kullanıcı eylemi dışında çalışmaz; dış solver/subprocess çağırmaz ve "
        "repo, kanonik config veya reports/ altına yazmaz."
    )
    st.markdown(
        f"`Fixture · {recipe.fixture_path.relative_to(REPO_ROOT)} · "
        f"{recipe.fixture_sha256}`"
    )
    st.markdown(
        f"`Arşiv · {recipe.archived_report_path.relative_to(REPO_ROOT)} · "
        f"{recipe.archived_report_sha256}`"
    )
    st.info(
        f"Sabit kaynak politikası: {recipe.expected_case_count} vaka · "
        f"{recipe.expected_condition_count} koşul · {recipe.expected_state_count} durum · "
        f"{recipe.annulus_count} annulus · açılar {recipe.angles_deg}° · "
        f"menteşe oranı {recipe.hinge_radius_ratio:.2f} · "
        f"{recipe.loading_branch}. Politika SHA-256: {recipe.policy_sha256}. "
        "Tipik çalışma süresi yaklaşık 20–30 saniyedir."
    )

    if st.button("Tarama analizini çalıştır", type="primary"):
        st.session_state.pop(ANALYSIS_RESULT_KEY, None)
        with st.spinner("İzinli PR-06D taraması çalıştırılıyor…"):
            try:
                artifact = run_analysis(REPO_ROOT, PR06D_ANALYSIS_ID)
            except AnalysisRunError as exc:
                st.session_state.pop(ANALYSIS_REQUEST_KEY, None)
                st.error(f"Analiz kapalı biçimde durduruldu: {exc}")
            else:
                st.session_state[ANALYSIS_RESULT_KEY] = artifact
                st.session_state[ANALYSIS_REQUEST_KEY] = request_identity

    artifact = st.session_state.get(ANALYSIS_RESULT_KEY)
    if isinstance(artifact, AnalysisRunArtifact):
        _render_session_analysis_result(artifact)
    else:
        st.caption("Henüz bu oturumda analiz çalıştırılmadı.")


def _render_performance_results() -> None:
    snapshot = load_opening_sensitivity(REPO_ROOT)
    st.title("Performans Sonuçları")
    st.warning(
        "Tarama amaçlı: PR-06D açılma duyarlılığı PR-06C fiziksel kapısı geçmeden "
        "tasarım kararı veya doğrulanmış performans değildir.",
        icon="🔎",
    )
    cases, conditions, states = st.columns(3)
    cases.metric("Vaka", str(snapshot.case_count))
    conditions.metric("Çalışma noktası", str(snapshot.condition_count))
    states.metric("Açılma durumu", str(snapshot.state_count))

    rows = _opening_result_rows(snapshot.rows)
    _render_opening_chart(rows)
    _render_markdown_table(rows)
    st.caption(f"Rapor SHA-256 · {snapshot.report_sha256}")


def _render_evidence_import() -> None:
    st.title("CFD / FEA / Deney")
    st.warning(
        "Yüklenen dosya yalnız bu tarayıcı oturumunda sözleşme denetiminden geçer. "
        "Repo'ya yazılmaz, solver çalıştırmaz ve fiziksel yeterlilik oluşturmaz.",
        icon="🔎",
    )
    label = st.selectbox("Kanıt sözleşmesi", tuple(EVIDENCE_KIND_BY_LABEL))
    uploaded = st.file_uploader(
        "JSON kanıt dosyası",
        type=("json",),
        accept_multiple_files=False,
        help="En fazla 5 MiB; dosya türü seçilen sözleşmeyle eşleşmelidir.",
    )
    st.caption(
        "Desteklenen ilk UI-05 dilimi: yayımlanmış CFD referans fixture'ı ile "
        "sürümlü PR-09/PR-10 sözleşme raporlarının salt-okunur denetimi."
    )
    if uploaded is None:
        st.info("Denetim için bir JSON dosyası seçin.")
        return
    if uploaded.size > MAX_EVIDENCE_UPLOAD_BYTES:
        st.error("Kanıt kapalı biçimde reddedildi: dosya 5 MiB sınırını aşıyor.")
        return
    try:
        artifact = inspect_evidence_upload(
            uploaded.getvalue(),
            uploaded.name,
            EVIDENCE_KIND_BY_LABEL[label],
        )
    except EvidenceImportError as exc:
        st.error(f"Kanıt kapalı biçimde reddedildi: {exc}")
        return

    st.success("Dosya seçilen sürümlü sözleşmeyle uyumlu.")
    identity, size, schema = st.columns(3)
    identity.metric("Kanıt kimliği", artifact.identity)
    size.metric("Dosya boyutu", f"{artifact.size_bytes / 1024.0:.1f} KiB")
    schema.metric("Şema", str(artifact.schema_version))
    st.markdown(f"`Sınıflandırma · {artifact.classification}`")
    st.markdown(f"`Qualification · {artifact.qualification}`")
    st.markdown("`Physical qualification · false`")
    st.markdown(f"`Kaynak SHA-256 · {artifact.source_sha256}`")
    _render_markdown_table(
        [{"Alan": field, "Değer": value} for field, value in artifact.summary]
    )


def main() -> None:
    st.set_page_config(
        page_title="PyFoldable Engineering Workspace",
        page_icon="⚙️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    with st.sidebar:
        st.markdown("## PyFoldable")
        st.caption("Evidence-first engineering workspace")
        page = st.radio("Çalışma alanı", PAGES)
        st.divider()
        st.caption("Niteliksiz çıktılar tasarım kararı değildir.")

    if page == "Genel Bakış":
        _render_overview()
    elif page == "Tasarım Geometrisi":
        _render_design_geometry()
    elif page == "Çalışma Koşulları":
        _render_operating_conditions()
    elif page == "Analiz Çalıştırma":
        _render_analysis_run()
    elif page == "Performans Sonuçları":
        _render_performance_results()
    elif page == "Mekanizma Geçişi":
        st.title("Mekanizma Geçişi")
        _render_mechanism_transient()
    elif page == "Katlanma Davranışı":
        _render_folding_mechanism()
    elif page == "CFD / FEA / Deney":
        _render_evidence_import()
    else:
        _render_planned_page(page)


main()
