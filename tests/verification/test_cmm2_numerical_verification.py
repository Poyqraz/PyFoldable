"""PR-C numerical verification for the frozen CMM-2 screening contract.

The frozen contract is the authority. Production code is the subject under
test. This module does not accept ADR-009 or physical qualification.
"""

from __future__ import annotations

import math
import struct
import warnings
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest
from scipy.integrate import IntegrationWarning, quad, solve_ivp

import pyfoldable.dynamics.cmm2_coupled_transient as cmm2
from pyfoldable.application.cmm2_coupled_transient_service import (
    Cmm2FoldableBemMappedAeroEvaluator,
    prepare_cmm2_coupled_transient,
    run_cmm2_coupled_transient,
)
from pyfoldable.application.coupled_transient_service import (
    CoupledBindingError,
    CoupledEnvironment,
    Pr07MotorEvaluator,
)
from pyfoldable.application.design_draft import DesignDraftInputs, build_design_draft
from pyfoldable.application.mechanism_binding import RadialMassSample, TipMassDistribution
from pyfoldable.core.bem import BEMAnnulusSettings
from pyfoldable.core.bem_rotor import BEMRotorSettings
from pyfoldable.core.foldable_aero_load import map_foldable_bem_aero_loads
from pyfoldable.core.foldable_rotor import FoldableRotorState, solve_foldable_bem_rotor
from pyfoldable.core.models import OperatingCondition
from pyfoldable.dynamics.cmm2_coupled_transient import (
    AERO_LOAD_QUALIFICATION,
    HINGE_RATE_AERO_MODEL,
    LOAD_MAPPING_MODEL,
    PROJECTION_MODEL,
    Cmm2AeroEvaluation,
    Cmm2DomainExit,
    Cmm2TransientError,
    Cmm2TransientFailure,
    Cmm2TransientRequest,
    cmm2_coupled_accelerations,
    solve_cmm2_transient,
)
from pyfoldable.dynamics.coupled_transient import (
    OMEGA_MIN,
    BaseRotatingAssemblyInertia,
    CoupledDomainExit,
    CoupledSolverControls,
    CoupledSystem,
    CoupledTransientError,
    HingeActuationHistory,
    MotorEvaluation,
    coupled_accelerations,
)
from pyfoldable.dynamics.mechanism_contracts import DryFriction
from pyfoldable.dynamics.mechanism_transient import MechanismParameters, _first_contact
from pyfoldable.core import load_design_config
from pythrust.propulsion.models import BatterySpec, MotorSpec, SystemSpec
from tests.verification.cmm2_prc_evidence import (
    EVIDENCE,
    measurement_partial,
    recorded_case,
    MANIFEST_SHA,
    commit_case,
    execute_measured_case,
    executed_fixture,
    fixture_digest,
    freeze_case_before_measurement,
    write_evidence,
)


ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "configs/designs/TIP_HINGED_250_CANONICAL.toml"
M_MASS = 0.02
R_HINGE = 0.08
C_CG = 0.03
J_HINGE = 2.0e-5
I0_BASE = 1.0e-4
K_SPRING = 0.01
THETA_REST = -0.2
B_DAMP = 0.002
TAU_C = 0.001
V_FRIC = 0.05
LOWER = -1.2
UPPER = 0.2
INVENTORY = ("motor rotor", "shaft", "hub", "fixed blade roots")


