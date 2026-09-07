"""PY-06C motor/rotor correlation contract."""

from __future__ import annotations

import dataclasses
import math

import pytest

import pyfoldable.core as core
from pyfoldable.core.experiment_contract import (
    CalibrationIdentity,
    ExperimentBundleDecision,
    ExperimentPolicy,
    ExperimentRunDecision,
    ExperimentSummary,
    TestStandManifest,
    UncertaintyMetric,
    canonical_experiment_summary_sha256,
    canonical_test_stand_manifest_sha256,
)
from pyfoldable.core.motor_bem_coupling import (
    AeroLoadSample,
    CoupledSolverSettings,
    canonical_coupled_operating_point_sha256,
    solve_coupled_operating_point,
)
from pyfoldable.core.motor_rotor_correlation import (
    MotorDynamometerEvidence,
    MotorRotorCorrelationError,
    MotorRotorCorrelationPolicy,
    MotorRotorRunContext,
    assess_motor_rotor_correlation,
    canonical_motor_dynamometer_evidence_sha256,
)
from pythrust.propulsion.models import BatterySpec, MotorSpec, SystemSpec


UNITS = {
    "thrust": "N", "torque": "N*m", "rpm": "rpm", "voltage": "V",
    "current": "A", "temperature": "K", "pressure": "Pa",
}
DYNAMOMETER_UNITS = {
    "torque": "N*m", "rpm": "rpm", "voltage": "V", "current": "A",
    "temperature": "K", "pressure": "Pa",
}


def _metric(mean: float, u: float, unit: str, calibration: float) -> UncertaintyMetric:
    type_a = math.sqrt(max(0.0, u * u - calibration * calibration))
    return UncertaintyMetric(mean, type_a, calibration, 0.0, u, 2.0 * u, unit)


def _manifest() -> TestStandManifest:
    return TestStandManifest(
        "stand-v1",
        tuple(
            CalibrationIdentity(
                f"stand-{name}", name, unit, f"cert-{name}", "a" * 64,
                "2026-01-01", "2027-01-01",
                0.01 if name in {"thrust", "torque"} else 0.1,
                "software_fixture_not_calibration_evidence",
            )
            for name, unit in UNITS.items()
        ),
        ExperimentPolicy(3, {"thrust": 0.05, "torque": 0.01}, 2.0),
    )


def _summary(rpm: float, voltage: float, current: float, torque: float) -> ExperimentSummary:
    direct = {
        "thrust": _metric(5.0, 0.02, "N", 0.01),
        "torque": _metric(torque, 0.01, "N*m", 0.01),
        "rpm": _metric(rpm, 1.0, "rpm", 0.1),
        "voltage": _metric(voltage, 0.2, "V", 0.1),
        "current": _metric(current, 0.2, "A", 0.1),
        "temperature": _metric(295.0, 0.2, "K", 0.1),
        "pressure": _metric(101000.0, 10.0, "Pa", 0.1),
    }
    power_type_a = math.hypot(
        current * direct["voltage"].standard_uncertainty_type_a,
        voltage * direct["current"].standard_uncertainty_type_a,
    )
    power_cal = math.hypot(current * 0.1, voltage * 0.1)
    power_u = math.hypot(power_type_a, power_cal)
    return ExperimentSummary("run-1", "foldable", 3, {
        **direct,
        "electrical_power": UncertaintyMetric(
            voltage * current, power_type_a, power_cal, 0.0,
            power_u, 2.0 * power_u, "W",
        ),
    })


def _point(throttle: float = 0.7):
    motor = MotorSpec(1000.0, 0.05, 1.0, 50.0)
    battery = BatterySpec(12.0, 0.5)  # Deliberately irrelevant to motor efficiency.
    system = SystemSpec(0.01)

    def load(rpm: float) -> AeroLoadSample:
        torque = 0.02 + 1e-9 * rpm * rpm
        return AeroLoadSample(
            rpm, 2e-7 * rpm * rpm, torque, torque * rpm * math.pi / 30.0,
            "bem-fixture", "software_fixture",
        )

    return solve_coupled_operating_point(
        motor=motor, battery=battery, system=system, throttle=throttle,
        aero_load=load,
        settings=CoupledSolverSettings(rpm_min=100.0, rpm_max=12000.0 * throttle),
    )


