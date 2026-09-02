"""Finite-grid minimization must never turn missing constraints into approval."""

import hashlib
import json
from dataclasses import replace

import pytest

from pyfoldable.application.design_search import (
    SearchAxis, GridSearchPlan, Evaluation, EvaluationFailure, SearchError, run_grid_search,
)


def axis(name="x", values=(-1., 0., 1.)):
    return SearchAxis(name, values, -1., 1.)


def plan(*, constraints=(), budget=9):
    return GridSearchPlan((axis(), axis("y")), budget, constraints)


def run(callback, search=None, identity=None):
    return run_grid_search(search or plan(), callback, evaluator_identity=identity or {"id": "analytic-test-v1"})


def test_analytic_discrete_minimum_and_reproducible_hashes():
    def quadratic(point):
        return Evaluation((point["x"] - 1) ** 2 + point["y"] ** 2)
    result = run(quadratic)
    assert result == run(quadratic)
    doc = json.loads(result.report_json)
    best = doc["best_candidate"]
    assert best["parameters"] == {"x": 1., "y": 0.}
    assert best["objective"] == 0
    assert doc["evaluations_attempted"] == 9
    assert doc["status_counts"] == {"feasible": 9, "failed": 0, "blocked": 0, "infeasible": 0}
    assert doc["physical_qualification"] is False
    assert doc["request"]["random_seed"] is None
    assert hashlib.sha256(result.report_json.encode()).hexdigest() == result.report_sha256


def test_canonical_order_and_ties_are_independent_of_supplied_axis_order():
    original = plan()
    shuffled = GridSearchPlan((axis("y", (1., -1., 0.)), axis("x", (0., 1., -1.))), 9)
    first = run(lambda p: Evaluation(1), original)
    assert first == run(lambda p: Evaluation(1), shuffled)
    assert json.loads(first.report_json)["best_candidate"]["parameters"] == {"x": -1., "y": -1.}


@pytest.mark.parametrize("values", [(), (0., 0.), (True,), ("1",), (float("nan"),), (float("inf"),), (2.,), tuple(range(10))])
def test_invalid_axis_values(values):
    with pytest.raises(SearchError): axis(values=values)


@pytest.mark.parametrize("changes", [{"name": ""}, {"name": "bad name"}, {"lower": True}, {"upper": float("inf")}, {"lower": 2.}])
def test_axis_name_and_bounds(changes):
    with pytest.raises(SearchError): replace(axis(), **changes)


@pytest.mark.parametrize("budget", [0, True, 9., 8, 82])
def test_budget_rejected_before_any_callback(budget):
    with pytest.raises(SearchError): plan(budget=budget)


@pytest.mark.parametrize("axes", [(), (axis(), axis()), tuple(axis(f"x{i}") for i in range(5))])
def test_invalid_axis_collection(axes):
    with pytest.raises(SearchError): GridSearchPlan(axes, 81)


def test_failed_infeasible_unknown_and_missing_constraints_do_not_rank():
    def evaluate(p):
        if p["x"] == -1: raise EvaluationFailure("unsupported polar cell")
        if p["y"] == -1: return Evaluation(-100, {"load": False, "evidence": True})
        if p["y"] == 0: return Evaluation(-200, {"load": True})
        return Evaluation(10, {"load": True, "evidence": True})
    doc = json.loads(run(evaluate, plan(constraints=("load", "evidence"))).report_json)
    assert doc["status_counts"] == {"failed": 3, "infeasible": 2, "blocked": 2, "feasible": 2}
    assert doc["best_candidate"]["objective"] == 10
    assert doc["evaluations_attempted"] == 9
    assert not doc["all_evaluations_succeeded"]
    assert doc["candidates"][0]["objective"] is None


def test_all_unknown_or_failed_has_no_best_candidate():
    doc = json.loads(run(lambda p: Evaluation(1, {"physical": None}), plan(constraints=("physical",))).report_json)
    assert doc["best_candidate"] is None
    assert doc["status_counts"]["blocked"] == 9


@pytest.mark.parametrize("evaluation", [None, Evaluation(True), Evaluation(float("nan")), Evaluation(float("inf")),
    Evaluation("1"), Evaluation(1, {"unknown_name": True}), Evaluation(1, {"gate": 1}), Evaluation(1, details={"x": float("nan")})])
def test_invalid_callback_result_recorded_as_failed(evaluation):
    doc = json.loads(run(lambda p: evaluation, plan(constraints=("gate",))).report_json)
    assert doc["status_counts"]["failed"] == 9
    assert doc["best_candidate"] is None


def test_arithmetic_failure_is_counted_but_programming_errors_are_not_hidden():
    def numeric(p): return Evaluation(1 / 0)
    assert json.loads(run(numeric).report_json)["status_counts"]["failed"] == 9
    def bug(p): raise RuntimeError("programming bug")
    with pytest.raises(RuntimeError, match="programming bug"): run(bug)


def test_callback_cannot_mutate_declared_grid_and_result_metadata_is_snapshotted():
    constraints = {"gate": True}; details = {"values": [1]}
    def callback(p):
        p["x"] = 1000
        return Evaluation(1, constraints, details)
    result = run(callback, plan(constraints=("gate",)))
    constraints["gate"] = False; details["values"][0] = 2
    doc = json.loads(result.report_json)
    assert doc["candidates"][0]["parameters"]["x"] == -1
    assert doc["candidates"][0]["details"]["values"] == [1]


def test_evaluator_identity_changes_request_and_is_snapshotted():
    one = run(lambda p: Evaluation(0), identity={"sha": "a"})
    two = run(lambda p: Evaluation(0), identity={"sha": "b"})
    assert one.request_sha256 != two.request_sha256
