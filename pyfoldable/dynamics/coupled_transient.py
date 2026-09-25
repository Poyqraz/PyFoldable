"""CMM-1 partial coupled aero–motor–mechanism screening transient.

The shaft speed and one shared hinge angle are dynamic states. Aerodynamic
hinge torque is omitted from the model. The result is not physical
qualification, clearance promotion, calibration, or a replacement for PY-05.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Mapping

import numpy as np
from scipy.integrate import RK45

from pyfoldable.dynamics.mechanism_contracts import ContactPolicy, DryFriction
from pyfoldable.dynamics.mechanism_transient import (
    MechanismParameters,
    _first_contact,
)


MODEL_CLASS = "partial_coupled_screening_only"
AERO_HINGE_STATUS = "unavailable_omitted_by_cmm1"
RPM_MIN = 100.0
OMEGA_MIN = RPM_MIN * 2.0 * math.pi / 60.0
FOLD_LIMIT_RAD = 0.5 * math.pi
_RESIDUAL_REL = 1.0e-8
_RESIDUAL_ROUND_ULPS = 64
_PIVOT_RESOLUTION_ULPS = 32
CMM1_LIMITATIONS = (
    "PR-06C physical aerodynamic gate is unresolved.",
    "Aerodynamic hinge load is omitted from the CMM-1 model.",
    "Airflow caused by hinge rate is not modeled.",
    "Fold projection is radial_cosine_v1.",
    "Fold is limited to less than 90 degrees from deployed.",
    "Zero-speed startup is outside the model domain.",
    "Blades are identical and synchronous.",
    "No impact, latch, or static holding is modeled.",
    "Dynamic motion is not clearance qualification.",
    "Rotating inertia and mechanical parameters are unqualified unless separately measured.",
)


class CoupledTransientError(ValueError):
    """The coupled request is not a valid CMM-1 problem."""


class CoupledTransientFailure(RuntimeError):
    """A hard failure. No successful shortened trajectory is returned."""


class CoupledDomainExit(CoupledTransientFailure):
    """The state left the CMM-1 model domain and was not continued."""


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CoupledTransientError(f"{name} must be a finite scalar.")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise CoupledTransientError(f"{name} must be a finite scalar.") from exc
    if not math.isfinite(result):
        raise CoupledTransientError(f"{name} must be a finite scalar.")
    return result


def _number(name: str, value: object) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise CoupledTransientFailure(f"CMM-1 {name} is not representable.") from exc
    if not math.isfinite(result):
        raise CoupledTransientFailure(f"CMM-1 {name} is not finite.")
    return result


def _source(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise CoupledTransientError(f"{name} must be a nonempty bounded string.")
    return value


@dataclass(frozen=True)
class BaseRotatingAssemblyInertia:
    """+z inertia of shaft-locked hardware, excluding every modeled movable tip."""

    inertia_kg_m2: float
    source: str
    component_inventory: tuple[str, ...]
    excludes_modeled_movable_tips: bool = True

    def __post_init__(self) -> None:
        inertia = _finite("inertia_kg_m2", self.inertia_kg_m2)
        _source("base rotating inertia source", self.source)
        if inertia <= 0.0:
            raise CoupledTransientError("Base rotating inertia must be strictly positive.")
        if self.excludes_modeled_movable_tips is not True:
            raise CoupledTransientError(
                "I0 must exclude every modeled movable tip; the exclusion flag cannot be false."
            )
        if (
            not isinstance(self.component_inventory, tuple)
            or not 1 <= len(self.component_inventory) <= 32
        ):
            raise CoupledTransientError(
                "Component inventory must be a nonempty immutable tuple of at most 32 names."
            )
        for item in self.component_inventory:
            if not isinstance(item, str) or not item.strip() or len(item) > 200:
                raise CoupledTransientError(
                    "Each inventory component must be a nonempty bounded string."
                )


@dataclass(frozen=True)
class HingeActuationHistory:
    """Piecewise-linear hinge torque. Shaft speed is not an input."""

    time_s: tuple[float, ...]
    torque_nm: tuple[float, ...]
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.time_s, tuple) or not isinstance(self.torque_nm, tuple):
            raise CoupledTransientError("Hinge actuation histories must be immutable tuples.")
        if len(self.time_s) < 2 or len(self.time_s) != len(self.torque_nm):
            raise CoupledTransientError(
                "Hinge actuation requires equal-length time and torque knots, at least two."
            )
        for value in self.time_s:
            _finite("actuation time", value)
        for value in self.torque_nm:
            _finite("actuation torque", value)
        _source("hinge actuation source", self.source)
        if self.time_s[0] < 0.0 or any(
            later <= earlier for earlier, later in zip(self.time_s, self.time_s[1:])
        ):
            raise CoupledTransientError(
                "Actuation knot times must be nonnegative and strictly increasing."
            )


@dataclass(frozen=True)
class CoupledSolverControls:
    """Software work ceilings for one CMM-1 run. They are not accuracy claims."""

    rtol: float = 1.0e-6
    angle_atol_rad: float = 1.0e-8
    hinge_velocity_atol_rad_s: float = 1.0e-8
    shaft_speed_atol_rad_s: float = 1.0e-6
    max_step_s: float = 0.002
    max_duration_s: float = 2.0
    max_samples: int = 5000
    max_rhs_evaluations: int = 12000
    max_input_knots: int = 256

    def __post_init__(self) -> None:
        for name in (
            "rtol",
            "angle_atol_rad",
            "hinge_velocity_atol_rad_s",
            "shaft_speed_atol_rad_s",
            "max_step_s",
            "max_duration_s",
        ):
            _finite(name, getattr(self, name))
        if not 0.0 < self.rtol <= 1.0e-3:
            raise CoupledTransientError("rtol is outside the CMM-1 solver budget.")
        if not 0.0 < self.angle_atol_rad <= 1.0e-4:
            raise CoupledTransientError("angle atol is outside the CMM-1 solver budget.")
        if not 0.0 < self.hinge_velocity_atol_rad_s <= 1.0e-3:
            raise CoupledTransientError("hinge-velocity atol is outside the CMM-1 solver budget.")
        if not 0.0 < self.shaft_speed_atol_rad_s <= 1.0e-2:
            raise CoupledTransientError("shaft-speed atol is outside the CMM-1 solver budget.")
        if not 0.0 < self.max_step_s <= 0.002:
            raise CoupledTransientError("max_step_s must be in (0, 0.002].")
        if not 0.0 < self.max_duration_s <= 2.0:
            raise CoupledTransientError("max_duration_s must be in (0, 2].")
        for name, value, upper in (
            ("max_samples", self.max_samples, 5000),
            ("max_rhs_evaluations", self.max_rhs_evaluations, 12000),
            ("max_input_knots", self.max_input_knots, 256),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= upper:
                raise CoupledTransientError(f"{name} exceeds the CMM-1 ceiling.")
        if self.max_input_knots < 2 or self.max_samples < 2:
            raise CoupledTransientError("Sample and knot budgets must allow a bounded segment.")


@dataclass(frozen=True)
class MotorEvaluation:
    """Algebraic motor sample. Current is not an ODE state."""

    torque_nm: float
    applied_voltage_v: float | None = None
    back_emf_v: float | None = None
    current_a: float | None = None
    electrical_power_w: float | None = None
    shaft_power_w: float | None = None
    winding_loss_w: float | None = None
    line_loss_w: float | None = None
    voltage_residual_v: float | None = None

    def __post_init__(self) -> None:
        _number("motor torque", self.torque_nm)
        for name in (
            "applied_voltage_v",
            "back_emf_v",
            "current_a",
            "electrical_power_w",
            "shaft_power_w",
            "winding_loss_w",
            "line_loss_w",
            "voltage_residual_v",
        ):
            value = getattr(self, name)
            if value is not None:
                _number(name, value)


@dataclass(frozen=True)
class AeroEvaluation:
    """Whole-rotor shaft load. This is not a hinge moment."""

    shaft_torque_nm: float
    thrust_n: float
    source_id: str
    qualification: str
    projection_model: str = "analytic_shaft_load"

    def __post_init__(self) -> None:
        _number("aero shaft torque", self.shaft_torque_nm)
        _number("aero thrust", self.thrust_n)
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise CoupledTransientFailure("Aerodynamic source id must be nonempty.")
        if not isinstance(self.qualification, str) or not self.qualification.strip():
            raise CoupledTransientFailure("Aerodynamic qualification must be nonempty.")
        if not isinstance(self.projection_model, str) or not self.projection_model.strip():
            raise CoupledTransientFailure("Projection model must be nonempty.")


@dataclass(frozen=True)
class CoupledSystem:
    """N identical synchronous tips plus sourced base inertia."""

    parameters: MechanismParameters
    blade_count: int
    base_inertia: BaseRotatingAssemblyInertia
    deployed_angle_rad: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.parameters, MechanismParameters):
            raise CoupledTransientError("parameters must be MechanismParameters.")
        if not isinstance(self.base_inertia, BaseRotatingAssemblyInertia):
            raise CoupledTransientError("base_inertia must be BaseRotatingAssemblyInertia.")
        if (
            isinstance(self.blade_count, bool)
            or not isinstance(self.blade_count, int)
            or not 1 <= self.blade_count <= 32
        ):
            raise CoupledTransientError("blade_count must be an integer from 1 to 32.")
        if self.parameters.hinge_radius_m <= 0.0:
            raise CoupledTransientError("CMM-1 requires a positive hinge radius.")
        deployed = _finite("deployed_angle_rad", self.deployed_angle_rad)
        if not math.isclose(deployed, 0.0, rel_tol=0.0, abs_tol=1.0e-15):
            raise CoupledTransientError("CMM-1 v1 requires the deployed angle to be zero.")


@dataclass(frozen=True)
class CoupledTransientRequest:
    """One bounded synchronous screening integration."""

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
            raise CoupledTransientError("system must be a CoupledSystem.")
        if not isinstance(self.actuation, HingeActuationHistory):
            raise CoupledTransientError("actuation must be a HingeActuationHistory.")
        if not isinstance(self.controls, CoupledSolverControls):
            raise CoupledTransientError("controls must be CoupledSolverControls.")
        if not isinstance(self.contact_policy, ContactPolicy):
            raise CoupledTransientError("contact_policy must be ContactPolicy.")
        if not callable(self.motor_evaluator) or not callable(self.aero_evaluator):
            raise CoupledTransientError("Motor and aerodynamic evaluators must be callable.")
        theta = _finite("initial_angle_rad", self.initial_angle_rad)
        _finite("initial_angular_velocity_rad_s", self.initial_angular_velocity_rad_s)
        omega = _finite("initial_omega_rad_s", self.initial_omega_rad_s)
        parameters = self.system.parameters
        if not parameters.lower_stop_rad < theta < parameters.upper_stop_rad:
            raise CoupledTransientError("Initial angle must lie strictly inside both stops.")
        if abs(theta - self.system.deployed_angle_rad) >= FOLD_LIMIT_RAD:
            raise CoupledTransientError(
                "Initial angle must lie strictly inside the foldable BEM domain."
            )
        if omega < OMEGA_MIN:
            raise CoupledTransientError(
                "Initial shaft speed must be at least the CMM-1 minimum of 100 rpm."
            )
        controls = self.controls
        if len(self.actuation.time_s) > controls.max_input_knots:
            raise CoupledTransientError("Actuation knots exceed the CMM-1 ceiling.")
        duration = self.actuation.time_s[-1] - self.actuation.time_s[0]
        if duration <= 0.0 or duration > controls.max_duration_s:
            raise CoupledTransientError("Actuation duration exceeds the CMM-1 ceiling.")
        minimum_samples = 1 + sum(
            math.ceil((later - earlier) / controls.max_step_s)
            for earlier, later in zip(self.actuation.time_s, self.actuation.time_s[1:])
        )
        if minimum_samples > controls.max_samples:
            raise CoupledTransientError("Actuation history exceeds the sample budget preflight.")


@dataclass(frozen=True)
class CoupledMassMatrix:
    """Symmetric 2x2 inertia operator and its positive Schur complement."""

    a_kg_m2: float
    b_kg_m2: float
    c_kg_m2: float
    m00: float
    m01: float
    m11: float
    determinant: float
    schur_kg_m2: float
    analytical_schur_kg_m2: float
    represented_pivot: float


@dataclass(frozen=True)
class HingeTerms:
    """One-tip hinge terms after dividing the collective row by N."""

    applied_nm: float
    spring_nm: float
    damping_nm: float
    friction_nm: float
    centrifugal_nm: float
    euler_nm: float
    theta_ddot_rad_s2: float


@dataclass(frozen=True)
class CoupledAcceleration:
    """Solved shaft and hinge accelerations for one state."""

    omega_dot_rad_s2: float
    theta_ddot_rad_s2: float
    mass_schur: float
    mass_residual: float
    rhs_shaft_nm: float
    rhs_hinge_nm: float
    motor_torque_nm: float
    aero_shaft_torque_nm: float
    parameters_c_kg_m2: float
    collective_spring_nm: float
    collective_damping_nm: float
    collective_friction_nm: float
    friction_nm: float
    collective_actuation_nm: float
    terms: HingeTerms


@dataclass(frozen=True)
class CoupledStopContact:
    stop: str
    time_s: float
    angle_rad: float
    preimpact_angular_velocity_rad_s: float
    omega_rad_s: float


@dataclass(frozen=True)
class CoupledSample:
    time_s: float
    theta_rad: float
    theta_dot_rad_s: float
    theta_ddot_rad_s2: float
    omega_rad_s: float
    omega_dot_rad_s2: float
    rpm: float
    motor_torque_nm: float
    applied_voltage_v: float | None
    back_emf_v: float | None
    current_a: float | None
    electrical_power_w: float | None
    motor_shaft_power_w: float
    winding_loss_w: float | None
    line_loss_w: float | None
    voltage_residual_v: float | None
    bem_thrust_n: float
    bem_shaft_torque_nm: float
    bem_shaft_power_w: float
    bem_source_id: str
    bem_qualification: str
    projection_model: str
    hinge_actuation_nm: float
    collective_hinge_actuation_nm: float
    spring_torque_nm: float
    damping_torque_nm: float
    dry_friction_torque_nm: float
    centrifugal_torque_nm: float
    euler_torque_nm: float
    shaft_gyro_nm: float
    aerodynamic_hinge_torque_status: str
    mass_schur: float
    mass_residual: float
    kinetic_energy_j: float
    spring_energy_j: float
    mechanical_energy_j: float
    hinge_actuation_power_w: float
    damping_power_w: float
    dry_friction_power_w: float
    power_identity_w: float
    cumulative_work_j: float
    energy_residual_j: float

    def __post_init__(self) -> None:
        if self.aerodynamic_hinge_torque_status != AERO_HINGE_STATUS:
            raise CoupledTransientError("Aerodynamic hinge torque must stay omitted by CMM-1.")
        for name, value in self.__dict__.items():
            if name in {
                "bem_source_id",
                "bem_qualification",
                "projection_model",
                "aerodynamic_hinge_torque_status",
            }:
                continue
            if value is None:
                continue
            _number(name, value)

    def as_mapping(self) -> dict[str, object]:
        return {
            name: value
            for name, value in self.__dict__.items()
            if name != "aerodynamic_hinge_torque_nm"
        }


@dataclass(frozen=True)
class CoupledTransientResult:
    status: str
    model_class: str
    physical_qualification: bool
    aerodynamic_hinge_torque_status: str
    full_propeller_clearance: None
    surface_path_clearance: None
    interblade_clearance: None
    samples: tuple[CoupledSample, ...]
    segment_boundary_times_s: tuple[float, ...]
    contact: CoupledStopContact | None
    rhs_evaluations: int
    bem_evaluations: int
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.model_class != MODEL_CLASS or self.physical_qualification is not False:
            raise CoupledTransientError("CMM-1 cannot claim a qualified or other model class.")
        if self.aerodynamic_hinge_torque_status != AERO_HINGE_STATUS:
            raise CoupledTransientError("Aerodynamic hinge status must be unavailable_omitted_by_cmm1.")
        if (
            self.full_propeller_clearance is not None
            or self.surface_path_clearance is not None
            or self.interblade_clearance is not None
        ):
            raise CoupledTransientError("CMM-1 cannot assign a GEOM clearance value.")
        if self.status not in {"completed", "first_contact_terminal"}:
            raise CoupledTransientError("Unknown CMM-1 termination status.")
        if not isinstance(self.samples, tuple) or not self.samples:
            raise CoupledTransientError("CMM-1 requires at least the initial sample.")


@dataclass(frozen=True)
class _ContactControls:
    atol: float
    atol_angular_velocity_rad_s: float


def _tip_c(parameters: MechanismParameters) -> float:
    try:
        coupling = parameters.mass_kg * parameters.hinge_radius_m * parameters.cg_distance_m
    except (ArithmeticError, OverflowError) as exc:
        raise CoupledTransientFailure("Tip coupling C overflowed.") from exc
    return _number("tip coupling", coupling)


def _friction_nm(parameters: MechanismParameters, theta_dot: float) -> float:
    friction = parameters.dry_friction
    if not isinstance(friction, DryFriction):
        raise CoupledTransientError("dry friction contract is invalid.")
    if friction.mode == "none":
        return 0.0
    try:
        value = -friction.coulomb_torque_nm * math.tanh(
            theta_dot / friction.transition_velocity_rad_s
        )
    except (ArithmeticError, OverflowError, ZeroDivisionError) as exc:
        raise CoupledTransientFailure("Friction evaluation overflowed.") from exc
    return _number("friction", value)


def _represented_factor(m00: float, m01: float, m11: float) -> tuple[float, float]:
    """Scale-aware Schur pivot of the represented symmetric matrix.

    The analytical determinant is not used. A mathematically positive matrix
    that is not distinguishable from singular in floating point fails closed.
    """
    if not all(math.isfinite(value) for value in (m00, m01, m11)):
        raise CoupledTransientFailure("Mass matrix is not finite.")
    if m00 <= 0.0 or m11 <= 0.0:
        raise CoupledTransientFailure("Mass matrix is singular or unresolved.")
    try:
        scale_0 = math.sqrt(m00)
        scale_1 = math.sqrt(m11)
        coupling = m01 / (scale_0 * scale_1)
        product = coupling * coupling
        pivot = 1.0 - product
        schur = pivot * m00
    except (ArithmeticError, OverflowError, ZeroDivisionError) as exc:
        raise CoupledTransientFailure("Mass-matrix scaling overflowed.") from exc
    if not all(math.isfinite(value) for value in (coupling, product, pivot, schur)):
        raise CoupledTransientFailure("Mass matrix is not finite.")
    resolution = _PIVOT_RESOLUTION_ULPS * math.ulp(max(1.0, abs(product)))
    if pivot <= resolution or schur <= 0.0:
        raise CoupledTransientFailure("Represented mass matrix is numerically unresolved.")
    return schur, pivot


def _row_backward_error(residual: float, rhs: float, products: tuple[float, ...]) -> float:
    """Relative residual against |b| + sum |M x|, with a zero-denominator rule."""
    if not all(math.isfinite(value) for value in (residual, rhs, *products)):
        raise CoupledTransientFailure("Mass-matrix residual is not finite.")
    magnitude = abs(rhs)
    for product in products:
        magnitude += abs(product)
    if not math.isfinite(magnitude):
        raise CoupledTransientFailure("Mass-matrix residual scale overflowed.")
    if magnitude == 0.0:
        if residual != 0.0:
            raise CoupledTransientFailure(
                "Mass-matrix residual exceeds the backward-error tolerance."
            )
        return 0.0
    relative = abs(residual) / magnitude
    roundoff = _RESIDUAL_ROUND_ULPS * math.ulp(magnitude) / magnitude
    if relative > max(_RESIDUAL_REL, roundoff):
        raise CoupledTransientFailure(
            "Mass-matrix residual exceeds the backward-error tolerance."
        )
    return relative


def coupled_mass_matrix(system: CoupledSystem, theta_rad: float) -> CoupledMassMatrix:
    """Return M(theta), the analytical determinant, and the represented pivot."""
    if not isinstance(system, CoupledSystem):
        raise CoupledTransientError("system must be a CoupledSystem.")
    theta = _finite("theta_rad", theta_rad)
    parameters = system.parameters
    count = system.blade_count
    coupling = _tip_c(parameters)
    try:
        cosine = math.cos(theta)
        inertia = parameters.hinge_inertia_kg_m2
        radial = parameters.mass_kg * parameters.hinge_radius_m**2
        one_a = inertia + radial + 2.0 * coupling * cosine
        one_b = inertia + coupling * cosine
        gap = inertia - parameters.mass_kg * parameters.cg_distance_m**2 * cosine**2
        determinant = (
            count * inertia * system.base_inertia.inertia_kg_m2
            + (count**2) * parameters.mass_kg * parameters.hinge_radius_m**2 * gap
        )
        m00 = system.base_inertia.inertia_kg_m2 + count * one_a
        m01 = count * one_b
        m11 = count * inertia
        analytical_schur = determinant / m11
    except (ArithmeticError, OverflowError, ZeroDivisionError) as exc:
        raise CoupledTransientFailure("Mass-matrix evaluation overflowed.") from exc
    values = (one_a, one_b, coupling, m00, m01, m11, determinant, analytical_schur)
    if not all(math.isfinite(value) for value in values):
        raise CoupledTransientFailure("Mass matrix is not finite.")
    schur, pivot = _represented_factor(m00, m01, m11)
    return CoupledMassMatrix(
        one_a,
        one_b,
        coupling,
        m00,
        m01,
        m11,
        determinant,
        schur,
        analytical_schur,
        pivot,
    )


def prescribed_shaft_hinge_acceleration(
    parameters: MechanismParameters,
    theta_rad: float,
    theta_dot_rad_s: float,
    omega_rad_s: float,
    omega_dot_rad_s2: float,
    hinge_torque_nm: float,
) -> HingeTerms:
    """Hinge row with prescribed shaft motion, divided back to one tip."""
    if not isinstance(parameters, MechanismParameters):
        raise CoupledTransientError("parameters must be MechanismParameters.")
    theta = _finite("theta_rad", theta_rad)
    theta_dot = _finite("theta_dot_rad_s", theta_dot_rad_s)
    omega = _finite("omega_rad_s", omega_rad_s)
    omega_dot = _finite("omega_dot_rad_s2", omega_dot_rad_s2)
    applied = _finite("hinge_torque_nm", hinge_torque_nm)
    coupling = _tip_c(parameters)
    try:
        spring = -parameters.spring_stiffness_nm_rad * (theta - parameters.rest_angle_rad)
        damping = -parameters.viscous_damping_nm_s_rad * theta_dot
        friction = _friction_nm(parameters, theta_dot)
        centrifugal = -coupling * omega**2 * math.sin(theta)
        euler = -(
            parameters.hinge_inertia_kg_m2 + coupling * math.cos(theta)
        ) * omega_dot
        acceleration = (
            applied + spring + damping + friction + centrifugal + euler
        ) / parameters.hinge_inertia_kg_m2
    except (ArithmeticError, OverflowError, ZeroDivisionError) as exc:
        raise CoupledTransientFailure("Prescribed hinge evaluation overflowed.") from exc
    terms = (
        applied,
        spring,
        damping,
        friction,
        centrifugal,
        euler,
        acceleration,
    )
    if not all(math.isfinite(value) for value in terms):
        raise CoupledTransientFailure("Prescribed hinge acceleration is not finite.")
    return HingeTerms(*terms)


def coupled_accelerations(
    system: CoupledSystem,
    theta: float,
    theta_dot: float,
    omega: float,
    motor_torque_nm: float,
    aero_shaft_torque_nm: float,
    hinge_torque_nm: float,
) -> CoupledAcceleration:
    """Solve the 2x2 symmetric system without evaluating BEM or a motor model."""
    angle = _finite("theta", theta)
    rate = _finite("theta_dot", theta_dot)
    speed = _finite("omega", omega)
    motor_torque = _finite("motor_torque_nm", motor_torque_nm)
    aero_torque = _finite("aero_shaft_torque_nm", aero_shaft_torque_nm)
    hinge_torque = _finite("hinge_torque_nm", hinge_torque_nm)
    mass = coupled_mass_matrix(system, angle)
    parameters = system.parameters
    try:
        spring = -parameters.spring_stiffness_nm_rad * (angle - parameters.rest_angle_rad)
        damping = -parameters.viscous_damping_nm_s_rad * rate
        friction = _friction_nm(parameters, rate)
        centrifugal = -mass.c_kg_m2 * speed**2 * math.sin(angle)
        hinge_one = hinge_torque + spring + damping + friction + centrifugal
        shaft_gyro = (
            system.blade_count
            * mass.c_kg_m2
            * math.sin(angle)
            * (2.0 * speed * rate + rate**2)
        )
        rhs_shaft = motor_torque - aero_torque + shaft_gyro
        rhs_hinge = system.blade_count * hinge_one
        omega_dot = (
            rhs_shaft - (mass.m01 / mass.m11) * rhs_hinge
        ) / mass.schur_kg_m2
        theta_ddot = (rhs_hinge - mass.m01 * omega_dot) / mass.m11
    except (ArithmeticError, OverflowError, ZeroDivisionError) as exc:
        raise CoupledTransientFailure("Coupled acceleration overflowed.") from exc
    if not all(math.isfinite(value) for value in (hinge_one, rhs_shaft, rhs_hinge, omega_dot, theta_ddot)):
        raise CoupledTransientFailure("Coupled acceleration is not finite.")
    residual_shaft = mass.m00 * omega_dot + mass.m01 * theta_ddot - rhs_shaft
    residual_hinge = mass.m01 * omega_dot + mass.m11 * theta_ddot - rhs_hinge
    _row_backward_error(residual_shaft, rhs_shaft, (mass.m00 * omega_dot, mass.m01 * theta_ddot))
    _row_backward_error(residual_hinge, rhs_hinge, (mass.m01 * omega_dot, mass.m11 * theta_ddot))
    residual = math.hypot(residual_shaft, residual_hinge)
    terms = prescribed_shaft_hinge_acceleration(
        parameters, angle, rate, speed, omega_dot, hinge_torque
    )
    return CoupledAcceleration(
        omega_dot_rad_s2=omega_dot,
        theta_ddot_rad_s2=theta_ddot,
        mass_schur=mass.schur_kg_m2,
        mass_residual=residual,
        rhs_shaft_nm=rhs_shaft,
        rhs_hinge_nm=rhs_hinge,
        motor_torque_nm=motor_torque,
        aero_shaft_torque_nm=aero_torque,
        parameters_c_kg_m2=mass.c_kg_m2,
        collective_spring_nm=system.blade_count * spring,
        collective_damping_nm=system.blade_count * damping,
        collective_friction_nm=system.blade_count * friction,
        friction_nm=friction,
        collective_actuation_nm=system.blade_count * hinge_torque,
        terms=terms,
    )


def mechanical_energy(
    system: CoupledSystem,
    theta: float,
    theta_dot: float,
    omega: float,
) -> tuple[float, float, float]:
    """Return kinetic energy, spring energy, and their sum."""
    angle = _finite("theta", theta)
    rate = _finite("theta_dot", theta_dot)
    speed = _finite("omega", omega)
    mass = coupled_mass_matrix(system, angle)
    try:
        kinetic = (
            0.5 * mass.m00 * speed**2
            + mass.m01 * speed * rate
            + 0.5 * mass.m11 * rate**2
        )
        spring = 0.5 * system.blade_count * system.parameters.spring_stiffness_nm_rad * (
            angle - system.parameters.rest_angle_rad
        ) ** 2
    except (ArithmeticError, OverflowError) as exc:
        raise CoupledTransientFailure("Mechanical energy overflowed.") from exc
    if not math.isfinite(kinetic) or not math.isfinite(spring):
        raise CoupledTransientFailure("Mechanical energy is not finite.")
    return kinetic, spring, kinetic + spring


def _interpolate(history: HingeActuationHistory, knots: tuple[float, ...], time_s: float, index: int) -> float:
    start, end = knots[index], knots[index + 1]
    fraction = min(1.0, max(0.0, (time_s - start) / (end - start)))
    torque = history.torque_nm[index] + fraction * (
        history.torque_nm[index + 1] - history.torque_nm[index]
    )
    return _number("hinge actuation", torque)


def _state(y) -> tuple[float, float, float]:
    theta = _number("theta", y[0])
    theta_dot = _number("theta_dot", y[1])
    omega = _number("omega", y[2])
    return theta, theta_dot, omega


def _call_evaluator(kind: str, evaluator: Callable, time_s: float, state: tuple[float, float, float], expected: type):
    try:
        value = evaluator(time_s, state[0], state[1], state[2])
    except CoupledTransientFailure:
        raise
    except (ArithmeticError, TypeError, ValueError, RuntimeError) as exc:
        raise CoupledTransientFailure(f"CMM-1 {kind} evaluator failed.") from exc
    if not isinstance(value, expected):
        raise CoupledTransientFailure(f"CMM-1 {kind} evaluator returned an unexpected type.")
    return value


_ROOT_BISECTION_LIMIT = 80
_ROOT_WORK_BUDGET = 800


def _trim_polynomial(coeffs: tuple[Fraction, ...]) -> tuple[Fraction, ...]:
    items = list(coeffs)
    while len(items) > 1 and items[-1] == 0:
        items.pop()
    return tuple(items)


def _evaluate_polynomial(coeffs: tuple[Fraction, ...], x: Fraction) -> Fraction:
    value = Fraction(0)
    for coeff in reversed(coeffs):
        value = value * x + coeff
    return value


def _differentiate(coeffs: tuple[Fraction, ...]) -> tuple[Fraction, ...]:
    derived = tuple(coeff * index for index, coeff in enumerate(coeffs) if index)
    if not derived:
        return (Fraction(0),)
    return _trim_polynomial(derived)


def _divide_polynomial(
    numerator: tuple[Fraction, ...],
    denominator: tuple[Fraction, ...],
) -> tuple[tuple[Fraction, ...], tuple[Fraction, ...]]:
    working = list(numerator)
    degree_gap = len(working) - len(denominator)
    if degree_gap < 0:
        return (Fraction(0),), _trim_polynomial(tuple(working))
    quotient = [Fraction(0)] * (degree_gap + 1)
    lead = denominator[-1]
    if lead == 0:
        raise CoupledTransientFailure("CMM-1 dense root isolation is unresolved.")
    for power in range(degree_gap, -1, -1):
        factor = working[power + len(denominator) - 1] / lead
        quotient[power] = factor
        for index, coeff in enumerate(denominator):
            working[power + index] -= factor * coeff
    return _trim_polynomial(tuple(quotient)), _trim_polynomial(tuple(working))


def _sturm_chain(polynomial: tuple[Fraction, ...]) -> tuple[tuple[Fraction, ...], ...] | None:
    polynomial = _trim_polynomial(polynomial)
    if polynomial == (Fraction(0),):
        return None
    chain = [polynomial]
    derivative = _differentiate(polynomial)
    if derivative != (Fraction(0),):
        chain.append(derivative)
    while len(chain[-1]) > 1:
        _quotient, remainder = _divide_polynomial(chain[-2], chain[-1])
        remainder = _trim_polynomial(tuple(-coeff for coeff in remainder))
        if remainder == (Fraction(0),):
            break
        chain.append(remainder)
        if len(chain) > 6:
            raise CoupledTransientFailure("CMM-1 dense root isolation is unresolved.")
    return tuple(chain)


def _sign_variations(chain: tuple[tuple[Fraction, ...], ...], x: Fraction) -> int:
    previous = 0
    changes = 0
    for polynomial in chain:
        value = _evaluate_polynomial(polynomial, x)
        if value == 0:
            continue
        sign = 1 if value > 0 else -1
        if previous and sign != previous:
            changes += 1
        previous = sign
    return changes


def _consume_root_work(budget: list[int]) -> None:
    if budget[0] <= 0:
        raise CoupledTransientFailure("CMM-1 dense root isolation is unresolved.")
    budget[0] -= 1


def _deflate_root(polynomial: tuple[Fraction, ...], root: Fraction) -> tuple[Fraction, ...]:
    """Exact synthetic division by ``(x - root)``."""
    quotient: list[Fraction] = []
    accumulator = Fraction(0)
    for coeff in reversed(polynomial):
        accumulator = accumulator * root + coeff
        quotient.append(accumulator)
    remainder = quotient.pop()
    if remainder != 0:
        raise CoupledTransientFailure("CMM-1 dense root isolation is unresolved.")
    return _trim_polynomial(tuple(reversed(quotient)))


def _remove_endpoint_roots(polynomial: tuple[Fraction, ...], root: Fraction) -> tuple[Fraction, ...]:
    while len(polynomial) > 1 and _evaluate_polynomial(polynomial, root) == 0:
        polynomial = _deflate_root(polynomial, root)
    return polynomial


def _isolate_real_roots(
    polynomial: tuple[Fraction, ...],
    left: Fraction,
    right: Fraction,
    budget: list[int],
    depth: int = 0,
) -> list[tuple[Fraction, Fraction]]:
    if depth > 32:
        raise CoupledTransientFailure("CMM-1 dense root isolation is unresolved.")
    polynomial = _remove_endpoint_roots(_trim_polynomial(polynomial), left)
    polynomial = _remove_endpoint_roots(polynomial, right)
    if len(polynomial) <= 1:
        return []
    chain = _sturm_chain(polynomial)
    if chain is None:
        return []
    count = _sign_variations(chain, left) - _sign_variations(chain, right)
    if count < 0:
        raise CoupledTransientFailure("CMM-1 dense root isolation is unresolved.")
    if count == 0:
        return []
    if right - left <= Fraction(1, 2**_ROOT_BISECTION_LIMIT) and count > 1:
        raise CoupledTransientFailure("CMM-1 dense root isolation is unresolved.")
    _consume_root_work(budget)
    middle = (left + right) / 2
    if middle == left or middle == right:
        raise CoupledTransientFailure("CMM-1 dense root isolation is unresolved.")
    if _evaluate_polynomial(polynomial, middle) == 0:
        return [
            (middle, middle),
            *_isolate_real_roots(_remove_endpoint_roots(polynomial, middle), left, right, budget, depth + 1),
        ]
    if count == 1:
        return _refine_real_root(chain, left, right, budget)
    return [
        *_isolate_real_roots(polynomial, left, middle, budget, depth + 1),
        *_isolate_real_roots(polynomial, middle, right, budget, depth + 1),
    ]


def _refine_real_root(
    chain: tuple[tuple[Fraction, ...], ...],
    left: Fraction,
    right: Fraction,
    budget: list[int],
) -> list[tuple[Fraction, Fraction]]:
    polynomial = chain[0]
    for _step in range(_ROOT_BISECTION_LIMIT):
        if right - left <= Fraction(1, 2**_ROOT_BISECTION_LIMIT):
            break
        _consume_root_work(budget)
        middle = (left + right) / 2
        if middle == left or middle == right:
            break
        if _evaluate_polynomial(polynomial, middle) == 0:
            return [(middle, middle)]
        if _sign_variations(chain, left) - _sign_variations(chain, middle) >= 1:
            right = middle
        else:
            left = middle
    return [(left, right)]


def _dense_component_value(
    origin: Fraction,
    step: Fraction,
    coefficients: tuple[Fraction, ...],
    x: Fraction,
) -> Fraction:
    accumulated = Fraction(0)
    power = x
    for coeff in coefficients:
        accumulated += coeff * power
        power *= x
    return origin + step * accumulated


def _magnitude_bound(coeffs: tuple[Fraction, ...], left: Fraction, right: Fraction) -> Fraction:
    span = max(abs(left), abs(right), Fraction(1))
    bound = Fraction(0)
    power = Fraction(1)
    for coeff in coeffs:
        bound += abs(coeff) * power
        power *= span
    return bound


def _value_enclosure(
    origin: Fraction,
    step: Fraction,
    coefficients: tuple[Fraction, ...],
    derivative: tuple[Fraction, ...],
    left: Fraction,
    right: Fraction,
) -> tuple[Fraction, Fraction]:
    if left == right:
        value = _dense_component_value(origin, step, coefficients, left)
        return value, value
    middle = (left + right) / 2
    center = _dense_component_value(origin, step, coefficients, middle)
    width = right - left
    endpoint_slope = max(
        abs(_evaluate_polynomial(derivative, left)),
        abs(_evaluate_polynomial(derivative, right)),
    )
    slope_bound = _magnitude_bound(_differentiate(derivative), left, right)
    derivative_bound = endpoint_slope + slope_bound * width
    variation = abs(step) * derivative_bound * width / 2
    return center - variation, center + variation


def _polynomial_gcd(
    left: tuple[Fraction, ...],
    right: tuple[Fraction, ...],
) -> tuple[Fraction, ...]:
    left = _trim_polynomial(left)
    right = _trim_polynomial(right)
    while right != (Fraction(0),):
        _quotient, remainder = _divide_polynomial(left, right)
        left, right = right, remainder
    return _trim_polynomial(left)


def _strict_interior_root_count(
    polynomial: tuple[Fraction, ...],
    left: Fraction,
    right: Fraction,
) -> int:
    """Count distinct real roots in the open interval ``(left, right)``.

    Exact endpoint roots are deflated before the Sturm count, so a closed
    bracket endpoint is not an interior root. There is no floating tolerance.
    """
    if left > right:
        raise CoupledTransientFailure("CMM-1 dense root isolation is unresolved.")
    if left == right:
        return 0
    polynomial = _remove_endpoint_roots(_trim_polynomial(polynomial), left)
    polynomial = _remove_endpoint_roots(polynomial, right)
    if len(polynomial) <= 1:
        return 0
    chain = _sturm_chain(polynomial)
    if chain is None:
        return 0
    count = _sign_variations(chain, left) - _sign_variations(chain, right)
    if count < 0:
        raise CoupledTransientFailure("CMM-1 dense root isolation is unresolved.")
    return count


def _critical_increment_matches(
    origin: Fraction,
    step: Fraction,
    coefficients: tuple[Fraction, ...],
    derivative: tuple[Fraction, ...],
    left: Fraction,
    right: Fraction,
    boundary: float,
) -> bool:
    """Whether this bracket's own stationary root lies on ``boundary``.

    A common root at another endpoint or at a different stationary root does
    not authorize the bracket. An open bracket that does not contain exactly
    one derivative root is unresolved.
    """
    if step == 0:
        return False
    target = (Fraction(boundary) - origin) / step
    difference = _trim_polynomial((-target, *coefficients))
    if left == right:
        return _evaluate_polynomial(derivative, left) == 0 and _evaluate_polynomial(difference, left) == 0
    if _strict_interior_root_count(derivative, left, right) != 1:
        raise CoupledTransientFailure("CMM-1 dense root isolation is unresolved.")
    common = _polynomial_gcd(derivative, difference)
    return _strict_interior_root_count(common, left, right) == 1


def _resolve_boundary_straddle(
    kind: str,
    origin: Fraction,
    step: Fraction,
    coefficients: tuple[Fraction, ...],
    derivative: tuple[Fraction, ...],
    left: Fraction,
    right: Fraction,
) -> str:
    """Classify an enclosure that touches a domain boundary.

    A positive-width remainder cannot prove that an irrational stationary value
    is exactly on the boundary. Equality holds only when the unique interior
    stationary root of this bracket is also a root of the boundary-level
    polynomial. A common root only at an endpoint does not authorize it.
    Speed equality is inside the domain. Fold equality is not. Unresolved root
    identity fails closed.
    """
    if kind == "speed":
        if _critical_increment_matches(
            origin, step, coefficients, derivative, left, right, OMEGA_MIN
        ):
            return "safe"
        return "unknown"
    for boundary in (FOLD_LIMIT_RAD, -FOLD_LIMIT_RAD):
        if _critical_increment_matches(
            origin, step, coefficients, derivative, left, right, boundary
        ):
            return "exit"
    return "unknown"


def _component_domain_decision(kind: str, lower: Fraction, upper: Fraction) -> str:
    if kind == "fold":
        if lower >= FOLD_LIMIT_RAD or upper <= -FOLD_LIMIT_RAD:
            return "exit"
        if upper < FOLD_LIMIT_RAD and lower > -FOLD_LIMIT_RAD:
            return "safe"
        return "unknown"
    if upper < OMEGA_MIN:
        return "exit"
    if lower >= OMEGA_MIN:
        return "safe"
    return "unknown"


def _raise_for_domain(kind: str) -> None:
    if kind == "fold":
        raise CoupledDomainExit(
            "CMM-1 dense fold domain was left; v1 does not continue or publish a terminal point."
        )
    raise CoupledDomainExit(
        "CMM-1 dense shaft-speed domain was left; v1 does not continue or publish a terminal point."
    )


def _audit_polynomial_component(
    origin: Fraction,
    step: Fraction,
    coefficients: tuple[Fraction, ...],
    left: Fraction,
    right: Fraction,
    kind: str,
    budget: list[int],
) -> None:
    derivative = _trim_polynomial(
        (
            coefficients[0],
            2 * coefficients[1],
            3 * coefficients[2],
            4 * coefficients[3],
        )
    )
    brackets = [(left, left), (right, right)]
    if derivative != (Fraction(0),):
        brackets.extend(_isolate_real_roots(derivative, left, right, budget))
    unresolved = False
    for bracket in brackets:
        lower, upper = _value_enclosure(origin, step, coefficients, derivative, bracket[0], bracket[1])
        decision = _component_domain_decision(kind, lower, upper)
        if decision == "unknown":
            decision = _resolve_boundary_straddle(
                kind, origin, step, coefficients, derivative, bracket[0], bracket[1]
            )
        if decision == "exit":
            _raise_for_domain(kind)
        if decision == "unknown":
            unresolved = True
    if unresolved:
        raise CoupledTransientFailure("CMM-1 dense root isolation is unresolved.")


def _audit_dense_model_domain(dense, t_start: float, t_end: float) -> None:
    """Require one RK45 quartic to stay inside the fold and shaft-speed domains.

    Real extrema come from exact rational Sturm isolation of the represented
    derivative, followed by bounded bisection. Companion-matrix eigenvalues and
    imaginary-part tolerances are not used. A stationary value exactly on a
    domain boundary is recognized only when that same isolated root is a root
    of the boundary-level polynomial. Shaft-speed equality stays inside, and
    fold equality does not. A different endpoint root does not authorize the
    bracket. An unresolved bracket, root identity, or exhausted work budget
    fails closed. An unexpected polynomial representation fails closed instead
    of falling back to sampling.
    """
    if type(dense).__name__ != "RkDenseOutput":
        raise CoupledTransientFailure(
            "CMM-1 dense output representation is not the expected RK45 polynomial."
        )
    q_matrix = getattr(dense, "Q", None)
    y_old = getattr(dense, "y_old", None)
    step = getattr(dense, "h", None)
    if q_matrix is None or y_old is None or step is None:
        raise CoupledTransientFailure(
            "CMM-1 dense output representation is not the expected RK45 polynomial."
        )
    q_matrix = np.asarray(q_matrix, dtype=float)
    y_old = np.asarray(y_old, dtype=float)
    if q_matrix.shape != (3, 4) or y_old.shape != (3,) or getattr(dense, "order", None) != 3:
        raise CoupledTransientFailure("CMM-1 dense polynomial degree is not the RK45 quartic.")
    if (
        not math.isfinite(step)
        or step == 0.0
        or not np.isfinite(q_matrix).all()
        or not np.isfinite(y_old).all()
    ):
        raise CoupledTransientFailure("CMM-1 dense polynomial is not finite.")
    try:
        x_start = (float(t_start) - float(dense.t_old)) / float(step)
        x_end = (float(t_end) - float(dense.t_old)) / float(step)
    except (ArithmeticError, OverflowError, TypeError, ValueError) as exc:
        raise CoupledTransientFailure("CMM-1 dense interval is not representable.") from exc
    if not math.isfinite(x_start) or not math.isfinite(x_end) or x_end < x_start:
        raise CoupledTransientFailure("CMM-1 dense interval is not representable.")
    if x_start < -1.0e-9 or x_end > 1.0 + 1.0e-9:
        raise CoupledTransientFailure("CMM-1 dense interval is outside the accepted step.")
    x_start = min(1.0, max(0.0, x_start))
    x_end = min(1.0, max(0.0, x_end))
    budget = [_ROOT_WORK_BUDGET]
    step_fraction = Fraction(float(step))
    left = Fraction(float(x_start))
    right = Fraction(float(x_end))
    for index, kind in ((0, "fold"), (2, "speed")):
        coefficients = tuple(Fraction(float(q_matrix[index, column])) for column in range(4))
        _audit_polynomial_component(
            Fraction(float(y_old[index])),
            step_fraction,
            coefficients,
            left,
            right,
            kind,
            budget,
        )


def solve_coupled_transient(request: CoupledTransientRequest) -> CoupledTransientResult:
    """Integrate the partial coupled screening model until duration or first contact."""
    if not isinstance(request, CoupledTransientRequest):
        raise CoupledTransientError("Expected a validated coupled transient request.")
    system = request.system
    controls = request.controls
    origin = request.actuation.time_s[0]
    knots = tuple(value - origin for value in request.actuation.time_s)
    contact_controls = _ContactControls(
        controls.angle_atol_rad,
        controls.hinge_velocity_atol_rad_s,
    )
    rows: list[CoupledSample] = []
    boundaries: list[float] = []
    evaluations = 0
    bem_evaluations = 0
    state = (
        request.initial_angle_rad,
        request.initial_angular_velocity_rad_s,
        request.initial_omega_rad_s,
    )
    contact: CoupledStopContact | None = None

    def evaluate(time_rel: float, y, index: int) -> tuple[CoupledAcceleration, MotorEvaluation, AeroEvaluation, float]:
        nonlocal evaluations, bem_evaluations
        evaluations += 1
        if evaluations > controls.max_rhs_evaluations:
            raise CoupledTransientFailure("CMM-1 work budget exhausted.")
        theta, theta_dot, omega = _state(y)
        if abs(theta - system.deployed_angle_rad) >= FOLD_LIMIT_RAD:
            raise CoupledDomainExit("CMM-1 fold domain was left; no aerodynamic substitute is used.")
        if omega < OMEGA_MIN:
            raise CoupledDomainExit("CMM-1 shaft-speed domain was left; no zero-speed startup is used.")
        absolute = origin + time_rel
        motor = _call_evaluator("motor", request.motor_evaluator, absolute, (theta, theta_dot, omega), MotorEvaluation)
        aero = _call_evaluator("aero", request.aero_evaluator, absolute, (theta, theta_dot, omega), AeroEvaluation)
        bem_evaluations += 1
        hinge = _interpolate(request.actuation, knots, time_rel, index)
        solved = coupled_accelerations(
            system,
            theta,
            theta_dot,
            omega,
            motor.torque_nm,
            aero.shaft_torque_nm,
            hinge,
        )
        return solved, motor, aero, hinge

    def record(time_rel: float, y, index: int) -> None:
        if len(rows) >= controls.max_samples:
            raise CoupledTransientFailure("CMM-1 sample budget exhausted.")
        theta, theta_dot, omega = _state(y)
        solved, motor, aero, hinge = evaluate(time_rel, (theta, theta_dot, omega), index)
        kinetic, spring_energy, total = mechanical_energy(system, theta, theta_dot, omega)
        actuation_power = system.blade_count * hinge * theta_dot
        damping_power = system.blade_count * solved.terms.damping_nm * theta_dot
        friction_power = system.blade_count * solved.terms.friction_nm * theta_dot
        motor_power = solved.motor_torque_nm * omega
        bem_power = solved.aero_shaft_torque_nm * omega
        identity = motor_power - bem_power + actuation_power + damping_power + friction_power
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
            CoupledSample(
                time_s=_number("time", origin + time_rel),
                theta_rad=theta,
                theta_dot_rad_s=theta_dot,
                theta_ddot_rad_s2=solved.theta_ddot_rad_s2,
                omega_rad_s=omega,
                omega_dot_rad_s2=solved.omega_dot_rad_s2,
                rpm=omega * 30.0 / math.pi,
                motor_torque_nm=solved.motor_torque_nm,
                applied_voltage_v=motor.applied_voltage_v,
                back_emf_v=motor.back_emf_v,
                current_a=motor.current_a,
                electrical_power_w=motor.electrical_power_w,
                motor_shaft_power_w=_number("motor shaft power", motor_power),
                winding_loss_w=motor.winding_loss_w,
                line_loss_w=motor.line_loss_w,
                voltage_residual_v=motor.voltage_residual_v,
                bem_thrust_n=aero.thrust_n,
                bem_shaft_torque_nm=aero.shaft_torque_nm,
                bem_shaft_power_w=_number("bem shaft power", bem_power),
                bem_source_id=aero.source_id,
                bem_qualification=aero.qualification,
                projection_model=aero.projection_model,
                hinge_actuation_nm=hinge,
                collective_hinge_actuation_nm=solved.collective_actuation_nm,
                spring_torque_nm=solved.terms.spring_nm,
                damping_torque_nm=solved.terms.damping_nm,
                dry_friction_torque_nm=solved.terms.friction_nm,
                centrifugal_torque_nm=solved.terms.centrifugal_nm,
                euler_torque_nm=solved.terms.euler_nm,
                shaft_gyro_nm=solved.rhs_shaft_nm - solved.motor_torque_nm + solved.aero_shaft_torque_nm,
                aerodynamic_hinge_torque_status=AERO_HINGE_STATUS,
                mass_schur=solved.mass_schur,
                mass_residual=solved.mass_residual,
                kinetic_energy_j=kinetic,
                spring_energy_j=spring_energy,
                mechanical_energy_j=total,
                hinge_actuation_power_w=_number("actuation power", actuation_power),
                damping_power_w=_number("damping power", damping_power),
                dry_friction_power_w=_number("friction power", friction_power),
                power_identity_w=_number("power identity", identity),
                cumulative_work_j=_number("cumulative work", cumulative),
                energy_residual_j=_number("energy residual", residual),
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
                    raise CoupledTransientFailure("CMM-1 integration failed.")
                current_time = float(solver.t)
                current_state = _state(solver.y)
                if current_time <= previous_time:
                    raise CoupledTransientFailure("CMM-1 integrator stalled.")
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
                    event_omega = _number("contact shaft speed", dense(event_time)[2])
                    if event_omega < OMEGA_MIN or abs(event_state[0]) >= FOLD_LIMIT_RAD:
                        raise CoupledDomainExit(
                            "Contact reconstruction left the CMM-1 model domain."
                        )
                    record(event_time, (event_state[0], event_state[1], event_omega), index)
                    contact = CoupledStopContact(
                        name,
                        rows[-1].time_s,
                        event_state[0],
                        event_state[1],
                        event_omega,
                    )
                    break
                record(current_time, current_state, index)
        except CoupledTransientFailure:
            raise
        except (ArithmeticError, ValueError, RuntimeError) as exc:
            raise CoupledTransientFailure("CMM-1 integration failed numerically.") from exc
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
    return CoupledTransientResult(
        status=status,
        model_class=MODEL_CLASS,
        physical_qualification=False,
        aerodynamic_hinge_torque_status=AERO_HINGE_STATUS,
        full_propeller_clearance=None,
        surface_path_clearance=None,
        interblade_clearance=None,
        samples=tuple(rows),
        segment_boundary_times_s=tuple(boundaries),
        contact=contact,
        rhs_evaluations=evaluations,
        bem_evaluations=bem_evaluations,
        limitations=CMM1_LIMITATIONS,
    )


def coupled_result_document(result: CoupledTransientResult) -> Mapping[str, object]:
    if not isinstance(result, CoupledTransientResult):
        raise CoupledTransientError("Expected a CMM-1 result.")
    return {
        "model_class": result.model_class,
        "physical_qualification": False,
        "aerodynamic_hinge_torque_status": AERO_HINGE_STATUS,
        "full_propeller_clearance": None,
        "surface_path_clearance": None,
        "interblade_clearance": None,
        "status": result.status,
        "rhs_evaluations": result.rhs_evaluations,
        "bem_evaluations": result.bem_evaluations,
        "limitations": list(result.limitations),
        "segment_boundary_times_s": list(result.segment_boundary_times_s),
        "contact": None
        if result.contact is None
        else {
            "stop": result.contact.stop,
            "time_s": result.contact.time_s,
            "angle_rad": result.contact.angle_rad,
            "preimpact_angular_velocity_rad_s": result.contact.preimpact_angular_velocity_rad_s,
            "omega_rad_s": result.contact.omega_rad_s,
        },
        "samples": [sample.as_mapping() for sample in result.samples],
    }


def coupled_result_json(result: CoupledTransientResult) -> str:
    """Strict finite JSON. NaN and Infinity are rejected."""
    return json.dumps(
        coupled_result_document(result),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
