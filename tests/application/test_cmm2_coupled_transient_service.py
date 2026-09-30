"""Source-bound CMM-2 production binding."""

from __future__ import annotations

import hashlib
import inspect
import json
import math
from pathlib import Path

import pytest

import pyfoldable.application.cmm2_coupled_transient_service as cmm2_service
from pyfoldable.application.cmm2_coupled_transient_service import (
    AERO_EVALUATOR_ID,
    SERVICE_ID,
    SERVICE_IMPLEMENTATION_ID,
    Cmm2CoupledBindingError,
    Cmm2FoldableBemMappedAeroEvaluator,
    assert_cmm2_production_evaluators,
    prepare_cmm2_coupled_transient,
    run_cmm2_coupled_transient,
    validate_cmm2_coupled_binding,
)
from pyfoldable.application.coupled_transient_service import (
    CoupledEnvironment,
    Pr07MotorEvaluator,
)
from pyfoldable.application.design_draft import DesignDraftInputs, build_design_draft
from pyfoldable.application.mechanism_binding import (
    RadialMassSample,
    TipMassDistribution,
    _load_draft,
)
from pyfoldable.core.bem import BEMAnnulusError, BEMAnnulusSettings, BEMConvergenceError
from pyfoldable.core.bem_rotor import BEMRotorElementError, BEMRotorError, BEMRotorSettings
from pyfoldable.core.foldable_aero_load import (
    DISTRIBUTED_COUPLE_MODEL,
    HINGE_RATE_AERODYNAMIC_MODEL,
    LOAD_MAPPING_MODEL,
    PLANAR_PROJECTED_MATERIAL_LOAD_SCHEMA_VERSION,
    PROJECTION_MODEL,
    QUALIFICATION,
    SECTIONAL_AERODYNAMIC_COUPLE,
    MappedRadialContribution,
    PlanarProjectedMaterialLoadError,
    PlanarProjectedMaterialLoadResult,
    map_foldable_bem_aero_loads,
)
from pyfoldable.core.foldable_rotor import (
    FoldableRotorGeometryError,
    solve_foldable_bem_rotor,
)
from pyfoldable.core.models import BladeGeometry, BladeStation
from pyfoldable.core.motor_bem_coupling import algebraic_motor_state
from pyfoldable.core.polar import PolarFamily, PolarInterpolationError, PolarTable
from pyfoldable.core.polar_spanwise import SpanwisePolarAnchor, SpanwisePolarSchedule
from pyfoldable.dynamics.cmm2_coupled_transient import (
    IMPLEMENTATION_ID,
    MODEL_CLASS,
    Cmm2DomainExit,
    Cmm2TransientFailure,
    Cmm2TransientRequest,
    solve_cmm2_transient,
)
from pyfoldable.dynamics.coupled_transient import (
    BaseRotatingAssemblyInertia,
    CoupledSolverControls,
    HingeActuationHistory,
)
from pyfoldable.dynamics.mechanism_contracts import DryFriction
from pythrust.propulsion.models import BatterySpec, MotorSpec, SystemSpec


ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "configs/designs/TIP_HINGED_250_CANONICAL.toml"
MOTOR = MotorSpec(1000.0, 0.05, 1.0, 80.0)
BATTERY = BatterySpec(12.0, 0.98)
SYSTEM = SystemSpec(0.01)
RAW_TORQUE = 1.7
RAW_THRUST = 3.3
SHAFT = -0.0137
ONE_TIP = 0.00021
COLLECTIVE = 4.2
THRUST = 0.42
RESISTING = 9.9
SERVICE = "pyfoldable.application.cmm2_coupled_transient_service"


def _draft():
    return build_design_draft(
        CANONICAL,
        DesignDraftInputs(
            diameter="220 mm",
            hub_radius="16 mm",
            hinge_radius="85 mm",
            blade_count=3,
            airfoil_id="NACA0012",
            chord_scale=1.0,
            twist_scale=1.0,
            preview_fold_angle="-60 deg",
            angular_speed="4000 rpm",
            forward_speed="4 m/s",
            air_density="1.18 kg/m^3",
            dynamic_viscosity="1.79e-5 Pa*s",
            temperature="20 degC",
            pressure="100 kPa",
        ),
    )


def _mass(distance: float = 0.01, mass: float = 0.01) -> TipMassDistribution:
    return TipMassDistribution(
        (RadialMassSample(distance, mass, "synthetic tip mass"),),
        "synthetic-tip",
        "synthetic_test_fixture",
    )


def _family(cl: float, source: str = "cmm2-fixture", metadata: dict | None = None) -> PolarFamily:
    return PolarFamily(
        (
            PolarTable(
                airfoil_id="NACA0012",
                scenario_id="cmm2",
                reynolds=1.0e5,
                mach=0.0,
                alpha_rad=(-0.5, 0.5),
                cl=(cl, cl),
                cd=(0.02, 0.02),
                cm=(0.0, 0.0),
                source=source,
                metadata={} if metadata is None else metadata,
            ),
        )
    )


