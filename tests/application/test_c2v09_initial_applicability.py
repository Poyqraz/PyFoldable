"""Applicability dossier. The evaluator is not called."""

from __future__ import annotations

from pathlib import Path

from pyfoldable.application.c2v09_initial_applicability import (
    ACCEPTED_REPAIR_HEAD,
    build_applicability_dossier,
    classify_implementation_change,
    declare_initial_operation_graph,
)
from pyfoldable.application.c2v09_initial_call_binding import bind_initial_call
from pyfoldable.application.c2v09_pre_call_admission import prepare_pre_call_admission
from pyfoldable.application.c2v09_pre_call_binding import observe_pre_call_binding


def _repository() -> Path:
    return Path(__file__).resolve().parents[2]


def _native_unavailable(_root):
    return {
        "canonical_payload": {
            "selected_call_target": {"classification": "NOT ESTABLISHED"},
            "cosine_function_calls": 0,
            "eligibility_evidence": False,
        }
    }


def _observer(root):
    return observe_pre_call_binding(root, cosine_observer=_native_unavailable)


def _collector(_root):
    return {"canonical_payload": {"executing_dependencies": {}, "observations": {}, "source_callbacks": 0}}


def _native_double(_root):
    return {"canonical_payload": {"cosine_function_calls": 0, "compiled_probe_image_sha256": "ab" * 32}}


def _bind():
    admission = prepare_pre_call_admission(
        _repository(),
        pre_call_observer=_observer,
        dependency_collector=_collector,
    )
    return bind_initial_call(_repository(), admission=admission, native_observer=_native_double)


def test_declared_graph_separates_geometry_from_bem_numerics() -> None:
    graph = declare_initial_operation_graph(_repository())
    by_name = {row["qualname"]: row for row in graph}
    projection = by_name["project_foldable_blade"]
    numerical = by_name["solve_bem_rotor"]
    guard = by_name["math.ulp"]
    assert projection["family"] == "geometric lemma"
    assert projection["bem_numerical_dependency"] is False
    assert projection["module_digest_clears_this_row"] is False
    assert projection["filename_clears_this_row"] is False
    assert numerical["family"] == "bem numerical dependency"
    assert numerical["geometric_lemma"] is False
    assert guard["classification"] == "NOT ESTABLISHED"
    assert guard["calls"] == 0
    assert guard["historical_equality_assumed"] is False
    assert all(row["module_digest_clears_this_row"] is False for row in graph)


def test_unreviewed_byte_change_is_not_a_reviewed_rebinding() -> None:
    pending = classify_implementation_change("aa" * 32, "bb" * 32)
    assert pending["relation"] == "CHANGED / REVIEW PENDING"
    assert pending["runtime_transfer_approved"] is False
    assert pending["clears_runtime_differences"] is False
    other = classify_implementation_change("cc" * 32, "dd" * 32)
    assert other["relation"] == "CHANGED / REVIEW PENDING"
    reviewed = classify_implementation_change(
        "aa" * 32,
        "bb" * 32,
        review_binding={"current_digest": "aa" * 32, "scope": "certificate source text only"},
    )
    assert reviewed["relation"] == "REVIEWED REBINDING"
    assert reviewed["review_scope"] == "certificate source text only"
    assert reviewed["runtime_transfer_approved"] is False
    mismatched_review = classify_implementation_change(
        "ee" * 32,
        "bb" * 32,
        review_binding={"current_digest": "aa" * 32, "scope": "certificate source text only"},
    )
    assert mismatched_review["relation"] == "CHANGED / REVIEW PENDING"


