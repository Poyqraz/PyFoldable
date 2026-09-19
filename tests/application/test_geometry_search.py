"""GEOM-01 uses existing kinematics/mesh and never selects incomplete geometry."""
from dataclasses import replace
import hashlib
import json
import re

import pytest

from pyfoldable.application.design_analysis import DesignAnalysisArtifact
from pyfoldable.application.geometry_search import prepare_geometry_search, run_geometry_search
from pyfoldable.application.design_search import SearchError
from pyfoldable.application import geometry_search as service
from pyfoldable.application.surface_clearance import SurfaceClearanceInputs
from test_polar_upload import draft


def _clearance_artifact(queries, **extra):
    document = {
        "physical_qualification": extra.get("physical_qualification", False),
        "full_propeller_clearance": extra.get("full_propeller_clearance", None),
        "modeled_surface_status": extra.get("modeled_surface_status", "unknown"),
        "node_comparisons": extra.get("node_comparisons", 1),
        "feature_tests": extra.get("feature_tests", 0),
        "hardware_queries": extra.get("hardware_queries", 0),
        "queries": queries,
        "request_sha256": "a" * 64,
    }
    text = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return DesignAnalysisArtifact("a" * 64, hashlib.sha256(text.encode()).hexdigest(), text,
                                  "surface_clearance_screening.json")


def _query(kind, status):
    return {"kind": kind, "a": "a", "b": "b",
            "result": {"status": status, "node_comparisons": 1, "feature_tests": 0}}


def _separated_surface_queries():
    return [_query("hub", "separated"), _query("own_root_tip", "separated"),
            _query("interblade", "separated")]


def _bind_clearance(monkeypatch, artifact_or_factory, **changes):
    calls = []

    def fake_run(request):
        calls.append(request)
        return artifact_or_factory(request) if callable(artifact_or_factory) else artifact_or_factory

    monkeypatch.setattr("pyfoldable.application.surface_clearance.run_surface_clearance", fake_run)
    input_keys = ("end_angle_deg", "required_clearance_m", "max_node_comparisons",
                  "max_feature_tests", "max_hardware_queries")
    inputs = {key: changes.pop(key) for key in input_keys if key in changes}
    prepared = prepare_geometry_search(
        draft(),
        hinge_radii_m=changes.pop("hinge_radii_m", (0.06,)),
        stowed_angles_deg=changes.pop("stowed_angles_deg", (-10.,)),
        clearance_inputs=SurfaceClearanceInputs(**inputs),
        hardware_json=changes.pop("hardware_json", None),
    )
    if changes:
        raise AssertionError(f"unused bind kwargs: {sorted(changes)}")
    return prepared, calls


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


def test_unbound_search_does_not_consume_clearance_or_change_unknown_constraints(monkeypatch):
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda *a, **k: pytest.fail("unbound GEOM-01 must not run GEOM-04"),
    )
    result = json.loads(run_geometry_search(request(hinge_radii_m=(.06,), stowed_angles_deg=(-150.,))).report_json)
    row = result["candidates"][0]
    assert row["constraints"]["surface_path_clearance"] is None
    assert row["constraints"]["interblade_clearance"] is None
    assert row["details"]["surface_path_clearance_status"] == "unknown_no_swept_surface_collision_model"
    assert result["physical_qualification"] is False
    assert row["details"].get("full_propeller_clearance") is None


def test_hardware_cannot_bind_without_clearance_inputs():
    from test_hardware_clearance_motion import raw
    with pytest.raises(SearchError, match="clearance"):
        prepare_geometry_search(draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
                                hardware_json=raw())


def test_clearance_binding_changes_request_identity_and_keeps_qualification_closed():
    unbound = prepare_geometry_search(draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,))
    bound = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    tighter = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10., required_clearance_m=.001),
    )
    context = json.loads(bound.context_json)
    assert bound.request_sha256 != unbound.request_sha256
    assert bound.request_sha256 != tighter.request_sha256
    assert context["candidate_clearance"]["physical_qualification"] is False
    assert context["candidate_clearance"]["full_propeller_clearance"] is None
    assert context["base_draft_toml"] == draft().toml


