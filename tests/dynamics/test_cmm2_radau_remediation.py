"""Frozen C2V-02 and C2V-03/05 trajectory regressions for the Radau remediation.

The oracle is test-owned. It does not call production acceleration or load
assembly. Fixture literals and section-7 scales are the frozen contract values.
"""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.integrate._ivp.radau import RadauDenseOutput

from pyfoldable.dynamics.cmm2_coupled_transient import (
    IMPLEMENTATION_ID,
    Cmm2AeroEvaluation,
    Cmm2TransientFailure,
    Cmm2TransientRequest,
    solve_cmm2_transient,
)
from pyfoldable.dynamics.cmm2_radau_dense import (
    RadauContractFailure,
    RadauDomainExit,
    audit_represented_domain,
    first_radau_contact,
    represented_cubic,
)
from pyfoldable.dynamics import coupled_transient
from pyfoldable.dynamics.coupled_transient import (
    FOLD_LIMIT_RAD,
    BaseRotatingAssemblyInertia,
    CoupledSolverControls,
    CoupledSystem,
    HingeActuationHistory,
    MotorEvaluation,
)
from pyfoldable.dynamics.mechanism_contracts import DryFriction
from pyfoldable.dynamics.mechanism_transient import MechanismParameters


def _mechanism(lower: float = -1.2, upper: float = 0.2) -> MechanismParameters:
    return MechanismParameters(
        mass_kg=0.02,
        cg_distance_m=0.03,
        hinge_inertia_kg_m2=2.0e-5,
        hinge_radius_m=0.08,
        spring_stiffness_nm_rad=0.01,
        rest_angle_rad=-0.2,
        viscous_damping_nm_s_rad=0.002,
        lower_stop_rad=lower,
        upper_stop_rad=upper,
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


def _controls(atol: float = 1.0e-8):
    class Controls:
        pass

    controls = Controls()
    controls.atol = atol
    controls.atol_angular_velocity_rad_s = atol
    return controls


def test_radau_identity_is_v2_and_cmm1_stays_rk45() -> None:
    assert IMPLEMENTATION_ID == "cmm2_planar_projected_rate_independent_coupling_v2"
    assert "RK45(" in open(coupled_transient.__file__, encoding="utf-8").read()


def test_represented_cubic_does_not_scale_q_by_h() -> None:
    q_matrix = np.zeros((3, 3))
    q_matrix[0, 0] = -0.2
    dense = RadauDenseOutput(0.0, 0.5, np.array([-0.4, 0.0, 40.0]), q_matrix)
    _t_old, step, polynomials = represented_cubic(dense)
    assert float(step) == 0.5
    assert float(polynomials[0][1]) == -0.2
    assert float(polynomials[0][1]) != -0.2 * 0.5
    assert float(polynomials[0][0] + polynomials[0][1] * 0.5) == pytest.approx(-0.5)


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


def test_interior_stop_breach_is_not_a_clear_step() -> None:
    q_matrix = np.zeros((3, 3))
    q_matrix[0, 0] = 6.4
    q_matrix[0, 1] = -20.0
    q_matrix[0, 2] = 40.0 / 3.0
    dense = RadauDenseOutput(0.0, 1.0, np.array([-0.5, 0.0, 40.0]), q_matrix)
    try:
        hit = first_radau_contact(
            dense, 0.0, 1.0, dense(0.0), dense(1.0), _mechanism(), _controls()
        )
    except RadauContractFailure as exc:
        assert "breach" in str(exc)
    else:
        assert hit is not None


def _dense(t_old, t, y_old, q_matrix):
    return RadauDenseOutput(t_old, t, np.array(y_old, dtype=float), np.array(q_matrix, dtype=float))


def test_exact_fold_equality_is_not_clear() -> None:
    q_matrix = np.zeros((3, 3))
    q_matrix[0] = (0.75, 0.0, -1.0)
    dense = _dense(0.0, 1.0, (FOLD_LIMIT_RAD - 0.25, 0.0, 40.0), q_matrix)
    with pytest.raises(RadauDomainExit):
        audit_represented_domain(dense, 0.0, 1.0, deployed_angle=0.0)


def test_exact_tolerance_contact_is_retained() -> None:
    atol = 2.0**-20
    q_matrix = np.zeros((3, 3))
    q_matrix[0] = (-0.75, 0.0, 1.0)
    dense = _dense(0.0, 1.0, (0.25 + 8.0 * atol, 0.0, 40.0), q_matrix)
    hit = first_radau_contact(
        dense, 0.0, 1.0, dense(0.0), dense(1.0), _mechanism(0.0, 1.2), _controls(atol)
    )
    assert hit is not None
    assert hit[0] == "lower"


def test_rate_just_above_velocity_tolerance_fails_the_breach() -> None:
    atol = 2.0**-20
    q_matrix = np.zeros((3, 3))
    q_matrix[0, 0] = -1.5
    q_matrix[1, 0] = 3.0
    dense = _dense(0.0, 1.0, (0.5, -1.0 + 2.0**-17 + 2.0**-50, 40.0), q_matrix)
    with pytest.raises(RadauContractFailure, match="breach"):
        first_radau_contact(
            dense, 0.0, 1.0, dense(0.0), dense(1.0), _mechanism(0.0, 1.2), _controls(atol)
        )


def test_out_of_step_audit_is_rejected() -> None:
    dense = _dense(0.0, 1.0, (0.1, 0.0, 40.0), np.zeros((3, 3)))
    with pytest.raises(RadauContractFailure, match="accepted step"):
        audit_represented_domain(dense, -1.0, 2.0, deployed_angle=0.0)


def test_distinct_roots_do_not_collapse_to_one_public_time() -> None:
    tiny_a = 2.0**-60
    tiny_b = 2.0**-59
    q_matrix = np.zeros((3, 3))
    q_matrix[0, 0] = -(tiny_a + tiny_b)
    q_matrix[0, 1] = 1.0
    dense = _dense(1.0, 2.0, (tiny_a * tiny_b, 0.0, 40.0), q_matrix)
    with pytest.raises(RadauContractFailure):
        first_radau_contact(
            dense,
            1.0,
            2.0,
            dense(1.0),
            dense(2.0),
            _mechanism(0.0, 1.2),
            _controls(),
            origin=0.0,
            last_published=0.0,
        )


def test_public_time_rounded_to_the_origin_is_rejected() -> None:
    q_matrix = np.zeros((3, 3))
    q_matrix[0, 0] = -0.5
    q_matrix[1, 0] = -250.0
    origin = float(2**44)
    dense = _dense(0.0, 0.002, (-0.2, -250.0, 40.0), q_matrix)
    with pytest.raises(RadauContractFailure):
        first_radau_contact(
            dense,
            0.0,
            0.002,
            dense(0.0),
            dense(0.002),
            _mechanism(-0.5, 0.2),
            _controls(),
            origin=origin,
            last_published=origin,
        )


def test_public_rounding_does_not_hide_a_shaft_exit() -> None:
    q_matrix = np.zeros((3, 3))
    q_matrix[2, 1] = -140.0
    q_matrix[2, 2] = 140.0 / 1.2
    dense = _dense(0.0, 0.002, (-0.2, 0.0, 40.0), q_matrix)
    with pytest.raises(RadauDomainExit):
        audit_represented_domain(
            dense, 0.0, 0.002, deployed_angle=0.0, origin=float(2**43)
        )


def test_refinement_count_persists_on_the_same_bracket() -> None:
    from pyfoldable.dynamics.cmm2_radau_dense import RootBudget, _refine_sign_change

    budget = RootBudget(800)
    polynomial = (Fraction(-1, 3), Fraction(1))
    _refine_sign_change(polynomial, Fraction(0), Fraction(1), budget)
    assert budget.refinements > 0
    with pytest.raises(RadauContractFailure, match="refinement"):
        _refine_sign_change(polynomial, Fraction(0), Fraction(1), budget)
    assert budget.refinements > 80


def test_contact_work_is_shared_across_stops() -> None:
    dense = _dense(0.0, 1.0, (-0.2, 0.0, 40.0), np.zeros((3, 3)))
    with pytest.raises(RadauContractFailure, match="budget"):
        first_radau_contact(
            dense,
            0.0,
            1.0,
            dense(0.0),
            dense(1.0),
            _mechanism(),
            _controls(),
            origin=0.0,
            last_published=0.0,
            work_limit=1,
        )
    assert (
        first_radau_contact(
            dense,
            0.0,
            1.0,
            dense(0.0),
            dense(1.0),
            _mechanism(),
            _controls(),
            origin=0.0,
            last_published=0.0,
        )
        is None
    )


def test_domain_work_is_shared_by_theta_and_omega() -> None:
    dense = _dense(0.0, 1.0, (0.1, 0.0, 40.0), np.zeros((3, 3)))
    used = audit_represented_domain(dense, 0.0, 1.0, deployed_angle=0.0)
    assert used > 1
    with pytest.raises(RadauContractFailure, match="budget"):
        audit_represented_domain(dense, 0.0, 1.0, deployed_angle=0.0, work_limit=used - 1)


def test_refinement_debits_the_shared_work_counter() -> None:
    from pyfoldable.dynamics.cmm2_radau_dense import RootBudget, _refine_sign_change

    budget = RootBudget(30)
    with pytest.raises(RadauContractFailure, match="budget"):
        _refine_sign_change((Fraction(-1, 3), Fraction(1)), Fraction(0), Fraction(1), budget)
    assert budget.used > 30
    assert budget.refinements > 30


def test_isolation_depth_above_32_fails() -> None:
    from pyfoldable.dynamics.cmm2_radau_dense import RootBudget, _isolate_real_roots

    budget = RootBudget(800)
    with pytest.raises(RadauContractFailure, match="depth"):
        _isolate_real_roots((Fraction(-1, 2), Fraction(1)), Fraction(0), Fraction(1), budget, 33)


def test_unseparated_roots_fail_at_the_width_floor() -> None:
    from pyfoldable.dynamics.cmm2_radau_dense import RootBudget, _isolate_real_roots

    right = Fraction(1, 1 << 80)
    center = Fraction(1, 1 << 81)
    offset = Fraction(3, 1 << 200)
    polynomial = (center * center - offset, -2 * center, Fraction(1))
    budget = RootBudget(800)
    with pytest.raises(RadauContractFailure, match="width"):
        _isolate_real_roots(polynomial, Fraction(0), right, budget)


def test_cubic_keeps_every_exact_rational_root_and_the_earliest() -> None:
    q_matrix = np.zeros((3, 3))
    q_matrix[0] = (22.0, -48.0, 32.0)
    dense = _dense(0.0, 1.0, (-3.0, 0.0, 40.0), q_matrix)
    hit = first_radau_contact(
        dense, 0.0, 1.0, dense(0.0), dense(1.0), _mechanism(0.0, 100.0), _controls()
    )
    assert hit is not None
    assert hit[0] == "lower"
    assert hit[1] == 0.25


def test_non_dyadic_cubic_roots_do_not_lose_the_earliest() -> None:
    q_matrix = np.zeros((3, 3))
    q_matrix[0] = (55.0, -150.0, 125.0)
    dense = _dense(0.0, 1.0, (-6.0, 0.0, 40.0), q_matrix)
    hit = first_radau_contact(
        dense, 0.0, 1.0, dense(0.0), dense(1.0), _mechanism(0.0, 100.0), _controls()
    )
    assert hit is not None
    assert hit[0] == "lower"
    assert abs(hit[1] - 0.2) < abs(hit[1] - 0.4)


def test_cubic_rational_root_identity_stays_exact() -> None:
    from pyfoldable.dynamics.cmm2_radau_dense import RootBudget, _locate_roots

    roots = _locate_roots(
        (Fraction(-1), Fraction(3), Fraction(-1), Fraction(3)),
        Fraction(0),
        Fraction(1),
        RootBudget(800),
    )
    assert [root.exact for root in roots] == [Fraction(1, 3)]


def test_irrational_tolerance_contact_is_kept() -> None:
    atol = 2.0**-12
    offset = (4.0 / 3.0) * math.sqrt(2.0 / 3.0) + 0.001
    q_matrix = np.zeros((3, 3))
    q_matrix[0] = (-2.0, 0.0, 1.0)
    dense = _dense(0.0, 1.0, (offset, 0.0, 40.0), q_matrix)
    hit = first_radau_contact(
        dense, 0.0, 1.0, dense(0.0), dense(1.0), _mechanism(0.0, 5.0), _controls(atol)
    )
    assert hit is not None
    assert hit[0] == "lower"


def test_irrational_transverse_root_calls_brent(monkeypatch) -> None:
    from pyfoldable.dynamics import cmm2_radau_dense

    calls = {"count": 0}
    real = cmm2_radau_dense.brentq

    def wrapped(*args, **kwargs):
        calls["count"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(cmm2_radau_dense, "brentq", wrapped)
    q_matrix = np.zeros((3, 3))
    q_matrix[0, 2] = 2.0
    dense = _dense(0.0, 1.0, (-1.0, 0.0, 40.0), q_matrix)
    hit = first_radau_contact(
        dense, 0.0, 1.0, dense(0.0), dense(1.0), _mechanism(0.0, 5.0), _controls()
    )
    assert calls["count"] > 0
    assert hit is not None
    assert hit[0] == "lower"


def test_large_coefficient_rational_root_stays_exact() -> None:
    from pyfoldable.dynamics.cmm2_radau_dense import RootBudget, _locate_roots

    scale = Fraction(1 << 40)
    roots = _locate_roots(
        (-scale, 3 * scale, Fraction(-1), Fraction(3)),
        Fraction(0),
        Fraction(1),
        RootBudget(800),
    )
    assert [root.exact for root in roots] == [Fraction(1, 3)]
    q_matrix = np.zeros((3, 3))
    q_matrix[0] = (float(3 * scale), -1.0, 3.0)
    dense = _dense(0.0, 1.0, (float(-scale), 0.0, 40.0), q_matrix)
    hit = first_radau_contact(
        dense, 0.0, 1.0, dense(0.0), dense(1.0), _mechanism(0.0, 5.0), _controls()
    )
    assert hit is not None
    assert hit[1] == float(Fraction(1, 3))


def test_dyadic_root_near_zero_is_not_published_as_zero() -> None:
    from pyfoldable.dynamics.cmm2_radau_dense import RootBudget, _locate_roots

    scale = Fraction(1 << 50)
    roots = _locate_roots(
        (Fraction(-1), scale, Fraction(-1), scale),
        Fraction(0),
        Fraction(1),
        RootBudget(800),
    )
    assert [root.exact for root in roots] == [Fraction(1, 1 << 50)]
    q_matrix = np.zeros((3, 3))
    q_matrix[0] = (float(scale), -1.0, float(scale))
    dense = _dense(0.0, 1.0, (-1.0, 0.0, 40.0), q_matrix)
    hit = first_radau_contact(
        dense, 0.0, 1.0, dense(0.0), dense(1.0), _mechanism(0.0, 1.0e6), _controls()
    )
    assert hit is not None
    assert hit[1] == float(Fraction(1, 1 << 50))
    assert hit[1] != 0.0


def test_successful_candidate_order_is_debited() -> None:
    from pyfoldable.dynamics.cmm2_radau_dense import RootBudget, _Root, _order_candidates

    budget = RootBudget(800)
    candidates = [
        (_Root(Fraction(3, 10), Fraction(3, 10), Fraction(3, 10)), "upper", 0.2, 1.0e-7),
        (_Root(Fraction(7, 10), Fraction(7, 10), Fraction(7, 10)), "lower", -0.2, 1.0e-7),
    ]
    ordered = _order_candidates(candidates, budget)
    assert ordered[0][1] == "upper"
    assert budget.used > 0


def test_public_relative_fraction_extends_the_shaft_audit() -> None:
    from pyfoldable.dynamics.coupled_transient import OMEGA_MIN

    origin = 3 * 2**-55
    q_matrix = np.zeros((3, 3))
    q_matrix[0, 0] = -0.5
    q_matrix[2, 0] = -1.25
    q_matrix[2, 1] = 1.0
    dense = _dense(0.0, 1.0, (0.25, -1.0, OMEGA_MIN + 0.375), q_matrix)
    hit = first_radau_contact(
        dense,
        0.0,
        1.0,
        dense(0.0),
        dense(1.0),
        _mechanism(0.0, 1.2),
        _controls(),
        origin=origin,
        last_published=0.0,
    )
    assert hit is not None
    assert hit[1] == 0.5
    public = float(origin) + hit[1]
    assert public == float.fromhex("0x1.0000000000001p-1")
    assert Fraction(public) - Fraction(origin) == Fraction(1, 2) + Fraction(1, 2**55)
    with pytest.raises(RadauDomainExit):
        audit_represented_domain(
            dense,
            0.0,
            hit[1],
            deployed_angle=0.0,
            origin=origin,
            evaluation_time=hit[1],
        )


def test_out_of_window_neighbors_do_not_hide_direction_rejection() -> None:
    from pyfoldable.dynamics.cmm2_radau_dense import RootBudget, _Root, _convert_root

    root = _Root(left=Fraction(1, 2), right=Fraction(1, 2), exact=Fraction(1, 2))
    start = 0.5
    for _step in range(3):
        start = float(np.nextafter(start, 0.0))
    budget = RootBudget(800)
    with pytest.raises(RadauContractFailure, match="direction") as caught:
        _convert_root(
            0.0,
            None,
            Fraction(0),
            Fraction(1),
            root,
            (Fraction(-1, 2), Fraction(1)),
            (Fraction(1),),
            Fraction(1, 100000000),
            True,
            start,
            1.0,
            budget,
        )
    assert "conversion" not in str(caught.value)


def test_converted_public_time_must_preserve_direction() -> None:
    q_matrix = np.zeros((3, 3))
    q_matrix[0, 0] = -1.5
    q_matrix[1, 0] = -3.0
    dense = _dense(0.0, 1.0, (0.5, 1.0 + 2**-17, 40.0), q_matrix)
    hit = first_radau_contact(
        dense,
        0.0,
        1.0,
        dense(0.0),
        dense(1.0),
        _mechanism(0.0, 1.2),
        _controls(2**-20),
        origin=0.5,
        last_published=0.0,
    )
    certificate = hit[4]
    assert certificate.selected_relative.hex() == "0x1.5555555555556p-2"
    assert certificate.selected_public.hex() == "0x1.aaaaaaaaaaaabp-1"
    assert certificate.selected_option == 1
    assert certificate.neighbors[0].hex() == "0x1.5555555555555p-2"
    assert certificate.relative_target == Fraction(1, 3)
    assert not certificate.relative_cell.contains(certificate.relative_target)
    assert certificate.public_cell.contains(certificate.public_target)
    assert certificate.q_r == Fraction(1, 27021597764222976)
    assert certificate.q_p == 0
    limit = Fraction(1, 2**17)
    rate_0 = Fraction.from_float(1.0 + 2**-17)
    relative_xi = certificate.relative_exact
    public_xi = certificate.public_exact - certificate.origin
    assert rate_0 + Fraction(-3) * relative_xi - limit == Fraction(-1, 2**53)
    assert rate_0 + Fraction(-3) * public_xi - limit == Fraction(-1, 2**53)


def test_timestamp_is_certified_against_the_root_enclosure() -> None:
    """Synthetic allowance witness. It is not the C2V-07 fixture."""
    from pyfoldable.dynamics.cmm2_radau_dense import RootBudget, certify_representable_time

    polynomial = (Fraction(633318697224539, 4503599627370496), Fraction(0), Fraction(-1))
    t_old = Fraction(6748644041614695, 9007199254740992)
    step = Fraction(9007199254741, 4503599627370496)
    timestamp = float.fromhex("0x1.7fffffffff83ap-1")
    budget = RootBudget(800)
    certify_representable_time(polynomial, t_old, step, timestamp, budget)
    assert budget.refinements == 55
    assert budget.used == 62
    infeasible = RootBudget(800)
    with pytest.raises(RadauContractFailure, match="conversion"):
        certify_representable_time(
            polynomial,
            t_old,
            step,
            0.1,
            infeasible,
        )


def test_repeated_domain_audit_does_not_reset_the_interval_budget() -> None:
    from pyfoldable.dynamics.cmm2_radau_dense import AcceptedIntervalWork

    dense = _dense(0.0, 1.0, (0.1, 0.0, 40.0), np.zeros((3, 3)))
    work = AcceptedIntervalWork.create(domain_limit=4)
    measured = []
    with pytest.raises(RadauContractFailure, match="budget"):
        for _ in range(3):
            measured.append(
                audit_represented_domain(dense, 0.0, 1.0, deployed_angle=0.0, work=work)
            )
    assert measured == [4]


def test_producer_exhausts_one_shared_domain_budget(monkeypatch) -> None:
    import pyfoldable.dynamics.cmm2_coupled_transient as solver

    real_create = solver.AcceptedIntervalWork.create

    def tiny(contact_limit=800, domain_limit=800):
        del domain_limit
        return real_create(contact_limit=contact_limit, domain_limit=3)

    monkeypatch.setattr(solver.AcceptedIntervalWork, "create", tiny)
    system = _system()
    with pytest.raises(Cmm2TransientFailure, match="budget"):
        solve_cmm2_transient(
            Cmm2TransientRequest(
                system,
                HingeActuationHistory((0.0, 0.02), (0.001, 0.001), "budget-context"),
                -0.4,
                0.0,
                40.0,
                lambda *_args: MotorEvaluation(0.05),
                _aero(0.0, 0.0, 2, 0.08, "budget-context"),
                CoupledSolverControls(),
            )
        )


def test_refinement_exhaustion_does_not_return_a_later_candidate() -> None:
    from pyfoldable.dynamics.cmm2_radau_dense import AcceptedIntervalWork

    q_matrix = np.zeros((3, 3))
    q_matrix[0, 1] = -2.0
    dense = _dense(1.0, 1.00704, (1.0, -1.0, 40.0), q_matrix)
    arguments = (
        dense,
        1.0,
        1.00704,
        dense(1.0),
        dense(1.00704),
        _mechanism(0.0, 1.2),
        _controls(),
    )
    work = AcceptedIntervalWork.create()
    for _index in range(9):
        hit = first_radau_contact(
            *arguments,
            origin=0.0,
            last_published=1.0,
            work=work,
        )
        assert hit is not None
        assert work.contact.refinements <= 80
    from pyfoldable.dynamics.cmm2_radau_dense import _refine_sign_change

    with pytest.raises(RadauContractFailure, match="refinement"):
        while True:
            _refine_sign_change((Fraction(-1, 3), Fraction(1)), Fraction(0), Fraction(1), work.contact)
    with pytest.raises(RadauContractFailure, match="refinement"):
        first_radau_contact(*arguments, origin=0.0, last_published=1.0, work=work)
    with pytest.raises(RadauContractFailure, match="refinement"):
        audit_represented_domain(dense, 1.0, 1.00704, deployed_angle=0.0, work=work)


def test_interior_shaft_minimum_is_a_domain_exit() -> None:
    q_matrix = np.zeros((3, 3))
    q_matrix[2, 1] = -600.0
    q_matrix[2, 2] = 800.0
    dense = RadauDenseOutput(0.0, 1.0, np.array([0.0, 0.0, 40.0]), q_matrix)
    with pytest.raises(RadauDomainExit):
        audit_represented_domain(dense, 0.0, 1.0, deployed_angle=0.0)