def _schedule(cl: float = 0.6, metadata: dict | None = None, source: str = "cmm2-fixture"):
    family = _family(cl, source=source, metadata=metadata)
    return SpanwisePolarSchedule(
        "cmm2-span",
        (
            SpanwisePolarAnchor(0.2, family),
            SpanwisePolarAnchor(1.0, family),
        ),
    )


def _settings(branch: str = "positive_only", annulus_count: int = 4) -> BEMRotorSettings:
    return BEMRotorSettings(
        annulus_count=annulus_count,
        annulus_settings=BEMAnnulusSettings(bracket_samples=16, loading_branch=branch),
    )


def _binding(**overrides):
    values = dict(
        draft=_draft(),
        distribution=_mass(),
        base_inertia=BaseRotatingAssemblyInertia(
            1.0e-4,
            "fixture inertia",
            ("motor rotor", "shaft", "hub", "fixed blade roots"),
        ),
        spring_stiffness_nm_rad=0.0,
        rest_angle_rad=-0.2,
        viscous_damping_nm_s_rad=0.0,
        initial_angle_rad=-0.2,
        initial_angular_velocity_rad_s=0.0,
        initial_omega_rad_s=400.0 * math.pi / 30.0,
        actuation=HingeActuationHistory((0.0, 0.004), (0.0, 0.0), "no actuation"),
        motor=MOTOR,
        battery=BATTERY,
        system=SYSTEM,
        throttle=0.1,
        environment=CoupledEnvironment("screen", 4.0, 1.18, 1.79e-5, 293.15, 100000.0),
        polars=_schedule(),
        bem_settings=_settings(),
        bounds="error",
        mechanical_source="explicit fixture",
    )
    values.update(overrides)
    return prepare_cmm2_coupled_transient(**values)


def _mapped(result, hinge_rate_rad_s: float, *, normalized: bool) -> PlanarProjectedMaterialLoadResult:
    theta = result.state.angle_from_deployed_rad
    hinge = result.state.hinge_radius_m
    tip = hinge + 0.02
    if normalized:
        terminal = math.nextafter(tip, 0.0)
        delta = tip - terminal
    else:
        terminal = tip
        delta = 0.0
    factor = math.cos(theta)
    return PlanarProjectedMaterialLoadResult(
        schema_version=PLANAR_PROJECTED_MATERIAL_LOAD_SCHEMA_VERSION,
        load_mapping_model=LOAD_MAPPING_MODEL,
        projection_model=PROJECTION_MODEL,
        qualification=QUALIFICATION,
        physical_qualification=False,
        distributed_couple_model=DISTRIBUTED_COUPLE_MODEL,
        hinge_rate_aerodynamic_model=HINGE_RATE_AERODYNAMIC_MODEL,
        sectional_aerodynamic_couple=SECTIONAL_AERODYNAMIC_COUPLE,
        blade_count=result.blade.blade_count,
        hinge_radius_m=hinge,
        theta_rad=theta,
        hinge_rate_rad_s=hinge_rate_rad_s,
        projection_factor=factor,
        projected_tip_radius_m=tip,
        operating_condition_id=result.condition.id,
        bem_settings=dict(result.settings.as_mapping()),
        polar_schedule_id="cmm2-span",
        airfoil_id="NACA0012",
        scenario_id="cmm2",
        polar_sources=("cmm2-fixture",),
        radial_domain="station_span",
        geometry_extended=False,
        source_inner_projected_radius_m=hinge,
        source_outer_projected_radius_m=tip,
        source_terminal_radius_m=terminal,
        terminal_boundary_normalized=normalized,
        terminal_boundary_delta_m=delta,
        intervals=(
            MappedRadialContribution(
                role="movable_tip",
                source_index=0,
                inner_projected_radius_m=hinge,
                outer_projected_radius_m=tip,
                source_differential_thrust_n_m=0.0,
                source_differential_torque_nm_m=0.0,
                whole_rotor_thrust_n=THRUST,
                whole_rotor_resisting_torque_nm=RESISTING,
                one_blade_shaft_generalized_load_nm=SHAFT / result.blade.blade_count,
                one_tip_hinge_generalized_torque_nm=ONE_TIP,
                geometry_extrapolated=False,
            ),
        ),
        source_whole_rotor_projected_thrust_n=THRUST,
        source_whole_rotor_resisting_torque_nm=RESISTING,
        whole_rotor_aerodynamic_shaft_generalized_load_nm=SHAFT,
        resisting_shaft_torque_nm=-SHAFT,
        one_tip_hinge_generalized_torque_nm=ONE_TIP,
        synchronous_n_times_one_tip_hinge_generalized_torque_nm=COLLECTIVE,
    )


