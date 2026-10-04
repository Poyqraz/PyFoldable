"""Pre-call binding observer. Hashes are not the loaded call graph."""

from __future__ import annotations

import json
from pathlib import Path

import pyfoldable.application.c2v09_pre_call_binding as pre_call
import pyfoldable.application.cmm2_coupled_transient_service as service
from pyfoldable.application.c2v09_cosine_path_certificate import prepare_cosine_path_certificate
from pyfoldable.application.c2v09_ordered_declaration import CANDIDATE29_MANIFEST_SHA256, canonical_bytes, sha256_bytes
from pyfoldable.application.c2v09_pre_call_binding import (
    MAPPER_BINDING,
    POST_RETURN_ONLY,
    SOURCE_BINDING,
    is_live_pre_call_evidence,
    name_only_double,
    observe_pre_call_binding,
    persistent_pre_call_record,
    same_calling_context,
)
from pyfoldable.core.foldable_aero_load import map_foldable_bem_aero_loads
from pyfoldable.core.foldable_rotor import solve_foldable_bem_rotor


def _repository() -> Path:
    return Path(__file__).resolve().parents[2]


def _native_unavailable(root):
    return {
        "canonical_payload": {
            "selected_call_target": {
                "classification": "NOT ESTABLISHED",
                "address": None,
                "independent_cdll_is_evidence": False,
            },
            "loaded_body": {"matches_historical_body": False, "sha256": None},
            "numerical_controls_and_features": {"classification": "NOT ESTABLISHED", "thread_id": "other"},
            "eligibility_evidence": False,
            "physical_qualification": False,
        }
    }


def test_live_observation_retains_the_loaded_source_and_mapper() -> None:
    observation = observe_pre_call_binding(_repository(), cosine_observer=_native_unavailable)
    retained = observation.retained_callables
    assert retained[SOURCE_BINDING] is solve_foldable_bem_rotor
    assert retained[MAPPER_BINDING] is map_foldable_bem_aero_loads
    assert retained[SOURCE_BINDING] is service.Cmm2FoldableBemMappedAeroEvaluator.__call__.__globals__[SOURCE_BINDING]
    assert retained[MAPPER_BINDING] is service.Cmm2FoldableBemMappedAeroEvaluator.__call__.__globals__[MAPPER_BINDING]
    assert retained[SOURCE_BINDING].__code__ is observation.retained_code_objects[SOURCE_BINDING]
    assert observation.binding_matches_loaded_module_source is True
    assert observation.eligibility_evidence is False
    assert observation.physical_qualification is False
    assert is_live_pre_call_evidence(observation) is True


def test_filename_or_hash_record_is_not_loaded_graph_evidence() -> None:
    observation = observe_pre_call_binding(_repository(), cosine_observer=_native_unavailable)
    hashes = {
        "name": SOURCE_BINDING,
        "co_filename": observation.retained_callables[SOURCE_BINDING].__code__.co_filename,
        "co_code_sha256": observation.code_hashes[SOURCE_BINDING],
        "file_sha256": observation.module_file_hashes[SOURCE_BINDING],
    }
    assert is_live_pre_call_evidence(hashes) is False
    assert is_live_pre_call_evidence(name_only_double(SOURCE_BINDING)) is False


def test_replaced_binding_is_observed_and_does_not_clear_history(monkeypatch) -> None:
    def replacement(*_args, **_kwargs):
        raise AssertionError("source evaluated")

    monkeypatch.setattr(service, SOURCE_BINDING, replacement)
    observation = observe_pre_call_binding(_repository(), cosine_observer=_native_unavailable)
    assert observation.retained_callables[SOURCE_BINDING] is replacement
    assert observation.binding_matches_loaded_module_source is False
    assert observation.proposed_current_graph_binding["status"] == "PROPOSED / NOT A HISTORICAL CLASSIFICATION"
    assert observation.proposed_current_graph_binding["eligibility_evidence"] is False
    assert "pyfoldable/application/cmm2_coupled_transient_service.py" in observation.historical_source_mismatches
    assert "pyfoldable/dynamics/cmm2_coupled_transient.py" in observation.historical_source_mismatches


def test_changed_constants_are_not_the_observed_constants() -> None:
    observation = observe_pre_call_binding(_repository(), cosine_observer=_native_unavailable)
    changed = observation.call_constants + ("changed-default",)
    assert observation.constants_match(observation.call_constants) is True
    assert observation.constants_match(changed) is False


