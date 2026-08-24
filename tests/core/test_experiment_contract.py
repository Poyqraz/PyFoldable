"""PR-10 test-first experiment, calibration, and uncertainty contract."""

from __future__ import annotations

import pytest

from pyfoldable.core.experiment_contract import (
    CalibrationIdentity,
    ExperimentPolicy,
    ExperimentRun,
    ExperimentSample,
    TestStandManifest,
    assess_experiment_bundle,
)


SHA = "c" * 64
UNITS = {
    "thrust": "N", "torque": "N*m", "rpm": "rpm", "voltage": "V",
    "current": "A", "temperature": "K", "pressure": "Pa",
}


def _manifest() -> TestStandManifest:
    calibrations = tuple(
        CalibrationIdentity(
            sensor_id=f"sensor-{quantity}", quantity=quantity, unit=unit,
            certificate_id=f"cert-{quantity}-v1", certificate_sha256=SHA,
            valid_from="2026-01-01", valid_until="2027-01-01",
            standard_uncertainty=0.01 if quantity in {"thrust", "torque"} else 0.1,
            qualification="software_fixture_not_calibration_evidence",
        )
        for quantity, unit in UNITS.items()
    )
    return TestStandManifest(
        id="stand-fixture-v1",
        calibrations=calibrations,
        policy=ExperimentPolicy(
            minimum_repeats=3,
            maximum_zero_drift={"thrust": 0.05, "torque": 0.01},
            coverage_factor=2.0,
        ),
    )


def _run(role: str, run_id: str, offset: float = 0.0, **changes) -> ExperimentRun:
    samples = tuple(
        ExperimentSample(
            run_id=run_id, role=role, design_id=f"design-{role}",
            repeat_index=index, sample_index=0, timestamp_s=float(index),
            thrust_n=8.0 + offset + index * 0.1,
            torque_nm=0.12 + offset * 0.01 + index * 0.001,
            rpm=7000.0 + index * 5.0, voltage_v=11.1,
            current_a=12.0 + index * 0.1, temperature_k=295.0,
            pressure_pa=101_000.0,
        )
        for index in range(3)
    )
    values = dict(
        id=run_id, role=role, design_id=f"design-{role}",
        experiment_date="2026-08-24", raw_data_sha256="d" * 64,
        zero_before={"thrust": 0.0, "torque": 0.0},
        zero_after={"thrust": 0.02, "torque": 0.002}, samples=samples,
    )
    values.update(changes)
    return ExperimentRun(**values)


def test_complete_fixed_and_foldable_bundle_passes_software_gate() -> None:
    decision = assess_experiment_bundle(
        _manifest(),
        (_run("fixed_reference", "fixed-1"), _run("foldable", "fold-1", 0.5)),
    )
    assert decision.software_gate_passed
    assert not decision.physical_qualification
    assert decision.state == "software_pass_physical_measurements_pending"
    assert len(decision.summaries) == 2
    thrust = decision.summaries[0].metrics["thrust"]
    assert thrust.expanded_uncertainty > thrust.standard_uncertainty_calibration
    power = decision.summaries[0].metrics["electrical_power"]
    assert power.mean == pytest.approx(11.1 * 12.1)
    assert power.unit == "W"


def test_missing_role_repeats_and_zero_drift_fail_closed() -> None:
    missing = assess_experiment_bundle(_manifest(), (_run("fixed_reference", "f"),))
    assert not missing.software_gate_passed
    assert missing.missing_roles == ("foldable",)

    short = _run(
        "foldable", "short",
        samples=_run("foldable", "short").samples[:2],
    )
    repeats = assess_experiment_bundle(
        _manifest(), (_run("fixed_reference", "f"), short)
    )
    assert "repeat_count_below_minimum" in repeats.runs[1].failures

    drifted = _run(
        "foldable", "drift",
        zero_after={"thrust": 0.2, "torque": 0.002},
    )
    drift = assess_experiment_bundle(
        _manifest(), (_run("fixed_reference", "f"), drifted)
    )
    assert "zero_drift_above_limit:thrust" in drift.runs[1].failures


def test_expired_calibration_blocks_every_run() -> None:
    manifest = _manifest()
    expired = CalibrationIdentity(
        sensor_id="expired-thrust", quantity="thrust", unit="N",
        certificate_id="old", certificate_sha256=SHA,
        valid_from="2025-01-01", valid_until="2025-12-31",
        standard_uncertainty=0.01, qualification="expired-fixture",
    )
    manifest = TestStandManifest(
        id="expired",
        calibrations=(expired,) + manifest.calibrations[1:],
        policy=manifest.policy,
    )
    decision = assess_experiment_bundle(
        manifest,
        (_run("fixed_reference", "f"), _run("foldable", "g")),
    )
    assert not decision.software_gate_passed
    assert "calibration_invalid_on_experiment_date:thrust" in decision.runs[0].failures


def test_duplicate_sample_identity_is_rejected() -> None:
    run = _run("fixed_reference", "dup")
    with pytest.raises(ValueError, match="unique"):
        ExperimentRun(
            id=run.id, role=run.role, design_id=run.design_id,
            experiment_date=run.experiment_date, raw_data_sha256=run.raw_data_sha256,
            zero_before=run.zero_before, zero_after=run.zero_after,
            samples=(run.samples[0], run.samples[0]),
        )


def test_manifest_requires_all_channels_with_exact_units() -> None:
    with pytest.raises(ValueError, match="required calibration"):
        TestStandManifest(
            id="incomplete",
            calibrations=_manifest().calibrations[:-1],
            policy=_manifest().policy,
        )

    wrong = list(_manifest().calibrations)
    wrong[0] = CalibrationIdentity(
        sensor_id="wrong", quantity="thrust", unit="kgf",
        certificate_id="wrong", certificate_sha256=SHA,
        valid_from="2026-01-01", valid_until="2027-01-01",
        standard_uncertainty=0.01, qualification="fixture",
    )
    with pytest.raises(ValueError, match="unit"):
        TestStandManifest("wrong-unit", tuple(wrong), _manifest().policy)
