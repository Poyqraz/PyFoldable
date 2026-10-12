"""Evidence for the call on one side of _Py_NewReference.

The slice reads loaded bytes in one LD_BIND_NOW process. It does not call
PyFloat_FromDouble, _Py_NewReference, or the callee. A push is not a restore.
An ABI name is not evidence that a callee preserves a register.
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
from pyfoldable.application.c2v09_fromdouble_storage import _written_canonicals
from pyfoldable.application.c2v09_ordered_declaration import (
    CANDIDATE29_DISPOSITION,
    canonical_bytes,
    sha256_bytes,
)
from pyfoldable.application.c2v09_runtime_semantic_correspondence import (
    NOT_ESTABLISHED,
    _decode_complete,
    _direct_target,
    _git_identity,
    _image_of,
    _leading_register,
    _register_width,
    _symbol_runtime,
)

_TRACKED = ("r14", "rbx")
_ENTRY = "entry"
_OTHER = "other"
_WINDOW = 0xA00
_STUB_BYTES = 48
_MAX_STUBS = 24
_MAX_STATES = 4000


def _thread_id() -> str:
    native = getattr(threading, "get_native_id", None)
    return str(native() if native is not None else threading.get_ident())


def _load(image: str, runtime: int, size: int) -> tuple[bytes | None, bool, str | None]:
    blob = _readable_process_bytes(runtime, size)
    if blob is None or len(blob) != size:
        return None, False, None
    mapped = _runtime_to_vaddr(runtime)
    vaddr = None if mapped is None else hex(mapped[1])
    file_bytes = None if mapped is None else _elf_bytes(mapped[0], mapped[1], size)
    return blob, file_bytes == blob, vaddr


def _rows(instructions: list[capstone.CsInsn]) -> list[dict[str, object]]:
    return [
        {
            "address": hex(insn.address),
            "bytes": insn.bytes.hex(),
            "mnemonic": insn.mnemonic,
            "operands": insn.op_str,
        }
        for insn in instructions
    ]


def _operand_register(insn: capstone.CsInsn) -> tuple[str, int] | None:
    width = _register_width(_leading_register(insn.op_str.split(",")[0] if insn.op_str else None))
    if width is None:
        return None
    return width


def _unmodeled_stack(insn: capstone.CsInsn) -> bool:
    """A stack slot write or rsp change this model does not track."""
    text = insn.op_str
    if "[" in text and any(name in text for name in ("rsp", "rbp", "esp", "ebp")):
        return True
    if insn.mnemonic in {"pushfq", "popfq", "enter"}:
        return True
    written = _written_canonicals(insn)
    if written is None:
        return False
    if "rsp" not in written or insn.mnemonic in {"push", "pop", "call", "ret"}:
        return False
    return not (insn.mnemonic in {"add", "sub"} and text.startswith("rsp,"))


def _rip_address(insn: capstone.CsInsn) -> int | None:
    text = insn.op_str
    if "rip + " in text:
        token = text.split("rip + ", 1)[1].split("]", 1)[0].split()[0]
        sign = 1
    elif "rip - " in text:
        token = text.split("rip - ", 1)[1].split("]", 1)[0].split()[0]
        sign = -1
    else:
        return None
    if not token.startswith("0x") and not token.isdigit():
        return None
    return insn.address + insn.size + sign * int(token, 16)


def _adjust_rsp(insn: capstone.CsInsn) -> int | None:
    """Signed qword delta applied to a tracked push stack. None means the model stops."""
    if insn.mnemonic not in {"add", "sub"} or not insn.op_str.startswith("rsp, "):
        return None
    token = insn.op_str.split(",", 1)[1].strip()
    try:
        value = int(token, 0)
    except ValueError:
        return None
    if value % 8:
        return None
    slots = value // 8
    return slots if insn.mnemonic == "sub" else -slots


def prove_entry_restore(
    instructions: list[capstone.CsInsn],
    entry: int,
) -> dict[str, object]:
    """Whether r14 and rbx still hold their entry values at every captured return.

    A push records a stack slot. It does not restore the register. A call or an
    uncaptured branch leaves the path unresolved. The walk state is finite.
    """
    by_address = {insn.address: insn for insn in instructions}
    seen: set[tuple] = set()
    pending: list[tuple] = [(entry, _ENTRY, _ENTRY, (), False)]
    returns: list[dict[str, object]] = []
    unresolved: list[str] = []
    calls: list[dict[str, str]] = []
    pushes: list[dict[str, str]] = []
    pops: list[dict[str, str]] = []
    overwrites: list[dict[str, str]] = []
    budget_exhausted = False
    while pending:
        address, r14, rbx, slots, broken = pending.pop()
        key = (address, r14, rbx, slots, broken)
        if key in seen:
            continue
        if len(seen) >= _MAX_STATES:
            budget_exhausted = True
            break
        seen.add(key)
        insn = by_address.get(address)
        if insn is None:
            unresolved.append(hex(address))
            continue
        values = {"r14": r14, "rbx": rbx}
        written = _written_canonicals(insn)
        if written is None:
            broken = True
            written = set()
        if _unmodeled_stack(insn):
            broken = True
        if insn.mnemonic == "push":
            operand = _operand_register(insn)
            if operand is None or operand[1] != 64 or broken or len(slots) >= 32:
                broken = True
            else:
                saved = operand[0]
                pushes.append({"address": hex(insn.address), "register": saved, "value": values.get(saved, _OTHER)})
                if not broken:
                    slots = slots + ((saved, values.get(saved, _OTHER)),)
        elif insn.mnemonic == "leave":
            broken = True
        elif insn.mnemonic == "pop":
            operand = _operand_register(insn)
            if operand is None or operand[1] != 64 or broken or not slots or slots[-1][0] == "pad":
                broken = True
            else:
                restored = operand[0]
                saved_reg, saved_value = slots[-1]
                slots = slots[:-1]
                values[restored] = saved_value if saved_reg == restored else _OTHER
                pops.append({"address": hex(insn.address), "register": restored, "restores_entry": values[restored] == _ENTRY})
        elif insn.mnemonic in {"add", "sub"} and insn.op_str.startswith("rsp,"):
            delta = _adjust_rsp(insn)
            if delta is None or broken:
                broken = True
            elif delta > 0:
                slots = slots + tuple(("pad", _OTHER) for _ in range(delta))
            else:
                for _ in range(-delta):
                    if not slots:
                        broken = True
                        break
                    slots = slots[:-1]
        elif insn.mnemonic in {"mov", "lea"} and insn.op_str.startswith("rsp"):
            broken = True
        if insn.mnemonic == "ret":
            returns.append({"address": hex(insn.address), "r14": values["r14"], "rbx": values["rbx"], "broken": broken})
            continue
        for reg in _TRACKED:
            if reg in written and insn.mnemonic not in {"push", "pop"}:
                values[reg] = _OTHER
                overwrites.append({"address": hex(insn.address), "register": reg, "mnemonic": insn.mnemonic})
        if insn.mnemonic == "call":
            target = _direct_target(insn)
            calls.append({"address": hex(insn.address), "target": None if target is None else hex(target)})
            broken = True
            for reg in _TRACKED:
                values[reg] = _OTHER
            nxt = insn.address + insn.size
            pending.append((nxt, values["r14"], values["rbx"], slots, True))
            continue
        if insn.mnemonic.startswith("j"):
            target = _direct_target(insn)
            if target is None:
                unresolved.append(hex(insn.address))
                broken = True
            else:
                pending.append((target, values["r14"], values["rbx"], slots, broken))
            if insn.mnemonic != "jmp":
                nxt = insn.address + insn.size
                pending.append((nxt, values["r14"], values["rbx"], slots, broken))
            continue
        pending.append((insn.address + insn.size, values["r14"], values["rbx"], slots, broken))
    def _unique(rows: list[dict[str, object]]) -> list[dict[str, object]]:
        seen_rows: set[str] = set()
        unique_rows: list[dict[str, object]] = []
        for row in rows:
            key = json.dumps(row, sort_keys=True)
            if key in seen_rows:
                continue
            seen_rows.add(key)
            unique_rows.append(row)
        return unique_rows

    returns = _unique(returns)
    calls = _unique(calls)
    pushes = _unique(pushes)
    pops = _unique(pops)
    overwrites = _unique(overwrites)
    restored = [
        row for row in returns
        if row["r14"] == _ENTRY and row["rbx"] == _ENTRY and row["broken"] is False
    ]
    established = bool(returns) and not unresolved and not calls and not budget_exhausted and len(restored) == len(returns)
    return {
        "established": established,
        "returns": returns,
        "returns_restoring_entry": [row["address"] for row in restored],
        "unresolved_exits": sorted(set(unresolved)),
        "outgoing_calls": calls,
        "pushes": pushes,
        "pops": pops,
        "overwrites": overwrites,
        "budget_exhausted": budget_exhausted,
        "assumptions": [],
    }


def _straight_outcome(instructions: list[capstone.CsInsn], address: int) -> tuple[str, capstone.CsInsn | None]:
    by_address = {insn.address: insn for insn in instructions}
    seen: set[int] = set()
    while address in by_address and address not in seen:
        seen.add(address)
        insn = by_address[address]
        if insn.mnemonic == "call":
            return "call", insn
        if insn.mnemonic == "ret":
            return "ret", insn
        if insn.mnemonic.startswith("j"):
            return "branch", insn
        address = insn.address + insn.size
    return "end", None


def _zero_dependent_call(instructions: list[capstone.CsInsn]) -> dict[str, object] | None:
    """A call on one side of a rip-relative test, with a return on the other side."""
    for index, branch in enumerate(instructions):
        if not branch.mnemonic.startswith("j") or branch.mnemonic == "jmp" or index == 0:
            continue
        compared = instructions[index - 1]
        if compared.mnemonic != "test":
            continue
        loaded = None
        for earlier in reversed(instructions[:index]):
            if earlier.mnemonic == "mov" and "rip" in earlier.op_str:
                loaded = earlier
                break
        if loaded is None:
            continue
        taken = _direct_target(branch)
        fallthrough = branch.address + branch.size
        if taken is None:
            continue
        sides = (
            _straight_outcome(instructions, taken),
            _straight_outcome(instructions, fallthrough),
        )
        calls = [item for kind, item in sides if kind == "call" and item is not None]
        returns = [item for kind, item in sides if kind == "ret"]
        if len(calls) != 1 or not returns:
            continue
        insn = calls[0]
        return {
            "call_address": hex(insn.address),
            "call_bytes": insn.bytes.hex(),
            "target": _direct_target(insn),
            "branch_address": hex(branch.address),
            "branch_mnemonic": branch.mnemonic,
            "branch_target": hex(taken),
            "flag_instruction": hex(loaded.address),
            "flag_address": None if _rip_address(loaded) is None else hex(_rip_address(loaded)),
        }
    return None


def _live_after_call(instructions: list[capstone.CsInsn], call_address: int) -> list[str]:
    """Registers named by instructions after the call and before the next ret."""
    found: list[str] = []
    seen_call = False
    for insn in instructions:
        if insn.address == call_address:
            seen_call = True
            continue
        if not seen_call:
            continue
        if insn.mnemonic == "ret":
            break
        for token in insn.op_str.replace(",", " ").split():
            width = _register_width(token)
            if width is not None and width[0] in _TRACKED and width[0] not in found:
                found.append(width[0])
    return found


def _outlined_stubs(
    image: str,
    entry: int,
    window: list[capstone.CsInsn],
) -> list[dict[str, object]]:
    inside = {insn.address for insn in window}
    found: list[dict[str, object]] = []
    seen: set[int] = set()
    for insn in window:
        if not insn.mnemonic.startswith("j"):
            continue
        target = _direct_target(insn)
        if target is None or target in inside or target in seen:
            continue
        seen.add(target)
        if len(found) >= _MAX_STUBS:
            break
        blob, match, vaddr = _load(image, target, _STUB_BYTES)
        if blob is None:
            continue
        decoded = list(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64).disasm(blob, target))
        piece: list[capstone.CsInsn] = []
        returns_to_window = False
        for item in decoded:
            piece.append(item)
            if item.mnemonic.startswith("j") or item.mnemonic in {"call", "ret"}:
                dest = _direct_target(item)
                returns_to_window = dest in inside
                break
        if not piece:
            continue
        size = piece[-1].address + piece[-1].size - target
        exact, exact_match, exact_vaddr = _load(image, target, size)
        if exact is None:
            continue
        found.append(
            {
                "address": hex(target),
                "elf_vaddr": exact_vaddr,
                "image": image,
                "loaded_bytes_hex": exact.hex(),
                "loaded_bytes_match_file": exact_match,
                "returns_to_window": returns_to_window,
                "disassembly": _rows(piece),
            }
        )
    return found


def analyze_reference_call(
    newref: list[capstone.CsInsn],
    callee: list[capstone.CsInsn],
    stubs: list[list[capstone.CsInsn]],
) -> dict[str, object]:
    call = _zero_dependent_call(newref)
    writes = []
    incomplete = False
    for insn in newref:
        if insn.mnemonic == "call":
            continue
        written = _written_canonicals(insn)
        if written is None:
            incomplete = True
            continue
        for reg in _TRACKED:
            if reg in written:
                writes.append({"address": hex(insn.address), "register": reg})
    combined = list(callee)
    for stub in stubs:
        combined.extend(stub)
    entry = callee[0].address if callee else 0
    proof = prove_entry_restore(combined, entry) if callee else {
        "established": False,
        "returns": [],
        "unresolved_exits": [],
        "outgoing_calls": [],
        "pushes": [],
        "pops": [],
        "overwrites": [],
        "budget_exhausted": False,
        "assumptions": [],
        "returns_restoring_entry": [],
    }
    no_call_preserves = not writes and not incomplete and any(insn.mnemonic == "ret" for insn in newref)
    return {
        "newref_writes_tracked_registers": writes,
        "newref_effect_information_complete": not incomplete,
        "no_call_path_preserves_r14_and_rbx": no_call_preserves and call is not None,
        "call": None if call is None else {key: value for key, value in call.items() if key != "target"} | {
            "target": None if call.get("target") is None else hex(call["target"]),
        },
        "callee_proof": proof,
        "preservation_established": False if call is None else bool(proof["established"]),
    }


def capture_reference_call_here(root: Path) -> dict[str, object]:
    """Read this process only. Do not call the constructor or the reference helper."""
    pid = os.getpid()
    thread_id = _thread_id()
    probed = _probe_words(root / PROBE_SOURCE)
    controls = _feature_record(None if probed is None else probed[0], _fegetround())
    controls["pid"] = pid
    controls["bind_now"] = os.environ.get("LD_BIND_NOW") == "1"
    wrapper = _c_function_address(math.cos)
    image = None if wrapper is None else _image_of(wrapper)
    head, tree = _git_identity(root)
    gaps = ["the call side of _Py_NewReference was not located in this process"]
    body: dict[str, object] = {
        "status": NOT_ESTABLISHED,
        "preservation_established": False,
        "readiness_admitted": False,
    }
    if image is not None:
        newref_symbol = _symbol_runtime(image, "_Py_NewReference")
        constructor_symbol = _symbol_runtime(image, "PyFloat_FromDouble")
        if newref_symbol is not None:
            runtime, vaddr, size = newref_symbol
            blob, match, elf_vaddr = _load(image, runtime, size)
            instructions = None if blob is None else _decode_complete(blob, runtime)
            if blob is not None and instructions is not None and match:
                call = _zero_dependent_call(instructions)
                flag = None
                if call is not None and isinstance(call.get("flag_address"), str):
                    flag_address = int(call["flag_address"], 16)
                    flag_bytes, flag_match, flag_vaddr = _load(image, flag_address, 4)
                    flag = {
                        "address": hex(flag_address),
                        "elf_vaddr": flag_vaddr,
                        "image": image,
                        "loaded_bytes_hex": None if flag_bytes is None else flag_bytes.hex(),
                        "loaded_bytes_match_file": flag_match,
                        "selects_future_branch": False,
                    }
                callee_instructions: list[capstone.CsInsn] = []
                callee_match = False
                callee_vaddr = None
                stubs: list[list[capstone.CsInsn]] = []
                stub_rows: list[dict[str, object]] = []
                target = None if call is None else call.get("target")
                stub_records: list[dict[str, object]] = []
                if isinstance(target, int):
                    callee_blob, _window_match, callee_vaddr = _load(image, target, _WINDOW)
                    if callee_blob is not None:
                        piece = callee_blob
                        while piece and _decode_complete(piece, target) is None:
                            piece = piece[:-1]
                        decoded = None if not piece else _decode_complete(piece, target)
                        if decoded is not None:
                            _exact, callee_match, callee_vaddr = _load(image, target, len(piece))
                            callee_instructions = decoded if callee_match else []
                        stub_records = _outlined_stubs(image, target, callee_instructions)
                        for record in stub_records:
                            if record.get("returns_to_window") is not True or record.get("loaded_bytes_match_file") is not True:
                                continue
                            stub_blob = bytes.fromhex(str(record["loaded_bytes_hex"]))
                            stub_ins = _decode_complete(stub_blob, int(str(record["address"]), 16))
                            if stub_ins is not None:
                                stubs.append(stub_ins)
                                stub_rows.append(record)
                analysis = analyze_reference_call(instructions, callee_instructions, stubs)
                constructor_use = []
                if constructor_symbol is not None and isinstance(target, int):
                    cons_blob, cons_match, cons_vaddr = _load(image, constructor_symbol[0], constructor_symbol[2])
                    cons_ins = None if cons_blob is None else _decode_complete(cons_blob, constructor_symbol[0])
                    if cons_ins is not None and cons_match:
                        for insn in cons_ins:
                            if insn.mnemonic == "call" and _direct_target(insn) == runtime:
                                constructor_use.append(
                                    {
                                        "address": hex(insn.address),
                                        "bytes": insn.bytes.hex(),
                                        "target": hex(runtime),
                                        "live_after_call": _live_after_call(cons_ins, insn.address),
                                    }
                                )
                gaps = []
                if call is None:
                    gaps.append("no zero-test-dependent call was decoded in _Py_NewReference")
                if not callee_instructions:
                    gaps.append("the call target bytes were not captured")
                proof = analysis["callee_proof"]
                if proof["outgoing_calls"]:
                    gaps.append("outgoing calls from the callee are unresolved child paths")
                if proof["unresolved_exits"]:
                    gaps.append("the callee still has unresolved exits")
                if proof["budget_exhausted"]:
                    gaps.append("the preservation walk reached its finite state budget")
                if not analysis["preservation_established"]:
                    gaps.append("r14 and rbx entry values are not established across the call")
                if flag is not None and flag.get("loaded_bytes_match_file") is not True:
                    gaps.append("the branch control dword does not match the file image")
                body = {
                    "status": NOT_ESTABLISHED if gaps else "ESTABLISHED CONDITIONALLY",
                    "readiness_admitted": False,
                    "preservation_established": analysis["preservation_established"],
                    "no_call_path_preserves_r14_and_rbx": analysis["no_call_path_preserves_r14_and_rbx"],
                    "newref_writes_tracked_registers": analysis["newref_writes_tracked_registers"],
                    "call": analysis["call"],
                    "constructor_call_sites": constructor_use,
                    "newref": {
                        "address": hex(runtime),
                        "elf_vaddr": elf_vaddr,
                        "image": image,
                        "symbol_name": "_Py_NewReference",
                        "symbol_size": size,
                        "loaded_bytes_hex": blob.hex(),
                        "loaded_bytes_match_file": match,
                        "coverage": "complete" if _decode_complete(blob, runtime) is not None else "incomplete",
                        "disassembly": _rows(instructions),
                    },
                    "callee": {
                        "address": None if not isinstance(target, int) else hex(target),
                        "elf_vaddr": callee_vaddr,
                        "image": image,
                        "symbol_name": None,
                        "loaded_bytes_hex": b"".join(insn.bytes for insn in callee_instructions).hex(),
                        "loaded_bytes_match_file": callee_match and bool(callee_instructions),
                        "decoded_bytes": sum(insn.size for insn in callee_instructions),
                        "window_bytes": _WINDOW,
                        "instruction_bytes_are_aligned": bool(callee_instructions),
                        "coverage": (
                            "missing" if not callee_instructions
                            else "complete_window" if sum(insn.size for insn in callee_instructions) == _WINDOW
                            else "complete_prefix"
                        ),
                    },
                    "flag_control": flag,
                    "outlined_stubs": stub_rows,
                    "callee_events": {
                        "pushes": proof["pushes"],
                        "pops": proof["pops"],
                        "overwrites": proof["overwrites"],
                        "outgoing_calls": proof["outgoing_calls"],
                        "unresolved_exits": proof["unresolved_exits"],
                        "returns": proof["returns"],
                    },
                    "assumptions": [
                        "no ABI callee-saved rule is used",
                        "a push is not evidence that the entry value is restored",
                        "the recorded flag dword does not select a future branch",
                        "outgoing calls and uncaptured branches stay unresolved",
                    ],
                    "gaps": gaps,
                }
                # file match for the callee window was computed above; correct the field
                if isinstance(target, int):
                    body["callee"]["loaded_bytes_match_file"] = callee_match if callee_instructions else False
    status = body.get("status", NOT_ESTABLISHED)
    if controls.get("classification") != "OBSERVED" or controls.get("required_bits_ok") is not True:
        gaps = list(body.get("gaps", [])) + ["required numerical controls were not observed in this process"]
        status = NOT_ESTABLISHED
    if controls.get("thread_id") != thread_id:
        gaps = list(body.get("gaps", [])) + ["controls are not from this thread"]
        status = NOT_ESTABLISHED
    body["status"] = status
    body["gaps"] = gaps if image is not None and body.get("newref") else body.get("gaps", gaps)
    return {
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
        "bind_now": controls.get("bind_now") is True,
        "pid": pid,
        "thread_id": thread_id,
        "single_process_thread": controls.get("thread_id") == thread_id and probed is not None,
        "controls": controls,
        "archived_reference_not_evidence": {
            "call": "0x583d32",
            "target": "0x611480",
            "used_as_evidence": False,
        },
        "dossier": body,
        "status": status,
        "gaps": body.get("gaps", gaps),
    }


def capture_reference_call(root: Path) -> dict[str, object]:
    """One LD_BIND_NOW process. Controls from another process are not reused."""
    if os.environ.get("LD_BIND_NOW") != "1":
        script = (
            "import json, sys\n"
            "from pathlib import Path\n"
            "from pyfoldable.application.c2v09_reference_call_evidence import capture_reference_call_here\n"
            "print(json.dumps(capture_reference_call_here(Path(sys.argv[1]))))\n"
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
            return _failed("the bound process did not return an observation")
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            parsed = None
        if not isinstance(parsed, dict) or parsed.get("bind_now") is not True or parsed.get("pid") is None:
            return _failed("the bound observation was not from one LD_BIND_NOW process")
        return parsed
    return capture_reference_call_here(root)


def _failed(reason: str) -> dict[str, object]:
    return {
        "status": NOT_ESTABLISHED,
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
        "gaps": [reason],
        "dossier": {"status": NOT_ESTABLISHED, "preservation_established": False, "gaps": [reason]},
    }


def reference_call_document(root: Path) -> dict[str, object]:
    payload = capture_reference_call(root)
    return {
        "canonical_sha256": sha256_bytes(canonical_bytes(payload)),
        "digest_scope": (
            "SHA-256 of the section 7.3 canonical bytes of canonical_payload only. "
            "canonical_sha256 and digest_scope are outside that payload."
        ),
        "canonical_payload": payload,
    }