def test_changed_defaults_are_not_the_observed_defaults() -> None:
    observation = observe_pre_call_binding(_repository(), cosine_observer=_native_unavailable)
    assert observation.defaults_match(
        observation.bound_defaults,
        observation.call_signature_defaults,
        observation.call_signature_kwdefaults,
    ) is True
    changed = dict(observation.bound_defaults)
    changed[SOURCE_BINDING] = ("changed-default",)
    assert observation.defaults_match(
        changed,
        observation.call_signature_defaults,
        observation.call_signature_kwdefaults,
    ) is False


def test_forged_cosine_observer_is_not_this_process_probe() -> None:
    def forged(_root):
        return {
            "canonical_payload": {
                "selected_call_target": {"classification": "OBSERVED", "address": "0x1"},
                "eligibility_evidence": True,
            }
        }

    observation = observe_pre_call_binding(_repository(), cosine_observer=forged)
    assert observation.native["native_observer"] == "test_double"
    assert observation.native["classification"] == "NOT ESTABLISHED"
    assert observation.native["selected_address"] is None
    assert observation.native["repaired_record_used_as_live_evidence"] is False
    assert observation.eligibility_evidence is False


def test_missing_pinned_source_is_not_dropped_from_the_inventory(monkeypatch) -> None:
    def pins(_root):
        return (("absent.py", "ab" * 32),)

    monkeypatch.setattr(pre_call, "pinned_certificate_sources", pins)
    observation = observe_pre_call_binding(_repository(), cosine_observer=_native_unavailable)
    assert observation.historical_source_mismatches == ()
    assert observation.certificate_source_file_identity[0]["path"] == "absent.py"
    assert observation.certificate_source_file_identity[0]["file_identity"] == "NOT ESTABLISHED"
    assert observation.certificate_source_file_identity[0]["loaded_code_identity"] == "NOT ESTABLISHED"
    assert observation.certificate_source_file_identity[0]["operation_graph_applicability"] == "NOT ESTABLISHED"


def test_missing_inputs_and_unavailable_native_observations_stay_unestablished() -> None:
    def missing(_root):
        raise RuntimeError("inputs unavailable")

    observation = observe_pre_call_binding(
        _repository(),
        materials_loader=missing,
        cosine_observer=_native_unavailable,
    )
    assert observation.inputs["classification"] == "NOT ESTABLISHED"
    assert observation.native["classification"] == "NOT ESTABLISHED"
    assert observation.native["selected_address"] is None
    assert observation.native["repaired_record_used_as_live_evidence"] is False
    assert observation.returned_bem_object_correspondence == POST_RETURN_ONLY
    assert observation.mapped_interval_consumption == POST_RETURN_ONLY


def test_stale_thread_is_not_this_calling_context() -> None:
    observation = observe_pre_call_binding(_repository(), cosine_observer=_native_unavailable)
    assert same_calling_context(observation, pid=observation.pid, thread_id=observation.thread_id) is True
    assert same_calling_context(observation, pid=observation.pid, thread_id=observation.thread_id + "-other") is False
    assert same_calling_context(observation, pid=observation.pid + 1, thread_id=observation.thread_id) is False


