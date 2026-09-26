"""PR-A contract for isolated CMM-2 paired-load screening dynamics."""

from __future__ import annotations

import dataclasses
import math
import struct
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from pyfoldable.dynamics.coupled_transient import (
    AERO_HINGE_STATUS,
    MODEL_CLASS as CMM1_MODEL_CLASS,
    OMEGA_MIN,
    AeroEvaluation,
    BaseRotatingAssemblyInertia,
    CoupledSolverControls,
    CoupledSystem,
    CoupledTransientRequest,
    HingeActuationHistory,
    MotorEvaluation,
    coupled_accelerations,
    coupled_mass_matrix,
    solve_coupled_transient,
)
from pyfoldable.dynamics.cmm2_coupled_transient import (
    AERO_LOAD_QUALIFICATION,
    FOLD_LIMIT_RAD,
    HINGE_RATE_AERO_MODEL,
    IMPLEMENTATION_ID,
    LOAD_MAPPING_MODEL,
    MODEL_CLASS,
    PROJECTION_MODEL,
    Cmm2AeroEvaluation,
    Cmm2DomainExit,
    Cmm2TransientError,
    Cmm2TransientFailure,
    Cmm2TransientRequest,
    cmm2_coupled_accelerations,
    cmm2_instantaneous_power_w,
    solve_cmm2_transient,
)
from pyfoldable.dynamics.mechanism_contracts import DryFriction
from pyfoldable.dynamics.mechanism_transient import MechanismParameters


