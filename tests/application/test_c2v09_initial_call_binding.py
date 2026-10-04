"""Actual initial-call binding. The evaluator is not called."""

from __future__ import annotations

from pathlib import Path

import pyfoldable.application.c2v09_initial_call_binding as binding_module
import pyfoldable.application.cmm2_coupled_transient_service as service
from pyfoldable.application.cmm2_coupled_transient_service import Cmm2FoldableBemMappedAeroEvaluator
from pyfoldable.core.config import load_design_config
from pyfoldable.core.foldable_aero_load import map_foldable_bem_aero_loads
from pyfoldable.core.foldable_rotor import solve_foldable_bem_rotor
from pyfoldable.application.c2v09_initial_call_binding import (
    binary64_hex,
    bind_initial_call,
    revalidate_initial_call_binding,
)
from pyfoldable.application.c2v09_pre_call_admission import prepare_pre_call_admission
from pyfoldable.application.c2v09_pre_call_binding import SOURCE_BINDING, observe_pre_call_binding


def _repository() -> Path:
    return Path(__file__).resolve().parents[2]


def _native_unavailable(_root):
    return {"canonical_payload": {"selected_call_target": {"classification": "NOT ESTABLISHED"}, "cosine_function_calls": 0, "eligibility_evidence": False}}


def _observer(root):
    return observe_pre_call_binding(root, cosine_observer=_native_unavailable)


def _collector(_root):
    return {"canonical_payload": {"executing_dependencies": {}, "observations": {}, "source_callbacks": 0}}


def _admission():
    return prepare_pre_call_admission(
        _repository(),
        pre_call_observer=_observer,
        dependency_collector=_collector,
    )


def test_signed_zero_is_distinct_binary64() -> None:
    assert binary64_hex(-0.0) == "-0x0.0p+0"
    assert binary64_hex(0.0) == "0x0.0p+0"
    assert binary64_hex(-0.0) != binary64_hex(0.0)


def test_binding_uses_parsed_inputs_and_does_not_call_the_evaluator() -> None:
    bound = bind_initial_call(_repository(), admission=_admission())
    evaluator = bound.evaluator
    assert evaluator.successful_bem_solves == 0
    assert evaluator.successful_map_calls == 0
    assert evaluator.bounds == "error"
    assert len(evaluator.blade.stations) == 6
    assert bound.input_identity["station_r_over_r_hex"][0] == binary64_hex(0.2)
    assert bound.input_identity["hinge_radius_hex"] == binary64_hex(evaluator.hinge_radius_m)
    assert bound.input_identity["parsed_draft_matches_manifest"] is True
    assert bound.caller_claims_role == "not actual-input evidence"
    assert bound.initial_arguments["time_s"] == "NOT ESTABLISHED"
    assert bound.deferred_routines["clearance_granted"] is False
    assert all(row["classification"] == "MATCH" for row in bound.active_graph)
    assert bound.deferred_routines["solve_cmm2_transient"] == "NOT CLEARED"
    assert bound.applicability["status"] == "CONTRACT BLOCKED"
    assert bound.applicability["exact_historical_equality_assumed"] is False
    assert bound.applicability["equivalence_assumed"] is False
    assert bound.post_return["returned_source_object"] == "POST-RETURN ONLY"
    assert bound.post_return["mapped_interval_consumption"] == "POST-RETURN ONLY"
    assert bound.candidate29_disposition == "NOT SELECTED"
    assert bound.eligibility_evidence is False
    assert bound.physical_qualification is False
    assert bound.authorizes_execution is False
    assert bound.dependent_counters == {"source": 0, "mapper": 0, "partition": 0, "selection": 0, "seal": 0, "trajectory": 0}
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"


def test_caller_claim_does_not_replace_parsed_hinge() -> None:
    bound = bind_initial_call(_repository(), admission=_admission(), caller_claims={"hinge_radius_m": 1.0})
    assert bound.evaluator.hinge_radius_m != 1.0
    assert bound.caller_claims["hinge_radius_m"] == 1.0


def test_input_and_code_mutations_invalidate_and_restore() -> None:
    bound = bind_initial_call(_repository(), admission=_admission())
    original_hinge = bound.evaluator.hinge_radius_m
    try:
        bound.evaluator.hinge_radius_m = original_hinge + 0.01
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        bound.evaluator.hinge_radius_m = original_hinge
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"

    function = Cmm2FoldableBemMappedAeroEvaluator.__call__
    original = function.__code__
    try:
        function.__code__ = original.replace(co_consts=original.co_consts + ("mutated",))
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        function.__code__ = original

    original_polars = bound.evaluator.polars
    try:
        bound.evaluator.polars = object()
        assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    finally:
        bound.evaluator.polars = original_polars
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"


def test_active_graph_code_replacement_invalidates(monkeypatch) -> None:
    bound = bind_initial_call(_repository(), admission=_admission())
    for function in (
        solve_foldable_bem_rotor,
        map_foldable_bem_aero_loads,
        load_design_config,
        Cmm2FoldableBemMappedAeroEvaluator.__init__,
    ):
        original = function.__code__
        try:
            function.__code__ = original.replace(co_consts=original.co_consts + ("mutated",))
            assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
        finally:
            function.__code__ = original
        assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"


def test_global_replacement_and_stale_context_invalidate(monkeypatch) -> None:
    bound = bind_initial_call(_repository(), admission=_admission())

    def other(*_args, **_kwargs):
        raise AssertionError("source evaluated")

    monkeypatch.setattr(service, SOURCE_BINDING, other)
    assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"
    monkeypatch.undo()
    assert revalidate_initial_call_binding(bound).classification == "REVALIDATED"
    bound.thread_id = bound.thread_id + "-other"
    assert revalidate_initial_call_binding(bound).classification == "INVALIDATED"


def test_test_double_native_and_archive_are_not_genuine() -> None:
    bound = bind_initial_call(_repository(), admission=_admission())
    assert bound.native_observation["kind"] == "test_double"
    assert bound.applicability["native_is_genuine"] is False
    assert revalidate_initial_call_binding({"kind": "archived"}).classification == "NOT ESTABLISHED"


def test_binding_does_not_invoke_source(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("source evaluated")

    monkeypatch.setattr(service, SOURCE_BINDING, forbidden)
    monkeypatch.setattr(service, "map_foldable_bem_aero_loads", forbidden)
    bound = bind_initial_call(_repository(), admission=_admission())
    assert bound.dependent_counters["source"] == 0
    assert bound.evaluator.successful_bem_solves == 0
