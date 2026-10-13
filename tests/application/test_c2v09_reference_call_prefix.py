"""Unread 256-byte prefix for five direct call edges. It does not admit readiness."""

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
    classify_direct_call,
    collect_prefix_observation,
    five_site_correspondence,
    gate_five_sites,
    observe_prefix,
    read_target_prefix,
    replay_prefix_record,
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
        fixture_sites=labels,
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
    assert five_site_correspondence(observed["edges"], expected_sites=labels, fixture=True)["reason"] == "differing_targets"


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
    assert "pid" not in observed["controls"]
    retained = observed["observer_envelope"]["raw_feature"]
    assert retained == observed["controls"]
    assert "pid" not in retained
    assert observed["observer_association"]["pid"] == observed["pid"]
    assert observed["observer_association"]["thread_id"] == observed["thread_id"]
    if observed["genuine_observer"] is True:
        assert observed["static_evidence"] is False
        assert observed["observer_defects"] == []
        assert observed["observer_envelope"]["before"] == observed["observer_envelope"]["after"]
        assert observed["capture_context"] == observed["observer_envelope"]["before"]
        assert observed["observer_envelope"]["probe_receipt"]["read_state_calls"] == 1
        assert observed["observer_envelope"]["probe_receipt"]["cosine_function_calls"] == 0
    else:
        assert observed["prefix"]["captured_length"] == 0
    if observed["controls"].get("thread_id") != observed["thread_id"]:
        assert observed["five_site_correspondence"] is False
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


def test_duplicate_rows_and_repeated_labels_do_not_read() -> None:
    instructions, labels = _five()
    edges = bind_labeled_edges(instructions, labels, image=_IMAGE, pid=_PID, thread_id=_THREAD)
    assert five_site_correspondence([dict(edges[0]) for _ in range(5)], expected_sites=labels, fixture=True)["established"] is False
    observed = _observe([instructions[0]], (labels[0],) * 5)
    assert observed["five_site_correspondence"] is False
    assert observed["prefix"]["captured_length"] == 0


def test_missing_extra_mixed_and_false_boundary_do_not_read() -> None:
    instructions, labels = _five()
    edges = bind_labeled_edges(instructions, labels, image=_IMAGE, pid=_PID, thread_id=_THREAD)

    def read(_address: int, _size: int) -> bytes:
        raise AssertionError("invalid coverage read the target")

    from pyfoldable.application.c2v09_reference_call_prefix import gate_five_sites

    assert five_site_correspondence(edges[:4], expected_sites=labels, fixture=True)["established"] is False
    extra = edges + [dict(edges[0])]
    assert gate_five_sites(extra, read, None, expected_sites=labels, fixture=True)["five_site_correspondence"] is False
    mixed = [dict(edge) for edge in edges]
    mixed[2]["pid"] = 99
    mixed[3]["thread_id"] = "other"
    mixed[4]["image"] = "/tmp/other"
    assert gate_five_sites(mixed, read, None, expected_sites=labels, fixture=True)["five_site_correspondence"] is False
    unmarked = [dict(edge) for edge in edges]
    unmarked[0]["instruction_boundary"] = False
    assert gate_five_sites(unmarked, read, None, expected_sites=labels, fixture=True)["five_site_correspondence"] is False
    forged = [dict(edge) for edge in edges]
    forged[0]["displacement"] = 0
    forged[0]["established"] = True
    assert gate_five_sites(forged, read, None, expected_sites=labels, fixture=True)["five_site_correspondence"] is False


def test_file_mismatch_does_not_claim_a_match() -> None:
    instructions, labels = _five()

    def read(_address: int, size: int) -> bytes:
        return b"\x90" * size

    observed = _observe(instructions, labels, read=read, file_read=lambda _address, size: b"\x00" * size)
    assert observed["five_site_correspondence"] is True
    assert observed["prefix"]["loaded_bytes_match_file"] is False
    assert observed["prefix"]["captured_length"] == PREFIX_BYTE_LIMIT