def _inertia(value: float = 1.0e-3) -> BaseRotatingAssemblyInertia:
    return BaseRotatingAssemblyInertia(
        value,
        "cmm2-test-i0",
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
    return HingeActuationHistory((0.0, end), (torque, torque), "cmm2-test-qh")


def _motor(torque: float):
    def evaluate(time_s, theta, theta_dot, omega):
        del time_s, theta, theta_dot, omega
        return MotorEvaluation(torque_nm=torque)

    return evaluate


def _loads(
    system: CoupledSystem,
    shaft_nm: float,
    hinge_nm: float,
    thrust_n: float = 0.1,
):
    def evaluate(time_s, theta, theta_dot, omega):
        del time_s, omega
        return Cmm2AeroEvaluation(
            whole_rotor_shaft_generalized_load_nm=shaft_nm,
            one_tip_hinge_generalized_load_nm=hinge_nm,
            thrust_n=thrust_n,
            load_mapping_model=LOAD_MAPPING_MODEL,
            qualification=AERO_LOAD_QUALIFICATION,
            projection_model=PROJECTION_MODEL,
            hinge_rate_aerodynamic_model=HINGE_RATE_AERO_MODEL,
            blade_count=system.blade_count,
            hinge_radius_m=system.parameters.hinge_radius_m,
            theta_rad=theta,
            hinge_rate_rad_s=theta_dot,
            source_id="analytic-pr-a",
        )

    return evaluate


def _request(system=None, **overrides) -> Cmm2TransientRequest:
    bound = system or _system()
    values = dict(
        system=bound,
        actuation=_history(),
        initial_angle_rad=-0.2,
        initial_angular_velocity_rad_s=0.0,
        initial_omega_rad_s=OMEGA_MIN * 2.0,
        motor_evaluator=_motor(0.0),
        aero_evaluator=_loads(bound, 0.0, 0.0),
    )
    values.update(overrides)
    return Cmm2TransientRequest(**values)


# The helper rejects a 64-ULP allowance. Callers must pass a fixture-specific
# bound. That bound is not a claim that every CMM-2 evaluation lies within it.
_MAX_STATED_ULPS = 16


def _ordered_binary64(value: float) -> int:
    """Map a finite binary64 value onto an integer that follows numeric order.

    Negative encodings are reflected so increasing integers track increasing
    values, including across zero. Positive and negative zero remain distinct
    here; ``_ulp_distance`` treats them as equal before using this map.
    """
    bits = struct.unpack(">Q", struct.pack(">d", value))[0]
    if bits & (1 << 63):
        return (~bits) & ((1 << 64) - 1)
    return bits | (1 << 63)


def _ulp_distance(actual: float, expected: float) -> int:
    """Exact count of binary64 steps between two finite values."""
    if (
        isinstance(actual, bool)
        or isinstance(expected, bool)
        or not isinstance(actual, float)
        or not isinstance(expected, float)
    ):
        raise AssertionError("ULP distance requires binary64 floats.")
    if not math.isfinite(actual) or not math.isfinite(expected):
        raise AssertionError("ULP distance rejects nonfinite values.")
    if actual == expected:
        return 0
    return abs(_ordered_binary64(actual) - _ordered_binary64(expected))


def _within_ulps(actual: float, expected: float, *, ulps: int) -> bool:
    if isinstance(ulps, bool) or not isinstance(ulps, int) or not 0 <= ulps <= _MAX_STATED_ULPS:
        raise AssertionError(f"ulps must be an integer from 0 through {_MAX_STATED_ULPS}.")
    return _ulp_distance(actual, expected) <= ulps


def _shift_ulps(value: float, steps: int) -> float:
    direction = math.inf if steps > 0 else -math.inf
    shifted = value
    for _step in range(abs(steps)):
        shifted = math.nextafter(shifted, direction)
    return shifted


def _mechanical_one_tip(system, theta, theta_dot, omega, hinge_nm):
    mass = coupled_mass_matrix(system, theta)
    parameters = system.parameters
    spring = -parameters.spring_stiffness_nm_rad * (theta - parameters.rest_angle_rad)
    damping = -parameters.viscous_damping_nm_s_rad * theta_dot
    friction = parameters.dry_friction
    if friction.mode == "none":
        friction_nm = 0.0
    else:
        friction_nm = -friction.coulomb_torque_nm * math.tanh(
            theta_dot / friction.transition_velocity_rad_s
        )
    centrifugal = -mass.c_kg_m2 * omega**2 * math.sin(theta)
    gyro = (
        system.blade_count
        * mass.c_kg_m2
        * math.sin(theta)
        * (2.0 * omega * theta_dot + theta_dot**2)
    )
    return mass, spring, damping, friction_nm, centrifugal, gyro


def test_ulp_distance_orders_finite_binary64_values() -> None:
    assert _ulp_distance(0.0, -0.0) == 0
    assert _ulp_distance(1.0, math.nextafter(1.0, math.inf)) == 1
    assert _ulp_distance(1.0, math.nextafter(1.0, -math.inf)) == 1
    assert _ulp_distance(-1.0, math.nextafter(-1.0, -math.inf)) == 1
    assert _ulp_distance(-1.0, math.nextafter(-1.0, math.inf)) == 1
    below = math.nextafter(2.0, 0.0)
    above = math.nextafter(2.0, 4.0)
    assert _ulp_distance(below, above) == 2
    with pytest.raises(AssertionError):
        _ulp_distance(float("nan"), 1.0)
    with pytest.raises(AssertionError):
        _ulp_distance(1.0, float("inf"))
    with pytest.raises(AssertionError):
        _within_ulps(1.0, 1.0, ulps=64)
    with pytest.raises(AssertionError):
        _within_ulps(1.0, 1.0, ulps=True)  # type: ignore[arg-type]


def test_acceptance_rejects_a_63_ulp_perturbation() -> None:
    parameters = _parameters()
    system = _system(parameters, blade_count=2)
    reference = coupled_accelerations(
        system,
        theta=-0.2,
        theta_dot=0.1,
        omega=40.0,
        motor_torque_nm=0.01,
        aero_shaft_torque_nm=0.004,
        hinge_torque_nm=0.0,
    )
    expected = reference.omega_dot_rad_s2
    shifted = _shift_ulps(expected, 63)
    assert _ulp_distance(shifted, expected) == 63
    assert not _within_ulps(shifted, expected, ulps=1)
    assert not _within_ulps(shifted, expected, ulps=3)
    assert _within_ulps(_shift_ulps(expected, 1), expected, ulps=1)
    assert not _within_ulps(_shift_ulps(expected, -2), expected, ulps=1)


def test_model_identifiers_are_the_screening_contract() -> None:
    assert MODEL_CLASS == "coupled_aero_hinge_screening_only"
    assert IMPLEMENTATION_ID == "cmm2_planar_projected_rate_independent_coupling_v1"
    assert LOAD_MAPPING_MODEL == "planar_projected_material_load_v1"
    assert AERO_LOAD_QUALIFICATION == "screening_only_projected_rate_independent"
    assert HINGE_RATE_AERO_MODEL == "ignored_rate_independent_quasi_steady"
    assert PROJECTION_MODEL == "radial_cosine_v1"
    source = Path("pyfoldable/dynamics/cmm2_coupled_transient.py").read_text(encoding="utf-8")
    for forbidden in (
        "solve_foldable_bem_rotor",
        "map_foldable_bem_aero_loads",
        "FoldableBemShaftEvaluator",
        "DesignDraftArtifact",
        "pyfoldable_dashboard",
    ):
        assert forbidden not in source


def test_hand_derived_acceleration_matches_the_paired_load_equations() -> None:
    friction = DryFriction("regularized_coulomb", 0.002, 0.05, source="cmm2-hand")
    parameters = _parameters(
        spring_stiffness_nm_rad=0.01,
        rest_angle_rad=-0.05,
        viscous_damping_nm_s_rad=0.002,
        dry_friction=friction,
    )
    system = _system(parameters, blade_count=2)
    theta = -0.35
    theta_dot = 0.22
    omega = 36.0
    motor = 0.018
    shaft = -0.007
    hinge_aero = -0.0015
    hinge = 0.0004
    aero = _loads(system, shaft, hinge_aero)(0.0, theta, theta_dot, omega)
    solved = cmm2_coupled_accelerations(
        system, theta, theta_dot, omega, motor, aero, hinge
    )
    mass, spring, damping, friction_nm, centrifugal, gyro = _mechanical_one_tip(
        system, theta, theta_dot, omega, hinge
    )
    rhs_shaft = motor + shaft + gyro
    rhs_hinge = system.blade_count * (
        hinge + hinge_aero + spring + damping + friction_nm + centrifugal
    )
    determinant = mass.m00 * mass.m11 - mass.m01 * mass.m01
    omega_dot = (rhs_shaft * mass.m11 - mass.m01 * rhs_hinge) / determinant
    theta_ddot = (mass.m00 * rhs_hinge - mass.m01 * rhs_shaft) / determinant
    with localcontext() as ctx:
        ctx.prec = 80
        precise_shaft = Decimal.from_float(rhs_shaft)
        precise_hinge = Decimal.from_float(rhs_hinge)
        precise_m00 = Decimal.from_float(mass.m00)
        precise_m01 = Decimal.from_float(mass.m01)
        precise_m11 = Decimal.from_float(mass.m11)
        precise_det = precise_m00 * precise_m11 - precise_m01 * precise_m01
        precise_omega_dot = float(
            (precise_shaft * precise_m11 - precise_m01 * precise_hinge) / precise_det
        )
        precise_theta_ddot = float(
            (precise_m00 * precise_hinge - precise_m01 * precise_shaft) / precise_det
        )
    assert solved.rhs_shaft_nm == rhs_shaft
    assert solved.rhs_hinge_nm == rhs_hinge
    assert solved.aero_shaft_generalized_load_nm == shaft
    assert solved.aero_one_tip_hinge_generalized_load_nm == hinge_aero
    assert solved.aero_collective_hinge_generalized_load_nm == (
        system.blade_count * hinge_aero
    )
    # Schur evaluation versus this fixture's Cramer's rule: 2 and 1 ULP.
    # The same RHS against an 80-digit solve, then rounded back to binary64:
    # 1 and 0 ULP. The gates sit one ULP above those observed gaps.
    assert _ulp_distance(solved.omega_dot_rad_s2, precise_omega_dot) <= 1
    assert _ulp_distance(solved.theta_ddot_rad_s2, precise_theta_ddot) <= 1
    assert _within_ulps(solved.omega_dot_rad_s2, omega_dot, ulps=3)
    assert _within_ulps(solved.theta_ddot_rad_s2, theta_ddot, ulps=2)
    assert solved.mass_schur > 0.0
    assert math.isfinite(solved.mass_residual)


def test_zero_hinge_load_reduces_to_cmm1_accelerations() -> None:
    friction = DryFriction("regularized_coulomb", 0.001, 0.04, source="cmm2-reduce")
    parameters = _parameters(
        spring_stiffness_nm_rad=0.015,
        rest_angle_rad=-0.02,
        viscous_damping_nm_s_rad=0.001,
        dry_friction=friction,
    )
    states = (
        (-0.4, 0.2, 25.0, 1, 0.01, 0.002, 0.004),
        (0.0, 0.0, OMEGA_MIN, 2, 0.0, 0.0, 0.0),
        (-0.2, -0.5, 80.0, 4, -0.03, 0.01, -0.002),
        (0.3, 1.0, 50.0, 3, 0.02, -0.004, 0.008),
    )
    # These four speeds make ``omega * omega == omega ** 2``, so CMM-1's
    # centrifugal square and CMM-2's product are the same binary64 value.
    # Shaft load uses ``Qm - Qa`` versus ``Qm + (-Qa)``, which is the IEEE
    # subtraction, and the gyro term is the same product. A separate ordinary
    # grid of 103680 states on explicit speeds also stayed at 0 ULP. Speeds
    # where the square and the product differ by 1 ULP can move the Schur
    # result by more than that; those speeds are outside this fixture class
    # and are not covered by a 1 ULP gate.
    for theta, theta_dot, omega, count, motor, hinge, resisting in states:
        assert omega * omega == omega**2
        system = _system(parameters, blade_count=count)
        cmm1 = coupled_accelerations(
            system, theta, theta_dot, omega, motor, resisting, hinge
        )
        aero = _loads(system, -resisting, 0.0)(0.0, theta, theta_dot, omega)
        cmm2 = cmm2_coupled_accelerations(
            system, theta, theta_dot, omega, motor, aero, hinge
        )
        assert _within_ulps(cmm2.omega_dot_rad_s2, cmm1.omega_dot_rad_s2, ulps=1)
        assert _within_ulps(cmm2.theta_ddot_rad_s2, cmm1.theta_ddot_rad_s2, ulps=1)
        assert _within_ulps(cmm2.rhs_shaft_nm, cmm1.rhs_shaft_nm, ulps=1)
        assert _within_ulps(cmm2.rhs_hinge_nm, cmm1.rhs_hinge_nm, ulps=1)


def test_zero_aerodynamic_field_keeps_coupled_motor_mechanism_motion() -> None:
    parameters = _parameters()
    inertia = _inertia(0.01)
    system = _system(parameters, blade_count=2, inertia=inertia)
    mass = coupled_mass_matrix(system, 0.0)
    motor_torque = 0.01
    alpha = motor_torque / mass.m00
    hinge = mass.b_kg_m2 * alpha
    omega0 = 30.0
    result = solve_cmm2_transient(
        _request(
            system=system,
            actuation=_history(hinge, end=0.02),
            initial_angle_rad=0.0,
            initial_angular_velocity_rad_s=0.0,
            initial_omega_rad_s=omega0,
            motor_evaluator=_motor(motor_torque),
            aero_evaluator=_loads(system, 0.0, 0.0),
        )
    )
    assert result.status == "completed"
    for sample in result.samples:
        assert sample.aero_shaft_generalized_load_nm == 0.0
        assert sample.aero_one_tip_hinge_generalized_load_nm == 0.0
        assert sample.theta_rad == pytest.approx(0.0, abs=1.0e-7)
        assert sample.omega_rad_s == pytest.approx(omega0 + alpha * sample.time_s, abs=1.0e-6)
        assert not hasattr(sample, "aerodynamic_hinge_torque_status")


def test_shaft_load_is_not_multiplied_by_blade_count() -> None:
    parameters = _parameters()
    theta = -0.25
    theta_dot = 0.18
    omega = 42.0
    motor = 0.02
    shaft = -0.02
    hinge_aero = -0.003
    hinge = 0.001
    by_count = {}
    for count in (1, 2, 4):
        system = _system(parameters, blade_count=count)
        aero = _loads(system, shaft, hinge_aero)(0.0, theta, theta_dot, omega)
        solved = cmm2_coupled_accelerations(
            system, theta, theta_dot, omega, motor, aero, hinge
        )
        _mass, _spring, _damping, _friction, _centrifugal, gyro = _mechanical_one_tip(
            system, theta, theta_dot, omega, hinge
        )
        assert solved.aero_shaft_generalized_load_nm == shaft
        assert solved.rhs_shaft_nm == motor + shaft + gyro
        assert solved.aero_one_tip_hinge_generalized_load_nm == hinge_aero
        assert solved.aero_collective_hinge_generalized_load_nm == count * hinge_aero
        if count != 1:
            assert solved.aero_collective_hinge_generalized_load_nm != count * (
                count * hinge_aero
            )
        by_count[count] = solved
    gyro_gap = by_count[4].shaft_gyro_nm - by_count[1].shaft_gyro_nm
    rhs_gap = by_count[4].rhs_shaft_nm - by_count[1].rhs_shaft_nm
    assert rhs_gap == gyro_gap
    assert rhs_gap != gyro_gap + 3.0 * shaft


def test_folding_and_opening_hinge_loads_move_theta_acceleration() -> None:
    system = _system(_parameters(), blade_count=2)
    theta = -0.3
    theta_dot = 0.1
    omega = 40.0
    motor = 0.01
    shaft = -0.004
    hinge = 0.0
    base = cmm2_coupled_accelerations(
        system, theta, theta_dot, omega, motor, _loads(system, shaft, 0.0)(0.0, theta, theta_dot, omega), hinge
    )
    folding = cmm2_coupled_accelerations(
        system,
        theta,
        theta_dot,
        omega,
        motor,
        _loads(system, shaft, -0.01)(0.0, theta, theta_dot, omega),
        hinge,
    )
    opening = cmm2_coupled_accelerations(
        system,
        theta,
        theta_dot,
        omega,
        motor,
        _loads(system, shaft, 0.01)(0.0, theta, theta_dot, omega),
        hinge,
    )
    assert folding.theta_ddot_rad_s2 < base.theta_ddot_rad_s2
    assert opening.theta_ddot_rad_s2 > base.theta_ddot_rad_s2


def test_deployed_nonzero_hinge_load_enters_the_hinge_row() -> None:
    system = _system(blade_count=3)
    theta = 0.0
    theta_dot = 0.05
    omega = 28.0
    hinge_aero = 0.004
    zero = cmm2_coupled_accelerations(
        system, theta, theta_dot, omega, 0.0, _loads(system, -0.002, 0.0)(0.0, theta, theta_dot, omega), 0.0
    )
    loaded = cmm2_coupled_accelerations(
        system,
        theta,
        theta_dot,
        omega,
        0.0,
        _loads(system, -0.002, hinge_aero)(0.0, theta, theta_dot, omega),
        0.0,
    )
    assert loaded.aero_one_tip_hinge_generalized_load_nm == hinge_aero
    assert loaded.rhs_hinge_nm - zero.rhs_hinge_nm == system.blade_count * hinge_aero
    assert loaded.theta_ddot_rad_s2 > zero.theta_ddot_rad_s2


def test_aerodynamic_power_changes_with_hinge_rate_while_loads_stay_fixed() -> None:
    system = _system(blade_count=2)
    theta = -0.2
    omega = 33.0
    shaft = -0.006
    hinge_aero = -0.002
    slow = _loads(system, shaft, hinge_aero)(0.0, theta, 0.1, omega)
    fast = _loads(system, shaft, hinge_aero)(0.0, theta, 0.4, omega)
    assert slow.whole_rotor_shaft_generalized_load_nm == fast.whole_rotor_shaft_generalized_load_nm
    assert slow.one_tip_hinge_generalized_load_nm == fast.one_tip_hinge_generalized_load_nm
    slow_power = slow.generalized_power_w(omega)
    fast_power = fast.generalized_power_w(omega)
    independent_slow = shaft * omega + system.blade_count * hinge_aero * 0.1
    independent_fast = shaft * omega + system.blade_count * hinge_aero * 0.4
    # Same product association as generalized_power_w. Measured distance is 0.
    # Four ULP remains the explicit gate and still rejects a 63-ULP shift.
    assert _within_ulps(slow_power, independent_slow, ulps=4)
    assert _within_ulps(fast_power, independent_fast, ulps=4)
    assert fast_power != slow_power
    solved = cmm2_coupled_accelerations(
        system, theta, 0.4, omega, 0.0, fast, 0.0
    )
    assert _within_ulps(solved.aero_generalized_power_w, independent_fast, ulps=4)


def test_instantaneous_energy_identity_omits_spring_and_gyroscopic_power() -> None:
    friction = DryFriction("regularized_coulomb", 0.003, 0.08, source="cmm2-energy")
    parameters = _parameters(
        spring_stiffness_nm_rad=0.02,
        rest_angle_rad=-0.04,
        viscous_damping_nm_s_rad=0.004,
        dry_friction=friction,
    )
    system = _system(parameters, blade_count=2)
    theta = -0.22
    theta_dot = 0.35
    omega = 31.0
    motor = 0.012
    shaft = -0.005
    hinge_aero = 0.001
    hinge = -0.0007
    aero = _loads(system, shaft, hinge_aero)(0.0, theta, theta_dot, omega)
    solved = cmm2_coupled_accelerations(
        system, theta, theta_dot, omega, motor, aero, hinge
    )
    _mass, spring, damping, friction_nm, _centrifugal, _gyro = _mechanical_one_tip(
        system, theta, theta_dot, omega, hinge
    )
    expected = (
        motor * omega
        + shaft * omega
        + system.blade_count * hinge_aero * theta_dot
        + system.blade_count * hinge * theta_dot
        + system.blade_count * damping * theta_dot
        + system.blade_count * friction_nm * theta_dot
    )
    spring_power = system.blade_count * spring * theta_dot
    assert spring_power != 0.0
    # Same six-term left-associated sum. ``(N * q) * rate`` matches
    # ``N * q * rate``. The fixture distance is 0 ULP; one ULP is the gate.
    assert _within_ulps(
        cmm2_instantaneous_power_w(solved, theta_dot, omega), expected, ulps=1
    )
    assert cmm2_instantaneous_power_w(solved, theta_dot, omega) != expected + spring_power
    result = solve_cmm2_transient(
        _request(
            system=system,
            actuation=_history(hinge, end=0.01),
            initial_angle_rad=theta,
            initial_angular_velocity_rad_s=theta_dot,
            initial_omega_rad_s=omega,
            motor_evaluator=_motor(motor),
            aero_evaluator=_loads(system, shaft, hinge_aero),
            controls=CoupledSolverControls(max_step_s=0.002, max_duration_s=0.01),
        )
    )
    for sample in result.samples:
        reconstructed = (
            sample.motor_shaft_power_w
            + sample.aero_generalized_power_w
            + sample.hinge_actuation_power_w
            + sample.damping_power_w
            + sample.dry_friction_power_w
        )
        # Same five stored addends, same order. Eight ULP is the explicit gate.
        assert _within_ulps(sample.power_identity_w, reconstructed, ulps=8)
        assert math.isfinite(sample.energy_residual_j)
        assert math.isfinite(sample.mechanical_energy_j)


def test_state_bound_mismatch_fails_closed() -> None:
    system = _system()
    theta = -0.2
    theta_dot = 0.1
    omega = 20.0
    aero = _loads(system, -0.001, 0.002)(0.0, theta, theta_dot, omega)
    cmm2_coupled_accelerations(system, theta, theta_dot, omega, 0.0, aero, 0.0)
    for field, value in (
        ("theta_rad", theta + 0.01),
        ("hinge_rate_rad_s", theta_dot + 0.01),
        ("hinge_radius_m", system.parameters.hinge_radius_m + 0.001),
        ("blade_count", system.blade_count + 1),
    ):
        mismatched = dataclasses.replace(aero, **{field: value})
        with pytest.raises(Cmm2TransientFailure, match="state-bound"):
            cmm2_coupled_accelerations(
                system, theta, theta_dot, omega, 0.0, mismatched, 0.0
            )


def test_nonfinite_paired_loads_and_wrong_evaluator_type_fail() -> None:
    system = _system()
    kwargs = dict(
        thrust_n=0.0,
        load_mapping_model=LOAD_MAPPING_MODEL,
        qualification=AERO_LOAD_QUALIFICATION,
        projection_model=PROJECTION_MODEL,
        hinge_rate_aerodynamic_model=HINGE_RATE_AERO_MODEL,
        blade_count=system.blade_count,
        hinge_radius_m=system.parameters.hinge_radius_m,
        theta_rad=-0.2,
        hinge_rate_rad_s=0.0,
        source_id="bad",
    )
    with pytest.raises((Cmm2TransientError, Cmm2TransientFailure)):
        Cmm2AeroEvaluation(
            whole_rotor_shaft_generalized_load_nm=float("nan"),
            one_tip_hinge_generalized_load_nm=0.0,
            **kwargs,
        )
    with pytest.raises((Cmm2TransientError, Cmm2TransientFailure)):
        Cmm2AeroEvaluation(
            whole_rotor_shaft_generalized_load_nm=0.0,
            one_tip_hinge_generalized_load_nm=float("inf"),
            **kwargs,
        )
    huge = Cmm2AeroEvaluation(
        whole_rotor_shaft_generalized_load_nm=1.0e308,
        one_tip_hinge_generalized_load_nm=0.0,
        **kwargs,
    )
    with pytest.raises(Cmm2TransientFailure, match="power"):
        cmm2_coupled_accelerations(
            system, -0.2, 0.0, 1.0e308, 0.0, dataclasses.replace(huge, theta_rad=-0.2), 0.0
        )

    def wrong_type(time_s, theta, theta_dot, omega):
        del time_s, theta, theta_dot, omega
        return AeroEvaluation(0.1, 0.0, "cmm1", "software_fixture")

    with pytest.raises(Cmm2TransientFailure, match="evaluator"):
        solve_cmm2_transient(_request(system=system, aero_evaluator=wrong_type))


def test_analytic_transient_completes_with_screening_qualification() -> None:
    system = _system()
    result = solve_cmm2_transient(
        _request(
            system=system,
            aero_evaluator=_loads(system, -0.001, -0.0002, thrust_n=0.4),
            motor_evaluator=_motor(0.001),
        )
    )
    assert result.status == "completed"
    assert result.model_class == MODEL_CLASS
    assert result.implementation_id == IMPLEMENTATION_ID
    assert result.physical_qualification is False
    assert result.full_propeller_clearance is None
    assert result.surface_path_clearance is None
    assert result.interblade_clearance is None
    assert len(result.samples) >= 2
    sample = result.samples[-1]
    assert sample.aero_load_mapping_model == LOAD_MAPPING_MODEL
    assert sample.aero_load_qualification == AERO_LOAD_QUALIFICATION
    assert sample.aero_projection_model == PROJECTION_MODEL
    assert sample.aero_hinge_rate_model == HINGE_RATE_AERO_MODEL
    assert sample.aero_source_id == "analytic-pr-a"
    assert sample.aero_thrust_n == 0.4
    assert sample.aero_shaft_generalized_load_nm == -0.001
    assert sample.aero_one_tip_hinge_generalized_load_nm == -0.0002
    with pytest.raises(Cmm2TransientError):
        dataclasses.replace(result, physical_qualification=True)


def test_first_contact_remains_terminal() -> None:
    parameters = _parameters(lower_stop_rad=-0.08, upper_stop_rad=0.8)
    system = _system(parameters, inertia=_inertia(0.05))
    result = solve_cmm2_transient(
        _request(
            system=system,
            actuation=_history(end=0.05),
            initial_angle_rad=-0.02,
            initial_angular_velocity_rad_s=-6.0,
            initial_omega_rad_s=40.0,
            aero_evaluator=_loads(system, 0.0, 0.0),
        )
    )
    assert result.status == "first_contact_terminal"
    assert result.contact is not None
    assert result.contact.stop == "lower"
    assert result.contact.angle_rad == pytest.approx(parameters.lower_stop_rad)
    assert result.samples[-1].time_s < 0.05
    assert result.physical_qualification is False


def test_fold_and_speed_domain_failures_stay_closed() -> None:
    with pytest.raises(Cmm2TransientError):
        _request(initial_angle_rad=-FOLD_LIMIT_RAD)
    with pytest.raises(Cmm2TransientError):
        _request(initial_omega_rad_s=OMEGA_MIN - 1.0e-9)
    with pytest.raises(Cmm2TransientError):
        _request(initial_angular_velocity_rad_s=float("nan"))

    slow_system = _system(inertia=_inertia(1.0e-5))
    with pytest.raises(Cmm2DomainExit):
        solve_cmm2_transient(
            _request(
                system=slow_system,
                actuation=_history(end=0.05),
                initial_omega_rad_s=OMEGA_MIN,
                aero_evaluator=_loads(slow_system, -5.0, 0.0),
            )
        )

    wide = _parameters(lower_stop_rad=-1.6, upper_stop_rad=1.6)
    folding = _system(wide, inertia=_inertia(0.05))
    with pytest.raises(Cmm2DomainExit):
        solve_cmm2_transient(
            _request(
                system=folding,
                actuation=_history(end=0.05),
                initial_angle_rad=-1.2,
                initial_angular_velocity_rad_s=-30.0,
                initial_omega_rad_s=40.0,
                aero_evaluator=_loads(folding, 0.0, 0.0),
            )
        )


def test_repeat_is_deterministic_and_budget_exhaustion_fails() -> None:
    system = _system()
    request = _request(
        system=system,
        aero_evaluator=_loads(system, -0.002, 0.0003),
        motor_evaluator=_motor(0.004),
    )
    first = solve_cmm2_transient(request)
    second = solve_cmm2_transient(request)
    assert [sample.time_s for sample in first.samples] == [
        sample.time_s for sample in second.samples
    ]
    assert [sample.theta_rad for sample in first.samples] == [
        sample.theta_rad for sample in second.samples
    ]
    assert [sample.omega_rad_s for sample in first.samples] == [
        sample.omega_rad_s for sample in second.samples
    ]
    with pytest.raises(Cmm2TransientFailure, match="budget"):
        solve_cmm2_transient(
            _request(
                system=system,
                aero_evaluator=_loads(system, 0.0, 0.0),
                controls=CoupledSolverControls(max_rhs_evaluations=1),
            )
        )


def test_unresolved_mass_matrix_fails_without_a_zero_hinge_substitute() -> None:
    parameters = _parameters(
        mass_kg=0.02,
        cg_distance_m=0.01,
        hinge_inertia_kg_m2=0.02 * 0.01**2,
    )
    system = _system(parameters, blade_count=2, inertia=_inertia(1.0e-20))
    aero = Cmm2AeroEvaluation(
        whole_rotor_shaft_generalized_load_nm=0.0,
        one_tip_hinge_generalized_load_nm=0.25,
        thrust_n=0.0,
        load_mapping_model=LOAD_MAPPING_MODEL,
        qualification=AERO_LOAD_QUALIFICATION,
        projection_model=PROJECTION_MODEL,
        hinge_rate_aerodynamic_model=HINGE_RATE_AERO_MODEL,
        blade_count=2,
        hinge_radius_m=parameters.hinge_radius_m,
        theta_rad=0.0,
        hinge_rate_rad_s=0.0,
        source_id="unresolved",
    )
    with pytest.raises(Cmm2TransientFailure, match="unresolved"):
        cmm2_coupled_accelerations(
            system, 0.0, 0.0, OMEGA_MIN, 1.0e-12, aero, 0.0
        )


def test_later_screening_contract_error_is_not_relabeled() -> None:
    system = _system()
    calls = {"count": 0}

    def evaluate(time_s, theta, theta_dot, omega):
        del time_s
        calls["count"] += 1
        if calls["count"] == 1:
            return _loads(system, 0.0, 0.0)(0.0, theta, theta_dot, omega)
        return Cmm2AeroEvaluation(
            whole_rotor_shaft_generalized_load_nm=0.0,
            one_tip_hinge_generalized_load_nm=0.0,
            thrust_n=0.0,
            load_mapping_model="not-the-screening-contract",
            qualification=AERO_LOAD_QUALIFICATION,
            projection_model=PROJECTION_MODEL,
            hinge_rate_aerodynamic_model=HINGE_RATE_AERO_MODEL,
            blade_count=system.blade_count,
            hinge_radius_m=system.parameters.hinge_radius_m,
            theta_rad=theta,
            hinge_rate_rad_s=theta_dot,
            source_id="analytic-pr-a",
        )

    with pytest.raises(Cmm2TransientError, match="load_mapping_model"):
        solve_cmm2_transient(_request(system=system, aero_evaluator=evaluate))


def test_cmm1_public_contract_stays_on_the_omitted_hinge_model() -> None:
    assert CMM1_MODEL_CLASS == "partial_coupled_screening_only"
    assert AERO_HINGE_STATUS == "unavailable_omitted_by_cmm1"
    cmm1 = coupled_accelerations(
        _system(),
        theta=-0.2,
        theta_dot=0.1,
        omega=20.0,
        motor_torque_nm=0.01,
        aero_shaft_torque_nm=0.004,
        hinge_torque_nm=0.0,
    )
    assert cmm1.aero_shaft_torque_nm == 0.004
    assert cmm1.rhs_shaft_nm < 0.01
    cmm1_request = CoupledTransientRequest(
        system=_system(),
        actuation=_history(),
        initial_angle_rad=-0.2,
        initial_angular_velocity_rad_s=0.0,
        initial_omega_rad_s=OMEGA_MIN * 2.0,
        motor_evaluator=_motor(0.0),
        aero_evaluator=lambda time_s, theta, theta_dot, omega: AeroEvaluation(
            0.0, 0.0, "cmm1-regression", "software_fixture"
        ),
    )
    result = solve_coupled_transient(cmm1_request)
    assert result.model_class == "partial_coupled_screening_only"
    assert result.aerodynamic_hinge_torque_status == "unavailable_omitted_by_cmm1"
    assert result.samples[0].aerodynamic_hinge_torque_status == AERO_HINGE_STATUS
    assert result.physical_qualification is False