def _bundle(point=None) -> tuple[TestStandManifest, ExperimentBundleDecision]:
    point = point or _point()
    summary = _summary(
        point.rpm, point.motor_state.applied_voltage_v,
        point.motor_state.current_a, point.aero.torque_nm,
    )
    manifest = _manifest()
    decision = ExperimentBundleDecision(
        manifest.id,
        (ExperimentRunDecision(
            "run-1", (), "b" * 64, "design-foldable", "2026-08-24",
            canonical_experiment_summary_sha256(summary),
        ),),
        (summary,),
        ("fixed_reference",),
        canonical_test_stand_manifest_sha256(manifest),
    )
    return manifest, decision


def _context(point=None, **changes) -> MotorRotorRunContext:
    point = point or _point()
    values = dict(
        run_id="run-1", expected_role="foldable", design_id="design-foldable",
        run_open_diameter_m=0.25, run_forward_speed_m_s=0.0,
        torque_channel="rotor_shaft_torque",
        motor_id="motor-x", motor_serial="motor-serial-x", esc_id="esc-x",
        dc_power_measurement_location="motor_terminal_dc_input",
        pr07_source_id=point.aero.source_id, pr07_source_sha256="c" * 64,
        pr07_case_sha256=canonical_coupled_operating_point_sha256(point),
        pr07_design_id="design-foldable", pr07_open_diameter_m=0.25,
        pr07_forward_speed_m_s=0.0,
        pr07_dc_power_location="motor_terminal_dc_input",
        pr07_temperature_k=295.0, pr07_pressure_pa=101000.0,
        source="source-bound software fixture", classification="software_fixture",
    )
    values.update(changes)
    return MotorRotorRunContext(**values)


def _dynamometer(point=None, **changes) -> MotorDynamometerEvidence:
    point = point or _point()
    values = dict(
        evidence_id="dyno-1", motor_id="motor-x", motor_serial="motor-serial-x",
        esc_id="esc-x", experiment_date="2026-08-24", raw_data_sha256="d" * 64,
        summary_sha256="0" * 64,
        calibrations=tuple(
            CalibrationIdentity(
                f"dyno-{name}", name, unit, f"dyno-cert-{name}", "e" * 64,
                "2026-01-01", "2027-01-01", 0.01 if name == "torque" else 0.1,
                "software_fixture_not_calibration_evidence",
            )
            for name, unit in DYNAMOMETER_UNITS.items()
        ),
        metrics={
            "torque": _metric(point.aero.torque_nm, 0.01, "N*m", 0.01),
            "rpm": _metric(point.rpm, 1.0, "rpm", 0.1),
            "voltage": _metric(point.motor_state.applied_voltage_v, 0.2, "V", 0.1),
            "current": _metric(point.motor_state.current_a, 0.2, "A", 0.1),
            "temperature": _metric(295.0, 0.2, "K", 0.1),
            "pressure": _metric(101000.0, 10.0, "Pa", 0.1),
        },
        coverage_factor=2.0,
        dc_power_measurement_location="motor_terminal_dc_input",
        source="independent dynamometer software fixture",
        classification="software_fixture",
    )
    values.update(changes)
    evidence = MotorDynamometerEvidence(**values)
    if "summary_sha256" not in changes:
        evidence = dataclasses.replace(
            evidence,
            summary_sha256=canonical_motor_dynamometer_evidence_sha256(evidence),
        )
    return evidence


def _rehash_dynamometer(evidence: MotorDynamometerEvidence) -> MotorDynamometerEvidence:
    return dataclasses.replace(
        evidence,
        summary_sha256=canonical_motor_dynamometer_evidence_sha256(evidence),
    )


def _policy(**changes) -> MotorRotorCorrelationPolicy:
    values = dict(
        maximum_rpm_relative_delta=0.01, maximum_voltage_delta_v=0.5,
        maximum_current_delta_a=0.5, maximum_temperature_delta_k=2.0,
        maximum_pressure_delta_pa=1000.0, maximum_diameter_delta_m=1e-6,
        maximum_forward_speed_delta_m_s=0.1, coverage_factor=2.0,
        dyno_voltage_current_correlation=0.0, dyno_torque_rpm_correlation=0.0,
        measured_torque_rpm_correlation=0.0,
        dyno_shaft_dc_power_correlation=0.0,
        dyno_measured_shaft_power_correlation=0.0,
        dyno_measured_torque_correlation=0.0,
    )
    values.update(changes)
    return MotorRotorCorrelationPolicy(**values)


