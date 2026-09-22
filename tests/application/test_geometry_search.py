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


def _modeled_status(queries):
    states = {(query.get("result") or {}).get("status") for query in queries}
    if "violation" in states:
        return "violation"
    if not states or "unknown" in states or None in states:
        return "unknown"
    return "separated"


def _bound_report_artifact(request, **fields):
    document = {
        "schema_version": 2,
        "request": json.loads(request.context_json),
        "request_sha256": request.request_sha256,
        "physical_qualification": False,
        "classification": "blocked",
        "modeled_surface_status": "separated",
        "full_propeller_clearance": None,
        "station_span_complete": False,
        "root_gap_m": 0.0,
        "tip_gap_m": 0.0,
        "excluded_regions": {
            "root_radial_width_m": 0.0, "hinge_half_width_m": 0.0,
            "source": "", "status": "not_evaluated",
            "scope": "declared_reference_radial_bands_move_with_each_rigid_part",
        },
        "original_triangle_count": 1,
        "retained_triangle_count": 1,
        "queries": _separated_surface_queries(),
        "hardware_status": None,
        "limitations": ["open_triangle_surfaces_not_solid_containment"],
    }
    queries = fields.get("queries", document["queries"])
    if "node_comparisons" not in fields:
        document["node_comparisons"] = sum(
            (query.get("result") or {}).get("node_comparisons", 0)
            for query in queries if query.get("kind") in {"hub", "own_root_tip", "interblade"}
            and type((query.get("result") or {}).get("node_comparisons")) is int)
    if "feature_tests" not in fields:
        document["feature_tests"] = sum(
            (query.get("result") or {}).get("feature_tests", 0)
            for query in queries if query.get("kind") in {"hub", "own_root_tip", "interblade"}
            and type((query.get("result") or {}).get("feature_tests")) is int)
    if "hardware_queries" not in fields:
        document["hardware_queries"] = sum(
            (query.get("result") or {}).get("hardware_queries", 0)
            for query in queries if query.get("kind") in {"hardware_surface", "hardware_pair"}
            and type((query.get("result") or {}).get("hardware_queries")) is int)
    document.update(fields)
    text = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return DesignAnalysisArtifact(
        request.request_sha256, hashlib.sha256(text.encode()).hexdigest(), text,
        "surface_clearance_screening.json")


def _clearance_artifact(queries, **extra):
    def factory(request):
        payload = dict(extra)
        payload.setdefault("queries", queries)
        payload.setdefault("modeled_surface_status", extra.get(
            "modeled_surface_status", _modeled_status(queries)))
        return _bound_report_artifact(request, **payload)
    return factory


def _geom04(row):
    return row["details"]["geom04_clearance"]


def _query(kind, status, **fields):
    result = {
        "status": status, "node_comparisons": 0, "feature_tests": 0,
        "lower_bound_m": 0.002 if status == "separated" else None,
        "witness_clearance_m": 0.0 if status == "violation" else None,
        "contact_status": "contact" if status == "violation" else "unknown",
        "reason": status,
        "intervals": [{
            "angle_min_rad": 0.0, "angle_max_rad": 0.0, "status": status,
            "lower_bound_m": None, "witness_clearance_m": None,
            "witness_angle_rad": 0.0 if status == "violation" else None,
            "method": "aabb_bound", "contact_status": "unknown",
            "point_a": None, "point_b": None,
        }],
    }
    a = fields.pop("a", "a")
    b = fields.pop("b", "b")
    result.update(fields)
    return {"kind": kind, "a": a, "b": b, "result": result}


def _assert_protected_constraints_unknown(row, result=None):
    assert row["constraints"]["surface_path_clearance"] is None
    assert row["constraints"]["interblade_clearance"] is None
    assert row["status"] != "feasible"
    if result is not None:
        assert result["best_candidate"] is None
        assert result["physical_qualification"] is False


