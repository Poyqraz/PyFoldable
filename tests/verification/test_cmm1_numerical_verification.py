"""Phase 4 numerical verification for the CMM-1 screening model.

Layers stay separate. This module does not change production code and does not
collapse the evidence into one score.

01 mass / acceleration grid
02 constant equilibrium
03 uniform hinge motion
04 constant shaft acceleration
05 coupled oscillator and conservative energy
06 manufactured forcing
07 independent DOP853 comparison
08 rtol / atol sensitivity
09 forced / dissipative energy-work
10 PY-05 seeded cross-model set
11 PR-07 + real BEM equilibrium
12 deployed BEM exact limit, reused
13 production source-bound ODE convergence
14 embedded BEM annulus sensitivity
15 knot restart / manual split
16 analytic first-contact convergence
17 nonlinear motor algebra
18 numerical boundary classification
19 same-environment reproducibility
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import math
import sys
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
from scipy.integrate import quad, solve_ivp
from scipy.optimize import brentq

from pyfoldable.application.coupled_transient_service import (
    CoupledBindingError,
    CoupledEnvironment,
    FoldableBemShaftEvaluator,
    Pr07MotorEvaluator,
    _parameters as derive_source_parameters,
    assert_cmm1_production_evaluators,
    prepare_coupled_transient,
    run_coupled_transient,
)
from pyfoldable.application.design_draft import DesignDraftInputs, build_design_draft
from pyfoldable.application.mechanism_binding import RadialMassSample, TipMassDistribution
from pyfoldable.core.bem import BEMAnnulusSettings
from pyfoldable.core.bem_rotor import BEMRotorSettings
from pyfoldable.core.models import BladeGeometry, BladeStation
from pyfoldable.core.motor_bem_coupling import (
    AeroLoadSample,
    algebraic_motor_state,
    solve_coupled_operating_point,
)
from pyfoldable.core.polar import PolarFamily, PolarTable
from pyfoldable.core.polar_spanwise import SpanwisePolarAnchor, SpanwisePolarSchedule
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
    prescribed_shaft_hinge_acceleration,
    solve_coupled_transient,
)
from pyfoldable.dynamics.mechanism_contracts import DryFriction
from pyfoldable.dynamics.mechanism_transient import MechanismParameters
from pythrust.propulsion.models import BatterySpec, MotorSpec, SystemSpec


ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "configs/designs/TIP_HINGED_250_CANONICAL.toml"
EVIDENCE: dict[str, object] = {}
INVENTORY = ("motor rotor", "shaft", "hub", "fixed roots")
SOURCE_INVENTORY = ("motor rotor", "shaft", "hub", "fixed blade roots")

_SERVICE_TEST_PATH = (
    Path(__file__).resolve().parents[1] / "application" / "test_coupled_transient_service.py"
)
_service_spec = importlib.util.spec_from_file_location(
    "cmm1_service_contract_tests",
    _SERVICE_TEST_PATH,
)
assert _service_spec is not None and _service_spec.loader is not None
_service_tests = importlib.util.module_from_spec(_service_spec)
sys.modules[_service_spec.name] = _service_tests
_service_spec.loader.exec_module(_service_tests)


@pytest.fixture(scope="session", autouse=True)
def _dump_phase4_evidence():
    yield
    path = Path("/tmp/cmm1_phase4_evidence.json")
    path.write_text(json.dumps(EVIDENCE, indent=2, sort_keys=True, allow_nan=False))


def _record(identifier: str, payload: dict[str, object]) -> None:
    EVIDENCE[identifier] = payload


def _inertia(value: float, source: str = "phase4-i0") -> BaseRotatingAssemblyInertia:
    return BaseRotatingAssemblyInertia(value, source, INVENTORY)


def _controls(**overrides) -> CoupledSolverControls:
    values = dict(
        rtol=1.0e-6,
        angle_atol_rad=1.0e-8,
        hinge_velocity_atol_rad_s=1.0e-8,
        shaft_speed_atol_rad_s=1.0e-6,
        max_step_s=0.001,
        max_duration_s=1.0,
    )
    values.update(overrides)
    return CoupledSolverControls(**values)


def _history(torque, end: float, source: str = "phase4-qh") -> HingeActuationHistory:
    if isinstance(torque, tuple):
        return HingeActuationHistory((0.0, end), torque, source)
    return HingeActuationHistory((0.0, end), (torque, torque), source)


def _motor_torque(torque):
    def evaluate(time_s, theta, theta_dot, omega, law=torque):
        del theta, theta_dot, omega
        value = law(time_s) if callable(law) else law
        return MotorEvaluation(torque_nm=value)

    return evaluate


def _aero_torque(torque: float = 0.0):
    def evaluate(time_s, theta, theta_dot, omega):
        del time_s, theta, theta_dot, omega
        return AeroEvaluation(torque, 0.0, "phase4-analytic", "software_fixture")

    return evaluate


def _parameters(**overrides) -> MechanismParameters:
    values = dict(
        mass_kg=0.02,
        cg_distance_m=0.0,
        hinge_inertia_kg_m2=1.0e-4,
        hinge_radius_m=0.08,
        spring_stiffness_nm_rad=0.0,
        rest_angle_rad=0.0,
        viscous_damping_nm_s_rad=0.0,
        lower_stop_rad=-1.2,
        upper_stop_rad=1.2,
    )
    values.update(overrides)
    return MechanismParameters(**values)


def _system(parameters=None, blade_count: int = 2, inertia=1.0e-3) -> CoupledSystem:
    base = inertia if isinstance(inertia, BaseRotatingAssemblyInertia) else _inertia(inertia)
    return CoupledSystem(parameters or _parameters(), blade_count, base)


def _solve(system, history, theta, theta_dot, omega, motor, aero, controls):
    return solve_coupled_transient(
        CoupledTransientRequest(
            system,
            history,
            theta,
            theta_dot,
            omega,
            motor,
            aero,
            controls,
        )
    )


def _atols(controls: CoupledSolverControls) -> tuple[float, float, float]:
    return (
        controls.angle_atol_rad,
        controls.hinge_velocity_atol_rad_s,
        controls.shaft_speed_atol_rad_s,
    )


def _scales(controls: CoupledSolverControls, reference: tuple[float, float, float]):
    return tuple(
        atol + controls.rtol * abs(value)
        for atol, value in zip(_atols(controls), reference)
    )


def _component_errors(samples, reference, controls: CoupledSolverControls, origin: float = 0.0):
    rows = []
    for sample in samples:
        ref = reference(sample.time_s - origin)
        got = (sample.theta_rad, sample.theta_dot_rad_s, sample.omega_rad_s)
        scale = _scales(controls, ref)
        normalized = tuple(abs(left - right) / width for left, right, width in zip(got, ref, scale))
        absolute = tuple(abs(left - right) for left, right in zip(got, ref))
        rows.append((normalized, absolute, scale))
    endpoint = rows[-1]
    maximum_e = tuple(max(row[0][index] for row in rows) for index in range(3))
    maximum_abs = tuple(max(row[1][index] for row in rows) for index in range(3))
    weight_sum = 0.0
    weighted = [0.0, 0.0, 0.0]
    previous_time = samples[0].time_s
    previous_error = rows[0][0]
    for sample, row in zip(samples[1:], rows[1:]):
        width = sample.time_s - previous_time
        if width > 0.0:
            for index in range(3):
                weighted[index] += 0.5 * (previous_error[index] ** 2 + row[0][index] ** 2) * width
            weight_sum += width
        previous_time = sample.time_s
        previous_error = row[0]
    if weight_sum == 0.0:
        rms = endpoint[0]
    else:
        rms = tuple(math.sqrt(value / weight_sum) for value in weighted)
    return {
        "endpoint_e": endpoint[0],
        "max_e": maximum_e,
        "rms_e": rms,
        "endpoint_abs": endpoint[1],
        "max_abs": maximum_abs,
        "samples": len(samples),
    }


def _accept_normalized(report: dict[str, object]) -> None:
    for key in ("endpoint_e", "max_e"):
        values = report[key]
        assert max(values) <= 1.0, (key, values)


def _screening(result) -> None:
    assert result.model_class == MODEL_CLASS
    assert result.physical_qualification is False
    assert result.full_propeller_clearance is None
    assert result.surface_path_clearance is None
    assert result.interblade_clearance is None
    assert result.aerodynamic_hinge_torque_status == AERO_HINGE_STATUS
    assert any("PR-06C" in item for item in result.limitations)
    assert all(
        sample.aerodynamic_hinge_torque_status == AERO_HINGE_STATUS for sample in result.samples
    )


def _orders(errors: list[float], floor: float) -> dict[str, object]:
    observed = []
    resolvable = []
    for coarse, fine in zip(errors, errors[1:]):
        if min(coarse, fine) <= floor:
            observed.append(None)
            resolvable.append(False)
            continue
        observed.append(math.log2(coarse / fine))
        resolvable.append(True)
    return {"p": observed, "resolvable": resolvable, "floor": floor}


def _require_order_or_roundoff(errors: list[float], floor: float) -> str:
    assert len(errors) >= 3
    summary = _orders(errors, floor)
    successive = [
        value
        for value, flag in zip(summary["p"], summary["resolvable"])
        if flag
    ]
    if len(successive) >= 2 and all(value >= 2.0 for value in successive):
        return "resolved_order"
    if min(errors) <= floor:
        return "order_unresolvable_at_roundoff"
    raise AssertionError({"errors": errors, "orders": summary})


def _tip_blocks(parameters: MechanismParameters, theta: float):
    coupling = parameters.mass_kg * parameters.hinge_radius_m * parameters.cg_distance_m
    cosine = math.cos(theta)
    inertia = parameters.hinge_inertia_kg_m2
    radial = parameters.mass_kg * parameters.hinge_radius_m ** 2
    one_a = inertia + radial + 2.0 * coupling * cosine
    one_b = inertia + coupling * cosine
    return coupling, one_a, one_b


def _independent_matrix(system: CoupledSystem, theta: float):
    coupling, one_a, one_b = _tip_blocks(system.parameters, theta)
    count = system.blade_count
    inertia = system.parameters.hinge_inertia_kg_m2
    return (
        system.base_inertia.inertia_kg_m2 + count * one_a,
        count * one_b,
        count * inertia,
        coupling,
    )


def _independent_rhs(system, theta, theta_dot, omega, motor_torque, aero_torque, hinge_torque):
    parameters = system.parameters
    coupling, _one_a, _one_b = _tip_blocks(parameters, theta)
    spring = -parameters.spring_stiffness_nm_rad * (theta - parameters.rest_angle_rad)
    damping = -parameters.viscous_damping_nm_s_rad * theta_dot
    friction = parameters.dry_friction
    if friction.mode == "none":
        friction_nm = 0.0
    else:
        friction_nm = -friction.coulomb_torque_nm * math.tanh(
            theta_dot / friction.transition_velocity_rad_s
        )
    centrifugal = -coupling * omega ** 2 * math.sin(theta)
    shaft_gyro = (
        system.blade_count
        * coupling
        * math.sin(theta)
        * (2.0 * omega * theta_dot + theta_dot ** 2)
    )
    rhs_hinge = system.blade_count * (
        hinge_torque + spring + damping + friction_nm + centrifugal
    )
    rhs_shaft = motor_torque - aero_torque + shaft_gyro
    return rhs_shaft, rhs_hinge


def _decimal_solve(m00, m01, m11, rhs0, rhs1):
    with localcontext() as ctx:
        ctx.prec = 80
        a = Decimal.from_float(m00)
        b = Decimal.from_float(m01)
        c = Decimal.from_float(m11)
        r0 = Decimal.from_float(rhs0)
        r1 = Decimal.from_float(rhs1)
        det = a * c - b * b
        omega_dot = (r0 * c - b * r1) / det
        theta_ddot = (a * r1 - b * r0) / det
        return float(omega_dot), float(theta_ddot)


def _row_eta(residual: float, rhs: float, products: tuple[float, ...]) -> float:
    magnitude = abs(rhs) + math.fsum(abs(product) for product in products)
    if magnitude == 0.0:
        if residual != 0.0:
            raise AssertionError("zero-denominator residual is nonzero")
        return 0.0
    return abs(residual) / magnitude


def _policy_limit(magnitude: float) -> float:
    if magnitude == 0.0:
        return 0.0
    roundoff = coupled_transient._RESIDUAL_ROUND_ULPS * math.ulp(magnitude) / magnitude
    return max(coupled_transient._RESIDUAL_REL, roundoff)


def _mechanical_energy_formula(system: CoupledSystem, theta: float, theta_dot: float, omega: float) -> float:
    _coupling, one_a, one_b = _tip_blocks(system.parameters, theta)
    count = system.blade_count
    kinetic = (
        0.5 * (system.base_inertia.inertia_kg_m2 + count * one_a) * omega ** 2
        + count * one_b * omega * theta_dot
        + 0.5 * count * system.parameters.hinge_inertia_kg_m2 * theta_dot ** 2
    )
    spring = 0.5 * count * system.parameters.spring_stiffness_nm_rad * (
        theta - system.parameters.rest_angle_rad
    ) ** 2
    return kinetic + spring


def _kl_constants(system: CoupledSystem) -> tuple[float, float, float]:
    parameters = system.parameters
    assert parameters.cg_distance_m == 0.0
    count = system.blade_count
    k_inertia = system.base_inertia.inertia_kg_m2 + count * (
        parameters.hinge_inertia_kg_m2 + parameters.mass_kg * parameters.hinge_radius_m ** 2
    )
    l_inertia = count * parameters.hinge_inertia_kg_m2
    reduced = l_inertia - (l_inertia ** 2) / k_inertia
    return k_inertia, l_inertia, reduced


def _broad_family(cl: float, airfoil: str, source: str) -> PolarFamily:
    return PolarFamily(
        tuple(
            PolarTable(
                airfoil_id=airfoil,
                scenario_id="cmm1-phase4",
                reynolds=reynolds,
                mach=mach,
                alpha_rad=(-0.5 * math.pi, 0.5 * math.pi),
                cl=(cl, cl),
                cd=(0.02, 0.02),
                cm=(0.0, 0.0),
                source=source,
            )
            for mach in (0.0, 0.5)
            for reynolds in (1.0e3, 1.0e7)
        )
    )


def _source_context():
    draft = build_design_draft(
        CANONICAL,
        DesignDraftInputs(
            diameter="220 mm",
            hub_radius="16 mm",
            hinge_radius="85 mm",
            blade_count=2,
            airfoil_id="NACA0012",
            chord_scale=1.0,
            twist_scale=1.0,
            preview_fold_angle="-40 deg",
            angular_speed="1200 rpm",
            forward_speed="1 m/s",
            air_density="1.225 kg/m^3",
            dynamic_viscosity="1.81e-5 Pa*s",
            temperature="15 degC",
            pressure="101325 Pa",
        ),
    )
    family = _broad_family(0.4, "NACA0012", "cmm1-phase4-broad")
    schedule = SpanwisePolarSchedule(
        "cmm1-phase4-span",
        (SpanwisePolarAnchor(0.2, family), SpanwisePolarAnchor(1.0, family)),
    )
    return {
        "draft": draft,
        "distribution": TipMassDistribution(
            (RadialMassSample(0.02, 0.02, "synthetic tip", intrinsic_inertia=5.0e-4),),
            "synthetic-tip",
            "synthetic_test_fixture",
        ),
        "base_inertia": BaseRotatingAssemblyInertia(2.0e-3, "phase4 fixture inertia", SOURCE_INVENTORY),
        "motor": MotorSpec(1000.0, 0.05, 0.4, 40.0),
        "battery": BatterySpec(12.0, 0.98),
        "system": SystemSpec(0.01),
        "throttle": 0.25,
        "environment": CoupledEnvironment("phase4", 1.0, 1.225, 1.81e-5, 288.15, 101325.0),
        "polars": schedule,
        "theta": -0.45,
        "omega": 140.0,
        "spring": 0.02,
        "duration": 0.02,
    }


def _source_binding(context, *, annulus_count: int, controls: CoupledSolverControls, duration: float | None = None):
    horizon = context["duration"] if duration is None else duration
    settings = BEMRotorSettings(
        annulus_count=annulus_count,
        annulus_settings=BEMAnnulusSettings(bracket_samples=16, loading_branch="positive_only"),
    )
    return prepare_coupled_transient(
        draft=context["draft"],
        distribution=context["distribution"],
        base_inertia=context["base_inertia"],
        spring_stiffness_nm_rad=context["spring"],
        rest_angle_rad=context["theta"],
        viscous_damping_nm_s_rad=0.0,
        initial_angle_rad=context["theta"],
        initial_angular_velocity_rad_s=0.0,
        initial_omega_rad_s=context["omega"],
        actuation=HingeActuationHistory((0.0, horizon), (0.0, 0.0), "phase4-hold"),
        motor=context["motor"],
        battery=context["battery"],
        system=context["system"],
        throttle=context["throttle"],
        environment=context["environment"],
        polars=context["polars"],
        bem_settings=settings,
        bounds="error",
        mechanical_source="phase4 synthetic fixture",
        controls=controls,
    )


def _source_rhs_factory(context, annulus_count: int, duration: float):
    design, parameters = derive_source_parameters(
        context["draft"],
        context["distribution"],
        context["theta"],
        context["spring"],
        context["theta"],
        0.0,
        DryFriction(),
    )
    settings = BEMRotorSettings(
        annulus_count=annulus_count,
        annulus_settings=BEMAnnulusSettings(bracket_samples=16, loading_branch="positive_only"),
    )

    def make_rhs():
        motor = Pr07MotorEvaluator(
            context["motor"], context["battery"], context["system"], context["throttle"]
        )
        aero = FoldableBemShaftEvaluator(
            design.blade,
            context["polars"],
            settings,
            context["environment"],
            parameters.hinge_radius_m,
            "error",
        )
        system = CoupledSystem(parameters, design.blade.blade_count, context["base_inertia"])

        def rhs(time_s, state):
            theta, theta_dot, omega = (float(state[0]), float(state[1]), float(state[2]))
            if abs(theta) >= FOLD_LIMIT_RAD or omega < OMEGA_MIN:
                raise CoupledDomainExit("reference left the CMM-1 domain")
            motor_sample = motor(time_s, theta, theta_dot, omega)
            aero_sample = aero(time_s, theta, theta_dot, omega)
            solved = coupled_accelerations(
                system,
                theta,
                theta_dot,
                omega,
                motor_sample.torque_nm,
                aero_sample.shaft_torque_nm,
                0.0,
            )
            return (theta_dot, solved.theta_ddot_rad_s2, solved.omega_dot_rad_s2)

        return rhs

    return make_rhs


def _dop853(rhs, y0, duration: float, rtol: float, atol: float):
    solution = solve_ivp(
        rhs,
        (0.0, duration),
        y0,
        method="DOP853",
        rtol=rtol,
        atol=atol,
        dense_output=True,
    )
    assert solution.success, solution.message
    return solution


def _reference_change(first, second, times, controls: CoupledSolverControls) -> tuple[float, float, float]:
    changes = [0.0, 0.0, 0.0]
    for time in times:
        left = first.sol(time)
        right = second.sol(time)
        reference = (float(right[0]), float(right[1]), float(right[2]))
        scale = _scales(controls, reference)
        for index in range(3):
            changes[index] = max(changes[index], abs(float(left[index]) - reference[index]) / scale[index])
    return tuple(changes)


def _errors_against_dense(samples, dense, controls: CoupledSolverControls):
    def reference(time_s: float):
        values = dense.sol(time_s)
        return (float(values[0]), float(values[1]), float(values[2]))

    return _component_errors(samples, reference, controls)


def test_01_mass_acceleration_grid() -> None:
    """Layer 1. Represented matrix, independent 2x2 solve, backward error."""
    rows = []
    ordinary = _parameters(
        mass_kg=0.02,
        cg_distance_m=0.01,
        hinge_inertia_kg_m2=1.0e-4,
        spring_stiffness_nm_rad=0.01,
        viscous_damping_nm_s_rad=0.001,
    )
    for blade_count in (1, 2, 4):
        for theta in (-1.0, -0.25, 0.35, 1.1):
            for inertia in (1.0e-3, 1.0e-2, 1.0e-8):
                system = _system(ordinary, blade_count, inertia)
                rows.append(("ordinary", system, theta, True))
    point = _parameters(
        mass_kg=0.02,
        cg_distance_m=0.01,
        hinge_inertia_kg_m2=0.02 * 0.01 ** 2,
        spring_stiffness_nm_rad=0.0,
        viscous_damping_nm_s_rad=0.0,
    )
    for inertia in (1.0e-3, 1.0e-8):
        for theta in (-0.4, 0.0, 0.4):
            rows.append(("point-mass", _system(point, 2, inertia), theta, inertia == 1.0e-8 and theta == 0.0 or inertia == 1.0e-3))

    measured = []
    for kind, system, theta, required in rows:
        try:
            produced = coupled_mass_matrix(system, theta)
        except CoupledTransientFailure as exc:
            assert not required, (kind, theta, system.base_inertia.inertia_kg_m2, str(exc))
            assert "unresolved" in str(exc)
            continue
        independent = _independent_matrix(system, theta)
        assert produced.m00 == pytest.approx(independent[0], rel=0.0, abs=0.0)
        assert produced.m01 == pytest.approx(independent[1], rel=0.0, abs=0.0)
        assert produced.m11 == pytest.approx(independent[2], rel=0.0, abs=0.0)
        assert produced.c_kg_m2 == pytest.approx(independent[3], rel=0.0, abs=0.0)
        rhs = _independent_rhs(system, theta, 0.15, 25.0, 0.004, 0.001, 0.0003)
        direct = _decimal_solve(produced.m00, produced.m01, produced.m11, rhs[0], rhs[1])
        solved = coupled_accelerations(
            system, theta, 0.15, 25.0, 0.004, 0.001, 0.0003
        )
        residual_shaft = produced.m00 * solved.omega_dot_rad_s2 + produced.m01 * solved.theta_ddot_rad_s2 - rhs[0]
        residual_hinge = produced.m01 * solved.omega_dot_rad_s2 + produced.m11 * solved.theta_ddot_rad_s2 - rhs[1]
        eta_shaft = _row_eta(
            residual_shaft,
            rhs[0],
            (produced.m00 * solved.omega_dot_rad_s2, produced.m01 * solved.theta_ddot_rad_s2),
        )
        eta_hinge = _row_eta(
            residual_hinge,
            rhs[1],
            (produced.m01 * solved.omega_dot_rad_s2, produced.m11 * solved.theta_ddot_rad_s2),
        )
        shaft_magnitude = abs(rhs[0]) + abs(produced.m00 * solved.omega_dot_rad_s2) + abs(produced.m01 * solved.theta_ddot_rad_s2)
        hinge_magnitude = abs(rhs[1]) + abs(produced.m01 * solved.omega_dot_rad_s2) + abs(produced.m11 * solved.theta_ddot_rad_s2)
        assert eta_shaft <= _policy_limit(shaft_magnitude)
        assert eta_hinge <= _policy_limit(hinge_magnitude)
        forward = max(
            abs(solved.omega_dot_rad_s2 - direct[0]),
            abs(solved.theta_ddot_rad_s2 - direct[1]),
        )
        if produced.represented_pivot >= 1.0e-4:
            scale = max(1.0, abs(direct[0]), abs(direct[1]))
            assert forward <= 1.0e-8 * scale
        measured.append(
            {
                "kind": kind,
                "theta": theta,
                "i0": system.base_inertia.inertia_kg_m2,
                "n": system.blade_count,
                "pivot": produced.represented_pivot,
                "eta_shaft": eta_shaft,
                "eta_hinge": eta_hinge,
                "forward_gap": forward,
            }
        )

    zero_system = _system(_parameters(), 2, 1.0e-3)
    zero = coupled_accelerations(zero_system, 0.0, 0.0, 30.0, 0.0, 0.0, 0.0)
    assert zero.omega_dot_rad_s2 == 0.0 or abs(zero.omega_dot_rad_s2) <= 1.0e-12
    assert coupled_transient._row_backward_error(0.0, 0.0, (0.0, 0.0)) == 0.0
    with pytest.raises(CoupledTransientFailure, match="backward-error"):
        coupled_transient._row_backward_error(1.0e-18, 0.0, (0.0,))
    unresolved = _system(point, 2, 1.0e-20)
    with pytest.raises(CoupledTransientFailure, match="unresolved") as failure:
        coupled_mass_matrix(unresolved, 0.0)
    assert failure.value is not None
    with pytest.raises(CoupledTransientFailure, match="unresolved"):
        coupled_accelerations(unresolved, 0.0, 0.0, OMEGA_MIN, 1.0e-12, 0.0, 0.0)

    point_small = next(
        row for row in measured if row["kind"] == "point-mass" and row["i0"] == 1.0e-8 and row["theta"] == 0.0
    )
    _record(
        "01",
        {
            "reference": "cross-model",
            "fixture": "represented-mass-grid",
            "resolved_cases": len(measured),
            "max_eta": max(max(row["eta_shaft"], row["eta_hinge"]) for row in measured),
            "min_pivot": min(row["pivot"] for row in measured),
            "max_forward_gap": max(row["forward_gap"] for row in measured),
            "point_mass_i0_1e-8": point_small,
            "unresolved_i0": 1.0e-20,
            "threshold": "production row backward-error policy",
            "threshold_basis": "mathematical",
            "result": "PASS",
        },
    )


def test_02_constant_equilibrium() -> None:
    """Layer 2. Case A exact equilibrium, force balance, and constant energy."""
    parameters = _parameters(
        cg_distance_m=0.01,
        spring_stiffness_nm_rad=0.015,
        rest_angle_rad=-0.05,
        dry_friction=DryFriction("regularized_coulomb", 0.002, 0.05, source="case-a"),
    )
    system = _system(parameters, 2, 1.0e-3)
    theta0 = -0.2
    omega0 = 28.0
    coupling = parameters.mass_kg * parameters.hinge_radius_m * parameters.cg_distance_m
    qh = parameters.spring_stiffness_nm_rad * (theta0 - parameters.rest_angle_rad)
    qh += coupling * omega0 ** 2 * math.sin(theta0)
    controls = _controls(max_step_s=0.0005)
    result = _solve(
        system,
        _history(qh, 0.04, "case-a"),
        theta0,
        0.0,
        omega0,
        _motor_torque(0.0),
        _aero_torque(0.0),
        controls,
    )
    _screening(result)
    assert result.status == "completed"

    def reference(_time):
        return (theta0, 0.0, omega0)

    report = _component_errors(result.samples, reference, controls)
    _accept_normalized(report)
    initial = result.samples[0]
    assert initial.theta_ddot_rad_s2 == pytest.approx(0.0, abs=1.0e-9)
    assert initial.omega_dot_rad_s2 == pytest.approx(0.0, abs=1.0e-9)
    assert initial.dry_friction_torque_nm == pytest.approx(0.0, abs=0.0)
    energy0 = _mechanical_energy_formula(system, theta0, 0.0, omega0)
    assert energy0 > 1.0e-3
    drift = max(abs(sample.mechanical_energy_j - energy0) for sample in result.samples) / energy0
    assert drift <= controls.rtol
    _record(
        "02",
        {
            "reference": "analytic",
            "fixture": "case-a-equilibrium",
            "controls": {"rtol": controls.rtol, "max_step_s": controls.max_step_s},
            "errors": report,
            "energy_drift_normalized": drift,
            "threshold": 1.0,
            "threshold_basis": "numerical-policy",
            "result": "PASS",
        },
    )


def test_03_uniform_hinge_motion() -> None:
    """Layer 2. Case B exact uniform hinge motion without contact."""
    system = _system(_parameters(), 2, 1.0e-3)
    theta0 = 0.12
    velocity = 0.35
    omega0 = 24.0
    controls = _controls(max_step_s=0.0005)
    result = _solve(
        system,
        _history(0.0, 0.05, "case-b"),
        theta0,
        velocity,
        omega0,
        _motor_torque(0.0),
        _aero_torque(0.0),
        controls,
    )
    _screening(result)

    def reference(time_s):
        return (theta0 + velocity * time_s, velocity, omega0)

    report = _component_errors(result.samples, reference, controls)
    _accept_normalized(report)
    assert result.status == "completed"
    assert result.contact is None
    _record(
        "03",
        {
            "reference": "analytic",
            "fixture": "case-b-uniform",
            "errors": report,
            "threshold": 1.0,
            "threshold_basis": "numerical-policy",
            "result": "PASS",
        },
    )


def test_04_constant_shaft_acceleration() -> None:
    """Layer 2. Case C exact constant shaft acceleration with C > 0."""
    parameters = _parameters(cg_distance_m=0.01)
    system = _system(parameters, 2, 2.0e-3)
    mass = coupled_mass_matrix(system, 0.0)
    alpha = 4.0
    qh = mass.b_kg_m2 * alpha
    qm = mass.m00 * alpha
    omega0 = 22.0
    controls = _controls(max_step_s=0.0005)
    result = _solve(
        system,
        _history(qh, 0.03, "case-c"),
        0.0,
        0.0,
        omega0,
        _motor_torque(qm),
        _aero_torque(0.0),
        controls,
    )
    _screening(result)

    def reference(time_s):
        return (0.0, 0.0, omega0 + alpha * time_s)

    report = _component_errors(result.samples, reference, controls)
    _accept_normalized(report)
    assert result.samples[0].omega_dot_rad_s2 == pytest.approx(alpha, rel=1.0e-12, abs=1.0e-12)
    assert result.samples[0].theta_ddot_rad_s2 == pytest.approx(0.0, abs=1.0e-10)
    _record(
        "04",
        {
            "reference": "analytic",
            "fixture": "case-c-shaft-acceleration",
            "alpha": alpha,
            "errors": report,
            "threshold": 1.0,
            "threshold_basis": "numerical-policy",
            "result": "PASS",
        },
    )


def _case_d():
    parameters = _parameters(spring_stiffness_nm_rad=0.8)
    system = _system(parameters, 2, 1.0e-3)
    k_inertia, l_inertia, reduced = _kl_constants(system)
    frequency = math.sqrt(system.blade_count * parameters.spring_stiffness_nm_rad / reduced)
    theta0 = 0.04
    velocity0 = 0.5
    omega0 = 40.0

    def reference(time_s: float):
        angle = theta0 * math.cos(frequency * time_s) + (velocity0 / frequency) * math.sin(frequency * time_s)
        rate = -theta0 * frequency * math.sin(frequency * time_s) + velocity0 * math.cos(frequency * time_s)
        speed = omega0 - (l_inertia / k_inertia) * (rate - velocity0)
        return (angle, rate, speed)

    return system, reference, frequency, theta0, velocity0, omega0


def test_05_coupled_oscillator_and_conservative_energy() -> None:
    """Layer 2. Case D primary RK45 refinement and conservative energy."""
    system, reference, frequency, theta0, velocity0, omega0 = _case_d()
    assert abs(reference(0.0)[0]) < 0.5 * math.pi
    levels = []
    for step in (0.002, 0.001, 0.0005):
        controls = _controls(
            rtol=1.0e-3,
            angle_atol_rad=1.0e-4,
            hinge_velocity_atol_rad_s=1.0e-3,
            shaft_speed_atol_rad_s=1.0e-2,
            max_step_s=step,
        )
        result = _solve(
            system,
            _history(0.0, 0.05, "case-d"),
            theta0,
            velocity0,
            omega0,
            _motor_torque(0.0),
            _aero_torque(0.0),
            controls,
        )
        _screening(result)
        assert result.status == "completed"
        assert result.contact is None
        report = _component_errors(result.samples, reference, controls)
        energy0 = _mechanical_energy_formula(system, *reference(0.0))
        assert energy0 > 1.0e-3
        drift = max(abs(sample.mechanical_energy_j - energy0) for sample in result.samples) / energy0
        levels.append(
            {
                "max_step_s": step,
                "samples": len(result.samples),
                "rhs": result.rhs_evaluations,
                "errors": report,
                "energy_drift_normalized": drift,
            }
        )
    final = levels[-1]
    _accept_normalized(final["errors"])
    order_rows = {}
    disposition = {}
    for index, name in enumerate(("theta", "theta_dot", "omega")):
        errors = [level["errors"]["max_abs"][index] for level in levels]
        floor = 256.0 * math.ulp(max(1.0, abs(reference(0.0)[index]), abs(reference(0.02)[index])))
        disposition[name] = _require_order_or_roundoff(errors, floor)
        order_rows[name] = _orders(errors, floor)
        order_rows[name]["abs"] = errors
    drifts = [level["energy_drift_normalized"] for level in levels]
    energy_floor = 256.0 * math.ulp(1.0)
    if min(drifts) > energy_floor:
        assert drifts[1] < drifts[0]
        assert drifts[2] < drifts[1]
    _record(
        "05",
        {
            "reference": "analytic",
            "fixture": "case-d-oscillator",
            "frequency_rad_s": frequency,
            "levels": levels,
            "orders": order_rows,
            "order_disposition": disposition,
            "threshold": 1.0,
            "threshold_basis": "numerical-policy",
            "result": "PASS",
        },
    )


def test_06_manufactured_forcing() -> None:
    """Layer 2. Manufactured quadratic trajectory through pure-dynamics injection."""
    parameters = _parameters(viscous_damping_nm_s_rad=0.002)
    system = _system(parameters, 2, 1.2e-3)
    k_inertia, l_inertia, _reduced = _kl_constants(system)
    theta0, velocity0, acceleration = 0.05, 0.15, -0.4
    omega0, alpha, jerk = 26.0, 1.5, -2.0
    duration = 0.05
    inertia = parameters.hinge_inertia_kg_m2
    damping = parameters.viscous_damping_nm_s_rad

    def qh(time_s: float) -> float:
        return inertia * (alpha + jerk * time_s + acceleration) + damping * (velocity0 + acceleration * time_s)

    def shaft(time_s: float) -> float:
        return k_inertia * (alpha + jerk * time_s) + l_inertia * acceleration

    history = HingeActuationHistory((0.0, duration), (qh(0.0), qh(duration)), "manufactured")
    assert history.torque_nm[1] != history.torque_nm[0]
    controls = _controls(max_step_s=0.0005)
    result = _solve(
        system,
        history,
        theta0,
        velocity0,
        omega0,
        _motor_torque(shaft),
        _aero_torque(0.0),
        controls,
    )
    _screening(result)

    def reference(time_s: float):
        return (
            theta0 + velocity0 * time_s + 0.5 * acceleration * time_s ** 2,
            velocity0 + acceleration * time_s,
            omega0 + alpha * time_s + 0.5 * jerk * time_s ** 2,
        )

    report = _component_errors(result.samples, reference, controls)
    _accept_normalized(report)
    midpoint = next(sample for sample in result.samples if sample.time_s > 0.0)
    expected = qh(midpoint.time_s)
    assert midpoint.hinge_actuation_nm == pytest.approx(expected, rel=0.0, abs=8.0 * math.ulp(max(1.0, abs(expected))))
    assert "aero_evaluator" not in inspect.signature(run_coupled_transient).parameters
    with pytest.raises(CoupledBindingError, match="PR-07"):
        assert_cmm1_production_evaluators(_motor_torque(shaft), _aero_torque(0.0))
    _record(
        "06",
        {
            "reference": "manufactured",
            "fixture": "quadratic-affine-forcing",
            "errors": report,
            "floating_point_floor": max(report["max_abs"]) <= 1.0e-12,
            "synthetic_evaluators_rejected": True,
            "threshold": 1.0,
            "threshold_basis": "numerical-policy",
            "result": "PASS",
        },
    )


def test_07_independent_dop853() -> None:
    """Layer 3. DOP853 integrates the same declared nonlinear contact-free RHS."""
    parameters = _parameters(
        mass_kg=0.025,
        cg_distance_m=0.015,
        hinge_inertia_kg_m2=2.0e-4,
        hinge_radius_m=0.07,
        spring_stiffness_nm_rad=0.025,
        rest_angle_rad=-0.1,
        lower_stop_rad=-1.2,
        upper_stop_rad=1.0,
    )
    system = _system(parameters, 2, 1.5e-3)
    theta0, velocity0, omega0 = -0.3, 0.45, 32.0
    duration = 0.04
    controls = _controls(max_step_s=0.001)

    def rhs(_time, state):
        solved = coupled_accelerations(
            system,
            float(state[0]),
            float(state[1]),
            float(state[2]),
            0.0,
            0.0,
            0.0,
        )
        return (float(state[1]), solved.theta_ddot_rad_s2, solved.omega_dot_rad_s2)

    y0 = (theta0, velocity0, omega0)
    loose = _dop853(rhs, y0, duration, 1.0e-8, 1.0e-10)
    tight = _dop853(rhs, y0, duration, 1.0e-10, 1.0e-12)
    result = _solve(
        system,
        _history(0.0, duration, "dop853"),
        theta0,
        velocity0,
        omega0,
        _motor_torque(0.0),
        _aero_torque(0.0),
        controls,
    )
    _screening(result)
    assert result.status == "completed"
    times = [sample.time_s for sample in result.samples]
    change = _reference_change(loose, tight, times, controls)
    assert max(change) <= 0.1
    report = _errors_against_dense(result.samples, tight, controls)
    _accept_normalized(report)
    _record(
        "07",
        {
            "reference": "independent solver",
            "fixture": "nonlinear-contact-free",
            "dop853_rtol": [1.0e-8, 1.0e-10],
            "reference_change_e": change,
            "errors": report,
            "threshold": 1.0,
            "reference_stability": 0.1,
            "threshold_basis": "numerical-policy",
            "result": "PASS",
        },
    )


def _sensitivity_run(rtol: float, atols: tuple[float, float, float], step: float):
    system, reference, _frequency, theta0, velocity0, omega0 = _case_d()
    controls = _controls(
        rtol=rtol,
        angle_atol_rad=atols[0],
        hinge_velocity_atol_rad_s=atols[1],
        shaft_speed_atol_rad_s=atols[2],
        max_step_s=step,
    )
    result = _solve(
        system,
        _history(0.0, 0.04, "sensitivity"),
        theta0,
        velocity0,
        omega0,
        _motor_torque(0.0),
        _aero_torque(0.0),
        controls,
    )
    return {
        "rtol": rtol,
        "atols": atols,
        "max_step_s": step,
        "samples": len(result.samples),
        "rhs": result.rhs_evaluations,
        "max_e": _component_errors(result.samples, reference, controls)["max_e"],
    }


def test_08_rtol_atol_sensitivity() -> None:
    """Layer 6. Case D tolerance sweeps. Step counts decide whether a claim is real."""
    small = (1.0e-8, 1.0e-8, 1.0e-6)
    rtol_rows = [_sensitivity_run(rtol, small, 0.002) for rtol in (1.0e-3, 1.0e-4, 1.0e-5)]
    atol_rows = [
        _sensitivity_run(1.0e-4, atols, 0.002)
        for atols in (
            (1.0e-5, 1.0e-5, 1.0e-4),
            (1.0e-6, 1.0e-6, 1.0e-5),
            (1.0e-7, 1.0e-7, 1.0e-6),
        )
    ]
    rtol_steps = [row["samples"] for row in rtol_rows]
    atol_steps = [row["samples"] for row in atol_rows]
    assert rtol_steps[1] >= rtol_steps[0]
    assert rtol_steps[2] >= rtol_steps[1]
    assert atol_steps[1] >= atol_steps[0]
    assert atol_steps[2] >= atol_steps[1]
    interpretation = {
        "rtol_max_step_dominates": len(set(rtol_steps)) == 1,
        "atol_max_step_dominates": len(set(atol_steps)) == 1,
        "note": (
            "Accepted step counts do not change, so tolerance sensitivity is not claimed. "
            "Normalized errors can exceed 1 when a tighter rtol or atol shrinks the scale "
            "while max_step still sets the trajectory. Case D acceptance is the step-limited run."
        ),
    }
    _record(
        "08",
        {
            "reference": "characterization",
            "fixture": "case-d-oscillator",
            "rtol_sweep": rtol_rows,
            "atol_sweep": atol_rows,
            "interpretation": interpretation,
            "threshold_basis": "empirical-regression",
            "result": "PASS",
        },
    )


def test_09_forced_dissipative_energy_work() -> None:
    """Layer 2/3. Independent quadrature is the work oracle."""
    friction = DryFriction("regularized_coulomb", 0.0004, 0.25, source="forced")
    parameters = _parameters(viscous_damping_nm_s_rad=0.0015, dry_friction=friction)
    system = _system(parameters, 2, 1.2e-3)
    duration = 0.04
    theta0, velocity0, omega0 = 0.05, 0.2, 30.0

    def qh(time_s: float) -> float:
        return 0.0002 + 0.001 * time_s

    def shaft(time_s: float) -> float:
        return 0.0003 + 0.002 * time_s

    def rhs(_time, state):
        solved = coupled_accelerations(
            system,
            float(state[0]),
            float(state[1]),
            float(state[2]),
            shaft(float(_time)),
            0.0,
            qh(float(_time)),
        )
        return (float(state[1]), solved.theta_ddot_rad_s2, solved.omega_dot_rad_s2)

    y0 = (theta0, velocity0, omega0)
    loose = _dop853(rhs, y0, duration, 1.0e-8, 1.0e-10)
    tight = _dop853(rhs, y0, duration, 1.0e-10, 1.0e-12)
    controls = _controls(max_step_s=0.0005)
    change = _reference_change(loose, tight, [0.0, 0.5 * duration, duration], controls)
    assert max(change) <= 0.1

    def power(time_s: float) -> float:
        state = tight.sol(float(time_s))
        rate = float(state[1])
        speed = float(state[2])
        count = system.blade_count
        return (
            shaft(float(time_s)) * speed
            + count * qh(float(time_s)) * rate
            - count * parameters.viscous_damping_nm_s_rad * rate ** 2
            - count * friction.coulomb_torque_nm * rate * math.tanh(rate / friction.transition_velocity_rad_s)
        )

    integral, estimate = quad(power, 0.0, duration, epsabs=1.0e-12, limit=400)
    result = _solve(
        system,
        HingeActuationHistory((0.0, duration), (qh(0.0), qh(duration)), "forced"),
        theta0,
        velocity0,
        omega0,
        _motor_torque(shaft),
        _aero_torque(0.0),
        controls,
    )
    _screening(result)
    assert result.status == "completed"
    energy0 = _mechanical_energy_formula(system, theta0, velocity0, omega0)
    assert energy0 > 1.0e-3
    delta = result.samples[-1].mechanical_energy_j - result.samples[0].mechanical_energy_j
    balance = abs(delta - integral) / energy0
    trapezoid = abs(result.samples[-1].cumulative_work_j - integral) / energy0
    assert balance <= controls.rtol
    _record(
        "09",
        {
            "reference": "independent solver",
            "fixture": "forced-dissipative",
            "reference_change_e": change,
            "quadrature_error": estimate,
            "energy_scale": energy0,
            "balance_error_normalized": balance,
            "trapezoid_diagnostic_normalized": trapezoid,
            "threshold": controls.rtol,
            "threshold_basis": "numerical-policy",
            "result": "PASS",
        },
    )


# Frozen interior states. Values are explicit so the set does not depend on a generator.
_PY05_CASES = (
    (1, 0.012, 0.004, 1.0e-4, 0.07, 6.0e-4, -0.55, 22.0, 0.25, 1.2, 0.008, -0.1, 0.0, 0.0004, 0.0),
    (1, 0.018, 0.0, 8.0e-5, 0.09, 1.2e-3, 0.15, 40.0, -0.35, -0.8, 0.0, 0.0, 0.001, 0.0, 0.0),
    (2, 0.02, 0.01, 1.5e-4, 0.08, 9.0e-4, -0.3, 33.0, 0.6, 2.5, 0.012, -0.05, 0.0, -0.0003, 0.0),
    (2, 0.025, 0.006, 2.0e-4, 0.065, 2.5e-3, 0.45, 18.0, -0.9, -1.5, 0.004, 0.1, 0.0008, 0.0007, 0.0),
    (4, 0.01, 0.008, 1.1e-4, 0.075, 7.0e-4, -0.8, 55.0, 0.15, 0.4, 0.02, -0.2, 0.0, 0.0002, 0.0),
    (4, 0.016, 0.003, 9.0e-5, 0.055, 1.5e-3, 0.25, 27.0, -0.2, 3.2, 0.0, 0.0, 0.0005, -0.0004, 0.0),
    (1, 0.03, 0.012, 2.2e-4, 0.1, 3.0e-3, -0.15, 16.0, 1.1, -2.2, 0.006, 0.0, 0.0, 0.001, 0.0015),
    (2, 0.014, 0.007, 1.3e-4, 0.085, 1.1e-3, 0.6, 45.0, -0.55, 0.7, 0.009, 0.2, 0.0012, 0.0001, 0.0008),
    (2, 0.022, 0.0, 1.0e-4, 0.07, 8.0e-4, -0.05, 30.0, 0.05, -4.0, 0.015, -0.05, 0.0, 0.0, 0.0),
    (4, 0.02, 0.009, 1.8e-4, 0.06, 2.0e-3, 0.1, 24.0, 0.8, -0.3, 0.003, 0.0, 0.0004, 0.0006, 0.0),
    (1, 0.015, 0.005, 1.6e-4, 0.08, 5.0e-4, -1.0, 60.0, -0.1, 1.8, 0.01, -0.4, 0.0, -0.0008, 0.0),
    (4, 0.011, 0.002, 7.5e-5, 0.095, 4.0e-3, 0.35, 21.0, -1.4, 0.9, 0.007, 0.05, 0.0003, 0.0005, 0.001),
)


def test_10_py05_seeded_cross_model() -> None:
    """Layer 4. Algebraic recovery of prescribed PY-05 hinge acceleration. No controller."""
    assert len(_PY05_CASES) == 12
    rows = []
    for case in _PY05_CASES:
        count, mass, cg, inertia, radius, i0, theta, omega, theta_dot, omega_dot, stiffness, rest, damping, qh, coulomb = case
        assert inertia + 16.0 * math.ulp(inertia) >= mass * cg ** 2
        friction = DryFriction() if coulomb == 0.0 else DryFriction(
            "regularized_coulomb", coulomb, 0.2, source="phase4-py05"
        )
        parameters = _parameters(
            mass_kg=mass,
            cg_distance_m=cg,
            hinge_inertia_kg_m2=inertia,
            hinge_radius_m=radius,
            spring_stiffness_nm_rad=stiffness,
            rest_angle_rad=rest,
            viscous_damping_nm_s_rad=damping,
            dry_friction=friction,
        )
        system = _system(parameters, count, i0)
        produced = coupled_mass_matrix(system, theta)
        independent = _independent_matrix(system, theta)
        assert produced.m00 == pytest.approx(independent[0], rel=1.0e-15, abs=0.0)
        hinge = prescribed_shaft_hinge_acceleration(parameters, theta, theta_dot, omega, omega_dot, qh)
        gyro = count * produced.c_kg_m2 * math.sin(theta) * (2.0 * omega * theta_dot + theta_dot ** 2)
        qm_qa = produced.m00 * omega_dot + produced.m01 * hinge.theta_ddot_rad_s2 - gyro
        solved = coupled_accelerations(system, theta, theta_dot, omega, qm_qa, 0.0, qh)
        scale = max(1.0, abs(omega_dot), abs(hinge.theta_ddot_rad_s2))
        omega_gap = abs(solved.omega_dot_rad_s2 - omega_dot)
        hinge_gap = abs(solved.theta_ddot_rad_s2 - hinge.theta_ddot_rad_s2)
        assert omega_gap <= 1.0e-8 * scale
        assert hinge_gap <= 1.0e-8 * scale
        rows.append({"omega_gap": omega_gap, "hinge_gap": hinge_gap, "pivot": produced.represented_pivot})
    _record(
        "10",
        {
            "reference": "cross-model",
            "fixture": "py05-frozen-12",
            "cases": len(rows),
            "max_omega_gap": max(row["omega_gap"] for row in rows),
            "max_hinge_gap": max(row["hinge_gap"] for row in rows),
            "min_pivot": min(row["pivot"] for row in rows),
            "threshold": "1e-8 * acceleration scale",
            "threshold_basis": "mathematical",
            "result": "PASS",
        },
    )


def _equilibrium_blade():
    blade = BladeGeometry(
        diameter_m=0.30,
        hub_radius_m=0.02,
        blade_count=2,
        stations=(
            BladeStation(0.2, 0.04, 0.45, "root"),
            BladeStation(0.5, 0.035, 0.35, "root"),
            BladeStation(0.8, 0.025, 0.22, "tip"),
            BladeStation(1.0, 0.015, 0.15, "tip"),
        ),
    )
    schedule = SpanwisePolarSchedule(
        "phase4-equilibrium",
        (
            SpanwisePolarAnchor(0.2, _broad_family(0.6, "root", "phase4-root")),
            SpanwisePolarAnchor(0.8, _broad_family(0.8, "tip", "phase4-tip")),
            SpanwisePolarAnchor(1.0, _broad_family(0.8, "tip", "phase4-tip")),
        ),
    )
    return blade, schedule


def test_11_pr07_real_bem_equilibrium() -> None:
    """Layer 4. Runtime PR-07 root is the reference. Stops straddle zero."""
    blade, schedule = _equilibrium_blade()
    motor = MotorSpec(1000.0, 0.05, 1.0, 80.0)
    battery = BatterySpec(12.0, 0.98)
    electrical = SystemSpec(0.01)
    throttle = 0.35
    environment = CoupledEnvironment("phase4-eq", 4.0, 1.225, 1.81e-5, 288.15, 101325.0)
    settings = BEMRotorSettings(
        annulus_count=4,
        annulus_settings=BEMAnnulusSettings(bracket_samples=16, loading_branch="positive_only"),
    )

    def aero_load(rpm: float) -> AeroLoadSample:
        evaluator = FoldableBemShaftEvaluator(blade, schedule, settings, environment, 0.075, "error")
        omega = rpm * math.pi / 30.0
        sample = evaluator(0.0, 0.0, 0.0, omega)
        return AeroLoadSample(
            rpm=rpm,
            thrust_n=sample.thrust_n,
            torque_nm=sample.shaft_torque_nm,
            shaft_power_w=sample.shaft_torque_nm * omega,
            source_id=sample.source_id,
            qualification=sample.qualification,
        )

    point = solve_coupled_operating_point(
        motor=motor,
        battery=battery,
        system=electrical,
        throttle=throttle,
        aero_load=aero_load,
    )
    assert point.feasible is True
    assert abs(point.torque_residual_nm) <= point.torque_tolerance_nm
    omega0 = point.rpm * math.pi / 30.0
    parameters = _parameters(
        hinge_radius_m=0.075,
        lower_stop_rad=-0.5,
        upper_stop_rad=0.5,
    )
    system = _system(parameters, 2, 1.0e-3)
    motor_law = Pr07MotorEvaluator(motor, battery, electrical, throttle)
    aero_law = FoldableBemShaftEvaluator(blade, schedule, settings, environment, 0.075, "error")
    motor_sample = motor_law(0.0, 0.0, 0.0, omega0)
    aero_sample = aero_law(0.0, 0.0, 0.0, omega0)
    torque_gap = abs(motor_sample.torque_nm - aero_sample.shaft_torque_nm)
    assert torque_gap <= point.torque_tolerance_nm
    solved = coupled_accelerations(
        system, 0.0, 0.0, omega0, motor_sample.torque_nm, aero_sample.shaft_torque_nm, 0.0
    )
    matrix = coupled_mass_matrix(system, 0.0)
    rhs = (motor_sample.torque_nm - aero_sample.shaft_torque_nm, 0.0)
    direct = _decimal_solve(matrix.m00, matrix.m01, matrix.m11, rhs[0], rhs[1])
    assert solved.omega_dot_rad_s2 == pytest.approx(direct[0], rel=1.0e-9, abs=1.0e-9)
    assert solved.theta_ddot_rad_s2 == pytest.approx(direct[1], rel=1.0e-9, abs=1.0e-9)
    controls = _controls(max_step_s=0.002)
    result = _solve(
        system,
        _history(0.0, 0.01, "equilibrium"),
        0.0,
        0.0,
        omega0,
        Pr07MotorEvaluator(motor, battery, electrical, throttle),
        FoldableBemShaftEvaluator(blade, schedule, settings, environment, 0.075, "error"),
        controls,
    )
    _screening(result)
    assert result.status == "completed"

    def reference(time_s: float):
        return (direct[1] * 0.5 * time_s ** 2, direct[1] * time_s, omega0 + direct[0] * time_s)

    report = _component_errors(result.samples, reference, controls)
    _accept_normalized(report)
    _record(
        "11",
        {
            "reference": "cross-model",
            "fixture": "pr07-foldable-bem-equilibrium",
            "rpm": point.rpm,
            "torque_residual_nm": point.torque_residual_nm,
            "torque_tolerance_nm": point.torque_tolerance_nm,
            "accelerations": {"omega_dot": direct[0], "theta_ddot": direct[1]},
            "errors": report,
            "threshold": 1.0,
            "threshold_basis": "numerical-policy",
            "result": "PASS",
        },
    )


def test_12_reused_deployed_bem_exact_limit() -> None:
    """Layer 4 prerequisite. The existing production equality test is the evidence."""
    _service_tests.test_deployed_evaluator_matches_fixed_and_foldable_bem()
    _record(
        "12",
        {
            "reference": "cross-model",
            "fixture": "tests/application/test_coupled_transient_service.py::test_deployed_evaluator_matches_fixed_and_foldable_bem",
            "result": "REUSED",
            "threshold_basis": "mathematical",
            "interpretation": "Deployed foldable BEM matches fixed-rotor BEM at theta = 0. No physical promotion.",
        },
    )


def test_13_production_source_bound_ode_convergence() -> None:
    """Layer 5. Real PR-07 and foldable BEM, three step ceilings, DOP853 reference."""
    context = _source_context()
    controls_base = dict(
        rtol=1.0e-5,
        angle_atol_rad=1.0e-7,
        hinge_velocity_atol_rad_s=1.0e-6,
        shaft_speed_atol_rad_s=1.0e-5,
        max_duration_s=0.05,
    )
    runs = []
    for step in (0.002, 0.001, 0.0005):
        controls = _controls(max_step_s=step, **controls_base)
        artifact = run_coupled_transient(_source_binding(context, annulus_count=8, controls=controls))
        result = artifact.result
        _screening(result)
        assert result.status == "completed"
        assert result.contact is None
        assert result.samples[0].bem_qualification == "screening_only_until_pr06c_passes"
        document = json.loads(artifact.report_json)
        assert document["physical_qualification"] is False
        assert document["bem_qualification"] == "screening_only_until_pr06c_passes"
        assert document["aerodynamic_hinge_torque_status"] == AERO_HINGE_STATUS
        runs.append((controls, result))
    factory = _source_rhs_factory(context, 8, context["duration"])
    y0 = (context["theta"], 0.0, context["omega"])
    loose = _dop853(factory(), y0, context["duration"], 1.0e-8, 1.0e-10)
    tight = _dop853(factory(), y0, context["duration"], 1.0e-10, 1.0e-12)
    times = [sample.time_s for _controls_used, result in runs for sample in result.samples]
    change = _reference_change(loose, tight, times, runs[-1][0])
    assert max(change) <= 0.1
    reports = []
    for controls, result in runs:
        report = _errors_against_dense(result.samples, tight, controls)
        reports.append(
            {
                "max_step_s": controls.max_step_s,
                "samples": len(result.samples),
                "rhs": result.rhs_evaluations,
                "errors": report,
            }
        )
    _accept_normalized(reports[-1]["errors"])
    for index in range(3):
        endpoint_abs = [level["errors"]["endpoint_abs"][index] for level in reports]
        assert endpoint_abs[1] < endpoint_abs[0]
        assert endpoint_abs[2] < endpoint_abs[1]
    _record(
        "13",
        {
            "reference": "independent solver",
            "fixture": "source-bound-folded-annulus-8",
            "reference_change_e": change,
            "levels": reports,
            "threshold": 1.0,
            "threshold_basis": "numerical-policy",
            "result": "PASS",
        },
    )


def test_14_embedded_bem_annulus_sensitivity() -> None:
    """Layer 5. Annulus count changes only. ODE controls stay fixed."""
    context = _source_context()
    controls = _controls(
        rtol=1.0e-6,
        angle_atol_rad=1.0e-8,
        hinge_velocity_atol_rad_s=1.0e-8,
        shaft_speed_atol_rad_s=1.0e-6,
        max_step_s=0.001,
        max_duration_s=0.05,
    )
    endpoints = {}
    for count in (4, 8, 16):
        result = run_coupled_transient(
            _source_binding(context, annulus_count=count, controls=controls)
        ).result
        _screening(result)
        assert result.status == "completed"
        sample = result.samples[-1]
        endpoints[count] = {
            "theta": sample.theta_rad,
            "theta_dot": sample.theta_dot_rad_s,
            "omega": sample.omega_rad_s,
            "rotor_torque_nm": sample.bem_shaft_torque_nm,
            "samples": len(result.samples),
        }
    names = ("theta", "theta_dot", "omega", "rotor_torque_nm")
    changes = {}
    monotone = True
    for name in names:
        coarse = abs(endpoints[8][name] - endpoints[4][name])
        fine = abs(endpoints[16][name] - endpoints[8][name])
        changes[name] = {"change_4_to_8": coarse, "change_8_to_16": fine}
        monotone = monotone and fine < coarse
    _record(
        "14",
        {
            "reference": "characterization",
            "fixture": "source-bound-folded-annulus-4-8-16",
            "endpoints": endpoints,
            "changes": changes,
            "threshold": "change(8 to 16) < change(4 to 8) for each declared quantity",
            "threshold_basis": "empirical-regression",
            "result": "PASS" if monotone else "UNRESOLVED",
        },
    )
    assert monotone


def _piecewise_reference(system, knots, torques, theta0, velocity0, omega0):
    k_inertia, l_inertia, reduced = _kl_constants(system)
    beta = system.blade_count / reduced
    ratio = l_inertia / k_inertia

    def state_at(time_s: float):
        theta, rate, speed = theta0, velocity0, omega0
        for start, end, left, right in zip(knots, knots[1:], torques, torques[1:]):
            if time_s <= start:
                break
            span = end - start
            slope = (right - left) / span
            local = min(time_s, end) - start
            next_rate = rate + beta * (left * local + 0.5 * slope * local ** 2)
            next_theta = theta + rate * local + beta * (
                0.5 * left * local ** 2 + slope * local ** 3 / 6.0
            )
            next_speed = speed - ratio * (next_rate - rate)
            theta, rate, speed = next_theta, next_rate, next_speed
            if time_s <= end:
                break
        return (theta, rate, speed)

    return state_at, beta, ratio


def test_15_knot_restart_manual_split() -> None:
    """Layer 6. Continuous piecewise-linear Qh with one interior slope change."""
    system = _system(_parameters(), 2, 1.0e-3)
    knots = (0.0, 0.02, 0.04)
    torques = (0.0, 0.0012, 0.0002)
    theta0, velocity0, omega0 = 0.02, 0.1, 28.0
    reference, beta, ratio = _piecewise_reference(system, knots, torques, theta0, velocity0, omega0)
    solved = coupled_accelerations(system, theta0, velocity0, omega0, 0.0, 0.0, torques[0])
    assert solved.theta_ddot_rad_s2 == pytest.approx(beta * torques[0], rel=1.0e-12, abs=1.0e-12)
    assert solved.omega_dot_rad_s2 == pytest.approx(-ratio * beta * torques[0], rel=1.0e-12, abs=1.0e-12)
    levels = []
    for step in (0.002, 0.001, 0.0005):
        controls = _controls(
            rtol=1.0e-3,
            angle_atol_rad=1.0e-4,
            hinge_velocity_atol_rad_s=1.0e-3,
            shaft_speed_atol_rad_s=1.0e-2,
            max_step_s=step,
        )
        full = _solve(
            system,
            HingeActuationHistory(knots, torques, "kink"),
            theta0,
            velocity0,
            omega0,
            _motor_torque(0.0),
            _aero_torque(0.0),
            controls,
        )
        _screening(full)
        assert full.status == "completed"
        assert knots[1] in full.segment_boundary_times_s
        first = _solve(
            system,
            HingeActuationHistory((knots[0], knots[1]), (torques[0], torques[1]), "split-1"),
            theta0,
            velocity0,
            omega0,
            _motor_torque(0.0),
            _aero_torque(0.0),
            controls,
        )
        terminal = first.samples[-1]
        second = _solve(
            system,
            HingeActuationHistory((knots[1], knots[2]), (torques[1], torques[2]), "split-2"),
            terminal.theta_rad,
            terminal.theta_dot_rad_s,
            terminal.omega_rad_s,
            _motor_torque(0.0),
            _aero_torque(0.0),
            controls,
        )
        report = _component_errors(full.samples, reference, controls)
        _accept_normalized(report)
        split_end = (
            second.samples[-1].theta_rad,
            second.samples[-1].theta_dot_rad_s,
            second.samples[-1].omega_rad_s,
        )
        full_end = (
            full.samples[-1].theta_rad,
            full.samples[-1].theta_dot_rad_s,
            full.samples[-1].omega_rad_s,
        )
        split_gap = tuple(
            abs(left - right) / width
            for left, right, width in zip(split_end, full_end, _scales(controls, full_end))
        )
        assert max(split_gap) <= 1.0
        before = next(sample for sample in full.samples if 0.0 < sample.time_s < knots[1])
        after = next(sample for sample in full.samples if sample.time_s > knots[1])
        assert before.hinge_actuation_nm == pytest.approx(torques[1] * before.time_s / knots[1], abs=1.0e-15)
        fraction = (after.time_s - knots[1]) / (knots[2] - knots[1])
        expected = torques[1] + fraction * (torques[2] - torques[1])
        assert after.hinge_actuation_nm == pytest.approx(expected, abs=1.0e-15)
        levels.append(
            {
                "max_step_s": step,
                "samples": len(full.samples),
                "rhs": full.rhs_evaluations,
                "errors": report,
                "split_gap_e": split_gap,
            }
        )
    disposition = {}
    for index, name in enumerate(("theta", "theta_dot", "omega")):
        errors = [level["errors"]["max_abs"][index] for level in levels]
        floor = 256.0 * math.ulp(1.0)
        disposition[name] = _require_order_or_roundoff(errors, floor)
    _record(
        "15",
        {
            "reference": "analytic",
            "fixture": "continuous-slope-change",
            "levels": levels,
            "order_disposition": disposition,
            "threshold": 1.0,
            "threshold_basis": "numerical-policy",
            "result": "PASS",
        },
    )


def test_16_analytic_first_contact() -> None:
    """Layer 6. Case B event reconstruction. Not an impact-physics claim."""
    theta0 = -0.01
    velocity = 1.5
    upper = 0.0047
    contact_time = (upper - theta0) / velocity
    parameters = _parameters(lower_stop_rad=-0.8, upper_stop_rad=upper)
    system = _system(parameters, 2, 1.0e-3)
    omega0 = 30.0
    rows = []
    for step in (0.002, 0.001, 0.0005):
        assert abs(contact_time / step - round(contact_time / step)) > 0.05
        controls = _controls(max_step_s=step, max_duration_s=0.05)
        result = _solve(
            system,
            _history(0.0, 0.02, "contact"),
            theta0,
            velocity,
            omega0,
            _motor_torque(0.0),
            _aero_torque(0.0),
            controls,
        )
        _screening(result)
        assert result.status == "first_contact_terminal"
        assert result.contact is not None
        assert result.contact.stop == "upper"
        assert result.samples[-1].time_s == result.contact.time_s
        assert all(sample.time_s <= result.contact.time_s for sample in result.samples)
        assert result.samples[-1].time_s < 0.02
        time_error = abs(result.contact.time_s - contact_time)
        rate_error = abs(result.contact.preimpact_angular_velocity_rad_s - velocity)
        speed_error = abs(result.contact.omega_rad_s - omega0)
        assert time_error <= max(8.0 * controls.angle_atol_rad / abs(velocity), 4.0 * math.ulp(contact_time))
        assert rate_error <= max(8.0 * controls.hinge_velocity_atol_rad_s, 4.0 * math.ulp(abs(velocity)))
        assert speed_error <= controls.shaft_speed_atol_rad_s
        rows.append(
            {
                "max_step_s": step,
                "time_error_s": time_error,
                "rate_error": rate_error,
                "speed_error": speed_error,
                "samples": len(result.samples),
            }
        )
    _record(
        "16",
        {
            "reference": "analytic",
            "fixture": "case-b-first-contact",
            "contact_time_s": contact_time,
            "levels": rows,
            "threshold": "event reconstruction tolerance from the solver angle atol",
            "threshold_basis": "numerical-policy",
            "result": "PASS",
        },
    )


def test_17_nonlinear_motor_algebra() -> None:
    """Layer 1. Independent cubic voltage residual for resistance_quadratic > 0."""
    motor = MotorSpec(1200.0, 0.08, 0.2, 40.0, resistance_quadratic=0.001)
    battery = BatterySpec(16.0, 1.0)
    electrical = SystemSpec(0.02)
    throttle = 0.6
    evaluator = Pr07MotorEvaluator(motor, battery, electrical, throttle)
    rows = []
    for rpm in (5000.0, 8500.0, 10500.0):
        state = algebraic_motor_state(motor, battery, electrical, throttle, rpm)
        sample = evaluator(0.0, 0.0, 0.0, rpm * math.pi / 30.0)
        applied = throttle * battery.voltage_v
        back_emf = (rpm / motor.kv_rpm_per_v) * (1.0 + motor.magnetic_lag_tau * rpm * math.pi / 30.0)
        voltage_head = applied - back_emf
        current = state.current_a
        residual = current * (
            motor.resistance_ohm + motor.resistance_quadratic * current ** 2 + electrical.resistance_ohm
        ) - voltage_head
        kt = 30.0 / (math.pi * motor.kv_rpm_per_v * motor.torque_constant_kv_ratio)
        torque = kt * (current - motor.get_no_load_current(rpm))
        scale = max(1.0, abs(voltage_head))
        gain = abs(
            motor.resistance_ohm
            + electrical.resistance_ohm
            + 3.0 * motor.resistance_quadratic * current ** 2
        )
        xtol = float(inspect.signature(brentq).parameters["xtol"].default)
        limit = max(64.0 * math.ulp(scale), xtol * max(gain, 1.0))
        assert abs(residual) <= limit
        assert sample.current_a == pytest.approx(state.current_a, abs=0.0)
        assert torque == pytest.approx(state.torque_nm, rel=0.0, abs=8.0 * math.ulp(max(1.0, abs(torque))))
        assert sample.torque_nm == pytest.approx(state.torque_nm, abs=0.0)
        rows.append(
            {
                "rpm": rpm,
                "current_a": current,
                "cubic_residual_v": residual,
                "residual_limit_v": limit,
                "torque_nm": torque,
            }
        )
    _record(
        "17",
        {
            "reference": "analytic",
            "fixture": "quadratic-resistance-cubic",
            "rows": rows,
            "threshold": "max(64 ulp of voltage head, brentq default xtol times local voltage gain)",
            "threshold_basis": "numerical-policy",
            "result": "PASS",
        },
    )


def test_18_numerical_boundary_classification() -> None:
    """Layer 6. Inside succeeds. Outside raises and returns no success artifact."""
    families = {}
    inside = _solve(
        _system(),
        _history(0.0, 0.004),
        -0.2,
        0.0,
        OMEGA_MIN * 2.0,
        _motor_torque(0.0),
        _aero_torque(0.0),
        _controls(max_step_s=0.002),
    )
    assert inside.status == "completed"
    with pytest.raises(CoupledTransientError):
        CoupledTransientRequest(
            _system(),
            _history(0.0, 0.004),
            -0.2,
            0.0,
            OMEGA_MIN * 0.5,
            _motor_torque(0.0),
            _aero_torque(0.0),
        )
    families["omega_floor"] = "inside completed; outside request rejected"
    with pytest.raises(CoupledTransientError):
        CoupledTransientRequest(
            _system(_parameters(lower_stop_rad=-2.0, upper_stop_rad=2.0)),
            _history(0.0, 0.004),
            FOLD_LIMIT_RAD,
            0.0,
            30.0,
            _motor_torque(0.0),
            _aero_torque(0.0),
        )
    families["fold_limit"] = "exact pi/2 rejected before integration"
    motor = MotorSpec(1000.0, 0.05, 1.0, 80.0)
    battery = BatterySpec(12.0, 0.98)
    electrical = SystemSpec(0.01)
    held = Pr07MotorEvaluator(motor, battery, electrical, 0.2)
    assert held(0.0, -0.2, 0.0, 400.0 * math.pi / 30.0).current_a < motor.current_max_a
    limited = Pr07MotorEvaluator(MotorSpec(1000.0, 0.05, 1.0, 5.0), battery, electrical, 1.0)
    with pytest.raises(CoupledDomainExit, match="current"):
        limited(0.0, 0.0, 0.0, 200.0 * math.pi / 30.0)
    families["motor_current"] = "interior current returned; excess current raised"
    blade, schedule = _equilibrium_blade()
    environment = CoupledEnvironment("phase4-bounds", 4.0, 1.225, 1.81e-5, 288.15, 101325.0)
    settings = BEMRotorSettings(
        annulus_count=4,
        annulus_settings=BEMAnnulusSettings(bracket_samples=16, loading_branch="positive_only"),
    )
    covered = FoldableBemShaftEvaluator(blade, schedule, settings, environment, 0.075, "error")
    covered_sample = covered(0.0, -0.2, 0.0, 500.0)
    assert math.isfinite(covered_sample.shaft_torque_nm)
    narrow = PolarFamily(
        (
            PolarTable(
                airfoil_id="narrow",
                scenario_id="phase4",
                reynolds=1.0e5,
                mach=0.0,
                alpha_rad=(-0.5, 0.5),
                cl=(0.2, 0.2),
                cd=(0.02, 0.02),
                cm=(0.0, 0.0),
                source="mach-only-zero",
            ),
        )
    )
    narrow_schedule = SpanwisePolarSchedule(
        "narrow",
        (SpanwisePolarAnchor(0.2, narrow), SpanwisePolarAnchor(1.0, narrow)),
    )
    outside = FoldableBemShaftEvaluator(blade, narrow_schedule, settings, environment, 0.075, "error")
    with pytest.raises(CoupledTransientFailure, match="BEM"):
        outside(0.0, -0.2, 0.0, 500.0)
    families["polar_bounds"] = "broad polar evaluated; mach-outside polar raised"
    resolved = coupled_mass_matrix(
        _system(
            _parameters(
                mass_kg=0.02,
                cg_distance_m=0.01,
                hinge_inertia_kg_m2=0.02 * 0.01 ** 2,
            ),
            2,
            1.0e-8,
        ),
        0.0,
    )
    assert resolved.schur_kg_m2 > 0.0
    with pytest.raises(CoupledTransientFailure, match="unresolved"):
        coupled_mass_matrix(
            _system(
                _parameters(
                    mass_kg=0.02,
                    cg_distance_m=0.01,
                    hinge_inertia_kg_m2=0.02 * 0.01 ** 2,
                ),
                2,
                1.0e-20,
            ),
            0.0,
        )
    families["mass_resolution"] = "I0=1e-8 resolved; I0=1e-20 unresolved"
    _record(
        "18",
        {
            "reference": "characterization",
            "fixture": "hard-domain-edges",
            "families": families,
            "threshold": "invalid input raises and does not return a success artifact",
            "threshold_basis": "mathematical",
            "result": "PASS",
        },
    )


def test_19_same_environment_reproducibility() -> None:
    """Layer 6. One sealed binding, two fresh production integrations."""
    context = _source_context()
    controls = _controls(max_step_s=0.002, max_duration_s=0.02)
    binding = _source_binding(context, annulus_count=4, controls=controls, duration=0.008)
    first = run_coupled_transient(binding)
    second = run_coupled_transient(binding)
    assert first.input_sha256 == second.input_sha256 == binding.input_sha256
    assert first.result.status == second.result.status == "completed"
    assert first.result.contact is None and second.result.contact is None
    assert len(first.result.samples) == len(second.result.samples)

    def rows(result):
        return tuple(
            (
                sample.time_s,
                sample.theta_rad,
                sample.theta_dot_rad_s,
                sample.omega_rad_s,
                sample.theta_ddot_rad_s2,
                sample.omega_dot_rad_s2,
                sample.motor_torque_nm,
                sample.bem_shaft_torque_nm,
                sample.mechanical_energy_j,
                sample.cumulative_work_j,
            )
            for sample in result.samples
        )

    assert rows(first.result) == rows(second.result)
    assert first.report_json == second.report_json
    assert first.report_sha256 == second.report_sha256
    _screening(first.result)
    _record(
        "19",
        {
            "reference": "characterization",
            "fixture": "sealed-source-bound-replay",
            "samples": len(first.result.samples),
            "input_sha256": first.input_sha256,
            "report_sha256": first.report_sha256,
            "threshold": "bitwise equality in one Python process",
            "threshold_basis": "mathematical",
            "result": "PASS",
        },
    )
