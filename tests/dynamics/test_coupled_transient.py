"""RED/GREEN contract for the CMM-1 partial coupled screening transient."""

from __future__ import annotations

import dataclasses
import math

import pytest

from pyfoldable.core.motor_bem_coupling import (
    AeroLoadSample,
    algebraic_motor_state,
    solve_coupled_operating_point,
)
from pyfoldable.dynamics.coupled_transient import (
    AERO_HINGE_STATUS,
    MODEL_CLASS,
    OMEGA_MIN,
    AeroEvaluation,
    BaseRotatingAssemblyInertia,
    CoupledDomainExit,
    CoupledSystem,
    CoupledTransientError,
    CoupledTransientFailure,
    CoupledTransientRequest,
    HingeActuationHistory,
    MotorEvaluation,
    coupled_accelerations,
    coupled_mass_matrix,
    coupled_result_json,
    mechanical_energy,
    prescribed_shaft_hinge_acceleration,
    solve_coupled_transient,
)
from pyfoldable.dynamics.mechanism_contracts import DryFriction
from pyfoldable.dynamics.mechanism_transient import (
    DriveHistory,
    MechanismParameters,
    SolverControls,
    TransientRequest,
    solve_mechanism_transient,
)
from pythrust.propulsion.models import BatterySpec, MotorSpec, SystemSpec


def _inertia(value: float = 1.0e-3, source: str = "test-i0") -> BaseRotatingAssemblyInertia:
    return BaseRotatingAssemblyInertia(
        value,
        source,
        ("motor rotor", "shaft", "hub", "fixed roots"),
    )


def _parameters(**overrides) -> MechanismParameters:
    values = dict(
        mass_kg=0.02,
        cg_distance_m=0.01,
        hinge_inertia_kg_m2=1.0e-4,
        hinge_radius_m=0.08,
        spring_stiffness_nm_rad=0.0,
        rest_angle_rad=0.0,
        viscous_damping_nm_s_rad=0.0,
        lower_stop_rad=-1.0,
        upper_stop_rad=1.0,
    )
    values.update(overrides)
    return MechanismParameters(**values)


def _system(parameters=None, blade_count: int = 2, inertia=None) -> CoupledSystem:
    return CoupledSystem(
        parameters or _parameters(),
        blade_count,
        inertia or _inertia(),
    )


def _history(torque: float = 0.0, end: float = 0.02) -> HingeActuationHistory:
    return HingeActuationHistory((0.0, end), (torque, torque), "test-qh")


def _motor(torque: float):
    def evaluate(time_s, theta, theta_dot, omega):
        del time_s, theta, theta_dot, omega
        return MotorEvaluation(torque_nm=torque)

    return evaluate


def _aero(torque: float, thrust: float = 0.0):
    def evaluate(time_s, theta, theta_dot, omega):
        del time_s, theta, theta_dot, omega
        return AeroEvaluation(torque, thrust, "analytic", "software_fixture")

    return evaluate


def _request(system=None, **overrides) -> CoupledTransientRequest:
    values = dict(
        system=system or _system(),
        actuation=_history(),
        initial_angle_rad=-0.2,
        initial_angular_velocity_rad_s=0.0,
        initial_omega_rad_s=OMEGA_MIN * 2.0,
        motor_evaluator=_motor(0.0),
        aero_evaluator=_aero(0.0),
    )
    values.update(overrides)
    return CoupledTransientRequest(**values)


def test_api_exports_the_partial_coupled_solver() -> None:
    assert callable(solve_coupled_transient)
    assert MODEL_CLASS == "partial_coupled_screening_only"
    assert AERO_HINGE_STATUS == "unavailable_omitted_by_cmm1"


