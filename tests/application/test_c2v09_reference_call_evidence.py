"""Call-side evidence for _Py_NewReference. It does not admit readiness."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pyfoldable.application.c2v09_ordered_declaration import canonical_bytes, sha256_bytes

from pyfoldable.application.c2v09_reference_call_evidence import (
    capture_reference_call,
    prove_entry_restore,
)
from pyfoldable.application.c2v09_runtime_semantic_correspondence import (
    NOT_ESTABLISHED,
    _decode_complete,
)

_ROOT = Path(__file__).resolve().parents[2]
_OBSERVATIONS = {
    "capsule.json": "09f7df71697528333be1674fde6419bbeadeec084213274c2eab3ee7abb6649a",
    "loaded_correspondence_capsule.json": "8cebb4d5fe12e4ef6f15aacae0dcc986999534346d9043de9c9cef51320024f5",
    "boundary_decode_capsule.json": "630d149e0da9c68fdcc328ccb45d4c79cddcbe2868b240a031be7ed01595e3ce",
    "runtime_semantic_correspondence.json": "74f4ea340bd524ac721ec002798effe5538f4bb38aec680f8db0fe30d27ad785",
    "runtime_semantic_fail_closed.json": "67cff33b9d5cfc1ec5724011fa9d652a756434b0123d4cdfe04d6caa1d8705d2",
    "runtime_semantic_path_provenance.json": "9eabc9c90488646c7f20d8a4b317ef1e1c1ad61cdb78d449a13e2cc66b99615d",
    "runtime_semantic_exit_walk.json": "558a7e50f72db0c18dc9059daeb1cd3578a15ad2f5b1ba1c94475e7cd06a063f",
    "runtime_semantic_slot_walk.json": "d12be39499170320fc2a27bfdf3e1a084dc3273a3da783b400cc1216f7e0dd19",
    "runtime_semantic_full_store.json": "7221d7f568618a39a843d08de529d2b3e1f0a5360618c623405e9755be968d6a",
    "fromdouble_storage.json": "ff96dc2154daf188b2f690c2840f87bf3164ed2d32a5b9bd0cd5bf5917d36f12",
}


def _decoded(blob: str, address: int = 0x2000):
    instructions = _decode_complete(bytes.fromhex(blob), address)
    assert instructions is not None
    return instructions


def test_a_push_is_not_a_restore() -> None:
    overwritten = prove_entry_restore(_decoded("415641be01000000c3"), 0x2000)
    assert overwritten["established"] is False
    restored = prove_entry_restore(_decoded("415641be01000000415ec3"), 0x2000)
    assert restored["established"] is True
    assert restored["returns_restoring_entry"]
    called = prove_entry_restore(_decoded("4156e800000000415ec3"), 0x2000)
    assert called["established"] is False
    assert called["outgoing_calls"]
    sibling = prove_entry_restore(_decoded("415641be010000007403415ec3"), 0x2000)
    assert sibling["established"] is False
    assert sibling["unresolved_exits"]
    ignored_push = prove_entry_restore(_decoded("415641be010000006a01415ec3"), 0x2000)
    assert ignored_push["established"] is False
    left = prove_entry_restore(_decoded("415641be01000000c9c3"), 0x2000)
    assert left["established"] is False
    for blob in (
        "415641be0100000048890424415ec3",
        "415641be0100000066415ec3",
        "41569c415ec3",
        "41564883e4f0415ec3",
        "4156415641be010000005c415ec3",
        "415641be010000004889e048c70000000000415ec3",
        "415641be0100000089c4415ec3",
    ):
        assert prove_entry_restore(_decoded(blob), 0x2000)["established"] is False


def test_reference_call_record_is_not_the_measurement_commit() -> None:
    path = _ROOT / "reports" / "c2v09_pre_call_capsule" / "reference_call_evidence.json"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "99d4304fab2a174f83cd45203f739811e33ff18abb522de17cefbfb7d2672664"
    document = json.loads(raw)
    payload = document["canonical_payload"]
    assert payload["measurement_implementation_head"] == "f0b9a990e221121ea3786c2e0b0c6c66b278fcdf"
    assert payload["measurement_implementation_tree"] == "35ec8d503f7b69941680e99d69af8645e98334ce"
    assert payload["record_commit_is_measurement_commit"] is False
    assert payload["readiness_hypotheses_admitted"] is False
    assert payload["accept_closed"] is True
    assert payload["candidate29_disposition"] == "NOT SELECTED"
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False
    assert payload["authorizes_execution"] is False
    assert payload["constructor_invoked"] is False
    assert payload["reference_helper_invoked"] is False
    assert payload["status"] == NOT_ESTABLISHED
    assert payload["pid"] == payload["controls"]["pid"]
    assert payload["thread_id"] == payload["controls"]["thread_id"]
    dossier = payload["dossier"]
    assert dossier["preservation_established"] is False
    assert dossier["no_call_path_preserves_r14_and_rbx"] is True
    assert dossier["flag_control"]["selects_future_branch"] is False
    assert dossier["newref"]["loaded_bytes_match_file"] is True
    assert dossier["callee"]["loaded_bytes_match_file"] is True
    assert dossier["callee"]["instruction_bytes_are_aligned"] is True
    assert dossier["callee"]["symbol_name"] is None
    assert dossier["call"]["target"] == dossier["callee"]["address"]
    live = dossier["constructor_call_sites"][0]["live_after_call"]
    assert live == ["r14", "rbx"]
    assert "outgoing calls from the callee are unresolved child paths" in dossier["gaps"]
    assert "canonical_sha256" not in payload
    assert document["canonical_sha256"] == "00364c0abd0feedbf0e3b670f443558b8805abafe91807e2ba618e1a12c08699"
    assert sha256_bytes(canonical_bytes(payload)) == document["canonical_sha256"]


def test_reference_call_capture_does_not_admit_readiness() -> None:
    observed = capture_reference_call(_ROOT)
    assert observed["bind_now"] is True
    assert observed["pid"] is not None
    assert observed["controls"]["pid"] == observed["pid"]
    assert observed["controls"]["thread_id"] == observed["thread_id"]
    assert observed["readiness_hypotheses_admitted"] is False
    assert observed["accept_closed"] is True
    assert observed["candidate29_disposition"] == "NOT SELECTED"
    assert observed["eligibility_evidence"] is False
    assert observed["physical_qualification"] is False
    assert observed["authorizes_execution"] is False
    assert observed["output_sampled"] is False
    assert observed["constructor_invoked"] is False
    assert observed["reference_helper_invoked"] is False
    assert observed["cosine_function_calls"] == 0
    assert observed["archived_reference_not_evidence"]["used_as_evidence"] is False
    assert observed["status"] == NOT_ESTABLISHED
    dossier = observed["dossier"]
    assert dossier["readiness_admitted"] is False
    flag = dossier.get("flag_control")
    if isinstance(flag, dict):
        assert flag["selects_future_branch"] is False
    if dossier.get("call") is not None:
        assert dossier["preservation_established"] is False
        assert "r14 and rbx entry values are not established across the call" in dossier["gaps"]
    root = _ROOT / "reports" / "c2v09_pre_call_capsule"
    for name, digest in _OBSERVATIONS.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
