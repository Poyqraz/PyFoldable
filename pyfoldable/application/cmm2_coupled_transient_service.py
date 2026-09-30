"""Source-bound CMM-2 screening service.

One aerodynamic evaluation solves foldable BEM once and maps that same
returned object. The pure dynamics module still accepts analytic callbacks.
This service does not change CMM-1, the accepted load-map mathematics, or
physical qualification.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from pyfoldable.application.coupled_transient_service import (
    CoupledBindingError,
    CoupledEnvironment,
    Pr07MotorEvaluator,
    _parameters,
    _polar_identity,
    _validate_electrical,
)
from pyfoldable.application.design_draft import DesignDraftArtifact
from pyfoldable.application.mechanism_binding import TipMassDistribution
from pyfoldable.core.bem import BEMAnnulusError, BEMConvergenceError
from pyfoldable.core.bem_rotor import (
    BEMRotorElementError,
    BEMRotorError,
    BEMRotorSettings,
)
from pyfoldable.core.foldable_aero_load import (
    DISTRIBUTED_COUPLE_MODEL,
    HINGE_RATE_AERODYNAMIC_MODEL as PLANAR_HINGE_RATE_MODEL,
    LOAD_MAPPING_MODEL as PLANAR_LOAD_MAPPING_MODEL,
    PLANAR_PROJECTED_MATERIAL_LOAD_SCHEMA_VERSION,
    PROJECTION_MODEL as PLANAR_PROJECTION_MODEL,
    QUALIFICATION as PLANAR_QUALIFICATION,
    SECTIONAL_AERODYNAMIC_COUPLE,
    PlanarProjectedMaterialLoadError,
    PlanarProjectedMaterialLoadResult,
    map_foldable_bem_aero_loads,
)
from pyfoldable.core.foldable_rotor import (
    FOLDABLE_BEM_ROTOR_SCHEMA_VERSION,
    FoldableRotorGeometryError,
    FoldableRotorState,
    solve_foldable_bem_rotor,
)
from pyfoldable.core.models import BladeGeometry, OperatingCondition
from pyfoldable.core.polar import PolarFamily, PolarInterpolationError
from pyfoldable.core.polar_spanwise import SpanwisePolarSchedule
from pyfoldable.dynamics.cmm2_coupled_transient import (
    AERO_LOAD_QUALIFICATION,
    AERO_LOAD_STATUS,
    FOLD_LIMIT_RAD,
    HINGE_RATE_AERO_MODEL,
    IMPLEMENTATION_ID as DYNAMICS_IMPLEMENTATION_ID,
    LOAD_MAPPING_MODEL,
    MODEL_CLASS,
    OMEGA_MIN,
    PROJECTION_MODEL,
    Cmm2AeroEvaluation,
    Cmm2DomainExit,
    Cmm2TransientError,
    Cmm2TransientFailure,
    Cmm2TransientRequest,
    Cmm2TransientResult,
    solve_cmm2_transient,
)
from pyfoldable.dynamics.coupled_transient import (
    BaseRotatingAssemblyInertia,
    CoupledSolverControls,
    CoupledSystem,
    HingeActuationHistory,
)
from pyfoldable.dynamics.mechanism_contracts import DryFriction
from pythrust.propulsion.models import BatterySpec, MotorSpec, SystemSpec


SERVICE_ID = "pyfoldable.application.cmm2_coupled_transient_service"
SERVICE_IMPLEMENTATION_ID = "cmm2_source_bound_screening_service_v1"
SCHEMA_VERSION = 1
AERO_EVALUATOR_ID = "cmm2_foldable_bem_planar_map_v1"
_HASH_SCOPE = "content_identity_not_authentication_correctness_or_physical_validity"
_AERO_SOURCE_FAILURE = "CMM-2 aerodynamic source evaluation failed."
_AERO_FAILURES = (
    BEMAnnulusError,
    BEMConvergenceError,
    BEMRotorElementError,
    BEMRotorError,
    FoldableRotorGeometryError,
    PolarInterpolationError,
    PlanarProjectedMaterialLoadError,
)


class Cmm2CoupledBindingError(ValueError):
    """The source-bound CMM-2 request cannot be sealed or rerun."""


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Cmm2CoupledBindingError(f"{name} must be a finite scalar.")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise Cmm2CoupledBindingError(f"{name} must be a finite scalar.") from exc
    if not math.isfinite(result):
        raise Cmm2CoupledBindingError(f"{name} must be a finite scalar.")
    return result


def _canonical_json(value: object, error: type[Exception], message: str) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise error(message) from exc


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _binding_error(exc: CoupledBindingError) -> Cmm2CoupledBindingError:
    return Cmm2CoupledBindingError(str(exc))


def _planar_contract() -> dict[str, object]:
    if (
        PLANAR_LOAD_MAPPING_MODEL != LOAD_MAPPING_MODEL
        or PLANAR_QUALIFICATION != AERO_LOAD_QUALIFICATION
        or PLANAR_PROJECTION_MODEL != PROJECTION_MODEL
        or PLANAR_HINGE_RATE_MODEL != HINGE_RATE_AERO_MODEL
    ):
        raise Cmm2CoupledBindingError(
            "CMM-2 planar load identifiers do not match the dynamics contract."
        )
    return {
        "schema_version": PLANAR_PROJECTED_MATERIAL_LOAD_SCHEMA_VERSION,
        "load_mapping_model": PLANAR_LOAD_MAPPING_MODEL,
        "qualification": PLANAR_QUALIFICATION,
        "projection_model": PLANAR_PROJECTION_MODEL,
        "distributed_couple_model": DISTRIBUTED_COUPLE_MODEL,
        "hinge_rate_aerodynamic_model": PLANAR_HINGE_RATE_MODEL,
        "sectional_aerodynamic_couple": SECTIONAL_AERODYNAMIC_COUPLE,
        "foldable_bem_schema_version": FOLDABLE_BEM_ROTOR_SCHEMA_VERSION,
    }


def _require_finite_state(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Cmm2TransientFailure(f"CMM-2 aerodynamic source received a nonfinite {name}.")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise Cmm2TransientFailure(
            f"CMM-2 aerodynamic source received a nonfinite {name}."
        ) from exc
    if not math.isfinite(result):
        raise Cmm2TransientFailure(f"CMM-2 aerodynamic source received a nonfinite {name}.")
    return result


def _bem_provenance(mapping: Mapping[str, object]) -> dict[str, object]:
    rotor = mapping.get("rotor_result")
    rotor_map = dict(rotor) if isinstance(rotor, Mapping) else {}
    settings = rotor_map.get("settings")
    return {
        "schema_version": mapping.get("schema_version"),
        "state": mapping.get("state"),
        "projection_factor": mapping.get("projection_factor"),
        "fixed_limit_equivalent": mapping.get("fixed_limit_equivalent"),
        "polar_schedule_id": mapping.get("polar_schedule_id"),
        "qualification": mapping.get("qualification"),
        "operating_condition_id": rotor_map.get("operating_condition_id"),
        "airfoil_id": rotor_map.get("airfoil_id"),
        "scenario_id": rotor_map.get("scenario_id"),
        "radial_domain": rotor_map.get("radial_domain"),
        "geometry_extended": rotor_map.get("geometry_extended"),
        "polar_bounds": rotor_map.get("polar_bounds"),
        "annulus_count": rotor_map.get("annulus_count"),
        "bem_settings": dict(settings) if isinstance(settings, Mapping) else settings,
        "polar_sources": rotor_map.get("polar_sources"),
        "raw_bem_thrust_n_not_used_as_cmm2_thrust": rotor_map.get("thrust_n"),
        "raw_bem_resisting_torque_nm_not_used_as_cmm2_generalized_load": (
            rotor_map.get("torque_nm")
        ),
    }


@dataclass(frozen=True)
class Cmm2AeroProvenanceRecord:
    """One successful BEM solve and the planar map of that same object."""

    evaluation_index: int
    absolute_time_s: float
    theta_rad: float
    hinge_rate_rad_s: float
    omega_rad_s: float
    source_id: str
    mapped_load_sha256: str
    bem_result_sha256: str
    whole_rotor_shaft_generalized_load_nm: float
    one_tip_hinge_generalized_load_nm: float
    thrust_n: float
    source_whole_rotor_resisting_torque_nm: float
    raw_bem_resisting_torque_nm_not_used_as_cmm2_generalized_load: float
    synchronous_n_times_one_tip_hinge_generalized_torque_nm: float
    collective_hinge_field_fed_to_dynamics: bool
    blade_count: int
    hinge_radius_m: float
    projection_factor: float
    projected_tip_radius_m: float
    source_outer_projected_radius_m: float
    source_terminal_radius_m: float
    terminal_boundary_normalized: bool
    terminal_boundary_delta_m: float
    operating_condition_id: str
    polar_schedule_id: str | None
    airfoil_id: str
    scenario_id: str
    polar_sources: tuple[str, ...]
    radial_domain: str
    geometry_extended: bool
    load_mapping_model: str
    qualification: str
    projection_model: str
    hinge_rate_aerodynamic_model: str
    physical_qualification: bool
    distributed_couple_model: str
    sectional_aerodynamic_couple: str
    schema_version: int
    bem_settings_json: str
    mapped_load_json: str
    bem_provenance_json: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.evaluation_index, bool)
            or not isinstance(self.evaluation_index, int)
            or self.evaluation_index < 0
        ):
            raise Cmm2TransientFailure("CMM-2 aerodynamic provenance index is invalid.")
        if self.collective_hinge_field_fed_to_dynamics is not False:
            raise Cmm2TransientFailure(
                "CMM-2 must not feed the collective hinge field into the one-tip load."
            )
        if self.physical_qualification is not False:
            raise Cmm2TransientFailure("CMM-2 provenance cannot claim physical qualification.")
        if (
            self.distributed_couple_model != DISTRIBUTED_COUPLE_MODEL
            or self.sectional_aerodynamic_couple != SECTIONAL_AERODYNAMIC_COUPLE
        ):
            raise Cmm2TransientFailure("CMM-2 provenance cannot add a sectional aerodynamic couple.")
        if not isinstance(self.terminal_boundary_normalized, bool):
            raise Cmm2TransientFailure("CMM-2 terminal provenance flag must be boolean.")
        if not isinstance(self.geometry_extended, bool):
            raise Cmm2TransientFailure("CMM-2 geometry_extended must be boolean.")

    def as_mapping(self) -> dict[str, object]:
        return {
            "evaluation_index": self.evaluation_index,
            "absolute_time_s": self.absolute_time_s,
            "theta_rad": self.theta_rad,
            "hinge_rate_rad_s": self.hinge_rate_rad_s,
            "omega_rad_s": self.omega_rad_s,
            "source_id": self.source_id,
            "mapped_load_sha256": self.mapped_load_sha256,
            "bem_result_sha256": self.bem_result_sha256,
            "whole_rotor_shaft_generalized_load_nm": (
                self.whole_rotor_shaft_generalized_load_nm
            ),
            "one_tip_hinge_generalized_load_nm": self.one_tip_hinge_generalized_load_nm,
            "theta_dot_rad_s": self.hinge_rate_rad_s,
            "foldable_bem_result_sha256": self.bem_result_sha256,
            "thrust_n": self.thrust_n,
            "source_whole_rotor_projected_thrust_n": self.thrust_n,
            "source_whole_rotor_resisting_torque_nm": (
                self.source_whole_rotor_resisting_torque_nm
            ),
            "raw_bem_resisting_torque_nm_not_used_as_cmm2_generalized_load": (
                self.raw_bem_resisting_torque_nm_not_used_as_cmm2_generalized_load
            ),
            "synchronous_n_times_one_tip_hinge_generalized_torque_nm": (
                self.synchronous_n_times_one_tip_hinge_generalized_torque_nm
            ),
            "collective_hinge_field_fed_to_dynamics": False,
            "blade_count": self.blade_count,
            "hinge_radius_m": self.hinge_radius_m,
            "projection_factor": self.projection_factor,
            "projected_tip_radius_m": self.projected_tip_radius_m,
            "source_outer_projected_radius_m": self.source_outer_projected_radius_m,
            "source_terminal_radius_m": self.source_terminal_radius_m,
            "terminal_boundary_normalized": self.terminal_boundary_normalized,
            "terminal_boundary_delta_m": self.terminal_boundary_delta_m,
            "operating_condition_id": self.operating_condition_id,
            "polar_schedule_id": self.polar_schedule_id,
            "airfoil_id": self.airfoil_id,
            "scenario_id": self.scenario_id,
            "polar_sources": list(self.polar_sources),
            "radial_domain": self.radial_domain,
            "geometry_extended": self.geometry_extended,
            "load_mapping_model": self.load_mapping_model,
            "qualification": self.qualification,
            "projection_model": self.projection_model,
            "hinge_rate_aerodynamic_model": self.hinge_rate_aerodynamic_model,
            "physical_qualification": self.physical_qualification,
            "distributed_couple_model": self.distributed_couple_model,
            "sectional_aerodynamic_couple": self.sectional_aerodynamic_couple,
            "schema_version": self.schema_version,
            "bem_settings": json.loads(self.bem_settings_json),
            "mapped_load": json.loads(self.mapped_load_json),
            "bem_provenance": json.loads(self.bem_provenance_json),
        }


class Cmm2FoldableBemMappedAeroEvaluator:
    """One foldable BEM solve and one planar map of that returned object."""

    canonical_id = AERO_EVALUATOR_ID

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
            raise Cmm2CoupledBindingError("blade must be a BladeGeometry.")
        if not isinstance(settings, BEMRotorSettings):
            raise Cmm2CoupledBindingError("BEM settings must be explicit BEMRotorSettings.")
        if not isinstance(environment, CoupledEnvironment):
            raise Cmm2CoupledBindingError("environment must be a CoupledEnvironment.")
        if bounds != "error":
            raise Cmm2CoupledBindingError('CMM-2 requires polar bounds = "error".')
        if _finite("hinge_radius_m", hinge_radius_m) <= 0.0:
            raise Cmm2CoupledBindingError("Hinge radius must be strictly positive.")
        try:
            _polar_identity(polars)
        except CoupledBindingError as exc:
            raise _binding_error(exc) from exc
        _planar_contract()
        self.blade = blade
        self.polars = polars
        self.settings = settings
        self.environment = environment
        self.hinge_radius_m = hinge_radius_m
        self.bounds = bounds
        self.successful_bem_solves = 0
        self.successful_map_calls = 0
        self.provenance_records: list[Cmm2AeroProvenanceRecord] = []

    def __call__(
        self,
        time_s: float,
        theta_rad: float,
        theta_dot_rad_s: float,
        omega_rad_s: float,
    ) -> Cmm2AeroEvaluation:
        absolute_time = _require_finite_state("time", time_s)
        theta = _require_finite_state("theta", theta_rad)
        theta_dot = _require_finite_state("hinge rate", theta_dot_rad_s)
        omega = _require_finite_state("omega", omega_rad_s)
        if abs(theta) >= FOLD_LIMIT_RAD or omega < OMEGA_MIN:
            raise Cmm2DomainExit(
                "CMM-2 aerodynamic source was not evaluated outside the screening domain."
            )
        index = self.successful_bem_solves
        state = FoldableRotorState(
            id=f"cmm2-{index}",
            hinge_radius_m=self.hinge_radius_m,
            opening_angle_rad=theta,
            deployed_angle_rad=0.0,
        )
        condition = OperatingCondition(
            id=f"cmm2-{self.environment.id}",
            angular_speed_rad_s=omega,
            forward_speed_m_s=self.environment.forward_speed_m_s,
            air_density_kg_m3=self.environment.air_density_kg_m3,
            dynamic_viscosity_pa_s=self.environment.dynamic_viscosity_pa_s,
            temperature_k=self.environment.temperature_k,
            pressure_pa=self.environment.pressure_pa,
        )
        try:
            bem_result = solve_foldable_bem_rotor(
                self.blade,
                state,
                condition,
                self.polars,
                bounds=self.bounds,
                settings=self.settings,
            )
        except _AERO_FAILURES as exc:
            raise Cmm2TransientFailure(_AERO_SOURCE_FAILURE) from exc
        try:
            bem_mapping = bem_result.as_mapping()
            raw_torque = float(bem_result.rotor_result.torque_nm)
        except (AttributeError, TypeError, ValueError) as exc:
            raise Cmm2TransientFailure(_AERO_SOURCE_FAILURE) from exc
        if not isinstance(bem_mapping, Mapping) or not math.isfinite(raw_torque):
            raise Cmm2TransientFailure(_AERO_SOURCE_FAILURE)
        try:
            mapped = map_foldable_bem_aero_loads(
                bem_result,
                hinge_rate_rad_s=theta_dot,
            )
        except _AERO_FAILURES as exc:
            raise Cmm2TransientFailure(_AERO_SOURCE_FAILURE) from exc
        if not isinstance(mapped, PlanarProjectedMaterialLoadResult):
            raise Cmm2TransientFailure(_AERO_SOURCE_FAILURE)
        if (
            mapped.theta_rad != theta
            or mapped.hinge_rate_rad_s != theta_dot
            or mapped.hinge_radius_m != self.hinge_radius_m
            or mapped.blade_count != self.blade.blade_count
        ):
            raise Cmm2TransientFailure(
                "CMM-2 refused a mapped load from a different state."
            )
        try:
            mapped_json = _canonical_json(
                dict(mapped.as_mapping()),
                Cmm2TransientFailure,
                _AERO_SOURCE_FAILURE,
            )
            bem_json = _canonical_json(
                dict(bem_mapping),
                Cmm2TransientFailure,
                _AERO_SOURCE_FAILURE,
            )
            provenance_json = _canonical_json(
                _bem_provenance(bem_mapping),
                Cmm2TransientFailure,
                _AERO_SOURCE_FAILURE,
            )
        except Cmm2TransientFailure:
            raise
        mapped_sha = _sha256(mapped_json)
        source_id = f"cmm2-planar-map:{index}:{mapped_sha}"
        try:
            evaluation = Cmm2AeroEvaluation(
                whole_rotor_shaft_generalized_load_nm=(
                    mapped.whole_rotor_aerodynamic_shaft_generalized_load_nm
                ),
                one_tip_hinge_generalized_load_nm=(
                    mapped.one_tip_hinge_generalized_torque_nm
                ),
                thrust_n=mapped.source_whole_rotor_projected_thrust_n,
                load_mapping_model=mapped.load_mapping_model,
                qualification=mapped.qualification,
                projection_model=mapped.projection_model,
                hinge_rate_aerodynamic_model=mapped.hinge_rate_aerodynamic_model,
                blade_count=mapped.blade_count,
                hinge_radius_m=mapped.hinge_radius_m,
                theta_rad=mapped.theta_rad,
                hinge_rate_rad_s=mapped.hinge_rate_rad_s,
                source_id=source_id,
            )
            evaluation_power = evaluation.generalized_power_w(omega)
            mapped_power = mapped.aerodynamic_generalized_power_w(omega)
        except (Cmm2TransientError, Cmm2TransientFailure, PlanarProjectedMaterialLoadError) as exc:
            raise Cmm2TransientFailure(_AERO_SOURCE_FAILURE) from exc
        if evaluation_power != mapped_power:
            raise Cmm2TransientFailure(
                "CMM-2 aerodynamic power does not match the mapped load."
            )
        record = Cmm2AeroProvenanceRecord(
            evaluation_index=index,
            absolute_time_s=absolute_time,
            theta_rad=theta,
            hinge_rate_rad_s=theta_dot,
            omega_rad_s=omega,
            source_id=source_id,
            mapped_load_sha256=mapped_sha,
            bem_result_sha256=_sha256(bem_json),
            whole_rotor_shaft_generalized_load_nm=(
                evaluation.whole_rotor_shaft_generalized_load_nm
            ),
            one_tip_hinge_generalized_load_nm=(
                evaluation.one_tip_hinge_generalized_load_nm
            ),
            thrust_n=evaluation.thrust_n,
            source_whole_rotor_resisting_torque_nm=(
                mapped.source_whole_rotor_resisting_torque_nm
            ),
            raw_bem_resisting_torque_nm_not_used_as_cmm2_generalized_load=raw_torque,
            synchronous_n_times_one_tip_hinge_generalized_torque_nm=(
                mapped.synchronous_n_times_one_tip_hinge_generalized_torque_nm
            ),
            collective_hinge_field_fed_to_dynamics=False,
            blade_count=mapped.blade_count,
            hinge_radius_m=mapped.hinge_radius_m,
            projection_factor=mapped.projection_factor,
            projected_tip_radius_m=mapped.projected_tip_radius_m,
            source_outer_projected_radius_m=mapped.source_outer_projected_radius_m,
            source_terminal_radius_m=mapped.source_terminal_radius_m,
            terminal_boundary_normalized=mapped.terminal_boundary_normalized,
            terminal_boundary_delta_m=mapped.terminal_boundary_delta_m,
            operating_condition_id=mapped.operating_condition_id,
            polar_schedule_id=mapped.polar_schedule_id,
            airfoil_id=mapped.airfoil_id,
            scenario_id=mapped.scenario_id,
            polar_sources=tuple(mapped.polar_sources),
            radial_domain=mapped.radial_domain,
            geometry_extended=mapped.geometry_extended,
            load_mapping_model=mapped.load_mapping_model,
            qualification=mapped.qualification,
            projection_model=mapped.projection_model,
            hinge_rate_aerodynamic_model=mapped.hinge_rate_aerodynamic_model,
            physical_qualification=mapped.physical_qualification,
            distributed_couple_model=mapped.distributed_couple_model,
            sectional_aerodynamic_couple=mapped.sectional_aerodynamic_couple,
            schema_version=mapped.schema_version,
            bem_settings_json=_canonical_json(
                dict(mapped.bem_settings),
                Cmm2TransientFailure,
                _AERO_SOURCE_FAILURE,
            ),
            mapped_load_json=mapped_json,
            bem_provenance_json=provenance_json,
        )
        self.provenance_records.append(record)
        self.successful_bem_solves += 1
        self.successful_map_calls += 1
        return evaluation


def assert_cmm2_production_evaluators(motor: object, aero: object) -> None:
    """Reject analytic callbacks before a source-bound artifact is built."""
    if type(motor) is not Pr07MotorEvaluator or type(aero) is not Cmm2FoldableBemMappedAeroEvaluator:
        raise Cmm2CoupledBindingError(
            "Source-bound CMM-2 accepts only the PR-07 motor law and the foldable BEM planar-map evaluator."
        )


@dataclass(frozen=True)
class Cmm2CoupledBinding:
    """Sealed inputs. The hash identifies content, not authenticity or qualification."""

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
class Cmm2CoupledArtifact:
    report_json: str
    report_sha256: str
    input_sha256: str
    result: Cmm2TransientResult


@dataclass(frozen=True)
class _BuiltRequest:
    request: Cmm2TransientRequest
    motor_evaluator: Pr07MotorEvaluator
    aero_evaluator: Cmm2FoldableBemMappedAeroEvaluator


def _input_payload(binding: Cmm2CoupledBinding) -> dict[str, object]:
    if binding.base_inertia.excludes_modeled_movable_tips is not True:
        raise Cmm2CoupledBindingError("I0 must exclude every modeled movable tip.")
    try:
        design, parameters = _parameters(
            binding.draft,
            binding.distribution,
            binding.initial_angle_rad,
            binding.spring_stiffness_nm_rad,
            binding.rest_angle_rad,
            binding.viscous_damping_nm_s_rad,
            binding.dry_friction,
        )
        polars = _polar_identity(binding.polars)
    except CoupledBindingError as exc:
        raise _binding_error(exc) from exc
    return {
        "schema_version": SCHEMA_VERSION,
        "service_id": SERVICE_ID,
        "service_implementation_id": SERVICE_IMPLEMENTATION_ID,
        "dynamics_implementation_id": DYNAMICS_IMPLEMENTATION_ID,
        "model_class": MODEL_CLASS,
        "physical_qualification": False,
        "aero_load_status": AERO_LOAD_STATUS,
        "full_propeller_clearance": None,
        "surface_path_clearance": None,
        "interblade_clearance": None,
        "aero_evaluator_id": AERO_EVALUATOR_ID,
        "motor_binding": {
            "law": "pr07_algebraic",
            "canonical_id": Pr07MotorEvaluator.canonical_id,
            "dynamic_current_state": False,
            "regeneration": False,
        },
        "planar_load_contract": _planar_contract(),
        "hash_identity_scope": _HASH_SCOPE,
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
        "polars": polars,
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


def _build_cmm2_request(binding: Cmm2CoupledBinding) -> _BuiltRequest:
    try:
        design, parameters = _parameters(
            binding.draft,
            binding.distribution,
            binding.initial_angle_rad,
            binding.spring_stiffness_nm_rad,
            binding.rest_angle_rad,
            binding.viscous_damping_nm_s_rad,
            binding.dry_friction,
        )
        motor = Pr07MotorEvaluator(
            binding.motor, binding.battery, binding.system, binding.throttle
        )
    except CoupledBindingError as exc:
        raise _binding_error(exc) from exc
    aero = Cmm2FoldableBemMappedAeroEvaluator(
        design.blade,
        binding.polars,
        binding.bem_settings,
        binding.environment,
        parameters.hinge_radius_m,
        binding.bounds,
    )
    assert_cmm2_production_evaluators(motor, aero)
    try:
        request = Cmm2TransientRequest(
            CoupledSystem(parameters, design.blade.blade_count, binding.base_inertia),
            binding.actuation,
            binding.initial_angle_rad,
            binding.initial_angular_velocity_rad_s,
            binding.initial_omega_rad_s,
            motor,
            aero,
            binding.controls,
        )
    except Cmm2TransientError as exc:
        raise Cmm2CoupledBindingError(str(exc)) from exc
    return _BuiltRequest(request, motor, aero)


def validate_cmm2_coupled_binding(binding: Cmm2CoupledBinding) -> None:
    if not isinstance(binding, Cmm2CoupledBinding):
        raise Cmm2CoupledBindingError("Expected a sealed CMM-2 binding.")
    payload = _canonical_json(
        _input_payload(binding),
        Cmm2CoupledBindingError,
        "CMM-2 context must contain finite JSON-safe data.",
    )
    if payload != binding.context_json or _sha256(payload) != binding.input_sha256:
        raise Cmm2CoupledBindingError("Binding identity does not match the sealed inputs.")


def prepare_cmm2_coupled_transient(
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
) -> Cmm2CoupledBinding:
    """Seal one source-bound CMM-2 problem without integrating it."""
    if not isinstance(base_inertia, BaseRotatingAssemblyInertia):
        raise Cmm2CoupledBindingError("base_inertia must be BaseRotatingAssemblyInertia.")
    if not isinstance(actuation, HingeActuationHistory):
        raise Cmm2CoupledBindingError(
            "actuation must be a hinge history, not a prescribed RPM drive."
        )
    if not isinstance(environment, CoupledEnvironment):
        raise Cmm2CoupledBindingError("environment must be a CoupledEnvironment.")
    if not isinstance(bem_settings, BEMRotorSettings):
        raise Cmm2CoupledBindingError("bem_settings must be explicit.")
    if not isinstance(controls, CoupledSolverControls):
        raise Cmm2CoupledBindingError("controls must be CoupledSolverControls.")
    if not isinstance(dry_friction, DryFriction):
        raise Cmm2CoupledBindingError("dry_friction must be a DryFriction contract.")
    if not isinstance(mechanical_source, str) or not mechanical_source.strip():
        raise Cmm2CoupledBindingError("mechanical_source must be nonempty.")
    if bounds != "error":
        raise Cmm2CoupledBindingError('CMM-2 requires polar bounds = "error".')
    try:
        _validate_electrical(motor, battery, system, throttle)
    except CoupledBindingError as exc:
        raise _binding_error(exc) from exc
    binding = Cmm2CoupledBinding(
        draft=draft,
        distribution=distribution,
        base_inertia=base_inertia,
        spring_stiffness_nm_rad=_finite("spring_stiffness_nm_rad", spring_stiffness_nm_rad),
        rest_angle_rad=_finite("rest_angle_rad", rest_angle_rad),
        viscous_damping_nm_s_rad=_finite(
            "viscous_damping_nm_s_rad", viscous_damping_nm_s_rad
        ),
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
    payload = _canonical_json(
        _input_payload(binding),
        Cmm2CoupledBindingError,
        "CMM-2 context must contain finite JSON-safe data.",
    )
    sealed = Cmm2CoupledBinding(
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
        input_sha256=_sha256(payload),
    )
    _build_cmm2_request(sealed)
    return sealed


def _result_document(result: Cmm2TransientResult) -> dict[str, object]:
    """Serialize every CMM-2 result field without changing its value."""
    document = asdict(result)
    if document.get("physical_qualification") is not False:
        raise Cmm2TransientFailure("CMM-2 invariant broken: physical qualification was set.")
    if document.get("limitations") != result.limitations:
        raise Cmm2TransientFailure("CMM-2 result serialization changed a limitation.")
    return document


# First-party sources whose executable model, binding, calculation, acceptance,
# or numerical logic materially defines the source-bound screening service.
# This is a reviewed list, not an import-graph walk and not a hash of SciPy,
# NumPy, or another external library. folding_mechanism.py can reject the
# binding. airfoil.py can reject a draft that carries inline coordinates.
_IMPLEMENTATION_FILE_MANIFEST: tuple[str, ...] = (
    "pyfoldable/application/cmm2_coupled_transient_service.py",
    "pyfoldable/application/coupled_transient_service.py",
    "pyfoldable/application/mechanism_binding.py",
    "pyfoldable/application/folding_mechanism.py",
    "pyfoldable/dynamics/cmm2_coupled_transient.py",
    "pyfoldable/dynamics/cmm2_radau_dense.py",
    "pyfoldable/dynamics/coupled_transient.py",
    "pyfoldable/dynamics/mechanism_transient.py",
    "pyfoldable/dynamics/mechanism_contracts.py",
    "pyfoldable/core/foldable_aero_load.py",
    "pyfoldable/core/foldable_rotor.py",
    "pyfoldable/core/bem_rotor.py",
    "pyfoldable/core/bem.py",
    "pyfoldable/core/polar.py",
    "pyfoldable/core/polar_spanwise.py",
    "pyfoldable/core/rotational_augmentation.py",
    "pyfoldable/core/models.py",
    "pyfoldable/core/motor_bem_coupling.py",
    "pyfoldable/core/config.py",
    "pyfoldable/core/units.py",
    "pyfoldable/core/airfoil.py",
    "pythrust/propulsion/models.py",
)


def _raw_manifest_parts(relative: object) -> tuple[str, ...]:
    """Reject unsafe keys before pathlib can collapse them."""
    if (
        not isinstance(relative, str)
        or not relative
        or "\\" in relative
        or relative.startswith("/")
    ):
        raise Cmm2TransientFailure(
            "CMM-2 implementation manifest path is not repository-relative."
        )
    raw_parts = relative.split("/")
    if any(part in {"", ".", ".."} or ":" in part for part in raw_parts):
        raise Cmm2TransientFailure(
            "CMM-2 implementation manifest path is not repository-relative."
        )
    return tuple(raw_parts)


def _manifest_file(repository_root: Path, relative: object) -> Path:
    raw_parts = _raw_manifest_parts(relative)
    parsed = Path(relative)
    if parsed.is_absolute() or parsed.drive:
        raise Cmm2TransientFailure(
            "CMM-2 implementation manifest path is not repository-relative."
        )
    candidate = repository_root
    for part in raw_parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise Cmm2TransientFailure(
                "CMM-2 implementation manifest path contains a symlink."
            )
    if not candidate.is_file():
        raise Cmm2TransientFailure(f"CMM-2 implementation file is missing: {relative}")
    resolved_root = repository_root.resolve()
    resolved = candidate.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise Cmm2TransientFailure(
            "CMM-2 implementation manifest path is not repository-relative."
        )
    return candidate


def _implementation_files() -> dict[str, str]:
    """Hash the reviewed manifest. An unsafe or missing path fails closed."""
    repository_root = Path(__file__).resolve().parents[2]
    manifest = _IMPLEMENTATION_FILE_MANIFEST
    if len(manifest) != len(set(manifest)):
        raise Cmm2TransientFailure("CMM-2 implementation manifest contains a duplicate path.")
    digests: dict[str, str] = {}
    for relative in manifest:
        path = _manifest_file(repository_root, relative)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise Cmm2TransientFailure(
                f"CMM-2 implementation file is missing: {relative}"
            ) from exc
        digests[relative] = hashlib.sha256(payload).hexdigest()
    return digests


def _assert_result_provenance(
    result: Cmm2TransientResult,
    aero: Cmm2FoldableBemMappedAeroEvaluator,
) -> None:
    if result.physical_qualification is not False:
        raise Cmm2TransientFailure("CMM-2 invariant broken: physical qualification was set.")
    if (
        result.full_propeller_clearance is not None
        or result.surface_path_clearance is not None
        or result.interblade_clearance is not None
    ):
        raise Cmm2TransientFailure("CMM-2 invariant broken: a clearance value was set.")
    if not (
        aero.successful_bem_solves
        == aero.successful_map_calls
        == len(aero.provenance_records)
        == result.aero_evaluations
    ):
        raise Cmm2TransientFailure("CMM-2 aerodynamic provenance count is inconsistent.")
    by_id: dict[str, Cmm2AeroProvenanceRecord] = {}
    for record in aero.provenance_records:
        if record.source_id in by_id:
            raise Cmm2TransientFailure("CMM-2 aerodynamic source id is not unique.")
        by_id[record.source_id] = record
    for sample in result.samples:
        record = by_id.get(sample.aero_source_id)
        if record is None:
            raise Cmm2TransientFailure(
                "CMM-2 sample aerodynamic source does not resolve to the provenance ledger."
            )
        collective = record.blade_count * record.one_tip_hinge_generalized_load_nm
        if (
            record.theta_rad != sample.theta_rad
            or record.hinge_rate_rad_s != sample.theta_dot_rad_s
            or record.omega_rad_s != sample.omega_rad_s
            or record.whole_rotor_shaft_generalized_load_nm
            != sample.aero_shaft_generalized_load_nm
            or record.one_tip_hinge_generalized_load_nm
            != sample.aero_one_tip_hinge_generalized_load_nm
            or record.thrust_n != sample.aero_thrust_n
            or collective != sample.aero_collective_hinge_generalized_load_nm
        ):
            raise Cmm2TransientFailure(
                "CMM-2 sample does not match its mapped aerodynamic provenance."
            )


def run_cmm2_coupled_transient(
    binding: Cmm2CoupledBinding,
    *,
    expected_input_sha256: str | None = None,
) -> Cmm2CoupledArtifact:
    """Integrate a sealed binding. Hard failures do not return a success artifact."""
    validate_cmm2_coupled_binding(binding)
    if expected_input_sha256 is not None and expected_input_sha256 != binding.input_sha256:
        raise Cmm2CoupledBindingError("Binding identity does not match the requested seal.")
    built = _build_cmm2_request(binding)
    result = solve_cmm2_transient(built.request)
    _assert_result_provenance(result, built.aero_evaluator)
    request = json.loads(binding.context_json)
    report = {
        "schema_version": SCHEMA_VERSION,
        "service_id": SERVICE_ID,
        "service_implementation_id": SERVICE_IMPLEMENTATION_ID,
        "dynamics_implementation_id": DYNAMICS_IMPLEMENTATION_ID,
        "model_class": MODEL_CLASS,
        "physical_qualification": False,
        "aero_load_status": AERO_LOAD_STATUS,
        "full_propeller_clearance": None,
        "surface_path_clearance": None,
        "interblade_clearance": None,
        "aero_evaluator_id": AERO_EVALUATOR_ID,
        "motor_evaluator_id": Pr07MotorEvaluator.canonical_id,
        "motor_binding": request["motor_binding"],
        "planar_load_contract": request["planar_load_contract"],
        "hash_identity_scope": _HASH_SCOPE,
        "source_identity_scope": request["source_identity_scope"],
        "implementation_files_sha256": _implementation_files(),
        "input_sha256": binding.input_sha256,
        "request": request,
        "draft_sha256": binding.draft.draft_sha256,
        "source_sha256": binding.draft.source_sha256,
        "base_rotating_inertia": request["base_rotating_inertia"],
        "bounds": binding.bounds,
        "bem_settings": request["bem_settings"],
        "loading_branch": binding.bem_settings.annulus_settings.loading_branch,
        "successful_bem_solves": built.aero_evaluator.successful_bem_solves,
        "successful_map_calls": built.aero_evaluator.successful_map_calls,
        "aero_evaluations": result.aero_evaluations,
        "aero_evaluation_count": result.aero_evaluations,
        "aero_evaluation_ledger": [
            record.as_mapping() for record in built.aero_evaluator.provenance_records
        ],
        "result": _result_document(result),
    }
    report_json = _canonical_json(
        report,
        Cmm2TransientFailure,
        "CMM-2 report must contain finite JSON-safe data.",
    )
    return Cmm2CoupledArtifact(
        report_json=report_json,
        report_sha256=_sha256(report_json),
        input_sha256=binding.input_sha256,
        result=result,
    )