def test_prescribed_shaft_reduction_matches_py05_term_by_term() -> None:
    friction = DryFriction("regularized_coulomb", 0.002, 0.05, source="reduction")
    parameters = _parameters(
        spring_stiffness_nm_rad=0.01,
        rest_angle_rad=-0.05,
        viscous_damping_nm_s_rad=0.002,
        dry_friction=friction,
    )
    theta = -0.2
    theta_dot = 0.3
    omega = 30.0
    omega_dot = -4.0
    qh = 0.001
    duration = 0.01
    rpm0 = omega * 30.0 / math.pi
    rpm1 = (omega + omega_dot * duration) * 30.0 / math.pi
    py05 = solve_mechanism_transient(
        TransientRequest(
            parameters,
            DriveHistory((0.0, duration), (rpm0, rpm1), (qh, qh)),
            theta,
            theta_dot,
            SolverControls(max_step_s=0.002, max_samples=1000),
        )
    )
    reduction = prescribed_shaft_hinge_acceleration(
        parameters, theta, theta_dot, omega, omega_dot, qh
    )
    assert reduction.applied_nm == pytest.approx(py05.applied_torque_nm[0], abs=1e-12)
    assert reduction.spring_nm == pytest.approx(py05.spring_torque_nm[0], abs=1e-12)
    assert reduction.damping_nm == pytest.approx(py05.damping_torque_nm[0], abs=1e-12)
    assert reduction.friction_nm == pytest.approx(py05.dry_friction_torque_nm[0], abs=1e-12)
    assert reduction.centrifugal_nm == pytest.approx(py05.centrifugal_torque_nm[0], abs=1e-12)
    assert reduction.euler_nm == pytest.approx(py05.euler_torque_nm[0], abs=1e-12)
    assert reduction.theta_ddot_rad_s2 == pytest.approx(
        py05.angular_acceleration_rad_s2[0], abs=1e-12
    )


def test_mass_matrix_matches_the_analytical_coefficients_and_point_mass_boundary() -> None:
    parameters = _parameters()
    system = _system(parameters, blade_count=3)
    theta = -0.4
    mass = coupled_mass_matrix(system, theta)
    mass_kg = parameters.mass_kg
    radius = parameters.hinge_radius_m
    cg = parameters.cg_distance_m
    inertia = parameters.hinge_inertia_kg_m2
    coupling = mass_kg * radius * cg
    cosine = math.cos(theta)
    expected_a = inertia + mass_kg * radius**2 + 2.0 * coupling * cosine
    expected_b = inertia + coupling * cosine
    assert mass.a_kg_m2 == pytest.approx(expected_a)
    assert mass.b_kg_m2 == pytest.approx(expected_b)
    assert mass.m11 == pytest.approx(3.0 * inertia)
    assert mass.m01 == pytest.approx(3.0 * expected_b)
    assert mass.m00 == pytest.approx(system.base_inertia.inertia_kg_m2 + 3.0 * expected_a)
    assert mass.schur_kg_m2 > 0.0
    point = _parameters(
        mass_kg=0.04,
        cg_distance_m=0.02,
        hinge_inertia_kg_m2=0.04 * 0.02**2,
    )
    point_mass = coupled_mass_matrix(_system(point, inertia=_inertia(2.0e-4)), 0.0)
    assert point_mass.schur_kg_m2 > 0.0
    solved = coupled_accelerations(
        _system(point, inertia=_inertia(2.0e-4)),
        theta=0.2,
        theta_dot=0.1,
        omega=OMEGA_MIN,
        motor_torque_nm=0.001,
        aero_shaft_torque_nm=0.0002,
        hinge_torque_nm=0.0,
    )
    assert math.isfinite(solved.omega_dot_rad_s2)
    assert math.isfinite(solved.theta_ddot_rad_s2)
    assert solved.mass_schur > 0.0
    with pytest.raises(CoupledTransientError):
        _inertia(0.0)
    with pytest.raises(CoupledTransientError):
        _inertia(-1.0)
    with pytest.raises(CoupledTransientError):
        _inertia(float("nan"))
    with pytest.raises(CoupledTransientError):
        BaseRotatingAssemblyInertia(1.0e-3, " ", ("hub",))
    with pytest.raises(CoupledTransientError):
        BaseRotatingAssemblyInertia(1.0e-3, "src", ())


