"""Isolated CMM-2 paired-load screening dynamics.

PR-A solves the signed shaft and one-tip hinge generalized loads on the
existing CMM-1 mass matrix. It does not bind a production aerodynamic source,
change CMM-1, or claim physical qualification. The implementation is under
review.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from scipy.integrate import RK45

from pyfoldable.dynamics.coupled_transient import (
    FOLD_LIMIT_RAD,
    OMEGA_MIN,
    CoupledDomainExit,
    CoupledSolverControls,
    CoupledSystem,
    CoupledTransientError,
    CoupledTransientFailure,
    HingeActuationHistory,
    MotorEvaluation,
    _ContactControls,
    _audit_dense_model_domain,
    _friction_nm,
    _interpolate,
    _row_backward_error,
    coupled_mass_matrix,
    mechanical_energy,
)
from pyfoldable.dynamics.mechanism_contracts import ContactPolicy
from pyfoldable.dynamics.mechanism_transient import _first_contact


MODEL_CLASS = "coupled_aero_hinge_screening_only"
IMPLEMENTATION_ID = "cmm2_planar_projected_rate_independent_coupling_v1"
LOAD_MAPPING_MODEL = "planar_projected_material_load_v1"
AERO_LOAD_QUALIFICATION = "screening_only_projected_rate_independent"
HINGE_RATE_AERO_MODEL = "ignored_rate_independent_quasi_steady"
PROJECTION_MODEL = "radial_cosine_v1"
AERO_LOAD_STATUS = "signed_paired_generalized_loads"

CMM2_LIMITATIONS = (
    "PR-A is isolated paired-load dynamics under independent review.",
    "Production aerodynamic source binding is not implemented.",
    "Aerodynamic loads are a rate-independent quasi-steady screen.",
    "No physical hinge-rate validity range is claimed.",
    "CMM-1 Phase-4 numerical verification does not transfer to this solver.",
    "PR-06C physical aerodynamic gate is unresolved.",
    "physical_qualification is false.",
    "No GEOM clearance, calibration, or experimental validation is claimed.",
    "CMM-2 is not an accepted physical model.",
)


class Cmm2TransientError(ValueError):
    """The CMM-2 request is not a valid screening problem."""


class Cmm2TransientFailure(RuntimeError):
    """A hard CMM-2 failure. No successful shortened trajectory is returned."""


class Cmm2DomainExit(Cmm2TransientFailure):
    """The state left the CMM-2 model domain and was not continued."""


def _raise_translated(exc: BaseException) -> None:
    """Re-voice an unchanged CMM-1 numerical failure as a CMM-2 failure."""
    if isinstance(exc, CoupledDomainExit):
        raise Cmm2DomainExit(str(exc).replace("CMM-1", "CMM-2")) from exc
    if isinstance(exc, CoupledTransientFailure):
        raise Cmm2TransientFailure(str(exc).replace("CMM-1", "CMM-2")) from exc
    if isinstance(exc, CoupledTransientError):
        raise Cmm2TransientError(str(exc).replace("CMM-1", "CMM-2")) from exc
    raise exc


def _finite_error(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Cmm2TransientError(f"{name} must be a finite scalar.")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise Cmm2TransientError(f"{name} must be a finite scalar.") from exc
    if not math.isfinite(result):
        raise Cmm2TransientError(f"{name} must be a finite scalar.")
    return result


def _finite_failure(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Cmm2TransientFailure(f"CMM-2 {name} is not representable.")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise Cmm2TransientFailure(f"CMM-2 {name} is not representable.") from exc
    if not math.isfinite(result):
        raise Cmm2TransientFailure(f"CMM-2 {name} is not finite.")
    return result


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise Cmm2TransientError(f"{name} must be a nonempty bounded string.")
    return value


def _approved(name: str, value: object, expected: str) -> str:
    text = _text(name, value)
    if text != expected:
        raise Cmm2TransientError(f"{name} must match the CMM-2 screening contract.")
    return text


@dataclass(frozen=True)
class Cmm2AeroEvaluation:
    """Signed paired generalized loads for one CMM-2 state.

    ``whole_rotor_shaft_generalized_load_nm`` is the whole-rotor shaft load.
    ``one_tip_hinge_generalized_load_nm`` is one tip, not the N-tip sum.
    """

    whole_rotor_shaft_generalized_load_nm: float
    one_tip_hinge_generalized_load_nm: float
    thrust_n: float
    load_mapping_model: str
    qualification: str
    projection_model: str
    hinge_rate_aerodynamic_model: str
    blade_count: int
    hinge_radius_m: float
    theta_rad: float
    hinge_rate_rad_s: float
    source_id: str

    def __post_init__(self) -> None:
        _finite_failure(
            "shaft generalized load", self.whole_rotor_shaft_generalized_load_nm
        )
        _finite_failure(
            "one-tip hinge generalized load", self.one_tip_hinge_generalized_load_nm
        )
        _finite_failure("thrust", self.thrust_n)
        _approved("load_mapping_model", self.load_mapping_model, LOAD_MAPPING_MODEL)
        _approved("qualification", self.qualification, AERO_LOAD_QUALIFICATION)
        _approved("projection_model", self.projection_model, PROJECTION_MODEL)
        _approved(
            "hinge_rate_aerodynamic_model",
            self.hinge_rate_aerodynamic_model,
            HINGE_RATE_AERO_MODEL,
        )
        if (
            isinstance(self.blade_count, bool)
            or not isinstance(self.blade_count, int)
            or not 1 <= self.blade_count <= 32
        ):
            raise Cmm2TransientError("blade_count must be an integer from 1 to 32.")
        radius = _finite_failure("hinge radius", self.hinge_radius_m)
        if radius <= 0.0:
            raise Cmm2TransientError("Hinge radius must be strictly positive.")
        _finite_failure("theta", self.theta_rad)
        _finite_failure("hinge rate", self.hinge_rate_rad_s)
        _text("aerodynamic source id", self.source_id)

    def generalized_power_w(self, omega_rad_s: float) -> float:
        """Shaft power plus one collective hinge-rate term. Not a second load."""
        speed = _finite_failure("omega", omega_rad_s)
        try:
            power = (
                self.whole_rotor_shaft_generalized_load_nm * speed
                + self.blade_count
                * self.one_tip_hinge_generalized_load_nm
                * self.hinge_rate_rad_s
            )
        except (ArithmeticError, OverflowError) as exc:
            raise Cmm2TransientFailure("CMM-2 aerodynamic power is not finite.") from exc
        if not math.isfinite(power):
            raise Cmm2TransientFailure("CMM-2 aerodynamic power is not finite.")
        return power


@dataclass(frozen=True)
class Cmm2CoupledAcceleration:
    """Solved CMM-2 accelerations and the paired-load diagnostics."""

    omega_dot_rad_s2: float
    theta_ddot_rad_s2: float
    rhs_shaft_nm: float
    rhs_hinge_nm: float
    motor_torque_nm: float
    aero_shaft_generalized_load_nm: float
    aero_one_tip_hinge_generalized_load_nm: float
    aero_collective_hinge_generalized_load_nm: float
    aero_generalized_power_w: float
    collective_hinge_actuation_nm: float
    collective_spring_nm: float
    collective_damping_nm: float
    collective_friction_nm: float
    spring_nm: float
    damping_nm: float
    friction_nm: float
    centrifugal_torque_nm: float
    shaft_gyro_nm: float
    mass_schur: float
    mass_residual: float


@dataclass(frozen=True)
class Cmm2StopContact:
    stop: str
    time_s: float
    angle_rad: float
    preimpact_angular_velocity_rad_s: float
    omega_rad_s: float


@dataclass(frozen=True)
class Cmm2Sample:
    time_s: float
    theta_rad: float
    theta_dot_rad_s: float
    theta_ddot_rad_s2: float
    omega_rad_s: float
    omega_dot_rad_s2: float
    rpm: float
    motor_torque_nm: float
    aero_shaft_generalized_load_nm: float
    aero_one_tip_hinge_generalized_load_nm: float
    aero_collective_hinge_generalized_load_nm: float
    aero_generalized_power_w: float
    aero_thrust_n: float
    aero_load_mapping_model: str
    aero_load_qualification: str
    aero_projection_model: str
    aero_hinge_rate_model: str
    aero_source_id: str
    hinge_actuation_nm: float
    collective_hinge_actuation_nm: float
    spring_torque_nm: float
    damping_torque_nm: float
    dry_friction_torque_nm: float
    centrifugal_torque_nm: float
    shaft_gyro_nm: float
    mass_schur: float
    mass_residual: float
    kinetic_energy_j: float
    spring_energy_j: float
    mechanical_energy_j: float
    motor_shaft_power_w: float
    hinge_actuation_power_w: float
    damping_power_w: float
    dry_friction_power_w: float
    power_identity_w: float
    cumulative_work_j: float
    energy_residual_j: float

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if name in {
                "aero_load_mapping_model",
                "aero_load_qualification",
                "aero_projection_model",
                "aero_hinge_rate_model",
                "aero_source_id",
            }:
                _text(name, value)
                continue
            _finite_failure(name, value)


@dataclass(frozen=True)
class Cmm2TransientRequest:
    """One bounded CMM-2 screening integration with an analytic load callback."""

    system: CoupledSystem
    actuation: HingeActuationHistory
    initial_angle_rad: float
    initial_angular_velocity_rad_s: float
    initial_omega_rad_s: float
    motor_evaluator: Callable
    aero_evaluator: Callable
    controls: CoupledSolverControls = CoupledSolverControls()
    contact_policy: ContactPolicy = ContactPolicy()

    def __post_init__(self) -> None:
        if not isinstance(self.system, CoupledSystem):
            raise Cmm2TransientError("system must be a CoupledSystem.")
        if not isinstance(self.actuation, HingeActuationHistory):
            raise Cmm2TransientError("actuation must be a HingeActuationHistory.")
        if not isinstance(self.controls, CoupledSolverControls):
            raise Cmm2TransientError("controls must be CoupledSolverControls.")
        if not isinstance(self.contact_policy, ContactPolicy):
            raise Cmm2TransientError("contact_policy must be ContactPolicy.")
        if not callable(self.motor_evaluator) or not callable(self.aero_evaluator):
            raise Cmm2TransientError("Motor and aerodynamic evaluators must be callable.")
        theta = _finite_error("initial_angle_rad", self.initial_angle_rad)
        _finite_error(
            "initial_angular_velocity_rad_s", self.initial_angular_velocity_rad_s
        )
        omega = _finite_error("initial_omega_rad_s", self.initial_omega_rad_s)
        parameters = self.system.parameters
        if not parameters.lower_stop_rad < theta < parameters.upper_stop_rad:
            raise Cmm2TransientError("Initial angle must lie strictly inside both stops.")
        if abs(theta - self.system.deployed_angle_rad) >= FOLD_LIMIT_RAD:
            raise Cmm2TransientError(
                "Initial angle must lie strictly inside the foldable domain."
            )
        if omega < OMEGA_MIN:
            raise Cmm2TransientError(
                "Initial shaft speed must be at least the screening minimum of 100 rpm."
            )
        controls = self.controls
        if len(self.actuation.time_s) > controls.max_input_knots:
            raise Cmm2TransientError("Actuation knots exceed the screening ceiling.")
        duration = self.actuation.time_s[-1] - self.actuation.time_s[0]
        if duration <= 0.0 or duration > controls.max_duration_s:
            raise Cmm2TransientError("Actuation duration exceeds the screening ceiling.")
        minimum_samples = 1 + sum(
            math.ceil((later - earlier) / controls.max_step_s)
            for earlier, later in zip(self.actuation.time_s, self.actuation.time_s[1:])
        )
        if minimum_samples > controls.max_samples:
            raise Cmm2TransientError("Actuation history exceeds the sample budget preflight.")


@dataclass(frozen=True)
class Cmm2TransientResult:
    status: str
    model_class: str
    implementation_id: str
    physical_qualification: bool
    full_propeller_clearance: None
    surface_path_clearance: None
    interblade_clearance: None
    aero_load_status: str
    samples: tuple[Cmm2Sample, ...]
    segment_boundary_times_s: tuple[float, ...]
    contact: Cmm2StopContact | None
    rhs_evaluations: int
    aero_evaluations: int
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.model_class != MODEL_CLASS or self.implementation_id != IMPLEMENTATION_ID:
            raise Cmm2TransientError("CMM-2 cannot claim another model identity.")
        if self.physical_qualification is not False:
            raise Cmm2TransientError("CMM-2 cannot claim physical qualification.")
        if self.aero_load_status != AERO_LOAD_STATUS:
            raise Cmm2TransientError("CMM-2 aerodynamic status must stay explicit.")
        if (
            self.full_propeller_clearance is not None
            or self.surface_path_clearance is not None
            or self.interblade_clearance is not None
        ):
            raise Cmm2TransientError("CMM-2 cannot assign a GEOM clearance value.")
        if self.status not in {"completed", "first_contact_terminal"}:
            raise Cmm2TransientError("Unknown CMM-2 termination status.")
        if not isinstance(self.samples, tuple) or not self.samples:
            raise Cmm2TransientError("CMM-2 requires at least the initial sample.")
        if self.limitations != CMM2_LIMITATIONS:
            raise Cmm2TransientError("CMM-2 limitations cannot be replaced.")


def _require_state_bound(
    evaluation: Cmm2AeroEvaluation,
    system: CoupledSystem,
    theta: float,
    theta_dot: float,
) -> None:
    if (
        evaluation.blade_count != system.blade_count
        or evaluation.hinge_radius_m != system.parameters.hinge_radius_m
        or evaluation.theta_rad != theta
        or evaluation.hinge_rate_rad_s != theta_dot
    ):
        raise Cmm2TransientFailure(
            "CMM-2 refused a state-bound paired aerodynamic load from a different state."
        )


def _call_aero(evaluator: Callable, time_s: float, state: tuple[float, float, float]) -> Cmm2AeroEvaluation:
    try:
        value = evaluator(time_s, state[0], state[1], state[2])
    except (Cmm2TransientFailure, Cmm2TransientError):
        raise
    except (CoupledDomainExit, CoupledTransientFailure, CoupledTransientError) as exc:
        _raise_translated(exc)
    except (ArithmeticError, TypeError, ValueError, RuntimeError) as exc:
        raise Cmm2TransientFailure("CMM-2 aero evaluator failed.") from exc
    if not isinstance(value, Cmm2AeroEvaluation):
        raise Cmm2TransientFailure("CMM-2 aero evaluator returned an unexpected type.")
    return value


def _call_motor(evaluator: Callable, time_s: float, state: tuple[float, float, float]) -> MotorEvaluation:
    try:
        value = evaluator(time_s, state[0], state[1], state[2])
    except (Cmm2TransientFailure, Cmm2TransientError):
        raise
    except (CoupledDomainExit, CoupledTransientFailure, CoupledTransientError) as exc:
        _raise_translated(exc)
    except (ArithmeticError, TypeError, ValueError, RuntimeError) as exc:
        raise Cmm2TransientFailure("CMM-2 motor evaluator failed.") from exc
    if not isinstance(value, MotorEvaluation):
        raise Cmm2TransientFailure("CMM-2 motor evaluator returned an unexpected type.")
    return value


def _state(y) -> tuple[float, float, float]:
    try:
        theta = y[0]
        theta_dot = y[1]
        omega = y[2]
    except (IndexError, TypeError) as exc:
        raise Cmm2TransientFailure("CMM-2 state is not representable.") from exc
    return (
        _finite_failure("theta", theta),
        _finite_failure("theta_dot", theta_dot),
        _finite_failure("omega", omega),
    )


def cmm2_coupled_accelerations(
    system: CoupledSystem,
    theta: float,
    theta_dot: float,
    omega: float,
    motor_torque_nm: float,
    aero_evaluation: Cmm2AeroEvaluation,
    hinge_torque_nm: float,
) -> Cmm2CoupledAcceleration:
    """Solve the signed paired-load system on the unchanged CMM-1 mass matrix."""
    if not isinstance(system, CoupledSystem):
        raise Cmm2TransientError("system must be a CoupledSystem.")
    if not isinstance(aero_evaluation, Cmm2AeroEvaluation):
        raise Cmm2TransientFailure("CMM-2 aero evaluator returned an unexpected type.")
    angle = _finite_error("theta", theta)
    rate = _finite_error("theta_dot", theta_dot)
    speed = _finite_error("omega", omega)
    motor_torque = _finite_error("motor_torque_nm", motor_torque_nm)
    hinge_torque = _finite_error("hinge_torque_nm", hinge_torque_nm)
    _require_state_bound(aero_evaluation, system, angle, rate)
    try:
        mass = coupled_mass_matrix(system, angle)
    except (CoupledDomainExit, CoupledTransientFailure, CoupledTransientError) as exc:
        _raise_translated(exc)
        raise AssertionError("translated CMM-1 failure") from exc
    parameters = system.parameters
    try:
        spring = -parameters.spring_stiffness_nm_rad * (angle - parameters.rest_angle_rad)
        damping = -parameters.viscous_damping_nm_s_rad * rate
        friction = _friction_nm(parameters, rate)
        q_phi = aero_evaluation.whole_rotor_shaft_generalized_load_nm
        q_theta = aero_evaluation.one_tip_hinge_generalized_load_nm
        count = system.blade_count
        collective_hinge_aero = count * q_theta
        aero_power = q_phi * speed + collective_hinge_aero * rate
        if not math.isfinite(collective_hinge_aero) or not math.isfinite(aero_power):
            raise Cmm2TransientFailure("CMM-2 aerodynamic power is not finite.")
        centrifugal = -mass.c_kg_m2 * speed**2 * math.sin(angle)
        shaft_gyro = (
            count
            * mass.c_kg_m2
            * math.sin(angle)
            * (2.0 * speed * rate + rate**2)
        )
        hinge_one = hinge_torque + q_theta + spring + damping + friction + centrifugal
        rhs_shaft = motor_torque + q_phi + shaft_gyro
        rhs_hinge = count * hinge_one
        omega_dot = (
            rhs_shaft - (mass.m01 / mass.m11) * rhs_hinge
        ) / mass.schur_kg_m2
        theta_ddot = (rhs_hinge - mass.m01 * omega_dot) / mass.m11
    except Cmm2TransientFailure:
        raise
    except (CoupledDomainExit, CoupledTransientFailure, CoupledTransientError) as exc:
        _raise_translated(exc)
        raise AssertionError("translated CMM-1 failure") from exc
    except (ArithmeticError, OverflowError, ZeroDivisionError) as exc:
        raise Cmm2TransientFailure("CMM-2 coupled acceleration overflowed.") from exc
    values = (
        hinge_one,
        collective_hinge_aero,
        rhs_shaft,
        rhs_hinge,
        aero_power,
        omega_dot,
        theta_ddot,
        spring,
        damping,
        friction,
        centrifugal,
        shaft_gyro,
    )
    if not all(math.isfinite(value) for value in values):
        raise Cmm2TransientFailure("CMM-2 coupled acceleration is not finite.")
    try:
        residual_shaft = mass.m00 * omega_dot + mass.m01 * theta_ddot - rhs_shaft
        residual_hinge = mass.m01 * omega_dot + mass.m11 * theta_ddot - rhs_hinge
        _row_backward_error(
            residual_shaft, rhs_shaft, (mass.m00 * omega_dot, mass.m01 * theta_ddot)
        )
        _row_backward_error(
            residual_hinge, rhs_hinge, (mass.m01 * omega_dot, mass.m11 * theta_ddot)
        )
        residual = math.hypot(residual_shaft, residual_hinge)
    except (CoupledDomainExit, CoupledTransientFailure, CoupledTransientError) as exc:
        _raise_translated(exc)
        raise AssertionError("translated CMM-1 failure") from exc
    except (ArithmeticError, OverflowError) as exc:
        raise Cmm2TransientFailure("CMM-2 mass-matrix residual is not finite.") from exc
    if not math.isfinite(residual):
        raise Cmm2TransientFailure("CMM-2 mass-matrix residual is not finite.")
    return Cmm2CoupledAcceleration(
        omega_dot_rad_s2=omega_dot,
        theta_ddot_rad_s2=theta_ddot,
        rhs_shaft_nm=rhs_shaft,
        rhs_hinge_nm=rhs_hinge,
        motor_torque_nm=motor_torque,
        aero_shaft_generalized_load_nm=q_phi,
        aero_one_tip_hinge_generalized_load_nm=q_theta,
        aero_collective_hinge_generalized_load_nm=collective_hinge_aero,
        aero_generalized_power_w=aero_power,
        collective_hinge_actuation_nm=count * hinge_torque,
        collective_spring_nm=count * spring,
        collective_damping_nm=count * damping,
        collective_friction_nm=count * friction,
        spring_nm=spring,
        damping_nm=damping,
        friction_nm=friction,
        centrifugal_torque_nm=centrifugal,
        shaft_gyro_nm=shaft_gyro,
        mass_schur=mass.schur_kg_m2,
        mass_residual=residual,
    )


def cmm2_instantaneous_power_w(
    acceleration: Cmm2CoupledAcceleration,
    theta_dot: float,
    omega: float,
) -> float:
    """Mechanical power identity. Spring storage and gyroscopic power are absent."""
    if not isinstance(acceleration, Cmm2CoupledAcceleration):
        raise Cmm2TransientError("acceleration must be a CMM-2 acceleration.")
    rate = _finite_error("theta_dot", theta_dot)
    speed = _finite_error("omega", omega)
    try:
        power = (
            acceleration.motor_torque_nm * speed
            + acceleration.aero_shaft_generalized_load_nm * speed
            + acceleration.aero_collective_hinge_generalized_load_nm * rate
            + acceleration.collective_hinge_actuation_nm * rate
            + acceleration.collective_damping_nm * rate
            + acceleration.collective_friction_nm * rate
        )
    except (ArithmeticError, OverflowError) as exc:
        raise Cmm2TransientFailure("CMM-2 power identity is not finite.") from exc
    if not math.isfinite(power):
        raise Cmm2TransientFailure("CMM-2 power identity is not finite.")
    return power


def solve_cmm2_transient(request: Cmm2TransientRequest) -> Cmm2TransientResult:
    """Integrate analytic paired loads until duration or first contact."""
    if not isinstance(request, Cmm2TransientRequest):
        raise Cmm2TransientError("Expected a validated CMM-2 transient request.")
    system = request.system
    controls = request.controls
    origin = request.actuation.time_s[0]
    knots = tuple(value - origin for value in request.actuation.time_s)
    contact_controls = _ContactControls(
        controls.angle_atol_rad,
        controls.hinge_velocity_atol_rad_s,
    )
    rows: list[Cmm2Sample] = []
    boundaries: list[float] = []
    evaluations = 0
    aero_evaluations = 0
    state = (
        request.initial_angle_rad,
        request.initial_angular_velocity_rad_s,
        request.initial_omega_rad_s,
    )
    contact: Cmm2StopContact | None = None

    def evaluate(time_rel: float, y, index: int):
        nonlocal evaluations, aero_evaluations
        evaluations += 1
        if evaluations > controls.max_rhs_evaluations:
            raise Cmm2TransientFailure("CMM-2 work budget exhausted.")
        theta, theta_dot, omega = _state(y)
        if abs(theta - system.deployed_angle_rad) >= FOLD_LIMIT_RAD:
            raise Cmm2DomainExit(
                "CMM-2 fold domain was left; paired aerodynamic loads are not replaced."
            )
        if omega < OMEGA_MIN:
            raise Cmm2DomainExit(
                "CMM-2 shaft-speed domain was left; no zero-speed startup is used."
            )
        absolute = origin + time_rel
        current = (theta, theta_dot, omega)
        motor = _call_motor(request.motor_evaluator, absolute, current)
        aero = _call_aero(request.aero_evaluator, absolute, current)
        aero_evaluations += 1
        try:
            hinge = _interpolate(request.actuation, knots, time_rel, index)
        except (CoupledDomainExit, CoupledTransientFailure, CoupledTransientError) as exc:
            _raise_translated(exc)
        solved = cmm2_coupled_accelerations(
            system,
            theta,
            theta_dot,
            omega,
            motor.torque_nm,
            aero,
            hinge,
        )
        return solved, motor, aero, hinge

    def record(time_rel: float, y, index: int) -> None:
        if len(rows) >= controls.max_samples:
            raise Cmm2TransientFailure("CMM-2 sample budget exhausted.")
        theta, theta_dot, omega = _state(y)
        solved, _motor, aero, hinge = evaluate(time_rel, (theta, theta_dot, omega), index)
        try:
            kinetic, spring_energy, total = mechanical_energy(system, theta, theta_dot, omega)
        except (CoupledDomainExit, CoupledTransientFailure, CoupledTransientError) as exc:
            _raise_translated(exc)
            raise AssertionError("translated CMM-1 failure") from exc
        motor_power = solved.motor_torque_nm * omega
        actuation_power = solved.collective_hinge_actuation_nm * theta_dot
        damping_power = solved.collective_damping_nm * theta_dot
        friction_power = solved.collective_friction_nm * theta_dot
        identity = (
            motor_power
            + solved.aero_generalized_power_w
            + actuation_power
            + damping_power
            + friction_power
        )
        if rows:
            step = time_rel - (rows[-1].time_s - origin)
            cumulative = rows[-1].cumulative_work_j + 0.5 * (
                rows[-1].power_identity_w + identity
            ) * step
            residual = total - rows[0].mechanical_energy_j - cumulative
        else:
            cumulative = 0.0
            residual = 0.0
        rows.append(
            Cmm2Sample(
                time_s=_finite_failure("time", origin + time_rel),
                theta_rad=theta,
                theta_dot_rad_s=theta_dot,
                theta_ddot_rad_s2=solved.theta_ddot_rad_s2,
                omega_rad_s=omega,
                omega_dot_rad_s2=solved.omega_dot_rad_s2,
                rpm=_finite_failure("rpm", omega * 30.0 / math.pi),
                motor_torque_nm=solved.motor_torque_nm,
                aero_shaft_generalized_load_nm=solved.aero_shaft_generalized_load_nm,
                aero_one_tip_hinge_generalized_load_nm=solved.aero_one_tip_hinge_generalized_load_nm,
                aero_collective_hinge_generalized_load_nm=solved.aero_collective_hinge_generalized_load_nm,
                aero_generalized_power_w=solved.aero_generalized_power_w,
                aero_thrust_n=aero.thrust_n,
                aero_load_mapping_model=aero.load_mapping_model,
                aero_load_qualification=aero.qualification,
                aero_projection_model=aero.projection_model,
                aero_hinge_rate_model=aero.hinge_rate_aerodynamic_model,
                aero_source_id=aero.source_id,
                hinge_actuation_nm=hinge,
                collective_hinge_actuation_nm=solved.collective_hinge_actuation_nm,
                spring_torque_nm=solved.spring_nm,
                damping_torque_nm=solved.damping_nm,
                dry_friction_torque_nm=solved.friction_nm,
                centrifugal_torque_nm=solved.centrifugal_torque_nm,
                shaft_gyro_nm=solved.shaft_gyro_nm,
                mass_schur=solved.mass_schur,
                mass_residual=solved.mass_residual,
                kinetic_energy_j=kinetic,
                spring_energy_j=spring_energy,
                mechanical_energy_j=total,
                motor_shaft_power_w=_finite_failure("motor shaft power", motor_power),
                hinge_actuation_power_w=_finite_failure("actuation power", actuation_power),
                damping_power_w=_finite_failure("damping power", damping_power),
                dry_friction_power_w=_finite_failure("friction power", friction_power),
                power_identity_w=_finite_failure("power identity", identity),
                cumulative_work_j=_finite_failure("cumulative work", cumulative),
                energy_residual_j=_finite_failure("energy residual", residual),
            )
        )

    record(knots[0], state, 0)
    for index, (start, end) in enumerate(zip(knots, knots[1:])):
        boundaries.append(origin + start)
        if contact is not None:
            break

        def rhs(time_rel: float, y, segment=index):
            solved, _motor, _aero, _hinge = evaluate(time_rel, y, segment)
            return (y[1], solved.theta_ddot_rad_s2, solved.omega_dot_rad_s2)

        try:
            solver = RK45(
                rhs,
                start,
                state,
                end,
                max_step=controls.max_step_s,
                rtol=controls.rtol,
                atol=(
                    controls.angle_atol_rad,
                    controls.hinge_velocity_atol_rad_s,
                    controls.shaft_speed_atol_rad_s,
                ),
            )
            while solver.status == "running":
                previous_time = float(solver.t)
                previous_state = _state(solver.y)
                solver.step()
                if solver.status == "failed":
                    raise Cmm2TransientFailure("CMM-2 integration failed.")
                current_time = float(solver.t)
                current_state = _state(solver.y)
                if current_time <= previous_time:
                    raise Cmm2TransientFailure("CMM-2 integrator stalled.")
                dense = solver.dense_output()
                hit = _first_contact(
                    dense,
                    previous_time,
                    current_time,
                    previous_state,
                    current_state,
                    system.parameters,
                    contact_controls,
                )
                if hit:
                    _audit_dense_model_domain(dense, previous_time, hit[1])
                else:
                    _audit_dense_model_domain(dense, previous_time, current_time)
                if hit:
                    name, event_time, event_state = hit
                    event_omega = _finite_failure("contact shaft speed", dense(event_time)[2])
                    if event_omega < OMEGA_MIN or abs(event_state[0]) >= FOLD_LIMIT_RAD:
                        raise Cmm2DomainExit(
                            "Contact reconstruction left the CMM-2 model domain."
                        )
                    record(event_time, (event_state[0], event_state[1], event_omega), index)
                    contact = Cmm2StopContact(
                        name,
                        rows[-1].time_s,
                        event_state[0],
                        event_state[1],
                        event_omega,
                    )
                    break
                record(current_time, current_state, index)
        except (Cmm2TransientFailure, Cmm2TransientError):
            raise
        except (CoupledDomainExit, CoupledTransientFailure, CoupledTransientError) as exc:
            _raise_translated(exc)
        except (ArithmeticError, ValueError, RuntimeError) as exc:
            raise Cmm2TransientFailure("CMM-2 integration failed numerically.") from exc
        state = (
            rows[-1].theta_rad,
            rows[-1].theta_dot_rad_s,
            rows[-1].omega_rad_s,
        )
        if contact is not None:
            break
    else:
        boundaries.append(request.actuation.time_s[-1])

    status = "first_contact_terminal" if contact is not None else "completed"
    return Cmm2TransientResult(
        status=status,
        model_class=MODEL_CLASS,
        implementation_id=IMPLEMENTATION_ID,
        physical_qualification=False,
        full_propeller_clearance=None,
        surface_path_clearance=None,
        interblade_clearance=None,
        aero_load_status=AERO_LOAD_STATUS,
        samples=tuple(rows),
        segment_boundary_times_s=tuple(boundaries),
        contact=contact,
        rhs_evaluations=evaluations,
        aero_evaluations=aero_evaluations,
        limitations=CMM2_LIMITATIONS,
    )
