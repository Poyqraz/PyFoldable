import json
import math
from pathlib import Path

import pytest

from pyfoldable.application.folding_mechanism import (
    MechanismGeometryInputs,
    build_mechanism_geometry_audit,
    build_mechanism_physics_fixture,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
V02_CONFIG = REPO_ROOT / "configs/foldable/TIP_HINGED_250_V02.json"
V01_CONFIG = REPO_ROOT / "configs/foldable/TIP_HINGED_250_V01.json"
STATIONS = (0.20, 0.40, 0.60, 0.80, 0.98)


def _inputs(**overrides):
    values = {
        "diameter_m": 0.250,
        "hub_radius_m": 0.018,
        "hinge_radius_m": 0.100,
        "fold_angle_deg": -180.0,
        "stowed_requirement_m": 0.140,
    }
    values.update(overrides)
    return MechanismGeometryInputs(**values)


def test_default_geometry_exposes_unreachable_stowed_target_and_station_gaps():
    audit = build_mechanism_geometry_audit(_inputs(), STATIONS)

    assert audit.minimum_centerline_envelope_diameter_m == pytest.approx(0.200)
    assert audit.minimum_requirement_reachable is False
    assert audit.current_envelope_requirement_met is False
    assert audit.stowed_requirement_margin_m == pytest.approx(-0.060)
    assert audit.root_surface_gap_m == pytest.approx(0.007)
    assert audit.tip_surface_gap_m == pytest.approx(0.0025)
    assert audit.station_span_complete is False
    assert audit.screening_checks_passed is False
    assert "stowed_requirement_unreachable" in audit.compatibility_reasons
    assert "surface_stations_do_not_cover_hub_to_tip" in audit.compatibility_reasons
    assert audit.classification == "kinematic_screening_only"
    assert audit.physical_qualification is False


def test_planar_centerline_envelope_uses_true_distance_not_radial_projection():
    audit = build_mechanism_geometry_audit(
        _inputs(fold_angle_deg=-90.0, stowed_requirement_m=0.250),
        (0.144, 1.0),
    )

    expected_radius = math.hypot(0.100, 0.025)
    assert audit.projected_effective_diameter_m == pytest.approx(0.200)
    assert audit.centerline_envelope_diameter_m == pytest.approx(2.0 * expected_radius)
    assert audit.centerline_envelope_diameter_m > audit.projected_effective_diameter_m


def test_reachable_target_is_distinct_from_current_angle_compliance():
    audit = build_mechanism_geometry_audit(
        _inputs(fold_angle_deg=-90.0, stowed_requirement_m=0.205),
        (0.144, 1.0),
    )

    assert audit.minimum_requirement_reachable is True
    assert audit.current_envelope_requirement_met is False
    assert audit.current_requirement_margin_m < 0.0
    assert "current_envelope_exceeds_requirement" in audit.compatibility_reasons


def test_full_fold_path_collision_is_reported_even_when_target_is_reachable():
    audit = build_mechanism_geometry_audit(
        _inputs(
            diameter_m=0.250,
            hub_radius_m=0.025,
            hinge_radius_m=0.060,
            fold_angle_deg=-90.0,
            stowed_requirement_m=0.140,
        ),
        (0.20, 0.48, 1.0),
    )

    assert audit.minimum_requirement_reachable is True
    assert audit.collision_free_minimum_envelope_diameter_m == pytest.approx(0.120)
    assert audit.full_stow_path_hub_clearance_m == pytest.approx(-0.025)
    assert "full_stow_path_intersects_hub" in audit.compatibility_reasons
    assert audit.screening_checks_passed is False


def test_open_geometry_matches_nominal_diameter_when_station_span_is_complete():
    audit = build_mechanism_geometry_audit(
        _inputs(fold_angle_deg=0.0, stowed_requirement_m=0.250),
        (0.144, 0.5, 1.0),
    )

    assert audit.centerline_envelope_diameter_m == pytest.approx(0.250)
    assert audit.minimum_centerline_envelope_diameter_m == pytest.approx(0.200)
    assert audit.hub_centerline_clearance_m == pytest.approx(0.082)
    assert audit.station_span_complete is True
    assert audit.minimum_requirement_reachable is True
    assert audit.current_envelope_requirement_met is True
    assert audit.screening_checks_passed is True
    assert not audit.compatibility_reasons


@pytest.mark.parametrize(
    "overrides",
    [
        {"diameter_m": 0.0},
        {"hub_radius_m": 0.101},
        {"hinge_radius_m": 0.126},
        {"fold_angle_deg": 1.0},
        {"stowed_requirement_m": -0.1},
    ],
)
def test_mechanism_geometry_rejects_impossible_inputs(overrides):
    with pytest.raises((TypeError, ValueError)):
        build_mechanism_geometry_audit(_inputs(**overrides), STATIONS)


def test_versioned_physics_fixture_separates_moments_without_aero_load():
    fixture = build_mechanism_physics_fixture(
        V02_CONFIG,
        rpm=7100.0,
        theta_deg=-90.0,
    )

    assert fixture.fixture_id == "TIP_HINGED_250_V02"
    assert len(fixture.source_sha256) == 64
    assert fixture.classification == "software_fixture_screening_only"
    assert fixture.physical_qualification is False
    assert fixture.aerodynamic_load_included is False
    assert fixture.selected.rpm == pytest.approx(7100.0)
    assert fixture.selected.theta_deg == pytest.approx(-90.0)
    assert fixture.selected.centrifugal_moment_nm > 0.0
    assert fixture.selected.aerodynamic_moment_nm == 0.0
    assert math.isfinite(fixture.selected.net_moment_nm)
    assert len(fixture.curve) == 37
    assert fixture.curve[0].theta_deg == pytest.approx(-180.0)
    assert fixture.curve[-1].theta_deg == pytest.approx(0.0)
    assert fixture.curve[0].centrifugal_moment_nm == pytest.approx(0.0, abs=1e-12)
    for point in fixture.curve:
        assert point.net_moment_nm == pytest.approx(
            point.centrifugal_moment_nm
            + point.aerodynamic_moment_nm
            - point.stiffness_moment_nm
            - point.damping_moment_nm
            - point.stop_moment_nm
            - point.friction_moment_nm
        )


def test_physics_fixture_rejects_angle_outside_hard_stops():
    with pytest.raises(ValueError, match="hard-stop"):
        build_mechanism_physics_fixture(V02_CONFIG, rpm=7100.0, theta_deg=1.0)


def test_physics_fixture_rejects_an_unapproved_fixture_version():
    with pytest.raises(ValueError, match="TIP_HINGED_250_V02"):
        build_mechanism_physics_fixture(V01_CONFIG, rpm=7100.0, theta_deg=-45.0)


def test_physics_fixture_rejects_same_id_with_modified_parameters(tmp_path):
    document = json.loads(V02_CONFIG.read_text(encoding="utf-8"))
    document["geometry"]["tip_segment_mass_kg"] = 99.0
    changed = tmp_path / "TIP_HINGED_250_V02.json"
    changed.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256"):
        build_mechanism_physics_fixture(changed, rpm=7100.0, theta_deg=-90.0)


@pytest.mark.parametrize("rpm", [12000.1, 1e200])
def test_physics_fixture_rejects_speed_outside_ui_contract(rpm):
    with pytest.raises(ValueError, match="rpm"):
        build_mechanism_physics_fixture(V02_CONFIG, rpm=rpm, theta_deg=-90.0)


def test_geometry_audit_reports_when_stations_do_not_cover_the_hinge():
    audit = build_mechanism_geometry_audit(
        _inputs(hinge_radius_m=0.100),
        (0.144, 0.50, 0.70),
    )

    assert audit.hinge_station_covered is False
    assert "hinge_outside_surface_station_span" in audit.compatibility_reasons