def _separated_surface_queries():
    return [_query("hub", "separated", node_comparisons=1),
            _query("own_root_tip", "separated"),
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
    assert context["candidate_clearance"]["selection_effect"] == "evidence_only_does_not_alter_geom01_constraints"
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
        _assert_protected_constraints_unknown(row, result)
        assert row["details"]["full_propeller_clearance"] is None
        assert row["details"]["physical_qualification"] is False
        ns = _geom04(row)
        assert ns["candidate_hinge_radius_m"] == pytest.approx(row["parameters"]["hinge_radius_m"])
        assert ns["clearance_end_angle_deg"] == pytest.approx(row["parameters"]["stowed_angle_deg"])
        assert ns["clearance_request_sha256"] != _geom04(result["candidates"][0])["clearance_request_sha256"] or row is result["candidates"][0]
        assert row["details"]["surface_path_clearance_status"] == "unknown_no_swept_surface_collision_model"


def test_geom04_violation_is_visible_but_does_not_change_geom01_constraints(monkeypatch):
    queries = [_query("hub", "violation"), _query("own_root_tip", "separated"),
               _query("interblade", "separated")]
    prepared, _ = _bind_clearance(monkeypatch, _clearance_artifact(queries))
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    ns = _geom04(row)
    _assert_protected_constraints_unknown(row, result)
    assert ns["scoped_geom04_status"] == "scoped_geom04_violation"
    assert any(query["result"]["status"] == "violation" for query in ns["report"]["queries"])
    assert any(query["result"].get("witness_clearance_m") == 0.0 for query in ns["report"]["queries"])
    assert any(query["result"].get("intervals") for query in ns["report"]["queries"])
    assert ns["report"]["excluded_regions"]["status"] == "not_evaluated"
    assert row["details"]["surface_path_clearance_status"] == "unknown_no_swept_surface_collision_model"


def test_geom04_separated_is_visible_but_does_not_change_geom01_constraints(monkeypatch):
    prepared, _ = _bind_clearance(monkeypatch, _clearance_artifact(_separated_surface_queries()))
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    ns = _geom04(row)
    _assert_protected_constraints_unknown(row, result)
    assert ns["scoped_geom04_status"] == "scoped_geom04_separated"
    assert {query["result"]["status"] for query in ns["report"]["queries"]} == {"separated"}
    assert all(query["result"].get("lower_bound_m") == 0.002 for query in ns["report"]["queries"])
    assert ns["report"]["modeled_surface_status"] == "separated"
    assert row["details"]["surface_path_clearance_status"] == "unknown_no_swept_surface_collision_model"


def test_geom04_unknown_keeps_protected_constraints_none(monkeypatch):
    queries = [_query("hub", "unknown"), _query("own_root_tip", "separated"),
               _query("interblade", "separated")]
    prepared, _ = _bind_clearance(monkeypatch, _clearance_artifact(queries))
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    ns = _geom04(row)
    _assert_protected_constraints_unknown(row, result)
    assert ns["scoped_geom04_status"] == "unknown_scoped_geom04"
    assert any(query["result"]["status"] == "unknown" for query in ns["report"]["queries"])


def test_hardware_violation_evidence_does_not_alter_protected_constraints(monkeypatch):
    from test_hardware_clearance_motion import raw
    queries = _separated_surface_queries() + [
        _query("hardware_surface", "violation", hardware_queries=0),
    ]
    prepared, calls = _bind_clearance(
        monkeypatch, _clearance_artifact(queries), hardware_json=raw(),
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    ns = _geom04(row)
    _assert_protected_constraints_unknown(row, result)
    assert calls and calls[0].hardware_json == raw()
    assert ns["scoped_geom04_status"] == "scoped_geom04_violation"
    assert any(query["kind"] == "hardware_surface" and query["result"]["status"] == "violation"
               for query in ns["report"]["queries"])
    assert ns["report"]["request"]["hardware"]["raw_sha256"] == hashlib.sha256(raw()).hexdigest()


def _complete_span_draft():
    base = draft(chord_scale=.1)
    text, root_count = re.subn(r"r_over_R = 0\.2(?:0*)\b", "r_over_R = 0.144", base.toml)
    text, tip_count = re.subn(r"r_over_R = 0\.98(?:0*)\b", "r_over_R = 1.0", text)
    assert root_count == tip_count == 1
    return replace(base, toml=text, draft_sha256=hashlib.sha256(text.encode()).hexdigest())


def test_bound_geom04_result_cannot_make_a_candidate_feasible_or_selectable(monkeypatch):
    complete = _complete_span_draft()
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        _clearance_artifact(_separated_surface_queries()),
    )
    prepared = prepare_geometry_search(
        complete, hinge_radii_m=(.06,), stowed_angles_deg=(-150.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-150.),
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    assert row["constraints"]["station_span_complete"] is True
    assert row["constraints"]["mesh_envelope_target"] is True
    assert _geom04(row)["scoped_geom04_status"] == "scoped_geom04_separated"
    _assert_protected_constraints_unknown(row, result)
    assert row["status"] == "blocked"


def test_forged_physical_qualification_true_aborts_search(monkeypatch):
    prepared, _ = _bind_clearance(
        monkeypatch,
        _clearance_artifact(_separated_surface_queries(), physical_qualification=True),
    )
    _assert_search_aborts(prepared)


def test_forged_full_propeller_clearance_true_aborts_search(monkeypatch):
    prepared, _ = _bind_clearance(
        monkeypatch,
        _clearance_artifact(_separated_surface_queries(), full_propeller_clearance=True),
    )
    _assert_search_aborts(prepared)


def test_bound_hardware_without_hardware_rows_stays_unknown_and_does_not_pass(monkeypatch):
    from test_hardware_clearance_motion import raw
    prepared, _ = _bind_clearance(
        monkeypatch, _clearance_artifact(_separated_surface_queries()),
        hardware_json=raw(),
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    _assert_protected_constraints_unknown(row, result)


def _assert_search_aborts(prepared):
    with pytest.raises(ValueError):
        run_geometry_search(prepared)


def test_foreign_real_geom04_artifact_from_another_hinge_aborts_search(monkeypatch):
    from pyfoldable.application.surface_clearance import (
        prepare_surface_clearance, run_surface_clearance,
    )
    inputs = SurfaceClearanceInputs(end_angle_deg=-10., max_node_comparisons=4000)
    draft_a = service._draft_with_hinge_radius(draft(), 0.06)
    draft_b = service._draft_with_hinge_radius(draft(), 0.10)
    req_a = prepare_surface_clearance(draft_a, inputs)
    req_b = prepare_surface_clearance(draft_b, inputs)
    art_a = run_surface_clearance(req_a)
    art_b = run_surface_clearance(req_b)
    assert art_a.request_sha256 != art_b.request_sha256
    assert json.loads(art_a.report_json)["request_sha256"] == req_a.request_sha256
    assert json.loads(art_b.report_json)["request_sha256"] == req_b.request_sha256
    swapped = {draft_a.draft_sha256: art_b, draft_b.draft_sha256: art_a}
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda request: swapped[request.draft.draft_sha256],
    )
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(0.06, 0.10), stowed_angles_deg=(-10.,),
        clearance_inputs=inputs,
    )
    _assert_search_aborts(prepared)


def test_surface_clearance_identity_changed_aborts_rather_than_succeeding(monkeypatch):
    from pyfoldable.application.surface_clearance import run_surface_clearance as real_run

    def forged(request):
        return real_run(replace(request, request_sha256="0" * 64))

    monkeypatch.setattr("pyfoldable.application.surface_clearance.run_surface_clearance", forged)
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_search_aborts(prepared)


def test_injected_programming_valueerror_aborts_search(monkeypatch):
    def boom(request):
        raise ValueError("injected programming error from GEOM-04 execution")

    monkeypatch.setattr("pyfoldable.application.surface_clearance.run_surface_clearance", boom)
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_search_aborts(prepared)


def test_malformed_artifact_json_aborts_search(monkeypatch):
    def bad_json(request):
        return DesignAnalysisArtifact(
            request.request_sha256, "0" * 64, "{not-json", "surface_clearance_screening.json")

    monkeypatch.setattr("pyfoldable.application.surface_clearance.run_surface_clearance", bad_json)
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_search_aborts(prepared)


def test_invalid_report_identity_aborts_search(monkeypatch):
    def mismatched(request):
        report = json.loads(_bound_report_artifact(request).report_json)
        report["request_sha256"] = "b" * 64
        text = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return DesignAnalysisArtifact(
            request.request_sha256, hashlib.sha256(text.encode()).hexdigest(), text,
            "surface_clearance_screening.json")

    monkeypatch.setattr("pyfoldable.application.surface_clearance.run_surface_clearance", mismatched)
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_search_aborts(prepared)


def test_hardware_unknown_evidence_does_not_alter_protected_constraints(monkeypatch):
    from test_hardware_clearance_motion import raw
    queries = _separated_surface_queries() + [
        _query("hardware_surface", "unknown", hardware_queries=0),
    ]
    prepared, calls = _bind_clearance(
        monkeypatch, _clearance_artifact(queries, hardware_queries=0),
        hardware_json=raw(),
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    assert calls and calls[0].hardware_json == raw()
    _assert_protected_constraints_unknown(row, result)
    assert _geom04(row)["scoped_geom04_status"] == "unknown_scoped_geom04"


def test_each_candidate_keeps_its_configured_geom04_budget(monkeypatch):
    def factory(request):
        assert request.inputs.max_node_comparisons == 1
        return _bound_report_artifact(request, node_comparisons=1)

    prepared, calls = _bind_clearance(
        monkeypatch, factory, hinge_radii_m=(.06, .1), stowed_angles_deg=(-10.,),
        max_node_comparisons=1,
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    context = json.loads(prepared.context_json)["candidate_clearance"]
    assert len(calls) == 2
    assert context["per_candidate_max_node_comparisons"] == 1
    assert context["aggregate_node_comparison_ceiling"] == 2
    first, second = result["candidates"]
    _assert_protected_constraints_unknown(first, result)
    _assert_protected_constraints_unknown(second, result)
    for row, request_obj in zip(result["candidates"], calls):
        ns = row["details"]["geom04_clearance"]
        assert ns["execution_status"] == "completed"
        assert ns["report"]["node_comparisons"] == 1
        assert request_obj.inputs.max_node_comparisons == 1
        assert row["constraints"]["surface_path_clearance"] is None
        assert row["constraints"]["interblade_clearance"] is None
    assert result["best_candidate"] is None


def test_real_candidate_clearance_attaches_evidence_without_changing_gates():
    prepared = prepare_geometry_search(
        draft(chord_scale=.1), hinge_radii_m=(.1,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-180., max_node_comparisons=4000),
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    _assert_protected_constraints_unknown(row, result)
    assert row["details"]["full_propeller_clearance"] is None
    assert row["details"]["physical_qualification"] is False
    ns = _geom04(row)
    assert ns["clearance_end_angle_deg"] == pytest.approx(-10.)
    assert ns["clearance_request_sha256"]
    assert ns["report"]["queries"]
    assert ns["scoped_geom04_status"] in {
        "scoped_geom04_violation", "scoped_geom04_separated", "unknown_scoped_geom04",
    }
    assert row["details"]["surface_path_clearance_status"] == "unknown_no_swept_surface_collision_model"
    assert row["status"] != "feasible"


def test_complete_geom04_report_round_trips_through_geom01_evidence():
    from pyfoldable.application.surface_clearance import (
        prepare_surface_clearance, run_surface_clearance,
    )
    inputs = SurfaceClearanceInputs(end_angle_deg=-10., max_node_comparisons=4000)
    prepared = prepare_geometry_search(
        draft(chord_scale=.1), hinge_radii_m=(.1,), stowed_angles_deg=(-10.,),
        clearance_inputs=inputs,
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    ns = row["details"]["geom04_clearance"]
    independent = run_surface_clearance(prepare_surface_clearance(
        service._draft_with_hinge_radius(prepared.draft, .1),
        replace(inputs, end_angle_deg=-10.),
    ))
    expected = json.loads(independent.report_json)
    assert ns["execution_status"] == "completed"
    assert ns["report"] == expected
    assert ns["clearance_request_sha256"] == independent.request_sha256
    assert ns["artifact_request_sha256"] == independent.request_sha256
    assert ns["artifact_report_sha256"] == independent.report_sha256
    for key in (
        "schema_version", "request", "request_sha256", "physical_qualification",
        "classification", "modeled_surface_status", "full_propeller_clearance",
        "station_span_complete", "root_gap_m", "tip_gap_m", "excluded_regions",
        "original_triangle_count", "retained_triangle_count", "node_comparisons",
        "feature_tests", "queries", "hardware_queries", "hardware_status",
        "limitations",
    ):
        assert key in ns["report"]
    assert "inputs" in ns["report"]["request"]
    assert "implementation_sha256" in ns["report"]["request"]
    assert ns["report"]["queries"]
    _assert_protected_constraints_unknown(row, result)


def test_oversized_geom04_evidence_preserves_geom01_audit_and_does_not_truncate(monkeypatch):
    from pyfoldable.application.design_search import _snapshot

    with pytest.raises(SearchError, match="byte budget"):
        _snapshot({"padding": "x" * (256 * 1024)}, 256 * 1024)

    def oversized(request):
        return _bound_report_artifact(request, padding="x" * (300 * 1024))

    complete = _complete_span_draft()
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance", oversized)
    prepared = prepare_geometry_search(
        complete, hinge_radii_m=(.06,), stowed_angles_deg=(-150.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-150.),
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    assert row["objective"] is not None
    assert row["details"]["audit"]
    assert row["constraints"]["surface_path_clearance"] is None
    assert row["constraints"]["interblade_clearance"] is None
    assert set(row["constraints"]) >= {
        "centerline_target", "centerline_path_clearance", "station_span_complete",
        "mesh_envelope_target", "surface_path_clearance", "interblade_clearance",
    }
    assert row["status"] == "blocked"
    ns = row["details"]["geom04_clearance"]
    assert ns["report"] is None
    assert "queries" not in ns
    assert ns["execution_status"] == "evidence_attachment_exceeds_search_details_budget"
    assert "256" in str(ns["failure_reason"])
    _assert_protected_constraints_unknown(row, result)
    assert result["all_evaluations_succeeded"] is True


def test_prepare_does_not_reject_candidate_exclusion_against_base_hinge(monkeypatch):
    from pyfoldable.application.surface_clearance import prepare_surface_clearance
    from pyfoldable.application import surface_clearance as clearance

    run_calls = []
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda *a, **k: run_calls.append("prepare") or pytest.fail("prepare must not execute GEOM-04"),
    )
    inputs = SurfaceClearanceInputs(
        end_angle_deg=-10., hinge_attachment_m=0.008,
        contact_source="synthetic hinge exclusion fixture",
    )
    candidate_draft = service._draft_with_hinge_radius(draft(), 0.06)
    independent = prepare_surface_clearance(candidate_draft, inputs)
    assert json.loads(independent.context_json)["draft_sha256"] == candidate_draft.draft_sha256
    model, _, _ = service._inputs(candidate_draft)
    assert model.hinge.radius_m == pytest.approx(0.06)

    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(0.06, 0.10), stowed_angles_deg=(-10.,),
        clearance_inputs=inputs,
    )
    assert run_calls == []
    assert prepared.draft == draft()
    base_model, _, _ = service._inputs(prepared.draft)
    assert base_model.hinge.radius_m == pytest.approx(0.10)

    hinges = []
    real_prepare = clearance.prepare_surface_clearance

    def spy(draft_obj, candidate_inputs, hardware_json=None):
        seen, _, _ = service._inputs(draft_obj)
        hinges.append(seen.hinge.radius_m)
        return real_prepare(draft_obj, candidate_inputs, hardware_json=hardware_json)

    monkeypatch.setattr(clearance, "prepare_surface_clearance", spy)
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda request: _bound_report_artifact(request),
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    assert any(abs(h - 0.06) < 1e-12 for h in hinges)
    close = next(row for row in result["candidates"]
                 if abs(row["parameters"]["hinge_radius_m"] - 0.06) < 1e-12)
    far = next(row for row in result["candidates"]
               if abs(row["parameters"]["hinge_radius_m"] - 0.10) < 1e-12)
    assert close["details"]["geom04_clearance"]["execution_status"] == "completed"
    assert far["details"]["geom04_clearance"]["execution_status"] == "candidate_validation_failed"
    _assert_protected_constraints_unknown(close, result)
    _assert_protected_constraints_unknown(far, result)


def test_impossible_candidate_accounting_aborts_search(monkeypatch):
    def overclaim(request):
        return _bound_report_artifact(
            request, node_comparisons=request.inputs.max_node_comparisons + 1)

    prepared, _ = _bind_clearance(
        monkeypatch, overclaim, max_node_comparisons=1,
    )
    _assert_search_aborts(prepared)


def test_geom04_arithmetic_error_aborts_search(monkeypatch):
    def boom(request):
        raise ZeroDivisionError("injected arithmetic failure from GEOM-04 execution")

    monkeypatch.setattr("pyfoldable.application.surface_clearance.run_surface_clearance", boom)
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_search_aborts(prepared)


def test_hinge_rewrite_valueerror_aborts_rather_than_failed_evidence(monkeypatch):
    def boom(*args, **kwargs):
        raise ValueError("injected hinge rewrite error")

    monkeypatch.setattr(service, "_draft_with_hinge_radius", boom)
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    with pytest.raises(ValueError, match="injected hinge rewrite"):
        run_geometry_search(prepared)


def test_invalid_candidate_geometry_is_bounded_validation_failure(monkeypatch):
    from pyfoldable.application.surface_clearance import prepare_surface_clearance
    inputs = SurfaceClearanceInputs(
        end_angle_deg=-10., hinge_attachment_m=0.008,
        contact_source="synthetic hinge exclusion fixture",
    )
    independent = prepare_surface_clearance(service._draft_with_hinge_radius(draft(), 0.06), inputs)
    assert independent.request_sha256
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda request: _bound_report_artifact(request),
    )
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(0.10,), stowed_angles_deg=(-10.,),
        clearance_inputs=inputs,
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    ns = _geom04(row)
    assert ns["execution_status"] == "candidate_validation_failed"
    assert ns["report"] is None
    assert result["all_evaluations_succeeded"] is True
    _assert_protected_constraints_unknown(row, result)


def test_programming_valueerror_inside_prepare_aborts(monkeypatch):
    from pyfoldable.application import surface_clearance as clearance

    def boom(value):
        raise ValueError("injected programming error after domain validation")

    monkeypatch.setattr(clearance, "_json", boom)
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_search_aborts(prepared)


def test_serializer_valueerror_during_prepare_aborts(monkeypatch):
    from pyfoldable.application import surface_clearance as clearance

    def boom(value):
        raise ValueError("Out of range float values are not JSON compliant")

    monkeypatch.setattr(clearance, "_json", boom)
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_search_aborts(prepared)


def test_internal_unexpected_valueerror_during_prepare_aborts(monkeypatch):
    from pyfoldable.application import surface_clearance as clearance

    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )

    def boom(*args, **kwargs):
        raise ValueError("internal unexpected ValueError")

    monkeypatch.setattr(clearance, "Path", boom)
    _assert_search_aborts(prepared)


def test_valid_geom04_report_is_attached_without_mutation():
    from pyfoldable.application.surface_clearance import (
        prepare_surface_clearance, run_surface_clearance,
    )
    inputs = SurfaceClearanceInputs(end_angle_deg=-10., max_node_comparisons=4000)
    prepared = prepare_geometry_search(
        draft(chord_scale=.1), hinge_radii_m=(.1,), stowed_angles_deg=(-10.,),
        clearance_inputs=inputs,
    )
    independent = run_surface_clearance(prepare_surface_clearance(
        service._draft_with_hinge_radius(prepared.draft, .1),
        replace(inputs, end_angle_deg=-10.),
    ))
    result = json.loads(run_geometry_search(prepared).report_json)
    ns = _geom04(result["candidates"][0])
    attached = ns["report"]
    original = json.loads(independent.report_json)
    assert attached == original
    assert attached["physical_qualification"] is False
    assert attached["full_propeller_clearance"] is None
    assert ns["artifact_report_sha256"] == independent.report_sha256
    assert ns["artifact_report_sha256"] == hashlib.sha256(independent.report_json.encode()).hexdigest()
    assert attached["node_comparisons"] == original["node_comparisons"]
    assert attached["feature_tests"] == original["feature_tests"]
    assert attached["hardware_queries"] == original["hardware_queries"]


def _nan_artifact(request, **fields):
    report = json.loads(_bound_report_artifact(request).report_json)
    report.update(fields)
    text = json.dumps(report, allow_nan=True)
    return DesignAnalysisArtifact(
        request.request_sha256, hashlib.sha256(text.encode()).hexdigest(), text,
        "surface_clearance_screening.json")


def test_nan_in_hashed_report_aborts_search(monkeypatch):
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda request: _nan_artifact(request, root_gap_m=float("nan")),
    )
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_search_aborts(prepared)


def test_infinity_in_hashed_report_aborts_search(monkeypatch):
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda request: _nan_artifact(request, tip_gap_m=float("inf")),
    )
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_search_aborts(prepared)