def test_blade_count_scales_tip_terms_without_double_counting_shaft_loads() -> None:
    parameters = _parameters(spring_stiffness_nm_rad=0.02, viscous_damping_nm_s_rad=0.001)
    theta = -0.3
    theta_dot = 0.2
    omega = 40.0
    qm = 0.03
    qa = 0.01
    qh = 0.002
    one = coupled_accelerations(
        _system(parameters, blade_count=1), theta, theta_dot, omega, qm, qa, qh
    )
    three = coupled_accelerations(
        _system(parameters, blade_count=3), theta, theta_dot, omega, qm, qa, qh
    )
    assert three.collective_spring_nm == pytest.approx(3.0 * one.collective_spring_nm)
    assert three.collective_damping_nm == pytest.approx(3.0 * one.collective_damping_nm)
    assert three.rhs_shaft_nm - one.rhs_shaft_nm == pytest.approx(
        2.0
        * one.parameters_c_kg_m2
        * math.sin(theta)
        * (2.0 * omega * theta_dot + theta_dot**2)
    )
    assert one.rhs_shaft_nm == pytest.approx(
        qm
        - qa
        + one.parameters_c_kg_m2
        * math.sin(theta)
        * (2.0 * omega * theta_dot + theta_dot**2)
    )
    assert three.motor_torque_nm == qm
    assert three.aero_shaft_torque_nm == qa
    assert three.rhs_shaft_nm == pytest.approx(
        qm
        - qa
        + 3.0
        * three.parameters_c_kg_m2
        * math.sin(theta)
        * (2.0 * omega * theta_dot + theta_dot**2)
    )


def test_friction_and_spring_collectives_use_n_not_shaft_torque() -> None:
    friction = DryFriction("regularized_coulomb", 0.004, 0.1, source="n-scale")
    parameters = _parameters(dry_friction=friction, spring_stiffness_nm_rad=0.01)
    solved = coupled_accelerations(
        _system(parameters, blade_count=4),
        theta=-0.25,
        theta_dot=0.3,
        omega=20.0,
        motor_torque_nm=0.2,
        aero_shaft_torque_nm=0.05,
        hinge_torque_nm=0.003,
    )
    assert solved.collective_friction_nm == pytest.approx(4.0 * solved.friction_nm)
    assert solved.collective_actuation_nm == pytest.approx(4.0 * 0.003)
    assert solved.motor_torque_nm == pytest.approx(0.2)
    assert solved.aero_shaft_torque_nm == pytest.approx(0.05)


def test_conservative_mechanics_keep_mechanical_energy_and_tighten() -> None:
    parameters = _parameters(
        mass_kg=0.05,
        cg_distance_m=0.02,
        hinge_inertia_kg_m2=1.0e-3,
        hinge_radius_m=0.06,
        spring_stiffness_nm_rad=0.02,
        rest_angle_rad=-0.1,
    )
    system = _system(parameters, inertia=_inertia(2.0e-3))

    def residual(rtol: float) -> float:
        result = solve_coupled_transient(
            _request(
                system=system,
                actuation=_history(end=0.04),
                initial_angle_rad=-0.3,
                initial_angular_velocity_rad_s=0.4,
                initial_omega_rad_s=25.0,
                controls=_controls(rtol=rtol),
            )
        )
        return max(abs(sample.energy_residual_j) for sample in result.samples)

    loose = residual(1.0e-4)
    tight = residual(1.0e-8)
    assert loose < 1.0e-4
    assert tight <= loose


def test_locked_theta_follows_the_analytic_shaft_acceleration() -> None:
    parameters = _parameters()
    inertia = _inertia(0.01)
    system = _system(parameters, blade_count=2, inertia=inertia)
    mass = coupled_mass_matrix(system, 0.0)
    qm = 0.01
    alpha = qm / mass.m00
    qh = mass.b_kg_m2 * alpha
    omega0 = 30.0
    result = solve_coupled_transient(
        _request(
            system=system,
            actuation=_history(qh, end=0.02),
            initial_angle_rad=0.0,
            initial_angular_velocity_rad_s=0.0,
            initial_omega_rad_s=omega0,
            motor_evaluator=_motor(qm),
            aero_evaluator=_aero(0.0),
        )
    )
    for sample in result.samples:
        assert sample.theta_rad == pytest.approx(0.0, abs=1.0e-7)
        assert sample.omega_rad_s == pytest.approx(omega0 + alpha * sample.time_s, abs=1.0e-6)


