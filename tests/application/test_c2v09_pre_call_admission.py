"""Zero-call pre-call admission. It does not authorize execution."""

from __future__ import annotations

from pathlib import Path

import pyfoldable.application.c2v09_pre_call_admission as admission
import pyfoldable.application.cmm2_coupled_transient_service as service
from pyfoldable.application.c2v09_ordered_declaration import (
    CANDIDATE29_MANIFEST_SHA256,
    TECHNICAL_ARTIFACT_SHA256,
    TECHNICAL_HEAD,
    canonical_bytes,
    load_reviewed_materials,
    sha256_bytes,
)
from pyfoldable.application.c2v09_pre_call_admission import (
    CLOSURE_HEAD,
    compare_native_obligations,
    prepare_pre_call_admission,
    revalidate_pre_call_admission,
)
from pyfoldable.application.c2v09_pre_call_binding import SOURCE_BINDING, observe_pre_call_binding


def _repository() -> Path:
    return Path(__file__).resolve().parents[2]


def _native_unavailable(_root):
    return {
        "canonical_payload": {
            "selected_call_target": {"classification": "NOT ESTABLISHED", "address": None},
            "eligibility_evidence": False,
            "physical_qualification": False,
            "cosine_function_calls": 0,
        }
    }


def _observer(root):
    return observe_pre_call_binding(root, cosine_observer=_native_unavailable)


def _collector(_root):
    return {
        "canonical_payload": {
            "executing_dependencies": {},
            "observations": {},
            "eligibility_evidence": False,
            "source_callbacks": 0,
        }
    }


def _prepare(**kwargs):
    defaults = {
        "pre_call_observer": _observer,
        "dependency_collector": _collector,
    }
    defaults.update(kwargs)
    return prepare_pre_call_admission(_repository(), **defaults)


def test_policy_bundle_keeps_closure_and_executing_heads_separate() -> None:
    prepared = _prepare()
    assert prepared.caller_claims_role == "not an operand"
    assert prepared.eligibility_evidence is False
    assert prepared.physical_qualification is False
    assert prepared.authorizes_execution is False
    assert prepared.dependent_counters == {
        "source": 0,
        "mapper": 0,
        "partition": 0,
        "selection": 0,
        "seal": 0,
        "trajectory": 0,
    }
    assert prepared.verified_operands["candidate29_sha256"] == CANDIDATE29_MANIFEST_SHA256
    assert prepared.verified_operands["theta0_role"] == "verified operand"
    if prepared.policy_bundle_sha256 is None:
        assert prepared.classification == "INVALIDATED"
        return
    bundle = prepared.policy_bundle
    assert prepared.classification == "ZERO-CALL PREPARATION"
    assert bundle["technical_head"] == TECHNICAL_HEAD
    assert bundle["closure_head"] == CLOSURE_HEAD
    assert "executing_head" not in bundle
    assert prepared.executing_head != bundle["technical_head"]
    assert prepared.executing_head != CLOSURE_HEAD
    assert set(bundle["proof_identities"]) == {
        "runtime_binding_sha256",
        "cosine_record_sha256",
        "prior_geometric_record_sha256",
        "connection_record_sha256",
    }


def test_declared_policy_bundle_digest_excludes_the_executing_head() -> None:
    bundle = admission.build_policy_bundle(dict(TECHNICAL_ARTIFACT_SHA256))
    assert "executing_head" not in bundle
    assert sha256_bytes(canonical_bytes(bundle)) == "564ba504f00cc2092dd325d5edca4549724f7a914326515c7859a9a212030167"


def test_stale_technical_authority_bytes_invalidate_the_bundle(monkeypatch) -> None:
    def stale(_root, _path):
        return b"stale-authority"

    monkeypatch.setattr(admission, "_technical_authority_bytes", stale)
    prepared = _prepare()
    assert prepared.policy_bundle_sha256 is None
    assert prepared.classification == "INVALIDATED"
    assert prepared.authorizes_execution is False
    assert _row(prepared, "technical authority artifact bytes")["classification"] == "NOT ESTABLISHED"


