"""PR-07 test-first contract for fully coupled motor/rotor equilibrium."""

from __future__ import annotations

import math

import pytest

from pyfoldable.core.motor_bem_coupling import (
    AeroLoadSample,
    AmbiguousEquilibriumError,
    CoupledEquilibriumEvidence,
    CoupledMultistartCase,
    CoupledSolverSettings,
    InvalidAeroLoadError,
    NoEquilibriumError,
    make_bem_aero_load_callback,
    solve_coupled_operating_point,
)
from pythrust.propulsion.models import BatterySpec, MotorSpec, SystemSpec


MOTOR = MotorSpec(
    kv_rpm_per_v=1000.0,
    resistance_ohm=0.05,
    no_load_current_a=1.0,
    current_max_a=50.0,
)
BATTERY = BatterySpec(voltage_v=12.0, discharge_efficiency=0.98)
SYSTEM = SystemSpec(resistance_ohm=0.01)


def _quadratic_load(rpm: float) -> AeroLoadSample:
    torque = 0.02 + 1.0e-9 * rpm * rpm
    omega = rpm * math.pi / 30.0
    return AeroLoadSample(
        rpm=rpm,
        thrust_n=2.0e-7 * rpm * rpm,
        torque_nm=torque,
        shaft_power_w=torque * omega,
        source_id="analytic-quadratic-v1",
        qualification="software_fixture",
    )


def test_unique_equilibrium_closes_torque_voltage_and_energy() -> None:
    result = solve_coupled_operating_point(
        motor=MOTOR,
        battery=BATTERY,
        system=SYSTEM,
        throttle=0.70,
        aero_load=_quadratic_load,
        settings=CoupledSolverSettings(rpm_min=100.0, rpm_max=8400.0),
    )

    assert result.converged
    assert result.feasible
    assert abs(result.torque_residual_nm) <= result.torque_tolerance_nm
    assert abs(result.voltage_residual_v) <= 1.0e-10
    assert abs(result.energy_residual_w) <= result.energy_tolerance_w
    assert result.aero.source_id == "analytic-quadratic-v1"
    assert result.qualification == "software_only_pending_measured_correlation"


def test_separated_initial_guesses_recover_same_root() -> None:
    settings = CoupledSolverSettings(rpm_min=100.0, rpm_max=8400.0)
    roots = []
    for guess in (300.0, 2500.0, 7000.0, 8300.0):
        result = solve_coupled_operating_point(
            motor=MOTOR,
            battery=BATTERY,
            system=SYSTEM,
            throttle=0.70,
            aero_load=_quadratic_load,
            settings=settings,
            initial_guess_rpm=guess,
        )
        roots.append(result.rpm)
    assert max(roots) - min(roots) <= settings.rpm_tolerance


def test_result_provenance_is_complete_and_json_safe() -> None:
    result = solve_coupled_operating_point(
        motor=MOTOR,
        battery=BATTERY,
        system=SYSTEM,
        throttle=0.70,
        aero_load=_quadratic_load,
    )
    payload = result.as_mapping()
    assert payload["schema_version"] == 1
    assert payload["motor"]["kv_rpm_per_v"] == 1000.0
    assert payload["battery"]["voltage_v"] == 12.0
    assert payload["system"]["resistance_ohm"] == 0.01
    assert payload["aero"]["qualification"] == "software_fixture"
    assert payload["settings"]["scan_points"] >= 25
    assert payload["physical_correlation_state"] == "pending"


def test_bem_callback_rebuilds_condition_at_every_candidate_rpm() -> None:
    seen = []

    class FakeRotorResult:
        thrust_n = 4.0
        torque_nm = 0.08
        shaft_power_w = 0.08 * 6000.0 * math.pi / 30.0

    def rotor_solver(condition):
        seen.append(condition)
        return FakeRotorResult()

    callback = make_bem_aero_load_callback(
        rotor_solver,
        forward_speed_m_s=3.0,
        air_density_kg_m3=1.18,
        dynamic_viscosity_pa_s=1.82e-5,
        temperature_k=298.15,
        pressure_pa=100_000.0,
        source_id="bem-test-v1",
        qualification="screening_only",
    )
    sample = callback(6000.0)
    assert seen[0].angular_speed_rad_s == pytest.approx(6000.0 * math.pi / 30.0)
    assert seen[0].forward_speed_m_s == 3.0
    assert sample.torque_nm == 0.08
    assert sample.source_id == "bem-test-v1"


def test_evidence_requires_unique_cases_and_reports_numerical_gate() -> None:
    results = tuple(
        solve_coupled_operating_point(
            motor=MOTOR,
            battery=BATTERY,
            system=SYSTEM,
            throttle=throttle,
            aero_load=_quadratic_load,
        )
        for throttle in (0.5, 0.7, 0.9)
    )
    evidence = CoupledEquilibriumEvidence(
        evidence_id="analytic-quadratic-v1",
        cases=results,
        multistart_cases=tuple(
            CoupledMultistartCase(
                throttle=result.throttle,
                initial_guesses_rpm=(300.0, 3000.0, 7000.0),
                converged_roots_rpm=(result.rpm, result.rpm, result.rpm),
            )
            for result in results
        ),
    )
    assert evidence.numerical_gate_passed
    assert not evidence.physical_gate_passed
    assert evidence.as_mapping()["physical_gate"] == "pending_measured_correlation"

    with pytest.raises(ValueError, match="unique"):
        CoupledEquilibriumEvidence(
            evidence_id="duplicates",
            cases=(results[0], results[0]),
            multistart_cases=(
                CoupledMultistartCase(
                    throttle=results[0].throttle,
                    initial_guesses_rpm=(300.0, 3000.0),
                    converged_roots_rpm=(results[0].rpm, results[0].rpm),
                ),
            ),
        )