class _FakeBem:
    def __init__(self, blade, state, condition, settings, bounds):
        self.blade = blade
        self.state = state
        self.condition = condition
        self.settings = settings
        self.bounds = bounds
        self.rotor_result = type(
            "Rotor",
            (),
            {"torque_nm": RAW_TORQUE, "thrust_n": RAW_THRUST},
        )()

    def as_mapping(self):
        return {
            "schema_version": 1,
            "state": {
                "id": self.state.id,
                "hinge_radius_m": self.state.hinge_radius_m,
                "opening_angle_rad": self.state.opening_angle_rad,
                "deployed_angle_rad": self.state.deployed_angle_rad,
                "angle_from_deployed_rad": self.state.angle_from_deployed_rad,
            },
            "projection_factor": math.cos(self.state.angle_from_deployed_rad),
            "polar_schedule_id": "cmm2-span",
            "rotor_result": {
                "operating_condition_id": self.condition.id,
                "airfoil_id": "NACA0012",
                "scenario_id": "cmm2",
                "radial_domain": "station_span",
                "geometry_extended": False,
                "settings": dict(self.settings.as_mapping()),
                "polar_sources": ["cmm2-fixture"],
                "torque_nm": RAW_TORQUE,
                "thrust_n": RAW_THRUST,
                "annulus_count": self.settings.annulus_count,
                "polar_bounds": self.bounds,
            },
        }


def _install(monkeypatch, *, fail=None, normalized: bool = False):
    returned = []
    received = []
    observed = []

    def fake_solve(blade, state, condition, polars, *, bounds="error", settings=None):
        del polars
        observed.append(
            {
                "bounds": bounds,
                "loading_branch": settings.annulus_settings.loading_branch,
                "omega": condition.angular_speed_rad_s,
                "theta": state.opening_angle_rad,
            }
        )
        if fail == "bem":
            raise BEMConvergenceError("unconverged")
        if isinstance(fail, BaseException):
            raise fail
        value = _FakeBem(blade, state, condition, settings, bounds)
        returned.append(value)
        return value

    def fake_map(result, *, hinge_rate_rad_s):
        received.append(result)
        if fail == "map":
            raise PlanarProjectedMaterialLoadError(
                "terminal boundary provenance is outside the native ULP envelope."
            )
        return _mapped(result, hinge_rate_rad_s, normalized=normalized)

    monkeypatch.setattr(f"{SERVICE}.solve_foldable_bem_rotor", fake_solve)
    monkeypatch.setattr(f"{SERVICE}.map_foldable_bem_aero_loads", fake_map)
    return returned, received, observed


def test_production_api_rejects_callbacks() -> None:
    assert "aero_evaluator" not in inspect.signature(prepare_cmm2_coupled_transient).parameters
    assert "motor_evaluator" not in inspect.signature(run_cmm2_coupled_transient).parameters
    assert "aero_evaluator" not in inspect.signature(solve_cmm2_transient).parameters
    assert "aero_evaluator" in Cmm2TransientRequest.__dataclass_fields__
    with pytest.raises(Cmm2CoupledBindingError, match="PR-07"):
        assert_cmm2_production_evaluators(lambda *_args: None, lambda *_args: None)
    binding = _binding()
    motor = Pr07MotorEvaluator(binding.motor, binding.battery, binding.system, binding.throttle)
    with pytest.raises(Cmm2CoupledBindingError):
        assert_cmm2_production_evaluators(motor, lambda *_args: None)


def test_same_returned_object_is_mapped_once_per_successful_bem(monkeypatch) -> None:
    returned, received, observed = _install(monkeypatch)
    artifact = run_cmm2_coupled_transient(_binding())
    assert returned
    assert len(returned) == len(received) == len(observed)
    assert all(left is right for left, right in zip(returned, received))
    document = json.loads(artifact.report_json)
    assert (
        document["successful_bem_solves"]
        == document["successful_map_calls"]
        == len(document["aero_evaluation_ledger"])
        == artifact.result.aero_evaluations
        == len(returned)
    )
    assert all(row["bounds"] == "error" for row in observed)


