"""Generate PR-10 experiment-contract software evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from pyfoldable.core import (
    CalibrationIdentity,
    ExperimentPolicy,
    ExperimentRun,
    ExperimentSample,
    TestStandManifest,
    assess_experiment_bundle,
    load_rotor_benchmark_fixture,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = PROJECT_ROOT / "reports" / "pr10_experiment_contract_evidence.json"
DEFAULT_MARKDOWN = PROJECT_ROOT / "reports" / "pr10_experiment_contract_evidence.md"
PUBLIC_BASELINE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "rotor_benchmark"
    / "uiuc_apcsf_10x4.7_v1.json"
)
UNITS = {
    "thrust": "N", "torque": "N*m", "rpm": "rpm", "voltage": "V",
    "current": "A", "temperature": "K", "pressure": "Pa",
}


def _manifest() -> TestStandManifest:
    return TestStandManifest(
        id="pr10-synthetic-test-stand-v1",
        calibrations=tuple(
            CalibrationIdentity(
                f"fixture-{quantity}", quantity, unit, f"fixture-cert-{quantity}",
                "c" * 64, "2026-01-01", "2027-01-01",
                0.01 if quantity in {"thrust", "torque"} else 0.1,
                "software_fixture_not_calibration_evidence",
            )
            for quantity, unit in UNITS.items()
        ),
        policy=ExperimentPolicy(
            minimum_repeats=3,
            maximum_zero_drift={"thrust": 0.05, "torque": 0.01},
            coverage_factor=2.0,
        ),
    )


def _run(role: str, run_id: str, thrust_offset: float) -> ExperimentRun:
    design_id = f"synthetic-{role}"
    samples = tuple(
        ExperimentSample(
            run_id, role, design_id, repeat, 0, float(repeat),
            8.0 + thrust_offset + 0.1 * repeat,
            0.12 + 0.001 * repeat,
            7000.0 + 5.0 * repeat,
            11.1, 12.0 + 0.1 * repeat, 295.0, 101_000.0,
        )
        for repeat in range(3)
    )
    return ExperimentRun(
        run_id, role, design_id, "2026-08-24", "d" * 64,
        {"thrust": 0.0, "torque": 0.0},
        {"thrust": 0.02, "torque": 0.002}, samples,
    )


def build_report() -> Mapping[str, Any]:
    manifest = _manifest()
    runs = (
        _run("fixed_reference", "fixed-fixture-1", 0.0),
        _run("foldable", "foldable-fixture-1", 0.5),
    )
    decision = assess_experiment_bundle(manifest, runs)
    baseline = load_rotor_benchmark_fixture(PUBLIC_BASELINE)
    return {
        "manifest": dict(manifest.as_mapping()),
        "software_fixture_decision": dict(decision.as_mapping()),
        "public_baseline_context": {
            "evidence_class": "published_external_baseline",
            "qualification_scope": "model_validation_context_only",
            "physical_qualification": False,
            "fixture_id": baseline.id,
            "fixture_sha256": baseline.source_sha256,
            "target_geometry": "APC Slow Flyer 10x4.7",
            "point_count": len(baseline.points),
            "eligible_point_count": len(baseline.eligible_points),
            "regime_counts": {
                "static": sum(point.regime == "static" for point in baseline.points),
                "forward": sum(point.regime == "forward" for point in baseline.points),
            },
            "quantities": ["CT", "CP", "J", "rpm"],
            "sources": [dict(source) for source in baseline.sources],
            "archive_identity": {
                "url": "https://m-selig.ae.illinois.edu/props/download/UIUC-propDB.zip",
                "published_md5": "a41e484f1fd0fb6ff80b76e27410808b",
            },
            "published_campaign_uncertainty_percent": {
                "source": (
                    "https://m-selig.ae.illinois.edu/props/volume-1/"
                    "Brandt_2005_UIUC-MS-Thesis.pdf"
                ),
                "efficiency": 0.595,
                "power": 0.240,
                "rpm": 0.100,
                "thrust": 0.504,
                "torque": 0.218,
                "freestream_velocity": 0.207,
                "scope": "campaign-level apparatus estimate, not per-point error bars",
            },
            "source_access_policy": "url_and_digest_only_no_raw_redistribution",
            "limitations": [
                "no_run_specific_atmosphere",
                "no_raw_sensor_stream",
                "no_calibration_certificates",
                "no_project_foldable_measurements",
                "do_not_convert_coefficients_to_si_loads_using_assumed_atmosphere",
            ],
        },
        "measurement_method_foundation": [
            {
                "id": "morgado-pascoa-2015-apc-10x4.7sf",
                "evidence_class": "independent_same_prop_dynamic_reference",
                "qualification_scope": "method_and_cross_laboratory_context_only",
                "url": "https://www.naun.org/main/NAUN/mechanics/2015/a372003-136.pdf",
                "extracted_precedent": {
                    "rpm": [4000, 5000],
                    "sample_rate_hz": 8,
                    "samples_per_point": 400,
                    "window_seconds": 50,
                    "sample_convergence_observed_above": 200,
                    "in_situ_check_loads": ["thrust", "torque", "combined"],
                },
                "limitations": [
                    "not_project_specific_measurement",
                    "reported_other_propeller_uncertainty_not_transferred",
                ],
            },
            {
                "id": "nist-tn-1297",
                "evidence_class": "measurement_uncertainty_guidance",
                "qualification_scope": "type_a_type_b_combination_and_reporting",
                "url": "https://doi.org/10.6028/NIST.TN.1297",
            },
            {
                "id": "astm-e74-e2428-static-boundary",
                "evidence_class": "static_calibration_standard",
                "qualification_scope": "force_and_torque_traceability_only",
                "urls": [
                    "https://store.astm.org/e0074-18r26.html",
                    "https://store.astm.org/e2428-22.html",
                ],
                "limitation": "static calibration does not establish dynamic adequacy",
            },
            {
                "id": "propdbtools",
                "evidence_class": "open_source_parser",
                "qualification_scope": "uiuc_format_ingestion_only",
                "url": "https://github.com/ramcdona/PropDBTools",
                "license": "BSD-2-Clause",
                "limitation": "parser license does not relicense UIUC data",
            },
        ],
        "project_readiness": {
            "state": "blocked_waiting_for_calibrated_raw_measurements",
            "missing_inputs": [
                "test_stand_sensor_certificates_and_sha256",
                "pre_and_post_run_zero_records",
                "fixed_reference_raw_repeated_measurements",
                "foldable_prototype_raw_repeated_measurements",
                "environmental_measurements",
                "approved_experiment_acceptance_limits",
            ],
            "physical_qualification": False,
        },
        "decision": "pr10_software_contract_complete_physical_measurements_pending",
        "scope": (
            "All samples and certificates are first-party software fixtures. "
            "They test data quality and uncertainty math, not propeller performance."
        ),
    }


def _markdown(report: Mapping[str, Any]) -> str:
    decision = report["software_fixture_decision"]
    baseline = report["public_baseline_context"]
    lines = [
        "# PR-10 experiment contract evidence", "",
        f"- Software fixture gate: **{decision['state']}**",
        "- Physical qualification: **pending**",
        f"- Fixture runs: {len(decision['runs'])}",
        "- Real-project readiness: **blocked_waiting_for_calibrated_raw_measurements**",
        "", "## Published external baseline", "",
        f"- Fixture: `{baseline['fixture_id']}`",
        f"- Points: {baseline['point_count']} total / {baseline['eligible_point_count']} propulsive",
        "- Quantities: CT, CP, J, rpm (no assumed conversion to T/Q)",
        "- Qualification scope: **model validation context only**",
        "- Physical qualification: **false**",
        "", "## Missing real inputs", "",
    ]
    lines.extend(
        f"- `{item}`" for item in report["project_readiness"]["missing_inputs"]
    )
    lines.extend(("", str(report["scope"]), ""))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = build_report()
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.markdown.write_text(_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
