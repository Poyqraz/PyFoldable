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


def five_site_correspondence(edges: list[dict[str, object]]) -> dict[str, object]:
    """Five established edges with one target. Any other result stays unresolved."""
    if len(edges) != 5 or not all(edge.get("established") is True for edge in edges):
        return {"established": False, "target": None, "reason": "unresolved_edge"}
    targets = {edge.get("target") for edge in edges}
    if len(targets) != 1 or None in targets:
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


def observe_prefix(
    instructions: list[capstone.CsInsn],
    labels: tuple[str, ...] | list[str],
    *,
    image: str,
    pid: int,
    thread_id: str,
    read,
    file_read,
    context_ok: bool,
) -> dict[str, object]:
    """Classify edges and, only when they agree, read one prefix. Not a live record."""
    edges = bind_labeled_edges(instructions, labels, image=image, pid=pid, thread_id=thread_id)
    if not context_ok:
        edges = _foreign(edges)
    correspondence = five_site_correspondence(edges)
    prefix = _empty_prefix(PREFIX_BYTE_LIMIT)
    if correspondence["established"] is True and isinstance(correspondence["target"], str):
        prefix = read_target_prefix(read, file_read, int(correspondence["target"], 16))
    return {
        "live_process": False,
        "preservation_established": False,
        "premises_discharged": False,
        "readiness_admitted": False,
        "five_site_correspondence": correspondence["established"] is True,
        "correspondence_reason": correspondence["reason"],
        "edges": edges,
        "prefix": prefix,
        "other_targets_unresolved": True,
        "indirect_sites_unresolved": True,
        "exits_unresolved": True,
        "historical_addresses_used_as_evidence": False,
    }


def _context_ok(controls: dict[str, object], thread_id: str) -> bool:
    return (
        controls.get("classification") == "OBSERVED"
        and controls.get("required_bits_ok") is True
        and controls.get("thread_id") == thread_id
        and controls.get("bind_now") is True
    )


def capture_target_prefix_here(root: Path) -> dict[str, object]:
    """Read one process. Do not call the target, constructor, or reference helper."""
    pid = os.getpid()
    thread_id = _thread_id()
    probed = _probe_words(root / PROBE_SOURCE)
    controls = _feature_record(None if probed is None else probed[0], _fegetround())
    controls["pid"] = pid
    controls["thread_id"] = thread_id
    controls["bind_now"] = os.environ.get("LD_BIND_NOW") == "1"
    wrapper = _c_function_address(math.cos)
    image = None if wrapper is None else _image_of(wrapper)
    head, tree = _git_identity(root)
    instructions: list[capstone.CsInsn] = []
    if image is not None and _context_ok(controls, thread_id):
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

    observed = observe_prefix(
        instructions,
        EDGE_LABELS,
        image=image or "",
        pid=pid,
        thread_id=thread_id,
        read=read,
        file_read=file_read,
        context_ok=_context_ok(controls, thread_id) and image is not None,
    )
    observed["live_process"] = True
    gaps = [
        "the four return premises are not discharged",
        "prefix child calls stay unresolved",
        "other direct targets stay unresolved",
        "the three indirect sites stay unresolved",
        "the four exits stay unresolved",
    ]
    if observed["five_site_correspondence"] is not True:
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
            "bind_now": controls.get("bind_now") is True,
            "pid": pid,
            "thread_id": thread_id,
            "single_process_thread": controls.get("thread_id") == thread_id and probed is not None,
            "controls": controls,
            "status": NOT_ESTABLISHED,
            "preservation_established": False,
            "gaps": gaps,
        }
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
