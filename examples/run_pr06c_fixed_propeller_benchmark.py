"""Generate the deterministic PR-06C fixed-propeller benchmark evidence package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from pyfoldable.core import (
    BEMAnnulusSettings,
    BEMRotorSettings,
    PolarFamily,
    build_rotor_benchmark_proxy_polar_family,
)
from pyfoldable.core.rotor_benchmark import (
    ROTOR_BENCHMARK_SCHEMA_VERSION,
    RotorBenchmarkPolicy,
    evaluate_rotor_benchmark_variant,
    load_rotor_benchmark_fixture,
    radial_convergence_evidence,
    run_rotor_benchmark_cases,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "rotor_benchmark"
    / "uiuc_apcsf_10x4.7_v1.json"
)
DEFAULT_JSON = PROJECT_ROOT / "reports" / "pr06c_fixed_propeller_benchmark.json"
DEFAULT_MARKDOWN = PROJECT_ROOT / "reports" / "pr06c_fixed_propeller_benchmark.md"


def _polar_contract(family: PolarFamily) -> Mapping[str, Any]:
    table = family.tables[0]
    return {
        "airfoil_id": family.airfoil_id,
        "scenario_id": family.scenario_id,
        "evidence_class": table.metadata["evidence_class"],
        "representative_polar_evidence": False,
        "source": table.source,
        "basis_url": table.metadata["basis_url"],
        "limitation": (
            "APC publishes spanwise geometry but not an exact, qualified polar family "
            "for the tested blade; this declared proxy cannot pass the physical-polar gate."
        ),
    }


def _variant_specs() -> tuple[Mapping[str, Any], ...]:
    return (
        {
            "id": "qprop-signed-tip_proxy-baseline",
            "polar": {},
            "annulus": {
                "include_tip_loss": True,
                "include_root_loss": False,
                "loading_branch": "signed_nonreversed",
            },
        },
        {
            "id": "qprop-signed-tip-prandtl-root_proxy-baseline",
            "polar": {},
            "annulus": {
                "include_tip_loss": True,
                "include_root_loss": True,
                "loading_branch": "signed_nonreversed",
            },
        },
        {
            "id": "qprop-signed-no-loss_proxy-baseline",
            "polar": {},
            "annulus": {
                "include_tip_loss": False,
                "include_root_loss": False,
                "loading_branch": "signed_nonreversed",
            },
        },
        {
            "id": "qprop-signed-tip_proxy-low-drag",
            "polar": {"drag_offset": 0.020, "drag_quadratic": 0.020},
            "annulus": {
                "include_tip_loss": True,
                "include_root_loss": False,
                "loading_branch": "signed_nonreversed",
            },
        },
        {
            "id": "qprop-signed-tip_proxy-higher-camber",
            "polar": {"zero_lift_deg": -5.0},
            "annulus": {
                "include_tip_loss": True,
                "include_root_loss": False,
                "loading_branch": "signed_nonreversed",
            },
        },
        {
            "id": "qprop-positive-only-tip_proxy-historical",
            "polar": {},
            "annulus": {
                "include_tip_loss": True,
                "include_root_loss": False,
                "loading_branch": "positive_only",
            },
        },
    )


def build_report(fixture_path: Path = DEFAULT_FIXTURE) -> Mapping[str, Any]:
    fixture = load_rotor_benchmark_fixture(fixture_path)
    policy = RotorBenchmarkPolicy()
    evaluated: list[Mapping[str, Any]] = []
    convergence_by_variant: dict[str, Mapping[str, Any]] = {}
    for spec in _variant_specs():
        family = build_rotor_benchmark_proxy_polar_family(**spec["polar"])
        annulus = BEMAnnulusSettings(**spec["annulus"])
        settings = BEMRotorSettings(
            annulus_count=80,
            radial_domain="station_span",
            annulus_settings=annulus,
        )
        convergence = radial_convergence_evidence(
            fixture,
            family,
            point_ids=("static-6528", "forward-6512-j0199"),
            annulus_settings=annulus,
        )
        convergence_by_variant[str(spec["id"])] = convergence
        predictions = run_rotor_benchmark_cases(fixture, family, settings=settings)
        evaluated.append(
            evaluate_rotor_benchmark_variant(
                fixture,
                predictions,
                policy,
                variant_id=str(spec["id"]),
                representative_polar_evidence=False,
                radial_terminal_delta=float(
                    convergence["maximum_terminal_relative_delta"]
                ),
                settings=settings,
                polar_contract=_polar_contract(family),
            )
        )

    selected = evaluated[0]
    sensitivity = []
    for variant in evaluated[1:]:
        sensitivity.append(
            {key: value for key, value in variant.items() if key != "predictions"}
        )
    failed_gates = tuple(
        name for name, passed in selected["gates"].items() if not passed
    )
    return {
        "schema_version": ROTOR_BENCHMARK_SCHEMA_VERSION,
        "benchmark_id": "pr06c-uiuc-apcsf-10x4.7-screening-v1",
        "passed": bool(selected["passed"]),
        "decision": (
            "qualified_for_pr06d" if selected["passed"] else "pr06d_blocked"
        ),
        "fixture": {
            "id": fixture.id,
            "path": str(fixture_path.relative_to(PROJECT_ROOT)),
            "sha256": fixture.source_sha256,
            "raw_point_count": len(fixture.points),
            "qualification_point_count": len(fixture.eligible_points),
            "excluded_windmilling_point_count": (
                len(fixture.points) - len(fixture.eligible_points)
            ),
            "sources": [dict(source) for source in fixture.sources],
            "environment_status": (
                "standard atmosphere assumed because run-specific tunnel state is not "
                "encoded in the downloaded coefficient files"
            ),
            "rights_scope": (
                "Third-party factual data; source terms apply and the project license "
                "does not relicense it."
            ),
        },
        "policy": dict(policy.as_mapping()),
        "selected_variant": selected,
        "radial_convergence": convergence_by_variant[selected["variant_id"]],
        "sensitivity_variants": sensitivity,
        "failed_gates": list(failed_gates),
        "evaluation": {
            "numerical_integration": (
                "passes the declared terminal annulus-sensitivity gate"
                if selected["gates"]["radial_convergence"]
                else "fails the declared terminal annulus-sensitivity gate"
            ),
            "physical_accuracy": (
                "not qualified: full-envelope coefficient accuracy and representative "
                "polar evidence fail, so PR-06D remains blocked"
            ),
            "principal_failure_mode": (
                "The signed local branch restores full solution coverage, exposing "
                "large forward-flight model-form/polar error that subset-only metrics hid."
            ),
            "data_interpretation": (
                "No APC performance table is distributed. UIUC measurements are the "
                "attributed physical reference; the bundled first-party synthetic "
                "software fixture is not qualification evidence."
            ),
            "next_required_actions": [
                "reconstruct or obtain the tested blade's spanwise section geometry",
                "generate Reynolds-aware polars with recorded solver confidence and limits",
                "address rotational/model-form error and rerun this unchanged frozen policy",
                "obtain independent aerodynamic review before physical promotion",
            ],
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    selected = report["selected_variant"]
    ct = selected["ct_metrics"]
    cp = selected["cp_metrics"]
    status = {
        gate: "PASS" if passed else "FAIL"
        for gate, passed in selected["gates"].items()
    }
    regime_values = tuple(selected["regime_metrics"].values())
    worst_regime_coverage = min(value["solution_coverage"] for value in regime_values)
    worst_regime_ct = max(value["ct_metrics"]["wmape"] for value in regime_values)
    worst_regime_cp = max(value["cp_metrics"]["wmape"] for value in regime_values)
    rows = [
        "# PR-06C fixed-propeller benchmark result",
        "",
        (
            f"**Decision:** `{report['decision']}` — benchmark pass: "
            f"`{str(report['passed']).lower()}`."
        ),
        "",
        "## Qualification summary",
        "",
        "| Gate | Result | Observed | Limit |",
        "| --- | --- | ---: | ---: |",
        (
            f"| Solution coverage | {status['solution_coverage']} | "
            f"{selected['solution_coverage']:.1%} | "
            f"≥ {report['policy']['minimum_solution_coverage']:.1%} |"
        ),
        (
            f"| CT WMAPE | {status['ct_wmape']} | {ct['wmape']:.2%} | "
            f"≤ {report['policy']['maximum_ct_wmape']:.1%} |"
        ),
        (
            f"| CP WMAPE | {status['cp_wmape']} | {cp['wmape']:.2%} | "
            f"≤ {report['policy']['maximum_cp_wmape']:.1%} |"
        ),
        (
            f"| CT normalized bias | {status['ct_bias']} | "
            f"{ct['normalized_bias']:.2%} | "
            f"±{report['policy']['maximum_absolute_ct_normalized_bias']:.1%} |"
        ),
        (
            f"| CP normalized bias | {status['cp_bias']} | "
            f"{cp['normalized_bias']:.2%} | "
            f"±{report['policy']['maximum_absolute_cp_normalized_bias']:.1%} |"
        ),
        (
            f"| Radial 80→160 delta | {status['radial_convergence']} | "
            f"{selected['radial_terminal_delta']:.3%} | "
            f"≤ {report['policy']['maximum_radial_terminal_delta']:.1%} |"
        ),
        (
            "| Representative polar evidence | "
            f"{status['representative_polar_evidence']} | proxy | required |"
        ),
        (
            "| Every-regime coverage | "
            f"{status['regime_solution_coverage']} | "
            f"{worst_regime_coverage:.1%} | "
            f"≥ {report['policy']['minimum_solution_coverage']:.1%} |"
        ),
        (
            "| Every-regime CT WMAPE | "
            f"{status['regime_ct_wmape']} | "
            f"{worst_regime_ct:.2%} | "
            f"≤ {report['policy']['maximum_ct_wmape']:.1%} |"
        ),
        (
            "| Every-regime CP WMAPE | "
            f"{status['regime_cp_wmape']} | "
            f"{worst_regime_cp:.2%} | "
            f"≤ {report['policy']['maximum_cp_wmape']:.1%} |"
        ),
        "",
        "## Correct interpretation",
        "",
        f"- {report['evaluation']['numerical_integration']}.",
        f"- {report['evaluation']['physical_accuracy']}.",
        f"- Principal failure: {report['evaluation']['principal_failure_mode']}",
        f"- Data boundary: {report['evaluation']['data_interpretation']}",
        "- Timing is telemetry only and is not an acceptance gate.",
        "",
        "## Coverage by regime",
        "",
        "| Regime | Solved | Coverage | CT WMAPE | CP WMAPE |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for regime in ("static", "forward"):
        metrics = selected["regime_metrics"][regime]
        rows.append(
            f"| {regime} | {metrics['successful_point_count']}/"
            f"{metrics['point_count']} | {metrics['solution_coverage']:.1%} | "
            f"{metrics['ct_metrics']['wmape']:.2%} | "
            f"{metrics['cp_metrics']['wmape']:.2%} |"
        )
    rows.extend(
        [
        "",
        "## Evidence scope",
        "",
        f"The frozen fixture contains {report['fixture']['raw_point_count']} measured points; "
        f"{report['fixture']['qualification_point_count']} positive-thrust points are in the "
        f"declared propulsive envelope and {report['fixture']['excluded_windmilling_point_count']} "
        "windmilling points are retained but excluded.",
        "",
        "The geometry is an approximate UIUC digitization. Run-specific tunnel atmosphere is "
        "not present in the coefficient files, so the solver uses a declared standard-atmosphere "
        "assumption. The APC airfoil proxy is intentionally non-qualifying.",
        "",
        "## Required remediation before PR-06D",
        "",
        ]
    )
    rows.extend(
        f"{index}. {action}"
        for index, action in enumerate(
            report["evaluation"]["next_required_actions"], start=1
        )
    )
    rows.extend(
        (
            "",
            "Machine-readable evidence: `reports/pr06c_fixed_propeller_benchmark.json`.",
            "",
        )
    )
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--require-pass", action="store_true")
    arguments = parser.parse_args()
    report = build_report(arguments.fixture)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    arguments.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        f"PR-06C benchmark: {'PASS' if report['passed'] else 'NOT QUALIFIED'}; "
        f"evidence={arguments.output}"
    )
    return 2 if arguments.require_pass and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
