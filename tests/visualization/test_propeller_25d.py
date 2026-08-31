import math

import pytest

from pyfoldable.visualization.propeller_25d import (
    PreviewBladeStation,
    PropellerPreviewSpec,
    build_propeller_preview_mesh,
    naca4_section_loop,
)


STATIONS = (
    PreviewBladeStation(0.20, 0.028, 31.0),
    PreviewBladeStation(0.40, 0.026, 24.0),
    PreviewBladeStation(0.60, 0.023, 17.0),
    PreviewBladeStation(0.80, 0.017, 10.0),
    PreviewBladeStation(0.98, 0.008, 5.0),
)


def _spec(**overrides):
    values = {
        "diameter_m": 0.25,
        "hub_radius_m": 0.018,
        "blade_count": 2,
        "hinge_radius_m": 0.10,
        "fold_angle_deg": 0.0,
        "airfoil_id": "NACA2412",
        "section_point_count": 25,
    }
    values.update(overrides)
    return PropellerPreviewSpec(**values)


def test_naca4_section_loop_is_closed_finite_and_has_positive_thickness():
    loop = naca4_section_loop("NACA2412", point_count=25)

    assert len(loop) == 48
    assert all(math.isfinite(value) for point in loop for value in point)
    assert max(z for _, z in loop) > 0.0
    assert min(z for _, z in loop) < 0.0
    assert loop[0][0] == pytest.approx(1.0)
    assert min(x for x, _ in loop) == pytest.approx(0.0)