def _feature(thread: str = _THREAD, **extra: object) -> dict[str, object]:
    record: dict[str, object] = {
        "classification": "OBSERVED",
        "required_bits_ok": True,
        "thread_id": thread,
    }
    record.update(extra)
    return record


def _sample(pid: int = _PID, thread: str = _THREAD, bind_now: bool = True) -> dict[str, object]:
    return {"pid": pid, "thread_id": thread, "bind_now": bind_now}


def _receipt() -> dict[str, object]:
    return {
        "role": "actual loaded probe image used for read_state",
        "source_path": "pyfoldable/application/c2v09_cosine_path_probe.c",
        "read_state_calls": 1,
        "cosine_function_calls": 0,
        "file_image_identity": "OBSERVED",
        "file_image_sha256": "ab" * 32,
    }


def _envelope(
    raw: dict[str, object],
    before: dict[str, object],
    after: dict[str, object],
    receipt: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "raw_feature": raw,
        "before": before,
        "after": after,
        "probe_receipt": receipt,
    }


_EDGE_SITES = (0x61169C, 0x6116D5, 0x61170D, 0x611745, 0x611787)


def _spaced_edges():
    """Place each archived label at its own address so every rel32 lands on one target."""
    base = _EDGE_SITES[0]
    blob = bytearray(b"\x90" * (_EDGE_SITES[-1] + 5 - base))
    for address, label in zip(_EDGE_SITES, EDGE_LABELS, strict=True):
        start = address - base
        blob[start : start + 5] = bytes.fromhex(label)
    return _decoded(bytes(blob), base)


def _collect_envelope(
    envelope: dict[str, object],
    outer: dict[str, object],
) -> tuple[dict[str, object], list[int]]:
    instructions = _spaced_edges()
    calls: list[int] = []

    def read(address: int, _size: int) -> bytes:
        calls.append(address)
        return b"\x90"

    raw = envelope["raw_feature"]
    assert isinstance(raw, dict)
    observed = collect_prefix_observation(
        raw,
        dict(envelope["before"]) if isinstance(envelope["before"], dict) else {},
        instructions,
        image=_IMAGE,
        read=read,
        file_read=read,
        head="0",
        tree="0",
        observer_envelope=envelope,
        outer_context=outer,
    )
    return observed, calls


def test_spaced_edge_labels_share_one_target() -> None:
    instructions = _spaced_edges()
    edges = bind_labeled_edges(instructions, EDGE_LABELS, image=_IMAGE, pid=_PID, thread_id=_THREAD)
    assert [edge["address"] for edge in edges] == [hex(site) for site in _EDGE_SITES]
    correspondence = five_site_correspondence(edges)
    assert correspondence["established"] is True
    assert correspondence["target"] == "0x583ec0"


def test_caller_supplied_identity_does_not_read() -> None:
    raw = _feature(pid=_PID, bind_now=True)
    before = _sample()
    envelope = _envelope(raw, before, _sample(), _receipt())
    outer = _sample()
    snapshot = copy.deepcopy(envelope)
    observed, calls = _collect_envelope(envelope, outer)
    assert observed["genuine_observer"] is False
    assert observed["static_evidence"] is True
    assert observed["five_site_correspondence"] is False
    assert observed["prefix"]["captured_length"] == 0
    assert calls == []
    assert envelope == snapshot
    assert "pid" not in observed["controls"] or observed["controls"]["pid"] == _PID
    assert observed["controls"] == raw


def test_missing_identity_does_not_read() -> None:
    raw = _feature()
    before = {"thread_id": _THREAD, "bind_now": True}
    envelope = _envelope(raw, before, _sample(), _receipt())
    snapshot = copy.deepcopy(raw)
    observed, calls = _collect_envelope(envelope, _sample())
    assert "missing_identity" in observed["observer_defects"]
    assert observed["genuine_observer"] is False
    assert observed["prefix"]["captured_length"] == 0
    assert calls == []
    assert raw == snapshot
    assert "pid" not in raw