def test_missing_dynamometer_evidence_blocks_without_metrics() -> None:
    point = _point()
    manifest, decision = _bundle(point)
    result = assess_motor_rotor_correlation(
        manifest, decision, _context(point), point, None, _policy()
    )
    assert result.state == "blocked_missing_independent_motor_evidence"
    assert result.metrics == {}
    assert not result.physical_qualification
    assert not result.target_fitting_performed


def test_complete_fixture_derives_power_efficiency_and_residual_intervals() -> None:
    point = _point()
    manifest, decision = _bundle(point)
    result = assess_motor_rotor_correlation(
        manifest, decision, _context(point), point, _dynamometer(point), _policy()
    )
    assert result.state == "screening_motor_rotor_correlation_complete_physical_evidence_pending"
    assert all(result.condition_matches.values())
    omega = point.rpm * math.pi / 30.0
    assert result.derived["dynamometer_dc_input_power_w"] == pytest.approx(
        point.motor_state.applied_voltage_v * point.motor_state.current_a
    )
    assert result.derived["dynamometer_shaft_power_w"] == pytest.approx(
        point.aero.torque_nm * omega
    )
    expected_dc_u = math.hypot(
        point.motor_state.current_a * 0.2,
        point.motor_state.applied_voltage_v * 0.2,
    )
    assert result.derived[
        "dynamometer_dc_input_power_standard_uncertainty_w"
    ] == pytest.approx(expected_dc_u)
    expected_shaft_u = math.hypot(point.rpm * math.pi / 30.0 * 0.01,
                                  point.aero.torque_nm * math.pi / 30.0)
    assert result.derived[
        "dynamometer_shaft_power_standard_uncertainty_w"
    ] == pytest.approx(expected_shaft_u)
    assert result.derived[
        "dynamometer_efficiency_expanded_uncertainty"
    ] == pytest.approx(
        2.0 * result.derived["dynamometer_efficiency_standard_uncertainty"]
    )
    assert result.derived["dynamometer_efficiency"] != pytest.approx(
        point.battery.discharge_efficiency
    )
    assert result.metrics["dynamometer_vs_rotor_torque"].residual == pytest.approx(0.0)
    expected_torque_residual_u = math.hypot(0.01, 0.01)
    assert result.metrics[
        "dynamometer_vs_rotor_torque"
    ].standard_uncertainty_residual == pytest.approx(expected_torque_residual_u)
    assert result.metrics[
        "dynamometer_vs_rotor_torque"
    ].residual_interval_lower == pytest.approx(-2.0 * expected_torque_residual_u)
    assert result.metrics["dynamometer_vs_rotor_shaft_power"].residual == pytest.approx(0.0)
    assert result.metrics["pr07_vs_experiment_dc_power"].decision == (
        "screening_indeterminate_missing_model_uncertainty"
    )
    assert result.dynamometer_identity["calibration_torque_certificate_sha256"] == "e" * 64
    assert result.as_mapping()["qualification"] == "screening_only"


@pytest.mark.parametrize(
    ("context_changes", "dyno_changes"),
    [
        ({"dc_power_measurement_location": "battery_bus_dc_input"}, {}),
        ({"pr07_dc_power_location": "esc_input"}, {}),
        ({"motor_serial": "other"}, {}),
        ({}, {"esc_id": "other"}),
    ],
)
def test_identity_or_power_boundary_mismatch_blocks(context_changes, dyno_changes) -> None:
    point = _point()
    manifest, decision = _bundle(point)
    result = assess_motor_rotor_correlation(
        manifest, decision, _context(point, **context_changes), point,
        _dynamometer(point, **dyno_changes), _policy(),
    )
    assert result.state == "blocked_unmatched_motor_rotor_conditions"
    assert result.metrics == {}


def test_torque_channel_substitutions_are_rejected() -> None:
    point = _point()
    for channel in ("hinge_axis_torque", "generic_torque"):
        with pytest.raises(ValueError, match="rotor_shaft_torque"):
            _context(point, torque_channel=channel)


