import json
import math

import pytest

from pyfoldable.core import (
    BEMAnnulusSettings,
    BEMRotorSettings,
    BladeGeometry,
    BladeStation,
    FixedLimitEquivalenceCase,
    FixedLimitEquivalenceEvidence,
    FoldableOpeningSweepEvidence,
    FoldableRotorGeometryError,
    FoldableRotorState,
    OperatingCondition,
    PolarFamily,
    PolarTable,
    SpanwisePolarAnchor,
    SpanwisePolarSchedule,
    assess_fixed_limit_equivalence,
    assess_foldable_opening_sensitivity,
    project_foldable_blade,
    project_spanwise_polar_schedule,
    solve_bem_rotor,
    solve_foldable_bem_rotor,
)


def _blade() -> BladeGeometry:
    return BladeGeometry(
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


def _family(airfoil_id: str, cl: float) -> PolarFamily:
    return PolarFamily(
        tuple(
            PolarTable(
                airfoil_id=airfoil_id,
                scenario_id="pr06d-fixed-limit",
                reynolds=reynolds,
                mach=mach,
                alpha_rad=(-math.pi / 2.0, math.pi / 2.0),
                cl=(cl, cl),
                cd=(0.02, 0.02),
                cm=(0.0, 0.0),
                source=f"fixture:{airfoil_id}",
            )
            for mach in (0.0, 0.5)
            for reynolds in (1.0e3, 1.0e7)
        )
    )


def _schedule() -> SpanwisePolarSchedule:
    return SpanwisePolarSchedule(
        "root-to-tip",
        (
            SpanwisePolarAnchor(0.2, _family("root", 0.6)),
            SpanwisePolarAnchor(0.8, _family("tip", 0.8)),
            SpanwisePolarAnchor(1.0, _family("tip", 0.8)),
        ),
    )


def _condition() -> OperatingCondition:
    return OperatingCondition(
        id="fixed-limit",
        angular_speed_rad_s=500.0,
        forward_speed_m_s=4.0,
        air_density_kg_m3=1.225,
        dynamic_viscosity_pa_s=1.81e-5,
        temperature_k=288.15,
        pressure_pa=101325.0,
    )


def test_fully_open_projection_and_solver_are_exact_fixed_blade_equivalents():
    blade = _blade()
    schedule = _schedule()
    state = FoldableRotorState(
        id="fully-open",
        hinge_radius_m=0.075,
        opening_angle_rad=0.0,
        deployed_angle_rad=0.0,
    )
    settings = BEMRotorSettings(
        12,
        "station_span",
        BEMAnnulusSettings(loading_branch="signed_nonreversed"),
    )

    projected = project_foldable_blade(blade, state)
    projected_schedule = project_spanwise_polar_schedule(
        schedule, blade, projected
    )
    fixed = solve_bem_rotor(
        blade, _condition(), schedule, settings=settings
    )
    foldable = solve_foldable_bem_rotor(
        blade, state, _condition(), schedule, settings=settings
    )

    assert projected.effective_blade is blade
    assert projected_schedule is schedule
    assert projected.projection_factor == 1.0
    assert foldable.rotor_result.as_mapping() == fixed.as_mapping()
    assert foldable.fixed_limit_equivalent


def test_partial_opening_projects_only_outboard_material_radii_continuously():
    blade = _blade()
    state = FoldableRotorState(
        id="partial",
        hinge_radius_m=0.075,
        opening_angle_rad=math.radians(-60.0),
        deployed_angle_rad=0.0,
    )

    projected = project_foldable_blade(blade, state)

    assert projected.projection_factor == pytest.approx(0.5)
    assert projected.effective_blade.radius_m == pytest.approx(0.1125)
    assert projected.effective_blade.diameter_m == pytest.approx(0.225)
    hinge = next(
        station
        for station in projected.stations
        if station.nominal_radius_m == pytest.approx(0.075)
    )
    assert hinge.effective_radius_m == pytest.approx(0.075)
    tip = projected.stations[-1]
    assert tip.nominal_radius_m == pytest.approx(0.15)
    assert tip.effective_radius_m == pytest.approx(0.1125)
    assert tip.chord_m == pytest.approx(blade.stations[-1].chord_m)
    assert tip.twist_rad == pytest.approx(blade.stations[-1].twist_rad)
    assert tip.airfoil_id == blade.stations[-1].airfoil_id
    assert all(
        upper.effective_radius_m > lower.effective_radius_m
        for lower, upper in zip(projected.stations, projected.stations[1:])
    )


def test_projected_schedule_preserves_material_section_identity():
    blade = _blade()
    schedule = _schedule()
    state = FoldableRotorState(
        id="partial",
        hinge_radius_m=0.075,
        opening_angle_rad=math.radians(-60.0),
        deployed_angle_rad=0.0,
    )
    projection = project_foldable_blade(blade, state)

    transformed = project_spanwise_polar_schedule(
        schedule, blade, projection
    )

    assert transformed.id == "root-to-tip@fold:partial"
    assert transformed.airfoil_ids == schedule.airfoil_ids
    assert transformed.anchors[0].r_over_R == pytest.approx(
        0.2 * blade.radius_m / projection.effective_blade.radius_m
    )
    assert transformed.anchors[-1].r_over_R == pytest.approx(1.0)
    assert [anchor.family for anchor in transformed.anchors] == [
        anchor.family for anchor in schedule.anchors
    ]


def test_foldable_result_records_nominal_and_effective_geometry_provenance():
    state = FoldableRotorState(
        id="screen",
        hinge_radius_m=0.075,
        opening_angle_rad=math.radians(-30.0),
        deployed_angle_rad=0.0,
    )
    result = solve_foldable_bem_rotor(
        _blade(),
        state,
        _condition(),
        _schedule(),
        settings=BEMRotorSettings(
            8,
            "station_span",
            BEMAnnulusSettings(loading_branch="signed_nonreversed"),
        ),
    )
    payload = result.as_mapping()

    assert payload["schema_version"] == 1
    assert payload["state"]["id"] == "screen"
    assert payload["nominal_geometry"]["diameter_m"] == pytest.approx(0.30)
    assert payload["effective_geometry"]["diameter_m"] < 0.30
    assert payload["fixed_limit_equivalent"] is False
    assert payload["polar_schedule_id"] == "root-to-tip@fold:screen"
    json.dumps(payload)


@pytest.mark.parametrize(
    "state, message",
    (
        (
            FoldableRotorState("outside", 0.16, 0.0, 0.0),
            "hinge_radius_m",
        ),
        (
            FoldableRotorState(
                "collapsed", 0.075, -math.pi / 2.0, 0.0
            ),
            "positive radial projection",
        ),
        (
            FoldableRotorState("wrapped", 0.075, 2.0 * math.pi, 0.0),
            "within 90 degrees",
        ),
    ),
)
def test_unsupported_fold_states_fail_closed(state, message):
    with pytest.raises(FoldableRotorGeometryError, match=message):
        project_foldable_blade(_blade(), state)


def test_projection_is_continuous_at_the_fully_open_limit():
    blade = _blade()
    deltas = (1.0e-2, 1.0e-3, 1.0e-4)
    diameters = tuple(
        project_foldable_blade(
            blade,
            FoldableRotorState("near-open", 0.075, -delta, 0.0),
        ).effective_blade.diameter_m
        for delta in deltas
    )

    errors = tuple(blade.diameter_m - diameter for diameter in diameters)
    assert errors[2] < errors[1] < errors[0]
    assert diameters[-1] == pytest.approx(blade.diameter_m, abs=1.0e-9)
    near_open = project_foldable_blade(
        blade, FoldableRotorState("near-open", 0.075, -1.0e-8, 0.0)
    )
    assert not near_open.fixed_limit_equivalent
    assert near_open.effective_blade is not blade


def test_projection_inserts_a_continuous_same_airfoil_hinge_station():
    blade = BladeGeometry(
        diameter_m=0.30,
        hub_radius_m=0.02,
        blade_count=2,
        stations=(
            BladeStation(0.2, 0.04, 0.45, "same"),
            BladeStation(0.8, 0.02, 0.25, "same"),
            BladeStation(1.0, 0.015, 0.15, "same"),
        ),
    )
    projection = project_foldable_blade(
        blade, FoldableRotorState("partial", 0.075, -0.5, 0.0)
    )

    assert projection.inserted_hinge_station
    hinge = next(
        station
        for station in projection.stations
        if station.nominal_radius_m == pytest.approx(0.075)
    )
    assert hinge.effective_radius_m == pytest.approx(0.075)
    assert hinge.airfoil_id == "same"


def test_projection_rejects_implicit_hinge_across_airfoil_boundary():
    with pytest.raises(FoldableRotorGeometryError, match="explicit blade station"):
        project_foldable_blade(
            _blade(), FoldableRotorState("partial", 0.090, -0.5, 0.0)
        )


def test_fixed_limit_evidence_requires_and_proves_exact_deployed_state():
    state = FoldableRotorState("deployed", 0.075, 0.0, 0.0)
    settings = BEMRotorSettings(
        8,
        "station_span",
        BEMAnnulusSettings(loading_branch="signed_nonreversed"),
    )

    evidence = assess_fixed_limit_equivalence(
        _blade(), state, (_condition(),), _schedule(), settings=settings
    )

    assert evidence.passed
    assert evidence.point_count == 1
    assert evidence.maximum_absolute_thrust_delta_n == 0.0
    assert evidence.maximum_absolute_torque_delta_nm == 0.0
    assert evidence.cases[0].rotor_mapping_equal
    assert evidence.as_mapping()["schema_version"] == 1

    with pytest.raises(FoldableRotorGeometryError, match="deployed state"):
        assess_fixed_limit_equivalence(
            _blade(),
            FoldableRotorState("partial", 0.075, -0.1, 0.0),
            (_condition(),),
            _schedule(),
            settings=settings,
        )
    with pytest.raises(FoldableRotorGeometryError, match="deployed state"):
        assess_fixed_limit_equivalence(
            _blade(),
            FoldableRotorState("almost", 0.075, 1.0e-16, 0.0),
            (_condition(),),
            _schedule(),
            settings=settings,
        )


def test_fixed_limit_evidence_contract_rejects_empty_or_duplicate_cases():
    state = FoldableRotorState("deployed", 0.075, 0.0, 0.0)
    case = FixedLimitEquivalenceCase("same", True, 0.0, 0.0, 0.0, 0.0)

    with pytest.raises(ValueError, match="at least one"):
        FixedLimitEquivalenceEvidence(state, ())
    with pytest.raises(ValueError, match="unique"):
        FixedLimitEquivalenceEvidence(state, (case, case))


def test_fixed_limit_assessment_rejects_invalid_state_type_cleanly():
    with pytest.raises(TypeError, match="FoldableRotorState"):
        assess_fixed_limit_equivalence(
            _blade(), object(), (_condition(),), _schedule()
        )


def test_opening_sweep_preserves_deployed_baseline_and_is_screening_only():
    blade = _blade()
    states = tuple(
        FoldableRotorState(
            f"fold-{degrees}", 0.075, math.radians(-degrees), 0.0
        )
        for degrees in (0, 15, 30, 45, 60)
    )
    evidence = assess_foldable_opening_sensitivity(
        blade,
        states,
        (_condition(),),
        _schedule(),
        settings=BEMRotorSettings(
            8,
            "station_span",
            BEMAnnulusSettings(loading_branch="signed_nonreversed"),
        ),
    )

    assert isinstance(evidence, FoldableOpeningSweepEvidence)
    assert evidence.state_count == 5
    assert evidence.condition_count == 1
    assert evidence.case_count == 5
    assert evidence.deployed_endpoint_exact
    assert evidence.qualification == "screening_only_until_pr06c_passes"
    assert evidence.cases[0].thrust_ratio_to_deployed == 1.0
    assert evidence.cases[0].torque_ratio_to_deployed == 1.0
    assert all(
        upper.effective_diameter_m < lower.effective_diameter_m
        for lower, upper in zip(evidence.cases, evidence.cases[1:])
    )
    assert evidence.as_mapping()["physical_qualification"] is False


def test_opening_sweep_rejects_missing_endpoint_duplicate_and_disordered_states():
    partial = FoldableRotorState("partial", 0.075, -0.2, 0.0)
    deployed = FoldableRotorState("deployed", 0.075, 0.0, 0.0)

    with pytest.raises(FoldableRotorGeometryError, match="deployed state first"):
        assess_foldable_opening_sensitivity(
            _blade(), (partial,), (_condition(),), _schedule()
        )
    with pytest.raises(ValueError, match="unique"):
        assess_foldable_opening_sensitivity(
            _blade(), (deployed, deployed), (_condition(),), _schedule()
        )
    with pytest.raises(ValueError, match="strictly increase"):
        assess_foldable_opening_sensitivity(
            _blade(),
            (
                deployed,
                FoldableRotorState("more", 0.075, -0.4, 0.0),
                FoldableRotorState("less", 0.075, -0.2, 0.0),
            ),
            (_condition(),),
            _schedule(),
        )
