"""Source-bound CMM-1 application contract."""

from __future__ import annotations

import dataclasses
import inspect
import json
import math
from pathlib import Path

import pytest

from pyfoldable.application.coupled_transient_service import (
    CoupledBindingError,
    CoupledEnvironment,
    FoldableBemShaftEvaluator,
    Pr07MotorEvaluator,
    assert_cmm1_production_evaluators,
    prepare_coupled_transient,
    run_coupled_transient,
)
from pyfoldable.application.design_draft import (
    DesignDraftInputs,
    build_design_draft,
)
from pyfoldable.application.mechanism_binding import (
    RadialMassSample,
    TipMassDistribution,
)
from pyfoldable.core.bem import BEMAnnulusSettings, BEMConvergenceError
from pyfoldable.core.bem_rotor import BEMRotorSettings, solve_bem_rotor
from pyfoldable.core.foldable_rotor import (
    FoldableRotorState,
    solve_foldable_bem_rotor,
)
from pyfoldable.core.models import BladeGeometry, BladeStation, OperatingCondition
from pyfoldable.core.motor_bem_coupling import algebraic_motor_state
from pyfoldable.core.polar import PolarFamily, PolarInterpolationError, PolarTable
from pyfoldable.core.polar_spanwise import SpanwisePolarAnchor, SpanwisePolarSchedule
from pyfoldable.dynamics.coupled_transient import (
    MODEL_CLASS,
    BaseRotatingAssemblyInertia,
    CoupledDomainExit,
    CoupledTransientFailure,
    HingeActuationHistory,
)
from pythrust.propulsion.models import BatterySpec, MotorSpec, SystemSpec


ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "configs/designs/TIP_HINGED_250_CANONICAL.toml"
MOTOR = MotorSpec(1000.0, 0.05, 1.0, 80.0)
BATTERY = BatterySpec(12.0, 0.98)
SYSTEM = SystemSpec(0.01)


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


def _family(cl: float) -> PolarFamily:
    return PolarFamily(
        (
            PolarTable(
                airfoil_id="NACA0012",
                scenario_id="cmm1",
                reynolds=1.0e5,
                mach=0.0,
                alpha_rad=(-0.5, 0.5),
                cl=(cl, cl),
                cd=(0.02, 0.02),
                cm=(0.0, 0.0),
                source="cmm1-fixture",
            ),
        )
    )


def _schedule(cl: float = 0.6) -> SpanwisePolarSchedule:
    family = _family(cl)
    return SpanwisePolarSchedule(
        "cmm1-span",
        (
            SpanwisePolarAnchor(0.2, family),
            SpanwisePolarAnchor(1.0, family),
        ),
    )


