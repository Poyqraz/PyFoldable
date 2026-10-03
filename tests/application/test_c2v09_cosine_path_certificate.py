"""One actual runtime's Python cosine call path. CDLL is not that path."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pyfoldable.application.c2v09_cosine_path_certificate import (
    CERTIFICATE_FILE_SHA256,
    HISTORICAL_BODY_SHA256,
    UNPARSED_STUB_METHOD,
    classify_selected_call,
    libm_body_verdict,
    plt_got_address,
    prepare_cosine_path_certificate,
)
from pyfoldable.application.c2v09_ordered_declaration import canonical_bytes, sha256_bytes


def _repository() -> Path:
    return Path(__file__).resolve().parents[2]


def _payload(record: dict) -> dict:
    payload = record["canonical_payload"]
    assert "canonical_sha256" not in payload
    return payload


def test_plt_got_is_the_rip_relative_slot() -> None:
    stub = bytes.fromhex("ff25f28b6000")
    assert plt_got_address(stub, 0x4207E0) == 0xA293D8
    endbr = b"\xf3\x0f\x1e\xfa" + stub
    assert plt_got_address(endbr, 0x4207E0 - 4) == 0xA293D8
    assert plt_got_address(b"\x90\x90\x90\x90\x90\x90", 0x4207E0) is None
    assert "does not repair an unrecognized stub" in UNPARSED_STUB_METHOD


def test_missing_loaded_bytes_block_instead_of_refuting_the_argument() -> None:
    blocked = libm_body_verdict(
        selected_observed=True,
        features_observed=True,
        body_sha=None,
        constant_rows=[],
        required_bits=True,
        body_vaddr=None,
        historical_vaddr="0x7bad0",
    )
    unread_constants = libm_body_verdict(
        selected_observed=True,
        features_observed=True,
        body_sha=HISTORICAL_BODY_SHA256,
        constant_rows=[{"classification": "NOT ESTABLISHED"}],
        required_bits=True,
        body_vaddr="0x7bad0",
        historical_vaddr="0x7bad0",
    )
    shifted = libm_body_verdict(
        selected_observed=True,
        features_observed=True,
        body_sha=HISTORICAL_BODY_SHA256,
        constant_rows=[{"classification": "MATCH"}],
        required_bits=True,
        body_vaddr="0x8000",
        historical_vaddr="0x7bad0",
    )
    applies = libm_body_verdict(
        selected_observed=True,
        features_observed=True,
        body_sha=HISTORICAL_BODY_SHA256,
        constant_rows=[{"classification": "MATCH"}],
        required_bits=True,
        body_vaddr="0x7bad0",
        historical_vaddr="0x7bad0",
    )
    assert blocked == unread_constants == "BLOCKED"
    assert shifted == "DOES NOT APPLY"
    assert applies == "APPLIES"


def test_unresolved_plt_is_not_replaced_by_cdll() -> None:
    selected = classify_selected_call(
        got_pointer=0x4207E6,
        stub_address=0x4207E0,
        cdll_pointer=0x7BAD0,
    )
    assert selected["classification"] == "NOT ESTABLISHED"
    assert selected["address"] is None
    assert selected["evidence"] == "python wrapper plt got"
    assert selected["independent_cdll_is_evidence"] is False
    assert "LD_BIND_NOW" in selected["method"]
    assert "CDLL" in selected["method"]


def test_resolved_got_stays_the_evidence_when_it_equals_cdll() -> None:
    selected = classify_selected_call(
        got_pointer=0x7F0000BAD0,
        stub_address=0x4207E0,
        cdll_pointer=0x7F0000BAD0,
    )
    assert selected["classification"] == "OBSERVED"
    assert selected["address"] == hex(0x7F0000BAD0)
    assert selected["evidence"] == "python wrapper plt got"
    assert selected["independent_cdll_is_evidence"] is False
    assert selected["addresses_equal"] is True


def test_historical_certificate_bytes_stay_unchanged() -> None:
    root = _repository()
    certificate = root / "docs/cmm2_c2v09_partition_runtime_certificate.md"
    assert sha256_bytes(certificate.read_bytes()) == CERTIFICATE_FILE_SHA256


def test_live_path_keeps_cdll_out_of_the_call_target() -> None:
    payload = _payload(prepare_cosine_path_certificate(_repository()))
    selected = payload["selected_call_target"]
    assert selected["evidence"] == "python wrapper plt got"
    assert selected["independent_cdll_is_evidence"] is False
    assert payload["historical_cpython_wrapper_argument"] == "DOES NOT APPLY"
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False
    assert payload["cosine_function_calls"] == 0
    assert payload["returned_source_object"] == "NOT IN THIS CERTIFICATE"
    assert payload["changed_python_operation_graph"] == "NOT IN THIS CERTIFICATE"
    if selected["classification"] == "OBSERVED":
        assert selected["address"]
        assert payload["libm_body_argument"] in {"APPLIES", "DOES NOT APPLY", "BLOCKED"}
    else:
        assert selected["classification"] == "NOT ESTABLISHED"
        assert payload["libm_body_argument"] == "BLOCKED"
        assert "LD_BIND_NOW" in selected["method"] or "objdump" in selected["method"]


def _assert_recorded_checkout(root: Path, checkout: str, tree_sha: str) -> None:
    assert len(checkout) == 40 and len(tree_sha) == 40
    present = subprocess.call(
        ["git", "cat-file", "-e", f"{checkout}^{{commit}}"],
        cwd=root,
        stderr=subprocess.DEVNULL,
    ) == 0
    if not present:
        return
    tree = subprocess.check_output(["git", "rev-parse", f"{checkout}^{{tree}}"], cwd=root, text=True).strip()
    assert tree_sha == tree


def test_persisted_path_certificate_recomputes() -> None:
    root = _repository()
    document = json.loads(
        (root / "reports/c2v09_cosine_path_certificate/observation.json").read_text(encoding="utf-8")
    )
    payload = _payload(document)
    assert document["canonical_sha256"] == sha256_bytes(canonical_bytes(payload))
    assert payload["libm_body_argument"] == "APPLIES"
    assert payload["historical_cpython_wrapper_argument"] == "DOES NOT APPLY"
    assert payload["selected_call_target"]["evidence"] == "python wrapper plt got"
    assert payload["selected_call_target"]["independent_cdll_is_evidence"] is False
    assert payload["selected_call_target"]["classification"] == "OBSERVED"
    assert payload["loaded_body"]["matches_historical_body"] is True
    assert payload["loaded_body"]["sha256"] == HISTORICAL_BODY_SHA256
    assert payload["loaded_body"]["elf_vaddr"] == "0x7bad0"
    assert payload["selected_call_target"]["plt_jmp_bytes_hex"] == "ff25f28b6000"
    assert payload["python_wrapper"]["loaded_wrapper_matches_elf"] is True
    assert payload["python_wrapper"]["disassembly_source"].startswith("objdump")
    assert payload["numerical_controls_and_features"]["required_bits_ok"] is True
    assert payload["numerical_controls_and_features"]["exact_historical_xcr0_match"] is False
    assert payload["ld_bind_now"] == "1"
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False
    assert payload["cosine_function_calls"] == 0
    _assert_recorded_checkout(root, payload["checkout_sha"], payload["tree_sha"])


def test_certificate_text_does_not_call_source_or_cosine() -> None:
    text = (_repository() / "pyfoldable/application/c2v09_cosine_path_certificate.py").read_text(encoding="utf-8")
    assert "math.cos(" not in text
    assert "bem" not in text
    assert "mapper" not in text
    assert "trajectory" not in text
    document = (_repository() / "docs/cmm2_c2v09_one_runtime_cosine_path_certificate.md").read_text(encoding="utf-8")
    assert "DOES NOT APPLY" in document
    assert "physical_qualification=false" in document
    assert "not eligibility evidence" in document
    assert HISTORICAL_BODY_SHA256
