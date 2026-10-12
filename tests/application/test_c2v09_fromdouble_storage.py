"""FromDouble result-storage evidence. It does not admit the readiness hypotheses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pyfoldable.application.c2v09_fromdouble_storage import (
    _inventory_from_observation,
    capture_fromdouble_storage,
)
from pyfoldable.application.c2v09_ordered_declaration import canonical_bytes, sha256_bytes
from pyfoldable.application.c2v09_runtime_semantic_correspondence import (
    NOT_ESTABLISHED,
    _decode_complete,
    _store_reaches_return,
)

_ROOT = Path(__file__).resolve().parents[2]
_CAPSULES = {
    "capsule.json": "09f7df71697528333be1674fde6419bbeadeec084213274c2eab3ee7abb6649a",
    "loaded_correspondence_capsule.json": "8cebb4d5fe12e4ef6f15aacae0dcc986999534346d9043de9c9cef51320024f5",
    "boundary_decode_capsule.json": "630d149e0da9c68fdcc328ccb45d4c79cddcbe2868b240a031be7ed01595e3ce",
}


def test_storage_capture_keeps_failure_paths_unsuccessful() -> None:
    observed = capture_fromdouble_storage(_ROOT)
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
    assert observed["cosine_function_calls"] == 0
    assert observed["ulp_function_calls"] == 0
    assert observed["nextafter_function_calls"] == 0
    assert observed["archived_reference_not_evidence"]["used_as_evidence"] is False
    assert observed["status"] == NOT_ESTABLISHED
    inventory = observed["inventory"]
    assert inventory["readiness_admitted"] is False
    replayed = _inventory_from_observation(observed)
    assert replayed["branch_table"] == inventory["branch_table"]
    assert replayed["paths"] == inventory["paths"]
    assert replayed["gaps"] == inventory["gaps"]
    for edge in inventory["branch_table"]:
        if edge["role"] == "allocation_null":
            assert edge["result"] == "not_a_successful_result"
            assert edge["result"] != "finite_store_under_conditions"
    for path in inventory["paths"]:
        if path["name"] == "allocation_failure":
            assert path["result"] == "not_a_successful_result"
        if path["result"] == "finite_store_under_conditions":
            assert path["result"] != "not_a_successful_result"
    constructor = observed.get("constructor")
    if (
        isinstance(constructor, dict)
        and constructor.get("loaded_bytes_hex")
        and constructor.get("address")
        and any(edge["role"] == "allocation_null" for edge in inventory["branch_table"])
    ):
        raw = bytes.fromhex(str(constructor["loaded_bytes_hex"]))
        instructions = _decode_complete(raw, int(str(constructor["address"]), 16))
        assert instructions is not None
        assert _store_reaches_return(instructions, instructions[0].address, frozenset({"xmm0"})) is False
    root = _ROOT / "reports" / "c2v09_pre_call_capsule"
    for name, digest in _CAPSULES.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest


def test_fromdouble_storage_record_is_not_the_measurement_commit() -> None:
    path = _ROOT / "reports" / "c2v09_pre_call_capsule" / "fromdouble_storage.json"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "ff96dc2154daf188b2f690c2840f87bf3164ed2d32a5b9bd0cd5bf5917d36f12"
    document = json.loads(raw)
    payload = document["canonical_payload"]
    assert payload["measurement_implementation_head"] == "7084b100d76a10bb3cab9d88bd314178eb1048b6"
    assert payload["measurement_implementation_tree"] == "1bbf0eb34aadc356d43d487d9cb84d7075dfbe81"
    assert payload["record_commit_is_measurement_commit"] is False
    assert payload["readiness_hypotheses_admitted"] is False
    assert payload["accept_closed"] is True
    assert payload["candidate29_disposition"] == "NOT SELECTED"
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False
    assert payload["status"] == "NOT ESTABLISHED"
    assert payload["archived_reference_not_evidence"]["used_as_evidence"] is False
    assert payload["pid"] == payload["controls"]["pid"]
    assert payload["thread_id"] == payload["controls"]["thread_id"]
    assert payload["controls"]["bind_now"] is True
    trace = payload["inventory"]["bit_trace"]
    assert trace["source"] == "xmm0"
    assert trace["carrier"] == "r14"
    assert trace["store_operands"] == "qword ptr [rbx + 0x10], r14"
    failure = next(row for row in payload["inventory"]["paths"] if row["name"] == "allocation_failure")
    assert failure["result"] == "not_a_successful_result"
    assert failure["null_return_reachable"] is True
    assert failure["unresolved_sibling"] is True
    assert "canonical_sha256" not in payload
    assert document["canonical_sha256"] == "3268f060342fce6160eff72ae4e1812aa980c0913030ba0d6f413731181f6dd1"
    assert sha256_bytes(canonical_bytes(payload)) == document["canonical_sha256"]
    assert _inventory_from_observation(payload)["branch_table"] == payload["inventory"]["branch_table"]


def test_historical_capsules_stay_byte_for_byte() -> None:
    root = _ROOT / "reports" / "c2v09_pre_call_capsule"
    historical = {
        "runtime_semantic_correspondence.json": "74f4ea340bd524ac721ec002798effe5538f4bb38aec680f8db0fe30d27ad785",
        "runtime_semantic_fail_closed.json": "67cff33b9d5cfc1ec5724011fa9d652a756434b0123d4cdfe04d6caa1d8705d2",
        "runtime_semantic_path_provenance.json": "9eabc9c90488646c7f20d8a4b317ef1e1c1ad61cdb78d449a13e2cc66b99615d",
        "runtime_semantic_exit_walk.json": "558a7e50f72db0c18dc9059daeb1cd3578a15ad2f5b1ba1c94475e7cd06a063f",
        "runtime_semantic_slot_walk.json": "d12be39499170320fc2a27bfdf3e1a084dc3273a3da783b400cc1216f7e0dd19",
        "runtime_semantic_full_store.json": "7221d7f568618a39a843d08de529d2b3e1f0a5360618c623405e9755be968d6a",
    }
    for name, digest in {**_CAPSULES, **historical}.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
