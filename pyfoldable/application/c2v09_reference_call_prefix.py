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
    if not isinstance(observed_pid, int) or not isinstance(captured_pid, int):
        return False
    return observed_pid == captured_pid


def replay_prefix_record(payload: Mapping[str, object]) -> dict[str, object]:
    """Replay stored edges. Do not invent an observer association from collector fields."""
    raw_edges = payload.get("edges")
    edges = list(raw_edges) if isinstance(raw_edges, list) else []
    geometry = five_site_correspondence(edges)
    controls = payload.get("controls")
    association = payload.get("observer_association")
    identity = False
    if isinstance(controls, dict) and isinstance(association, dict):
        identity = observer_association_matches(controls, association)
    return {
        "edge_geometry_established": geometry["established"] is True,
        "observer_associated": identity,
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
) -> dict[str, object]:
    """Decide a prefix read from an untouched observer record and a separate association."""
    matched = observer_association_matches(controls, association)
    pid = association.get("pid")
    thread_id = association.get("thread_id")
    observed = observe_prefix(
        instructions,
        EDGE_LABELS,
        image=image,
        pid=pid if isinstance(pid, int) else -1,
        thread_id=thread_id if isinstance(thread_id, str) else "",
        read=read,
        file_read=file_read,
        context_ok=matched,
    )
    gaps = [
        "the four return premises are not discharged",
        "prefix child calls stay unresolved",
        "other direct targets stay unresolved",
        "the three indirect sites stay unresolved",
        "the four exits stay unresolved",
    ]
    if not matched:
        gaps.insert(0, "the observer identity does not match this capture")
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
            "bind_now": association.get("bind_now") is True,
            "pid": pid if isinstance(pid, int) else None,
            "thread_id": thread_id if isinstance(thread_id, str) else None,
            "controls": controls,
            "observer_association": {
                "pid": association.get("pid"),
                "thread_id": association.get("thread_id"),
                "bind_now": association.get("bind_now"),
            },
            "status": NOT_ESTABLISHED,
            "preservation_established": False,
            "premises_discharged": False,
            "gaps": gaps,
        }
    )
    return observed


def capture_target_prefix_here(root: Path) -> dict[str, object]:
    """Read one process. Do not call the target, constructor, or reference helper."""
    pid = os.getpid()
    thread_id = _thread_id()
    probed = _probe_words(root / PROBE_SOURCE)
    controls = _feature_record(None if probed is None else probed[0], _fegetround())
    association = {
        "pid": pid,
        "thread_id": thread_id,
        "bind_now": os.environ.get("LD_BIND_NOW") == "1",
    }
    wrapper = _c_function_address(math.cos)
    image = None if wrapper is None else _image_of(wrapper)
    head, tree = _git_identity(root)
    instructions: list[capstone.CsInsn] = []
    if image is not None and observer_association_matches(controls, association):
        newref_symbol = _symbol_runtime(image, "_Py_NewReference")
        if newref_symbol is not None:
            runtime, _vaddr, size = newref_symbol
            blob, match, _elf_vaddr = _load(image, runtime, size)
            newref = None if blob is None else _decode_complete(blob, runtime)
            call = None if newref is None or not match else _zero_dependent_call(newref)
            parent = None if call is None else call.get("target")
            if isinstance(parent, int):
                window, _window_match, _parent_vaddr = _load(image, parent, _WINDOW)
                if window is not None:
                    piece = window
                    while piece and _decode_complete(piece, parent) is None:
                        piece = piece[:-1]
                    decoded = None if not piece else _decode_complete(piece, parent)
                    if decoded is not None:
                        _exact, parent_match, _parent_vaddr = _load(image, parent, len(piece))
                        if parent_match:
                            instructions = decoded

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
        controls,
        association,
        instructions,
        image=image or "",
        read=read,
        file_read=file_read,
        head=head,
        tree=tree,
    )
    observed["live_process"] = True
    observed["single_process_thread"] = controls.get("thread_id") == thread_id and probed is not None
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