def test_observer_does_not_evaluate_source(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("source evaluated")

    monkeypatch.setattr(service, SOURCE_BINDING, forbidden)
    monkeypatch.setattr(service, MAPPER_BINDING, forbidden)
    observation = observe_pre_call_binding(_repository(), cosine_observer=_native_unavailable)
    assert observation.source_callbacks == 0
    assert observation.eligibility_evidence is False
    assert observe_pre_call_binding.__kwdefaults__["cosine_observer"] is prepare_cosine_path_certificate


def test_reviewed_inputs_stay_with_the_historical_mismatches() -> None:
    observation = observe_pre_call_binding(_repository(), cosine_observer=_native_unavailable)
    assert observation.inputs["classification"] == "OBSERVED"
    assert isinstance(observation.inputs["bytes"], bytes)
    assert sha256_bytes(observation.inputs["bytes"]) == observation.inputs["sha256"]
    assert observation.inputs["sha256"] == CANDIDATE29_MANIFEST_SHA256
    assert observation.inputs["theta0"] is not None and len(observation.inputs["theta0"]) == 2
    assert observation.inputs["uncertainty_hex"]
    assert observation.retained_evaluator_call is service.Cmm2FoldableBemMappedAeroEvaluator.__call__
    assert observation.historical_source_mismatches == (
        "pyfoldable/application/cmm2_coupled_transient_service.py",
        "pyfoldable/dynamics/cmm2_coupled_transient.py",
    )
    assert len(observation.certificate_source_file_identity) == 21
    assert [row["path"] for row in observation.certificate_source_file_identity if row["file_identity"] == "MISMATCH"] == list(
        observation.historical_source_mismatches
    )
    assert all(
        row["loaded_code_identity"] == "NOT ESTABLISHED" and row["operation_graph_applicability"] == "NOT ESTABLISHED"
        for row in observation.certificate_source_file_identity
    )
    assert observation.proposed_current_graph_binding["does_not_rewrite_historical_classifications"] is True
    assert observation.returned_bem_object_correspondence == POST_RETURN_ONLY
    probe = [row for row in observation.modules_without_historical_record if row["role"] == "probe_source"]
    assert probe[0]["compiled_loaded_native_identity"] == "NOT ESTABLISHED"
    assert all(row["amends_collector_inventory"] is False for row in observation.modules_without_historical_record)


def test_persistent_record_omits_callables_and_keeps_the_digest_outside() -> None:
    observation = observe_pre_call_binding(_repository(), cosine_observer=_native_unavailable)
    record = persistent_pre_call_record(observation)
    payload = record["canonical_payload"]
    assert record["canonical_sha256"] == sha256_bytes(canonical_bytes(payload))
    assert "canonical_sha256" not in payload
    assert payload["retained_references_serialized"] is False
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False
    assert payload["source_callbacks"] == 0
    assert payload["inputs"]["utf8"].encode("utf-8") == observation.inputs["bytes"]
    assert payload["returned_bem_object_correspondence"] == POST_RETURN_ONLY
    assert payload["mapped_interval_consumption"] == POST_RETURN_ONLY
    assert is_live_pre_call_evidence(record) is False
    json.dumps(record)


def test_archived_pre_call_record_is_not_live_or_eligibility_evidence() -> None:
    record = json.loads((_repository() / "reports/c2v09_pre_call_binding/observation.json").read_text(encoding="utf-8"))
    payload = record["canonical_payload"]
    assert record["canonical_sha256"] == sha256_bytes(canonical_bytes(payload))
    assert "canonical_sha256" not in payload
    assert payload["checkout_sha"] == "3b8d790d09f5eefd1be8669895de1cbb6ee3442d"
    assert payload["tree_sha"] == "085f30932817951b67b4066595820ed6d6e34b4b"
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False
    assert payload["retained_references_serialized"] is False
    assert payload["source_callbacks"] == 0
    assert payload["inputs"]["sha256"] == CANDIDATE29_MANIFEST_SHA256
    assert sha256_bytes(payload["inputs"]["utf8"].encode("utf-8")) == CANDIDATE29_MANIFEST_SHA256
    assert payload["returned_bem_object_correspondence"] == POST_RETURN_ONLY
    assert payload["mapped_interval_consumption"] == POST_RETURN_ONLY
    assert payload["historical_source_mismatches"] == [
        "pyfoldable/application/cmm2_coupled_transient_service.py",
        "pyfoldable/dynamics/cmm2_coupled_transient.py",
    ]
    assert len(payload["certificate_source_file_identity"]) == 21
    assert all(
        row["loaded_code_identity"] == "NOT ESTABLISHED" and row["operation_graph_applicability"] == "NOT ESTABLISHED"
        for row in payload["certificate_source_file_identity"]
    )
    assert payload["proposed_current_graph_binding"]["status"] == "PROPOSED / NOT A HISTORICAL CLASSIFICATION"
    assert payload["proposed_current_graph_binding"]["eligibility_evidence"] is False
    assert payload["native"]["repaired_record_used_as_live_evidence"] is False
    assert payload["native"]["eligibility_evidence"] is False
    assert payload["native"]["native_observer"] == "prepare_cosine_path_certificate"
    assert payload["native"]["cosine_function_calls"] == 0
    assert is_live_pre_call_evidence(record) is False


def test_repaired_probe_is_the_only_native_observer() -> None:
    observation = observe_pre_call_binding(_repository())
    assert observation.native["native_observer"] == "prepare_cosine_path_certificate"
    assert observation.native["cosine_function_calls"] == 0
    assert observation.native["independent_cdll_is_evidence"] is False
    assert observation.native["repaired_record_used_as_live_evidence"] is False
    assert observation.native["eligibility_evidence"] is False
    assert observation.eligibility_evidence is False
    assert observation.physical_qualification is False
    if observation.native["classification"] == "OBSERVED":
        assert observation.native["selected_evidence"] == "python wrapper plt got"
        assert observation.native["selected_address"]