def _settings(branch: str = "positive_only", annulus_count: int = 4) -> BEMRotorSettings:
    return BEMRotorSettings(
        annulus_count=annulus_count,
        annulus_settings=BEMAnnulusSettings(
            bracket_samples=16,
            loading_branch=branch,
        ),
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
    return prepare_coupled_transient(**values)


def _constant_bem(torque: float = 0.01, thrust: float = 0.2):
    class _Rotor:
        torque_nm = torque
        thrust_n = thrust

    class _Result:
        rotor_result = _Rotor()

    def fake(blade, state, condition, polars, *, bounds="error", settings=None):
        del blade, polars
        fake.calls.append(
            {
                "bounds": bounds,
                "loading_branch": settings.annulus_settings.loading_branch,
                "omega": condition.angular_speed_rad_s,
                "theta": state.opening_angle_rad,
                "forward": condition.forward_speed_m_s,
            }
        )
        return _Result()

    fake.calls = []
    return fake


def test_run_rejects_injected_evaluators_and_noncanonical_callbacks() -> None:
    assert "aero_evaluator" not in inspect.signature(run_coupled_transient).parameters
    with pytest.raises(CoupledBindingError, match="PR-07"):
        assert_cmm1_production_evaluators(lambda *_args: None, lambda *_args: None)
    binding = _binding()
    motor = Pr07MotorEvaluator(binding.motor, binding.battery, binding.system, binding.throttle)
    with pytest.raises(CoupledBindingError):
        assert_cmm1_production_evaluators(motor, lambda *_args: None)


def test_input_identity_tracks_inertia_motor_throttle_environment_polars_and_mass() -> None:
    baseline = _binding()
    assert _binding().input_sha256 == baseline.input_sha256
    variants = [
        _binding(base_inertia=BaseRotatingAssemblyInertia(2.0e-4, "fixture inertia", ("motor rotor", "shaft", "hub", "fixed blade roots"))),
        _binding(base_inertia=BaseRotatingAssemblyInertia(1.0e-4, "other source", ("motor rotor", "shaft", "hub", "fixed blade roots"))),
        _binding(base_inertia=BaseRotatingAssemblyInertia(1.0e-4, "fixture inertia", ("motor rotor", "shaft", "hub", "fasteners"))),
        _binding(motor=MotorSpec(1100.0, 0.05, 1.0, 80.0)),
        _binding(throttle=0.2),
        _binding(environment=CoupledEnvironment("screen", 4.0, 1.2, 1.79e-5, 293.15, 100000.0)),
        _binding(polars=_schedule(0.7)),
        _binding(bem_settings=_settings("signed_nonreversed")),
        _binding(distribution=_mass(mass=0.012)),
    ]
    assert len({item.input_sha256 for item in variants}) == len(variants)
    assert baseline.input_sha256 not in {item.input_sha256 for item in variants}


def test_tampered_binding_is_rejected(monkeypatch) -> None:
    binding = _binding()
    object.__setattr__(binding, "throttle", 0.5)
    with pytest.raises(CoupledBindingError, match="identity"):
        run_coupled_transient(binding)
    fresh = _binding()
    with pytest.raises(CoupledBindingError, match="identity"):
        run_coupled_transient(fresh, expected_input_sha256="0" * 64)
    cleared = _binding()
    object.__setattr__(cleared.base_inertia, "excludes_modeled_movable_tips", False)
    with pytest.raises(CoupledBindingError, match="movable tip"):
        run_coupled_transient(cleared)


def test_loading_branch_and_bounds_are_not_rewritten(monkeypatch) -> None:
    fake = _constant_bem()
    monkeypatch.setattr(
        "pyfoldable.application.coupled_transient_service.solve_foldable_bem_rotor",
        fake,
    )
    artifact = run_coupled_transient(_binding(bem_settings=_settings("signed_nonreversed")))
    assert fake.calls
    assert {call["bounds"] for call in fake.calls} == {"error"}
    assert {call["loading_branch"] for call in fake.calls} == {"signed_nonreversed"}
    assert artifact.result.physical_qualification is False
    with pytest.raises(CoupledBindingError, match="bounds"):
        _binding(bounds="clamp")


def test_bem_and_polar_failures_abort_without_a_success_artifact(monkeypatch) -> None:
    def bem_fail(*_args, **_kwargs):
        raise BEMConvergenceError("unconverged")

    monkeypatch.setattr(
        "pyfoldable.application.coupled_transient_service.solve_foldable_bem_rotor",
        bem_fail,
    )
    with pytest.raises(CoupledTransientFailure, match="BEM") as bem_error:
        run_coupled_transient(_binding())
    assert bem_error.value.__cause__ is not None

    def polar_fail(*_args, **_kwargs):
        raise PolarInterpolationError("outside the polar")

    monkeypatch.setattr(
        "pyfoldable.application.coupled_transient_service.solve_foldable_bem_rotor",
        polar_fail,
    )
    with pytest.raises(CoupledTransientFailure, match="BEM"):
        run_coupled_transient(_binding())


def test_motor_domain_is_explicit_and_matches_pr07_inside_the_domain() -> None:
    evaluator = Pr07MotorEvaluator(MOTOR, BATTERY, SYSTEM, 0.1)
    omega = 400.0 * math.pi / 30.0
    sample = evaluator(0.0, 0.0, 0.0, omega)
    state = algebraic_motor_state(MOTOR, BATTERY, SYSTEM, 0.1, 400.0)
    assert sample.torque_nm == pytest.approx(state.torque_nm, abs=0.0)
    assert sample.current_a == pytest.approx(state.current_a, abs=0.0)
    limited = Pr07MotorEvaluator(MotorSpec(1000.0, 0.05, 1.0, 5.0), BATTERY, SYSTEM, 1.0)
    with pytest.raises(CoupledDomainExit, match="current"):
        limited(0.0, 0.0, 0.0, 1000.0 * math.pi / 30.0)
    with pytest.raises(CoupledDomainExit, match="motoring"):
        evaluator(0.0, 0.0, 0.0, 13000.0 * math.pi / 30.0)


def test_report_keeps_screening_limits_and_does_not_promote_geom(monkeypatch) -> None:
    monkeypatch.setattr(
        "pyfoldable.application.coupled_transient_service.solve_foldable_bem_rotor",
        _constant_bem(),
    )
    artifact = run_coupled_transient(_binding())
    document = json.loads(artifact.report_json)
    assert document["model_class"] == MODEL_CLASS
    assert document["physical_qualification"] is False
    assert document["aerodynamic_hinge_torque_status"] == "unavailable_omitted_by_cmm1"
    assert document["full_propeller_clearance"] is None
    assert document["surface_path_clearance"] is None
    assert document["interblade_clearance"] is None
    assert "aerodynamic_hinge_torque_nm" not in artifact.report_json
    assert document["bem_qualification"] == "screening_only_until_pr06c_passes"
    assert document["projection_model"] == "radial_cosine_v1"
    assert document["base_rotating_inertia"]["component_inventory"] == [
        "motor rotor",
        "shaft",
        "hub",
        "fixed blade roots",
    ]
    assert document["base_rotating_inertia"]["excludes_modeled_movable_tips"] is True
    assert document["result"]["samples"][0]["bem_qualification"] == "screening_only_until_pr06c_passes"
    assert artifact.result.samples[0].aerodynamic_hinge_torque_status == "unavailable_omitted_by_cmm1"
    with pytest.raises(dataclasses.FrozenInstanceError):
        artifact.result.physical_qualification = True  # type: ignore[misc]


def test_deployed_evaluator_matches_fixed_and_foldable_bem() -> None:
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
    root = PolarFamily(
        tuple(
            PolarTable(
                airfoil_id="root",
                scenario_id="cmm1-equiv",
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
    tip = PolarFamily(
        tuple(
            PolarTable(
                airfoil_id="tip",
                scenario_id="cmm1-equiv",
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
    schedule = SpanwisePolarSchedule(
        "root-to-tip",
        (
            SpanwisePolarAnchor(0.2, root),
            SpanwisePolarAnchor(0.8, tip),
            SpanwisePolarAnchor(1.0, tip),
        ),
    )
    settings = BEMRotorSettings(
        annulus_count=4,
        annulus_settings=BEMAnnulusSettings(bracket_samples=16, loading_branch="positive_only"),
    )
    environment = CoupledEnvironment("equiv", 4.0, 1.225, 1.81e-5, 288.15, 101325.0)
    evaluator = FoldableBemShaftEvaluator(blade, schedule, settings, environment, 0.075, "error")
    sample = evaluator(0.0, 0.0, 0.0, 500.0)
    condition = OperatingCondition(
        "fixed-limit",
        500.0,
        4.0,
        1.225,
        1.81e-5,
        288.15,
        101325.0,
    )
    fixed = solve_bem_rotor(blade, condition, schedule, bounds="error", settings=settings)
    folded = solve_foldable_bem_rotor(
        blade,
        FoldableRotorState("open", 0.075, 0.0, 0.0),
        condition,
        schedule,
        bounds="error",
        settings=settings,
    )
    assert sample.shaft_torque_nm == pytest.approx(fixed.torque_nm, abs=0.0)
    assert sample.thrust_n == pytest.approx(fixed.thrust_n, abs=0.0)
    assert sample.shaft_torque_nm == pytest.approx(folded.rotor_result.torque_nm, abs=0.0)
    assert folded.fixed_limit_equivalent is True
    assert sample.qualification == "screening_only_until_pr06c_passes"
    assert sample.projection_model == "radial_cosine_v1"
