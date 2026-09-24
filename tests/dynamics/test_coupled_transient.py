"""RED/GREEN contract for the CMM-1 partial coupled screening transient."""

from __future__ import annotations

import dataclasses
import math
from decimal import Decimal, getcontext
from fractions import Fraction

import numpy as np
import pytest
from scipy.integrate import RK45
from scipy.integrate._ivp.rk import RkDenseOutput

from pyfoldable.core.motor_bem_coupling import (
    AeroLoadSample,
    algebraic_motor_state,
    solve_coupled_operating_point,
)
import pyfoldable.dynamics.coupled_transient as coupled_transient
from pyfoldable.dynamics.coupled_transient import (
    AERO_HINGE_STATUS,
    FOLD_LIMIT_RAD,
    MODEL_CLASS,
    OMEGA_MIN,
    AeroEvaluation,
    BaseRotatingAssemblyInertia,
    CoupledDomainExit,
    CoupledSolverControls,
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
    values = dict(max_duration_s=0.05, max_samples=500, max_rhs_evaluations=4000)
    values.update(overrides)
    return CoupledSolverControls(**values)


def _one_step_controls() -> CoupledSolverControls:
    return CoupledSolverControls(
        rtol=1.0e-3,
        angle_atol_rad=1.0e-4,
        hinge_velocity_atol_rad_s=1.0e-3,
        shaft_speed_atol_rad_s=1.0e-2,
        max_step_s=0.002,
        max_duration_s=0.002,
        max_samples=20,
        max_rhs_evaluations=200,
    )


def _dense_extrema(dense) -> tuple[float, float, float, float]:
    """Endpoints plus real derivative roots of the RK45 quartic."""
    q_matrix = np.asarray(dense.Q, dtype=float)
    y_old = np.asarray(dense.y_old, dtype=float)
    step = float(dense.h)

    def component(index: int) -> tuple[float, float]:
        coeff = q_matrix[index]
        deriv = [coeff[0], 2.0 * coeff[1], 3.0 * coeff[2], 4.0 * coeff[3]]
        while len(deriv) > 1 and deriv[-1] == 0.0:
            deriv.pop()
        roots = [] if len(deriv) == 1 else np.polynomial.polynomial.polyroots(deriv)
        xs = [0.0, 1.0]
        for root in roots:
            real = float(np.real(root))
            imag = float(np.imag(root))
            if abs(imag) <= 512.0 * np.finfo(float).eps and 0.0 < real < 1.0:
                xs.append(real)
        values = []
        for x in xs:
            power = x
            acc = 0.0
            for term in coeff:
                acc += float(term) * power
                power *= x
            values.append(float(y_old[index]) + step * acc)
        return min(values), max(values)

    theta_min, theta_max = component(0)
    omega_min, _omega_max = component(2)
    return theta_min, theta_max, omega_min, float(y_old[0] + step * np.dot(q_matrix[0], [1, 1, 1, 1]))


def _quartic(y_old, q_rows, t_old=0.0, step=1.0) -> RkDenseOutput:
    q_matrix = np.zeros((3, 4), dtype=float)
    for index, row in enumerate(q_rows):
        q_matrix[index, : len(row)] = row
    return RkDenseOutput(t_old, t_old + step, np.asarray(y_old, dtype=float), q_matrix)


def test_hidden_dense_fold_excursion_aborts_without_a_result() -> None:
    """Accepted endpoints stay inside while the RK45 quartic crosses ±pi/2."""
    theta0 = 1.5653333333333335
    speed = OMEGA_MIN * 5.0
    calls = []

    def motor(time_s, theta, theta_dot, omega):
        del time_s, theta_dot
        calls.append(omega)
        assert abs(theta) < FOLD_LIMIT_RAD
        assert omega >= OMEGA_MIN
        return MotorEvaluation(0.0)

    def aero(time_s, theta, theta_dot, omega):
        del time_s, theta_dot
        assert abs(theta) < FOLD_LIMIT_RAD
        assert omega >= OMEGA_MIN
        return AeroEvaluation(0.0, 0.0, "analytic", "software_fixture")

    for sign, torque in ((1.0, -0.8), (-1.0, 0.8)):
        calls.clear()
        system = _system(
            _parameters(lower_stop_rad=-1.65, upper_stop_rad=1.65),
            blade_count=1,
            inertia=_inertia(1.0e-2),
        )
        request = _request(
            system,
            actuation=_history(torque, 0.002),
            initial_angle_rad=sign * theta0,
            initial_angular_velocity_rad_s=sign * 10.0,
            initial_omega_rad_s=speed,
            motor_evaluator=motor,
            aero_evaluator=aero,
            controls=_one_step_controls(),
        )
        def rhs(time_s, y, hinge=torque, plant=system):
            del time_s
            solved = coupled_accelerations(plant, y[0], y[1], y[2], 0.0, 0.0, hinge)
            return (y[1], solved.theta_ddot_rad_s2, solved.omega_dot_rad_s2)

        solver = RK45(
            rhs,
            0.0,
            (sign * theta0, sign * 10.0, speed),
            0.002,
            max_step=0.002,
            rtol=1.0e-3,
            atol=(1.0e-4, 1.0e-3, 1.0e-2),
        )
        solver.step()
        dense = solver.dense_output()
        theta_min, theta_max, omega_min, _endpoint = _dense_extrema(dense)
        assert abs(float(solver.y[0])) < FOLD_LIMIT_RAD
        assert float(solver.y[2]) >= OMEGA_MIN
        assert omega_min >= OMEGA_MIN
        assert theta_max > FOLD_LIMIT_RAD or theta_min < -FOLD_LIMIT_RAD
        with pytest.raises(CoupledDomainExit):
            solve_coupled_transient(request)
        assert calls


def test_hidden_dense_omega_excursion_aborts_without_a_result() -> None:
    """Endpoints stay at or above 100 rpm while the RK45 quartic dips below it."""
    parameters = _parameters(
        mass_kg=0.001,
        cg_distance_m=0.001,
        hinge_inertia_kg_m2=1.0e-3,
        hinge_radius_m=0.05,
    )
    system = _system(parameters, blade_count=1, inertia=_inertia(1.0e-3))
    schur = coupled_mass_matrix(system, 0.0).schur_kg_m2
    slope = 20000.0
    peak = 0.0011
    omega0 = OMEGA_MIN + 0.01
    seen = []

    def motor(time_s, theta, theta_dot, omega):
        del theta_dot
        seen.append((theta, omega))
        assert abs(theta) < FOLD_LIMIT_RAD
        assert omega >= OMEGA_MIN
        return MotorEvaluation(schur * slope * (time_s - peak))

    def aero(time_s, theta, theta_dot, omega):
        del time_s, theta_dot
        assert abs(theta) < FOLD_LIMIT_RAD
        assert omega >= OMEGA_MIN
        return AeroEvaluation(0.0, 0.0, "analytic", "software_fixture")

    request = _request(
        system,
        actuation=_history(0.0, 0.002),
        initial_angle_rad=0.0,
        initial_angular_velocity_rad_s=0.0,
        initial_omega_rad_s=omega0,
        motor_evaluator=motor,
        aero_evaluator=aero,
        controls=_one_step_controls(),
    )
    def rhs(time_s, y):
        solved = coupled_accelerations(
            system, y[0], y[1], y[2], schur * slope * (time_s - peak), 0.0, 0.0
        )
        return (y[1], solved.theta_ddot_rad_s2, solved.omega_dot_rad_s2)

    solver = RK45(
        rhs,
        0.0,
        (0.0, 0.0, omega0),
        0.002,
        max_step=0.002,
        rtol=1.0e-3,
        atol=(1.0e-4, 1.0e-3, 1.0e-2),
    )
    solver.step()
    _theta_min, theta_max, omega_min, _endpoint = _dense_extrema(solver.dense_output())
    assert abs(float(solver.y[0])) < FOLD_LIMIT_RAD
    assert abs(theta_max) < FOLD_LIMIT_RAD
    assert float(solver.y[2]) >= OMEGA_MIN
    assert omega_min < OMEGA_MIN
    with pytest.raises(CoupledDomainExit):
        solve_coupled_transient(request)
    assert seen
    assert min(omega for _theta, omega in seen) >= OMEGA_MIN


def test_dense_domain_audit_uses_only_the_rk45_quartic() -> None:
    audit = coupled_transient._audit_dense_model_domain
    inside = _quartic((0.2, 0.0, OMEGA_MIN + 1.0), ((0.0, 0.0), (0.0,), (0.0,)))
    audit(inside, 0.0, 1.0)

    margin = 0.015625
    below = math.nextafter(FOLD_LIMIT_RAD, 0.0)
    infinitesimal = _quartic((below - margin, 0.0, OMEGA_MIN + 1.0), ((4.0 * margin, -4.0 * margin), (0.0,), (0.0,)))
    audit(infinitesimal, 0.0, 1.0)
    negative_inside = _quartic((-below + margin, 0.0, OMEGA_MIN + 1.0), ((-4.0 * margin, 4.0 * margin), (0.0,), (0.0,)))
    audit(negative_inside, 0.0, 1.0)
    speed_inside = _quartic((0.0, 0.0, OMEGA_MIN), ((0.0,), (0.0,), (0.0,)))
    audit(speed_inside, 0.0, 1.0)

    on_fold = _quartic((FOLD_LIMIT_RAD, 0.0, OMEGA_MIN + 1.0), ((0.0,), (0.0,), (0.0,)))
    with pytest.raises(CoupledDomainExit):
        audit(on_fold, 0.0, 1.0)
    on_negative = _quartic((-FOLD_LIMIT_RAD, 0.0, OMEGA_MIN + 1.0), ((0.0,), (0.0,), (0.0,)))
    with pytest.raises(CoupledDomainExit):
        audit(on_negative, 0.0, 1.0)
    with pytest.raises(CoupledDomainExit):
        audit(
            _quartic((0.0, 0.0, math.nextafter(OMEGA_MIN, 0.0)), ((0.0,), (0.0,), (0.0,))),
            0.0,
            1.0,
        )

    # Interior fold peak is after the early audit window.
    late_peak = _quartic((1.0, 0.0, OMEGA_MIN + 1.0), ((2.4, -2.4), (0.0,), (0.0,)))
    audit(late_peak, 0.0, 0.05)
    with pytest.raises(CoupledDomainExit):
        audit(late_peak, 0.0, 1.0)

    with pytest.raises(CoupledTransientFailure, match="dense output"):
        audit(lambda time_s: (0.0, 0.0, OMEGA_MIN), 0.0, 1.0)
    cubic = RkDenseOutput(0.0, 1.0, np.zeros(3), np.zeros((3, 3)))
    with pytest.raises(CoupledTransientFailure, match="quartic"):
        audit(cubic, 0.0, 1.0)


# Represented RK45 row whose derivative cubic has three real roots. NumPy's
# companion solver returns the close pair as complex with an imaginary part
# far above 512 eps, so the old audit never evaluates that stationary point.
_ILL_CONDITIONED_Q = (
    -1.1520000826779448,
    3.5200001492796225,
    -4.5333334098869855,
    2.0,
)
_ILL_CONDITIONED_Y = 10.608508859385182
_ILL_CONDITIONED_X_END = 0.4000000287076197


def _represented_derivative(q):
    coeff = [Decimal.from_float(float(term)) for term in q]
    return (coeff[0], Decimal(2) * coeff[1], Decimal(3) * coeff[2], Decimal(4) * coeff[3])


def _cubic_discriminant(deriv) -> Decimal:
    constant, linear, quadratic, cubic = deriv
    return (
        Decimal(18) * cubic * quadratic * linear * constant
        - Decimal(4) * quadratic**3 * constant
        + quadratic**2 * linear**2
        - Decimal(4) * cubic * linear**3
        - Decimal(27) * cubic**2 * constant**2
    )


def _decimal_horner(coeffs, x: Decimal) -> Decimal:
    value = Decimal(0)
    for coeff in reversed(coeffs):
        value = value * x + coeff
    return value


def _isolate_represented_real_roots(deriv, lo: Decimal, hi: Decimal) -> list[Decimal]:
    """Sign-change isolation on the represented cubic. Not a NumPy root query."""
    constant, linear, quadratic, cubic = deriv
    turning = [lo, hi]
    second_lead = Decimal(3) * cubic
    second_linear = Decimal(2) * quadratic
    if second_lead == 0 and second_linear != 0:
        root = -linear / second_linear
        if lo < root < hi:
            turning.append(root)
    elif second_lead != 0:
        disc = second_linear**2 - Decimal(4) * second_lead * linear
        if disc > 0:
            root_gap = disc.sqrt()
            for root in (
                (-second_linear + root_gap) / (Decimal(2) * second_lead),
                (-second_linear - root_gap) / (Decimal(2) * second_lead),
            ):
                if lo < root < hi:
                    turning.append(root)
    turning = sorted(turning)
    roots = []
    for left, right in zip(turning, turning[1:]):
        left_value = _decimal_horner(deriv, left)
        right_value = _decimal_horner(deriv, right)
        if left_value == 0:
            roots.append(left)
        if left_value * right_value < 0:
            low, high = left, right
            low_value = left_value
            for _ in range(200):
                mid = (low + high) / 2
                mid_value = _decimal_horner(deriv, mid)
                if mid_value == 0:
                    low = high = mid
                    break
                if (low_value > 0) == (mid_value > 0):
                    low, low_value = mid, mid_value
                else:
                    high = mid
            roots.append((low + high) / 2)
        if right_value == 0:
            roots.append(right)
    return roots


def _increment(q, x: Decimal) -> Decimal:
    coeff = [Decimal.from_float(float(term)) for term in q]
    return _decimal_horner((Decimal(0), *coeff), x)


def _float_quartic_value(y: float, q, x: float) -> float:
    accumulated = 0.0
    power = x
    for term in q:
        accumulated += float(term) * power
        power *= x
    return y + accumulated


def test_ill_conditioned_cubic_minimum_is_a_dense_domain_exit() -> None:
    """Three real derivative roots, one skipped by companion eigenvalues.

    The float power sum at the audited endpoint rounds to the legal speed
    floor. High-precision evaluation of the represented polynomial is below
    that floor by a fraction of an ulp. The old imaginary-part test misses it.
    """
    getcontext().prec = 80
    deriv = _represented_derivative(_ILL_CONDITIONED_Q)
    assert _cubic_discriminant(deriv) > 0
    roots = _isolate_represented_real_roots(deriv, Decimal(0), Decimal(1))
    assert len(roots) == 3
    numpy_roots = np.polynomial.polynomial.polyroots(
        [
            _ILL_CONDITIONED_Q[0],
            2 * _ILL_CONDITIONED_Q[1],
            3 * _ILL_CONDITIONED_Q[2],
            4 * _ILL_CONDITIONED_Q[3],
        ]
    )
    imag_tol = 512.0 * float(np.finfo(float).eps)
    assert max(abs(float(np.imag(root))) for root in numpy_roots) > 1.0e-9
    accepted = [
        float(np.real(root))
        for root in numpy_roots
        if abs(float(np.imag(root))) <= imag_tol and 0.0 < float(np.real(root)) < _ILL_CONDITIONED_X_END
    ]
    assert accepted == []
    x_end = Decimal.from_float(_ILL_CONDITIONED_X_END)
    interior = [root for root in roots if Decimal(0) < root < x_end]
    assert interior
    omega = Decimal.from_float(OMEGA_MIN)
    y = Decimal.from_float(_ILL_CONDITIONED_Y)
    deficits = [y + _increment(_ILL_CONDITIONED_Q, root) - omega for root in interior]
    worst = min(deficits)
    assert -Decimal("1e-12") < worst < 0
    assert _float_quartic_value(_ILL_CONDITIONED_Y, _ILL_CONDITIONED_Q, 0.0) >= OMEGA_MIN
    assert _float_quartic_value(_ILL_CONDITIONED_Y, _ILL_CONDITIONED_Q, _ILL_CONDITIONED_X_END) >= OMEGA_MIN
    dense = _quartic((0.2, 0.0, _ILL_CONDITIONED_Y), ((0.0,), (0.0,), _ILL_CONDITIONED_Q))
    with pytest.raises(CoupledDomainExit):
        coupled_transient._audit_dense_model_domain(dense, 0.0, _ILL_CONDITIONED_X_END)


def test_ill_conditioned_speed_root_before_contact_aborts() -> None:
    """A pre-contact stationary minimum is not excused by a legal contact state."""
    q = np.asarray(_ILL_CONDITIONED_Q, dtype=float)
    system = _system(
        _parameters(lower_stop_rad=-1.2, upper_stop_rad=1.2),
        blade_count=1,
        inertia=_inertia(1.0e-2),
    )

    def rhs(time_s, state):
        del time_s
        solved = coupled_accelerations(system, state[0], state[1], state[2], 0.0, 0.0, 0.0)
        return (state[1], solved.theta_ddot_rad_s2, solved.omega_dot_rad_s2)

    preview = RK45(
        rhs,
        0.0,
        (0.0, 2.0, OMEGA_MIN * 2.0),
        0.002,
        max_step=0.002,
        rtol=1.0e-3,
        atol=(1.0e-4, 1.0e-3, 1.0e-2),
    )
    preview.step()
    dense = preview.dense_output()
    contact_time = _ILL_CONDITIONED_X_END * float(dense.h)
    contact_angle = float(dense(contact_time)[0])
    assert abs(contact_angle) < FOLD_LIMIT_RAD
    original = coupled_transient.RK45.dense_output

    def patched(self, *args, **kwargs):
        output = original(self, *args, **kwargs)
        output.y_old = np.array(output.y_old, dtype=float, copy=True)
        output.Q = np.array(output.Q, dtype=float, copy=True)
        output.y_old[2] = _ILL_CONDITIONED_Y
        output.Q[2] = q / float(output.h)
        return output

    coupled_transient.RK45.dense_output = patched
    try:
        stopped = _system(
            _parameters(lower_stop_rad=-1.2, upper_stop_rad=contact_angle),
            blade_count=1,
            inertia=_inertia(1.0e-2),
        )
        normalized = (contact_time - float(dense.t_old)) / float(dense.h)
        contact_omega = _float_quartic_value(_ILL_CONDITIONED_Y, q, normalized)
        assert contact_omega >= OMEGA_MIN
        with pytest.raises(CoupledDomainExit):
            solve_coupled_transient(
                _request(
                    stopped,
                    actuation=_history(0.0, 0.002),
                    initial_angle_rad=0.0,
                    initial_angular_velocity_rad_s=2.0,
                    initial_omega_rad_s=OMEGA_MIN * 2.0,
                    motor_evaluator=_motor(0.0),
                    aero_evaluator=_aero(0.0),
                    controls=_one_step_controls(),
                )
            )
    finally:
        coupled_transient.RK45.dense_output = original


def test_interior_fold_peak_and_trough_use_the_same_real_audit() -> None:
    audit = coupled_transient._audit_dense_model_domain
    with pytest.raises(CoupledDomainExit):
        audit(_quartic((1.2, 0.0, OMEGA_MIN + 1.0), ((2.0, -2.0), (0.0,), (0.0,))), 0.0, 1.0)
    with pytest.raises(CoupledDomainExit):
        audit(_quartic((-1.2, 0.0, OMEGA_MIN + 1.0), ((-2.0, 2.0), (0.0,), (0.0,))), 0.0, 1.0)
    inside = _quartic((0.2, 0.0, OMEGA_MIN + 1.0), (_ILL_CONDITIONED_Q, (0.0,), (0.0,)))
    audit(inside, 0.399, _ILL_CONDITIONED_X_END)
    on_limit = _quartic((1.707329674214102, 0.0, OMEGA_MIN + 1.0), (_ILL_CONDITIONED_Q, (0.0,), (0.0,)))
    with pytest.raises(CoupledDomainExit):
        audit(on_limit, 0.0, _ILL_CONDITIONED_X_END)


def test_multiple_and_lower_degree_derivative_roots_stay_fail_closed() -> None:
    audit = coupled_transient._audit_dense_model_domain
    # Triple real root: endpoints stay above the floor, the flat minimum does not.
    lead = Fraction(1)
    d0, d1, d2, d3 = [lead * value for value in (Fraction(-1, 8), Fraction(3, 4), Fraction(-3, 2), Fraction(1))]
    triple = tuple(float(value) for value in (d0, d1 / 2, d2 / 3, d3 / 4))
    with pytest.raises(CoupledDomainExit):
        audit(_quartic((0.0, 0.0, OMEGA_MIN + 0.01), ((0.0,), (0.0,), triple)), 0.0, 1.0)
    audit(_quartic((0.0, 0.0, OMEGA_MIN + 1.0), ((0.0,), (0.0,), triple)), 0.0, 1.0)

    # Double root is a stationary inflection. A monotone safe segment stays inside.
    inflection = tuple(float(value) for value in (Fraction(1, 4), Fraction(-1, 2), Fraction(1, 3), Fraction(0)))
    audit(_quartic((0.0, 0.0, OMEGA_MIN + 1.0), ((0.0,), (0.0,), inflection)), 0.0, 1.0)

    # Identically linear derivative, then a quadratic derivative after a zero leading coeff.
    audit(_quartic((0.0, 0.0, OMEGA_MIN + 1.0), ((0.0,), (0.0,), (1.0,))), 0.0, 1.0)
    with pytest.raises(CoupledDomainExit):
        audit(_quartic((0.0, 0.0, OMEGA_MIN - 0.5), ((0.0,), (0.0,), (1.0,))), 0.0, 1.0)
    audit(_quartic((0.2, 0.0, OMEGA_MIN + 1.0), ((0.0,), (0.0,), (0.0, 0.1, -0.1))), 0.0, 1.0)


def test_interior_speed_floor_and_one_real_derivative_root() -> None:
    """Equality at an interior speed minimum is legal; a simple real minimum is not."""
    audit = coupled_transient._audit_dense_model_domain
    flat_min = (-0.125, 0.375, -0.5, 0.25)
    level = float(Fraction(OMEGA_MIN) + Fraction(1, 64))
    audit(_quartic((0.0, 0.0, level), ((0.0,), (0.0,), flat_min)), 0.0, 1.0)
    with pytest.raises(CoupledDomainExit):
        audit(_quartic((0.0, 0.0, level - 1.0e-6), ((0.0,), (0.0,), flat_min)), 0.0, 1.0)

    # d(x) = (x - 0.4)(x^2 + 1): one real root and a complex pair.
    simple = (-0.4, 0.5, -0.4 / 3.0, 0.25)
    with pytest.raises(CoupledDomainExit):
        audit(_quartic((0.0, 0.0, OMEGA_MIN + 0.05), ((0.0,), (0.0,), simple)), 0.0, 1.0)


def test_irrational_interior_speed_floor_is_allowed() -> None:
    """x^4 - x^2 is minimized at 1/sqrt(2) with increment exactly -1/4."""
    audit = coupled_transient._audit_dense_model_domain
    coefficients = (0.0, -1.0, 0.0, 1.0)
    level = float(Fraction(OMEGA_MIN) + Fraction(1, 4))
    assert Fraction(level) == Fraction(OMEGA_MIN) + Fraction(1, 4)
    audit(_quartic((0.0, 0.0, level), ((0.0,), (0.0,), coefficients)), 0.0, 1.0)
    with pytest.raises(CoupledDomainExit):
        audit(
            _quartic((0.0, 0.0, math.nextafter(level, 0.0)), ((0.0,), (0.0,), coefficients)),
            0.0,
            1.0,
        )
    peak = (0.0, 1.0, 0.0, -1.0)
    fold_level = float(Fraction(FOLD_LIMIT_RAD) - Fraction(1, 4))
    assert Fraction(fold_level) == Fraction(FOLD_LIMIT_RAD) - Fraction(1, 4)
    with pytest.raises(CoupledDomainExit):
        audit(_quartic((fold_level, 0.0, OMEGA_MIN + 1.0), (peak, (0.0,), (0.0,))), 0.0, 1.0)
    audit(
        _quartic((math.nextafter(fold_level, 0.0), 0.0, OMEGA_MIN + 1.0), (peak, (0.0,), (0.0,))),
        0.0,
        1.0,
    )


def test_root_isolation_budget_exhaustion_fails_closed() -> None:
    derivative = coupled_transient._trim_polynomial(
        tuple(Fraction(value) for value in (-0.125, 0.75, -1.5, 1.0))
    )
    with pytest.raises(CoupledTransientFailure, match="unresolved") as caught:
        coupled_transient._isolate_real_roots(derivative, Fraction(0), Fraction(1), [0])
    assert type(caught.value) is CoupledTransientFailure


def test_contact_before_a_later_dense_excursion_stays_terminal() -> None:
    theta0 = 1.5653333333333335
    speed = OMEGA_MIN * 5.0

    def motor(time_s, theta, theta_dot, omega):
        del time_s, theta_dot
        assert abs(theta) < FOLD_LIMIT_RAD and omega >= OMEGA_MIN
        return MotorEvaluation(0.0)

    def aero(time_s, theta, theta_dot, omega):
        del time_s, theta_dot
        assert abs(theta) < FOLD_LIMIT_RAD and omega >= OMEGA_MIN
        return AeroEvaluation(0.0, 0.0, "analytic", "software_fixture")

    upper = solve_coupled_transient(
        _request(
            _system(
                _parameters(lower_stop_rad=-1.65, upper_stop_rad=1.569),
                blade_count=1,
                inertia=_inertia(1.0e-2),
            ),
            actuation=_history(-0.8, 0.002),
            initial_angle_rad=theta0,
            initial_angular_velocity_rad_s=10.0,
            initial_omega_rad_s=speed,
            motor_evaluator=motor,
            aero_evaluator=aero,
            controls=_one_step_controls(),
        )
    )
    assert upper.status == "first_contact_terminal"
    assert upper.contact is not None and upper.contact.stop == "upper"
    assert abs(upper.contact.angle_rad) < FOLD_LIMIT_RAD

    lower = solve_coupled_transient(
        _request(
            _system(
                _parameters(lower_stop_rad=-1.569, upper_stop_rad=1.65),
                blade_count=1,
                inertia=_inertia(1.0e-2),
            ),
            actuation=_history(0.8, 0.002),
            initial_angle_rad=-theta0,
            initial_angular_velocity_rad_s=-10.0,
            initial_omega_rad_s=speed,
            motor_evaluator=motor,
            aero_evaluator=aero,
            controls=_one_step_controls(),
        )
    )
    assert lower.status == "first_contact_terminal"
    assert lower.contact is not None and lower.contact.stop == "lower"
    assert abs(lower.contact.angle_rad) < FOLD_LIMIT_RAD


def test_dense_excursion_before_contact_aborts() -> None:
    parameters = _parameters(
        mass_kg=0.001,
        cg_distance_m=0.001,
        hinge_inertia_kg_m2=1.0e-3,
        hinge_radius_m=0.05,
        upper_stop_rad=0.00085,
    )
    system = _system(parameters, blade_count=1, inertia=_inertia(1.0e-3))
    schur = coupled_mass_matrix(system, 0.0).schur_kg_m2
    slope = 20000.0
    peak = 0.0011
    omega0 = OMEGA_MIN + 0.01

    def motor(time_s, theta, theta_dot, omega):
        del theta_dot
        assert abs(theta) < FOLD_LIMIT_RAD and omega >= OMEGA_MIN
        return MotorEvaluation(schur * slope * (time_s - peak))

    def aero(time_s, theta, theta_dot, omega):
        del time_s, theta_dot
        assert abs(theta) < FOLD_LIMIT_RAD and omega >= OMEGA_MIN
        return AeroEvaluation(0.0, 0.0, "analytic", "software_fixture")

    with pytest.raises(CoupledDomainExit):
        solve_coupled_transient(
            _request(
                system,
                actuation=_history(0.0, 0.002),
                initial_angle_rad=0.0,
                initial_angular_velocity_rad_s=0.5,
                initial_omega_rad_s=omega0,
                motor_evaluator=motor,
                aero_evaluator=aero,
                controls=_one_step_controls(),
            )
        )


def test_interior_run_without_a_dense_excursion_still_completes() -> None:
    result = solve_coupled_transient(_request())
    assert result.status == "completed"
    assert all(abs(sample.theta_rad) < FOLD_LIMIT_RAD for sample in result.samples)
    assert all(sample.omega_rad_s >= OMEGA_MIN for sample in result.samples)


def _point_mass_system(i0: float, mass_kg: float = 0.02, cg_m: float = 0.01, radius_m: float = 0.08):
    inertia = mass_kg * cg_m**2
    return _system(
        _parameters(
            mass_kg=mass_kg,
            cg_distance_m=cg_m,
            hinge_inertia_kg_m2=inertia,
            hinge_radius_m=radius_m,
        ),
        blade_count=2,
        inertia=_inertia(i0, source="point-mass"),
    )


def test_unresolved_represented_mass_matrix_fails_closed() -> None:
    """Astra case: analytical Schur stays positive while the float matrix does not."""
    system = _point_mass_system(1.0e-20)
    mass_value = 0.02
    cg = 0.01
    radius = 0.08
    inertia = mass_value * cg**2
    count = 2
    cosine = 1.0
    coupling = mass_value * radius * cg
    gap = inertia - mass_value * cg**2 * cosine**2
    determinant = (
        count * inertia * 1.0e-20
        + (count**2) * mass_value * radius**2 * gap
    )
    assert determinant > 0.0
    with pytest.raises(CoupledTransientFailure, match="unresolved"):
        coupled_mass_matrix(system, 0.0)
    with pytest.raises(CoupledTransientFailure, match="unresolved"):
        coupled_accelerations(
            system,
            theta=0.0,
            theta_dot=0.0,
            omega=OMEGA_MIN,
            motor_torque_nm=1.0e-12,
            aero_shaft_torque_nm=0.0,
            hinge_torque_nm=0.0,
        )


def test_resolved_small_inertia_and_point_mass_still_solve() -> None:
    resolved = coupled_mass_matrix(_point_mass_system(1.0e-8), 0.0)
    assert resolved.determinant > 0.0
    assert resolved.analytical_schur_kg_m2 > 0.0
    assert resolved.represented_pivot > 0.0
    assert resolved.schur_kg_m2 > 0.0
    solved = coupled_accelerations(
        _point_mass_system(1.0e-8),
        theta=0.0,
        theta_dot=0.0,
        omega=OMEGA_MIN,
        motor_torque_nm=1.0e-12,
        aero_shaft_torque_nm=0.0,
        hinge_torque_nm=0.0,
    )
    assert math.isfinite(solved.omega_dot_rad_s2)
    assert solved.mass_residual >= 0.0

    ordinary = coupled_accelerations(
        _point_mass_system(1.0e-4),
        theta=0.2,
        theta_dot=0.0,
        omega=OMEGA_MIN,
        motor_torque_nm=1.0e-4,
        aero_shaft_torque_nm=0.0,
        hinge_torque_nm=0.0,
    )
    assert math.isfinite(ordinary.theta_ddot_rad_s2)
    reference = coupled_accelerations(
        _system(),
        theta=-0.2,
        theta_dot=0.1,
        omega=30.0,
        motor_torque_nm=0.01,
        aero_shaft_torque_nm=0.002,
        hinge_torque_nm=0.001,
    )
    for scale in (1.0e-6, 1.0e-3, 1.0, 1.0e3, 1.0e6):
        scaled = coupled_accelerations(
            _system(
                _parameters(mass_kg=0.02 * scale, hinge_inertia_kg_m2=1.0e-4 * scale),
                inertia=_inertia(1.0e-3 * scale),
            ),
            theta=-0.2,
            theta_dot=0.1,
            omega=30.0,
            motor_torque_nm=0.01 * scale,
            aero_shaft_torque_nm=0.002 * scale,
            hinge_torque_nm=0.001 * scale,
        )
        assert scaled.omega_dot_rad_s2 == pytest.approx(reference.omega_dot_rad_s2, rel=1.0e-8, abs=1.0e-8)
        assert scaled.theta_ddot_rad_s2 == pytest.approx(reference.theta_ddot_rad_s2, rel=1.0e-8, abs=1.0e-8)


def test_mass_residual_has_no_one_newton_meter_floor() -> None:
    row_backward_error = coupled_transient._row_backward_error
    with pytest.raises(CoupledTransientFailure, match="backward-error"):
        row_backward_error(4.64e-12, 1.0e-12, (1.0e-12,))
    assert row_backward_error(0.0, 0.0, (0.0, 0.0)) == 0.0
    with pytest.raises(CoupledTransientFailure, match="backward-error"):
        row_backward_error(1.0e-12, 0.0, (0.0,))
    with pytest.raises((CoupledTransientError, CoupledTransientFailure)):
        coupled_mass_matrix(_system(), float("nan"))
    with pytest.raises(CoupledTransientFailure):
        coupled_mass_matrix(
            _system(
                _parameters(
                    mass_kg=1.0e20,
                    cg_distance_m=1.0e50,
                    hinge_inertia_kg_m2=1.0e200,
                    hinge_radius_m=1.0e20,
                ),
                inertia=_inertia(1.0e200),
            ),
            0.0,
        )
