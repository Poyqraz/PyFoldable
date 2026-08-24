"""Streamlit entrypoint for the evidence-first PyFoldable workspace."""

from __future__ import annotations

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
    DesignDraftInputs,
    DraftUnitSelection,
    build_design_draft,
)
from pyfoldable.application.evidence_import import (
    EvidenceImportError,
    MAX_EVIDENCE_UPLOAD_BYTES,
    inspect_evidence_upload,
)
from pyfoldable.application.opening_sensitivity import load_opening_sensitivity
from pyfoldable.application.ui_render import build_markdown_table
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
EVIDENCE_KIND_BY_LABEL = {
    "Yayımlanmış CFD referans fixture'ı": "cfd_reference",
    "PR-09 FEA sözleşme raporu": "fea_contract_report",
    "PR-10 deney sözleşme raporu": "experiment_contract_report",
}


def _render_markdown_table(rows: list[dict[str, object]]) -> None:
    """Render small read-only tables without Streamlit's Arrow bridge."""
    table = build_markdown_table(rows)
    if not table:
        st.caption("Gösterilecek kayıt yok.")
        return
    st.markdown(table)


def _render_overview() -> None:
    snapshot = load_dashboard_snapshot(REPO_ROOT)

    st.title("PyFoldable Engineering Workspace")
    st.caption(f"Aktif tasarım · {snapshot.design_id}")
    st.markdown(f"`Manifest SHA-256 · {snapshot.manifest_sha256}`")
    st.warning(snapshot.qualification_warning, icon="⚠️")

    diameter, envelope, checkpoint = st.columns(3)
    diameter.metric("Açık çap", f"{snapshot.open_diameter_m * 1000:.0f} mm")
    envelope.metric("Katlanmış zarf", f"≈ {snapshot.stowed_envelope_m * 1000:.0f} mm")
    checkpoint.metric("Kontrol noktası", f"{snapshot.checkpoint_rpm:.0f} rpm")

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
        ("NACA2412", "NACA0012", "NACA4412"),
        index=0,
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
        preview_spec = PropellerPreviewSpec(
            diameter_m=diameter_mm / 1000.0,
            hub_radius_m=hub_radius_mm / 1000.0,
            blade_count=int(blade_count),
            hinge_radius_m=hinge_radius_mm / 1000.0,
            fold_angle_deg=float(fold_angle_deg),
            airfoil_id=airfoil_id,
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
            showlegend=False,
        )
        st.plotly_chart(
            figure,
            use_container_width=True,
            config={"displaylogo": False},
        )
        preview_metrics = st.columns(4)
        preview_metrics[0].metric(
            "Radyal zarf çapı",
            f"{2.0 * preview_mesh.effective_radius_m * 1000:.1f} mm",
        )
        preview_metrics[1].metric(
            "Mesh zarf çapı",
            f"{2.0 * preview_mesh.mesh_envelope_radius_m * 1000:.1f} mm",
        )
        preview_metrics[2].metric("Yüzey üçgeni", f"{len(preview_mesh.faces):,}")
        preview_metrics[3].metric("Önizleme modeli", airfoil_id)
        st.caption(
            "Rotor düzlemi x–y, eksenel yön z'dir. Menteşe dışı yüzey negatif açıyla "
            "ayrı bir seam üzerinden rijit döndürülür. Radyal zarf merkez-hat "
            "projeksiyonudur; mesh zarfı chord dahil çizilen planformu ölçer. İkisi de "
            "CFD/BEM performans sonucu değildir."
        )

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
    elif page == "CFD / FEA / Deney":
        _render_evidence_import()
    else:
        _render_planned_page(page)


main()