def test_stale_binding_is_not_a_current_observation() -> None:
    bound = _bind()
    bound.native_observation = {
        "kind": "genuine",
        "measurement_image": {
            "handle_associated": True,
            "loaded_code_correspondence": "MATCH",
            "file_image_identity": "OBSERVED",
            "file_image_sha256": "ab" * 32,
            "second_compilation_is_evidence": False,
            "source_hash_is_the_image": False,
        },
        "cosine_function_calls": 0,
    }
    bound.pid = bound.pid + 1
    dossier = build_applicability_dossier(_repository(), binding=bound)
    assert dossier["binding_revalidation"] == "INVALIDATED"
    assert dossier["genuine_runtime_observations"]["current"] is False
    assert dossier["genuine_runtime_observations"]["loaded_code_correspondence"] != "MATCH"
    retained = dossier["retained_observation"]
    assert retained["role"] == "historical/unvalidated"
    assert retained["original_pid"] == bound.pid
    assert retained["measurement_image"]["loaded_code_correspondence"] == "MATCH"
    serialized = build_applicability_dossier(_repository(), binding={"kind": "archived"})
    assert serialized["binding_revalidation"] == "NOT ESTABLISHED"
    assert serialized["serialized_record_is_a_live_binding"] is False
    assert serialized["genuine_runtime_observations"]["current"] is False
    assert serialized["authorizes_execution"] is False


def test_dossier_blocks_unresolved_items_and_rejects_test_doubles() -> None:
    bound = _bind()
    dossier = build_applicability_dossier(_repository(), binding=bound)
    assert dossier["status"] == "CONTRACT BLOCKED"
    assert dossier["authorizes_execution"] is False
    assert dossier["eligibility_evidence"] is False
    assert dossier["physical_qualification"] is False
    assert dossier["candidate29_disposition"] == "NOT SELECTED"
    assert dossier["accepted_repair"]["head"] == ACCEPTED_REPAIR_HEAD
    assert dossier["time_s"] == "NOT ESTABLISHED"
    assert dossier["post_return"]["returned_source_object"] == "POST-RETURN ONLY"
    assert dossier["post_return"]["mapped_interval_consumption"] == "POST-RETURN ONLY"
    assert dossier["dependent_counters"]["source"] == 0
    assert dossier["genuine_runtime_observations"]["kind"] == "test_double"
    assert dossier["genuine_runtime_observations"]["measurement_image"]["file_image_identity"] == "NOT ESTABLISHED"
    assert dossier["genuine_runtime_observations"]["loaded_code_correspondence"] == "NOT ESTABLISHED"
    assert dossier["genuine_runtime_observations"]["test_double_is_measurement_evidence"] is False
    assert dossier["genuine_runtime_observations"]["archived_json_is_measurement_evidence"] is False
    assert dossier["archived_record_authorizes_later_process"] is False
    assert dossier["historical_certificate_hypotheses"]["exact_equality_assumed"] is False
    assert dossier["historical_certificate_hypotheses"]["implementation"]["clears_runtime_differences"] is False
    assert dossier["historical_certificate_hypotheses"]["implementation"]["runtime_transfer_approved"] is False
    assert dossier["historical_certificate_hypotheses"]["implementation"]["relation"] == "CHANGED / REVIEW PENDING"
    assert dossier["deferred_radau_is_prerequisite_for_isolated_source_attempt"] is False
    assert dossier["post_return_demanded_before_existence"] is False
    timed = {row["name"]: row for row in dossier["unmet_hypotheses"]}
    assert timed["returned source object"]["timing"] == "POST-RETURN ONLY"
    assert timed["returned source object"]["demanded_before_it_exists"] is False
    assert timed["solve_cmm2_transient"]["timing"] == "deferred integration"
    assert timed["solve_cmm2_transient"]["prerequisite_for_isolated_source_attempt"] is False
    assert timed["time_s"]["timing"] == "pre-call"
    assert dossier["current_implementation"]["module_digest_clears_any_row"] is False
    names = {row["name"] for row in dossier["unmet_hypotheses"]}
    assert "returned source object" in names
    assert "time_s" in names
    assert "math.ulp" in names
    assert bound.evaluator.successful_bem_solves == 0
    assert bound.evaluator.successful_map_calls == 0
