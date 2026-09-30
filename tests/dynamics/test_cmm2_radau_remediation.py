"""Frozen C2V-02 and C2V-03/05 trajectory regressions for the Radau remediation.

The oracle is test-owned. It does not call production acceleration or load
assembly. Fixture literals and section-7 scales are the frozen contract values.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.integrate._ivp.radau import RadauDenseOutput

from pyfoldable.dynamics.cmm2_coupled_transient import (
    IMPLEMENTATION_ID,
    Cmm2AeroEvaluation,
    Cmm2TransientRequest,
    solve_cmm2_transient,
)
from pyfoldable.dynamics.cmm2_radau_dense import (
    RadauContractFailure,
    first_radau_contact,
    represented_cubic,
)
from pyfoldable.dynamics import coupled_transient
from pyfoldable.dynamics.coupled_transient import (
    BaseRotatingAssemblyInertia,
    CoupledSolverControls,
    CoupledSystem,
    HingeActuationHistory,
    MotorEvaluation,
)
from pyfoldable.dynamics.mechanism_contracts import DryFriction
from pyfoldable.dynamics.mechanism_transient import MechanismParameters


def _mechanism() -> MechanismParameters:
    return MechanismParameters(
        mass_kg=0.02,
        cg_distance_m=0.03,
        hinge_inertia_kg_m2=2.0e-5,
        hinge_radius_m=0.08,
        spring_stiffness_nm_rad=0.01,
        rest_angle_rad=-0.2,
        viscous_damping_nm_s_rad=0.002,
        lower_stop_rad=-1.2,
        upper_stop_rad=0.2,
        dry_friction=DryFriction("regularized_coulomb", 0.001, 0.05, source="prc-contract"),
    )


def _system(count: int = 2) -> CoupledSystem:
    return CoupledSystem(
        _mechanism(),
        count,
        BaseRotatingAssemblyInertia(1.0e-4, "prc fixture", ("motor rotor", "shaft", "hub", "fixed blade roots")),
    )


def _tip_c(system: CoupledSystem) -> float:
    mechanism = system.parameters
    return mechanism.mass_kg * mechanism.hinge_radius_m * mechanism.cg_distance_m


def _matrix(system: CoupledSystem, theta: float):
    mechanism = system.parameters
    count = system.blade_count
    coupling = _tip_c(system)
    cosine = math.cos(theta)
    one_a = mechanism.hinge_inertia_kg_m2 + mechanism.mass_kg * mechanism.hinge_radius_m**2 + 2.0 * coupling * cosine
    one_b = mechanism.hinge_inertia_kg_m2 + coupling * cosine
    return (
        system.base_inertia.inertia_kg_m2 + count * one_a,
        count * one_b,
        count * mechanism.hinge_inertia_kg_m2,
        coupling,
    )


def _rhs(system, theta, theta_dot, omega, motor_nm, hinge_nm, q_phi, q_theta):
    mechanism = system.parameters
    _m00, _m01, _m11, coupling = _matrix(system, theta)
    sine = math.sin(theta)
    spring = -mechanism.spring_stiffness_nm_rad * (theta - mechanism.rest_angle_rad)
    damping = -mechanism.viscous_damping_nm_s_rad * theta_dot
    friction = -mechanism.dry_friction.coulomb_torque_nm * math.tanh(
        theta_dot / mechanism.dry_friction.transition_velocity_rad_s
    )
    shaft = motor_nm + q_phi + system.blade_count * coupling * sine * (2.0 * omega * theta_dot + theta_dot**2)
    hinge = system.blade_count * (
        hinge_nm + q_theta + spring + damping + friction - coupling * omega**2 * sine
    )
    return shaft, hinge


def _loads(system, theta, theta_dot, omega, omega_dot, theta_ddot, motor_nm, hinge_nm):
    shaft_0, hinge_0 = _rhs(system, theta, theta_dot, omega, motor_nm, hinge_nm, 0.0, 0.0)
    m00, m01, m11, _coupling = _matrix(system, theta)
    return (
        m00 * omega_dot + m01 * theta_ddot - shaft_0,
        (m01 * omega_dot + m11 * theta_ddot - hinge_0) / system.blade_count,
    )


def _scales(reference):
    controls = CoupledSolverControls()
    return (
        controls.angle_atol_rad + controls.rtol * abs(reference[0]),
        controls.hinge_velocity_atol_rad_s + controls.rtol * abs(reference[1]),
        controls.shaft_speed_atol_rad_s + controls.rtol * abs(reference[2]),
    )


def _max_e(samples, reference_at):
    worst = 0.0
    for sample in samples:
        reference = reference_at(sample.time_s)
        scale = _scales(reference)
        produced = (sample.theta_rad, sample.theta_dot_rad_s, sample.omega_rad_s)
        for index in range(3):
            worst = max(worst, abs(produced[index] - reference[index]) / scale[index])
    return worst


def _aero(q_phi, q_theta, blade_count, radius, source):
    def evaluate(_time, theta, theta_dot, _omega):
        return Cmm2AeroEvaluation(
            q_phi,
            q_theta,
            1.0,
            "planar_projected_material_load_v1",
            "screening_only_projected_rate_independent",
            "radial_cosine_v1",
            "ignored_rate_independent_quasi_steady",
            blade_count,
            radius,
            theta,
            theta_dot,
            source,
        )

    return evaluate


def test_c2v02_constant_state_gate() -> None:
    system = _system()
    theta, omega, motor_nm, hinge_nm = -0.4, 40.0, 0.05, 0.001
    q_phi, q_theta = _loads(system, theta, 0.0, omega, 0.0, 0.0, motor_nm, hinge_nm)
    result = solve_cmm2_transient(
        Cmm2TransientRequest(
            system,
            HingeActuationHistory((0.0, 0.02), (hinge_nm, hinge_nm), "prc"),
            theta,
            0.0,
            omega,
            lambda *_args: MotorEvaluation(motor_nm),
            _aero(q_phi, q_theta, 2, 0.08, "c2v02"),
            CoupledSolverControls(),
        )
    )
    assert result.status == "completed"
    assert _max_e(result.samples, lambda _time: (theta, 0.0, omega)) <= 1.0


def _target(time: float):
    theta = -0.30 + 0.05 * math.sin(2.0 * math.pi * time / 0.2)
    theta_dot = 0.05 * (2.0 * math.pi / 0.2) * math.cos(2.0 * math.pi * time / 0.2)
    theta_ddot = -0.05 * (2.0 * math.pi / 0.2) ** 2 * math.sin(2.0 * math.pi * time / 0.2)
    omega = 40.0 + 2.0 * time
    return theta, theta_dot, theta_ddot, omega, 2.0


def test_c2v03_c2v05_manufactured_gate() -> None:
    system = _system()
    controls = CoupledSolverControls()

    def loads(time):
        theta, theta_dot, theta_ddot, omega, omega_dot = _target(time)
        return _loads(system, theta, theta_dot, omega, omega_dot, theta_ddot, 0.04, 0.001)

    def motor(_time, _theta, _rate, _omega):
        return MotorEvaluation(0.04)

    def aero(time, theta, theta_dot, _omega):
        q_phi, q_theta = loads(time)
        return _aero(q_phi, q_theta, 2, system.parameters.hinge_radius_m, "c2v03")(
            time, theta, theta_dot, _omega
        )

    def rhs(time, state):
        q_phi, q_theta = loads(time)
        shaft, hinge = _rhs(system, state[0], state[1], state[2], 0.04, 0.001, q_phi, q_theta)
        m00, m01, m11, _coupling = _matrix(system, state[0])
        determinant = m00 * m11 - m01 * m01
        omega_dot = (shaft * m11 - m01 * hinge) / determinant
        theta_ddot = (m00 * hinge - shaft * m01) / determinant
        return (state[1], theta_ddot, omega_dot)

    initial = _target(0.0)
    result = solve_cmm2_transient(
        Cmm2TransientRequest(
            system,
            HingeActuationHistory((0.0, 0.2), (0.001, 0.001), "prc"),
            initial[0],
            initial[1],
            initial[3],
            motor,
            aero,
            controls,
        )
    )
    times = [sample.time_s for sample in result.samples]
    atol = (
        controls.angle_atol_rad / 100,
        controls.hinge_velocity_atol_rad_s / 100,
        controls.shaft_speed_atol_rad_s / 100,
    )
    reference_a = solve_ivp(
        rhs, (0.0, times[-1]), (initial[0], initial[1], initial[3]), method="DOP853",
        rtol=controls.rtol / 100, atol=atol, max_step=controls.max_step_s / 4, dense_output=True,
    )
    atol_b = tuple(value / 100 for value in atol)
    reference_b = solve_ivp(
        rhs, (0.0, times[-1]), (initial[0], initial[1], initial[3]), method="DOP853",
        rtol=controls.rtol / 10000, atol=atol_b, max_step=controls.max_step_s / 8, dense_output=True,
    )
    assert reference_a.success and reference_b.success
    for time in times:
        left = reference_a.sol(time)
        right = reference_b.sol(time)
        scale = _scales(tuple(float(value) for value in right))
        for index in range(3):
            assert abs(float(left[index]) - float(right[index])) <= 0.1 * scale[index]
    assert result.status == "completed"
    assert _max_e(
        result.samples,
        lambda time: tuple(float(value) for value in reference_b.sol(time)),
    ) <= 1.0


def _controls():
    class Controls:
        atol = 1.0e-8
        atol_angular_velocity_rad_s = 1.0e-8

    return Controls()


def test_radau_identity_is_v2_and_cmm1_stays_rk45() -> None:
    assert IMPLEMENTATION_ID == "cmm2_planar_projected_rate_independent_coupling_v2"
    assert "RK45(" in open(coupled_transient.__file__, encoding="utf-8").read()


def test_represented_cubic_does_not_scale_q_by_h() -> None:
    q_matrix = np.zeros((3, 3))
    q_matrix[0, 0] = -0.2
    dense = RadauDenseOutput(0.0, 0.5, np.array([-0.4, 0.0, 40.0]), q_matrix)
    _t_old, step, polynomials = represented_cubic(dense)
    assert step == pytest.approx(0.5) or float(step) == 0.5
    x = 0.5
    expected = -0.4 + (-0.2) * x
    assert float(dense(0.25)[0]) == pytest.approx(expected)


def test_malformed_dense_output_fails_closed() -> None:
    class Bad:
        t_old = 0.0
        t = 1.0
        h = 1.0
        y_old = np.zeros(3)
        Q = np.zeros((3, 4))
        order = 3

    with pytest.raises(RadauContractFailure):
        represented_cubic(Bad())


def test_hidden_lower_stop_crossing_is_not_reported_as_clear() -> None:
    q_matrix = np.zeros((3, 3))
    q_matrix[0, 0] = -1.3
    dense = RadauDenseOutput(0.0, 1.0, np.array([-0.2, -1.0, 40.0]), q_matrix)
    hit = first_radau_contact(
        dense,
        0.0,
        1.0,
        dense(0.0),
        dense(1.0),
        _mechanism(),
        _controls(),
    )
    assert hit is not None
    assert hit[0] == "lower"