def test_deployed_equilibrium_matches_pr07_motor_torque() -> None:
    motor = MotorSpec(1000.0, 0.05, 1.0, 80.0)
    battery = BatterySpec(12.0, 0.98)
    system_elec = SystemSpec(0.01)
    throttle = 0.1
    rpm = 400.0
    state = algebraic_motor_state(motor, battery, system_elec, throttle, rpm)
    point = solve_coupled_operating_point(
        motor=motor,
        battery=battery,
        system=system_elec,
        throttle=throttle,
        aero_load=lambda speed: AeroLoadSample(
            rpm=speed,
            thrust_n=0.1,
            torque_nm=state.torque_nm,
            shaft_power_w=state.torque_nm * speed * math.pi / 30.0,
            source_id="constant",
            qualification="software_fixture",
        ),
        initial_guess_rpm=rpm,
    )
    assert point.motor_state.torque_nm == pytest.approx(state.torque_nm, abs=1e-12)
    assert point.rpm == pytest.approx(rpm, abs=1e-6)
    solved = coupled_accelerations(
        _system(),
        theta=0.0,
        theta_dot=0.0,
        omega=point.rpm * math.pi / 30.0,
        motor_torque_nm=point.motor_state.torque_nm,
        aero_shaft_torque_nm=point.aero.torque_nm,
        hinge_torque_nm=0.0,
    )
    assert solved.omega_dot_rad_s2 == pytest.approx(0.0, abs=1e-9)
    assert solved.theta_ddot_rad_s2 == pytest.approx(0.0, abs=1e-9)
    assert state.current_a == pytest.approx(
        (throttle * battery.voltage_v - rpm / motor.kv_rpm_per_v)
        / (motor.resistance_ohm + system_elec.resistance_ohm)
    )


def test_initial_fold_speed_and_reverse_domains_fail_closed() -> None:
    with pytest.raises(CoupledTransientError):
        _request(initial_angle_rad=-1.6)
    with pytest.raises(CoupledTransientError):
        _request(initial_angle_rad=-math.pi / 2.0)
    with pytest.raises(CoupledTransientError):
        _request(initial_omega_rad_s=OMEGA_MIN - 1.0e-9)
    with pytest.raises(CoupledTransientError):
        _request(initial_omega_rad_s=0.0)
    with pytest.raises(CoupledTransientError):
        _request(initial_omega_rad_s=-5.0)

    def slowing_motor(time_s, theta, theta_dot, omega):
        del time_s, theta, theta_dot
        if omega < OMEGA_MIN:
            raise AssertionError("physics evaluated below the shaft-speed floor")
        return MotorEvaluation(torque_nm=0.0)

    def heavy_aero(time_s, theta, theta_dot, omega):
        del time_s, theta, theta_dot
        if omega < OMEGA_MIN:
            raise AssertionError("BEM evaluated below the shaft-speed floor")
        return AeroEvaluation(5.0, 0.0, "drag", "software_fixture")

    with pytest.raises(CoupledDomainExit):
        solve_coupled_transient(
            _request(
                system=_system(inertia=_inertia(1.0e-5)),
                actuation=_history(end=0.05),
                initial_omega_rad_s=OMEGA_MIN,
                motor_evaluator=slowing_motor,
                aero_evaluator=heavy_aero,
            )
        )


