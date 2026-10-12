"""Call-side evidence for _Py_NewReference. It does not admit readiness."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pyfoldable.application.c2v09_ordered_declaration import canonical_bytes, sha256_bytes

from pyfoldable.application.c2v09_reference_call_evidence import (
    analyze_reference_call,
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
    "reference_call_evidence.json": "99d4304fab2a174f83cd45203f739811e33ff18abb522de17cefbfb7d2672664",
}


def _newref_calling(address: int = 0x2000):
    call = _decoded("8b050000000085c07501c3e8f00f0000", 0x1000)
    assert call[-1].mnemonic == "call"
    assert int(call[-1].op_str, 16) == address
    return call


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


def test_saved_stack_slot_alias_does_not_restore_entry() -> None:
    """A write through a copied stack pointer replaces the saved entry value."""
    witnesses = (
        ("r14", "41564889e54889e848c7000100000041be02000000415ec3"),
        ("rbx", "534889e54889e848c70001000000bb020000005bc3"),
        ("r14", "41564889e54889e8488d0848c7010100000041be02000000415ec3"),
    )
    newref = _newref_calling()
    for register, blob in witnesses:
        instructions = _decoded(blob)
        proof = prove_entry_restore(instructions, 0x2000)
        assert proof["established"] is False
        assert proof["returns"]
        assert all(row[register] != "entry" for row in proof["returns"])
        assert any(
            pop["register"] == register and pop["restores_entry"] is False
            for pop in proof["pops"]
        )
        analysis = analyze_reference_call(newref, instructions, [])
        assert analysis["call"] is not None
        assert analysis["preservation_established"] is False
        assert analysis["callee_proof"]["established"] is False
    partial = prove_entry_restore(
        _decoded("41564889e54889e866b8010048c7000100000041be02000000415ec3"),
        0x2000,
    )
    assert partial["established"] is False
    assert all(row["r14"] != "entry" for row in partial["returns"])
    joined = prove_entry_restore(
        _decoded("41564889e54889e885c0740231c048c7000100000041be02000000415ec3"),
        0x2000,
    )
    assert joined["established"] is False
    assert any(row["r14"] != "entry" for row in joined["returns"])
    transferred = prove_entry_restore(
        _decoded("41564889e54889e8505948c70101000000415ec3"),
        0x2000,
    )
    assert transferred["established"] is False
    assert all(row["r14"] != "entry" for row in transferred["returns"])
    displaced = prove_entry_restore(
        _decoded("4156534889e0488d480848c701010000005b415ec3"),
        0x2000,
    )
    assert displaced["established"] is False
    assert all(row["r14"] != "entry" for row in displaced["returns"])
    assert any(row["rbx"] == "entry" for row in displaced["returns"])
    for blob in (
        "41564889e54889e84887c848c7010100000041be02000000415ec3",
        "41564889e54889e84801c148c7010100000041be02000000415ec3",
        "4156545848c70001000000415ec3",
        "4156fff45848c70001000000415ec3",
        "4156544889e0488b0848c7010100000058415ec3",
    ):
        moved = prove_entry_restore(_decoded(blob), 0x2000)
        assert moved["established"] is False
        assert all(row["r14"] != "entry" for row in moved["returns"])
        assert any(pop["register"] == "r14" and pop["restores_entry"] is False for pop in moved["pops"])
    pushed_rbx = prove_entry_restore(_decoded("53545848c700010000005bc3"), 0x2000)
    assert pushed_rbx["established"] is False
    assert all(row["rbx"] != "entry" for row in pushed_rbx["returns"])
    both = prove_entry_restore(_decoded("415653545848c700010000005b415ec3"), 0x2000)
    assert both["established"] is False
    assert all(row["rbx"] != "entry" for row in both["returns"])
    compared = prove_entry_restore(
        _decoded("415631c04889e1480fb1c148c70001000000415ec3"),
        0x2000,
    )
    assert compared["established"] is False
    assert all(row["r14"] != "entry" for row in compared["returns"])
    assert analyze_reference_call(newref, _decoded("415631c04889e1480fb1c148c70001000000415ec3"), [])[
        "preservation_established"
    ] is False
    looped = prove_entry_restore(
        _decoded("41564889e0b902000000e203415ec348c70001000000415ec3"),
        0x2000,
    )
    assert looped["established"] is False
    assert any(row["r14"] != "entry" for row in looped["returns"])
    exchanged = prove_entry_restore(
        _decoded("415631c031c94889e2480fb1d148c70101000000415ec3"),
        0x2000,
    )
    assert exchanged["established"] is False
    assert all(row["r14"] != "entry" for row in exchanged["returns"])
    added = prove_entry_restore(
        _decoded("41565431c94889e048030848c7010100000058415ec3"),
        0x2000,
    )
    assert added["established"] is False
    assert all(row["r14"] != "entry" for row in added["returns"])


def test_archived_reference_call_replay_keeps_the_recorded_events() -> None:
    path = _ROOT / "reports" / "c2v09_pre_call_capsule" / "reference_call_evidence.json"
    document = json.loads(path.read_bytes())
    dossier = document["canonical_payload"]["dossier"]
    newref = _decode_complete(
        bytes.fromhex(dossier["newref"]["loaded_bytes_hex"]),
        int(dossier["newref"]["address"], 16),
    )
    callee = _decode_complete(
        bytes.fromhex(dossier["callee"]["loaded_bytes_hex"]),
        int(dossier["callee"]["address"], 16),
    )
    assert newref is not None and callee is not None
    stubs = []
    for record in dossier["outlined_stubs"]:
        decoded = _decode_complete(bytes.fromhex(record["loaded_bytes_hex"]), int(record["address"], 16))
        assert decoded is not None
        stubs.append(decoded)
    analysis = analyze_reference_call(newref, callee, stubs)
    proof = analysis["callee_proof"]
    events = dossier["callee_events"]
    assert proof["pushes"] == events["pushes"]
    assert proof["pops"] == events["pops"]
    assert proof["overwrites"] == events["overwrites"]
    assert proof["outgoing_calls"] == events["outgoing_calls"]
    assert proof["unresolved_exits"] == events["unresolved_exits"]
    assert proof["returns"] == events["returns"]
    assert proof["budget_exhausted"] is False
    assert proof["established"] is False
    assert analysis["preservation_established"] is False
    assert analysis["no_call_path_preserves_r14_and_rbx"] is True
    assert len(events["outgoing_calls"]) == 16
    assert len(events["unresolved_exits"]) == 4


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