def test_missing_queries_aborts_search(monkeypatch):
    def missing(request):
        report = json.loads(_bound_report_artifact(request).report_json)
        del report["queries"]
        text = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return DesignAnalysisArtifact(
            request.request_sha256, hashlib.sha256(text.encode()).hexdigest(), text,
            "surface_clearance_screening.json")

    monkeypatch.setattr("pyfoldable.application.surface_clearance.run_surface_clearance", missing)
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_search_aborts(prepared)


def test_malformed_query_result_aborts_search(monkeypatch):
    def malformed(request):
        return _bound_report_artifact(
            request,
            queries=[{"kind": "hub", "a": "a", "b": "hub_envelope", "result": "nope"}],
            node_comparisons=0, feature_tests=0,
        )

    monkeypatch.setattr("pyfoldable.application.surface_clearance.run_surface_clearance", malformed)
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_search_aborts(prepared)


def test_wrong_required_field_type_aborts_search(monkeypatch):
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda request: _bound_report_artifact(request, schema_version="2"),
    )
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_search_aborts(prepared)


def test_query_level_node_overclaim_aborts_search(monkeypatch):
    def overclaim(request):
        queries = [
            _query("hub", "separated", node_comparisons=1_000_000_000),
            _query("own_root_tip", "separated", node_comparisons=0),
            _query("interblade", "separated", node_comparisons=0),
        ]
        return _bound_report_artifact(request, queries=queries, node_comparisons=3)

    prepared, _ = _bind_clearance(monkeypatch, overclaim, max_node_comparisons=3)
    _assert_search_aborts(prepared)