def test_changed_theta0_and_uncertainty_do_not_replace_verified_operands(monkeypatch) -> None:
    def tampered(root):
        return load_reviewed_materials(root).with_theta0(("9/1", "8/1"))

    prepared = _prepare(materials_loader=tampered)
    assert prepared.verified_operands["classification"] == "VERIFIED"
    assert prepared.verified_operands["theta0"] == [
        "-1888948576541780995587/9444732965739290427392",
        "-1888944609753935385085/9444732965739290427392",
    ]
    assert prepared.classification == "INVALIDATED"
    assert prepared.authorizes_execution is False

    state = {"calls": 0}
    real = admission._verified_operands

    def changed(root):
        state["calls"] += 1
        value = real(root)
        if state["calls"] >= 2:
            updated = dict(value)
            updated["uncertainty_hex"] = ["0x0"]
            updated["digest"] = "changed-uncertainty"
            return updated
        return value

    monkeypatch.setattr(admission, "_verified_operands", changed)
    drifted = _prepare()
    assert drifted.classification == "INVALIDATED"
    assert drifted.authorizes_execution is False


def test_caller_claim_does_not_become_theta0() -> None:
    prepared = _prepare(caller_claims={"theta0": ["1/2", "1/3"], "eligibility_evidence": True})
    assert prepared.verified_operands["theta0"] != ["1/2", "1/3"]
    assert prepared.caller_claims["eligibility_evidence"] is True
    assert prepared.eligibility_evidence is False


def test_source_replacement_and_stale_context_invalidate_preparation(monkeypatch) -> None:
    def replace_source(_observation):
        monkeypatch.setattr(service, SOURCE_BINDING, lambda *_args, **_kwargs: None)

    replaced = _prepare(before_revalidate=replace_source)
    assert replaced.classification == "INVALIDATED"
    assert replaced.revalidation_classification == "INVALIDATED"
    assert replaced.authorizes_execution is False

    def stale_thread(observation):
        observation.thread_id = observation.thread_id + "-other"

    stale = _prepare(before_revalidate=stale_thread)
    assert stale.classification == "INVALIDATED"
    assert stale.authorizes_execution is False


def test_body_match_does_not_clear_xcr0_or_wrapper_mismatch() -> None:
    compared = compare_native_obligations(
        {
            "native_observer": "prepare_cosine_path_certificate",
            "classification": "OBSERVED",
            "selected_address": "0x7ff900000000",
            "selected_evidence": "python wrapper plt got",
            "got_slot": "0xa293d8",
            "python_wrapper": {"address": "0x62e430"},
            "loaded_body": {
                "sha256": "f7a54037fbab80cbbf5a2c6954284f47330d936b103a0beac05913b6b1949a02",
                "elf_vaddr": "0x7bad0",
                "matches_historical_body": True,
            },
            "loaded_constants": [{"vaddr": "0x1", "classification": "MATCH"}],
            "numerical_controls_and_features": {
                "classification": "OBSERVED",
                "xcr0": ["0x602e7", "0x0"],
                "exact_historical_xcr0_match": False,
                "mxcsr": "0x1fa0",
                "fegetround": "0",
                "mxcsr_daz": False,
                "mxcsr_ftz": False,
            },
            "executable": {"file_sha256": "e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f"},
            "libraries": {
                "libm": "f06f2ce1f1833df5f41cf13b6447ff07bea993ad9b27297d3428c2f70ab3f0e7",
                "libc": "different",
                "loader": "different",
            },
        },
        {
            "xcr0": ["0xe7", "0x0"],
            "mxcsr": "0x1fa0",
            "fegetround": "0",
            "daz": False,
            "ftz": False,
            "executable_sha256": "fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7",
            "libm_sha256": "f06f2ce1f1833df5f41cf13b6447ff07bea993ad9b27297d3428c2f70ab3f0e7",
            "libc_sha256": "511f825ee075610ac9c0f7f91e2c13de2000d0f7b859f6461137e809a0a009d0",
            "loader_sha256": "6222a16be7f2d458d6870efe6e715fc0c8d45766fb79cf7dcc3125538d703e28",
            "body_sha256": "f7a54037fbab80cbbf5a2c6954284f47330d936b103a0beac05913b6b1949a02",
            "body_vaddr": "0x7bad0",
            "wrapper_vaddr": "0x180a180",
            "got_vaddr": "0x1432ef8",
        },
    )
    assert compared["loaded_body"]["classification"] == "MATCH"
    assert compared["historical_xcr0"]["classification"] == "MISMATCH"
    assert compared["historical_wrapper"]["classification"] == "MISMATCH"
    assert compared["executable"]["classification"] == "MISMATCH"
    assert compared["body_match_clears_xcr0"] is False
    assert compared["body_match_clears_wrapper"] is False
    assert compared["body_match_clears_executable"] is False
    assert "historical XCR0" in compared["mismatches"]


