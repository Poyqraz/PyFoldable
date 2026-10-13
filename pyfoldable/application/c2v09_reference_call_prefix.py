"""One unread prefix for five direct calls. It does not call the target.

Historical call bytes are labels. A current edge is bound only from an
instruction in this process. Five-site correspondence requires all five
labels, each established, and one shared target. The target read is at most
256 bytes and does not follow child calls.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import capstone

from pyfoldable.application.c2v09_cosine_path_certificate import (
    PROBE_SOURCE,
    _c_function_address,
    _elf_bytes,
    _fegetround,
    _feature_record,
    _probe_words,
    _readable_process_bytes,
    _runtime_to_vaddr,
)
from pyfoldable.application.c2v09_ordered_declaration import (
    CANDIDATE29_DISPOSITION,
    canonical_bytes,
    sha256_bytes,
)
from pyfoldable.application.c2v09_reference_call_evidence import (
    _WINDOW,
    _load,
    _thread_id,
    _zero_dependent_call,
)
from pyfoldable.application.c2v09_runtime_semantic_correspondence import (
    NOT_ESTABLISHED,
    _decode_complete,
    _direct_target,
    _git_identity,
    _image_of,
    _symbol_runtime,
)

PREFIX_BYTE_LIMIT = 256
EDGE_LABELS = (
    "e81f28f7ff",
    "e8e627f7ff",
    "e8ae27f7ff",
    "e87627f7ff",
    "e83427f7ff",
)


def _empty_prefix(requested: int, refused: bool = False) -> dict[str, object]:
    return {
        "refused": refused,
        "requested_length": requested,
        "captured_length": 0,
        "decoded_length": 0,
        "raw_bytes_hex": None,
        "incomplete_trailing_hex": "",
        "loaded_bytes_match_file": False,
        "unresolved_child_calls": [],
        "child_bytes_read": False,
    }


def classify_direct_call(
    address: int,
    raw: bytes,
    decoded_target: int | None,
    mnemonic: str,
) -> dict[str, object]:
    """A direct call is established only when its rel32 and decoded target agree."""
    relative = None
    computed = None
    if len(raw) == 5 and raw[0] == 0xE8:
        relative = int.from_bytes(raw[1:], "little", signed=True)
        computed = address + 5 + relative
    established = mnemonic == "call" and computed is not None and decoded_target == computed
    return {
        "established": established,
        "reason": "established" if established else "incorrect_displacement",
        "target": None if not established or computed is None else hex(computed),
        "displacement": relative,
    }


def bind_labeled_edges(
    instructions: list[capstone.CsInsn],
    labels: tuple[str, ...] | list[str],
    *,
    image: str,
    pid: int,
    thread_id: str,
) -> list[dict[str, object]]:
    """Bind each label on its own instruction boundary. Addresses are current."""
    edges: list[dict[str, object]] = []
    for label in labels:
        matches = [insn for insn in instructions if insn.bytes.hex() == label]
        if len(matches) != 1:
            edges.append(
                {
                    "label": label,
                    "established": False,
                    "reason": "missing" if not matches else "ambiguous",
                    "address": None,
                    "end": None,
                    "exact_bytes": None,
                    "displacement": None,
                    "target": None,
                    "image": image,
                    "pid": pid,
                    "thread_id": thread_id,
                    "instruction_boundary": False,
                }
            )
            continue
        insn = matches[0]
        decoded = _direct_target(insn) if insn.mnemonic == "call" else None
        classified = classify_direct_call(insn.address, bytes(insn.bytes), decoded, insn.mnemonic)
        edges.append(
            {
                "label": label,
                "established": classified["established"],
                "reason": classified["reason"],
                "address": hex(insn.address),
                "end": hex(insn.address + insn.size),
                "exact_bytes": insn.bytes.hex(),
                "displacement": classified["displacement"],
                "target": classified["target"],
                "image": image,
                "pid": pid,
                "thread_id": thread_id,
                "instruction_boundary": True,
            }
        )
    return edges


def _declaration(
    expected_sites: tuple[str, ...] | None,
    fixture: bool,
) -> tuple[str, ...] | None:
    """The packet declaration is fixed. A fixture must name five distinct sites."""
    if not fixture:
        if expected_sites not in (None, EDGE_LABELS):
            return None
        return EDGE_LABELS
    if expected_sites is None or len(expected_sites) != 5 or len(set(expected_sites)) != 5:
        return None
    return tuple(expected_sites)


def _edge_evidence(edge: Mapping[str, object], label: str) -> bool:
    """Recompute the call from its bytes. Summary flags are not evidence."""
    if edge.get("instruction_boundary") is not True:
        return False
    if edge.get("label") != label or edge.get("exact_bytes") != label:
        return False
    try:
        raw = bytes.fromhex(label)
        start = int(str(edge.get("address")), 16)
        stop = int(str(edge.get("end")), 16)
    except (TypeError, ValueError):
        return False
    if len(raw) != 5 or raw[0] != 0xE8 or stop - start != 5:
        return False
    relative = int.from_bytes(raw[1:], "little", signed=True)
    if edge.get("displacement") != relative:
        return False
    if edge.get("target") != hex(start + 5 + relative):
        return False
    if not isinstance(edge.get("pid"), int):
        return False
    if not isinstance(edge.get("thread_id"), str) or not edge.get("thread_id"):
        return False
    if not isinstance(edge.get("image"), str) or not edge.get("image"):
        return False
    return True


def five_site_correspondence(
    edges: list[dict[str, object]],
    expected_sites: tuple[str, ...] | None = None,
    *,
    fixture: bool = False,
) -> dict[str, object]:
    """Exact coverage of the declared sites. Repeated or summary-only rows stay unresolved."""
    declared = _declaration(expected_sites, fixture)
    if declared is None or len(edges) != 5:
        return {"established": False, "target": None, "reason": "unresolved_edge"}
    by_label: dict[str, dict[str, object]] = {}
    addresses: list[str] = []
    for edge in edges:
        label = edge.get("label")
        if not isinstance(label, str) or label in by_label or label not in declared:
            return {"established": False, "target": None, "reason": "unresolved_edge"}
        if not _edge_evidence(edge, label):
            return {"established": False, "target": None, "reason": "unresolved_edge"}
        by_label[label] = edge
        address = edge.get("address")
        if not isinstance(address, str) or address in addresses:
            return {"established": False, "target": None, "reason": "unresolved_edge"}
        addresses.append(address)
    if set(by_label) != set(declared):
        return {"established": False, "target": None, "reason": "unresolved_edge"}
    if len({edge["pid"] for edge in edges}) != 1 or len({edge["thread_id"] for edge in edges}) != 1:
        return {"established": False, "target": None, "reason": "mixed_context"}
    if len({edge["image"] for edge in edges}) != 1:
        return {"established": False, "target": None, "reason": "mixed_context"}
    targets = {edge["target"] for edge in edges}
    if len(targets) != 1:
        return {"established": False, "target": None, "reason": "differing_targets"}
    return {"established": True, "target": next(iter(targets)), "reason": "established"}


def _split_prefix(blob: bytes, address: int) -> tuple[bytes, bytes]:
    piece = blob
    while piece and _decode_complete(piece, address) is None:
        piece = piece[:-1]
    return piece, blob[len(piece) :]


def _child_calls(decoded: bytes, address: int) -> list[dict[str, object]]:
    instructions = _decode_complete(decoded, address)
    if instructions is None:
        return []
    rows: list[dict[str, object]] = []
    for insn in instructions:
        if insn.mnemonic != "call":
            continue
        target = _direct_target(insn)
        rows.append(
            {
                "address": hex(insn.address),
                "bytes": insn.bytes.hex(),
                "target": None if target is None else hex(target),
                "resolved": False,
            }
        )
    return rows


def read_target_prefix(
    read,
    file_read,
    target: int,
    limit: int = PREFIX_BYTE_LIMIT,
) -> dict[str, object]:
    """Read at most 256 bytes. A larger request does not call the reader."""
    if limit > PREFIX_BYTE_LIMIT or limit < 0:
        return _empty_prefix(limit, refused=True)
    blob = read(target, limit)
    if blob is None or len(blob) > limit:
        return _empty_prefix(limit)
    decoded, trailing = _split_prefix(blob, target)
    file_bytes = None if file_read is None else file_read(target, len(blob))
    return {
        "refused": False,
        "requested_length": limit,
        "captured_length": len(blob),
        "decoded_length": len(decoded),
        "raw_bytes_hex": blob.hex(),
        "incomplete_trailing_hex": trailing.hex(),
        "loaded_bytes_match_file": file_bytes == blob,
        "unresolved_child_calls": _child_calls(decoded, target),
        "child_bytes_read": False,
    }


def _foreign(edges: list[dict[str, object]]) -> list[dict[str, object]]:
    rewritten: list[dict[str, object]] = []
    for edge in edges:
        row = dict(edge)
        row["established"] = False
        row["reason"] = "foreign_context"
        row["target"] = None
        rewritten.append(row)
    return rewritten


def gate_five_sites(
    edges: list[dict[str, object]],
    read,
    file_read,
    *,
    expected_sites: tuple[str, ...] | None = None,
    fixture: bool = False,
) -> dict[str, object]:
    """Read the shared target only after the declared sites revalidate."""
    correspondence = five_site_correspondence(edges, expected_sites, fixture=fixture)
    prefix = _empty_prefix(PREFIX_BYTE_LIMIT)
    if correspondence["established"] is True and isinstance(correspondence["target"], str):
        prefix = read_target_prefix(read, file_read, int(correspondence["target"], 16))
    return {
        "five_site_correspondence": correspondence["established"] is True,
        "correspondence_reason": correspondence["reason"],
        "prefix": prefix,
        "live_process": False,
    }


def observe_prefix(
    instructions: list[capstone.CsInsn],
    labels: tuple[str, ...] | list[str] | None = None,
    *,
    fixture_sites: tuple[str, ...] | None = None,
    image: str,
    pid: int,
    thread_id: str,
    read,
    file_read,
    context_ok: bool,
) -> dict[str, object]:
    """Classify the declared sites. A repeated label argument does not replace them."""
    fixture = fixture_sites is not None
    declared = _declaration(fixture_sites, fixture)
    if labels and not fixture and tuple(labels) != EDGE_LABELS:
        declared = None
    if declared is None:
        edges = []
        gated = {
            "five_site_correspondence": False,
            "correspondence_reason": "unresolved_edge",
            "prefix": _empty_prefix(PREFIX_BYTE_LIMIT),
            "live_process": False,
        }
    else:
        edges = bind_labeled_edges(instructions, declared, image=image, pid=pid, thread_id=thread_id)
        if not context_ok:
            edges = _foreign(edges)
        gated = gate_five_sites(edges, read, file_read, expected_sites=declared, fixture=fixture)
    return {
        "live_process": False,
        "preservation_established": False,
        "premises_discharged": False,
        "readiness_admitted": False,
        "five_site_correspondence": gated["five_site_correspondence"],
        "correspondence_reason": gated["correspondence_reason"],
        "edges": edges,
        "prefix": gated["prefix"],
        "other_targets_unresolved": True,
        "indirect_sites_unresolved": True,
        "exits_unresolved": True,
        "historical_addresses_used_as_evidence": False,
    }


def observer_association_matches(controls: Mapping[str, object], association: Mapping[str, object]) -> bool:
    """Both process and thread must already be present. Missing fields are not filled in."""
    if controls.get("classification") != "OBSERVED" or controls.get("required_bits_ok") is not True:
        return False
    if association.get("bind_now") is not True:
        return False
    observed_thread = controls.get("thread_id")
    observed_pid = controls.get("pid")
    captured_thread = association.get("thread_id")
    captured_pid = association.get("pid")
    if not isinstance(observed_thread, str) or not observed_thread:
        return False
    if not isinstance(captured_thread, str) or observed_thread != captured_thread:
        return False
    if not isinstance(observed_pid, int) or isinstance(observed_pid, bool):
        return False
    if not isinstance(captured_pid, int) or isinstance(captured_pid, bool):
        return False
    return observed_pid == captured_pid


class _BoundObserver:
    """In-process probe result. Its seal is not a caller-writable dictionary."""

    __slots__ = ()

    @property
    def raw_feature(self) -> object:
        return _SEALS[self][0]

    @property
    def before(self) -> object:
        return _SEALS[self][1]

    @property
    def after(self) -> object:
        return _SEALS[self][2]

    @property
    def probe_receipt(self) -> object:
        return _SEALS[self][3]


_LIVE_OBSERVERS: set[_BoundObserver] = set()
_SEALS: dict[_BoundObserver, tuple[object, object, object, object]] = {}


def _sample_association() -> dict[str, object]:
    return {
        "pid": os.getpid(),
        "thread_id": _thread_id(),
        "bind_now": os.environ.get("LD_BIND_NOW") == "1",
    }


def bind_genuine_observer(root: Path) -> _BoundObserver:
    """Call the probe once and record process identity around that call."""
    before = _sample_association()
    probed = _probe_words(root / PROBE_SOURCE)
    after = _sample_association()
    words = None if probed is None else probed[0]
    receipt = None if probed is None else probed[1]
    raw = _feature_record(words if isinstance(words, list) else None, _fegetround())
    observer = _BoundObserver()
    _SEALS[observer] = (
        _freeze(raw),
        _freeze(before),
        _freeze(after),
        None if not isinstance(receipt, dict) else _freeze(receipt),
    )
    _LIVE_OBSERVERS.add(observer)
    return observer


def _is_live_observer(envelope: object) -> bool:
    return type(envelope) is _BoundObserver and envelope in _LIVE_OBSERVERS and envelope in _SEALS


def _envelope_parts(
    envelope: object,
) -> tuple[object, object, object, object]:
    if type(envelope) is _BoundObserver:
        return _SEALS.get(envelope, (None, None, None, None))
    if isinstance(envelope, Mapping):
        return (
            envelope.get("raw_feature"),
            envelope.get("before"),
            envelope.get("after"),
            envelope.get("probe_receipt"),
        )
    return None, None, None, None


def _is_pid(value: object) -> bool:
    return type(value) is int


def _same_value(left: object, right: object) -> bool:
    return type(left) is type(right) and left == right


def _typed_equal(left: object, right: object) -> bool:
    """Bool and int stay distinct. True == 1 is not evidence equality."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            return False
        return all(_typed_equal(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_typed_equal(item, other) for item, other in zip(left, right))
    return left == right


def _complete_sample(sample: object) -> bool:
    if not isinstance(sample, Mapping):
        return False
    thread = sample.get("thread_id")
    return _is_pid(sample.get("pid")) and isinstance(thread, str) and bool(thread) and isinstance(sample.get("bind_now"), bool)


def _receipt_ok(receipt: object) -> bool:
    if not isinstance(receipt, Mapping):
        return False
    digest = receipt.get("file_image_sha256")
    calls = receipt.get("read_state_calls")
    cosine = receipt.get("cosine_function_calls")
    return (
        type(calls) is int
        and calls == 1
        and type(cosine) is int
        and cosine == 0
        and receipt.get("file_image_identity") == "OBSERVED"
        and receipt.get("source_path") == PROBE_SOURCE
        and isinstance(digest, str)
        and len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest)
    )


