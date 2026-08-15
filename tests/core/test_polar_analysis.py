"""Analytic and invariant tests for generated-polar section consumption."""

from __future__ import annotations

import json
import math
import random
from dataclasses import replace

import pytest

from pyfoldable.core import (
    AirfoilDefinition, BladeGeometry, BladeStation, OperatingCondition,
    PolarFamilyBatchPolicy, PolarFamilyGenerationPlan, PolarGenerationRequest,
    PolarGenerationResult, PolarPointResult, PolarProviderExecutionError,
    PolarSectionAnalysisError, PolarSectionAnalysisResult,
    PropellerDesign, ProviderCapabilities, ProviderIdentity,
    analyze_generated_polar_sections, generate_polar_family_batch,
    load_polar_family_config,
)


AIRFOIL = AirfoilDefinition(
    "PYFOLDABLE_DEMO", "fixture",
    ((1.0, 0.0), (0.5, 0.1), (0.0, 0.0), (0.5, -0.1), (1.0, 0.0)),
)
IDENTITY = ProviderIdentity("analytic", "1", "fixture", "1")


class AnalyticProvider:
    identity = IDENTITY
    capabilities = ProviderCapabilities(True, True, True, False, False, True, True, True)

    def generate(self, request):
        points = tuple(PolarPointResult(
            alpha, "converged", cl=2.0 * alpha, cd=0.02, cm=0.0
        ) for alpha in request.alpha_rad)
        return PolarGenerationResult(
            request, self.identity, points, 0.01, warnings=("provider-note",),
            metadata={
                "cache": {"status": "hit"},
                "orchestration": {"fallback_used": False, "attempts": ("analytic",)},
            },
        )


class PartiallyFailingProvider(AnalyticProvider):
    def generate(self, request):
        if request.reynolds == 2_000_000.0:
            raise PolarProviderExecutionError("fixture failure")
        return super().generate(request)


def fixture(*, forward=0.0, omega=100.0, twists=(0.1, 0.1), airfoils=None):
    condition = OperatingCondition("hover" if forward == 0 else "forward", omega, forward,
                                   1.2, 1.8e-5, 288.15, 101325.0)
    stations = tuple(BladeStation(r, 0.1, twist, aid) for r, twist, aid in zip(
        (0.5, 1.0), twists, airfoils or (AIRFOIL.id, AIRFOIL.id)
    ))
    definitions = (AIRFOIL,) if not airfoils or len(set(airfoils)) == 1 else (
        AIRFOIL, AirfoilDefinition("OTHER", "fixture")
    )
    design = PropellerDesign("design", "fixture", BladeGeometry(2.0, 0.1, 2, stations),
                             definitions, (condition,))
    request = PolarGenerationRequest(AIRFOIL, (-0.5, 0.0, 0.5), 10_000.0,
                                     mach=0.0, scenario_id="clean")
    plan = PolarFamilyGenerationPlan(request, (10_000.0, 2_000_000.0), (0.0, 0.5))
    generation = generate_polar_family_batch((AnalyticProvider(),), plan)
    config = replace(load_polar_family_config("configs/polars/PYFOLDABLE_DEMO_FAMILY.toml"),
                     plan=plan)
    return design, condition, generation, config


def test_analytic_hover_loads_and_trapezoidal_integration():
    design, condition, generation, config = fixture()
    result = analyze_generated_polar_sections(
        design, condition, generation, config, bounds="clamp", git_commit="abc"
    )
    first = result.sections[0]
    assert first.inflow_angle_rad == 0.0
    assert first.alpha_rad == pytest.approx(0.1)
    assert first.cl == pytest.approx(0.2)
    expected_lift = 0.5 * 1.2 * 50.0**2 * 0.1 * 0.2
    assert first.lift_per_span_n_m == pytest.approx(expected_lift)
    expected = 2 * 0.5 * (first.axial_force_per_span_n_m
                          + result.sections[1].axial_force_per_span_n_m) * 0.5
    assert result.simulation_result.thrust_n == pytest.approx(expected)