@pytest.mark.parametrize(
    "context_changes",
    [
        {"pr07_design_id": "other-design"},
        {"pr07_open_diameter_m": 0.249},
        {"pr07_forward_speed_m_s": 1.0},
    ],
)
def test_pr07_geometry_and_flight_condition_mismatch_blocks(context_changes) -> None:
    point = _point()
    manifest, decision = _bundle(point)
    result = assess_motor_rotor_correlation(
        manifest, decision, _context(point, **context_changes), point,
        _dynamometer(point), _policy(),
    )
    assert result.state == "blocked_unmatched_motor_rotor_conditions"
    assert result.metrics == {}


@pytest.mark.parametrize("field", ["applied_voltage_v", "current_a"])
def test_pr07_motor_state_equation_tampering_is_rejected(field) -> None:
    point = _point()
    changed = getattr(point.motor_state, field) + 0.6
    state = dataclasses.replace(point.motor_state, **{field: changed})
    state = dataclasses.replace(
        state,
        electrical_input_power_w=state.applied_voltage_v * state.current_a,
    )
    forged = dataclasses.replace(point, motor_state=state)
    manifest, decision = _bundle(point)
    context = _context(
        point, pr07_case_sha256=canonical_coupled_operating_point_sha256(forged)
    )
    with pytest.raises(MotorRotorCorrelationError, match="PR-07"):
        assess_motor_rotor_correlation(
            manifest, decision, context, forged, _dynamometer(point), _policy()
        )


def test_valid_but_electrically_unmatched_pr07_point_is_blocked() -> None:
    measured_point = _point(0.7)
    other_point = _point(0.76)
    manifest, decision = _bundle(measured_point)
    result = assess_motor_rotor_correlation(
        manifest, decision, _context(other_point), other_point,
        _dynamometer(measured_point), _policy(),
    )
    assert result.state == "blocked_unmatched_motor_rotor_conditions"
    assert not result.condition_matches["pr07_voltage"]
    assert result.metrics == {}


def test_outside_condition_tolerance_blocks_but_boundary_is_inclusive() -> None:
    point = _point()
    manifest, decision = _bundle(point)
    boundary = _dynamometer(point)
    boundary = _rehash_dynamometer(dataclasses.replace(
        boundary,
        metrics={
            **boundary.metrics,
            "voltage": _metric(
                point.motor_state.applied_voltage_v + 0.5, 0.2, "V", 0.1
            ),
        },
    ))
    accepted = assess_motor_rotor_correlation(
        manifest, decision, _context(point), point, boundary, _policy()
    )
    assert accepted.condition_matches["voltage"]
    rejected = _rehash_dynamometer(dataclasses.replace(
        boundary,
        metrics={
            **boundary.metrics,
            "voltage": _metric(
                point.motor_state.applied_voltage_v + 0.5001, 0.2, "V", 0.1
            ),
        },
    ))
    blocked = assess_motor_rotor_correlation(
        manifest, decision, _context(point), point, rejected, _policy()
    )
    assert not blocked.condition_matches["voltage"]
    assert blocked.metrics == {}


def test_tampered_pr07_case_is_rejected_even_with_recomputed_digest() -> None:
    point = _point()
    forged = dataclasses.replace(
        point,
        motor_state=dataclasses.replace(
            point.motor_state, shaft_power_w=point.motor_state.shaft_power_w + 1.0
        ),
    )
    manifest, decision = _bundle(point)
    context = _context(
        point, pr07_case_sha256=canonical_coupled_operating_point_sha256(forged)
    )
    with pytest.raises(MotorRotorCorrelationError, match="PR-07.*shaft power"):
        assess_motor_rotor_correlation(
            manifest, decision, context, forged, _dynamometer(point), _policy()
        )


def test_pr07_digest_mismatch_and_substitute_dynamometer_channels_fail_closed() -> None:
    point = _point()
    manifest, decision = _bundle(point)
    with pytest.raises(MotorRotorCorrelationError, match="digest"):
        assess_motor_rotor_correlation(
            manifest, decision, _context(point, pr07_case_sha256="f" * 64),
            point, _dynamometer(point), _policy(),
        )
    dyno = _dynamometer(point)
    for replacement in ("hinge_torque", "manufacturer_motor_efficiency"):
        metrics = dict(dyno.metrics)
        metrics[replacement] = metrics.pop("torque")
        with pytest.raises(MotorRotorCorrelationError, match="metric keys"):
            assess_motor_rotor_correlation(
                manifest, decision, _context(point), point,
                _rehash_dynamometer(dataclasses.replace(dyno, metrics=metrics)),
                _policy(),
            )


