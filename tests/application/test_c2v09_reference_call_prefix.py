"""Unread 256-byte prefix for five direct call edges. It does not admit readiness."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pyfoldable.application.c2v09_reference_call_prefix import (
    PREFIX_BYTE_LIMIT,
    bind_labeled_edges,
    classify_direct_call,
    five_site_correspondence,
    observe_prefix,
    read_target_prefix,
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
_IMAGE = "/usr/bin/python3.12"
_PID = 10
_THREAD = "10"


def _rel_call(address: int, target: int) -> bytes:
    relative = target - (address + 5)
    return b"\xe8" + int(relative).to_bytes(4, "little", signed=True)


def _decoded(blob: bytes, address: int):
    instructions = _decode_complete(blob, address)
    assert instructions is not None
    return instructions


def _five(target: int = 0x4000):
    addresses = [0x3000 + (5 * index) for index in range(5)]
    blob = b"".join(_rel_call(address, target) for address in addresses)
    instructions = _decoded(blob, addresses[0])
    labels = tuple(insn.bytes.hex() for insn in instructions)
    return instructions, labels


def _observe(instructions, labels, read=None, file_read=None, context_ok: bool = True):
    def _unused(_address: int, _size: int) -> bytes | None:
        raise AssertionError("the target prefix was read")

    return observe_prefix(
        instructions,
        labels,
        image=_IMAGE,
        pid=_PID,
        thread_id=_THREAD,
        read=_unused if read is None else read,
        file_read=file_read,
        context_ok=context_ok,
    )


def test_five_matching_edges_read_at_most_256_bytes() -> None:
    instructions, labels = _five()
    seen: list[tuple[int, int]] = []

    def read(address: int, size: int) -> bytes:
        seen.append((address, size))
        return b"\x90" * size

    observed = _observe(instructions, labels, read=read, file_read=lambda _address, size: b"\x90" * size)
    assert observed["live_process"] is False
    assert observed["five_site_correspondence"] is True
    assert observed["preservation_established"] is False
    assert observed["premises_discharged"] is False
    assert observed["prefix"]["requested_length"] == PREFIX_BYTE_LIMIT
    assert observed["prefix"]["captured_length"] == PREFIX_BYTE_LIMIT
    assert observed["prefix"]["decoded_length"] == PREFIX_BYTE_LIMIT
    assert observed["prefix"]["incomplete_trailing_hex"] == ""
    assert observed["prefix"]["loaded_bytes_match_file"] is True
    assert observed["prefix"]["child_bytes_read"] is False
    assert seen == [(0x4000, PREFIX_BYTE_LIMIT)]


def test_missing_edge_does_not_invent_a_target() -> None:
    instructions, labels = _five()
    observed = _observe(instructions, labels[:4] + ("e800000000",))
    assert observed["five_site_correspondence"] is False
    assert observed["prefix"]["raw_bytes_hex"] is None
    assert observed["prefix"]["captured_length"] == 0
    assert any(edge["reason"] == "missing" for edge in observed["edges"])


def test_incorrect_displacement_stays_unresolved() -> None:
    classified = classify_direct_call(0x1000, bytes.fromhex("e800000000"), 0x2000, "call")
    assert classified["established"] is False
    assert classified["reason"] == "incorrect_displacement"
    assert classified["target"] is None


def test_differing_targets_do_not_correspond() -> None:
    first, first_labels = _five(0x4000)
    second, second_labels = _five(0x5000)
    mixed = list(first[:4]) + [second[-1]]
    labels = first_labels[:4] + (second_labels[-1],)
    observed = _observe(mixed, labels)
    assert observed["five_site_correspondence"] is False
    assert {edge["target"] for edge in observed["edges"] if edge["established"]} == {"0x4000", "0x5000"}
    assert five_site_correspondence(observed["edges"])["reason"] == "differing_targets"


def test_unreadable_prefix_has_no_fabricated_bytes() -> None:
    instructions, labels = _five()

    def read(_address: int, _size: int) -> bytes | None:
        return None

    observed = _observe(instructions, labels, read=read, file_read=read)
    assert observed["five_site_correspondence"] is True
    assert observed["prefix"]["raw_bytes_hex"] is None
    assert observed["prefix"]["captured_length"] == 0
    assert observed["prefix"]["loaded_bytes_match_file"] is False


def test_incomplete_trailing_byte_is_not_decoded() -> None:
    prefix = read_target_prefix(lambda _address, _size: b"\x90\xe8", lambda _address, _size: b"\x90\xe8", 0x4000)
    assert prefix["captured_length"] == 2
    assert prefix["decoded_length"] == 1
    assert prefix["incomplete_trailing_hex"] == "e8"
    assert prefix["raw_bytes_hex"] == "90e8"


def test_oversized_read_is_refused() -> None:
    prefix = read_target_prefix(
        lambda _address, _size: (_ for _ in ()).throw(AssertionError("oversized read")),
        None,
        0x4000,
        limit=PREFIX_BYTE_LIMIT + 1,
    )
    assert prefix["refused"] is True
    assert prefix["captured_length"] == 0
    assert prefix["raw_bytes_hex"] is None


def test_foreign_context_drops_correspondence() -> None:
    instructions, labels = _five()
    observed = _observe(instructions, labels, context_ok=False)
    assert observed["five_site_correspondence"] is False
    assert observed["prefix"]["raw_bytes_hex"] is None
    assert all(edge["reason"] == "foreign_context" for edge in observed["edges"])


def test_bound_edges_carry_process_identity() -> None:
    instructions, labels = _five()
    edges = bind_labeled_edges(instructions, labels, image=_IMAGE, pid=_PID, thread_id=_THREAD)
    assert all(edge["established"] for edge in edges)
    assert {edge["target"] for edge in edges} == {"0x4000"}
    for edge in edges:
        assert edge["image"] == _IMAGE
        assert edge["pid"] == _PID
        assert edge["thread_id"] == _THREAD
        assert edge["instruction_boundary"] is True
        assert edge["exact_bytes"]
        assert isinstance(edge["displacement"], int)


def test_prefix_bytes_do_not_follow_child_calls() -> None:
    child = _rel_call(0x4000, 0x9000) + (b"\x90" * (PREFIX_BYTE_LIMIT - 5))
    calls: list[int] = []

    def read(address: int, size: int) -> bytes:
        calls.append(address)
        assert size == PREFIX_BYTE_LIMIT
        return child

    instructions, labels = _five()
    observed = _observe(instructions, labels, read=read, file_read=lambda _address, _size: child)
    assert calls == [0x4000]
    assert observed["prefix"]["child_bytes_read"] is False
    assert observed["prefix"]["unresolved_child_calls"]
    assert all(call["resolved"] is False for call in observed["prefix"]["unresolved_child_calls"])


def test_capture_reports_missing_evidence_without_admission() -> None:
    from pyfoldable.application.c2v09_reference_call_prefix import capture_target_prefix

    observed = capture_target_prefix(_ROOT)
    assert observed["live_process"] is True
    assert observed["bind_now"] is True
    assert observed["status"] == NOT_ESTABLISHED
    assert observed["preservation_established"] is False
    assert observed["premises_discharged"] is False
    assert observed["readiness_hypotheses_admitted"] is False
    assert observed["accept_closed"] is True
    assert observed["candidate29_disposition"] == "NOT SELECTED"
    assert observed["eligibility_evidence"] is False
    assert observed["physical_qualification"] is False
    assert observed["authorizes_execution"] is False
    assert observed["constructor_invoked"] is False
    assert observed["reference_helper_invoked"] is False
    assert observed["target_invoked"] is False
    assert observed["historical_addresses_used_as_evidence"] is False
    if observed["five_site_correspondence"] is not True:
        assert observed["prefix"]["raw_bytes_hex"] is None
        assert observed["prefix"]["captured_length"] == 0
    else:
        assert observed["prefix"]["requested_length"] == PREFIX_BYTE_LIMIT
        assert observed["prefix"]["captured_length"] <= PREFIX_BYTE_LIMIT
        assert len({edge["target"] for edge in observed["edges"]}) == 1
    root = _ROOT / "reports" / "c2v09_pre_call_capsule"
    for name, digest in _OBSERVATIONS.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