def test_query_level_feature_overclaim_aborts_search(monkeypatch):
    def overclaim(request):
        queries = [
            _query("hub", "separated", node_comparisons=1, feature_tests=10_000),
            _query("own_root_tip", "separated", node_comparisons=0, feature_tests=0),
            _query("interblade", "separated", node_comparisons=0, feature_tests=0),
        ]
        return _bound_report_artifact(
            request, queries=queries, node_comparisons=1, feature_tests=1)

    prepared, _ = _bind_clearance(monkeypatch, overclaim, max_feature_tests=8)
    _assert_search_aborts(prepared)


def test_hardware_query_overclaim_aborts_search(monkeypatch):
    def overclaim(request):
        queries = _separated_surface_queries() + [
            _query("hardware_surface", "unknown", node_comparisons=0, feature_tests=0,
                   hardware_queries=1_000_000_000),
        ]
        return _bound_report_artifact(
            request, queries=queries, node_comparisons=3, feature_tests=0, hardware_queries=0)

    prepared, _ = _bind_clearance(monkeypatch, overclaim, max_hardware_queries=4)
    _assert_search_aborts(prepared)


def test_ledger_sum_inconsistent_with_top_level_aborts_search(monkeypatch):
    def inconsistent(request):
        queries = [
            _query("hub", "separated", node_comparisons=1),
            _query("own_root_tip", "separated", node_comparisons=1),
            _query("interblade", "separated", node_comparisons=1),
        ]
        return _bound_report_artifact(request, queries=queries, node_comparisons=2)

    prepared, _ = _bind_clearance(monkeypatch, inconsistent, max_node_comparisons=8)
    _assert_search_aborts(prepared)