def test_mapped_fields_are_not_raw_torque_or_collective_hinge(monkeypatch) -> None:
    _install(monkeypatch)
    artifact = run_cmm2_coupled_transient(_binding())
    document = json.loads(artifact.report_json)
    for sample in document["result"]["samples"]:
        assert sample["aero_shaft_generalized_load_nm"] == SHAFT
        assert sample["aero_shaft_generalized_load_nm"] != RAW_TORQUE
        assert sample["aero_shaft_generalized_load_nm"] != RESISTING
        assert sample["aero_one_tip_hinge_generalized_load_nm"] == ONE_TIP
        assert sample["aero_one_tip_hinge_generalized_load_nm"] != COLLECTIVE
        assert sample["aero_collective_hinge_generalized_load_nm"] == ONE_TIP * 3
        assert sample["aero_collective_hinge_generalized_load_nm"] != COLLECTIVE
        assert sample["aero_thrust_n"] == THRUST
        assert sample["aero_thrust_n"] != RAW_THRUST
        expected_power = SHAFT * sample["omega_rad_s"] + 3 * ONE_TIP * sample["theta_dot_rad_s"]
        assert sample["aero_generalized_power_w"] == expected_power
    for row in document["aero_evaluation_ledger"]:
        assert row["raw_bem_resisting_torque_nm_not_used_as_cmm2_generalized_load"] == RAW_TORQUE
        assert row["source_whole_rotor_projected_thrust_n"] == THRUST
        assert row["source_whole_rotor_resisting_torque_nm"] == RESISTING
        assert row["distributed_couple_model"] == DISTRIBUTED_COUPLE_MODEL
        assert row["sectional_aerodynamic_couple"] == SECTIONAL_AERODYNAMIC_COUPLE
        assert row["physical_qualification"] is False
        assert "torque_nm" not in row
        assert "source_bem_rotor_torque_nm" not in row
        assert row["collective_hinge_field_fed_to_dynamics"] is False
        assert row["synchronous_n_times_one_tip_hinge_generalized_torque_nm"] == COLLECTIVE
        assert row["whole_rotor_shaft_generalized_load_nm"] == SHAFT


def test_source_id_is_deterministic_and_changes_with_mapped_content(monkeypatch) -> None:
    _install(monkeypatch)
    binding = _binding()
    built = _evaluator(binding)
    omega = 400.0 * math.pi / 30.0
    first = built(0.0, -0.2, 0.0, omega)
    second = built(0.0, -0.2, 0.0, omega)
    third = built(0.0, -0.1, 0.05, omega)
    records = built.provenance_records
    assert first.source_id == f"cmm2-planar-map:0:{records[0].mapped_load_sha256}"
    assert second.source_id != first.source_id
    assert records[0].mapped_load_sha256 == records[1].mapped_load_sha256
    assert records[2].mapped_load_sha256 != records[0].mapped_load_sha256
    assert third.source_id.endswith(records[2].mapped_load_sha256)
    again = _evaluator(binding)
    repeat = again(0.0, -0.2, 0.0, omega)
    assert repeat.source_id == first.source_id


def _blade_from_binding(binding):
    return _load_draft(binding.draft).blade


def _evaluator(binding) -> Cmm2FoldableBemMappedAeroEvaluator:
    return Cmm2FoldableBemMappedAeroEvaluator(
        _blade_from_binding(binding),
        binding.polars,
        binding.bem_settings,
        binding.environment,
        0.085,
        "error",
    )


def test_seal_tracks_declared_inputs() -> None:
    baseline = _binding()
    assert _binding().input_sha256 == baseline.input_sha256
    request = json.loads(baseline.context_json)
    assert request["service_id"] == SERVICE_ID
    assert request["service_implementation_id"] == SERVICE_IMPLEMENTATION_ID
    assert request["dynamics_implementation_id"] == IMPLEMENTATION_ID
    contract = request["planar_load_contract"]
    assert contract["schema_version"] == PLANAR_PROJECTED_MATERIAL_LOAD_SCHEMA_VERSION
    assert contract["load_mapping_model"] == LOAD_MAPPING_MODEL
    assert contract["projection_model"] == PROJECTION_MODEL
    assert contract["qualification"] == QUALIFICATION
    assert contract["distributed_couple_model"] == DISTRIBUTED_COUPLE_MODEL
    assert contract["hinge_rate_aerodynamic_model"] == HINGE_RATE_AERODYNAMIC_MODEL
    assert contract["sectional_aerodynamic_couple"] == SECTIONAL_AERODYNAMIC_COUPLE
    assert request["source_identity_scope"] == "declared_source_hash_not_external_authentication"
    assert request["hash_identity_scope"] == (
        "content_identity_not_authentication_correctness_or_physical_validity"
    )
    assert request["bounds"] == "error"
    assert request["physical_qualification"] is False
    variants = [
        _binding(base_inertia=BaseRotatingAssemblyInertia(2.0e-4, "fixture inertia", ("motor rotor", "shaft", "hub", "fixed blade roots"))),
        _binding(base_inertia=BaseRotatingAssemblyInertia(1.0e-4, "other inertia", ("motor rotor", "shaft", "hub", "fixed blade roots"))),
        _binding(base_inertia=BaseRotatingAssemblyInertia(1.0e-4, "fixture inertia", ("motor rotor", "shaft", "hub"))),
        _binding(motor=MotorSpec(1100.0, 0.05, 1.0, 80.0)),
        _binding(battery=BatterySpec(14.8, 0.98)),
        _binding(battery=BatterySpec(12.0, 0.97)),
        _binding(system=SystemSpec(0.02)),
        _binding(throttle=0.2),
        _binding(environment=CoupledEnvironment("screen", 5.0, 1.18, 1.79e-5, 293.15, 100000.0)),
        _binding(polars=_schedule(cl=0.7)),
        _binding(polars=_schedule(source="other-fixture")),
        _binding(polars=_schedule(metadata={"tag": "b"})),
        _binding(bem_settings=_settings(annulus_count=6)),
        _binding(bem_settings=_settings(branch="signed_nonreversed")),
        _binding(distribution=_mass(mass=0.02)),
        _binding(spring_stiffness_nm_rad=0.001),
        _binding(rest_angle_rad=-0.1),
        _binding(viscous_damping_nm_s_rad=0.0001),
        _binding(dry_friction=DryFriction("regularized_coulomb", 0.001, 0.04, source="fixture friction")),
        _binding(mechanical_source="other fixture"),
        _binding(actuation=HingeActuationHistory((0.0, 0.004), (0.0, 0.001), "no actuation")),
        _binding(initial_angle_rad=-0.15),
        _binding(initial_angular_velocity_rad_s=0.01),
        _binding(initial_omega_rad_s=500.0 * math.pi / 30.0),
        _binding(controls=CoupledSolverControls(rtol=1.0e-7)),
    ]
    digests = {item.input_sha256 for item in variants}
    assert baseline.input_sha256 not in digests
    assert len(digests) == len(variants)


