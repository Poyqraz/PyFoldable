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
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = PROJECT_ROOT / "reports" / "pr10_experiment_contract_evidence.json"
DEFAULT_MARKDOWN = PROJECT_ROOT / "reports" / "pr10_experiment_contract_evidence.md"
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
    return {
        "manifest": dict(manifest.as_mapping()),
        "software_fixture_decision": dict(decision.as_mapping()),
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
    lines = [
        "# PR-10 experiment contract evidence", "",
        f"- Software fixture gate: **{decision['state']}**",
        "- Physical qualification: **pending**",
        f"- Fixture runs: {len(decision['runs'])}",
        "- Real-project readiness: **blocked_waiting_for_calibrated_raw_measurements**",
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