def _json_copy(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_copy(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_copy(inner) for inner in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"Unsupported observer value {type(value).__name__}.")


def _freeze(value: object) -> object:
    copied = _json_copy(value)
    if isinstance(copied, dict):
        return MappingProxyType({key: _freeze(inner) for key, inner in copied.items()})
    if isinstance(copied, list):
        return tuple(_freeze(inner) for inner in copied)
    return copied


def association_defects(envelope: object, outer_context: object) -> list[str]:
    """Content checks only. A passing dictionary is still not a live observer."""
    defects: list[str] = []
    raw, before, after, receipt = _envelope_parts(envelope)
    if outer_context is not None and (outer_context is raw or outer_context is before or outer_context is after):
        defects.append("context_not_separate")
    if not _complete_sample(before) or not _complete_sample(after):
        defects.append("missing_identity")
    elif (
        before.get("pid") != after.get("pid")
        or before.get("thread_id") != after.get("thread_id")
        or before.get("bind_now") != after.get("bind_now")
    ):
        defects.append("context_changed")
    elif before.get("bind_now") is not True:
        defects.append("missing_identity")
    if not isinstance(raw, Mapping) or not isinstance(raw.get("thread_id"), str) or not raw.get("thread_id"):
        if "missing_identity" not in defects:
            defects.append("missing_identity")
    else:
        measured_thread = before.get("thread_id") if isinstance(before, Mapping) else None
        measured_pid = before.get("pid") if isinstance(before, Mapping) else None
        measured_bind = before.get("bind_now") if isinstance(before, Mapping) else None
        contradictory = not _same_value(raw.get("thread_id"), measured_thread)
        if "pid" in raw and not _same_value(raw.get("pid"), measured_pid):
            contradictory = True
        if "bind_now" in raw and not _same_value(raw.get("bind_now"), measured_bind):
            contradictory = True
        if "recording_thread_id" in raw and not _same_value(raw.get("recording_thread_id"), measured_thread):
            contradictory = True
        if contradictory:
            defects.append("contradictory_metadata")
        if raw.get("classification") != "OBSERVED" or raw.get("required_bits_ok") is not True:
            defects.append("feature_not_observed")
    if not _receipt_ok(receipt):
        defects.append("missing_receipt")
    if not isinstance(outer_context, Mapping) or not _complete_sample(outer_context):
        defects.append("foreign_context")
    elif isinstance(before, Mapping) and isinstance(after, Mapping) and (
        outer_context.get("pid") != before.get("pid")
        or outer_context.get("thread_id") != before.get("thread_id")
        or outer_context.get("bind_now") is not True
        or outer_context.get("pid") != after.get("pid")
        or outer_context.get("thread_id") != after.get("thread_id")
    ):
        defects.append("foreign_context")
    return defects


def _public_envelope(envelope: object) -> dict[str, object]:
    raw, before, after, receipt = _envelope_parts(envelope)
    return {
        "raw_feature": _json_copy(raw) if isinstance(raw, Mapping) else None,
        "before": _json_copy(before) if isinstance(before, Mapping) else None,
        "after": _json_copy(after) if isinstance(after, Mapping) else None,
        "probe_receipt": _json_copy(receipt) if isinstance(receipt, Mapping) else None,
    }


def replay_prefix_record(payload: Mapping[str, object]) -> dict[str, object]:
    """Replay stored edges. A serialized envelope is not a live observer."""
    raw_edges = payload.get("edges")
    edges = list(raw_edges) if isinstance(raw_edges, list) else []
    geometry = five_site_correspondence(edges)
    controls = payload.get("controls")
    association = payload.get("observer_association")
    identity = False
    if isinstance(controls, dict) and isinstance(association, dict):
        identity = observer_association_matches(controls, association)
    envelope = payload.get("observer_envelope")
    outer = payload.get("capture_context")
    consistent = isinstance(envelope, Mapping) and not association_defects(envelope, outer)
    return {
        "edge_geometry_established": geometry["established"] is True,
        "observer_associated": identity,
        "recorded_association_consistent": consistent,
        "preservation_established": False,
    }


def collect_prefix_observation(
    controls: dict[str, object],
    association: Mapping[str, object],
    instructions: list[capstone.CsInsn],
    *,
    image: str,
    read,
    file_read,
    head: str | None,
    tree: str | None,
    observer_envelope: object | None = None,
    outer_context: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Read the target only for a live probe envelope. Dictionaries stay static."""
    source: object = observer_envelope if observer_envelope is not None else {
        "raw_feature": controls,
        "before": association,
        "after": association,
        "probe_receipt": None,
    }
    defects = association_defects(source, outer_context)
    sealed_raw = _envelope_parts(source)[0]
    if isinstance(sealed_raw, Mapping) and not _typed_equal(_json_copy(controls), _json_copy(sealed_raw)):
        if "contradictory_metadata" not in defects:
            defects.append("contradictory_metadata")
    live = _is_live_observer(observer_envelope)
    authorizes = live and not defects
    _raw, before, after, _receipt = _envelope_parts(source)
    consistent = (
        isinstance(before, Mapping)
        and isinstance(after, Mapping)
        and _complete_sample(before)
        and before.get("pid") == after.get("pid")
        and before.get("thread_id") == after.get("thread_id")
        and before.get("bind_now") == after.get("bind_now")
    )
    if consistent:
        pid = before.get("pid")
        thread_id = before.get("thread_id")
        bind_now = before.get("bind_now") is True
    else:
        pid = None
        thread_id = None
        bind_now = False
    observed = observe_prefix(
        instructions,
        EDGE_LABELS,
        image=image,
        pid=pid if _is_pid(pid) else -1,
        thread_id=thread_id if isinstance(thread_id, str) else "",
        read=read,
        file_read=file_read,
        context_ok=authorizes,
    )
    gaps = [
        "the four return premises are not discharged",
        "prefix child calls stay unresolved",
        "other direct targets stay unresolved",
        "the three indirect sites stay unresolved",
        "the four exits stay unresolved",
    ]
    if not authorizes:
        detail = "the observer identity does not match this capture"
        if defects:
            detail = detail + ": " + ", ".join(defects)
        gaps.insert(0, detail)
    elif observed["five_site_correspondence"] is not True:
        gaps.insert(0, "the five call edges were not established in this process")
    elif observed["prefix"]["raw_bytes_hex"] is None:
        gaps.insert(0, "the target prefix was not readable")
    observed.update(
        {
            "measurement_implementation_head": head,
            "measurement_implementation_tree": tree,
            "record_commit_is_measurement_commit": False,
            "readiness_hypotheses_admitted": False,
            "accept_closed": True,
            "candidate29_disposition": CANDIDATE29_DISPOSITION,
            "eligibility_evidence": False,
            "physical_qualification": False,
            "authorizes_execution": False,
            "output_sampled": False,
            "cosine_function_calls": 0,
            "ulp_function_calls": 0,
            "nextafter_function_calls": 0,
            "constructor_invoked": False,
            "reference_helper_invoked": False,
            "target_invoked": False,
            "bind_now": bind_now,
            "pid": pid if _is_pid(pid) else None,
            "thread_id": thread_id if isinstance(thread_id, str) else None,
            "controls": _json_copy(sealed_raw) if isinstance(sealed_raw, Mapping) else _json_copy(controls),
            "capture_context": _json_copy(outer_context) if isinstance(outer_context, Mapping) else None,
            "observer_envelope": _public_envelope(source),
            "observer_association": {
                "pid": pid if _is_pid(pid) else None,
                "thread_id": thread_id if isinstance(thread_id, str) else None,
                "bind_now": bind_now,
            },
            "observer_defects": list(defects),
            "genuine_observer": authorizes,
            "static_evidence": not live,
            "status": NOT_ESTABLISHED,
            "preservation_established": False,
            "premises_discharged": False,
            "gaps": gaps,
        }
    )
    return observed


def _parent_instructions(image: str) -> list[capstone.CsInsn]:
    """Decode the current parent window. This does not read the target prefix."""
    newref_symbol = _symbol_runtime(image, "_Py_NewReference")
    if newref_symbol is None:
        return []
    runtime, _vaddr, size = newref_symbol
    blob, match, _elf_vaddr = _load(image, runtime, size)
    newref = None if blob is None else _decode_complete(blob, runtime)
    call = None if newref is None or not match else _zero_dependent_call(newref)
    parent = None if call is None else call.get("target")
    if not isinstance(parent, int):
        return []
    window, _window_match, _parent_vaddr = _load(image, parent, _WINDOW)
    if window is None:
        return []
    piece = window
    while piece and _decode_complete(piece, parent) is None:
        piece = piece[:-1]
    decoded = None if not piece else _decode_complete(piece, parent)
    if decoded is None:
        return []
    _exact, parent_match, _parent_vaddr = _load(image, parent, len(piece))
    if not parent_match:
        return []
    return decoded


def capture_target_prefix_here(root: Path) -> dict[str, object]:
    """Read one process. Do not call the target, constructor, or reference helper."""
    outer = _sample_association()
    envelope = bind_genuine_observer(root)
    raw = envelope.raw_feature
    wrapper = _c_function_address(math.cos)
    image = None if wrapper is None else _image_of(wrapper)
    head, tree = _git_identity(root)
    authorizes = _is_live_observer(envelope) and not association_defects(envelope, outer)
    instructions = _parent_instructions(image) if authorizes and image is not None else []

    def read(address: int, size: int) -> bytes | None:
        if size > PREFIX_BYTE_LIMIT:
            return None
        return _readable_process_bytes(address, size)

    def file_read(address: int, size: int) -> bytes | None:
        mapped = _runtime_to_vaddr(address)
        if mapped is None or size > PREFIX_BYTE_LIMIT:
            return None
        return _elf_bytes(mapped[0], mapped[1], size)

    observed = collect_prefix_observation(
        raw,
        envelope.before,
        instructions,
        image=image or "",
        read=read,
        file_read=file_read,
        head=head,
        tree=tree,
        observer_envelope=envelope,
        outer_context=outer,
    )
    observed["live_process"] = True
    observed["single_process_thread"] = (
        raw.get("thread_id") == outer.get("thread_id")
        and envelope.before.get("thread_id") == envelope.after.get("thread_id")
        and envelope.before.get("pid") == envelope.after.get("pid")
        and envelope.probe_receipt is not None
    )
    return observed


def capture_target_prefix(root: Path) -> dict[str, object]:
    """One LD_BIND_NOW process. A failed child does not invent correspondence."""
    if os.environ.get("LD_BIND_NOW") != "1":
        script = (
            "import json, sys\n"
            "from pathlib import Path\n"
            "from pyfoldable.application.c2v09_reference_call_prefix import capture_target_prefix_here\n"
            "print(json.dumps(capture_target_prefix_here(Path(sys.argv[1]))))\n"
        )
        env = os.environ.copy()
        env["LD_BIND_NOW"] = "1"
        completed = subprocess.run(
            [sys.executable, "-c", script, str(root)],
            env=env,
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            return _failed("the bound process did not return a prefix observation")
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            parsed = None
        if not isinstance(parsed, dict) or parsed.get("bind_now") is not True or parsed.get("pid") is None:
            return _failed("the bound observation was not from one LD_BIND_NOW process")
        return parsed
    return capture_target_prefix_here(root)


def _failed(reason: str) -> dict[str, object]:
    return {
        "live_process": False,
        "status": NOT_ESTABLISHED,
        "preservation_established": False,
        "premises_discharged": False,
        "readiness_hypotheses_admitted": False,
        "accept_closed": True,
        "candidate29_disposition": CANDIDATE29_DISPOSITION,
        "eligibility_evidence": False,
        "physical_qualification": False,
        "authorizes_execution": False,
        "bind_now": False,
        "pid": None,
        "constructor_invoked": False,
        "reference_helper_invoked": False,
        "target_invoked": False,
        "historical_addresses_used_as_evidence": False,
        "five_site_correspondence": False,
        "prefix": _empty_prefix(PREFIX_BYTE_LIMIT),
        "gaps": [reason],
    }


def prefix_observation_document(root: Path) -> dict[str, object]:
    payload = capture_target_prefix(root)
    return {
        "canonical_sha256": sha256_bytes(canonical_bytes(payload)),
        "digest_scope": (
            "SHA-256 of the section 7.3 canonical bytes of canonical_payload only. "
            "canonical_sha256 and digest_scope are outside that payload."
        ),
        "canonical_payload": payload,
    }