def test_evidence_rejects_forged_or_incomplete_multistart_roots() -> None:
    result = solve_coupled_operating_point(
        motor=MOTOR,
        battery=BATTERY,
        system=SYSTEM,
        throttle=0.7,
        aero_load=_quadratic_load,
    )
    forged = CoupledMultistartCase(
        throttle=0.7,
        initial_guesses_rpm=(300.0, 7000.0),
        converged_roots_rpm=(result.rpm, result.rpm + 5.0),
    )
    evidence = CoupledEquilibriumEvidence(
        evidence_id="forged-spread",
        cases=(result,),
        multistart_cases=(forged,),
    )
    assert not evidence.numerical_gate_passed

    with pytest.raises(ValueError, match="match"):
        CoupledEquilibriumEvidence(
            evidence_id="missing-case",
            cases=(result,),
            multistart_cases=(
                CoupledMultistartCase(
                    throttle=0.5,
                    initial_guesses_rpm=(300.0, 3000.0),
                    converged_roots_rpm=(result.rpm, result.rpm),
                ),
            ),
        )


def test_nonfinite_or_power_inconsistent_aero_load_fails_closed() -> None:
    def invalid(rpm: float) -> AeroLoadSample:
        return AeroLoadSample(
            rpm=rpm,
            thrust_n=1.0,
            torque_nm=float("nan"),
            shaft_power_w=1.0,
            source_id="invalid",
            qualification="software_fixture",
        )

    with pytest.raises(InvalidAeroLoadError):
        solve_coupled_operating_point(
            motor=MOTOR,
            battery=BATTERY,
            system=SYSTEM,
            throttle=0.5,
            aero_load=invalid,
        )


def test_missing_and_ambiguous_equilibria_fail_closed() -> None:
    def impossible(rpm: float) -> AeroLoadSample:
        omega = rpm * math.pi / 30.0
        return AeroLoadSample(rpm, 0.0, 100.0, 100.0 * omega, "no-root", "fixture")

    with pytest.raises(NoEquilibriumError):
        solve_coupled_operating_point(
            motor=MOTOR,
            battery=BATTERY,
            system=SYSTEM,
            throttle=0.7,
            aero_load=impossible,
        )

    def three_roots(rpm: float) -> AeroLoadSample:
        applied = 0.7 * BATTERY.voltage_v
        current = (applied - rpm / MOTOR.kv_rpm_per_v) / (
            MOTOR.resistance_ohm + SYSTEM.resistance_ohm
        )
        kt = 30.0 / (math.pi * MOTOR.kv_rpm_per_v)
        motor_torque = kt * (current - MOTOR.no_load_current_a)
        residual = 2.0e-12 * (rpm - 2000.0) * (rpm - 5000.0) * (rpm - 7800.0)
        torque = motor_torque - residual
        omega = rpm * math.pi / 30.0
        return AeroLoadSample(rpm, 1.0, torque, torque * omega, "three-root", "fixture")

    with pytest.raises(AmbiguousEquilibriumError):
        solve_coupled_operating_point(
            motor=MOTOR,
            battery=BATTERY,
            system=SYSTEM,
            throttle=0.7,
            aero_load=three_roots,
            settings=CoupledSolverSettings(rpm_min=1000.0, rpm_max=8200.0, scan_points=289),
        )


def test_current_limit_is_reported_without_promoting_physical_validity() -> None:
    limited_motor = MotorSpec(1000.0, 0.05, 1.0, 5.0)
    result = solve_coupled_operating_point(
        motor=limited_motor,
        battery=BATTERY,
        system=SYSTEM,
        throttle=0.70,
        aero_load=_quadratic_load,
    )
    assert result.converged
    assert not result.feasible
    assert result.infeasible_reason == "current_limit"
    assert result.physical_correlation_state == "pending"


@pytest.mark.parametrize("throttle", [0.0, -0.1, 1.01, float("nan")])
def test_invalid_throttle_is_rejected(throttle: float) -> None:
    with pytest.raises(ValueError, match="throttle"):
        solve_coupled_operating_point(
            motor=MOTOR,
            battery=BATTERY,
            system=SYSTEM,
            throttle=throttle,
            aero_load=_quadratic_load,
        )


def test_invalid_propulsion_parameters_fail_before_root_search() -> None:
    invalid_motor = MotorSpec(0.0, 0.05, 1.0, 30.0)
    with pytest.raises(ValueError, match="Kv"):
        solve_coupled_operating_point(
            motor=invalid_motor,
            battery=BATTERY,
            system=SYSTEM,
            throttle=0.7,
            aero_load=_quadratic_load,
        )