def test_forward_flight_kinematics_are_analytic():
    design, condition, generation, config = fixture(forward=10.0, twists=(0.3, 0.3))
    section = analyze_generated_polar_sections(
        design, condition, generation, config, bounds="clamp", git_commit="abc"
    ).sections[0]
    assert section.relative_speed_m_s == pytest.approx(math.hypot(50.0, 10.0))
    assert section.inflow_angle_rad == pytest.approx(math.atan2(10.0, 50.0))
    assert section.alpha_rad == pytest.approx(0.3 - math.atan2(10.0, 50.0))


def test_error_is_default_and_clamp_is_audited_everywhere():
    design, condition, generation, config = fixture(twists=(1.0, 1.0))
    with pytest.raises(PolarSectionAnalysisError, match="Station 0.*outside"):
        analyze_generated_polar_sections(
            design, condition, generation, config, git_commit="abc"
        )
    result = analyze_generated_polar_sections(
        design, condition, generation, config, bounds="clamp", git_commit="abc"
    )
    assert "alpha_rad" in result.sections[0].clamped_dimensions
    assert result.simulation_result.warnings
    provenance = result.simulation_result.metadata["polar_provenance"]
    assert "alpha_rad" in provenance["clamped_dimensions"]


@pytest.mark.parametrize("mutation, message", [
    (lambda d, c, g, p: (d, replace(c, forward_speed_m_s=-1), g, p), "Negative"),
    (lambda d, c, g, p: (d, replace(c, angular_speed_rad_s=0), g, p), "Shaft"),
    (lambda d, c, g, p: (d, replace(c, id="alien"), g, p), "does not belong"),
])
def test_invalid_conditions_fail_closed(mutation, message):
    args = mutation(*fixture())
    with pytest.raises(PolarSectionAnalysisError, match=message):
        analyze_generated_polar_sections(*args, bounds="clamp", git_commit="abc")


def test_mixed_airfoil_and_generation_config_mismatch_fail_closed():
    args = fixture(airfoils=(AIRFOIL.id, "OTHER"))
    with pytest.raises(PolarSectionAnalysisError, match="Mixed-airfoil"):
        analyze_generated_polar_sections(*args, bounds="clamp", git_commit="abc")
    design, condition, generation, config = fixture()
    bad_plan = replace(config.plan, reynolds_grid=(10_000.0,))
    with pytest.raises(PolarSectionAnalysisError, match="provenance"):
        analyze_generated_polar_sections(design, condition, generation,
                                         replace(config, plan=bad_plan),
                                         bounds="clamp", git_commit="abc")


def test_provenance_and_json_serialization_are_complete():
    result = analyze_generated_polar_sections(*fixture(), bounds="clamp", git_commit="abc")
    encoded = json.dumps(result.as_mapping(), allow_nan=False)
    assert "polar_config_sha256" in encoded
    assert "cache_status" in encoded
    assert "fallback_used" in encoded
    assert "analytic" in encoded


def test_batch_without_materialized_family_fails_closed():
    design, condition, generation, config = fixture()
    failed = generate_polar_family_batch(
        (PartiallyFailingProvider(),),
        generation.plan,
        policy=PolarFamilyBatchPolicy(
            failure_mode="collect_all", subgrid_policy="none"
        ),
    )
    assert failed.family is None
    with pytest.raises(PolarSectionAnalysisError, match="materialize"):
        analyze_generated_polar_sections(
            design, condition, failed, config, bounds="clamp", git_commit="abc"
        )


def test_result_contract_rejects_forged_section_provenance():
    result = analyze_generated_polar_sections(
        *fixture(), bounds="clamp", git_commit="abc"
    )
    forged = replace(result.simulation_result, metadata={})
    with pytest.raises(ValueError, match="provenance"):
        PolarSectionAnalysisResult(result.sections, forged)


def test_randomized_outputs_remain_finite():
    rng = random.Random(20260815)
    for _ in range(500):
        design, condition, generation, config = fixture(
            forward=rng.uniform(0.0, 30.0), omega=rng.uniform(20.0, 200.0),
            twists=(rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4)),
        )
        result = analyze_generated_polar_sections(
            design, condition, generation, config, bounds="clamp", git_commit="abc"
        )
        values = [result.simulation_result.thrust_n, result.simulation_result.torque_nm,
                  result.simulation_result.shaft_power_w]
        values.extend(value for section in result.sections
                      for value in section.as_mapping().values()
                      if isinstance(value, float))
        assert all(math.isfinite(value) for value in values)
