"""Generate the screening-only PR-06D opening-angle sweep."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any, Mapping

from pyfoldable.core import (
    BEMAnnulusSettings,
    BEMRotorSettings,
    FoldableRotorState,
    assess_foldable_opening_sensitivity,
    build_rotor_benchmark_proxy_polar_family,
    load_rotor_benchmark_fixture,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "rotor_benchmark"
    / "uiuc_apcsf_10x4.7_v1.json"
)
DEFAULT_JSON = PROJECT_ROOT / "reports" / "pr06d_opening_sensitivity.json"
DEFAULT_MARKDOWN = PROJECT_ROOT / "reports" / "pr06d_opening_sensitivity.md"


def build_report(fixture_path: Path = DEFAULT_FIXTURE) -> Mapping[str, Any]:
    fixture = load_rotor_benchmark_fixture(fixture_path)
    family = build_rotor_benchmark_proxy_polar_family()
    blade = fixture.blade(family.airfoil_id)
    angles_deg = (0, 15, 30, 45, 60)
    states = tuple(
        FoldableRotorState(
            id=f"fold-{angle_deg:02d}deg",
            hinge_radius_m=0.75 * blade.radius_m,
            opening_angle_rad=math.radians(-angle_deg),
            deployed_angle_rad=0.0,
        )
        for angle_deg in angles_deg
    )
    settings = BEMRotorSettings(
        annulus_count=80,
        radial_domain="station_span",
        annulus_settings=BEMAnnulusSettings(
            include_tip_loss=True,
            include_root_loss=False,
            loading_branch="signed_nonreversed",
        ),
    )
    evidence = assess_foldable_opening_sensitivity(
        blade,
        states,
        tuple(fixture.condition(point) for point in fixture.eligible_points),
        {family.airfoil_id: family},
        settings=settings,
    )
    point_regimes = {point.id: point.regime for point in fixture.eligible_points}
    summaries = []
    for state, angle_deg in zip(states, angles_deg):
        state_cases = [case for case in evidence.cases if case.state_id == state.id]
        regime_summaries = {}
        for regime in ("static", "forward"):
            ratios = [
                case.thrust_ratio_to_deployed
                for case in state_cases
                if point_regimes[case.condition_id] == regime
            ]
            torque_ratios = [
                case.torque_ratio_to_deployed
                for case in state_cases
                if point_regimes[case.condition_id] == regime
            ]
            regime_summaries[regime] = {
                "point_count": len(ratios),
                "thrust_ratio_median": statistics.median(ratios),
                "thrust_ratio_minimum": min(ratios),
                "thrust_ratio_maximum": max(ratios),
                "torque_ratio_median": statistics.median(torque_ratios),
            }
        summaries.append(
            {
                "state_id": state.id,
                "angle_from_deployed_deg": -float(angle_deg),
                "projection_factor": state_cases[0].projection_factor,
                "effective_diameter_m": state_cases[0].effective_diameter_m,
                "regimes": regime_summaries,
            }
        )
    return {
        **dict(evidence.as_mapping()),
        "benchmark_id": "pr06d-uiuc-apcsf-10x4.7-opening-screen-v1",
        "fixture": {
            "id": fixture.id,
            "path": str(fixture_path.relative_to(PROJECT_ROOT)),
            "sha256": fixture.source_sha256,
            "qualification_point_count": len(fixture.eligible_points),
        },
        "solver": {
            "annulus_count": settings.annulus_count,
            "radial_domain": settings.radial_domain,
            "loading_branch": settings.annulus_settings.loading_branch,
        },
        "polar_evidence": {
            "airfoil_id": family.airfoil_id,
            "evidence_class": "analytic_proxy",
            "representative": False,
        },
        "angle_summaries": summaries,
        "decision": "pr06d_opening_sensitivity_software_complete_screening_only",
        "scope": (
            "Geometry/solver sensitivity only. Folded-state physical accuracy remains "
            "blocked by PR-06C and these ratios must not drive a final design decision."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    rows = "\n".join(
        "| {angle:.0f} | {factor:.4f} | {diameter:.4f} | {static:.3f} | "
        "{forward:.3f} | {torque:.3f} |".format(
            angle=summary["angle_from_deployed_deg"],
            factor=summary["projection_factor"],
            diameter=summary["effective_diameter_m"],
            static=summary["regimes"]["static"]["thrust_ratio_median"],
            forward=summary["regimes"]["forward"]["thrust_ratio_median"],
            torque=summary["regimes"]["static"]["torque_ratio_median"],
        )
        for summary in report["angle_summaries"]
    )
    return f"""# PR-06D opening-angle sensitivity

## Decision

**Software sweep complete; physical qualification remains blocked.** The exact deployed
endpoint matches the fixed path over all {report['condition_count']} frozen propulsive
points, and {report['state_count']} ordered opening states produced a complete
{report['case_count']}-case grid.

| fold angle (deg) | radial projection | effective D (m) | median static T/T0 | median forward T/T0 | median static Q/Q0 |
| ---: | ---: | ---: | ---: | ---: | ---: |
{rows}

## Evidence boundary

- Fixture: `{report['fixture']['id']}` ({report['fixture']['qualification_point_count']} points)
- Annuli: {report['solver']['annulus_count']}; loading branch: `{report['solver']['loading_branch']}`
- Polar: analytic proxy, explicitly non-representative
- Qualification: `{report['qualification']}`
- Physical qualification: `false`

{report['scope']}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = build_report(args.fixture)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.markdown.write_text(render_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
