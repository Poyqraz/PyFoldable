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
from pyfoldable.application.opening_sensitivity import load_opening_sensitivity
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
    st.dataframe(
        [
            {
                "Kapı": gate.id,
                "Durum": gate.state.label_tr,
                "Karar": gate.decision,
                "Kanıt dosyası": str(gate.evidence_path.relative_to(REPO_ROOT)),
            }
            for gate in snapshot.gates
        ],
        hide_index=True,
        width="stretch",
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
        value=18.0,
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
        st.plotly_chart(figure, width="stretch", config={"displaylogo": False})
        preview_metrics = st.columns(3)
        preview_metrics[0].metric(
            "Efektif çap",
            f"{2.0 * preview_mesh.effective_radius_m * 1000:.1f} mm",
        )
        preview_metrics[1].metric("Yüzey üçgeni", f"{len(preview_mesh.faces):,}")
        preview_metrics[2].metric("Önizleme modeli", airfoil_id)
        st.caption(
            "Rotor düzlemi x–y, eksenel yön z'dir. Menteşe dışı yüzey negatif açıyla "
            "rijit döndürülür; kesit kalınlığı NACA analitik tanımından gelir."
        )

    st.subheader("Kanat istasyonları")
    st.dataframe(
        [
            {
                "r/R": station.r_over_R,
                "Chord [mm]": round(station.chord_m * 1000.0, 3),
                "Twist [deg]": round(station.twist_deg, 3),
                "Airfoil": station.airfoil_id,
            }
            for station in snapshot.blade_stations
        ],
        hide_index=True,
        width="stretch",
    )
    st.info(
        "İstasyon tablosu kanonik girdiyi salt okunur gösterir; önizleme kontrolleri "
        "yalnız tarayıcı oturumu içindir."
    )


def _render_operating_conditions() -> None:
    snapshot = load_dashboard_snapshot(REPO_ROOT)
    st.title("Çalışma Koşulları")
    st.dataframe(
        [
            {
                "Kimlik": condition.id,
                "RPM": round(condition.rpm, 3),
                "V∞ [m/s]": condition.forward_speed_m_s,
                "ρ [kg/m³]": condition.air_density_kg_m3,
                "T [K]": condition.temperature_k,
                "p [Pa]": condition.pressure_pa,
            }
            for condition in snapshot.operating_conditions
        ],
        hide_index=True,
        width="stretch",
    )
    st.info("Gösterilen değerler kanonik TOML dosyasından SI birimlerinde okunur.")


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

    rows = [
        {
            "Açı [deg]": row.angle_from_deployed_deg,
            "D_eff [mm]": row.effective_diameter_m * 1000.0,
            "Statik T/T₀": row.static_thrust_ratio_median,
            "Statik Q/Q₀": row.static_torque_ratio_median,
            "İleri T/T₀": row.forward_thrust_ratio_median,
            "İleri Q/Q₀": row.forward_torque_ratio_median,
        }
        for row in snapshot.rows
    ]
    st.line_chart(
        rows,
        x="Açı [deg]",
        y=["Statik T/T₀", "Statik Q/Q₀", "İleri T/T₀", "İleri Q/Q₀"],
    )
    st.dataframe(rows, hide_index=True, width="stretch")
    st.caption(f"Rapor SHA-256 · {snapshot.report_sha256}")


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
    elif page == "Performans Sonuçları":
        _render_performance_results()
    else:
        _render_planned_page(page)


main()
