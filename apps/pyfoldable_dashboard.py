"""Streamlit entrypoint for the evidence-first PyFoldable workspace."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pyfoldable.application.dashboard import EvidenceState, load_dashboard_snapshot
from pyfoldable.application.opening_sensitivity import load_opening_sensitivity


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
    st.markdown(f"### {snapshot.design_id}")
    st.caption(snapshot.design_description)
    diameter, blades, hinge = st.columns(3)
    diameter.metric("Açık çap", f"{snapshot.open_diameter_m * 1000:.0f} mm")
    blades.metric("Kanat sayısı", str(snapshot.blade_count))
    hinge.metric("Menteşe yarıçapı", f"{snapshot.hinge_radius_m * 1000:.0f} mm")
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
        "Bu ekran kanonik girdiyi salt okunur gösterir; henüz config dosyasını değiştirmez."
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
