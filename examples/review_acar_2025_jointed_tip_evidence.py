"""Audit and integrate the transferable contracts in Acar's 2025 jointed-tip paper."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from pyfoldable.core import assess_signed_propulsor_state


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "literature"
    / "acar_2025_jointed_tip_bemt_v1.json"
)
DEFAULT_JSON = PROJECT_ROOT / "reports" / "pr06d_acar_2025_jointed_tip_review.json"
DEFAULT_MARKDOWN = PROJECT_ROOT / "reports" / "pr06d_acar_2025_jointed_tip_review.md"


def _fixture(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported Acar 2025 fixture schema.")
    if payload.get("physical_qualification") is not False:
        raise ValueError("Literature fixture cannot claim physical qualification.")
    points = payload.get("points")
    if not isinstance(points, list) or len(points) != 31:
        raise ValueError("Acar 2025 Table 1 must contain exactly 31 points.")
    speeds = [float(point["v_m_s"]) for point in points]
    if speeds != [float(value) for value in range(31)]:
        raise ValueError("Acar 2025 speeds must be the frozen 0..30 m/s sweep.")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_report(fixture_path: Path = DEFAULT_FIXTURE) -> Mapping[str, Any]:
    payload = _fixture(fixture_path)
    points = payload["points"]
    components = {
        "main": ("t_main_n", "p_main_w", "eta_main"),
        "tip": ("t_tip_n", "p_tip_w", "eta_tip"),
        "combined": ("t_total_n", "p_total_w", "eta_total"),
    }
    mode_counts: dict[str, Mapping[str, int]] = {}
    rejected_efficiencies: list[Mapping[str, Any]] = []
    reported_efficiency_formula_errors: list[float] = []
    first_modes: dict[str, dict[str, float]] = {}
    for component, (thrust_key, power_key, eta_key) in components.items():
        counts: Counter[str] = Counter()
        transitions: dict[str, float] = {}
        for point in points:
            assessment = assess_signed_propulsor_state(
                float(point[thrust_key]),
                float(point[power_key]),
                float(point["v_m_s"]),
            )
            counts[assessment.mode] += 1
            transitions.setdefault(assessment.mode, float(point["v_m_s"]))
            reported = float(point[eta_key])
            expected = assessment.propulsive_efficiency
            if assessment.raw_thrust_power_ratio is not None:
                reported_efficiency_formula_errors.append(
                    abs(reported - assessment.raw_thrust_power_ratio)
                )
            if (
                expected is None and abs(reported) > 1.0e-9
            ) or (
                expected is not None and abs(expected - reported) > 5.0e-4
            ):
                rejected_efficiencies.append(
                    {
                        "component": component,
                        "speed_m_s": float(point["v_m_s"]),
                        "mode": assessment.mode,
                        "reported_eta": reported,
                        "safe_propulsive_efficiency": expected,
                    }
                )
        mode_counts[component] = dict(sorted(counts.items()))
        first_modes[component] = dict(sorted(transitions.items()))

    thrust_errors = [
        abs(
            float(point["t_total_n"])
            - float(point["t_main_n"])
            - float(point["t_tip_n"])
        )
        for point in points
    ]
    power_errors = [
        abs(
            float(point["p_total_w"])
            - float(point["p_main_w"])
            - float(point["p_tip_w"])
        )
        for point in points
    ]
    source = dict(payload["source"])
    return {
        "schema_version": 1,
        "kind": "pr06d-acar-2025-jointed-tip-methodology-review",
        "evidence_class": payload["evidence_class"],
        "physical_qualification": False,
        "source": source,
        "fixture": {
            "id": payload["id"],
            "path": str(fixture_path.relative_to(PROJECT_ROOT)),
            "sha256": _sha256(fixture_path),
        },
        "reported_model": dict(payload["reported_model"]),
        "point_count": len(points),
        "speed_range_m_s": [float(points[0]["v_m_s"]), float(points[-1]["v_m_s"])],
        "table_audit": {
            "maximum_thrust_closure_error_n": max(thrust_errors),
            "maximum_power_closure_error_w": max(power_errors),
            "maximum_reported_efficiency_formula_error": max(
                reported_efficiency_formula_errors
            ),
            "reported_efficiency_rejected_count": len(rejected_efficiencies),
            "rejected_efficiency_examples": rejected_efficiencies[:8],
        },
        "mode_counts": mode_counts,
        "first_mode_speed_m_s": first_modes,
        "internal_consistency_findings": [
            "main_thrust_narrative_conflicts_with_table",
            "angular_speed_power_equation_has_extra_2pi",
            "claimed_predictive_accuracy_has_no_experimental_or_cfd_validation",
            "discussion_uses_a_second_nonidentical_tip_inflow_equation",
        ],
        "reproduction_blockers": list(payload["reproduction_blockers"]),
        "transfer_to_pyfoldable": {
            "implemented": [
                "sign_safe_propulsor_mode_classification",
                "fail_closed_propulsive_efficiency",
                "typed_tip_mounted_effective_inflow_screening_relation",
                "machine_readable_table_closure_and_consistency_audit",
            ],
            "design_hypotheses_only": [
                "active_pitch_or_stow_to_avoid_powered_drag",
                "energy_recovery_requires_explicit_generator_and_net_drag_accounting",
                "tip_mass_requires_flutter_fatigue_and_vibration_assessment",
            ],
            "not_transferred": [
                "paper_performance_values_as_validation_targets",
                "generic_naca2412_linear_polar_as_project_airfoil_evidence",
                "reported_efficiency_outside_propulsive_mode",
            ],
        },
        "gate_effect": {
            "pr06c_physical_gate_changed": False,
            "pr06d_physical_qualification_changed": False,
            "reason": "computational methodology with incomplete reproducibility inputs",
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    audit = report["table_audit"]
    lines = [
        "# PR-06D Acar 2025 jointed-tip methodology review",
        "",
        f"- Evidence class: `{report['evidence_class']}`",
        "- Physical qualification: **false**",
        f"- Audited table points: {report['point_count']}",
        f"- Speed range: {report['speed_range_m_s'][0]:.0f}-{report['speed_range_m_s'][1]:.0f} m/s",
        f"- Maximum thrust closure error: {audit['maximum_thrust_closure_error_n']:.6f} N",
        f"- Maximum power closure error: {audit['maximum_power_closure_error_w']:.6f} W",
        f"- Reported efficiencies rejected by sign-safe rules: {audit['reported_efficiency_rejected_count']}",
        "",
        "## Transferable implementation",
        "",
    ]
    lines.extend(
        f"- `{item}`" for item in report["transfer_to_pyfoldable"]["implemented"]
    )
    lines.extend(("", "## Reproduction blockers", ""))
    lines.extend(f"- `{item}`" for item in report["reproduction_blockers"])
    lines.extend(("", "## Gate decision", ""))
    lines.append(
        "The paper is computational methodology evidence only. It does not change "
        "PR-06C or PR-06D physical qualification."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = build_report(args.fixture)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.markdown.write_text(render_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
