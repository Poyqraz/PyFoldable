"""Unread taken-branch prefix. Static geometry is labelled static. It does not admit readiness."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from pyfoldable.application.c2v09_ordered_declaration import canonical_bytes, sha256_bytes
from pyfoldable.application.c2v09_reference_call_prefix import (
    EDGE_LABELS,
    PREFIX_BYTE_LIMIT,
    bind_labeled_edges,
)
from pyfoldable.application.c2v09_reference_call_taken_prefix import (
    JE_BYTES,
    collect_taken_branch,
    je_site_evidence,
    replay_taken_prefix,
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
    "reference_call_prefix.json": "a4447513d006de822f9aef079a1b7397c93817c35d1089aaa8ecfd9719528ec3",
    "reference_call_prefix_associated.json": "f7d9b24afc7b1e1d6f5be52ceef8d08f99687f528b7f3198f4fa7a9a8143a967",
}
_IMAGE = "/usr/bin/python3.12"
_PID = 10
_THREAD = "10"
_ENTRY = 0x583EC0
_TAKEN = 0x45DC4B
_EDGE_SITES = (0x61169C, 0x6116D5, 0x61170D, 0x611745, 0x611787)
_ENTRY_BLOB = bytes.fromhex(
    "f30f1efa"
    "55"
    "4889e5"
    "4154"
    "53"
    "4c8b6708"
    "4889fb"
    "498b442478"
    "4885c0"
    "0f846b9dedff"
)


def _spaced_edges():
    base = _EDGE_SITES[0]
    blob = bytearray(b"\x90" * (_EDGE_SITES[-1] + 5 - base))
    for address, label in zip(_EDGE_SITES, EDGE_LABELS, strict=True):
        start = address - base
        blob[start : start + 5] = bytes.fromhex(label)
    instructions = _decode_complete(bytes(blob), base)
    assert instructions is not None
    return bind_labeled_edges(instructions, EDGE_LABELS, image=_IMAGE, pid=_PID, thread_id=_THREAD)


def _collect(
    entry_blob: bytes = _ENTRY_BLOB,
    taken_blob: bytes | None = None,
    *,
    edges=None,
    file_entry: bytes | None = None,
    file_taken: bytes | None = None,
    static_control: bool = True,
    pid: int = _PID,
    thread_id: str = _THREAD,
    image: str = _IMAGE,
    limit: int = PREFIX_BYTE_LIMIT,
    taken_unreadable: bool = False,
    claimed_summary: dict[str, object] | None = None,
    observer_envelope: object | None = None,
    outer_context: dict[str, object] | None = None,
    controls: dict[str, object] | None = None,
):
    if taken_blob is None:
        taken_blob = bytes.fromhex("e800000000") + (b"\x90" * (PREFIX_BYTE_LIMIT - 5))
    taken: list[tuple[int, int]] = []
    files: list[tuple[int, int]] = []

    def read_process(address: int, size: int) -> bytes | None:
        if address == _TAKEN:
            taken.append((address, size))
            if taken_unreadable:
                return None
            return taken_blob
        if address == _ENTRY:
            return entry_blob[:size]
        taken.append((address, size))
        return None

    def read_file(address: int, size: int) -> bytes | None:
        files.append((address, size))
        if address == _ENTRY:
            source = entry_blob if file_entry is None else file_entry
            return source[:size]
        if address == _TAKEN:
            source = taken_blob if file_taken is None else file_taken
            return None if source is None else source[:size]
        return None

    observed = collect_taken_branch(
        _spaced_edges() if edges is None else edges,
        read_process=read_process,
        read_file=read_file,
        image=image,
        pid=pid,
        thread_id=thread_id,
        static_control=static_control,
        limit=limit,
        claimed_summary=claimed_summary,
        observer_envelope=observer_envelope,
        outer_context=outer_context,
        controls=controls,
        head="0",
        tree="0",
    )
    return observed, taken, files


def test_static_fallthrough_reads_the_taken_target_once() -> None:
    observed, taken, files = _collect()
    assert observed["evidence_class"] == "static"
    assert observed["static_evidence"] is True
    assert observed["genuine_observer"] is False
    assert observed["live_process"] is False
    assert observed["five_site_correspondence"] is True
    assert [edge["exact_bytes"] for edge in observed["edges"]] == list(EDGE_LABELS)
    assert {edge["target"] for edge in observed["edges"]} == {hex(_ENTRY)}
    assert observed["je"]["exact_bytes"] == JE_BYTES.hex()
    assert observed["je"]["displacement"] == -0x126295
    assert observed["je"]["target"] == hex(_TAKEN)
    assert observed["je"]["end"] == hex(0x583EDA + 6)
    assert observed["fallthrough"][0] == hex(_ENTRY)
    assert observed["fallthrough"][-1] == "0x583eda"
    assert taken == [(_TAKEN, PREFIX_BYTE_LIMIT)]
    assert (_TAKEN, PREFIX_BYTE_LIMIT) in files
    assert observed["read_accounting"]["taken_process"] == [{"address": hex(_TAKEN), "size": PREFIX_BYTE_LIMIT}]
    assert observed["read_accounting"]["taken_file"] == [{"address": hex(_TAKEN), "size": PREFIX_BYTE_LIMIT}]
    assert observed["taken_target_correspondence"] is True
    assert observed["prefix"]["child_bytes_read"] is False
    assert observed["prefix"]["unresolved_child_calls"]
    assert all(call["resolved"] is False for call in observed["prefix"]["unresolved_child_calls"])
    assert observed["preservation_established"] is False
    assert observed["premises_discharged"] is False
    assert observed["target_invoked"] is False
    assert observed["accept_closed"] is True
    assert observed["candidate29_disposition"] == "NOT SELECTED"


def test_differing_entry_instructions_change_the_retained_digest() -> None:
    first, first_taken, _files = _collect()
    swapped = _ENTRY_BLOB.replace(bytes.fromhex("4889fb"), bytes.fromhex("4889f3"), 1)
    assert swapped != _ENTRY_BLOB
    second, second_taken, _files = _collect(entry_blob=swapped)
    assert first_taken == [(_TAKEN, PREFIX_BYTE_LIMIT)]
    assert second_taken == [(_TAKEN, PREFIX_BYTE_LIMIT)]
    assert first["entry_prefix"]["loaded_bytes_hex"] == _ENTRY_BLOB.hex()
    assert second["entry_prefix"]["loaded_bytes_hex"] == swapped.hex()
    assert first["entry_prefix"]["file_bytes_hex"] == first["entry_prefix"]["loaded_bytes_hex"]
    assert second["entry_prefix"]["file_bytes_hex"] == swapped.hex()
    assert first["entry_prefix"]["address"] == hex(_ENTRY)
    assert first["entry_prefix"]["end"] == hex(_ENTRY + len(_ENTRY_BLOB))
    assert first["entry_prefix"]["requested_length"] == PREFIX_BYTE_LIMIT
    assert first["entry_prefix"]["captured_length"] == len(_ENTRY_BLOB)
    assert first["entry_prefix"]["image"] == _IMAGE
    assert first["entry_prefix"]["pid"] == _PID
    assert first["entry_prefix"]["thread_id"] == _THREAD
    assert sha256_bytes(canonical_bytes(first)) != sha256_bytes(canonical_bytes(second))
    assert replay_taken_prefix(first)["entry_supported"] is True
    assert replay_taken_prefix(second)["entry_supported"] is True
    assert replay_taken_prefix(first)["instruction_bytes"] != replay_taken_prefix(second)["instruction_bytes"]


def test_missing_or_truncated_entry_bytes_are_not_supported() -> None:
    observed, _taken, _files = _collect()
    missing = copy.deepcopy(observed)
    missing.pop("entry_prefix")
    assert replay_taken_prefix(missing)["entry_supported"] is False
    truncated = copy.deepcopy(observed)
    truncated["entry_prefix"]["loaded_bytes_hex"] = _ENTRY_BLOB[:4].hex()
    truncated["entry_prefix"]["file_bytes_hex"] = _ENTRY_BLOB[:4].hex()
    assert replay_taken_prefix(truncated)["entry_supported"] is False
    historical = json.loads(
        (_ROOT / "reports" / "c2v09_pre_call_capsule" / "reference_call_taken_prefix.json").read_text()
    )["canonical_payload"]
    assert replay_taken_prefix(historical)["entry_supported"] is False
    assert replay_taken_prefix(historical)["preservation_established"] is False


def test_tampered_or_inconsistent_entry_bytes_are_not_supported() -> None:
    observed, _taken, _files = _collect()
    tampered = copy.deepcopy(observed)
    tampered["entry_prefix"]["loaded_bytes_hex"] = tampered["entry_prefix"]["loaded_bytes_hex"][:-2] + "90"
    assert replay_taken_prefix(tampered)["entry_supported"] is False
    inconsistent = copy.deepcopy(observed)
    inconsistent["entry_prefix"]["file_bytes_hex"] = "00" * len(_ENTRY_BLOB)
    assert replay_taken_prefix(inconsistent)["entry_supported"] is False


def test_retained_bytes_must_agree_with_the_claimed_je() -> None:
    observed, _taken, _files = _collect()
    disagreed = copy.deepcopy(observed)
    disagreed["je"]["target"] = "0x1000"
    assert replay_taken_prefix(disagreed)["entry_supported"] is False
    other_path = copy.deepcopy(observed)
    other_path["fallthrough"] = ["0x1000"]
    assert replay_taken_prefix(other_path)["entry_supported"] is False
    foreign = copy.deepcopy(observed)
    foreign["entry_prefix"]["pid"] = 99
    assert replay_taken_prefix(foreign)["entry_supported"] is False


def test_invalid_five_site_coverage_does_not_read() -> None:
    edges = _spaced_edges()
    observed, taken, _files = _collect(edges=edges[:4])
    assert observed["five_site_correspondence"] is False
    assert taken == []
    assert observed["read_accounting"]["taken_process"] == []
    duplicate, _taken, _files = _collect(edges=[dict(edges[0]) for _ in range(5)])
    assert duplicate["five_site_correspondence"] is False
    assert _taken == []


def test_static_observer_does_not_read() -> None:
    envelope = {
        "raw_feature": {"classification": "OBSERVED", "required_bits_ok": True, "thread_id": _THREAD, "pid": _PID},
        "before": {"pid": _PID, "thread_id": _THREAD, "bind_now": True},
        "after": {"pid": _PID, "thread_id": _THREAD, "bind_now": True},
        "probe_receipt": {"read_state_calls": 1},
    }
    observed, taken, _files = _collect(
        static_control=False,
        observer_envelope=envelope,
        outer_context={"pid": _PID, "thread_id": _THREAD, "bind_now": True},
        controls=envelope["raw_feature"],
    )
    assert observed["evidence_class"] == "refused"
    assert observed["genuine_observer"] is False
    assert observed["static_evidence"] is True
    assert taken == []


def test_foreign_context_does_not_read() -> None:
    observed, taken, _files = _collect(pid=99, thread_id="other")
    assert observed["evidence_class"] == "refused"
    assert taken == []
    assert observed["prefix"]["captured_length"] == 0


def test_wrong_opcode_does_not_read() -> None:
    blob = _ENTRY_BLOB.replace(bytes.fromhex("0f84"), bytes.fromhex("0f85"), 1)
    observed, taken, _files = _collect(entry_blob=blob)
    assert taken == []
    assert observed["je"]["established"] is False


def test_wrong_displacement_does_not_read() -> None:
    blob = _ENTRY_BLOB[: -4] + b"\x00\x00\x00\x00"
    observed, taken, _files = _collect(entry_blob=blob)
    assert blob.endswith(bytes.fromhex("0f8400000000"))
    assert taken == []
    assert observed["je"]["established"] is False


def test_false_endpoint_does_not_establish() -> None:
    evidence = je_site_evidence(_ENTRY + 0x1A, JE_BYTES, "je", 5, JE_BYTES)
    assert evidence["established"] is False
    observed, taken, _files = _collect(
        claimed_summary={"established": True, "end": hex(_ENTRY + 0x1A + 5), "target": hex(_TAKEN)}
    )
    assert taken == [(_TAKEN, PREFIX_BYTE_LIMIT)]
    assert observed["je"]["end"] == hex(_ENTRY + 0x1A + 6)


def test_false_boundary_does_not_read() -> None:
    blob = b"\x48\xb8" + JE_BYTES + b"\x00\x00"
    assert JE_BYTES in blob
    observed, taken, _files = _collect(entry_blob=blob)
    assert taken == []
    assert observed["je"]["established"] is False


def test_je_bytes_outside_the_entry_walk_do_not_read() -> None:
    blob = bytes.fromhex("eb06") + JE_BYTES + b"\xc3"
    assert JE_BYTES in blob
    observed, taken, _files = _collect(entry_blob=blob)
    assert taken == []
    assert observed["je"]["established"] is False


def test_prefixed_return_or_jump_does_not_reach_the_je() -> None:
    for blob in (
        bytes.fromhex("f3c3") + JE_BYTES,
        bytes.fromhex("cb") + JE_BYTES,
        bytes.fromhex("f2ffe0") + JE_BYTES,
    ):
        assert JE_BYTES in blob
        observed, taken, _files = _collect(entry_blob=blob)
        assert taken == [], blob.hex()
        assert observed["je"]["established"] is False


def test_non_integer_pid_does_not_read() -> None:
    observed, taken, _files = _collect(pid=10.0)  # type: ignore[arg-type]
    assert taken == []
    assert observed["evidence_class"] == "refused"
    base = _EDGE_SITES[0]
    raw = bytearray(b"\x90" * (_EDGE_SITES[-1] + 5 - base))
    for address, label in zip(_EDGE_SITES, EDGE_LABELS, strict=True):
        start = address - base
        raw[start : start + 5] = bytes.fromhex(label)
    instructions = _decode_complete(bytes(raw), base)
    assert instructions is not None
    integer_edges = bind_labeled_edges(instructions, EDGE_LABELS, image=_IMAGE, pid=1, thread_id="1")
    boolean, boolean_taken, _files = _collect(edges=integer_edges, pid=True, thread_id="1")  # type: ignore[arg-type]
    assert boolean_taken == []
    assert boolean["evidence_class"] == "refused"
    assert boolean["genuine_observer"] is False


def test_broken_path_before_the_je_does_not_read() -> None:
    blob = b"\xc3" + _ENTRY_BLOB
    assert JE_BYTES in blob
    observed, taken, _files = _collect(entry_blob=blob)
    assert taken == []
    assert observed["je"]["established"] is False


def test_parent_file_mismatch_does_not_read() -> None:
    observed, taken, _files = _collect(file_entry=b"\x00" * len(_ENTRY_BLOB))
    assert observed["entry_file_match"] is False
    assert taken == []
    assert observed["read_accounting"]["taken_process"] == []


def test_unreadable_taken_target_is_explicit() -> None:
    observed, taken, _files = _collect(taken_unreadable=True)
    assert taken == [(_TAKEN, PREFIX_BYTE_LIMIT)]
    assert observed["prefix"]["raw_bytes_hex"] is None
    assert observed["prefix"]["captured_length"] == 0
    assert observed["taken_target_correspondence"] is False


def test_truncated_taken_target_keeps_trailing_coverage() -> None:
    observed, taken, _files = _collect(taken_blob=b"\x90\xe8")
    assert taken == [(_TAKEN, PREFIX_BYTE_LIMIT)]
    assert observed["prefix"]["captured_length"] == 2
    assert observed["prefix"]["decoded_length"] == 1
    assert observed["prefix"]["incomplete_trailing_hex"] == "e8"
    assert observed["prefix"]["child_bytes_read"] is False


def test_taken_file_mismatch_does_not_establish_correspondence() -> None:
    observed, taken, files = _collect(file_taken=b"\x00" * PREFIX_BYTE_LIMIT)
    assert taken == [(_TAKEN, PREFIX_BYTE_LIMIT)]
    assert files[-1][0] == _TAKEN
    assert observed["prefix"]["captured_length"] == PREFIX_BYTE_LIMIT
    assert observed["prefix"]["loaded_bytes_match_file"] is False
    assert observed["taken_target_correspondence"] is False


def test_oversized_request_does_not_read() -> None:
    observed, taken, _files = _collect(limit=PREFIX_BYTE_LIMIT + 1)
    assert observed["prefix"]["refused"] is True
    assert observed["prefix"]["captured_length"] == 0
    assert taken == []


def test_summary_does_not_select_the_target() -> None:
    observed, taken, _files = _collect(
        entry_blob=b"\x90",
        claimed_summary={"established": True, "exact_bytes": JE_BYTES.hex(), "target": hex(_TAKEN)},
    )
    assert JE_BYTES.hex() in str(observed["claimed_summary"])
    assert taken == []
    assert observed["je"]["established"] is False


def test_capture_reports_missing_evidence_without_admission() -> None:
    from pyfoldable.application.c2v09_reference_call_taken_prefix import capture_taken_prefix

    observed = capture_taken_prefix(_ROOT)
    assert observed["live_process"] is True
    assert observed["bind_now"] is True
    assert observed["status"] == NOT_ESTABLISHED
    assert observed["preservation_established"] is False
    assert observed["premises_discharged"] is False
    assert observed["accept_closed"] is True
    assert observed["candidate29_disposition"] == "NOT SELECTED"
    assert observed["eligibility_evidence"] is False
    assert observed["physical_qualification"] is False
    assert observed["authorizes_execution"] is False
    assert observed["target_invoked"] is False
    assert observed["historical_addresses_used_as_evidence"] is False
    assert "pid" not in observed["controls"]
    if observed["je"]["established"] is not True:
        assert observed["read_accounting"]["taken_process"] == []
        assert observed["prefix"]["captured_length"] == 0
    else:
        assert observed["je"]["exact_bytes"] == JE_BYTES.hex()
        assert observed["read_accounting"]["taken_process"]
        assert observed["read_accounting"]["taken_process"][0]["size"] <= PREFIX_BYTE_LIMIT
        assert observed["prefix"]["requested_length"] <= PREFIX_BYTE_LIMIT
        assert observed["prefix"]["child_bytes_read"] is False
    root = _ROOT / "reports" / "c2v09_pre_call_capsule"
    for name, digest in _OBSERVATIONS.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest


def test_taken_prefix_record_is_not_the_measurement_commit() -> None:
    path = _ROOT / "reports" / "c2v09_pre_call_capsule" / "reference_call_taken_prefix.json"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "aac74f9aab1dd788a036067c165dded65bc31622c7f27a594ab4a5e807d44913"
    document = json.loads(raw)
    payload = document["canonical_payload"]
    assert "canonical_sha256" not in payload
    assert document["canonical_sha256"] == "9c58bcbba5862f5c2c9c04e4e31a98218e95ad342aef727118bc3007ea253920"
    assert sha256_bytes(canonical_bytes(payload)) == document["canonical_sha256"]
    assert payload["measurement_implementation_head"] == "894f796eccf2ca22cad46d50823af23554f37bb6"
    assert payload["measurement_implementation_tree"] == "6e152336ec7fdfdc697c3a0509bf2350a080277e"
    assert payload["record_commit_is_measurement_commit"] is False
    assert payload["evidence_class"] == "genuine"
    assert payload["genuine_observer"] is True
    assert payload["static_evidence"] is False
    assert payload["live_process"] is True
    assert payload["five_site_correspondence"] is True
    assert [edge["exact_bytes"] for edge in payload["edges"]] == list(EDGE_LABELS)
    assert {edge["target"] for edge in payload["edges"]} == {"0x583ec0"}
    assert payload["fallthrough"][0] == "0x583ec0"
    assert payload["fallthrough"][-1] == "0x583eda"
    je = payload["je"]
    assert je["established"] is True
    assert je["exact_bytes"] == "0f846b9dedff"
    assert je["end"] == "0x583ee0"
    assert je["displacement"] == -1204885
    assert je["target"] == "0x45dc4b"
    assert je["file_match"] is True
    assert "pid" not in payload["controls"]
    assert payload["pid"] == je["pid"]
    assert payload["thread_id"] == je["thread_id"]
    assert payload["read_accounting"]["taken_process"] == [{"address": "0x45dc4b", "size": 256}]
    assert payload["read_accounting"]["taken_file"] == [{"address": "0x45dc4b", "size": 256}]
    assert payload["read_accounting"]["entry_process"] == [{"address": "0x583ec0", "size": 256}]
    prefix = payload["prefix"]
    assert prefix["requested_length"] == 256
    assert prefix["captured_length"] == 256
    assert prefix["decoded_length"] == 253
    assert prefix["incomplete_trailing_hex"] == "488b7d"
    assert prefix["loaded_bytes_match_file"] is True
    assert prefix["child_bytes_read"] is False
    assert len(prefix["unresolved_child_calls"]) == 10
    assert all(call["resolved"] is False for call in prefix["unresolved_child_calls"])
    assert payload["taken_target_correspondence"] is True
    assert payload["preservation_established"] is False
    assert payload["premises_discharged"] is False
    assert payload["target_invoked"] is False
    assert payload["historical_addresses_used_as_evidence"] is False
    assert payload["accept_closed"] is True
    assert payload["candidate29_disposition"] == "NOT SELECTED"
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False
    assert payload["authorizes_execution"] is False
    assert replay_taken_prefix(payload)["entry_supported"] is False


def test_supported_taken_prefix_retains_entry_bytes() -> None:
    path = _ROOT / "reports" / "c2v09_pre_call_capsule" / "reference_call_taken_prefix_supported.json"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "aefeca408379c5495304ff29b9fc991644f680f849a4be354e623246dd3b0b82"
    historical = (_ROOT / "reports" / "c2v09_pre_call_capsule" / "reference_call_taken_prefix.json").read_bytes()
    assert hashlib.sha256(historical).hexdigest() == "aac74f9aab1dd788a036067c165dded65bc31622c7f27a594ab4a5e807d44913"
    document = json.loads(raw)
    payload = document["canonical_payload"]
    assert "canonical_sha256" not in payload
    assert document["canonical_sha256"] == "61f538c08e546b57a553ac8ff939e7d284a264cbccb2984d745a0293cf746eb2"
    assert sha256_bytes(canonical_bytes(payload)) == document["canonical_sha256"]
    assert payload["measurement_implementation_head"] == "10b8fbb4bdead8374aa1c7398f47e6df1e44b6e3"
    assert payload["measurement_implementation_tree"] == "3dd2dcaddc117307791f87358ad77200d9299d91"
    assert payload["record_commit_is_measurement_commit"] is False
    entry = payload["entry_prefix"]
    assert entry["address"] == "0x583ec0"
    assert entry["end"] == "0x583fc0"
    assert entry["requested_length"] == 256
    assert entry["captured_length"] == 256
    assert entry["decoded_length"] == 255
    assert entry["incomplete_trailing_hex"] == "48"
    assert entry["loaded_bytes_hex"] == entry["file_bytes_hex"]
    assert "4889fb" in entry["loaded_bytes_hex"]
    assert entry["image"] == "/usr/bin/python3.12"
    assert entry["pid"] == payload["pid"] == payload["je"]["pid"]
    assert entry["thread_id"] == payload["thread_id"] == payload["je"]["thread_id"]
    replayed = replay_taken_prefix(payload)
    assert replayed["entry_supported"] is True
    assert "4889fb" in "".join(replayed["instruction_bytes"])
    assert replayed["preservation_established"] is False
    assert payload["je"]["exact_bytes"] == "0f846b9dedff"
    assert payload["je"]["target"] == "0x45dc4b"
    assert payload["read_accounting"]["entry_process"] == [{"address": "0x583ec0", "size": 256}]
    assert payload["read_accounting"]["taken_process"] == [{"address": "0x45dc4b", "size": 256}]
    assert payload["read_accounting"]["taken_file"] == [{"address": "0x45dc4b", "size": 256}]
    prefix = payload["prefix"]
    assert prefix["captured_length"] == 256
    assert prefix["decoded_length"] == 253
    assert prefix["incomplete_trailing_hex"] == "488b7d"
    assert prefix["loaded_bytes_match_file"] is True
    assert prefix["child_bytes_read"] is False
    assert len(prefix["unresolved_child_calls"]) == 10
    assert payload["preservation_established"] is False
    assert payload["accept_closed"] is True
    assert payload["candidate29_disposition"] == "NOT SELECTED"
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False
    assert payload["authorizes_execution"] is False
    assert payload["target_invoked"] is False


def _published_taken_prefix() -> dict[str, object]:
    path = _ROOT / "reports" / "c2v09_pre_call_capsule" / "reference_call_taken_prefix_supported.json"
    payload = json.loads(path.read_text())["canonical_payload"]
    assert isinstance(payload, dict)
    return payload


def test_published_replay_binds_the_packet_without_a_live_observer() -> None:
    replayed = replay_taken_prefix(_published_taken_prefix())
    assert replayed["entry_supported"] is True
    assert replayed["live_observer"] is False
    assert replayed["preservation_established"] is False


def test_empty_callers_reject_the_published_record() -> None:
    payload = _published_taken_prefix()
    payload["edges"] = []
    assert replay_taken_prefix(payload)["entry_supported"] is False


def test_foreign_caller_context_rejects_the_published_record() -> None:
    payload = _published_taken_prefix()
    payload["edges"][2]["image"] = "/tmp/other"
    assert replay_taken_prefix(payload)["entry_supported"] is False


def test_shifted_entry_with_unchanged_callers_rejects() -> None:
    payload = _published_taken_prefix()
    delta = 0x1000
    entry = payload["entry_prefix"]
    entry["address"] = hex(int(str(entry["address"]), 16) + delta)
    entry["end"] = hex(int(str(entry["end"]), 16) + delta)
    payload["fallthrough"] = [hex(int(str(item), 16) + delta) for item in payload["fallthrough"]]
    je = payload["je"]
    je["address"] = hex(int(str(je["address"]), 16) + delta)
    je["end"] = hex(int(str(je["end"]), 16) + delta)
    je["target"] = hex(int(str(je["target"]), 16) + delta)
    assert replay_taken_prefix(payload)["entry_supported"] is False


def test_missing_je_support_rejects_after_the_digest_is_recomputed() -> None:
    payload = _published_taken_prefix()
    del payload["je"]["loaded_bytes_hex"]
    recomputed = sha256_bytes(canonical_bytes(payload))
    assert recomputed != "61f538c08e546b57a553ac8ff939e7d284a264cbccb2984d745a0293cf746eb2"
    assert replay_taken_prefix(payload)["entry_supported"] is False


def test_controls_feature_disagreement_rejects_the_published_record() -> None:
    payload = _published_taken_prefix()
    payload["controls"]["mxcsr"] = "0x0"
    assert payload["observer_envelope"]["raw_feature"]["mxcsr"] == "0x1fa0"
    recomputed = sha256_bytes(canonical_bytes(payload))
    assert recomputed != "61f538c08e546b57a553ac8ff939e7d284a264cbccb2984d745a0293cf746eb2"
    assert replay_taken_prefix(payload)["entry_supported"] is False
    assert replay_taken_prefix(payload)["live_observer"] is False


def test_controls_pid_without_thread_rejects_the_published_record() -> None:
    payload = _published_taken_prefix()
    del payload["controls"]["thread_id"]
    payload["controls"]["pid"] = True
    assert replay_taken_prefix(payload)["entry_supported"] is False
    assert replay_taken_prefix(payload)["live_observer"] is False


def test_float_after_pid_rejects_the_published_record() -> None:
    payload = _published_taken_prefix()
    payload["observer_envelope"]["after"]["pid"] = 89941.0
    recomputed = sha256_bytes(canonical_bytes(payload))
    assert recomputed != "61f538c08e546b57a553ac8ff939e7d284a264cbccb2984d745a0293cf746eb2"
    assert replay_taken_prefix(payload)["entry_supported"] is False
    assert replay_taken_prefix(payload)["live_observer"] is False


def test_contradictory_je_file_slice_rejects_after_the_digest_is_recomputed() -> None:
    payload = _published_taken_prefix()
    payload["je"]["file_bytes_hex"] = "000000000000"
    payload["je"]["file_match"] = True
    recomputed = sha256_bytes(canonical_bytes(payload))
    assert recomputed != "61f538c08e546b57a553ac8ff939e7d284a264cbccb2984d745a0293cf746eb2"
    assert replay_taken_prefix(payload)["entry_supported"] is False