def test_mutated_metadata_and_bad_json_are_rejected() -> None:
    metadata = {"tag": "a"}
    binding = _binding(polars=_schedule(metadata=metadata))
    metadata["tag"] = "b"
    with pytest.raises(Cmm2CoupledBindingError, match="identity"):
        validate_cmm2_coupled_binding(binding)
    resealed = _binding(polars=_schedule(metadata={"tag": "b"}))
    assert resealed.input_sha256 != binding.input_sha256
    with pytest.raises(Cmm2CoupledBindingError):
        _binding(polars=_schedule(metadata={"bad": float("nan")}))
    object.__setattr__(binding, "throttle", 0.2)
    with pytest.raises(Cmm2CoupledBindingError, match="identity"):
        validate_cmm2_coupled_binding(binding)


def test_i0_flag_and_wrong_seal_fail_closed(monkeypatch) -> None:
    returned, _received, _observed = _install(monkeypatch)
    binding = _binding()
    object.__setattr__(binding.base_inertia, "excludes_modeled_movable_tips", False)
    with pytest.raises(Cmm2CoupledBindingError, match="I0"):
        run_cmm2_coupled_transient(binding)
    assert returned == []
    fresh = _binding()
    with pytest.raises(Cmm2CoupledBindingError, match="seal"):
        run_cmm2_coupled_transient(fresh, expected_input_sha256="0" * 64)
    assert returned == []