def test_preview_mesh_replicates_blades_and_builds_valid_triangles():
    mesh = build_propeller_preview_mesh(_spec(), STATIONS)

    assert mesh.blade_count == 2
    assert mesh.station_count == len(STATIONS) + 1
    assert len(mesh.vertices) == 2 * mesh.station_count * 48
    assert mesh.faces
    assert all(0 <= index < len(mesh.vertices) for face in mesh.faces for index in face)
    assert {index for face in mesh.faces for index in face} == set(
        range(len(mesh.vertices))
    )
    assert all(math.isfinite(value) for point in mesh.vertices for value in point)
    assert mesh.maximum_radius_m == pytest.approx(0.25 / 2.0)
    assert mesh.effective_radius_m == pytest.approx(0.25 / 2.0)

    first_blade = mesh.vertices[: len(mesh.vertices) // 2]
    second_blade = mesh.vertices[len(mesh.vertices) // 2 :]
    first_centroid_x = sum(point[0] for point in first_blade) / len(first_blade)
    second_centroid_x = sum(point[0] for point in second_blade) / len(second_blade)
    assert first_centroid_x == pytest.approx(-second_centroid_x)


def test_fold_transform_keeps_root_fixed_and_moves_only_hinge_outboard_geometry():
    deployed = build_propeller_preview_mesh(_spec(blade_count=1), STATIONS)
    folded = build_propeller_preview_mesh(
        _spec(blade_count=1, fold_angle_deg=-60.0), STATIONS
    )
    perimeter_count = deployed.section_point_count * 2 - 2

    root_vertex_count = (deployed.hinge_root_station_index + 1) * perimeter_count
    assert folded.vertices[:root_vertex_count] == deployed.vertices[:root_vertex_count]
    assert folded.vertices[root_vertex_count:] != deployed.vertices[root_vertex_count:]
    assert folded.effective_radius_m < deployed.effective_radius_m
    assert folded.effective_radius_m >= folded.hinge_radius_m
    assert folded.qualification == "geometry_preview_not_cad_or_physical_result"


def test_outboard_mesh_is_a_rigid_body_with_a_disconnected_hinge_seam():
    deployed = build_propeller_preview_mesh(_spec(blade_count=1), STATIONS)
    folded = build_propeller_preview_mesh(
        _spec(blade_count=1, fold_angle_deg=-60.0), STATIONS
    )
    perimeter_count = deployed.section_point_count * 2 - 2
    tip_station = deployed.station_count - 1

    for section_index in range(perimeter_count):
        deployed_hinge = deployed.vertices[
            deployed.hinge_tip_station_index * perimeter_count + section_index
        ]
        deployed_tip = deployed.vertices[tip_station * perimeter_count + section_index]
        folded_hinge = folded.vertices[
            folded.hinge_tip_station_index * perimeter_count + section_index
        ]
        folded_tip = folded.vertices[tip_station * perimeter_count + section_index]
        deployed_distance = math.dist(deployed_hinge, deployed_tip)
        folded_distance = math.dist(folded_hinge, folded_tip)
        assert folded_distance == pytest.approx(deployed_distance, abs=1e-12)

    root_vertices = set(
        range(
            deployed.hinge_root_station_index * perimeter_count,
            (deployed.hinge_root_station_index + 1) * perimeter_count,
        )
    )
    tip_vertices = set(
        range(
            deployed.hinge_tip_station_index * perimeter_count,
            (deployed.hinge_tip_station_index + 1) * perimeter_count,
        )
    )
    assert not any(
        root_vertices.intersection(face) and tip_vertices.intersection(face)
        for face in deployed.faces
    )


def test_radial_and_mesh_envelopes_are_distinct_and_never_ignore_the_fixed_root():
    deployed = build_propeller_preview_mesh(_spec(blade_count=1), STATIONS)
    stowed = build_propeller_preview_mesh(
        _spec(blade_count=1, fold_angle_deg=-180.0), STATIONS
    )

    assert 2.0 * deployed.effective_radius_m == pytest.approx(0.25)
    assert stowed.effective_radius_m == pytest.approx(stowed.hinge_radius_m)
    assert stowed.mesh_envelope_radius_m >= stowed.hinge_radius_m
    assert stowed.mesh_envelope_radius_m == pytest.approx(
        max(math.hypot(x, y) for x, y, _ in stowed.vertices)
    )


def test_centerline_envelope_uses_axis_distance_while_effective_radius_is_projection():
    folded = build_propeller_preview_mesh(
        _spec(blade_count=1, fold_angle_deg=-90.0), STATIONS
    )

    assert folded.effective_radius_m == pytest.approx(0.100)
    assert folded.centerline_envelope_radius_m == pytest.approx(
        math.hypot(0.100, 0.025)
    )
    assert folded.centerline_envelope_radius_m > folded.effective_radius_m


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"diameter_m": 0.0}, "diameter_m"),
        ({"blade_count": 0}, "blade_count"),
        ({"hub_radius_m": 0.11}, "hub_radius_m"),
        ({"hinge_radius_m": 0.13}, "hinge_radius_m"),
        ({"fold_angle_deg": 10.0}, "fold_angle_deg"),
        ({"airfoil_id": "E63"}, "NACA 4-digit"),
    ],
)
def test_preview_spec_rejects_unsupported_or_impossible_inputs(overrides, message):
    with pytest.raises((TypeError, ValueError), match=message):
        _spec(**overrides)


def test_preview_rejects_unordered_or_out_of_span_stations():
    with pytest.raises(ValueError, match="strictly increasing"):
        build_propeller_preview_mesh(_spec(), tuple(reversed(STATIONS)))


@pytest.mark.parametrize(
    "overrides",
    (
        {"hinge_radius_m": 0.019},
        {"hinge_radius_m": 0.025},
        {"hinge_radius_m": 0.124},
        {"hub_radius_m": 0.030},
    ),
)
def test_preview_rejects_hub_or_hinge_outside_the_defined_station_span(overrides):
    with pytest.raises(ValueError, match="defined blade-station span"):
        build_propeller_preview_mesh(_spec(**overrides), STATIONS)


def test_preview_rejects_non_string_airfoil_identifiers_cleanly():
    with pytest.raises(TypeError, match="airfoil_id"):
        _spec(airfoil_id=2412)


def test_package_wildcard_exports_keep_the_existing_2d_api_and_new_preview_api():
    import pyfoldable.visualization as visualization

    assert {
        "PropellerVisualState",
        "blade_polylines",
        "PropellerPreviewSpec",
        "build_propeller_preview_mesh",
    } <= set(visualization.__all__)