def test_mismatched_hardware_hub_is_rejected_at_prepare():
    from test_hardware_clearance_motion import raw
    with pytest.raises(SearchError, match="radius"):
        prepare_geometry_search(
            draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
            clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
            hardware_json=raw(radius=10.),
        )


def test_candidate_clearance_rebuilds_draft_and_never_reuses_one_report(monkeypatch):
    prepared, calls = _bind_clearance(
        monkeypatch, _clearance_artifact(_separated_surface_queries()),
        hinge_radii_m=(.06, .1), stowed_angles_deg=(-10., -30.),
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    assert len(calls) == 4
    identities = []
    for request_obj in calls:
        identities.append((request_obj.draft.draft_sha256, request_obj.inputs.end_angle_deg))
        model, _, _ = service._inputs(request_obj.draft)
        hinge = next(row["parameters"]["hinge_radius_m"] for row in result["candidates"]
                     if abs(row["parameters"]["stowed_angle_deg"] - request_obj.inputs.end_angle_deg) < 1e-12
                     and abs(row["parameters"]["hinge_radius_m"] - model.hinge.radius_m) < 1e-12)
        assert hinge == pytest.approx(model.hinge.radius_m)
        assert request_obj.draft.toml != prepared.draft.toml or model.hinge.radius_m == pytest.approx(.1)
    assert len(set(identities)) == 4
    assert prepared.draft == draft()
    for row in result["candidates"]:
        assert row["details"]["full_propeller_clearance"] is None
        assert row["details"]["physical_qualification"] is False
        assert row["details"]["candidate_hinge_radius_m"] == pytest.approx(row["parameters"]["hinge_radius_m"])
        assert row["details"]["clearance_end_angle_deg"] == pytest.approx(row["parameters"]["stowed_angle_deg"])
        assert row["details"]["clearance_request_sha256"] != result["candidates"][0]["details"]["clearance_request_sha256"] or row is result["candidates"][0]


def test_query_mapping_never_promotes_unknown_or_missing_pairs_to_passed(monkeypatch):
    cases = [
        ([], None, None),
        ([_query("interblade", "separated")], None, True),
        ([_query("hub", "separated"), _query("own_root_tip", "unknown"),
          _query("interblade", "separated")], None, True),
        ([_query("hub", "separated"), _query("own_root_tip", "separated"),
          _query("interblade", "unknown")], True, None),
        ([_query("hub", "violation"), _query("own_root_tip", "separated"),
          _query("interblade", "separated")], False, True),
        ([_query("hub", "separated"), _query("own_root_tip", "separated"),
          _query("interblade", "violation")], True, False),
        (_separated_surface_queries(), True, True),
    ]
    for queries, surface, interblade in cases:
        prepared, _ = _bind_clearance(monkeypatch, _clearance_artifact(queries))
        row = json.loads(run_geometry_search(prepared).report_json)["candidates"][0]
        assert row["constraints"]["surface_path_clearance"] is surface
        assert row["constraints"]["interblade_clearance"] is interblade
        if surface is not True or interblade is not True:
            assert row["status"] != "feasible"


def test_forged_clearance_qualification_flags_cannot_pass_or_widen_scope(monkeypatch):
    prepared, _ = _bind_clearance(
        monkeypatch,
        _clearance_artifact(
            _separated_surface_queries(),
            physical_qualification=True,
            full_propeller_clearance=True,
            modeled_surface_status="separated",
        ),
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    assert result["physical_qualification"] is False
    assert row["details"]["physical_qualification"] is False
    assert row["details"]["full_propeller_clearance"] is None
    assert row["constraints"]["surface_path_clearance"] is True
    assert row["constraints"]["interblade_clearance"] is True


def test_bound_hardware_without_hardware_rows_stays_unknown(monkeypatch):
    from test_hardware_clearance_motion import raw
    prepared, _ = _bind_clearance(
        monkeypatch, _clearance_artifact(_separated_surface_queries()),
        hardware_json=raw(),
    )
    row = json.loads(run_geometry_search(prepared).report_json)["candidates"][0]
    assert row["constraints"]["surface_path_clearance"] is None
    assert row["constraints"]["interblade_clearance"] is None
    assert row["status"] != "feasible"


def test_hardware_violation_fails_both_constraints(monkeypatch):
    from test_hardware_clearance_motion import raw
    queries = _separated_surface_queries() + [_query("hardware_surface", "violation")]
    prepared, _ = _bind_clearance(
        monkeypatch, _clearance_artifact(queries), hardware_json=raw(),
    )
    row = json.loads(run_geometry_search(prepared).report_json)["candidates"][0]
    assert row["constraints"]["surface_path_clearance"] is False
    assert row["constraints"]["interblade_clearance"] is False
    assert row["status"] != "feasible"
    assert row["details"]["surface_path_clearance_status"] == "scoped_geom04_violation"


def test_candidate_clearance_error_stays_unknown(monkeypatch):
    def boom(request):
        raise ValueError("candidate clearance failed")

    monkeypatch.setattr("pyfoldable.application.surface_clearance.run_surface_clearance", boom)
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    row = json.loads(run_geometry_search(prepared).report_json)["candidates"][0]
    assert row["constraints"]["surface_path_clearance"] is None
    assert row["constraints"]["interblade_clearance"] is None
    assert row["details"]["surface_path_clearance_status"] == "unknown_candidate_clearance_unresolved"
    assert row["status"] != "feasible"


def test_hardware_unknown_blocks_both_constraints_even_if_surfaces_separated(monkeypatch):
    from test_hardware_clearance_motion import raw
    queries = _separated_surface_queries() + [
        _query("hardware_surface", "unknown"),
    ]
    prepared, calls = _bind_clearance(
        monkeypatch, _clearance_artifact(queries, hardware_queries=0),
        hardware_json=raw(),
    )
    row = json.loads(run_geometry_search(prepared).report_json)["candidates"][0]
    assert calls and calls[0].hardware_json == raw()
    assert row["constraints"]["surface_path_clearance"] is None
    assert row["constraints"]["interblade_clearance"] is None
    assert row["status"] != "feasible"


def test_shared_clearance_budget_leaves_later_candidates_unknown(monkeypatch):
    def factory(request):
        return _clearance_artifact(_separated_surface_queries(), node_comparisons=request.inputs.max_node_comparisons)

    prepared, calls = _bind_clearance(
        monkeypatch, factory, hinge_radii_m=(.06, .1), stowed_angles_deg=(-10.,),
        max_node_comparisons=3,
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    assert len(calls) == 1
    first, second = result["candidates"]
    assert first["constraints"]["surface_path_clearance"] is True
    assert first["constraints"]["interblade_clearance"] is True
    assert second["constraints"]["surface_path_clearance"] is None
    assert second["constraints"]["interblade_clearance"] is None
    assert second["details"]["surface_path_clearance_status"] == "unknown_clearance_budget_exhausted"
    assert second["status"] != "feasible"
    assert result["best_candidate"] is None


def test_real_candidate_clearance_stays_unqualified_and_pair_scoped():
    prepared = prepare_geometry_search(
        draft(chord_scale=.1), hinge_radii_m=(.1,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-180., max_node_comparisons=4000),
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    assert result["physical_qualification"] is False
    assert row["details"]["full_propeller_clearance"] is None
    assert row["details"]["physical_qualification"] is False
    assert row["details"]["clearance_end_angle_deg"] == pytest.approx(-10.)
    assert row["constraints"]["surface_path_clearance"] is not True or all(
        query["result"]["status"] == "separated"
        for query in row["details"]["clearance_queries"]
        if query["kind"] in {"hub", "own_root_tip"}
    )
    if row["constraints"]["surface_path_clearance"] is True:
        assert row["details"]["surface_path_clearance_status"] != "unknown_no_swept_surface_collision_model"
    if None in row["constraints"].values():
        assert row["status"] == "blocked"
        assert result["best_candidate"] is None