def test_dynamometer_calibration_and_uncertainty_tampering_fails_closed() -> None:
    point = _point()
    manifest, decision = _bundle(point)
    dyno = _dynamometer(point)
    expired = _rehash_dynamometer(
        dataclasses.replace(dyno, experiment_date="2030-01-01")
    )
    with pytest.raises(MotorRotorCorrelationError, match="calibration.*date"):
        assess_motor_rotor_correlation(
            manifest, decision, _context(point), point, expired, _policy()
        )
    bad_torque = dataclasses.replace(
        dyno.metrics["torque"], combined_standard_uncertainty=0.3
    )
    malformed = _rehash_dynamometer(dataclasses.replace(
        dyno, metrics={**dyno.metrics, "torque": bad_torque}
    ))
    with pytest.raises(MotorRotorCorrelationError, match="combined"):
        assess_motor_rotor_correlation(
            manifest, decision, _context(point), point, malformed, _policy()
        )
    forged_summary = dataclasses.replace(
        dyno,
        metrics={
            **dyno.metrics,
            "torque": _metric(point.aero.torque_nm + 0.01, 0.01, "N*m", 0.01),
        },
    )
    with pytest.raises(MotorRotorCorrelationError, match="summary digest"):
        assess_motor_rotor_correlation(
            manifest, decision, _context(point), point, forged_summary, _policy()
        )


@pytest.mark.parametrize("bad_mean", [True, -1.0, float("nan"), float("inf")])
def test_invalid_dynamometer_scalars_fail_controlled(bad_mean) -> None:
    point = _point()
    manifest, decision = _bundle(point)
    dyno = _dynamometer(point)
    bad = dataclasses.replace(dyno.metrics["rpm"], mean=bad_mean)
    candidate = dataclasses.replace(dyno, metrics={**dyno.metrics, "rpm": bad})
    if isinstance(bad_mean, bool) or (isinstance(bad_mean, float) and math.isfinite(bad_mean)):
        candidate = _rehash_dynamometer(candidate)
    with pytest.raises(MotorRotorCorrelationError, match="rpm|canonically"):
        assess_motor_rotor_correlation(
            manifest, decision, _context(point), point,
            candidate, _policy(),
        )


def test_policy_and_result_collections_are_immutable_and_public() -> None:
    with pytest.raises(ValueError, match="correlation"):
        _policy(dyno_voltage_current_correlation=1.01)
    point = _point()
    manifest, decision = _bundle(point)
    result = assess_motor_rotor_correlation(
        manifest, decision, _context(point), point, _dynamometer(point), _policy()
    )
    with pytest.raises(TypeError):
        result.metrics["x"] = result.metrics["dynamometer_vs_rotor_torque"]
    reconstructed = dataclasses.replace(result, metrics=dict(result.metrics))
    with pytest.raises(TypeError):
        reconstructed.metrics["x"] = reconstructed.metrics[
            "dynamometer_vs_rotor_torque"
        ]
    assert core.MotorRotorRunContext is MotorRotorRunContext
    namespace = {}
    exec("from pyfoldable.core import *", {}, namespace)
    assert {
        "MotorDynamometerEvidence", "MotorRotorCorrelationError",
        "MotorRotorCorrelationPolicy", "MotorRotorRunContext",
        "assess_motor_rotor_correlation",
        "canonical_motor_dynamometer_evidence_sha256",
    }.issubset(namespace)


def test_extreme_uncertainty_overflow_fails_instead_of_collapsing_to_zero() -> None:
    point = _point()
    manifest, decision = _bundle(point)
    dyno = _dynamometer(point)
    huge = dataclasses.replace(
        dyno.metrics["voltage"],
        standard_uncertainty_type_a=1e308,
        combined_standard_uncertainty=1e308,
        expanded_uncertainty=1e308,
    )
    malformed = _rehash_dynamometer(dataclasses.replace(
        dyno, metrics={**dyno.metrics, "voltage": huge}
    ))
    with pytest.raises(MotorRotorCorrelationError, match="finite|overflow|expanded"):
        assess_motor_rotor_correlation(
            manifest, decision, _context(point), point, malformed, _policy()
        )
