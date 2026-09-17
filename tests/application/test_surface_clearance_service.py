"""GEOM-03 integration uses explicit surfaces, exclusions and bounded work."""
from dataclasses import replace
import hashlib
import json

import pytest

from pyfoldable.application import surface_clearance as service
from pyfoldable.application.surface_clearance import (
    SurfaceClearanceInputs, prepare_surface_clearance, run_surface_clearance,
)
from test_polar_upload import draft


def request(**changes):
    return prepare_surface_clearance(draft(), SurfaceClearanceInputs(**changes))


def test_preparation_binds_full_source_and_controls_without_generating_a_mesh(monkeypatch):
    monkeypatch.setattr(service, "build_propeller_preview_mesh", lambda *a, **k: pytest.fail("implicit mesh"))
    req = request()
    context = json.loads(req.context_json)
    assert context["draft_toml"] == req.draft.toml
    assert context["physical_qualification"] is False
    assert context["hub_obstacle"] == "infinite_cylinder_conservative_envelope"
    assert req == request()
    assert req.request_sha256 != request(end_angle_deg=-90.).request_sha256


@pytest.mark.parametrize("changes", [
    {"end_angle_deg": -181.}, {"end_angle_deg": True}, {"required_clearance_m": -1.},
    {"root_attachment_m": .1}, {"hinge_attachment_m": .1},
    {"hinge_attachment_m": .001},  # explicit source reference required for exclusions
    {"contact_source": "x", "root_attachment_m": float("nan")},
    {"max_node_comparisons": 0}, {"max_node_comparisons": True}, {"max_node_comparisons": 200001},
    {"max_depth": 9}, {"max_intervals": 256},
])
def test_invalid_inputs_fail_before_work(changes):
    with pytest.raises((ValueError, TypeError)):
        request(**changes)


def test_geometry_only_loading_preserves_integrity_at_zero_rpm():
    req = prepare_surface_clearance(draft(angular_speed="0 rpm"), SurfaceClearanceInputs())
    assert req.draft.toml
    forged = replace(req.draft, toml=req.draft.toml + "\n")
    with pytest.raises(ValueError):
        prepare_surface_clearance(forged, req.inputs)
    with pytest.raises(ValueError, match="identity"):
        run_surface_clearance(replace(req, request_sha256="0" * 64))


def test_partial_span_and_excluded_regions_cannot_be_promoted_to_full_clearance():
    req = request(end_angle_deg=-30., root_attachment_m=.001, hinge_attachment_m=.001,
                  contact_source="synthetic joint-region example", max_node_comparisons=3000)
    artifact = run_surface_clearance(req)
    report = json.loads(artifact.report_json)
    assert report["physical_qualification"] is False
    assert report["full_propeller_clearance"] is None
    assert report["station_span_complete"] is False
    assert report["excluded_regions"]["hinge_half_width_m"] == .001
    assert report["excluded_regions"]["status"] == "not_evaluated"
    assert report["queries"]
    assert {q["kind"] for q in report["queries"]} == {"hub", "own_root_tip", "interblade"}
    assert report["node_comparisons"] <= 3000
    assert artifact.report_sha256 == hashlib.sha256(artifact.report_json.encode()).hexdigest()
    assert artifact == run_surface_clearance(req)


def test_global_budget_exhaustion_keeps_all_remaining_queries_unknown():
    report = json.loads(run_surface_clearance(request(max_node_comparisons=1)).report_json)
    assert report["node_comparisons"] <= 1
    assert any(q["result"]["reason"] == "global_budget_exhausted" for q in report["queries"])
    assert report["modeled_surface_status"] != "separated"
    assert report["full_propeller_clearance"] is None


def test_clipping_preserves_surfaces_instead_of_dropping_whole_boundary_faces():
    triangle = ((0., 0., 0.), (2., 0., 0.), (0., 2., 0.))
    clipped = service._clip_triangle(triangle, minimum_x=1., maximum_x=3.)
    assert clipped
    points = {p for tri in clipped for p in tri}
    assert (1., 1., 0.) in points
    assert (2., 0., 0.) in points
    assert all(p[0] >= 1. for p in points)


def test_supported_surface_scope_rejects_offsets_and_unsupported_axis():
    import re
    base = draft()
    text = re.sub(r'axis_elevation = .*', 'axis_elevation = "0 deg"', base.toml)
    altered = replace(base, toml=text, draft_sha256=hashlib.sha256(text.encode()).hexdigest())
    with pytest.raises(ValueError, match="planar"):
        prepare_surface_clearance(altered, SurfaceClearanceInputs())


def test_full_span_separation_remains_scoped_to_retained_surfaces():
    from test_blade_stations import SOURCE, inputs, raw
    from pyfoldable.application.blade_stations import parse_station_bundle
    from pyfoldable.application.design_draft import build_design_draft
    from pyfoldable.core.profile_catalog import load_project_airfoil
    base = build_design_draft(SOURCE, inputs(), station_bundle=parse_station_bundle(raw()),
                             airfoil_definition=load_project_airfoil("NACA2412"))
    req = prepare_surface_clearance(base, SurfaceClearanceInputs(end_angle_deg=-10.,
        root_attachment_m=.001, hinge_attachment_m=.004, contact_source="synthetic geometry only"))
    report = json.loads(run_surface_clearance(req).report_json)
    assert report["modeled_surface_status"] == "separated"
    assert report["station_span_complete"] is True
    assert report["classification"] == "screening-only"
    assert report["full_propeller_clearance"] is None


def test_refined_service_binds_and_shares_feature_budget():
    req = request(max_feature_tests=23)
    report = json.loads(run_surface_clearance(req).report_json)
    assert report['schema_version'] == 2
    assert report['request']['inputs']['max_feature_tests'] == 23
    assert report['feature_tests'] == sum(q['result']['feature_tests'] for q in report['queries'])
    assert 0 <= report['feature_tests'] <= 23
    assert 'geometry/triangle_distance.py' in report['request']['implementation_sha256']
    assert req.request_sha256 != request(max_feature_tests=24).request_sha256


@pytest.mark.parametrize('value', [-1, True, 200001])
def test_invalid_feature_budget_rejected(value):
    with pytest.raises(ValueError):
        request(max_feature_tests=value)
