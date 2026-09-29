"""PR-C numerical verification for the frozen CMM-2 screening contract.

The frozen contract is the authority. Production code is the subject under
test. This module does not accept ADR-009 or physical qualification.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import subprocess
import tempfile
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


ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "configs/designs/TIP_HINGED_250_CANONICAL.toml"
CONTRACT_HEAD = "613072514f793f2a1bc65704f9158f536210707f"
EVIDENCE: dict[str, object] = {}
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


def _repository_head() -> str:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_name == "pull_request" and event_path:
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
        sha = payload.get("pull_request", {}).get("head", {}).get("sha")
        if isinstance(sha, str) and sha:
            return sha
    if event_name == "push" and os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


MANIFEST = {
    "shared": {
        "m_kg": M_MASS,
        "hinge_radius_m": R_HINGE,
        "cg_distance_m": C_CG,
        "hinge_inertia_kg_m2": J_HINGE,
        "base_inertia_kg_m2": I0_BASE,
        "spring_nm_rad": K_SPRING,
        "rest_rad": THETA_REST,
        "damping_nm_s_rad": B_DAMP,
        "coulomb_nm": TAU_C,
        "friction_velocity_rad_s": V_FRIC,
        "lower_stop_rad": LOWER,
        "upper_stop_rad": UPPER,
        "controls": {
            "rtol": 1.0e-6,
            "angle_atol_rad": 1.0e-8,
            "hinge_velocity_atol_rad_s": 1.0e-8,
            "shaft_speed_atol_rad_s": 1.0e-6,
            "max_step_s": 0.002,
        },
    },
    "policy_ids": {
        "threshold": "prc_state_scale_v1",
        "reference": "prc_dop853_ab_v1",
        "conditioning": "prc_represented_forward_v1",
        "selection": "prc_c2v09_ordered_candidates_v1",
        "manifest": "prc_critical_fixture_manifest_v1",
    },
}
MANIFEST_SHA = _sha(_canonical(MANIFEST))


@pytest.fixture(scope="session", autouse=True)
def _dump_prc_evidence(tmp_path_factory):
    yield
    path = tmp_path_factory.getbasetemp() / "cmm2_prc_evidence.json"
    path.write_text(
        json.dumps(EVIDENCE, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    print(f"CMM2_PRC_EVIDENCE {path}")


def _record(case_id: str, payload: dict[str, object]) -> None:
    payload = {
        "repository_head": _repository_head(),
        "contract_head": CONTRACT_HEAD,
        "case_id": case_id,
        "critical_fixture_manifest_sha256": MANIFEST_SHA,
        "threshold_policy_id": "prc_state_scale_v1",
        "reference_policy_id": "prc_dop853_ab_v1",
        "conditioning_policy_id": "prc_represented_forward_v1",
        "fixture_selection_policy_id": "prc_c2v09_ordered_candidates_v1",
        "model_class": MODEL_CLASS,
        "implementation_id": IMPLEMENTATION_ID,
        "component_order": ["theta", "theta_dot", "omega"],
        "physical_qualification": False,
        **payload,
    }
    json.dumps(payload, sort_keys=True, allow_nan=False)
    EVIDENCE[case_id] = payload


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
        raise AssertionError("REFERENCE NOT STABILIZED")
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
    if not solution.success or solution.sol is None:
        raise AssertionError("REFERENCE NOT STABILIZED")
    return solution


def _stabilize(rhs, y0, times, controls):
    first = _dop853(rhs, y0, times[-1], controls, "A")
    second = _dop853(rhs, y0, times[-1], controls, "B")
    worst = 0.0
    for time in times:
        left = first.sol(time)
        right = second.sol(time)
        scale = _state_scale(controls, tuple(right))
        for index in range(3):
            worst = max(worst, abs(left[index] - right[index]) / (0.1 * scale[index]))
            if abs(left[index] - right[index]) > 0.1 * scale[index]:
                raise AssertionError("REFERENCE NOT STABILIZED")
    return second, worst


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


def test_c2v01_represented_algebra() -> None:
    rows = []
    separated = {name: False for name in ("A", "B", "C", "D")}
    state = (-0.4, 0.2, 40.0)
    pairs = ((-0.02, 0.004), (0.015, -0.003))
    for count in (1, 2, 4):
        system = _system(count)
        for q_phi, q_theta in pairs:
            m00, m01, m11, _coupling = _matrix(system, state[0])
            shaft, hinge = _rhs(system, *state, 0.05, 0.001, q_phi, q_theta)
            produced = _production_acceleration(system, *state, 0.05, 0.001, q_phi, q_theta)
            report, _reference, bound = _audit_solution(m00, m01, m11, shaft, hinge, produced)
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
            rows.append({"N": count, "loads": [q_phi, q_theta], "audit": report, "gaps_rad_s2": gaps})
            assert report["classification"] == "PASS"
    assert all(separated.values())
    _record(
        "C2V-01",
        {
            "primary_evidence_class": "MATHEMATICAL",
            "purpose": "represented paired-load algebra",
            "classification": "PASS",
            "oracle_method": "Fraction.from_float exact 2x2 determinant",
            "independence_limit": "production acceleration is the subject, not the oracle",
            "metrics": {"rows": rows, "mutants_separated": separated},
            "acceptance_rule": "row backward error and Q2 forward bound",
            "limitations": "no trajectory and no FoldableBEM qualification",
        },
    )


def test_c2v02_exact_equilibrium() -> None:
    system = _system(2)
    theta, omega, motor_nm, hinge_nm = -0.4, 40.0, 0.05, 0.001
    q_phi, q_theta = _target_loads(system, theta, 0.0, omega, 0.0, 0.0, motor_nm, hinge_nm)
    assert q_phi == pytest.approx(-motor_nm)
    m00, m01, m11, _coupling = _matrix(system, theta)
    shaft, hinge = _rhs(system, theta, 0.0, omega, motor_nm, hinge_nm, q_phi, q_theta)
    produced = _production_acceleration(system, theta, 0.0, omega, motor_nm, hinge_nm, q_phi, q_theta)
    report, _reference, _bound = _audit_solution(m00, m01, m11, shaft, hinge, produced)
    assert report["classification"] == "PASS"
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
        actuation=HingeActuationHistory((0.0, 0.02), (hinge_nm, hinge_nm), "prc"),
    )
    controls = _controls()
    errors = [
        _max_state_error(controls, (sample.theta_rad, sample.theta_dot_rad_s, sample.omega_rad_s), (theta, 0.0, omega))
        for sample in result.samples
    ]
    assert result.status == "completed"
    assert max(max(row) for row in errors) <= 1.0
    _record(
        "C2V-02",
        {
            "primary_evidence_class": "INDEPENDENT_NUMERICAL",
            "purpose": "constant equilibrium",
            "classification": "PASS",
            "metrics": {
                "q_phi_nm": q_phi,
                "q_theta_nm": q_theta,
                "acceleration_audit": report,
                "max_state_e": max(max(row) for row in errors),
            },
            "acceptance_rule": "Q2 acceleration envelope and section 7 trajectory",
            "limitations": "theta_dot is zero, so damping and friction torques vanish",
        },
    )


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


def _trajectory_gate(system, duration, theta, theta_dot, omega, motor, aero, rhs, controls=None, actuation=None):
    controls = controls or _controls()
    result = _run(system, duration, theta, theta_dot, omega, motor, aero, controls, actuation)
    times = [sample.time_s for sample in result.samples]
    reference, ratio = _stabilize(rhs, (theta, theta_dot, omega), times, controls)
    errors = []
    for sample in result.samples:
        compared = reference.sol(sample.time_s)
        errors.append(
            _max_state_error(
                controls,
                (sample.theta_rad, sample.theta_dot_rad_s, sample.omega_rad_s),
                (float(compared[0]), float(compared[1]), float(compared[2])),
            )
        )
    worst = max(max(row) for row in errors)
    assert worst <= 1.0
    return result, worst, ratio


def test_c2v03_and_c2v05_manufactured_trajectory() -> None:
    system = _system(2)
    motor, aero, rhs, loads = _manufactured_callbacks(system)
    theta, theta_dot, theta_ddot, omega, omega_dot, _time = _c2v03_target(0.05)
    q_phi, q_theta = loads(0.05)
    assert _tip_c(system.parameters) != 0.0
    assert theta_dot != 0.0 and omega_dot != 0.0 and theta_ddot != 0.0
    assert q_phi != 0.0 and q_theta != 0.0
    result, worst, ratio = _trajectory_gate(
        system,
        0.2,
        *_c2v03_target(0.0)[:2],
        _c2v03_target(0.0)[3],
        motor,
        aero,
        rhs,
        actuation=HingeActuationHistory((0.0, 0.2), (0.001, 0.001), "prc"),
    )
    # _c2v03_target returns theta, theta_dot, theta_ddot, omega, omega_dot, time
    payload = {
        "primary_evidence_class": "INDEPENDENT_NUMERICAL",
        "classification": "PASS",
        "metrics": {"max_state_e": worst, "stabilization_ratio": ratio},
        "reference_stabilization": "DOP853 A versus B within 0.1 S_j",
        "acceptance_rule": "section 7 after reference stabilization",
        "independence_limit": "loads are target-time functions, not production-state functions",
    }
    _record("C2V-03", {**payload, "purpose": "manufactured coupled trajectory"})
    _record("C2V-05", {**payload, "purpose": "DOP853 reference on the C2V-03 right-hand side", "oracle_method": "DOP853"})
    assert result.status == "completed"


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

    residuals = [sample(time / 20.0) for time in range(5)]
    assert all(abs(residual) <= allowance for residual, allowance, _power_value in residuals)

    def integrand(time: float) -> float:
        _residual, _allowance, power = sample(time)
        return power

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", IntegrationWarning)
        integral_a, _error_a = quad(integrand, 0.0, 0.2, epsabs=0.0, epsrel=1.0e-10)
        integral_b, error_b = quad(integrand, 0.0, 0.2, epsabs=0.0, epsrel=1.0e-12)
    assert not caught
    assert all(math.isfinite(value) for value in (integral_a, integral_b, error_b))
    start = _c2v03_target(0.0)
    end = _c2v03_target(0.2)
    energy_start = _mechanical(system, start[0], start[1], start[3])
    energy_end = _mechanical(system, end[0], end[1], end[3])
    energy_scale = abs(energy_end) + abs(energy_start) + abs(integral_b)
    quadrature_uncertainty = max(error_b, abs(integral_b - integral_a))
    roundoff = max(1.0e-8 * energy_scale, 64.0 * math.ulp(energy_scale))
    assert energy_scale > 0.0
    assert quadrature_uncertainty <= 0.1 * roundoff
    energy_residual = energy_end - energy_start - integral_b
    assert abs(energy_residual) <= roundoff + quadrature_uncertainty
    _record(
        "C2V-04",
        {
            "primary_evidence_class": "INDEPENDENT_NUMERICAL",
            "purpose": "independent work and energy",
            "classification": "PASS",
            "metrics": {
                "max_abs_power_residual_w": max(abs(item[0]) for item in residuals),
                "U_quad_j": quadrature_uncertainty,
                "U_round_E_j": roundoff,
                "R_E_j": energy_residual,
            },
            "acceptance_rule": "U_P watt gate, then U_quad <= 0.1 U_round_E, then energy gate",
            "limitations": "production cumulative_work_j is not the oracle",
        },
    )


def _mechanical(system: CoupledSystem, theta: float, theta_dot: float, omega: float) -> float:
    m00, m01, m11, _coupling = _matrix(system, theta)
    kinetic = 0.5 * m00 * omega**2 + m01 * omega * theta_dot + 0.5 * m11 * theta_dot**2
    spring = 0.5 * system.blade_count * system.parameters.spring_stiffness_nm_rad * (
        theta - system.parameters.rest_angle_rad
    ) ** 2
    return kinetic + spring


def test_c2v06_zero_hinge_limit() -> None:
    system = _system(2)
    theta, theta_dot, omega = -0.3, 0.1, 40.0
    resisting = 0.02
    cmm2_values = _production_acceleration(system, theta, theta_dot, omega, 0.04, 0.001, -resisting, 0.0)
    cmm1 = coupled_accelerations(system, theta, theta_dot, omega, 0.04, resisting, 0.001)
    compared = (
        (cmm2_values[0], cmm1.omega_dot_rad_s2),
        (cmm2_values[1], cmm1.theta_ddot_rad_s2),
        (_rhs(system, theta, theta_dot, omega, 0.04, 0.001, -resisting, 0.0)[0], cmm1.rhs_shaft_nm),
        (_rhs(system, theta, theta_dot, omega, 0.04, 0.001, -resisting, 0.0)[1], cmm1.rhs_hinge_nm),
    )
    distances = [_ulp_distance(left, right) for left, right in compared]
    assert max(distances) <= 1
    _record(
        "C2V-06",
        {
            "primary_evidence_class": "CROSS_MODEL",
            "purpose": "zero-hinge CMM-1 limit",
            "classification": "PASS",
            "metrics": {"max_ulp": max(distances), "ulp_distances": distances},
            "acceptance_rule": "represented scalars within 1 ULP",
            "limitations": "not a transfer of CMM-1 Phase-4 evidence",
        },
    )


def _zero_acceleration_loads(system, theta, theta_dot, omega, motor_nm, hinge_nm):
    return _target_loads(system, theta, theta_dot, omega, 0.0, 0.0, motor_nm, hinge_nm)


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

    result = _run(system, 1.0, -0.20, -0.40, 40.0, motor, aero)
    assert result.status == "first_contact_terminal"
    assert result.contact is not None
    assert result.contact.stop == "lower"
    assert observed
    controls = _controls()
    theta_target = -0.20 - 0.40 * float(observed["event_time"])
    scale = controls.angle_atol_rad + controls.rtol * abs(theta_target)
    dense_error = abs(float(observed["theta_dense"]) - theta_target)
    assert dense_error <= scale
    start = float(observed["start"])
    end = float(observed["end"])
    width = end - start
    nodes = [start + width * index / 4.0 for index in range(5)]
    dense = observed["dense"]
    contact_scale = max(1.0, abs(-0.50), *(abs(dense(node)[0]) for node in nodes))
    angle_tolerance = max(8.0 * controls.angle_atol_rad, 2.0 * math.ulp(contact_scale))
    assert abs(float(observed["theta_dense"]) - (-0.50)) <= 4.0 * angle_tolerance
    xi = (float(observed["event_time"]) - start) / width
    root_time = width * (1.0e-14 + 1.0e-14 * abs(xi))
    allowance = (scale + 4.0 * angle_tolerance) / 0.40 + root_time
    assert abs(result.contact.time_s - 0.75) <= allowance
    rate_scale = controls.hinge_velocity_atol_rad_s + controls.rtol * 0.40
    speed_scale = controls.shaft_speed_atol_rad_s + controls.rtol * 40.0
    assert abs(result.contact.preimpact_angular_velocity_rad_s - (-0.40)) <= rate_scale
    assert abs(result.contact.omega_rad_s - 40.0) <= speed_scale
    assert all(sample.time_s <= result.contact.time_s + 1.0e-15 for sample in result.samples)
    _record(
        "C2V-07",
        {
            "primary_evidence_class": "INDEPENDENT_NUMERICAL",
            "purpose": "manufactured first contact",
            "classification": "PASS",
            "metrics": {
                "t_contact_s": result.contact.time_s,
                "T_allow_s": allowance,
                "D_event_rad": dense_error,
                "S_theta_event_rad": scale,
                "angle_tol_contact_rad": angle_tolerance,
            },
            "acceptance_rule": "pre-snap dense gate, production angle tolerance, and T_allow",
            "limitations": "not an all-interval dense-error theorem",
        },
    )


def test_c2v08_fail_closed_layers() -> None:
    layers = {}
    fold = _system(2, _mechanism(lower_stop_rad=-2.0, upper_stop_rad=0.5))

    def fold_aero(time, theta, theta_dot, _omega):
        q_phi, q_theta = _zero_acceleration_loads(fold, -1.20 - time, -1.0, 40.0, 0.04, 0.0)
        return Cmm2AeroEvaluation(
            q_phi, q_theta, 1.0, LOAD_MAPPING_MODEL, AERO_LOAD_QUALIFICATION,
            PROJECTION_MODEL, HINGE_RATE_AERO_MODEL, 2, R_HINGE, theta, theta_dot, "fold",
        )

    with pytest.raises(Cmm2DomainExit):
        _run(fold, 0.5, -1.20, -1.0, 40.0, lambda *_args: MotorEvaluation(0.04), fold_aero)
    layers["fold"] = "Cmm2DomainExit"
    calls = []

    def counting(*_args):
        calls.append(1)
        return MotorEvaluation(0.04)

    with pytest.raises(Cmm2TransientError, match="100 rpm"):
        _run(_system(2), 0.2, -0.3, 0.0, 10.0, counting, counting)
    assert calls == []
    layers["speed"] = "Cmm2TransientError"
    with pytest.raises(Cmm2TransientFailure, match="work budget exhausted"):
        _run(
            _system(2),
            0.2,
            -0.3,
            0.1,
            40.0,
            lambda *_args: MotorEvaluation(0.04),
            lambda _time, theta, theta_dot, _omega: Cmm2AeroEvaluation(
                -0.02, 0.004, 1.0, LOAD_MAPPING_MODEL, AERO_LOAD_QUALIFICATION,
                PROJECTION_MODEL, HINGE_RATE_AERO_MODEL, 2, R_HINGE, theta, theta_dot, "budget",
            ),
            _controls(max_rhs_evaluations=1),
        )
    layers["budget"] = "Cmm2TransientFailure: CMM-2 work budget exhausted."

    def hard(_time, _theta, _rate, _omega):
        raise Cmm2TransientFailure("hard failure")

    with pytest.raises(Cmm2TransientFailure, match="hard failure"):
        _run(
            _system(2),
            0.2,
            -0.3,
            0.1,
            40.0,
            lambda *_args: MotorEvaluation(0.04),
            hard,
        )
    layers["hard"] = "Cmm2TransientFailure: hard failure"
    _record(
        "C2V-08",
        {
            "primary_evidence_class": "REGRESSION_CONTRACT",
            "purpose": "fail-closed boundaries",
            "classification": "PASS",
            "metrics": {"failure_layers": layers},
            "acceptance_rule": "no shortened success artifact",
            "limitations": "not a catalogue of every lower-layer exception",
        },
    )