def test_negative_accounting_aborts_search(monkeypatch):
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda request: _bound_report_artifact(request, node_comparisons=-1),
    )
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_search_aborts(prepared)


def test_query_level_negative_accounting_aborts_search(monkeypatch):
    def negative(request):
        queries = [
            _query("hub", "separated", node_comparisons=-1),
            _query("own_root_tip", "separated", node_comparisons=0),
            _query("interblade", "separated", node_comparisons=0),
        ]
        return _bound_report_artifact(request, queries=queries, node_comparisons=1)

    prepared, _ = _bind_clearance(monkeypatch, negative, max_node_comparisons=8)
    _assert_search_aborts(prepared)


def test_non_integer_accounting_aborts_search(monkeypatch):
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda request: _bound_report_artifact(request, node_comparisons=1.5),
    )
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_search_aborts(prepared)


def test_query_level_non_integer_accounting_aborts_search(monkeypatch):
    def fractional(request):
        queries = [
            _query("hub", "separated", node_comparisons=1.5),
            _query("own_root_tip", "separated", node_comparisons=0),
            _query("interblade", "separated", node_comparisons=0),
        ]
        return _bound_report_artifact(request, queries=queries, node_comparisons=1)

    prepared, _ = _bind_clearance(monkeypatch, fractional, max_node_comparisons=8)
    _assert_search_aborts(prepared)