def test_context_change_does_not_read() -> None:
    raw = _feature()
    envelope = _envelope(raw, _sample(pid=1), _sample(pid=2), _receipt())
    snapshot = copy.deepcopy(envelope)
    observed, calls = _collect_envelope(envelope, _sample(pid=1))
    assert "context_changed" in observed["observer_defects"]
    assert observed["genuine_observer"] is False
    assert observed["prefix"]["captured_length"] == 0
    assert calls == []
    assert envelope == snapshot


def test_contradictory_raw_metadata_does_not_read() -> None:
    raw = _feature(thread="other", pid=99)
    envelope = _envelope(raw, _sample(), _sample(), _receipt())
    observed, calls = _collect_envelope(envelope, _sample())
    assert "contradictory_metadata" in observed["observer_defects"]
    assert observed["genuine_observer"] is False
    assert observed["prefix"]["captured_length"] == 0
    assert calls == []
    assert raw["thread_id"] == "other"
    assert raw["pid"] == 99
    assert "pid" not in observed["controls"] or observed["controls"]["pid"] == 99


def test_foreign_outer_context_does_not_read() -> None:
    raw = _feature()
    envelope = _envelope(raw, _sample(), _sample(), _receipt())
    outer = _sample(pid=99, thread="other")
    outer_snapshot = copy.deepcopy(outer)
    observed, calls = _collect_envelope(envelope, outer)
    assert "foreign_context" in observed["observer_defects"]
    assert observed["genuine_observer"] is False
    assert observed["prefix"]["captured_length"] == 0
    assert calls == []
    assert outer == outer_snapshot
    assert "pid" not in raw


def test_live_probe_association_cannot_be_relabeled() -> None:
    from pyfoldable.application.c2v09_reference_call_prefix import bind_genuine_observer

    observer = bind_genuine_observer(_ROOT)
    recorded = observer.before["pid"]
    replacement = {"pid": 1, "thread_id": "1", "bind_now": True}
    try:
        observer.before = replacement
    except AttributeError:
        replaced = False
    else:
        replaced = True
    assert replaced is False
    try:
        observer.before["pid"] = 1
    except TypeError:
        mutated = False
    else:
        mutated = True
    assert mutated is False
    assert observer.before["pid"] == recorded


def test_bool_identity_and_receipt_counters_do_not_match() -> None:
    raw = _feature(pid=True)
    receipt = _receipt()
    receipt["read_state_calls"] = True
    receipt["cosine_function_calls"] = False
    envelope = _envelope(raw, _sample(pid=1), _sample(pid=1), receipt)
    observed, calls = _collect_envelope(envelope, _sample(pid=1))
    assert "contradictory_metadata" in observed["observer_defects"]
    assert "missing_receipt" in observed["observer_defects"]
    assert observed["prefix"]["captured_length"] == 0
    assert calls == []