def test_bounds_clamp_never_reaches_bem(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("bem called")

    monkeypatch.setattr(f"{SERVICE}.solve_foldable_bem_rotor", boom)
    with pytest.raises(Cmm2CoupledBindingError, match="bounds"):
        _binding(bounds="clamp")
    binding = _binding()
    assert binding.bounds == "error"


def test_loading_branch_reaches_the_bem_call(monkeypatch) -> None:
    _returned, _received, observed = _install(monkeypatch)
    run_cmm2_coupled_transient(_binding(bem_settings=_settings(branch="signed_nonreversed")))
    assert observed
    assert {row["loading_branch"] for row in observed} == {"signed_nonreversed"}
    assert {row["bounds"] for row in observed} == {"error"}


def test_prepare_does_not_call_bem(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("bem called")

    monkeypatch.setattr(f"{SERVICE}.solve_foldable_bem_rotor", boom)
    binding = _binding()
    assert binding.input_sha256


def test_motor_domain_is_revoiced_and_matches_pr07(monkeypatch) -> None:
    _install(monkeypatch)
    artifact = run_cmm2_coupled_transient(_binding())
    state = algebraic_motor_state(MOTOR, BATTERY, SYSTEM, 0.1, 400.0)
    assert artifact.result.samples[0].motor_torque_nm == state.torque_nm
    with pytest.raises(Cmm2DomainExit, match="motoring"):
        run_cmm2_coupled_transient(_binding(initial_omega_rad_s=13000.0 * math.pi / 30.0))
    with pytest.raises(Cmm2DomainExit, match="current"):
        run_cmm2_coupled_transient(
            _binding(
                motor=MotorSpec(1000.0, 0.05, 1.0, 5.0),
                throttle=1.0,
                initial_omega_rad_s=1000.0 * math.pi / 30.0,
            )
        )


@pytest.mark.parametrize(
    "error",
    [
        BEMAnnulusError("annulus"),
        BEMConvergenceError("unconverged"),
        BEMRotorElementError("element"),
        BEMRotorError("rotor"),
        FoldableRotorGeometryError("geometry"),
        PolarInterpolationError("outside the polar"),
    ],
)
def test_bem_failures_abort_without_a_success_artifact(monkeypatch, error) -> None:
    returned, received, _observed = _install(monkeypatch, fail=error)
    with pytest.raises(Cmm2TransientFailure, match="aerodynamic source") as caught:
        run_cmm2_coupled_transient(_binding())
    assert type(caught.value.__cause__) is type(error)
    assert str(error) in str(caught.value.__cause__)
    assert returned == []
    assert received == []


def test_map_and_terminal_failures_do_not_fall_back_to_raw_bem(monkeypatch) -> None:
    returned, received, _observed = _install(monkeypatch, fail="map")
    with pytest.raises(Cmm2TransientFailure, match="aerodynamic source") as caught:
        run_cmm2_coupled_transient(_binding())
    assert isinstance(caught.value.__cause__, PlanarProjectedMaterialLoadError)
    assert "terminal boundary" in str(caught.value.__cause__)
    assert len(returned) == 1
    assert len(received) == 1
    assert received[0] is returned[0]


def test_report_is_deterministic_and_keeps_the_seal(monkeypatch) -> None:
    _install(monkeypatch)
    binding = _binding()
    first = run_cmm2_coupled_transient(binding)
    second = run_cmm2_coupled_transient(binding)
    assert first.report_json == second.report_json
    assert first.report_sha256 == second.report_sha256
    assert hashlib.sha256(first.report_json.encode("utf-8")).hexdigest() == first.report_sha256
    document = json.loads(first.report_json)
    assert document["request"] == json.loads(binding.context_json)
    assert document["input_sha256"] == binding.input_sha256
    assert document["model_class"] == MODEL_CLASS
    assert document["dynamics_implementation_id"] == IMPLEMENTATION_ID
    assert document["service_implementation_id"] == SERVICE_IMPLEMENTATION_ID
    assert document["service_implementation_id"] != document["dynamics_implementation_id"]
    assert document["aero_evaluator_id"] == AERO_EVALUATOR_ID
    assert document["physical_qualification"] is False
    assert document["full_propeller_clearance"] is None
    assert document["surface_path_clearance"] is None
    assert document["interblade_clearance"] is None
    assert document["hash_identity_scope"] == (
        "content_identity_not_authentication_correctness_or_physical_validity"
    )
    assert document["source_identity_scope"] == "declared_source_hash_not_external_authentication"
    assert document["base_rotating_inertia"] == document["request"]["base_rotating_inertia"]
    assert document["bem_settings"] == document["request"]["bem_settings"]
    assert document["motor_binding"] == document["request"]["motor_binding"]
    assert document["motor_binding"]["law"] == "pr07_algebraic"
    assert document["motor_binding"]["dynamic_current_state"] is False
    assert document["motor_binding"]["regeneration"] is False
    assert document["planar_load_contract"]["distributed_couple_model"] == "none"
    assert document["planar_load_contract"]["sectional_aerodynamic_couple"] == "excluded_in_v1"
    assert document["aero_evaluation_count"] == first.result.aero_evaluations
    assert document["aero_evaluation_count"] == len(document["aero_evaluation_ledger"])
    assert document["loading_branch"] == document["bem_settings"]["annulus_settings"]["loading_branch"]
    assert document["result"]["physical_qualification"] is False
    assert document["result"]["limitations"][1].startswith("A source-bound production screening service")
    for name, digest in document["implementation_files_sha256"].items():
        assert not Path(name).is_absolute()
        assert ".." not in Path(name).parts
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert "pyfoldable/dynamics/cmm2_coupled_transient.py" in document["implementation_files_sha256"]
    assert "pyfoldable/core/foldable_aero_load.py" in document["implementation_files_sha256"]
    ledger = document["aero_evaluation_ledger"]
    by_id = {row["source_id"]: row for row in ledger}
    assert len(by_id) == len(ledger)
    for sample in document["result"]["samples"]:
        row = by_id[sample["aero_source_id"]]
        assert row["theta_rad"] == sample["theta_rad"]
        assert row["hinge_rate_rad_s"] == sample["theta_dot_rad_s"]
        assert row["omega_rad_s"] == sample["omega_rad_s"]
        mapped = row["mapped_load"]
        assert hashlib.sha256(
            json.dumps(mapped, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        ).hexdigest() == row["mapped_load_sha256"]
        assert row["terminal_boundary_normalized"] is False
        assert row["terminal_boundary_delta_m"] == 0.0
        assert row["source_terminal_radius_m"] == row["projected_tip_radius_m"]


_EXPECTED_IMPLEMENTATION_MANIFEST = (
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


def test_implementation_file_manifest_covers_direct_calculation_path(monkeypatch) -> None:
    assert len(_EXPECTED_IMPLEMENTATION_MANIFEST) == len(set(_EXPECTED_IMPLEMENTATION_MANIFEST))
    assert cmm2_service._IMPLEMENTATION_FILE_MANIFEST == _EXPECTED_IMPLEMENTATION_MANIFEST
    required = {
        "pyfoldable/core/bem.py",
        "pyfoldable/core/polar.py",
        "pyfoldable/core/polar_spanwise.py",
        "pyfoldable/core/rotational_augmentation.py",
        "pyfoldable/core/models.py",
        "pyfoldable/core/motor_bem_coupling.py",
        "pythrust/propulsion/models.py",
        "pyfoldable/dynamics/mechanism_transient.py",
        "pyfoldable/dynamics/mechanism_contracts.py",
        "pyfoldable/application/mechanism_binding.py",
        "pyfoldable/application/cmm2_coupled_transient_service.py",
        "pyfoldable/application/coupled_transient_service.py",
        "pyfoldable/dynamics/cmm2_coupled_transient.py",
        "pyfoldable/dynamics/coupled_transient.py",
        "pyfoldable/core/foldable_aero_load.py",
        "pyfoldable/core/foldable_rotor.py",
        "pyfoldable/core/bem_rotor.py",
        "pyfoldable/core/config.py",
        "pyfoldable/core/units.py",
        "pyfoldable/application/folding_mechanism.py",
        "pyfoldable/core/airfoil.py",
    }
    assert required <= set(_EXPECTED_IMPLEMENTATION_MANIFEST)
    assert len(_EXPECTED_IMPLEMENTATION_MANIFEST) == 22
    _install(monkeypatch)
    document = json.loads(run_cmm2_coupled_transient(_binding()).report_json)
    published = document["implementation_files_sha256"]
    assert len(published) == 22
    assert set(published) == set(_EXPECTED_IMPLEMENTATION_MANIFEST)
    for path in _EXPECTED_IMPLEMENTATION_MANIFEST:
        digest = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        assert published[path] == digest
        assert int(digest, 16) >= 0
        assert len(published[path]) == 64


def test_unavailable_implementation_manifest_path_fails_closed(monkeypatch) -> None:
    _install(monkeypatch)
    monkeypatch.setattr(
        cmm2_service,
        "_IMPLEMENTATION_FILE_MANIFEST",
        ("pyfoldable/core/bem.py", "pyfoldable/core/not_a_source_file.py"),
    )
    with pytest.raises(Cmm2TransientFailure, match="missing"):
        run_cmm2_coupled_transient(_binding())
    monkeypatch.setattr(
        cmm2_service,
        "_IMPLEMENTATION_FILE_MANIFEST",
        ("pyfoldable/core/bem.py", "pyfoldable/core/bem.py"),
    )
    with pytest.raises(Cmm2TransientFailure, match="duplicate"):
        cmm2_service._implementation_files()
    monkeypatch.setattr(
        cmm2_service,
        "_IMPLEMENTATION_FILE_MANIFEST",
        ("../pyfoldable/core/bem.py",),
    )
    with pytest.raises(Cmm2TransientFailure, match="repository-relative"):
        cmm2_service._implementation_files()


@pytest.mark.parametrize(
    "relative",
    [
        "pyfoldable//core/bem.py",
        "pyfoldable/./core/bem.py",
        "./pyfoldable/core/bem.py",
        "pyfoldable/core/../core/bem.py",
        "pyfoldable/core/bem.py/",
        "/pyfoldable/core/bem.py",
        "pyfoldable\\core\\bem.py",
        "C:/pyfoldable/core/bem.py",
    ],
)
def test_manifest_rejects_raw_path_components_before_normalization(relative: str) -> None:
    assert (ROOT / "pyfoldable/core/bem.py").is_file()
    with pytest.raises(Cmm2TransientFailure, match="repository-relative"):
        cmm2_service._manifest_file(ROOT, relative)


def test_manifest_rejects_symlink_components_and_accepts_a_regular_file(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    source = real / "source.py"
    source.write_text("regular\n", encoding="utf-8")
    linked = tmp_path / "linked"
    leaf = tmp_path / "real_source.py"
    alias = tmp_path / "alias.py"
    nested = real / "inner"
    nested.mkdir()
    nested_source = nested / "source.py"
    nested_source.write_text("nested\n", encoding="utf-8")
    nested_link = real / "via"
    try:
        linked.symlink_to(real, target_is_directory=True)
        leaf.write_text("leaf\n", encoding="utf-8")
        alias.symlink_to(leaf)
        nested_link.symlink_to(nested, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")
    with pytest.raises(Cmm2TransientFailure, match="symlink"):
        cmm2_service._manifest_file(tmp_path, "linked/source.py")
    with pytest.raises(Cmm2TransientFailure, match="symlink"):
        cmm2_service._manifest_file(tmp_path, "alias.py")
    with pytest.raises(Cmm2TransientFailure, match="symlink"):
        cmm2_service._manifest_file(tmp_path, "real/via/source.py")
    accepted = cmm2_service._manifest_file(tmp_path, "real/source.py")
    assert accepted == source
    assert accepted.is_file()
    assert not accepted.is_symlink()


def test_normalized_terminal_provenance_is_preserved(monkeypatch) -> None:
    _install(monkeypatch, normalized=True)
    document = json.loads(run_cmm2_coupled_transient(_binding()).report_json)
    row = document["aero_evaluation_ledger"][0]
    assert row["terminal_boundary_normalized"] is True
    assert row["terminal_boundary_delta_m"] != 0.0
    assert row["source_outer_projected_radius_m"] == row["projected_tip_radius_m"]
    assert row["source_terminal_radius_m"] != row["projected_tip_radius_m"]
    assert row["mapped_load"]["terminal_boundary_normalized"] is True
    assert row["mapped_load"]["terminal_boundary_delta_m"] == row["terminal_boundary_delta_m"]


def test_direct_power_matches_the_mapped_expression(monkeypatch) -> None:
    _install(monkeypatch)
    evaluator = _evaluator(_binding())
    omega = 400.0 * math.pi / 30.0
    evaluation = evaluator(0.0, -0.2, 0.05, omega)
    expected = SHAFT * omega + 3 * ONE_TIP * 0.05
    assert evaluation.generalized_power_w(omega) == expected
    assert evaluator.provenance_records[0].one_tip_hinge_generalized_load_nm == ONE_TIP


def test_real_bem_object_is_the_mapped_object(monkeypatch) -> None:
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
    tip = PolarFamily(
        tuple(
            PolarTable(
                airfoil_id="tip",
                scenario_id="cmm2-real",
                reynolds=reynolds,
                mach=mach,
                alpha_rad=(-math.pi / 2.0, math.pi / 2.0),
                cl=(0.8, 0.8),
                cd=(0.02, 0.02),
                cm=(0.0, 0.0),
                source="fixture:tip",
            )
            for mach in (0.0, 0.5)
            for reynolds in (1.0e3, 1.0e7)
        )
    )
    root = PolarFamily(
        tuple(
            PolarTable(
                airfoil_id="root",
                scenario_id="cmm2-real",
                reynolds=reynolds,
                mach=mach,
                alpha_rad=(-math.pi / 2.0, math.pi / 2.0),
                cl=(0.6, 0.6),
                cd=(0.02, 0.02),
                cm=(0.0, 0.0),
                source="fixture:root",
            )
            for mach in (0.0, 0.5)
            for reynolds in (1.0e3, 1.0e7)
        )
    )
    schedule = SpanwisePolarSchedule(
        "real-map",
        (
            SpanwisePolarAnchor(0.2, root),
            SpanwisePolarAnchor(0.8, tip),
            SpanwisePolarAnchor(1.0, tip),
        ),
    )
    settings = _settings()
    environment = CoupledEnvironment("real", 4.0, 1.225, 1.81e-5, 288.15, 101325.0)
    captured: dict[str, object] = {}

    def wrap_solve(*args, **kwargs):
        value = solve_foldable_bem_rotor(*args, **kwargs)
        captured["bem"] = value
        return value

    def wrap_map(result, **kwargs):
        captured["received"] = result
        mapped = map_foldable_bem_aero_loads(result, **kwargs)
        captured["mapped"] = mapped
        return mapped

    monkeypatch.setattr(cmm2_service, "solve_foldable_bem_rotor", wrap_solve)
    monkeypatch.setattr(cmm2_service, "map_foldable_bem_aero_loads", wrap_map)
    evaluator = Cmm2FoldableBemMappedAeroEvaluator(
        blade, schedule, settings, environment, 0.075, "error"
    )
    omega = 500.0
    evaluation = evaluator(0.0, 0.0, 0.02, omega)
    assert captured["received"] is captured["bem"]
    mapped = captured["mapped"]
    assert evaluation.whole_rotor_shaft_generalized_load_nm == (
        mapped.whole_rotor_aerodynamic_shaft_generalized_load_nm
    )
    assert evaluation.one_tip_hinge_generalized_load_nm == mapped.one_tip_hinge_generalized_torque_nm
    assert evaluation.thrust_n == mapped.source_whole_rotor_projected_thrust_n
    assert evaluation.generalized_power_w(omega) == mapped.aerodynamic_generalized_power_w(omega)
    assert evaluator.successful_bem_solves == evaluator.successful_map_calls == 1
    if mapped.blade_count != 1 and mapped.one_tip_hinge_generalized_torque_nm != 0.0:
        assert evaluation.one_tip_hinge_generalized_load_nm != (
            mapped.synchronous_n_times_one_tip_hinge_generalized_torque_nm
        )
    if mapped.whole_rotor_aerodynamic_shaft_generalized_load_nm != 0.0:
        assert evaluation.whole_rotor_shaft_generalized_load_nm != (
            mapped.blade_count * mapped.whole_rotor_aerodynamic_shaft_generalized_load_nm
        )
