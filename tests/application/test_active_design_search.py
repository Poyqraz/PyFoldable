"""Active draft integration, fixed-baseline scaling, and nonqualification."""

import hashlib
import json
from dataclasses import replace

import pytest

from pyfoldable.application.active_design_search import prepare_active_search, run_active_search
from pyfoldable.application.design_search import SearchError
from pyfoldable.application.design_search import GridSearchPlan, SearchAxis
from pyfoldable.application.polar_upload import prepare_polar_run
from pyfoldable.application import design_analysis as analysis
from test_polar_upload import draft, payload


def request(**changes):
    return prepare_active_search(prepare_polar_run(draft(), payload(), annulus_count=4),
        chord_scales=changes.pop("chord_scales", (.9, 1., 1.1)),
        twist_scales=changes.pop("twist_scales", (1.,)), minimum_thrust_n=changes.pop("minimum_thrust_n", 0.), **changes)


def test_preparation_is_idle_and_canonical(monkeypatch):
    monkeypatch.setattr(analysis, "solve_bem_rotor", lambda *a, **k: pytest.fail("automatic solve"))
    assert request() == request(chord_scales=(1.1, .9, 1.))


def test_search_uses_exact_baseline_polars_and_never_qualifies_unknown_constraints():
    base = request()
    artifact = run_active_search(base)
    doc = json.loads(artifact.report_json)
    assert doc["physical_qualification"] is False
    assert doc["best_candidate"] is None
    assert doc["evaluations_attempted"] == 3
    assert doc["status_counts"]["failed"] == 0
    assert doc["request"]["evaluator_identity"]["base_polar_json"] == payload().decode()
    assert doc["request"]["evaluator_identity"]["base_draft_toml"] == base.base.draft.toml
    for row in doc["candidates"]:
        assert row["constraints"]["structural_evidence"] is None
        assert row["constraints"]["physical_validation"] is None
        assert row["constraints"]["stowed_geometry"] is False
        assert row["objective"] == row["details"]["rotor"]["shaft_power_w"]
        assert row["details"]["rotor"]["polar_bounds"] == "error"
        assert row["details"]["rotor"]["clamped_dimensions"] == []
    assert artifact == run_active_search(base)
    assert artifact.report_sha256 == hashlib.sha256(artifact.report_json.encode()).hexdigest()


def test_scales_are_relative_to_baseline_not_previous_candidate():
    base = request(chord_scales=(.8, 1., 1.2), twist_scales=(.9, 1.1))
    doc = json.loads(run_active_search(base).report_json)
    original, _ = analysis._load(base.base.draft)
    for row in doc["candidates"]:
        detail = row["details"]
        candidate = replace(base.base.draft, toml=detail["draft_toml"],
            draft_sha256=detail["draft_sha256"], source_sha256=base.base.draft.draft_sha256)
        restored, _ = analysis._load(candidate)
        assert restored.blade.diameter_m == original.blade.diameter_m
        for before, after in zip(original.blade.stations, restored.blade.stations):
            assert after.chord_m == pytest.approx(before.chord_m * row["parameters"]["chord_scale"])
            assert after.twist_rad == pytest.approx(before.twist_rad * row["parameters"]["twist_scale"])
        assert restored.airfoils == original.airfoils


@pytest.mark.parametrize("changes", [{"minimum_thrust_n": -1}, {"minimum_thrust_n": True},
    {"minimum_thrust_n": float("nan")}, {"chord_scales": (0.,)}, {"twist_scales": (2.,)},
    {"chord_scales": ()}, {"max_evaluations": 2}, {"max_evaluations": 26}])
def test_invalid_or_unbudgeted_search_rejected(changes):
    with pytest.raises(SearchError): request(**changes)


def test_aggregate_solver_budget_rejected_before_any_solve(monkeypatch):
    monkeypatch.setattr(analysis, "solve_bem_rotor", lambda *a, **k: pytest.fail("unbudgeted solve"))
    base = prepare_polar_run(draft(), payload(), annulus_count=40)
    with pytest.raises(SearchError, match="budget"):
        prepare_active_search(base, chord_scales=(.8,.9,1.,1.1,1.2), twist_scales=(.8,.9,1.,1.1,1.2), minimum_thrust_n=0.)


def test_request_identity_tracks_all_search_inputs_and_rejects_forgery():
    base = request()
    assert base.request_sha256 != request(minimum_thrust_n=1.).request_sha256
    assert base.request_sha256 != request(chord_scales=(1.,)).request_sha256
    with pytest.raises(SearchError, match="identity"):
        run_active_search(replace(base, minimum_thrust_n=1.))


def test_expected_solver_failure_is_counted_without_a_penalty_or_partial_rotor(monkeypatch):
    def fail(*a, **k): raise analysis.DesignAnalysisError("outside polar envelope")
    monkeypatch.setattr(analysis, "run_design_analysis", fail)
    doc = json.loads(run_active_search(request()).report_json)
    assert doc["status_counts"]["failed"] == 3
    assert doc["best_candidate"] is None
    assert all(row["objective"] is None and not row["details"] for row in doc["candidates"])


def test_unmet_minimum_thrust_cannot_select_a_candidate():
    doc = json.loads(run_active_search(request(minimum_thrust_n=1e9)).report_json)
    assert all(row["constraints"]["minimum_thrust"] is False for row in doc["candidates"])
    assert doc["best_candidate"] is None


@pytest.mark.parametrize("bad_plan", [None, GridSearchPlan((SearchAxis("x", (1.,), .5, 1.5),), 1)])
def test_malformed_prepared_plan_has_controlled_rejection(bad_plan):
    with pytest.raises(SearchError):
        run_active_search(replace(request(), plan=bad_plan))


def test_unmodeled_hinge_axis_cannot_use_planar_geometry_gate():
    import re
    original = draft()
    toml = re.sub(r'axis_elevation = .*', 'axis_elevation = "0 deg"', original.toml)
    altered = replace(original, toml=toml, draft_sha256=hashlib.sha256(toml.encode()).hexdigest())
    base = prepare_polar_run(altered, payload(), annulus_count=4)
    search = prepare_active_search(base, chord_scales=(1.,), twist_scales=(1.,), minimum_thrust_n=0.)
    assert json.loads(search.context_json)["geometry_bound"]["constraint"] is None