def test_live_observer_reads_one_shared_target() -> None:
    import os
    import subprocess
    import sys

    blob = bytearray(b"\x90" * (_EDGE_SITES[-1] + 5 - _EDGE_SITES[0]))
    for address, label in zip(_EDGE_SITES, EDGE_LABELS, strict=True):
        start = address - _EDGE_SITES[0]
        blob[start : start + 5] = bytes.fromhex(label)
    script = """
import json, sys
from pathlib import Path
from pyfoldable.application.c2v09_reference_call_prefix import bind_genuine_observer, collect_prefix_observation
from pyfoldable.application.c2v09_runtime_semantic_correspondence import _decode_complete
root, blob_hex, base = sys.argv[1:]
instructions = _decode_complete(bytes.fromhex(blob_hex), int(base, 16))
assert instructions is not None
observer = bind_genuine_observer(Path(root))
calls = []

def read(address, size):
    calls.append((address, size))
    return b"\\x90" * size

outer = {"pid": observer.before["pid"], "thread_id": observer.before["thread_id"], "bind_now": True}
observed = collect_prefix_observation(
    observer.raw_feature,
    outer,
    instructions,
    image="/usr/bin/python3.12",
    read=read,
    file_read=read,
    head="0",
    tree="0",
    observer_envelope=observer,
    outer_context=dict(outer),
    )
print(json.dumps({
    "calls": calls,
    "genuine": observed["genuine_observer"],
    "defects": observed["observer_defects"],
    "captured": observed["prefix"]["captured_length"],
    "target_invoked": observed["target_invoked"],
    "controls_pid": "pid" in observed["controls"],
    "same_feature": observed["controls"] == observed["observer_envelope"]["raw_feature"],
}))
"""
    env = os.environ.copy()
    env["LD_BIND_NOW"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", script, str(_ROOT), blob.hex(), hex(_EDGE_SITES[0])],
        env=env,
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["defects"] == []
    assert report["genuine"] is True
    assert report["calls"] == [[0x583EC0, 256], [0x583EC0, 256]]
    assert report["captured"] == 256
    assert report["target_invoked"] is False
    assert report["controls_pid"] is False
    assert report["same_feature"] is True


def test_forged_controls_do_not_ride_a_live_observer() -> None:
    import os
    import subprocess
    import sys

    blob = bytearray(b"\x90" * (_EDGE_SITES[-1] + 5 - _EDGE_SITES[0]))
    for address, label in zip(_EDGE_SITES, EDGE_LABELS, strict=True):
        start = address - _EDGE_SITES[0]
        blob[start : start + 5] = bytes.fromhex(label)
    script = """
import json, sys
from pathlib import Path
from pyfoldable.application.c2v09_reference_call_prefix import bind_genuine_observer, collect_prefix_observation
from pyfoldable.application.c2v09_runtime_semantic_correspondence import _decode_complete
root, blob_hex, base = sys.argv[1:]
instructions = _decode_complete(bytes.fromhex(blob_hex), int(base, 16))
assert instructions is not None
observer = bind_genuine_observer(Path(root))
calls = []

def read(address, size):
    calls.append(address)
    return b"\\x90" * size

forged = {"classification": "OBSERVED", "required_bits_ok": True, "thread_id": "forged", "pid": 1, "bind_now": False}
outer = {"pid": observer.before["pid"], "thread_id": observer.before["thread_id"], "bind_now": observer.before["bind_now"]}
observed = collect_prefix_observation(
    forged,
    {"pid": observer.before["pid"], "thread_id": observer.before["thread_id"], "bind_now": observer.before["bind_now"]},
    instructions,
    image="/usr/bin/python3.12",
    read=read,
    file_read=read,
    head="0",
    tree="0",
    observer_envelope=observer,
    outer_context=outer,
)
print(json.dumps({
    "calls": calls,
    "genuine": observed["genuine_observer"],
    "defects": observed["observer_defects"],
    "captured": observed["prefix"]["captured_length"],
    "controls": observed["controls"],
    "envelope_pid": "pid" in observed["observer_envelope"]["raw_feature"],
}))
"""
    env = os.environ.copy()
    env["LD_BIND_NOW"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", script, str(_ROOT), blob.hex(), hex(_EDGE_SITES[0])],
        env=env,
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["calls"] == []
    assert report["captured"] == 0
    assert report["genuine"] is False
    assert "contradictory_metadata" in report["defects"]
    assert "pid" not in report["controls"]
    assert report["controls"]["thread_id"] != "forged"
    assert report["envelope_pid"] is False


def test_aliased_outer_context_does_not_read() -> None:
    raw = _feature()
    before = _sample()
    envelope = _envelope(raw, before, _sample(), _receipt())
    observed, calls = _collect_envelope(envelope, before)
    assert "context_not_separate" in observed["observer_defects"]
    assert observed["prefix"]["captured_length"] == 0
    assert calls == []
    assert before == _sample()


def test_collector_rejects_missing_and_foreign_identity() -> None:
    instructions = _decoded(b"".join(bytes.fromhex(label) for label in EDGE_LABELS), 0x61169c)
    calls: list[int] = []

    def read(address: int, _size: int) -> bytes:
        calls.append(address)
        return b"\x90"

    controls = {
        "classification": "OBSERVED",
        "required_bits_ok": True,
        "thread_id": _THREAD,
        "bind_now": True,
    }
    original = dict(controls)
    association = {"pid": _PID, "thread_id": _THREAD, "bind_now": True}
    missing = collect_prefix_observation(
        controls,
        association,
        instructions,
        image=_IMAGE,
        read=read,
        file_read=read,
        head="0",
        tree="0",
    )
    assert missing["five_site_correspondence"] is False
    assert missing["prefix"]["captured_length"] == 0
    assert missing["live_process"] is False
    assert controls == original
    assert "pid" not in controls
    foreign = dict(controls)
    foreign["pid"] = 99
    foreign["thread_id"] = "other"
    rejected = collect_prefix_observation(
        foreign,
        association,
        instructions,
        image=_IMAGE,
        read=read,
        file_read=read,
        head="0",
        tree="0",
    )
    assert rejected["five_site_correspondence"] is False
    assert rejected["prefix"]["captured_length"] == 0
    assert foreign["pid"] == 99
    assert foreign["thread_id"] == "other"
    assert calls == []


def test_legacy_prefix_replay_lacks_observer_association() -> None:
    path = _ROOT / "reports" / "c2v09_pre_call_capsule" / "reference_call_prefix.json"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == _OBSERVATIONS["reference_call_prefix.json"]
    payload = json.loads(raw)["canonical_payload"]
    replayed = replay_prefix_record(payload)
    assert replayed["edge_geometry_established"] is True
    assert replayed["observer_associated"] is False
    assert replayed["preservation_established"] is False


def test_prefix_record_is_not_the_measurement_commit() -> None:
    path = _ROOT / "reports" / "c2v09_pre_call_capsule" / "reference_call_prefix.json"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "a4447513d006de822f9aef079a1b7397c93817c35d1089aaa8ecfd9719528ec3"
    document = json.loads(raw)
    payload = document["canonical_payload"]
    assert payload["measurement_implementation_head"] == "0c9976f2a292ad760800bd051950548194867ad5"
    assert payload["measurement_implementation_tree"] == "ee35ff7d7289a7df43bcfa5d13e31377a79b6cce"
    assert payload["record_commit_is_measurement_commit"] is False
    assert payload["live_process"] is True
    assert payload["historical_addresses_used_as_evidence"] is False
    assert payload["five_site_correspondence"] is True
    assert payload["preservation_established"] is False
    assert payload["premises_discharged"] is False
    assert payload["target_invoked"] is False
    assert {edge["target"] for edge in payload["edges"]} == {"0x583ec0"}
    assert all(edge["established"] is True for edge in payload["edges"])
    prefix = payload["prefix"]
    assert prefix["requested_length"] == 256
    assert prefix["captured_length"] == 256
    assert prefix["decoded_length"] == 255
    assert prefix["incomplete_trailing_hex"] == "48"
    assert prefix["loaded_bytes_match_file"] is True
    assert prefix["child_bytes_read"] is False
    assert prefix["unresolved_child_calls"]
    assert all(call["resolved"] is False for call in prefix["unresolved_child_calls"])
    assert "canonical_sha256" not in payload
    assert document["canonical_sha256"] == "5534adb20971568ba2d09399cacfd732896108676d8c11c46163620db471a189"
    assert sha256_bytes(canonical_bytes(payload)) == document["canonical_sha256"]