def test_details_serialization_error_aborts_rather_than_oversize(monkeypatch):
    real_json = service._json

    def boom(value):
        if isinstance(value, dict) and "geom04_clearance" in value:
            raise SearchError("injected details serializer failure")
        return real_json(value)

    monkeypatch.setattr(service, "_json", boom)
    prepared, _ = _bind_clearance(monkeypatch, _clearance_artifact(_separated_surface_queries()))
    _assert_search_aborts(prepared)


def _rehashed_artifact(request, mutate, **fields):
    artifact = _bound_report_artifact(request, **fields)
    report = json.loads(artifact.report_json)
    mutate(report)
    text = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return DesignAnalysisArtifact(
        request.request_sha256, hashlib.sha256(text.encode()).hexdigest(), text,
        "surface_clearance_screening.json")


def test_prepare_arithmetic_error_aborts_search_not_failed_row(monkeypatch):
    from pyfoldable.application import surface_clearance as clearance

    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )

    def boom(*args, **kwargs):
        raise ZeroDivisionError("injected arithmetic failure from candidate preparation")

    monkeypatch.setattr(clearance, "prepare_surface_clearance", boom)
    with pytest.raises(SearchError, match="Candidate clearance preparation failed.") as caught:
        run_geometry_search(prepared)
    assert isinstance(caught.value.__cause__, ZeroDivisionError)


def test_prepare_typeerror_aborts_search(monkeypatch):
    from pyfoldable.application import surface_clearance as clearance

    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )

    def boom(*args, **kwargs):
        raise TypeError("injected type error from candidate preparation")

    monkeypatch.setattr(clearance, "prepare_surface_clearance", boom)
    with pytest.raises(TypeError, match="injected type error from candidate preparation"):
        run_geometry_search(prepared)


def test_prepare_searcherror_aborts_search(monkeypatch):
    from pyfoldable.application import surface_clearance as clearance

    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )

    def boom(*args, **kwargs):
        raise SearchError("injected search error from candidate preparation")

    monkeypatch.setattr(clearance, "prepare_surface_clearance", boom)
    _assert_search_aborts(prepared)


def _schema_case_aborts(monkeypatch, mutate, **fields):
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda request: _rehashed_artifact(request, mutate, **fields),
    )
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_search_aborts(prepared)


def test_non_object_interval_aborts_search(monkeypatch):
    _schema_case_aborts(
        monkeypatch,
        lambda report: report["queries"][0]["result"].__setitem__(
            "intervals", ["not an interval"]),
    )


def test_invalid_interval_status_aborts_search(monkeypatch):
    def mutate(report):
        report["queries"][0]["result"]["intervals"][0]["status"] = "not-a-status"

    _schema_case_aborts(monkeypatch, mutate)


def test_non_numeric_interval_lower_bound_aborts_search(monkeypatch):
    def mutate(report):
        report["queries"][0]["result"]["intervals"][0]["lower_bound_m"] = "bad"

    _schema_case_aborts(monkeypatch, mutate)


def test_object_query_lower_bound_aborts_search(monkeypatch):
    def mutate(report):
        report["queries"][0]["result"]["lower_bound_m"] = {"nested": True}

    _schema_case_aborts(monkeypatch, mutate)


def test_missing_query_result_intervals_aborts_search(monkeypatch):
    def mutate(report):
        del report["queries"][0]["result"]["intervals"]

    _schema_case_aborts(monkeypatch, mutate)


def test_missing_query_result_reason_aborts_search(monkeypatch):
    def mutate(report):
        del report["queries"][0]["result"]["reason"]

    _schema_case_aborts(monkeypatch, mutate)


