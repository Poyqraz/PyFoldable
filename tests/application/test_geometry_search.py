"""GEOM-01 uses existing kinematics/mesh and never selects incomplete geometry."""
from dataclasses import replace
import hashlib
import json
import re

import pytest

from pyfoldable.application.geometry_search import prepare_geometry_search, run_geometry_search
from pyfoldable.application.design_search import SearchError
from pyfoldable.application import geometry_search as service
from test_polar_upload import draft


@pytest.mark.parametrize("changes", [{"angular_speed": "0 rpm"}, {"forward_speed": "-3 m/s"}])
def test_geometry_does_not_inherit_bem_operating_condition_restrictions(changes):
    from pyfoldable.application.design_analysis import _load, DesignAnalysisError
    base = draft(**changes)
    prepared = prepare_geometry_search(base, hinge_radii_m=(.1,), stowed_angles_deg=(-90.,))
    assert json.loads(run_geometry_search(prepared).report_json)["evaluations_attempted"] == 1
    with pytest.raises(DesignAnalysisError):
        _load(base)  # aerodynamic restrictions are preserved


def request(**changes):
    values = dict(hinge_radii_m=(0.06, 0.07, 0.1), stowed_angles_deg=(-180., -150.))
    values.update(changes)
    return prepare_geometry_search(draft(), **values)


def test_prepare_is_idle_canonical_and_preserves_the_active_draft(monkeypatch):
    monkeypatch.setattr(service, "build_propeller_preview_mesh", lambda *a, **k: pytest.fail("automatic mesh"))
    base = request()
    assert base == request(hinge_radii_m=(.1, .07, .06), stowed_angles_deg=(-150., -180.))
    assert base.draft == draft()
    context = json.loads(base.context_json)
    assert context["full_180_centerline_lower_bound_m"] == pytest.approx(.143)
    assert context["full_180_target_necessary_condition_met"] is False


def test_grid_retains_canonical_failures_partial_path_and_mesh_bounds():
    base = request()
    report = run_geometry_search(base)
    doc = json.loads(report.report_json)
    assert doc["evaluations_attempted"] == 6
    assert doc["best_candidate"] is None
    assert doc["physical_qualification"] is False
    assert doc["status_counts"]["failed"] == 0
    assert report == run_geometry_search(base)
    assert report.report_sha256 == hashlib.sha256(report.report_json.encode()).hexdigest()
    for row in doc["candidates"]:
        audit = row["details"]["audit"]
        assert row["constraints"]["station_span_complete"] is False
        assert row["constraints"]["surface_path_clearance"] is None
        assert row["constraints"]["interblade_clearance"] is None
        assert row["details"]["mesh_qualification"] == "geometry_preview_not_cad_or_physical_result"
        assert row["objective"] == audit["centerline_envelope_diameter_m"]
        if row["parameters"]["hinge_radius_m"] == .1:
            assert row["constraints"]["centerline_target"] is False
        if row["parameters"] == {"hinge_radius_m": .06, "stowed_angle_deg": -150.}:
            assert row["constraints"]["centerline_target"] is True
            assert row["constraints"]["centerline_path_clearance"] is True
            assert audit["full_stow_path_hub_clearance_m"] < 0  # -180 is a separate proposed path
            assert row["details"]["proposed_path_minimum_hub_clearance_m"] > 0
    assert json.loads(base.context_json)["base_draft_toml"] == base.draft.toml


@pytest.mark.parametrize("changes", [
    {"hinge_radii_m": ()}, {"hinge_radii_m": (.018,)}, {"hinge_radii_m": (.125,)},
    {"hinge_radii_m": (True,)}, {"hinge_radii_m": (.06, .06)},
    {"stowed_angles_deg": (float("nan"),)}, {"stowed_angles_deg": (-181.,)},
    {"stowed_angles_deg": (1.,)}, {"max_evaluations": 2}, {"max_evaluations": 26},
])
def test_invalid_or_overbudget_grid_fails_before_running(changes):
    with pytest.raises(SearchError):
        request(**changes)


def test_source_changes_and_forged_requests_fail_closed():
    base = request()
    assert base.request_sha256 != request(stowed_angles_deg=(-150.,)).request_sha256
    with pytest.raises(SearchError, match="identity"):
        run_geometry_search(replace(base, request_sha256="0" * 64))
    bad = replace(base.draft, toml=base.draft.toml + "\n")
    with pytest.raises(ValueError):
        prepare_geometry_search(bad, hinge_radii_m=(.06,), stowed_angles_deg=(-150.,))


@pytest.mark.parametrize("old,new", [('axis_elevation = "90 deg"', 'axis_elevation = "0 deg"'),
    ('axial_offset = "0 mm"', 'axial_offset = "2 mm"'),
    ('tangential_offset = "0 mm"', 'tangential_offset = "1 mm"')])
def test_unsupported_geometry_cannot_be_silently_projected(old, new):
    base = draft()
    key = old.split(" = ")[0]
    text, count = re.subn(r"^" + key + r" = .*", new, base.toml, flags=re.MULTILINE)
    assert count == 1
    altered = replace(base, toml=text, draft_sha256=hashlib.sha256(text.encode()).hexdigest())
    with pytest.raises(SearchError, match="planar"):
        prepare_geometry_search(altered, hinge_radii_m=(.06,), stowed_angles_deg=(-150.,))


def test_hinge_outside_station_span_retains_audit_without_invented_mesh():
    result = json.loads(run_geometry_search(request(hinge_radii_m=(.02,), stowed_angles_deg=(-150.,))).report_json)
    row = result["candidates"][0]
    assert row["details"]["audit"]["hinge_station_covered"] is False
    assert row["details"]["mesh_envelope_diameter_m"] is None
    assert row["constraints"]["mesh_envelope_target"] is None
    assert result["best_candidate"] is None


def test_complete_explicit_stations_still_cannot_pass_unknown_surface_constraints():
    base = draft(chord_scale=.1)  # Narrow synthetic sections keep the endpoint inside 140 mm.
    text, root_count = re.subn(r"r_over_R = 0\.2(?:0*)\b", "r_over_R = 0.144", base.toml)
    text, tip_count = re.subn(r"r_over_R = 0\.98(?:0*)\b", "r_over_R = 1.0", text)
    assert root_count == tip_count == 1
    # Explicit synthetic full-span test input; production never fills these gaps.
    complete = replace(base, toml=text, draft_sha256=hashlib.sha256(text.encode()).hexdigest())
    req = prepare_geometry_search(complete, hinge_radii_m=(.06,), stowed_angles_deg=(-150.,))
    result = json.loads(run_geometry_search(req).report_json)
    row = result["candidates"][0]
    assert row["constraints"]["station_span_complete"] is True
    assert row["constraints"]["mesh_envelope_target"] is True
    assert row["status"] == "blocked"
    assert result["best_candidate"] is None