def test_first_stop_contact_is_terminal() -> None:
    parameters = _parameters(lower_stop_rad=-0.08, upper_stop_rad=0.8)
    result = solve_coupled_transient(
        _request(
            system=_system(parameters, inertia=_inertia(0.05)),
            actuation=_history(end=0.05),
            initial_angle_rad=-0.02,
            initial_angular_velocity_rad_s=-6.0,
            initial_omega_rad_s=40.0,
        )
    )
    assert result.status == "first_contact_terminal"
    assert result.contact is not None
    assert result.contact.stop == "lower"
    assert result.contact.angle_rad == pytest.approx(parameters.lower_stop_rad)
    assert result.samples[-1].time_s == pytest.approx(result.contact.time_s)
    assert result.samples[-1].time_s < 0.05
    assert result.physical_qualification is False


def test_actuation_knots_restart_the_integrator() -> None:
    result = solve_coupled_transient(
        _request(
            actuation=HingeActuationHistory(
                (0.0, 0.01, 0.02),
                (0.0, 0.0, 0.001),
                "kinked-qh",
            ),
            initial_angle_rad=-0.1,
            initial_omega_rad_s=30.0,
        )
    )
    assert 0.01 in result.segment_boundary_times_s
    assert any(math.isclose(sample.time_s, 0.01, abs_tol=1e-12) for sample in result.samples)


def test_work_budget_aborts_without_a_successful_result() -> None:
    with pytest.raises(CoupledTransientFailure, match="budget"):
        solve_coupled_transient(
            _request(
                actuation=_history(end=0.02),
                controls=_controls(max_rhs_evaluations=1),
            )
        )


def test_result_contract_is_immutable_finite_and_repeatable() -> None:
    request = _request(actuation=_history(end=0.01), initial_angle_rad=-0.15)
    first = solve_coupled_transient(request)
    second = solve_coupled_transient(request)
    assert first.model_class == MODEL_CLASS
    assert first.physical_qualification is False
    assert first.full_propeller_clearance is None
    assert first.surface_path_clearance is None
    assert first.interblade_clearance is None
    assert first.samples[0].aerodynamic_hinge_torque_status == AERO_HINGE_STATUS
    assert [sample.time_s for sample in first.samples] == [
        sample.time_s for sample in second.samples
    ]
    assert [sample.theta_rad for sample in first.samples] == [
        sample.theta_rad for sample in second.samples
    ]
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.samples[0].theta_rad = 0.0  # type: ignore[misc]
    document = coupled_result_json(first)
    assert "aerodynamic_hinge_torque_nm" not in document
    assert '"physical_qualification":false' in document
    object.__setattr__(first.samples[0], "theta_rad", float("nan"))
    with pytest.raises(ValueError):
        coupled_result_json(first)


def test_nonfinite_mass_solve_fails_closed() -> None:
    with pytest.raises((CoupledTransientError, CoupledTransientFailure, ValueError)):
        coupled_accelerations(
            _system(),
            theta=0.0,
            theta_dot=0.0,
            omega=OMEGA_MIN,
            motor_torque_nm=float("inf"),
            aero_shaft_torque_nm=0.0,
            hinge_torque_nm=0.0,
        )
    with pytest.raises((CoupledTransientError, CoupledTransientFailure, OverflowError)):
        coupled_accelerations(
            _system(),
            theta=-0.2,
            theta_dot=0.0,
            omega=1.0e200,
            motor_torque_nm=0.0,
            aero_shaft_torque_nm=0.0,
            hinge_torque_nm=0.0,
        )


def test_mechanical_energy_uses_the_coupled_quadratic_form() -> None:
    system = _system()
    theta = -0.2
    theta_dot = 0.3
    omega = 20.0
    mass = coupled_mass_matrix(system, theta)
    expected = (
        0.5 * mass.m00 * omega**2
        + mass.m01 * omega * theta_dot
        + 0.5 * mass.m11 * theta_dot**2
    )
    kinetic, _spring, total = mechanical_energy(system, theta, theta_dot, omega)
    assert kinetic == pytest.approx(expected)
    assert total == pytest.approx(expected)


def _controls(**overrides):
    from pyfoldable.dynamics.coupled_transient import CoupledSolverControls

    values = dict(max_duration_s=0.05, max_samples=500, max_rhs_evaluations=4000)
    values.update(overrides)
    return CoupledSolverControls(**values)