def _finite(value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise AssertionError("nonfinite verification value")
    return number


def _pack(value: float) -> bytes:
    return struct.pack("!d", value)


def _ulp_distance(left: float, right: float) -> int:
    if left == right:
        return 0
    if not (math.isfinite(left) and math.isfinite(right)):
        return 2**63
    def ordered(number: float) -> int:
        bits = int.from_bytes(struct.pack(">d", number), "big", signed=True)
        if bits < 0:
            bits = 0x8000000000000000 - bits
        return bits
    return abs(ordered(left) - ordered(right))


@pytest.fixture(scope="session", autouse=True)
def _dump_prc_evidence(tmp_path_factory):
    yield
    path = tmp_path_factory.getbasetemp() / "cmm2_prc_evidence.json"
    write_evidence(path)
    mirror = Path("/tmp/cmm2_prc_evidence.json")
    write_evidence(mirror)
    print(f"CMM2_PRC_EVIDENCE {path}")


def _publish(case_id: str, payload: dict[str, object]) -> None:
    partial = measurement_partial()
    payload = {**partial, **payload}
    if partial.get("premeasurement_snapshots"):
        payload["premeasurement_digest"] = partial["premeasurement_digest"]
    executed = payload.pop("executed_inputs", {})
    fixture = executed_fixture(case_id, executed if isinstance(executed, dict) else {})
    payload.setdefault("fixture_identity", f"prc_critical_fixture_manifest_v1:{case_id}")
    if payload.get("premeasurement_digest"):
        payload["fixture_digest"] = payload["premeasurement_digest"]
    else:
        payload.setdefault("fixture_digest", fixture_digest(fixture))
    payload.setdefault("controls", fixture["controls"])
    payload.setdefault("executed_inputs", executed)
    partial.update(payload)
    commit_case(case_id, payload)


def _mechanism(**overrides) -> MechanismParameters:
    friction = overrides.pop(
        "dry_friction",
        DryFriction("regularized_coulomb", TAU_C, V_FRIC, source="prc-contract"),
    )
    values = dict(
        mass_kg=M_MASS,
        cg_distance_m=C_CG,
        hinge_inertia_kg_m2=J_HINGE,
        hinge_radius_m=R_HINGE,
        spring_stiffness_nm_rad=K_SPRING,
        rest_angle_rad=THETA_REST,
        viscous_damping_nm_s_rad=B_DAMP,
        lower_stop_rad=LOWER,
        upper_stop_rad=UPPER,
        dry_friction=friction,
    )
    values.update(overrides)
    return MechanismParameters(**values)


def _system(count: int, mechanism: MechanismParameters | None = None, inertia: float = I0_BASE) -> CoupledSystem:
    return CoupledSystem(
        mechanism or _mechanism(),
        count,
        BaseRotatingAssemblyInertia(inertia, "prc fixture", INVENTORY),
    )


def _controls(**overrides) -> CoupledSolverControls:
    return replace(CoupledSolverControls(), **overrides)


def _tip_c(mechanism: MechanismParameters) -> float:
    return mechanism.mass_kg * mechanism.hinge_radius_m * mechanism.cg_distance_m


def _matrix(system: CoupledSystem, theta: float) -> tuple[float, float, float, float]:
    mechanism = system.parameters
    count = system.blade_count
    coupling = _tip_c(mechanism)
    cosine = math.cos(theta)
    one_a = (
        mechanism.hinge_inertia_kg_m2
        + mechanism.mass_kg * mechanism.hinge_radius_m**2
        + 2.0 * coupling * cosine
    )
    one_b = mechanism.hinge_inertia_kg_m2 + coupling * cosine
    m00 = system.base_inertia.inertia_kg_m2 + count * one_a
    m01 = count * one_b
    m11 = count * mechanism.hinge_inertia_kg_m2
    return m00, m01, m11, coupling


def _friction(mechanism: MechanismParameters, theta_dot: float) -> float:
    friction = mechanism.dry_friction
    if friction.mode == "none":
        return 0.0
    return -friction.coulomb_torque_nm * math.tanh(
        theta_dot / friction.transition_velocity_rad_s
    )


def _rhs(
    system: CoupledSystem,
    theta: float,
    theta_dot: float,
    omega: float,
    motor_nm: float,
    hinge_nm: float,
    q_phi: float,
    q_theta: float,
) -> tuple[float, float]:
    mechanism = system.parameters
    _m00, _m01, _m11, coupling = _matrix(system, theta)
    sine = math.sin(theta)
    spring = -mechanism.spring_stiffness_nm_rad * (theta - mechanism.rest_angle_rad)
    damping = -mechanism.viscous_damping_nm_s_rad * theta_dot
    friction = _friction(mechanism, theta_dot)
    centrifugal = -coupling * omega**2 * sine
    shaft = motor_nm + q_phi + system.blade_count * coupling * sine * (
        2.0 * omega * theta_dot + theta_dot**2
    )
    hinge = system.blade_count * (
        hinge_nm + q_theta + spring + damping + friction + centrifugal
    )
    return shaft, hinge


def _solve_fraction(m00: float, m01: float, m11: float, b0: float, b1: float):
    left = Fraction.from_float(m00)
    couple = Fraction.from_float(m01)
    right = Fraction.from_float(m11)
    load0 = Fraction.from_float(b0)
    load1 = Fraction.from_float(b1)
    determinant = left * right - couple * couple
    omega_dot = (load0 * right - couple * load1) / determinant
    theta_ddot = (left * load1 - load0 * couple) / determinant
    return omega_dot, theta_ddot, left, couple, right, load0, load1, determinant


def _inverse_inf(left: Fraction, couple: Fraction, right: Fraction, determinant: Fraction) -> Fraction:
    inverse = [
        [right / determinant, -couple / determinant],
        [-couple / determinant, left / determinant],
    ]
    return max(abs(inverse[0][0]) + abs(inverse[0][1]), abs(inverse[1][0]) + abs(inverse[1][1]))


def _audit_solution(m00, m01, m11, b0, b1, x_prod):
    omega_ref, theta_ref, left, couple, right, load0, load1, determinant = _solve_fraction(
        m00, m01, m11, b0, b1
    )
    x_frac = (
        Fraction.from_float(float(x_prod[0])),
        Fraction.from_float(float(x_prod[1])),
    )
    residual = (
        load0 - (left * x_frac[0] + couple * x_frac[1]),
        load1 - (couple * x_frac[0] + right * x_frac[1]),
    )
    matrix_inf = max(abs(left) + abs(couple), abs(couple) + abs(right))
    inverse_inf = _inverse_inf(left, couple, right, determinant)
    kappa = matrix_inf * inverse_inf
    residual_inf = max(abs(residual[0]), abs(residual[1]))
    solution_inf = max(abs(x_frac[0]), abs(x_frac[1]))
    load_inf = max(abs(load0), abs(load1))
    denominator = matrix_inf * solution_inf + load_inf
    if denominator == 0 and residual_inf == 0:
        rho = Fraction(0)
        rho_defined = True
    elif denominator == 0:
        rho = None
        rho_defined = False
    else:
        rho = residual_inf / denominator
        rho_defined = True
    reference = (omega_ref, theta_ref)
    reference_inf = max(abs(reference[0]), abs(reference[1]))
    absolute_error = max(abs(x_frac[0] - reference[0]), abs(x_frac[1] - reference[1]))
    rows = []
    products = (
        (left * x_frac[0], couple * x_frac[1]),
        (couple * x_frac[0], right * x_frac[1]),
    )
    loads = (load0, load1)
    for index, residual_i in enumerate(residual):
        scale = abs(float(loads[index])) + abs(float(products[index][0])) + abs(float(products[index][1]))
        if scale == 0.0:
            passed = residual_i == 0
            eta = 0.0 if passed else math.inf
        else:
            eta = abs(float(residual_i)) / scale
            allowance = max(1.0e-8, 64.0 * math.ulp(scale) / scale)
            passed = eta <= allowance
        rows.append({"eta": eta, "passed": passed, "row_scale": scale})
    absolute_bound = inverse_inf * residual_inf
    report = {
        "x_ref": [float(reference[0]), float(reference[1])],
        "x_prod": [float(x_prod[0]), float(x_prod[1])],
        "absolute_forward_error_rad_s2": float(absolute_error),
        "row_backward_errors": rows,
        "kappa_inf": float(kappa),
        "rho_inf": None if rho is None else float(rho),
        "B_abs_rad_s2": float(absolute_bound),
        "classification": "PASS",
    }
    if not all(row["passed"] for row in rows):
        report["classification"] = "FAIL"
        return report, reference, absolute_bound
    if reference_inf == 0:
        report["branch"] = "absolute"
        report["E_abs_rad_s2"] = float(absolute_error)
        if not absolute_error <= absolute_bound:
            report["classification"] = "FAIL"
        return report, reference, absolute_bound
    if not rho_defined or kappa * rho >= 1:
        report["branch"] = "relative"
        report["classification"] = "NUMERICALLY INCONCLUSIVE"
        return report, reference, absolute_bound
    relative_bound = 2 * kappa * rho / (1 - kappa * rho)
    relative_error = absolute_error / reference_inf
    report["branch"] = "relative"
    report["B_rel"] = float(relative_bound)
    report["E_rel"] = float(relative_error)
    if not relative_error <= relative_bound:
        report["classification"] = "FAIL"
    return report, reference, absolute_bound


def _production_acceleration(system, theta, theta_dot, omega, motor_nm, hinge_nm, q_phi, q_theta):
    evaluation = Cmm2AeroEvaluation(
        q_phi,
        q_theta,
        1.0,
        LOAD_MAPPING_MODEL,
        AERO_LOAD_QUALIFICATION,
        PROJECTION_MODEL,
        HINGE_RATE_AERO_MODEL,
        system.blade_count,
        system.parameters.hinge_radius_m,
        theta,
        theta_dot,
        "prc-production",
    )
    solved = cmm2_coupled_accelerations(
        system, theta, theta_dot, omega, motor_nm, evaluation, hinge_nm
    )
    return solved.omega_dot_rad_s2, solved.theta_ddot_rad_s2


def _state_scale(controls: CoupledSolverControls, reference: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        controls.angle_atol_rad + controls.rtol * abs(reference[0]),
        controls.hinge_velocity_atol_rad_s + controls.rtol * abs(reference[1]),
        controls.shaft_speed_atol_rad_s + controls.rtol * abs(reference[2]),
    )


def _max_state_error(controls, production, reference) -> list[float]:
    scale = _state_scale(controls, reference)
    return [abs(production[index] - reference[index]) / scale[index] for index in range(3)]


def _dop853(rhs, y0, t1, controls: CoupledSolverControls, level: str):
    factor = 100 if level == "A" else 10000
    step_factor = 4 if level == "A" else 8
    rtol = controls.rtol / factor
    atol = (
        controls.angle_atol_rad / factor,
        controls.hinge_velocity_atol_rad_s / factor,
        controls.shaft_speed_atol_rad_s / factor,
    )
    max_step = controls.max_step_s / step_factor
    if min(rtol, *atol, max_step) <= 0.0:
        return None, "REFERENCE NOT STABILIZED"
    try:
        solution = solve_ivp(
            rhs,
            (0.0, t1),
            y0,
            method="DOP853",
            rtol=rtol,
            atol=atol,
            max_step=max_step,
            dense_output=True,
        )
    except Exception:
        # Entry recording boundaries retain the partial measurements, then the
        # original oracle exception must remain a pytest failure.
        raise
    if not solution.success or solution.sol is None:
        return None, "REFERENCE NOT STABILIZED"
    return solution, None


def _stabilization_metrics(rhs, y0, times, controls):
    empty = {
        "max_abs_A_minus_B_over_S": None,
        "max_abs_A_minus_B_over_S_limit": 0.1,
        "max_abs_A_minus_B_over_0_1_S": None,
        "max_abs_A_minus_B_over_0_1_S_limit": 1.0,
        "stabilized": False,
        "reason": "REFERENCE NOT STABILIZED",
        "reference_b": None,
    }
    if not times:
        empty["reason"] = "REFERENCE NOT STABILIZED: no production samples"
        return empty
    first, reason_a = _dop853(rhs, y0, times[-1], controls, "A")
    if first is None:
        empty["reason"] = reason_a
        return empty
    second, reason_b = _dop853(rhs, y0, times[-1], controls, "B")
    if second is None:
        empty["reason"] = reason_b
        return empty
    max_over_s = 0.0
    max_over_point1_s = 0.0
    for time in times:
        if not math.isfinite(float(time)):
            empty["reason"] = "nonfinite sample time"
            return empty
        left = first.sol(time)
        right = second.sol(time)
        produced = [float(left[index]) for index in range(3)]
        reference = [float(right[index]) for index in range(3)]
        if any(not math.isfinite(value) for value in produced + reference):
            empty["reason"] = "nonfinite state component"
            return empty
        scale = _state_scale(controls, (reference[0], reference[1], reference[2]))
        if any((not math.isfinite(value)) or value <= 0.0 for value in scale):
            empty["reason"] = "nonpositive or nonfinite scale"
            return empty
        for index in range(3):
            gap = abs(produced[index] - reference[index])
            ratio = gap / scale[index]
            ratio_point1 = gap / (0.1 * scale[index])
            if not math.isfinite(ratio) or not math.isfinite(ratio_point1):
                empty["reason"] = "nonfinite stabilization ratio"
                return empty
            max_over_s = max(max_over_s, ratio)
            max_over_point1_s = max(max_over_point1_s, ratio_point1)
    stabilized = max_over_s <= 0.1 and max_over_point1_s <= 1.0
    return {
        "max_abs_A_minus_B_over_S": max_over_s,
        "max_abs_A_minus_B_over_S_limit": 0.1,
        "max_abs_A_minus_B_over_0_1_S": max_over_point1_s,
        "max_abs_A_minus_B_over_0_1_S_limit": 1.0,
        "stabilized": stabilized,
        "reason": None if stabilized else "REFERENCE NOT STABILIZED",
        "reference_b": second,
    }


def _invalid_sample(reason: str) -> dict[str, object]:
    return {
        "valid": False,
        "reason": reason,
        "e": None,
        "time_s": None,
        "component": None,
        "absolute_error": None,
        "scale": None,
        "unit": None,
    }


def _worst_sample(controls, samples, reference_at):
    names = ("theta", "theta_dot", "omega")
    units = ("rad", "rad/s", "rad/s")
    worst = None
    for sample in samples:
        if not math.isfinite(float(sample.time_s)):
            return _invalid_sample("nonfinite sample time")
        reference = reference_at(sample.time_s)
        if any(not math.isfinite(float(value)) for value in reference):
            return _invalid_sample("nonfinite state component")
        scale = _state_scale(controls, reference)
        if any((not math.isfinite(value)) or value <= 0.0 for value in scale):
            return _invalid_sample("nonpositive or nonfinite scale")
        produced = (sample.theta_rad, sample.theta_dot_rad_s, sample.omega_rad_s)
        if any(not math.isfinite(float(value)) for value in produced):
            return _invalid_sample("nonfinite state component")
        for index, name in enumerate(names):
            absolute = abs(float(produced[index]) - float(reference[index]))
            ratio = absolute / scale[index]
            if not math.isfinite(absolute) or not math.isfinite(ratio):
                return _invalid_sample("nonfinite state ratio")
            row = {
                "valid": True,
                "reason": None,
                "time_s": float(sample.time_s),
                "component": name,
                "absolute_error": absolute,
                "scale": scale[index],
                "e": ratio,
                "unit": units[index],
            }
            if worst is None or ratio > worst["e"]:
                worst = row
    return worst or _invalid_sample("no production samples")


def _quadrature_is_reliable(integral_a, error_a, integral_b, error_b):
    values = (integral_a, error_a, integral_b, error_b)
    if any(value is None or not math.isfinite(float(value)) for value in values):
        return False, "QUADRATURE REFERENCE NOT RELIABLE"
    return True, None


def _actuation(duration: float, torque: float = 0.0) -> HingeActuationHistory:
    return HingeActuationHistory((0.0, duration), (torque, torque), "prc")


def _run(system, duration, theta, theta_dot, omega, motor, aero, controls=None, actuation=None):
    controls = controls or _controls()
    request = Cmm2TransientRequest(
        system,
        actuation or _actuation(duration),
        theta,
        theta_dot,
        omega,
        motor,
        aero,
        controls,
    )
    return solve_cmm2_transient(request)


def _target_loads(system, theta, theta_dot, omega, omega_dot, theta_ddot, motor_nm, hinge_nm):
    shaft_without, hinge_without = _rhs(
        system, theta, theta_dot, omega, motor_nm, hinge_nm, 0.0, 0.0
    )
    m00, m01, m11, _coupling = _matrix(system, theta)
    shaft_target = m00 * omega_dot + m01 * theta_ddot
    hinge_target = m01 * omega_dot + m11 * theta_ddot
    return shaft_target - shaft_without, (hinge_target - hinge_without) / system.blade_count


def _energy_rate(system, theta, theta_dot, omega, omega_dot, theta_ddot) -> float:
    mechanism = system.parameters
    count = system.blade_count
    coupling = _tip_c(mechanism)
    sine = math.sin(theta)
    m00, m01, m11, _coupling = _matrix(system, theta)
    m00_theta = -2.0 * count * coupling * sine
    m01_theta = -count * coupling * sine
    kinetic_rate = (
        0.5 * m00_theta * theta_dot * omega**2
        + m00 * omega * omega_dot
        + m01_theta * theta_dot * omega * theta_dot
        + m01 * (omega_dot * theta_dot + omega * theta_ddot)
        + m11 * theta_dot * theta_ddot
    )
    spring_rate = (
        count
        * mechanism.spring_stiffness_nm_rad
        * (theta - mechanism.rest_angle_rad)
        * theta_dot
    )
    return kinetic_rate + spring_rate


def _power(system, theta, theta_dot, omega, motor_nm, hinge_nm, q_phi, q_theta) -> tuple[float, float, float]:
    mechanism = system.parameters
    count = system.blade_count
    friction = _friction(mechanism, theta_dot)
    terms = (
        motor_nm * omega,
        q_phi * omega,
        count * q_theta * theta_dot,
        count * hinge_nm * theta_dot,
        -count * mechanism.viscous_damping_nm_s_rad * theta_dot**2,
        count * friction * theta_dot,
    )
    # friction already includes the minus sign of -tau tanh, so the last
    # contract term -N*tau*theta_dot*tanh equals N*friction*theta_dot.
    return sum(terms), sum(abs(term) for term in terms), terms[-1]


@recorded_case("C2V-01")
def test_c2v01_represented_algebra() -> None:
    rows = []
    separated = {name: False for name in ("A", "B", "C", "D")}
    state = (-0.4, 0.2, 40.0)
    pairs = ((-0.02, 0.004), (0.015, -0.003))
    partial = measurement_partial()
    partial["metrics"] = {"rows": rows, "mutants_separated": separated}
    systems = {count: _system(count) for count in (1, 2, 4)}
    controls = _controls()
    for count, system in systems.items():
        for pair in pairs:
            freeze_case_before_measurement("C2V-01", system=system, controls=controls,
                executed_inputs={"state_rad": list(state), "Qm_nm": .05, "Qh_nm": .001, "load_pair_nm": list(pair)})
    partial["freeze_complete"] = True
    for count, system in systems.items():
        for q_phi, q_theta in pairs:
            m00, m01, m11, _coupling = _matrix(system, state[0])
            shaft, hinge = _rhs(system, *state, 0.05, 0.001, q_phi, q_theta)
            produced = _production_acceleration(system, *state, 0.05, 0.001, q_phi, q_theta)
            row = {"N": count, "loads": [q_phi, q_theta], "production_accelerations_rad_s2": list(produced)}
            rows.append(row)
            report, _reference, bound = _audit_solution(m00, m01, m11, shaft, hinge, produced)
            row["audit"] = report
            mutants = {
                "A": (count * q_phi, q_theta),
                "B": (q_phi, q_theta / count if count else q_theta),
                "C": (q_phi, count * q_theta),
                "D": (q_phi, -q_theta),
            }
            # B removes the collective factor: the one-tip value is used where
            # the hinge row would otherwise multiply by N, so the represented
            # one-tip input that cancels that factor is q_theta itself only
            # when the mutant omits the outer N. The independent mutant RHS
            # applies the missing-N form directly.
            mutant_rhs = {
                "A": _rhs(system, *state, 0.05, 0.001, count * q_phi, q_theta),
                "B": (
                    _rhs(system, *state, 0.05, 0.001, q_phi, 0.0)[0],
                    hinge - count * q_theta + q_theta,
                ),
                "C": _rhs(system, *state, 0.05, 0.001, q_phi, count * q_theta),
                "D": _rhs(system, *state, 0.05, 0.001, q_phi, -q_theta),
            }
            gaps = {}
            correct = _solve_fraction(m00, m01, m11, shaft, hinge)
            for name, loads in mutant_rhs.items():
                mutant = _solve_fraction(m00, m01, m11, loads[0], loads[1])
                gap = max(
                    abs(mutant[0] - correct[0]),
                    abs(mutant[1] - correct[1]),
                )
                gaps[name] = float(gap)
                if gap > bound and (name == "D" or count > 1):
                    separated[name] = True
            row["gaps_rad_s2"] = gaps
    passed = all(row["audit"]["classification"] == "PASS" for row in rows) and all(separated.values())
    _publish(
        "C2V-01",
        {
            "primary_evidence_class": "MATHEMATICAL",
            "purpose": "represented paired-load algebra",
            "classification": "PASS" if passed else "FAIL",
            "oracle_method": "Fraction.from_float exact 2x2 determinant",
            "independence_limit": "production acceleration is the subject, not the oracle",
            "executed_inputs": {"state_rad": list(state), "Qm_nm": 0.05, "Qh_nm": 0.001},
            "metrics": {"rows": rows, "mutants_separated": separated},
            "units": {"gaps_rad_s2": "rad/s^2", "B_abs_rad_s2": "rad/s^2"},
            "reference_stabilization": None,
            "acceptance_rule": "row backward error and Q2 forward bound",
            "threshold_basis": "section 10 prc_represented_forward_v1",
            "limitations": "no trajectory and no FoldableBEM qualification",
        },
    )
    assert passed, "C2V-01 represented algebra or mutant separation failed"


def _analytic_bridge(produced, reference, b_solve: Fraction) -> dict[str, object]:
    assembly = max(abs(reference[0]), abs(reference[1]))
    analytic_error = max(
        abs(Fraction.from_float(float(produced[0]))),
        abs(Fraction.from_float(float(produced[1]))),
    )
    return {
        "x_analytic_rad_s2": [0.0, 0.0],
        "x_repr_rad_s2": [float(reference[0]), float(reference[1])],
        "B_assembly_rad_s2": float(assembly),
        "B_solve_rad_s2": float(b_solve),
        "E_analytic_rad_s2": float(analytic_error),
        "analytic_bridge_pass": analytic_error <= assembly + b_solve,
    }


@recorded_case("C2V-02")
def test_c2v02_exact_equilibrium() -> None:
    system = _system(2)
    theta, omega, motor_nm, hinge_nm = -0.4, 40.0, 0.05, 0.001
    q_phi, q_theta = _target_loads(system, theta, 0.0, omega, 0.0, 0.0, motor_nm, hinge_nm)
    executed = {
        "theta_rad": theta,
        "theta_dot_rad_s": 0.0,
        "omega_rad_s": omega,
        "Qm_nm": motor_nm,
        "Qh_nm": hinge_nm,
        "Q_phi_nm": q_phi,
        "q_theta_nm": q_theta,
        "duration_s": 0.02,
        "actuation_knots_s": [0., .02], "actuation_torques_nm": [.001, .001],
    }
    controls = _controls()
    frozen = freeze_case_before_measurement(
        "C2V-02",
        system=system,
        controls=controls,
        executed_inputs=executed,
    )
    measurement_partial()["freeze_complete"] = True
    q_phi_matches = q_phi == pytest.approx(-motor_nm)
    m00, m01, m11, _coupling = _matrix(system, theta)
    shaft, hinge = _rhs(system, theta, 0.0, omega, motor_nm, hinge_nm, q_phi, q_theta)
    produced = _production_acceleration(system, theta, 0.0, omega, motor_nm, hinge_nm, q_phi, q_theta)
    measurement_partial()["metrics"] = {"production_accelerations_rad_s2": list(produced)}
    report, reference, bound = _audit_solution(m00, m01, m11, shaft, hinge, produced)
    measurement_partial()["metrics"]["q2_audit"] = report
    bridge = _analytic_bridge(produced, reference, bound)
    measurement_partial()["metrics"] = {"q2_audit": report, **bridge}
    result = _run(
        system,
        0.02,
        theta,
        0.0,
        omega,
        lambda *_args: MotorEvaluation(motor_nm),
        lambda _time, angle, rate, speed: Cmm2AeroEvaluation(
            q_phi, q_theta, 1.0, LOAD_MAPPING_MODEL, AERO_LOAD_QUALIFICATION,
            PROJECTION_MODEL, HINGE_RATE_AERO_MODEL, 2, R_HINGE, angle, rate, "c2v02",
        ),
        controls=controls,
        actuation=HingeActuationHistory((0.0, 0.02), (hinge_nm, hinge_nm), "prc"),
    )
    worst = None
    if result.status == "completed" and result.samples:
        worst = _worst_sample(
            controls,
            result.samples,
            lambda _time: (theta, 0.0, omega),
        )
    trajectory_pass = bool(
        worst is not None
        and worst.get("valid") is True
        and worst["e"] <= 1.0
        and result.status == "completed"
    )
    q2_pass = report["classification"] == "PASS"
    bridge_pass = bridge["analytic_bridge_pass"] is True
    passed = bool(q_phi_matches and q2_pass and bridge_pass and trajectory_pass)
    _publish(
        "C2V-02",
        {
            "primary_evidence_class": "INDEPENDENT_NUMERICAL",
            "purpose": "constant equilibrium",
            "classification": "PASS" if passed else "FAIL",
            "oracle_method": "independent represented solve plus exact constant state",
            "independence_limit": "Q_phi and q_theta are not taken from a production residual",
            "executed_inputs": executed,
            "premeasurement_digest": frozen["premeasurement_digest"],
            "metrics": {
                "q_phi_nm": q_phi,
                "q_theta_nm": q_theta,
                "q2_audit": report,
                "B_assembly_rad_s2": bridge["B_assembly_rad_s2"],
                "B_solve_rad_s2": bridge["B_solve_rad_s2"],
                "E_analytic_rad_s2": bridge["E_analytic_rad_s2"],
                "x_repr_rad_s2": bridge["x_repr_rad_s2"],
                "analytic_bridge_pass": bridge_pass,
                "q2_pass": q2_pass,
                "trajectory_pass": trajectory_pass,
                "trajectory_status": result.status,
                "worst_state_error": worst,
            },
            "units": {
                "B_assembly_rad_s2": "rad/s^2",
                "B_solve_rad_s2": "rad/s^2",
                "E_analytic_rad_s2": "rad/s^2",
                "q_phi_nm": "N*m",
                "q_theta_nm": "N*m",
                "worst_state_error.e": "1",
            },
            "reference_stabilization": None,
            "acceptance_rule": "Q2 represented solve and E_analytic <= B_assembly + B_solve, separately max e_j <= 1",
            "threshold_basis": "section 10 ordinary Q2; C2V-02 analytic bridge; section 7 max e_j <= 1",
            "limitations": "theta_dot is zero, so damping and friction torques vanish; trajectory failure stays FAIL",
        },
    )
    assert q_phi_matches
    assert passed, "C2V-02 trajectory gate max e_j <= 1 failed" if not trajectory_pass else "C2V-02 initial acceleration gate failed"


def _c2v03_target(time: float) -> tuple[float, float, float, float, float, float]:
    theta = -0.30 + 0.05 * math.sin(2.0 * math.pi * time / 0.2)
    theta_dot = 0.05 * (2.0 * math.pi / 0.2) * math.cos(2.0 * math.pi * time / 0.2)
    theta_ddot = -0.05 * (2.0 * math.pi / 0.2) ** 2 * math.sin(2.0 * math.pi * time / 0.2)
    omega = 40.0 + 2.0 * time
    return theta, theta_dot, theta_ddot, omega, 2.0, time


def _manufactured_callbacks(system: CoupledSystem):
    def loads(time: float):
        theta, theta_dot, theta_ddot, omega, omega_dot, _time = _c2v03_target(time)
        return _target_loads(system, theta, theta_dot, omega, omega_dot, theta_ddot, 0.04, 0.001)

    def motor(_time, _theta, _theta_dot, _omega):
        return MotorEvaluation(0.04)

    def aero(time, theta, theta_dot, _omega):
        q_phi, q_theta = loads(time)
        return Cmm2AeroEvaluation(
            q_phi, q_theta, 1.0, LOAD_MAPPING_MODEL, AERO_LOAD_QUALIFICATION,
            PROJECTION_MODEL, HINGE_RATE_AERO_MODEL, system.blade_count,
            system.parameters.hinge_radius_m, theta, theta_dot, "c2v03",
        )

    def rhs(_time, state):
        q_phi, q_theta = loads(_time)
        omega_dot, theta_ddot = _solve_fraction(
            *_matrix(system, state[0])[:3],
            *_rhs(system, state[0], state[1], state[2], 0.04, 0.001, q_phi, q_theta),
        )[:2]
        return (state[1], float(theta_ddot), float(omega_dot))

    return motor, aero, rhs, loads


def _manufactured_measurement():
    cached_error = getattr(_manufactured_measurement, "error", None)
    if cached_error is not None:
        raise cached_error
    cached = getattr(_manufactured_measurement, "value", None)
    if cached is not None:
        return cached
    _manufactured_measurement.partial = {}
    system = _system(2)
    controls = _controls()
    motor, aero, rhs, loads = _manufactured_callbacks(system)
    initial = _c2v03_target(0.0)
    if initial[0] != -0.30 or initial[3] != 40.0 or initial[4] != 2.0:
        raise AssertionError("shared target formula drifted before measurement")
    probe = _c2v03_target(0.05)
    q_phi, q_theta = loads(0.05)
    shared_inputs = _manufactured_inputs(initial)
    _manufactured_measurement.partial = {}
    try:
        frozen_03 = freeze_case_before_measurement(
            "C2V-03", system=system, controls=controls, executed_inputs=shared_inputs
        )
        _manufactured_measurement.partial = {"C2V-03": _snapshot_partial(frozen_03)}
        frozen_05 = freeze_case_before_measurement(
            "C2V-05", system=system, controls=controls, executed_inputs=shared_inputs
        )
        _manufactured_measurement.partial = {
            "C2V-03": _snapshot_partial(frozen_03),
            "C2V-05": _snapshot_partial(frozen_05),
        }
        result = _run(
            system,
            0.2,
            initial[0],
            initial[1],
            initial[3],
            motor,
            aero,
            controls=controls,
            actuation=HingeActuationHistory((0.0, 0.2), (0.001, 0.001), "prc"),
        )
        for case_partial in _manufactured_measurement.partial.values():
            case_partial["metrics"] = {"result_status": result.status, "sample_count": len(result.samples), "q_phi_sample_nm": q_phi, "q_theta_sample_nm": q_theta}
        times = [sample.time_s for sample in result.samples]
        stabilization = _stabilization_metrics(
            rhs, (initial[0], initial[1], initial[3]), times, controls
        )
        reference = stabilization.pop("reference_b")
        worst = None
        if stabilization["stabilized"] and reference is not None and result.samples:
            worst = _worst_sample(
                controls,
                result.samples,
                lambda time: tuple(float(value) for value in reference.sol(time)),
            )
        trajectory_pass = bool(
            stabilization["stabilized"]
            and result.status == "completed"
            and worst is not None
            and worst.get("valid") is True
            and worst["e"] <= 1.0
        )
        cached = {
            "coupling_nonzero": _tip_c(system.parameters) != 0.0,
            "target_nonzero": probe[1] != 0.0 and probe[4] != 0.0 and probe[2] != 0.0,
            "loads_nonzero": q_phi != 0.0 and q_theta != 0.0,
            "q_phi_nm": q_phi,
            "q_theta_nm": q_theta,
            "result_status": result.status,
            "stabilization": stabilization,
            "worst_state_error": worst,
            "trajectory_pass": trajectory_pass,
            "premeasurement_digest": frozen_03["premeasurement_digest"],
            "premeasurement_digest_c2v05": frozen_05["premeasurement_digest"],
        }
        cached["premeasurement_snapshots"] = {"C2V-03": frozen_03, "C2V-05": frozen_05}
        _manufactured_measurement.value = cached
        return cached
    except Exception as exc:
        _manufactured_measurement.error = exc
        raise


_manufactured_measurement.value = None
_manufactured_measurement.error = None
_manufactured_measurement.partial = {}


def _trajectory_case_payload(measurement: dict[str, object], purpose: str, oracle: str) -> dict[str, object]:
    stabilization = measurement["stabilization"]
    stabilized = stabilization["stabilized"] is True
    trajectory_pass = measurement["trajectory_pass"] is True
    passed = stabilized and trajectory_pass
    return {
        "primary_evidence_class": "INDEPENDENT_NUMERICAL",
        "purpose": purpose,
        "classification": "PASS" if passed else "FAIL",
        "oracle_method": oracle,
        "independence_limit": "loads are target-time functions, not production-state functions",
        "executed_inputs": {"duration_s": 0.2, "Qm_nm": 0.04, "Qh_nm": 0.001},
        "metrics": {
            "max_abs_A_minus_B_over_S": stabilization["max_abs_A_minus_B_over_S"],
            "max_abs_A_minus_B_over_0_1_S": stabilization["max_abs_A_minus_B_over_0_1_S"],
            "trajectory_pass": trajectory_pass,
            "worst_state_error": measurement["worst_state_error"],
            "result_status": measurement["result_status"],
            "q_phi_sample_nm": measurement["q_phi_nm"],
            "q_theta_sample_nm": measurement["q_theta_nm"],
            "reference_reason": stabilization["reason"],
        },
        "units": {
            "max_abs_A_minus_B_over_S": "1",
            "max_abs_A_minus_B_over_0_1_S": "1",
            "worst_state_error.e": "1",
            "q_phi_sample_nm": "N*m",
            "q_theta_sample_nm": "N*m",
        },
        "reference_stabilization": {
            "max_abs_A_minus_B_over_S_limit": 0.1,
            "max_abs_A_minus_B_over_0_1_S_limit": 1.0,
            "stabilized": stabilized,
            "reason": stabilization["reason"],
        },
        "acceptance_rule": "section 7 after DOP853 A/B stabilization; stabilization alone is not a pass",
        "threshold_basis": "abs(A-B) <= 0.1 S_j and max e_j <= 1",
        "limitations": "manufactured force is not the planar map",
        "pass_blocked_reason": None if passed else stabilization["reason"] or "trajectory gate max e_j <= 1 failed",
    }


def _manufactured_inputs(initial=None):
    initial = initial or _c2v03_target(0.0)
    return {"duration_s": .2, "Qm_nm": .04, "Qh_nm": .001,
            "initial_state_rad": [initial[0], initial[1], initial[3]],
            "theta_formula": "theta*(t) = -0.30 + 0.05 * sin(2 * pi * t / 0.2)",
            "omega_formula": "omega*(t) = 40 + 2 * t", "omega_dot_rad_s2": 2.,
            "load_formula": "Q_phi*(t) and q_theta*(t) solve the target equations at the target state and accelerations",
            "actuation_knots_s": [0., .2], "actuation_torques_nm": [.001, .001]}


def _snapshot_partial(snapshot):
    return {"freeze_complete": True, "premeasurement_snapshots": [snapshot],
            "premeasurement_digest": snapshot["premeasurement_digest"],
            "fixture_digest": snapshot["premeasurement_digest"],
            "executed_inputs": snapshot["executed_inputs"], "controls": snapshot["controls"]}


def _shared_measurement_or_partial(case_id, partial: dict[str, object]):
    try:
        result = _manufactured_measurement()
        partial.update(_snapshot_partial(result["premeasurement_snapshots"][case_id]))
        return result
    except Exception:
        partial.update((getattr(_manufactured_measurement, "partial", {}) or {}).get(case_id, {}))
        raise


def test_c2v03_manufactured_trajectory() -> None:
    def measure(partial):
        measurement = _shared_measurement_or_partial("C2V-03", partial)
        payload = _trajectory_case_payload(
            measurement,
            "manufactured coupled trajectory",
            "independent target right-hand side",
        )
        payload["premeasurement_digest"] = measurement["premeasurement_digest"]
        partial["metrics"] = payload["metrics"]
        partial["premeasurement_digest"] = measurement["premeasurement_digest"]
        payload["premeasurement_snapshots"] = partial["premeasurement_snapshots"]
        payload["executed_inputs"] = partial["executed_inputs"]
        return payload

    def checks(payload):
        measurement = _manufactured_measurement()
        if not measurement["coupling_nonzero"]:
            raise AssertionError("shared target coupling is zero")
        if not measurement["target_nonzero"]:
            raise AssertionError("shared target derivatives vanished")
        if not measurement["loads_nonzero"]:
            raise AssertionError("shared target loads vanished")
        if payload["classification"] != "PASS":
            raise AssertionError(str(payload.get("pass_blocked_reason")))

    execute_measured_case("C2V-03", measure, checks=[checks])


def test_c2v05_dop853_reference() -> None:
    def measure(partial):
        measurement = _shared_measurement_or_partial("C2V-05", partial)
        payload = _trajectory_case_payload(
            measurement,
            "DOP853 reference on the C2V-03 right-hand side",
            "DOP853 Reference A and Reference B",
        )
        if measurement["stabilization"]["stabilized"] is True and measurement["trajectory_pass"] is not True:
            payload["classification"] = "FAIL"
            payload["pass_blocked_reason"] = "production versus Reference B failed max e_j <= 1"
        payload["premeasurement_digest"] = measurement["premeasurement_digest_c2v05"]
        partial["metrics"] = payload["metrics"]
        partial["premeasurement_digest"] = measurement["premeasurement_digest_c2v05"]
        payload["premeasurement_snapshots"] = partial["premeasurement_snapshots"]
        payload["executed_inputs"] = partial["executed_inputs"]
        return payload

    execute_measured_case("C2V-05", measure)


@recorded_case("C2V-04")
def test_c2v04_independent_work() -> None:
    system = _system(2)
    _motor, _aero, _rhs, loads = _manufactured_callbacks(system)

    def sample(time: float):
        theta, theta_dot, theta_ddot, omega, omega_dot, _time = _c2v03_target(time)
        q_phi, q_theta = loads(time)
        rate = _energy_rate(system, theta, theta_dot, omega, omega_dot, theta_ddot)
        power, scale, _friction_power = _power(
            system, theta, theta_dot, omega, 0.04, 0.001, q_phi, q_theta
        )
        residual = rate - power
        allowance = 0.0 if scale == 0.0 else max(1.0e-8 * scale, 64.0 * math.ulp(scale))
        return residual, allowance, power

    inputs = _manufactured_inputs()
    inputs.pop("actuation_knots_s")
    inputs.pop("actuation_torques_nm")
    inputs.update(quad_A_epsrel=1.e-10, quad_B_epsrel=1.e-12, quad_epsabs=0., power_sample_times_s=[i / 20. for i in range(5)])
    frozen = freeze_case_before_measurement("C2V-04", system=system, controls=_controls(), executed_inputs=inputs)
    measurement_partial()["freeze_complete"] = True
    residuals = []
    measurement_partial()["metrics"] = {"power_samples": residuals}
    for time in inputs["power_sample_times_s"]:
        residuals.append(sample(time))
    power_pass = all(abs(residual) <= allowance for residual, allowance, _power_value in residuals)
    quadrature_reason = None
    quadrature_error = None
    integral_a = error_a = integral_b = error_b = None
    energy_scale = quadrature_uncertainty = roundoff = energy_residual = None

    def integrand(time: float) -> float:
        _residual, _allowance, power = sample(time)
        return power

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", IntegrationWarning)
            integral_a, error_a = quad(integrand, 0.0, 0.2, epsabs=inputs["quad_epsabs"], epsrel=inputs["quad_A_epsrel"])
            measurement_partial()["metrics"].update(integral_a_j=integral_a, error_a_j=error_a)
            integral_b, error_b = quad(integrand, 0.0, 0.2, epsabs=inputs["quad_epsabs"], epsrel=inputs["quad_B_epsrel"])
        reliable, reliable_reason = _quadrature_is_reliable(integral_a, error_a, integral_b, error_b)
        if caught or not reliable:
            quadrature_reason = reliable_reason or "QUADRATURE REFERENCE NOT RELIABLE"
        else:
            start = _c2v03_target(0.0)
            end = _c2v03_target(0.2)
            energy_start = _mechanical(system, start[0], start[1], start[3])
            energy_end = _mechanical(system, end[0], end[1], end[3])
            energy_scale = abs(energy_end) + abs(energy_start) + abs(integral_b)
            quadrature_uncertainty = max(error_b, abs(integral_b - integral_a))
            roundoff = max(1.0e-8 * energy_scale, 64.0 * math.ulp(energy_scale))
            energy_residual = energy_end - energy_start - integral_b
            if not (
                energy_scale > 0.0
                and quadrature_uncertainty <= 0.1 * roundoff
                and abs(energy_residual) <= roundoff + quadrature_uncertainty
            ):
                quadrature_reason = "QUADRATURE REFERENCE NOT RELIABLE" if not (
                    energy_scale > 0.0 and quadrature_uncertainty <= 0.1 * roundoff
                ) else "energy gate failed"
    except Exception as exc:
        quadrature_error = exc
        quadrature_reason = f"QUADRATURE REFERENCE NOT RELIABLE: {type(exc).__name__}: {exc}"
    passed = power_pass and quadrature_reason is None
    _publish(
        "C2V-04",
        {
            "primary_evidence_class": "INDEPENDENT_NUMERICAL",
            "purpose": "independent work and energy",
            "classification": "PASS" if passed else "FAIL",
            "oracle_method": "independent power identity and scipy.integrate.quad",
            "independence_limit": "production cumulative_work_j is not the oracle",
            "executed_inputs": {"duration_s": 0.2, "Qm_nm": 0.04, "Qh_nm": 0.001},
            "premeasurement_digest": frozen["premeasurement_digest"],
            "metrics": {
                "max_abs_power_residual_w": max(abs(item[0]) for item in residuals),
                "integral_a_j": integral_a,
                "error_a_j": error_a,
                "integral_b_j": integral_b,
                "error_b_j": error_b,
                "U_quad_j": quadrature_uncertainty,
                "U_round_E_j": roundoff,
                "R_E_j": energy_residual,
                "quadrature_reason": quadrature_reason,
            },
            "units": {
                "max_abs_power_residual_w": "W",
                "integral_a_j": "J",
                "error_a_j": "J",
                "integral_b_j": "J",
                "error_b_j": "J",
                "U_quad_j": "J",
                "U_round_E_j": "J",
                "R_E_j": "J",
            },
            "reference_stabilization": None,
            "acceptance_rule": "U_P watt gate, then U_quad <= 0.1 U_round_E, then energy gate",
            "threshold_basis": "section C2V-04 watt and quadrature gates",
            "limitations": "production cumulative_work_j is not the oracle",
            "pass_blocked_reason": None if passed else quadrature_reason or "watt gate failed",
        },
    )
    if quadrature_error is not None:
        raise quadrature_error
    assert passed, quadrature_reason or "C2V-04 watt gate failed"


def _mechanical(system: CoupledSystem, theta: float, theta_dot: float, omega: float) -> float:
    m00, m01, m11, _coupling = _matrix(system, theta)
    kinetic = 0.5 * m00 * omega**2 + m01 * omega * theta_dot + 0.5 * m11 * theta_dot**2
    spring = 0.5 * system.blade_count * system.parameters.spring_stiffness_nm_rad * (
        theta - system.parameters.rest_angle_rad
    ) ** 2
    return kinetic + spring


@recorded_case("C2V-06")
def test_c2v06_zero_hinge_limit() -> None:
    system = _system(2)
    theta, theta_dot, omega = -0.3, 0.1, 40.0
    resisting = 0.02
    executed = {"theta_rad": theta, "theta_dot_rad_s": theta_dot, "omega_rad_s": omega, "Qa_nm": resisting, "Q_phi_nm": -resisting, "q_theta_nm": 0., "Qm_nm": .04, "Qh_nm": .001}
    freeze_case_before_measurement("C2V-06", system=system, controls=_controls(), executed_inputs=executed)
    measurement_partial()["freeze_complete"] = True
    cmm2_values = _production_acceleration(system, theta, theta_dot, omega, 0.04, 0.001, -resisting, 0.0)
    measurement_partial()["metrics"] = {"cmm2_accelerations_rad_s2": list(cmm2_values)}
    cmm1 = coupled_accelerations(system, theta, theta_dot, omega, 0.04, resisting, 0.001)
    compared = (
        (cmm2_values[0], cmm1.omega_dot_rad_s2),
        (cmm2_values[1], cmm1.theta_ddot_rad_s2),
        (_rhs(system, theta, theta_dot, omega, 0.04, 0.001, -resisting, 0.0)[0], cmm1.rhs_shaft_nm),
        (_rhs(system, theta, theta_dot, omega, 0.04, 0.001, -resisting, 0.0)[1], cmm1.rhs_hinge_nm),
    )
    distances = [_ulp_distance(left, right) for left, right in compared]
    passed = max(distances) <= 1
    _publish(
        "C2V-06",
        {
            "primary_evidence_class": "CROSS_MODEL",
            "purpose": "zero-hinge CMM-1 limit",
            "classification": "PASS" if passed else "FAIL",
            "oracle_method": "CMM-1 coupled_accelerations at q_theta = 0 and Q_phi = -Qa",
            "independence_limit": "CMM-1 verification module is not the oracle",
            "executed_inputs": {
                "theta_rad": theta,
                "theta_dot_rad_s": theta_dot,
                "omega_rad_s": omega,
                "Qa_nm": resisting,
                "Q_phi_nm": -resisting,
                "q_theta_nm": 0.0,
            },
            "metrics": {"max_ulp": max(distances), "ulp_distances": distances},
            "units": {"max_ulp": "ULP"},
            "reference_stabilization": None,
            "acceptance_rule": "represented scalars within 1 ULP",
            "threshold_basis": "ULP distance at most 1",
            "limitations": "not a transfer of CMM-1 Phase-4 evidence",
        },
    )
    assert passed, "C2V-06 one-ULP limit failed"


def _zero_acceleration_loads(system, theta, theta_dot, omega, motor_nm, hinge_nm):
    return _target_loads(system, theta, theta_dot, omega, 0.0, 0.0, motor_nm, hinge_nm)


@recorded_case("C2V-07")
def test_c2v07_manufactured_contact(monkeypatch) -> None:
    system = _system(2, _mechanism(lower_stop_rad=-0.50, upper_stop_rad=0.20))
    observed: dict[str, object] = {}
    original = _first_contact

    def wrapped(dense, start, end, y0, y1, parameters, controls):
        result = original(dense, start, end, y0, y1, parameters, controls)
        if result is not None:
            _name, event_time, _event_state = result
            observed["start"] = start
            observed["end"] = end
            observed["event_time"] = event_time
            observed["theta_dense"] = dense(event_time)[0]
            observed["omega_dense"] = dense(event_time)[2]
            observed["dense"] = dense
        return result

    monkeypatch.setattr(cmm2, "_first_contact", wrapped)

    def motor(_time, _theta, _rate, _omega):
        return MotorEvaluation(0.04)

    def aero(time, theta, theta_dot, omega):
        angle = -0.20 - 0.40 * time
        q_phi, q_theta = _zero_acceleration_loads(system, angle, -0.40, 40.0, 0.04, 0.0)
        return Cmm2AeroEvaluation(
            q_phi, q_theta, 1.0, LOAD_MAPPING_MODEL, AERO_LOAD_QUALIFICATION,
            PROJECTION_MODEL, HINGE_RATE_AERO_MODEL, 2, R_HINGE, theta, theta_dot, "c2v07",
        )

    executed = {"duration_s": 1., "theta_rad": -.20, "theta_dot_rad_s": -.40, "omega_rad_s": 40., "Qm_nm": .04, "Qh_nm": 0., "theta_rate_rad_s": -.40, "theta_ddot_rad_s2": 0., "omega_dot_rad_s2": 0., "load_formula": "zero_acceleration_target", "actuation_knots_s": [0., 1.], "actuation_torques_nm": [0., 0.]}
    controls = _controls()
    freeze_case_before_measurement("C2V-07", system=system, controls=controls, executed_inputs=executed)
    measurement_partial()["freeze_complete"] = True
    measurement_partial()["metrics"] = observed
    result = _run(system, 1.0, -0.20, -0.40, 40.0, motor, aero, controls)
    metrics = {
        "t_contact_s": None,
        "T_allow_s": None,
        "D_event_rad": None,
        "S_theta_event_rad": None,
        "angle_tol_contact_rad": None,
    }
    passed = False
    reason = None
    if result.status != "first_contact_terminal" or result.contact is None or not observed:
        reason = "contact reconstruction was not available"
    elif result.contact.stop != "lower":
        reason = "contact stop was not the lower stop"
    else:
        theta_target = -0.20 - 0.40 * float(observed["event_time"])
        scale = controls.angle_atol_rad + controls.rtol * abs(theta_target)
        dense_error = abs(float(observed["theta_dense"]) - theta_target)
        start = float(observed["start"])
        end = float(observed["end"])
        width = end - start
        nodes = [start + width * index / 4.0 for index in range(5)]
        dense = observed["dense"]
        contact_scale = max(1.0, abs(-0.50), *(abs(dense(node)[0]) for node in nodes))
        angle_tolerance = max(8.0 * controls.angle_atol_rad, 2.0 * math.ulp(contact_scale))
        xi = (float(observed["event_time"]) - start) / width
        root_time = width * (1.0e-14 + 1.0e-14 * abs(xi))
        allowance = (scale + 4.0 * angle_tolerance) / 0.40 + root_time
        rate_scale = controls.hinge_velocity_atol_rad_s + controls.rtol * 0.40
        speed_scale = controls.shaft_speed_atol_rad_s + controls.rtol * 40.0
        metrics = {
            "t_contact_s": result.contact.time_s,
            "T_allow_s": allowance,
            "D_event_rad": dense_error,
            "S_theta_event_rad": scale,
            "angle_tol_contact_rad": angle_tolerance,
        }
        passed = (
            dense_error <= scale
            and abs(float(observed["theta_dense"]) - (-0.50)) <= 4.0 * angle_tolerance
            and abs(result.contact.time_s - 0.75) <= allowance
            and abs(result.contact.preimpact_angular_velocity_rad_s - (-0.40)) <= rate_scale
            and abs(result.contact.omega_rad_s - 40.0) <= speed_scale
            and all(sample.time_s <= result.contact.time_s + 1.0e-15 for sample in result.samples)
        )
        if not passed:
            reason = "manufactured contact gate failed"
    _publish(
        "C2V-07",
        {
            "primary_evidence_class": "INDEPENDENT_NUMERICAL",
            "purpose": "manufactured first contact",
            "classification": "PASS" if passed else "FAIL",
            "oracle_method": "analytic first-contact target",
            "independence_limit": "the wrapper observes production dense output and does not replace the solver",
            "executed_inputs": {"duration_s": 1.0, "lower_stop_rad": -0.50, "upper_stop_rad": 0.20},
            "metrics": metrics,
            "units": {
                "t_contact_s": "s",
                "T_allow_s": "s",
                "D_event_rad": "rad",
                "S_theta_event_rad": "rad",
                "angle_tol_contact_rad": "rad",
            },
            "reference_stabilization": None,
            "acceptance_rule": "pre-snap dense gate, production angle tolerance, and T_allow",
            "threshold_basis": "section C2V-07 contact gates",
            "limitations": "not an all-interval dense-error theorem",
            "pass_blocked_reason": reason,
        },
    )
    assert passed, reason or "C2V-07 contact gate failed"


def _exception_text(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    cause = exc.__cause__
    if cause is not None:
        text = f"{text}; cause {type(cause).__name__}: {cause}"
    return text


def _expect_layer(name, exc_type, match, action, layers):
    try:
        action()
    except exc_type as exc:
        text = _exception_text(exc)
        if match is not None and match not in text:
            layers[name] = text
            raise
        layers[name] = text
        return
    except Exception as exc:
        layers[name] = _exception_text(exc)
        raise
    layers[name] = f"missing {exc_type.__name__}"
    raise AssertionError(f"{name} did not raise {exc_type.__name__}")


def _c2v08_payload(layers, calls, digest, passed, reason):
    return {
        "primary_evidence_class": "REGRESSION_CONTRACT",
        "purpose": "fail-closed boundaries",
        "classification": "PASS" if passed else "FAIL",
        "oracle_method": "expected exception layer for each manufactured boundary",
        "independence_limit": "callbacks are the production request callbacks",
        "executed_inputs": {"subcases": ["fold", "speed", "budget", "hard"]},
        "premeasurement_digest": digest,
        "metrics": {"failure_layers": dict(layers), "speed_callbacks_invoked": list(calls)},
        "units": {},
        "reference_stabilization": None,
        "acceptance_rule": "no shortened success artifact",
        "threshold_basis": "section C2V-08 expected exception layers",
        "limitations": "not a catalogue of every lower-layer exception",
        "record_reason": reason,
        "pass_blocked_reason": reason,
    }


@recorded_case("C2V-08")
def _execute_c2v08(fold_aero=None):
    layers = {}
    calls = []
    partial = measurement_partial()
    partial["metrics"] = {"failure_layers": layers, "speed_callbacks_invoked": calls}
    systems = {"fold": _system(2, _mechanism(lower_stop_rad=-2., upper_stop_rad=.5)),
               "speed": _system(2), "budget": _system(2), "hard": _system(2)}
    inputs = {
        "fold": dict(duration_s=.5, theta_rad=-1.2, theta_dot_rad_s=-1., omega_rad_s=40., Qm_nm=.04, Qh_nm=0., theta_rate_rad_s=-1., theta_ddot_rad_s2=0., omega_dot_rad_s2=0., load_formula="zero_acceleration_target"),
        "speed": dict(duration_s=.2, theta_rad=-.3, theta_dot_rad_s=0., omega_rad_s=10., Qm_nm=.04, Qh_nm=0., load_formula="unreachable_counting_callback"),
        "budget": dict(duration_s=.2, theta_rad=-.3, theta_dot_rad_s=.1, omega_rad_s=40., Qm_nm=.04, Qh_nm=0., Q_phi_nm=-.02, q_theta_nm=.004),
        "hard": dict(duration_s=.2, theta_rad=-.3, theta_dot_rad_s=.1, omega_rad_s=40., Qm_nm=.04, Qh_nm=0., load_formula="raises_Cmm2TransientFailure", failure_message="hard failure"),
    }
    controls = {name: _controls(max_rhs_evaluations=1) if name == "budget" else _controls() for name in inputs}
    for name, executed in inputs.items():
        executed.update(actuation_knots_s=[0., executed["duration_s"]], actuation_torques_nm=[0., 0.])
        freeze_case_before_measurement("C2V-08", system=systems[name], controls=controls[name], executed_inputs=executed, subcase=name)

    partial["freeze_complete"] = True

    def default_fold(time, theta, theta_dot, _omega):
        row = inputs["fold"]
        q_phi, q_theta = _zero_acceleration_loads(systems["fold"], row["theta_rad"] + row["theta_rate_rad_s"] * time, row["theta_dot_rad_s"], row["omega_rad_s"], row["Qm_nm"], row["Qh_nm"])
        return Cmm2AeroEvaluation(q_phi, q_theta, 1., LOAD_MAPPING_MODEL, AERO_LOAD_QUALIFICATION,
            PROJECTION_MODEL, HINGE_RATE_AERO_MODEL, 2, R_HINGE, theta, theta_dot, "fold")

    def counting(*_args):
        calls.append(1)
        return MotorEvaluation(inputs["speed"]["Qm_nm"])

    def budget_aero(_time, theta, theta_dot, _omega):
        row = inputs["budget"]
        return Cmm2AeroEvaluation(row["Q_phi_nm"], row["q_theta_nm"], 1., LOAD_MAPPING_MODEL, AERO_LOAD_QUALIFICATION,
            PROJECTION_MODEL, HINGE_RATE_AERO_MODEL, 2, R_HINGE, theta, theta_dot, "budget")

    def hard(*_args):
        raise Cmm2TransientFailure(inputs["hard"]["failure_message"])

    aero_callbacks = {"fold": fold_aero or default_fold, "speed": counting, "budget": budget_aero, "hard": hard}
    expected_layers = {"fold": (Cmm2DomainExit, None), "speed": (Cmm2TransientError, "100 rpm"),
                       "budget": (Cmm2TransientFailure, "work budget exhausted"), "hard": (Cmm2TransientFailure, "hard failure")}
    for name, row in inputs.items():
        def action(name=name, row=row):
            return _run(systems[name], row["duration_s"], row["theta_rad"], row["theta_dot_rad_s"], row["omega_rad_s"],
                        counting if name == "speed" else lambda *_args: MotorEvaluation(row["Qm_nm"]),
                        aero_callbacks[name], controls[name],
                        actuation=HingeActuationHistory(tuple(row["actuation_knots_s"]), tuple(row["actuation_torques_nm"]), "prc"))
        _expect_layer(name, *expected_layers[name], action, layers)
        if name == "speed" and calls:
            raise AssertionError("speed callback was invoked")
    passed = set(layers) == {"fold", "speed", "budget", "hard"} and not calls
    _publish("C2V-08", _c2v08_payload(layers, calls, partial["premeasurement_digest"], passed, None))
    assert passed


def test_c2v08_fail_closed_layers() -> None:
    _execute_c2v08()


def run_c2v08_with_callback_fault(exc: BaseException) -> None:
    def faulty(*_args):
        raise exc

    _execute_c2v08(faulty)
