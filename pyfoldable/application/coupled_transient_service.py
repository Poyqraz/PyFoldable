"""Source-bound CMM-1 binding. Production evaluators are PR-07 and foldable BEM.

Synthetic load callbacks are rejected here. They remain available only to the
pure dynamics tests. Nothing in this module promotes GEOM clearance or claims
physical qualification.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from pyfoldable.application.design_draft import DesignDraftArtifact
from pyfoldable.application.mechanism_binding import (
    MechanismBindingError,
    TipMassDistribution,
    _load_draft,
    _mass_properties,
    _validate_geometry,
)
from pyfoldable.core.bem import BEMAnnulusError, BEMConvergenceError
from pyfoldable.core.bem_rotor import (
    BEMRotorElementError,
    BEMRotorError,
    BEMRotorSettings,
)
from pyfoldable.core.foldable_rotor import (
    FoldableRotorGeometryError,
    FoldableRotorState,
    solve_foldable_bem_rotor,
)
from pyfoldable.core.models import BladeGeometry, OperatingCondition
from pyfoldable.core.motor_bem_coupling import algebraic_motor_state
from pyfoldable.core.polar import PolarFamily, PolarInterpolationError
from pyfoldable.core.polar_spanwise import SpanwisePolarSchedule
from pyfoldable.dynamics.coupled_transient import (
    AERO_HINGE_STATUS,
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
    CoupledTransientResult,
    HingeActuationHistory,
    MotorEvaluation,
    coupled_result_document,
    solve_coupled_transient,
)
from pyfoldable.dynamics.mechanism_contracts import DryFriction
from pyfoldable.dynamics.mechanism_transient import MechanismParameters
from pythrust.propulsion.models import BatterySpec, MotorSpec, SystemSpec


SERVICE_ID = "pyfoldable.application.coupled_transient_service"
IMPLEMENTATION_ID = "cmm1_partial_coupled_screening_v1"
SCHEMA_VERSION = 1
_BEM_QUALIFICATION = "screening_only_until_pr06c_passes"
_PROJECTION_MODEL = "radial_cosine_v1"


class CoupledBindingError(ValueError):
    """The source-bound CMM-1 request cannot be sealed or rerun."""


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CoupledBindingError(f"{name} must be a finite scalar.")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise CoupledBindingError(f"{name} must be a finite scalar.") from exc
    if not math.isfinite(result):
        raise CoupledBindingError(f"{name} must be a finite scalar.")
    return result


def _json(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise CoupledBindingError("CMM-1 context must contain finite JSON-safe data.") from exc


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CoupledEnvironment:
    """Fixed flight condition. Shaft speed comes from the dynamic state."""

    id: str
    forward_speed_m_s: float
    air_density_kg_m3: float
    dynamic_viscosity_pa_s: float
    temperature_k: float
    pressure_pa: float

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip() or len(self.id) > 200:
            raise CoupledBindingError("CoupledEnvironment.id must be a nonempty bounded string.")
        _finite("forward_speed_m_s", self.forward_speed_m_s)
        for name in (
            "air_density_kg_m3",
            "dynamic_viscosity_pa_s",
            "temperature_k",
            "pressure_pa",
        ):
            if _finite(name, getattr(self, name)) <= 0.0:
                raise CoupledBindingError(f"{name} must be greater than zero.")


def _table_identity(table) -> dict[str, object]:
    return {
        "airfoil_id": table.airfoil_id,
        "scenario_id": table.scenario_id,
        "reynolds": table.reynolds,
        "mach": table.mach,
        "alpha_rad": list(table.alpha_rad),
        "cl": list(table.cl),
        "cd": list(table.cd),
        "cm": list(table.cm),
        "source": table.source,
    }


def _family_identity(family: PolarFamily) -> dict[str, object]:
    if not isinstance(family, PolarFamily):
        raise CoupledBindingError("Expected a PolarFamily.")
    return {
        "airfoil_id": family.airfoil_id,
        "tables": [_table_identity(table) for table in family.tables],
    }


def _polar_identity(polars: Mapping[str, PolarFamily] | SpanwisePolarSchedule) -> dict[str, object]:
    if isinstance(polars, SpanwisePolarSchedule):
        return {
            "kind": "spanwise",
            "id": polars.id,
            "anchors": [
                {"r_over_R": anchor.r_over_R, "family": _family_identity(anchor.family)}
                for anchor in polars.anchors
            ],
        }
    if isinstance(polars, Mapping):
        return {
            "kind": "mapping",
            "families": [
                {"airfoil_id": key, "family": _family_identity(polars[key])}
                for key in sorted(polars)
            ],
        }
    raise CoupledBindingError("Polars must be a mapping or a SpanwisePolarSchedule.")


def _validate_electrical(motor: MotorSpec, battery: BatterySpec, system: SystemSpec, throttle: float) -> float:
    if not isinstance(motor, MotorSpec) or not isinstance(battery, BatterySpec) or not isinstance(system, SystemSpec):
        raise CoupledBindingError("Motor, battery, and system specs are required.")
    for name, value in (
        ("motor.kv_rpm_per_v", motor.kv_rpm_per_v),
        ("motor.resistance_ohm", motor.resistance_ohm),
        ("motor.no_load_current_a", motor.no_load_current_a),
        ("motor.current_max_a", motor.current_max_a),
        ("motor.torque_constant_kv_ratio", motor.torque_constant_kv_ratio),
        ("battery.voltage_v", battery.voltage_v),
        ("system.resistance_ohm", system.resistance_ohm),
    ):
        _finite(name, value)
    if motor.kv_rpm_per_v <= 0.0 or motor.resistance_ohm <= 0.0:
        raise CoupledBindingError("Motor Kv and resistance must be greater than zero.")
    if motor.no_load_current_a < 0.0 or motor.current_max_a <= 0.0:
        raise CoupledBindingError("Motor currents violate the declared domain.")
    if motor.torque_constant_kv_ratio <= 0.0 or battery.voltage_v <= 0.0:
        raise CoupledBindingError("Torque-constant ratio and battery voltage must be positive.")
    if system.resistance_ohm < 0.0:
        raise CoupledBindingError("System resistance must not be negative.")
    throttle_value = _finite("throttle", throttle)
    if not 0.0 < throttle_value <= 1.0:
        raise CoupledBindingError("throttle must satisfy 0 < throttle <= 1.")
    return throttle_value


class Pr07MotorEvaluator:
    """PR-07 algebraic motor law with the CMM-1 motoring-domain gate."""

    canonical_id = "cmm1_pr07_motor_algebra_v1"

    def __init__(self, motor: MotorSpec, battery: BatterySpec, system: SystemSpec, throttle: float) -> None:
        self.motor = motor
        self.battery = battery
        self.system = system
        self.throttle = _validate_electrical(motor, battery, system, throttle)

    def __call__(self, time_s: float, theta_rad: float, theta_dot_rad_s: float, omega_rad_s: float) -> MotorEvaluation:
        del time_s, theta_rad, theta_dot_rad_s
        rpm = omega_rad_s * 30.0 / math.pi
        try:
            state = algebraic_motor_state(
                self.motor, self.battery, self.system, self.throttle, rpm
            )
        except (ArithmeticError, TypeError, ValueError, RuntimeError) as exc:
            raise CoupledTransientFailure("PR-07 motor algebra failed.") from exc
        if not all(
            math.isfinite(value)
            for value in (
                state.torque_nm,
                state.current_a,
                state.applied_voltage_v,
                state.back_emf_v,
                state.voltage_residual_v,
            )
        ):
            raise CoupledTransientFailure("PR-07 motor algebra returned a nonfinite state.")
        if state.applied_voltage_v <= state.back_emf_v:
            raise CoupledDomainExit("CMM-1 left the motoring domain; regeneration is not modeled.")
        if state.current_a > self.motor.current_max_a:
            raise CoupledDomainExit("CMM-1 current limit was exceeded; current is not clipped.")
        if state.current_a < self.motor.get_no_load_current(rpm):
            raise CoupledDomainExit("CMM-1 current is below the no-load motoring current.")
        return MotorEvaluation(
            torque_nm=state.torque_nm,
            applied_voltage_v=state.applied_voltage_v,
            back_emf_v=state.back_emf_v,
            current_a=state.current_a,
            electrical_power_w=state.electrical_input_power_w,
            shaft_power_w=state.shaft_power_w,
            winding_loss_w=state.winding_loss_w,
            line_loss_w=state.line_loss_w,
            voltage_residual_v=state.voltage_residual_v,
        )


class FoldableBemShaftEvaluator:
    """Frozen-fold whole-rotor BEM shaft load. Hinge torque is not derived."""

    canonical_id = "cmm1_foldable_bem_v1"

    def __init__(
        self,
        blade: BladeGeometry,
        polars: Mapping[str, PolarFamily] | SpanwisePolarSchedule,
        settings: BEMRotorSettings,
        environment: CoupledEnvironment,
        hinge_radius_m: float,
        bounds: str,
    ) -> None:
        if not isinstance(blade, BladeGeometry):
            raise CoupledBindingError("blade must be a BladeGeometry.")
        if not isinstance(settings, BEMRotorSettings):
            raise CoupledBindingError("BEM settings must be explicit BEMRotorSettings.")
        if not isinstance(environment, CoupledEnvironment):
            raise CoupledBindingError("environment must be a CoupledEnvironment.")
        if bounds != "error":
            raise CoupledBindingError('CMM-1 requires polar bounds = "error".')
        _polar_identity(polars)
        self.blade = blade
        self.polars = polars
        self.settings = settings
        self.environment = environment
        self.hinge_radius_m = hinge_radius_m
        self.bounds = bounds
        self.source_id = (
            polars.id if isinstance(polars, SpanwisePolarSchedule) else "airfoil-polar-mapping"
        )
        self.calls = 0

    def __call__(self, time_s: float, theta_rad: float, theta_dot_rad_s: float, omega_rad_s: float) -> AeroEvaluation:
        del time_s, theta_dot_rad_s
        if omega_rad_s < OMEGA_MIN or abs(theta_rad) >= 0.5 * math.pi:
            raise CoupledDomainExit("Foldable BEM was not evaluated outside the CMM-1 domain.")
        self.calls += 1
        state = FoldableRotorState(
            id=f"cmm1-{self.calls}",
            hinge_radius_m=self.hinge_radius_m,
            opening_angle_rad=theta_rad,
            deployed_angle_rad=0.0,
        )
        condition = OperatingCondition(
            id=f"cmm1-{self.calls}",
            angular_speed_rad_s=omega_rad_s,
            forward_speed_m_s=self.environment.forward_speed_m_s,
            air_density_kg_m3=self.environment.air_density_kg_m3,
            dynamic_viscosity_pa_s=self.environment.dynamic_viscosity_pa_s,
            temperature_k=self.environment.temperature_k,
            pressure_pa=self.environment.pressure_pa,
        )
        try:
            result = solve_foldable_bem_rotor(
                self.blade,
                state,
                condition,
                self.polars,
                bounds=self.bounds,
                settings=self.settings,
            )
        except (
            BEMAnnulusError,
            BEMConvergenceError,
            BEMRotorElementError,
            BEMRotorError,
            FoldableRotorGeometryError,
            PolarInterpolationError,
        ) as exc:
            raise CoupledTransientFailure("Foldable BEM evaluation failed.") from exc
        return AeroEvaluation(
            shaft_torque_nm=result.rotor_result.torque_nm,
            thrust_n=result.rotor_result.thrust_n,
            source_id=self.source_id,
            qualification=_BEM_QUALIFICATION,
            projection_model=_PROJECTION_MODEL,
        )


def assert_cmm1_production_evaluators(motor: object, aero: object) -> None:
    """Reject analytic or test evaluators before a source-bound artifact is built."""
    if type(motor) is not Pr07MotorEvaluator or type(aero) is not FoldableBemShaftEvaluator:
        raise CoupledBindingError(
            "Source-bound CMM-1 accepts only the PR-07 motor law and foldable BEM evaluators."
        )


def _derive(draft: DesignDraftArtifact, distribution: TipMassDistribution, initial_angle_rad: float):
    try:
        design = _load_draft(draft)
        hinge, _audit = _validate_geometry(design, initial_angle_rad)
        tip_length = design.blade.radius_m - hinge.radius_m
        mass, cg, inertia = _mass_properties(distribution, tip_length)
    except MechanismBindingError as exc:
        raise CoupledBindingError(str(exc)) from exc
    return design, hinge, mass, cg, inertia


def _parameters(
    draft: DesignDraftArtifact,
    distribution: TipMassDistribution,
    initial_angle_rad: float,
    spring_stiffness_nm_rad: float,
    rest_angle_rad: float,
    viscous_damping_nm_s_rad: float,
    dry_friction: DryFriction,
) -> tuple[object, MechanismParameters]:
    design, hinge, mass, cg, inertia = _derive(draft, distribution, initial_angle_rad)
    try:
        parameters = MechanismParameters(
            mass_kg=mass,
            cg_distance_m=cg,
            hinge_inertia_kg_m2=inertia,
            hinge_radius_m=hinge.radius_m,
            spring_stiffness_nm_rad=spring_stiffness_nm_rad,
            rest_angle_rad=rest_angle_rad,
            viscous_damping_nm_s_rad=viscous_damping_nm_s_rad,
            lower_stop_rad=hinge.stowed_angle_rad,
            upper_stop_rad=hinge.stop_angle_rad,
            dry_friction=dry_friction,
        )
    except (TypeError, ValueError) as exc:
        raise CoupledBindingError(str(exc)) from exc
    return design, parameters


def _input_payload(binding: "CoupledBinding") -> dict[str, object]:
    if binding.base_inertia.excludes_modeled_movable_tips is not True:
        raise CoupledBindingError("I0 must exclude every modeled movable tip.")
    design, parameters = _parameters(
        binding.draft,
        binding.distribution,
        binding.initial_angle_rad,
        binding.spring_stiffness_nm_rad,
        binding.rest_angle_rad,
        binding.viscous_damping_nm_s_rad,
        binding.dry_friction,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "model_class": MODEL_CLASS,
        "physical_qualification": False,
        "aerodynamic_hinge_torque_status": AERO_HINGE_STATUS,
        "full_propeller_clearance": None,
        "implementation_id": IMPLEMENTATION_ID,
        "draft_sha256": binding.draft.draft_sha256,
        "source_sha256": binding.draft.source_sha256,
        "source_identity_scope": "declared_source_hash_not_external_authentication",
        "blade_count": design.blade.blade_count,
        "hinge_radius_m": parameters.hinge_radius_m,
        "derived_mass_kg": parameters.mass_kg,
        "derived_cg_distance_m": parameters.cg_distance_m,
        "derived_hinge_inertia_kg_m2": parameters.hinge_inertia_kg_m2,
        "lower_stop_rad": parameters.lower_stop_rad,
        "upper_stop_rad": parameters.upper_stop_rad,
        "mass_distribution": asdict(binding.distribution),
        "spring_stiffness_nm_rad": binding.spring_stiffness_nm_rad,
        "rest_angle_rad": binding.rest_angle_rad,
        "viscous_damping_nm_s_rad": binding.viscous_damping_nm_s_rad,
        "dry_friction": asdict(binding.dry_friction),
        "mechanical_source": binding.mechanical_source,
        "base_rotating_inertia": {
            "inertia_kg_m2": binding.base_inertia.inertia_kg_m2,
            "source": binding.base_inertia.source,
            "component_inventory": list(binding.base_inertia.component_inventory),
            "excludes_modeled_movable_tips": True,
        },
        "motor": asdict(binding.motor),
        "battery": asdict(binding.battery),
        "system": asdict(binding.system),
        "throttle": binding.throttle,
        "environment": asdict(binding.environment),
        "polars": _polar_identity(binding.polars),
        "bem_settings": dict(binding.bem_settings.as_mapping()),
        "bounds": binding.bounds,
        "controls": asdict(binding.controls),
        "initial_angle_rad": binding.initial_angle_rad,
        "initial_angular_velocity_rad_s": binding.initial_angular_velocity_rad_s,
        "initial_omega_rad_s": binding.initial_omega_rad_s,
        "actuation": {
            "time_s": list(binding.actuation.time_s),
            "torque_nm": list(binding.actuation.torque_nm),
            "source": binding.actuation.source,
        },
    }


@dataclass(frozen=True)
class CoupledBinding:
    """Sealed inputs. Hash identity is not authentication or qualification."""

    draft: DesignDraftArtifact
    distribution: TipMassDistribution
    base_inertia: BaseRotatingAssemblyInertia
    spring_stiffness_nm_rad: float
    rest_angle_rad: float
    viscous_damping_nm_s_rad: float
    dry_friction: DryFriction
    mechanical_source: str
    initial_angle_rad: float
    initial_angular_velocity_rad_s: float
    initial_omega_rad_s: float
    actuation: HingeActuationHistory
    motor: MotorSpec
    battery: BatterySpec
    system: SystemSpec
    throttle: float
    environment: CoupledEnvironment
    polars: Mapping[str, PolarFamily] | SpanwisePolarSchedule
    bem_settings: BEMRotorSettings
    bounds: str
    controls: CoupledSolverControls
    context_json: str
    input_sha256: str


@dataclass(frozen=True)
class CoupledArtifact:
    report_json: str
    report_sha256: str
    input_sha256: str
    result: CoupledTransientResult


def _build_request(binding: CoupledBinding) -> CoupledTransientRequest:
    design, parameters = _parameters(
        binding.draft,
        binding.distribution,
        binding.initial_angle_rad,
        binding.spring_stiffness_nm_rad,
        binding.rest_angle_rad,
        binding.viscous_damping_nm_s_rad,
        binding.dry_friction,
    )
    motor = Pr07MotorEvaluator(binding.motor, binding.battery, binding.system, binding.throttle)
    aero = FoldableBemShaftEvaluator(
        design.blade,
        binding.polars,
        binding.bem_settings,
        binding.environment,
        parameters.hinge_radius_m,
        binding.bounds,
    )
    assert_cmm1_production_evaluators(motor, aero)
    try:
        return CoupledTransientRequest(
            CoupledSystem(parameters, design.blade.blade_count, binding.base_inertia),
            binding.actuation,
            binding.initial_angle_rad,
            binding.initial_angular_velocity_rad_s,
            binding.initial_omega_rad_s,
            motor,
            aero,
            binding.controls,
        )
    except CoupledTransientError as exc:
        raise CoupledBindingError(str(exc)) from exc


def validate_coupled_binding(binding: CoupledBinding) -> None:
    if not isinstance(binding, CoupledBinding):
        raise CoupledBindingError("Expected a sealed CMM-1 binding.")
    payload = _json(_input_payload(binding))
    if payload != binding.context_json or _sha(payload) != binding.input_sha256:
        raise CoupledBindingError("Binding identity does not match the sealed inputs.")


def prepare_coupled_transient(
    draft: DesignDraftArtifact,
    distribution: TipMassDistribution,
    *,
    base_inertia: BaseRotatingAssemblyInertia,
    spring_stiffness_nm_rad: float,
    rest_angle_rad: float,
    viscous_damping_nm_s_rad: float,
    initial_angle_rad: float,
    initial_angular_velocity_rad_s: float,
    initial_omega_rad_s: float,
    actuation: HingeActuationHistory,
    motor: MotorSpec,
    battery: BatterySpec,
    system: SystemSpec,
    throttle: float,
    environment: CoupledEnvironment,
    polars: Mapping[str, PolarFamily] | SpanwisePolarSchedule,
    bem_settings: BEMRotorSettings,
    bounds: str,
    mechanical_source: str,
    dry_friction: DryFriction = DryFriction(),
    controls: CoupledSolverControls = CoupledSolverControls(),
) -> CoupledBinding:
    """Seal one source-bound CMM-1 problem without integrating it."""
    if not isinstance(base_inertia, BaseRotatingAssemblyInertia):
        raise CoupledBindingError("base_inertia must be BaseRotatingAssemblyInertia.")
    if not isinstance(actuation, HingeActuationHistory):
        raise CoupledBindingError("actuation must be a CMM-1 hinge history, not a prescribed RPM drive.")
    if not isinstance(environment, CoupledEnvironment):
        raise CoupledBindingError("environment must be a CoupledEnvironment.")
    if not isinstance(bem_settings, BEMRotorSettings):
        raise CoupledBindingError("bem_settings must be explicit.")
    if not isinstance(controls, CoupledSolverControls):
        raise CoupledBindingError("controls must be CoupledSolverControls.")
    if not isinstance(dry_friction, DryFriction):
        raise CoupledBindingError("dry_friction must be a DryFriction contract.")
    if not isinstance(mechanical_source, str) or not mechanical_source.strip():
        raise CoupledBindingError("mechanical_source must be nonempty.")
    if bounds != "error":
        raise CoupledBindingError('CMM-1 requires polar bounds = "error".')
    _validate_electrical(motor, battery, system, throttle)
    _polar_identity(polars)
    binding = CoupledBinding(
        draft=draft,
        distribution=distribution,
        base_inertia=base_inertia,
        spring_stiffness_nm_rad=_finite("spring_stiffness_nm_rad", spring_stiffness_nm_rad),
        rest_angle_rad=_finite("rest_angle_rad", rest_angle_rad),
        viscous_damping_nm_s_rad=_finite("viscous_damping_nm_s_rad", viscous_damping_nm_s_rad),
        dry_friction=dry_friction,
        mechanical_source=mechanical_source,
        initial_angle_rad=_finite("initial_angle_rad", initial_angle_rad),
        initial_angular_velocity_rad_s=_finite(
            "initial_angular_velocity_rad_s", initial_angular_velocity_rad_s
        ),
        initial_omega_rad_s=_finite("initial_omega_rad_s", initial_omega_rad_s),
        actuation=actuation,
        motor=motor,
        battery=battery,
        system=system,
        throttle=_finite("throttle", throttle),
        environment=environment,
        polars=polars,
        bem_settings=bem_settings,
        bounds=bounds,
        controls=controls,
        context_json="",
        input_sha256="",
    )
    payload = _json(_input_payload(binding))
    sealed = CoupledBinding(
        draft=draft,
        distribution=distribution,
        base_inertia=base_inertia,
        spring_stiffness_nm_rad=binding.spring_stiffness_nm_rad,
        rest_angle_rad=binding.rest_angle_rad,
        viscous_damping_nm_s_rad=binding.viscous_damping_nm_s_rad,
        dry_friction=dry_friction,
        mechanical_source=mechanical_source,
        initial_angle_rad=binding.initial_angle_rad,
        initial_angular_velocity_rad_s=binding.initial_angular_velocity_rad_s,
        initial_omega_rad_s=binding.initial_omega_rad_s,
        actuation=actuation,
        motor=motor,
        battery=battery,
        system=system,
        throttle=binding.throttle,
        environment=environment,
        polars=polars,
        bem_settings=bem_settings,
        bounds=bounds,
        controls=controls,
        context_json=payload,
        input_sha256=_sha(payload),
    )
    _build_request(sealed)
    return sealed


def _implementation_files() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]
    names = (
        "dynamics/coupled_transient.py",
        "application/coupled_transient_service.py",
        "core/motor_bem_coupling.py",
    )
    return {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in names
    }


def run_coupled_transient(
    binding: CoupledBinding,
    *,
    expected_input_sha256: str | None = None,
) -> CoupledArtifact:
    """Integrate a sealed binding. Hard failures do not return a success artifact."""
    validate_coupled_binding(binding)
    if expected_input_sha256 is not None and expected_input_sha256 != binding.input_sha256:
        raise CoupledBindingError("Binding identity does not match the requested seal.")
    result = solve_coupled_transient(_build_request(binding))
    if result.physical_qualification is not False or result.full_propeller_clearance is not None:
        raise CoupledTransientFailure("CMM-1 invariant broken: qualification or clearance was set.")
    report = {
        "schema_version": SCHEMA_VERSION,
        "service_id": SERVICE_ID,
        "implementation_id": IMPLEMENTATION_ID,
        "implementation_files_sha256": _implementation_files(),
        "model_class": MODEL_CLASS,
        "physical_qualification": False,
        "aerodynamic_hinge_torque_status": AERO_HINGE_STATUS,
        "full_propeller_clearance": None,
        "surface_path_clearance": None,
        "interblade_clearance": None,
        "input_sha256": binding.input_sha256,
        "draft_sha256": binding.draft.draft_sha256,
        "source_sha256": binding.draft.source_sha256,
        "source_identity_scope": "declared_source_hash_not_external_authentication",
        "base_rotating_inertia": json.loads(binding.context_json)["base_rotating_inertia"],
        "bounds": binding.bounds,
        "bem_settings": dict(binding.bem_settings.as_mapping()),
        "loading_branch": binding.bem_settings.annulus_settings.loading_branch,
        "projection_model": _PROJECTION_MODEL,
        "bem_qualification": _BEM_QUALIFICATION,
        "result": coupled_result_document(result),
    }
    report_json = _json(report)
    if "aerodynamic_hinge_torque_nm" in report_json:
        raise CoupledTransientFailure("CMM-1 report must not publish a numeric aerodynamic hinge torque.")
    return CoupledArtifact(
        report_json=report_json,
        report_sha256=_sha(report_json),
        input_sha256=binding.input_sha256,
        result=result,
    )