def test_oversized_malformed_interval_aborts_as_invalid_not_oversize(monkeypatch):
    def malformed_oversize(request):
        def mutate(report):
            report["queries"][0]["result"]["intervals"][0]["status"] = "not-a-status"

        return _rehashed_artifact(request, mutate, padding="x" * (300 * 1024))

    complete = _complete_span_draft()
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        malformed_oversize,
    )
    prepared = prepare_geometry_search(
        complete, hinge_radii_m=(.06,), stowed_angles_deg=(-150.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-150.),
    )
    try:
        artifact = run_geometry_search(prepared)
    except ValueError:
        return
    document = json.loads(artifact.report_json)
    namespace = document["candidates"][0]["details"]["geom04_clearance"]
    pytest.fail(
        "malformed oversized evidence must abort as invalid; got "
        f"execution_status={namespace.get('execution_status')} "
        f"all_evaluations_succeeded={document.get('all_evaluations_succeeded')}"
    )


def test_empty_intervals_remain_valid_producer_budget_exhaustion(monkeypatch):
    def exhausted(request):
        queries = [
            _query("hub", "unknown", node_comparisons=1, intervals=[]),
            _query("own_root_tip", "unknown", intervals=[]),
            _query("interblade", "unknown", intervals=[]),
        ]
        return _bound_report_artifact(
            request, queries=queries, modeled_surface_status="unknown",
            classification="blocked")

    prepared, _ = _bind_clearance(monkeypatch, exhausted)
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    assert _geom04(row)["execution_status"] == "completed"
    assert all(query["result"]["intervals"] == [] for query in _geom04(row)["report"]["queries"])
    _assert_protected_constraints_unknown(row, result)


def _assert_aborts_not_failed_grid_row(prepared):
    try:
        artifact = run_geometry_search(prepared)
    except SearchError:
        return
    document = json.loads(artifact.report_json)
    row = document["candidates"][0]
    pytest.fail(
        "nested qualification forgery must abort before Evaluation; got "
        f"all_evaluations_succeeded={document.get('all_evaluations_succeeded')} "
        f"status={row.get('status')} constraints={row.get('constraints')} "
        f"details={row.get('details')}"
    )


def test_nested_forged_qualification_aborts_before_failed_row(monkeypatch):
    def mutate(report):
        report["extra"] = {"physical_qualification": True}

    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda request: _rehashed_artifact(request, mutate),
    )
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_aborts_not_failed_grid_row(prepared)


def test_deep_nested_forged_qualification_in_query_result_aborts(monkeypatch):
    def mutate(report):
        report["queries"][0]["result"]["extra"] = {"physical_qualification": True}

    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda request: _rehashed_artifact(request, mutate),
    )
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10.),
    )
    _assert_aborts_not_failed_grid_row(prepared)


def test_nested_false_qualification_attaches_unchanged(monkeypatch):
    captured = {}

    def factory(request):
        artifact = _rehashed_artifact(
            request, lambda report: report.__setitem__(
                "extra", {"physical_qualification": False}))
        captured["artifact"] = artifact
        return artifact

    prepared, _ = _bind_clearance(monkeypatch, factory)
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    attached = _geom04(row)["report"]
    original = json.loads(captured["artifact"].report_json)
    assert attached == original
    assert attached["extra"]["physical_qualification"] is False
    _assert_protected_constraints_unknown(row, result)


def _negative_policy(required_clearance_m=0.0005, **changes):
    from pyfoldable.application.geometry_clearance_policy import NegativeClearancePolicy
    values = {"required_clearance_m": required_clearance_m}
    values.update(changes)
    return NegativeClearancePolicy(**values)


def _policy_violation_queries(kind, a, b):
    import math
    witness = math.radians(-10.0) / 2
    return [_query(
        kind, "violation",
        a=a, b=b,
        node_comparisons=1, feature_tests=0,
        intervals=[{
            "angle_min_rad": math.radians(-150.0),
            "angle_max_rad": 0.0,
            "status": "violation",
            "lower_bound_m": None,
            "witness_clearance_m": 0.0,
            "witness_angle_rad": witness,
            "method": "triangle_distance",
            "contact_status": "penetrating",
            "point_a": None,
            "point_b": None,
        }],
    )]


def test_negative_policy_declaration_changes_geometry_request_sha():
    low = _negative_policy(0.001)
    high = _negative_policy(0.002)
    base = prepare_geometry_search(draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,))
    bound_low = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,), clearance_policy=low)
    bound_high = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,), clearance_policy=high)
    assert base.request_sha256 != bound_low.request_sha256
    assert bound_low.request_sha256 != bound_high.request_sha256
    context = json.loads(bound_low.context_json)
    assert context["negative_clearance_policy"]["required_clearance_m"] == 0.001
    assert context["negative_clearance_policy"]["motion_domain"] == (
        "synchronous_planar_rigid_tips_from_zero_to_declared_endpoint")
    assert context["negative_clearance_policy"]["policy_id"] == "geom01_negative_clearance_v1"


