"""One unread prefix of the taken entry JE. It does not call that target.

The five-site check and the genuine probe envelope stay in the prefix module.
This module only reads the JE target after fallthrough from the shared entry
reaches that exact six-byte instruction. A supplied address or summary is not
a binding. Historical addresses are labels.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping

import capstone

from pyfoldable.application.c2v09_cosine_path_certificate import (
    _c_function_address,
    _elf_bytes,
    _readable_process_bytes,
    _runtime_to_vaddr,
)
from pyfoldable.application.c2v09_ordered_declaration import (
    CANDIDATE29_DISPOSITION,
    canonical_bytes,
    sha256_bytes,
)
from pyfoldable.application.c2v09_reference_call_prefix import (
    EDGE_LABELS,
    PREFIX_BYTE_LIMIT,
    _empty_prefix,
    _envelope_parts,
    _is_live_observer,
    _json_copy,
    _parent_instructions,
    _public_envelope,
    _sample_association,
    _same_value,
    _split_prefix,
    _typed_equal,
    association_defects,
    bind_genuine_observer,
    bind_labeled_edges,
    five_site_correspondence,
    read_target_prefix,
)
from pyfoldable.application.c2v09_runtime_semantic_correspondence import (
    NOT_ESTABLISHED,
    _decode_complete,
    _git_identity,
    _image_of,
)

JE_BYTES = bytes.fromhex("0f846b9dedff")


def _empty_je() -> dict[str, object]:
    return {
        "established": False,
        "address": None,
        "end": None,
        "exact_bytes": None,
        "displacement": None,
        "target": None,
        "file_bytes_hex": None,
        "loaded_bytes_hex": None,
        "file_match": False,
        "image": None,
        "pid": None,
        "thread_id": None,
    }


def je_site_evidence(
    address: int,
    raw: bytes,
    mnemonic: str,
    size: int,
    file_bytes: bytes | None,
) -> dict[str, object]:
    """The JE is established only from its bytes, length, rel32, and file bytes."""
    record = _empty_je()
    record["loaded_bytes_hex"] = raw.hex()
    record["file_bytes_hex"] = None if file_bytes is None else file_bytes.hex()
    if mnemonic != "je" or raw != JE_BYTES or size != 6 or file_bytes != raw:
        return record
    relative = int.from_bytes(raw[2:], "little", signed=True)
    target = address + 6 + relative
    record.update(
        {
            "established": True,
            "address": hex(address),
            "end": hex(address + 6),
            "exact_bytes": raw.hex(),
            "displacement": relative,
            "target": hex(target),
            "file_match": True,
        }
    )
    return record


def _exact_je(insn: capstone.CsInsn) -> bool:
    return insn.mnemonic == "je" and bytes(insn.bytes) == JE_BYTES and insn.size == 6


_STOP_GROUPS = {
    capstone.CS_GRP_JUMP,
    capstone.CS_GRP_CALL,
    capstone.CS_GRP_RET,
    capstone.CS_GRP_INT,
    capstone.CS_GRP_IRET,
    capstone.CS_GRP_BRANCH_RELATIVE,
}


def _breaks_fallthrough(insn: capstone.CsInsn) -> bool:
    """A transfer ends the straight walk, including prefixed ret and jmp forms."""
    groups = set(insn.groups)
    if groups & _STOP_GROUPS:
        return True
    name = insn.mnemonic
    return any(token in name for token in ("jmp", "call", "ret", "loop", "int"))


def _fallthrough_je(
    instructions: list[capstone.CsInsn],
    entry: int,
) -> tuple[capstone.CsInsn | None, list[capstone.CsInsn]]:
    """Follow only the next instruction. A branch, call, or return ends the walk."""
    by_address: dict[int, capstone.CsInsn] = {}
    for insn in instructions:
        if insn.address in by_address:
            return None, []
        by_address[insn.address] = insn
    address = entry
    seen: set[int] = set()
    path: list[capstone.CsInsn] = []
    while address in by_address and address not in seen:
        seen.add(address)
        insn = by_address[address]
        path.append(insn)
        if _exact_je(insn):
            return insn, path
        if _breaks_fallthrough(insn):
            return None, path
        address = insn.address + insn.size
    return None, path


def _context_matches(edges: list[dict[str, object]], image: str, pid: int, thread_id: str) -> bool:
    if not edges or type(pid) is not int or not isinstance(thread_id, str) or not thread_id or not isinstance(image, str) or not image:
        return False
    return all(
        _same_value(edge.get("pid"), pid) and _same_value(edge.get("thread_id"), thread_id) and _same_value(edge.get("image"), image)
        for edge in edges
    )


def _genuine(envelope: object, outer: object, controls: object, pid: int, thread_id: str) -> bool:
    if not _is_live_observer(envelope) or not isinstance(controls, Mapping):
        return False
    if association_defects(envelope, outer):
        return False
    raw, before, _after, _receipt = _envelope_parts(envelope)
    if not isinstance(raw, Mapping) or not isinstance(before, Mapping):
        return False
    if not _typed_equal(_json_copy(controls), _json_copy(raw)):
        return False
    return _same_value(before.get("pid"), pid) and _same_value(before.get("thread_id"), thread_id)


def _closed(head: str | None, tree: str | None) -> dict[str, object]:
    return {
        "measurement_implementation_head": head,
        "measurement_implementation_tree": tree,
        "record_commit_is_measurement_commit": False,
        "readiness_hypotheses_admitted": False,
        "readiness_admitted": False,
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
        "historical_addresses_used_as_evidence": False,
        "indirect_tail_unresolved": True,
        "linear_window_calls_unresolved": True,
        "other_targets_unresolved": True,
        "indirect_sites_unresolved": True,
        "exits_unresolved": True,
        "status": NOT_ESTABLISHED,
        "preservation_established": False,
        "premises_discharged": False,
    }


def collect_taken_branch(
    edges: list[dict[str, object]],
    *,
    read_process,
    read_file,
    image: str,
    pid: int,
    thread_id: str,
    static_control: bool = False,
    limit: int = PREFIX_BYTE_LIMIT,
    claimed_summary: Mapping[str, object] | None = None,
    observer_envelope: object | None = None,
    outer_context: Mapping[str, object] | None = None,
    controls: Mapping[str, object] | None = None,
    head: str | None = None,
    tree: str | None = None,
) -> dict[str, object]:
    """Read the taken target once, only after fallthrough binds the JE."""
    accounting: dict[str, list[dict[str, object]]] = {
        "entry_process": [],
        "entry_file": [],
        "taken_process": [],
        "taken_file": [],
    }
    refused_limit = limit > PREFIX_BYTE_LIMIT or limit < 0
    context_ok = _context_matches(edges, image, pid, thread_id)
    genuine = _genuine(observer_envelope, outer_context, controls, pid, thread_id) and context_ok
    static = static_control is True and observer_envelope is None and outer_context is None and context_ok
    if genuine:
        evidence_class = "genuine"
    elif static:
        evidence_class = "static"
    else:
        evidence_class = "refused"
    allowed = evidence_class in {"genuine", "static"}
    correspondence = five_site_correspondence(list(edges))
    five_ok = correspondence["established"] is True and isinstance(correspondence["target"], str)
    je = _empty_je()
    fallthrough: list[str] = []
    entry_file_match = False
    entry_captured = 0
    prefix = _empty_prefix(limit, refused=refused_limit)
    if allowed and five_ok and not refused_limit:
        entry = int(str(correspondence["target"]), 16)
        accounting["entry_process"].append({"address": hex(entry), "size": PREFIX_BYTE_LIMIT})
        entry_blob = read_process(entry, PREFIX_BYTE_LIMIT)
        if isinstance(entry_blob, (bytes, bytearray)) and entry_blob:
            entry_captured = len(entry_blob)
            accounting["entry_file"].append({"address": hex(entry), "size": len(entry_blob)})
            file_entry = read_file(entry, len(entry_blob))
            entry_file_match = file_entry == bytes(entry_blob)
            decoded_bytes, _trailing = _split_prefix(bytes(entry_blob), entry)
            instructions = [] if not decoded_bytes else _decode_complete(decoded_bytes, entry) or []
            insn, path = _fallthrough_je(instructions, entry)
            fallthrough = [hex(item.address) for item in path]
            if entry_file_match and insn is not None and isinstance(file_entry, (bytes, bytearray)):
                offset = insn.address - entry
                loaded = bytes(entry_blob[offset : offset + insn.size])
                file_slice = bytes(file_entry[offset : offset + insn.size])
                if loaded == bytes(insn.bytes):
                    je = je_site_evidence(insn.address, bytes(insn.bytes), insn.mnemonic, insn.size, file_slice)
                    je["image"] = image
                    je["pid"] = pid
                    je["thread_id"] = thread_id
            if je["established"] is True and isinstance(je["target"], str):
                target = int(je["target"], 16)

                def read_taken(address: int, size: int) -> bytes | None:
                    accounting["taken_process"].append({"address": hex(address), "size": size})
                    return read_process(address, size)

                def file_taken(address: int, size: int) -> bytes | None:
                    accounting["taken_file"].append({"address": hex(address), "size": size})
                    return read_file(address, size)

                prefix = read_target_prefix(read_taken, file_taken, target, limit)
    taken_match = (
        je["established"] is True
        and prefix["refused"] is not True
        and isinstance(prefix["raw_bytes_hex"], str)
        and prefix["raw_bytes_hex"] != ""
        and prefix["loaded_bytes_match_file"] is True
        and isinstance(prefix["captured_length"], int)
        and prefix["captured_length"] > 0
    )
    gaps = [
        "the taken je does not discharge the four return premises",
        "the indirect tail stays unresolved",
        "the four linear-window calls stay unresolved",
        "other direct targets stay unresolved",
        "the three parent indirect sites stay unresolved",
        "the four original exits stay unresolved",
    ]
    if evidence_class == "refused":
        gaps.insert(0, "the observer or capture context does not authorize this read")
    elif refused_limit:
        gaps.insert(0, "the taken-target request exceeds 256 bytes")
    elif not five_ok:
        gaps.insert(0, "the five call edges were not established in this process")
    elif entry_captured == 0:
        gaps.insert(0, "the entry prefix was not readable")
    elif not entry_file_match:
        gaps.insert(0, "the entry prefix bytes do not match the file")
    elif je["established"] is not True:
        gaps.insert(0, "the entry je was not reached by instruction-boundary fallthrough")
    elif prefix["raw_bytes_hex"] is None:
        gaps.insert(0, "the taken target prefix was not readable")
    elif prefix["loaded_bytes_match_file"] is not True:
        gaps.insert(0, "the taken target bytes do not match the file")
    observed = {
        "evidence_class": evidence_class,
        "static_evidence": evidence_class != "genuine",
        "genuine_observer": evidence_class == "genuine",
        "live_process": False,
        "five_site_correspondence": five_ok,
        "correspondence_reason": correspondence["reason"],
        "edges": _json_copy(edges),
        "entry_file_match": entry_file_match,
        "entry_captured_length": entry_captured,
        "fallthrough": fallthrough,
        "je": je,
        "taken_target_correspondence": taken_match,
        "prefix": prefix,
        "read_accounting": accounting,
        "claimed_summary": None if claimed_summary is None else _json_copy(claimed_summary),
        "controls": _json_copy(controls) if isinstance(controls, Mapping) else {},
        "observer_envelope": None if observer_envelope is None else _public_envelope(observer_envelope),
        "bind_now": False,
        "pid": pid if genuine else None,
        "thread_id": thread_id if genuine else None,
        "gaps": gaps,
    }
    observed.update(_closed(head, tree))
    return observed


def capture_taken_prefix_here(root: Path) -> dict[str, object]:
    """Read one process. Do not call the taken target or the entry."""
    outer = _sample_association()
    envelope = bind_genuine_observer(root)
    raw = envelope.raw_feature
    wrapper = _c_function_address(math.cos)
    image = None if wrapper is None else _image_of(wrapper)
    head, tree = _git_identity(root)
    authorizes = _is_live_observer(envelope) and not association_defects(envelope, outer)
    instructions: list[capstone.CsInsn] = _parent_instructions(image) if authorizes and image is not None else []
    before = envelope.before
    pid = before.get("pid")
    thread_id = before.get("thread_id")
    edges: list[dict[str, object]] = []
    if authorizes and image is not None and isinstance(pid, int) and isinstance(thread_id, str):
        edges = bind_labeled_edges(instructions, EDGE_LABELS, image=image, pid=pid, thread_id=thread_id)

    def read_process(address: int, size: int) -> bytes | None:
        if size > PREFIX_BYTE_LIMIT:
            return None
        return _readable_process_bytes(address, size)

    def read_file(address: int, size: int) -> bytes | None:
        mapped = _runtime_to_vaddr(address)
        if mapped is None or size > PREFIX_BYTE_LIMIT:
            return None
        return _elf_bytes(mapped[0], mapped[1], size)

    observed = collect_taken_branch(
        edges,
        read_process=read_process,
        read_file=read_file,
        image=image or "",
        pid=pid if isinstance(pid, int) else -1,
        thread_id=thread_id if isinstance(thread_id, str) else "",
        observer_envelope=envelope,
        outer_context=outer,
        controls=raw if isinstance(raw, Mapping) else {},
        head=head,
        tree=tree,
    )
    observed["live_process"] = True
    observed["bind_now"] = before.get("bind_now") is True
    observed["single_process_thread"] = (
        isinstance(raw, Mapping)
        and raw.get("thread_id") == outer.get("thread_id")
        and before.get("thread_id") == envelope.after.get("thread_id")
        and before.get("pid") == envelope.after.get("pid")
        and envelope.probe_receipt is not None
    )
    return observed


def _failed(reason: str) -> dict[str, object]:
    observed = {
        "evidence_class": "refused",
        "static_evidence": True,
        "genuine_observer": False,
        "live_process": False,
        "five_site_correspondence": False,
        "entry_file_match": False,
        "je": _empty_je(),
        "taken_target_correspondence": False,
        "prefix": _empty_prefix(PREFIX_BYTE_LIMIT),
        "read_accounting": {"entry_process": [], "entry_file": [], "taken_process": [], "taken_file": []},
        "fallthrough": [],
        "bind_now": False,
        "pid": None,
        "controls": {},
        "gaps": [reason],
    }
    observed.update(_closed(None, None))
    return observed


def capture_taken_prefix(root: Path) -> dict[str, object]:
    """One LD_BIND_NOW process. A failed child does not invent a taken target."""
    if os.environ.get("LD_BIND_NOW") != "1":
        script = (
            "import json, sys\n"
            "from pathlib import Path\n"
            "from pyfoldable.application.c2v09_reference_call_taken_prefix import capture_taken_prefix_here\n"
            "print(json.dumps(capture_taken_prefix_here(Path(sys.argv[1]))))\n"
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
            return _failed("the bound process did not return a taken-prefix observation")
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            parsed = None
        if not isinstance(parsed, dict) or parsed.get("bind_now") is not True:
            return _failed("the bound observation was not from one LD_BIND_NOW process")
        return parsed
    return capture_taken_prefix_here(root)


def taken_prefix_document(root: Path) -> dict[str, object]:
    payload = capture_taken_prefix(root)
    return {
        "canonical_sha256": sha256_bytes(canonical_bytes(payload)),
        "digest_scope": (
            "SHA-256 of the section 7.3 canonical bytes of canonical_payload only. "
            "canonical_sha256 and digest_scope are outside that payload."
        ),
        "canonical_payload": payload,
    }