def test_direct_node_match_does_not_clear_unchecked_graph_nodes() -> None:
    prepared = _prepare()
    matrix = {row["name"]: row for row in prepared.obligation_matrix}
    assert matrix["returned source object correspondence"]["when"] == "POST-RETURN"
    assert matrix["returned source object correspondence"]["classification"] == "POST-RETURN ONLY"
    assert matrix["mapped interval consumption"]["classification"] == "POST-RETURN ONLY"
    assert matrix["partition evaluation"]["when"] == "LATER"
    assert matrix["selection"]["classification"] == "NOT IN THIS TRANSACTION"
    assert matrix["unchecked transitive graph"]["classification"] == "NOT ESTABLISHED"
    assert matrix["geometric applicability"]["classification"] == "NOT ESTABLISHED"
    file_rows = prepared.checked_coverage["file_inventory"]
    assert len(file_rows) == 21
    assert any(row["file_identity"] == "MATCH" and row["loaded_code_identity"] == "NOT ESTABLISHED" for row in file_rows)
    assert any(row["role"] == "native terminal guard" and row["classification"] == "NOT ESTABLISHED" for row in prepared.checked_coverage["graph_nodes"])
    roles = [row["role"] for row in prepared.checked_coverage["historical_unbound_nodes"]]
    assert roles[:7] == [
        "dense",
        "declaration",
        "eligibility",
        "collector",
        "applicability",
        "cosine_certificate",
        "probe_source",
    ]
    assert "pre_call_admission" in roles
    assert prepared.checked_coverage["direct_node_match_clears_transitive_graph"] is False


def test_archived_record_cannot_stand_in_for_live_observations() -> None:
    prepared = _prepare()
    record = admission.persistent_pre_call_admission(prepared)
    assert record["canonical_sha256"]
    assert "canonical_sha256" not in record["canonical_payload"]
    archived = revalidate_pre_call_admission(record)
    assert archived.classification == "NOT ESTABLISHED"
    assert archived.authorizes_execution is False
    assert archived.eligibility_evidence is False


def test_live_admission_preserves_runtime_mismatches() -> None:
    prepared = prepare_pre_call_admission(_repository())
    assert prepared.eligibility_evidence is False
    assert prepared.physical_qualification is False
    assert prepared.authorizes_execution is False
    assert prepared.dependent_counters["source"] == 0
    assert prepared.native_comparison["body_match_clears_xcr0"] is False
    assert prepared.native_comparison["collector_kind"] == "collect_binding_record"
    mismatches = set(prepared.native_comparison["mismatches"])
    assert "historical XCR0" in mismatches or prepared.native_comparison["historical_xcr0"]["classification"] == "NOT ESTABLISHED"
    assert prepared.verified_operands["candidate29_sha256"] == CANDIDATE29_MANIFEST_SHA256
    assert "pyfoldable/application/cmm2_coupled_transient_service.py" in prepared.historical_source_mismatches
    executing = prepared.executing_authority_copies
    assert executing["docs/cmm2_numerical_feasibility_amendment.md"] == "MISMATCH"


def _row(prepared, name: str) -> dict:
    return next(row for row in prepared.obligation_matrix if row["name"] == name)
