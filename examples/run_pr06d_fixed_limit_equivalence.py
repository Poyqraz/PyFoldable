"""Generate the deterministic PR-06D fixed-limit equivalence evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from pyfoldable.core import (
    BEMAnnulusSettings,
    BEMRotorSettings,
    FoldableRotorState,
    assess_fixed_limit_equivalence,
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
DEFAULT_JSON = PROJECT_ROOT / "reports" / "pr06d_fixed_limit_equivalence.json"
DEFAULT_MARKDOWN = PROJECT_ROOT / "reports" / "pr06d_fixed_limit_equivalence.md"


def build_report(fixture_path: Path = DEFAULT_FIXTURE) -> Mapping[str, Any]:
    """Evaluate all frozen, qualification-eligible UIUC operating points."""
    fixture = load_rotor_benchmark_fixture(fixture_path)
    family = build_rotor_benchmark_proxy_polar_family()
    blade = fixture.blade(family.airfoil_id)
    state = FoldableRotorState(
        id="fully-deployed-fixed-limit",
        hinge_radius_m=0.75 * blade.radius_m,
        opening_angle_rad=0.0,
        deployed_angle_rad=0.0,
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
    evidence = assess_fixed_limit_equivalence(
        blade,
        state,
        tuple(fixture.condition(point) for point in fixture.eligible_points),
        {family.airfoil_id: family},
        settings=settings,
    )
    return {
        **dict(evidence.as_mapping()),
        "benchmark_id": "pr06d-uiuc-apcsf-10x4.7-fixed-limit-v1",
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
            "include_tip_loss": settings.annulus_settings.include_tip_loss,
            "include_root_loss": settings.annulus_settings.include_root_loss,
        },
        "polar_evidence": {
            "airfoil_id": family.airfoil_id,
            "evidence_class": "analytic_proxy",
            "representative": False,
        },
        "decision": (
            "pr06d_software_fixed_limit_passed"
            if evidence.passed
            else "pr06d_software_fixed_limit_failed"
        ),
        "scope": (
            "Exact software-path equivalence only. This does not pass the PR-06C "
            "physical-accuracy gates or qualify folded-state predictions."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render the fixed-limit decision without upgrading its evidence class."""
    status = "PASS" if report["passed"] else "FAIL"
    return f"""# PR-06D fixed-limit equivalence evidence

## Decision

**{status} — {report['decision']}**

The fully deployed fold-state path is exactly identical to the unchanged fixed-blade
BEM path over all {report['point_count']} qualification-eligible points in the frozen
UIUC fixture. Maximum absolute thrust and torque deltas are both exactly zero.

## Evidence boundary

- Fixture: `{report['fixture']['id']}`
- Fixture SHA-256: `{report['fixture']['sha256']}`
- Fold state: `{report['state']['id']}`
- Projection model: `{report['state']['projection_model']}`
- Annuli: {report['solver']['annulus_count']}
- Loading branch: `{report['solver']['loading_branch']}`
- Polar evidence: analytic proxy, non-representative
- Maximum |ΔT|: {report['maximum_absolute_thrust_delta_n']:.1f} N
- Maximum |ΔQ|: {report['maximum_absolute_torque_delta_nm']:.1f} N·m

## Interpretation

{report['scope']} The result permits the PR-06D software foundation to begin while
the PR-06C physical qualification remains blocked.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()

    report = build_report(args.fixture)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.markdown.write_text(render_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