def test_enabled_surface_violation_makes_candidate_infeasible_and_not_best(monkeypatch):
    complete = _complete_span_draft()
    queries = _policy_violation_queries("own_root_tip", "blade_1_root", "blade_1_tip")
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        _clearance_artifact(queries),
    )
    prepared = prepare_geometry_search(
        complete, hinge_radii_m=(.06,), stowed_angles_deg=(-150.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-150.),
        clearance_policy=_negative_policy(),
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    assert row["constraints"]["surface_path_clearance"] is False
    assert row["constraints"]["interblade_clearance"] is None
    assert row["status"] == "infeasible"
    assert result["best_candidate"] is None
    assert result["physical_qualification"] is False
    assert row["details"]["full_propeller_clearance"] is None
    assert row["details"]["geom04_clearance"]["report"]["queries"][0]["kind"] == "own_root_tip"


def test_enabled_interblade_violation_makes_candidate_infeasible(monkeypatch):
    complete = _complete_span_draft()
    queries = _policy_violation_queries("interblade", "blade_1_tip", "blade_2_root")
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        _clearance_artifact(queries),
    )
    prepared = prepare_geometry_search(
        complete, hinge_radii_m=(.06,), stowed_angles_deg=(-150.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-150.),
        clearance_policy=_negative_policy(),
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    assert row["constraints"]["surface_path_clearance"] is None
    assert row["constraints"]["interblade_clearance"] is False
    assert row["status"] == "infeasible"
    assert result["best_candidate"] is None


def test_enabled_policy_without_a_negative_keeps_candidate_blocked(monkeypatch):
    complete = _complete_span_draft()
    queries = [
        _query("own_root_tip", "separated", a="blade_1_root", b="blade_1_tip", node_comparisons=1),
        _query("interblade", "separated", a="blade_1_root", b="blade_2_tip"),
    ]
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        _clearance_artifact(queries),
    )
    prepared = prepare_geometry_search(
        complete, hinge_radii_m=(.06,), stowed_angles_deg=(-150.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-150.),
        clearance_policy=_negative_policy(),
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    assert row["constraints"]["surface_path_clearance"] is None
    assert row["constraints"]["interblade_clearance"] is None
    assert row["status"] == "blocked"
    assert result["best_candidate"] is None
    assert True not in row["constraints"].values()


def test_policy_leaves_a_real_geom04_report_unchanged_and_never_true():
    from pyfoldable.application.surface_clearance import prepare_surface_clearance, run_surface_clearance
    inputs = SurfaceClearanceInputs(end_angle_deg=-10., max_node_comparisons=4000)
    policy = _negative_policy(inputs.required_clearance_m)
    prepared = prepare_geometry_search(
        draft(chord_scale=.1), hinge_radii_m=(.1,), stowed_angles_deg=(-10.,),
        clearance_inputs=inputs, clearance_policy=policy,
    )
    independent = run_surface_clearance(prepare_surface_clearance(
        service._draft_with_hinge_radius(prepared.draft, .1),
        replace(inputs, end_angle_deg=-10.),
    ))
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    attached = _geom04(row)["report"]
    assert attached == json.loads(independent.report_json)
    assert row["constraints"]["surface_path_clearance"] is not True
    assert row["constraints"]["interblade_clearance"] is not True
    assert result["physical_qualification"] is False
    assert attached["full_propeller_clearance"] is None
    assert result["best_candidate"] is None


def test_policy_metadata_near_details_budget_does_not_fail_the_row(monkeypatch):
    complete = _complete_span_draft()
    queries = _policy_violation_queries("own_root_tip", "blade_1_root", "blade_1_tip")

    def run_padded(padding):
        monkeypatch.setattr(
            "pyfoldable.application.surface_clearance.run_surface_clearance",
            lambda request: _bound_report_artifact(request, queries=queries, padding="x" * padding),
        )
        prepared = prepare_geometry_search(
            complete, hinge_radii_m=(.06,), stowed_angles_deg=(-150.,),
            clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-150.),
            clearance_policy=_negative_policy(),
        )
        artifact = run_geometry_search(prepared)
        document = json.loads(artifact.report_json)
        return document, document["candidates"][0]

    failed_padding = None
    low, high = 180_000, 320_000
    while low <= high:
        padding = (low + high) // 2
        document, row = run_padded(padding)
        failed = row["status"] == "failed" or document["all_evaluations_succeeded"] is False
        if failed:
            failed_padding = padding
            high = padding - 1
        else:
            low = padding + 1
            namespace = row["details"]["geom04_clearance"]
            surface = row["constraints"]["surface_path_clearance"]
            interblade = row["constraints"]["interblade_clearance"]
            assert surface is not True and interblade is not True
            if namespace["execution_status"] == "completed":
                assert surface is False
                assert namespace["report"]["padding"] == "x" * padding
            else:
                assert namespace["execution_status"] == "evidence_attachment_exceeds_search_details_budget"
                assert namespace["report"] is None
                assert surface is None and interblade is None
                assert row["details"]["geom04_negative_clearance_policy"]["surface_path_clearance"]["reason"] == (
                    "evidence_unavailable_oversize")
    assert failed_padding is None


def test_policy_without_geom04_inputs_records_no_evidence():
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(.06,), stowed_angles_deg=(-10.,),
        clearance_policy=_negative_policy(),
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    assert row["constraints"]["surface_path_clearance"] is None
    assert row["constraints"]["interblade_clearance"] is None
    assert "geom04_clearance" not in row["details"]
    recorded = row["details"]["geom04_negative_clearance_policy"]
    assert recorded["surface_path_clearance"]["reason"] == "no_evidence"
    assert recorded["interblade_clearance"]["reason"] == "no_evidence"
    assert result["best_candidate"] is None


def test_policy_on_candidate_validation_failure_stays_none(monkeypatch):
    inputs = SurfaceClearanceInputs(
        end_angle_deg=-10., hinge_attachment_m=0.008,
        contact_source="synthetic hinge exclusion fixture",
    )
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda request: pytest.fail("validation failure must not execute GEOM-04"),
    )
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(0.10,), stowed_angles_deg=(-10.,),
        clearance_inputs=inputs, clearance_policy=_negative_policy(inputs.required_clearance_m),
    )
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    assert _geom04(row)["execution_status"] == "candidate_validation_failed"
    assert row["constraints"]["surface_path_clearance"] is None
    assert row["constraints"]["interblade_clearance"] is None
    assert row["details"]["geom04_negative_clearance_policy"]["surface_path_clearance"]["reason"] == (
        "candidate_validation_failed")
    _assert_protected_constraints_unknown(row, result)
