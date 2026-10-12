"""Evidence for the call on one side of _Py_NewReference.

The slice reads loaded bytes in one LD_BIND_NOW process. It does not call
PyFloat_FromDouble, _Py_NewReference, or the callee. A push is not a restore.
A later store through a copied stack address replaces the saved slot. An ABI
name is not evidence that a callee preserves a register.
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


def _reads_rsp(insn: capstone.CsInsn) -> bool:
    try:
        reads, _written = insn.regs_access()
    except capstone.CsError:
        return True
    for reg in reads:
        width = _register_width(insn.reg_name(reg))
        if width is not None and width[0] == "rsp":
            return True
    return False


_AMBIGUOUS = "amb"
_MAX_ALIAS_REGISTERS = 16


def _alias_key(aliases: Mapping[str, object]) -> tuple[tuple[str, object], ...]:
    return tuple(sorted(aliases.items()))


def _rsp_level(slots: tuple[tuple[object, ...], ...]) -> int:
    return int(slots[-1][3]) if slots else 0


def _poison_slots(slots: tuple[tuple[object, ...], ...]) -> tuple[tuple[object, ...], ...]:
    return tuple((name, _OTHER, _AMBIGUOUS, level) for name, _value, _ptr, level in slots)


def _write_slot(
    slots: tuple[tuple[object, ...], ...],
    level: int,
    pointer: object,
) -> tuple[tuple[tuple[object, ...], ...], bool]:
    index = next((item for item, slot in enumerate(slots) if slot[3] == level), None)
    if index is None:
        return slots, False
    items = list(slots)
    name, _value, _ptr, slot_level = items[index]
    items[index] = (name, _OTHER, pointer, slot_level)
    return tuple(items), True


def _operand_width(insn: capstone.CsInsn, operand: object) -> tuple[str, int] | None:
    if getattr(operand, "type", None) != capstone.x86.X86_OP_REG:
        return None
    return _register_width(insn.reg_name(operand.reg))


def _plain_stack_pointer_copy(insn: capstone.CsInsn) -> bool:
    """A full copy or aligned lea of rsp. The walker tracks where it points."""
    operands = getattr(insn, "operands", ())
    if insn.mnemonic == "mov" and len(operands) == 2:
        dest = _operand_width(insn, operands[0])
        src = _operand_width(insn, operands[1])
        return bool(dest and src and dest[1] == 64 and src[1] == 64 and src[0] == "rsp" and dest[0] != "rsp")
    if insn.mnemonic == "lea" and len(operands) == 2 and not operands[1].mem.index:
        dest = _operand_width(insn, operands[0])
        base = _register_width(insn.reg_name(operands[1].mem.base) if operands[1].mem.base else None)
        return bool(
            dest
            and base
            and dest[1] == 64
            and base[0] == "rsp"
            and operands[1].type == capstone.x86.X86_OP_MEM
            and operands[1].mem.disp % 8 == 0
        )
    return False


def _unmodeled_stack(insn: capstone.CsInsn) -> bool:
    """A stack write or rsp change whose slot effect this walker does not track."""
    if _plain_stack_pointer_copy(insn):
        return False
    text = insn.op_str
    if "[" in text and any(name in text for name in ("rsp", "rbp", "esp", "ebp")):
        return True
    if insn.mnemonic in {"pushfq", "popfq", "enter", "leave"}:
        return True
    if insn.mnemonic == "pop":
        operand = _operand_register(insn)
        return operand is not None and operand[0] == "rsp"
    if insn.mnemonic in {"push", "call", "ret"}:
        return False
    if insn.mnemonic == "mov" and text == "rbp, rsp":
        return False
    if insn.mnemonic in {"add", "sub"} and text.startswith("rsp,"):
        return False
    written = _written_canonicals(insn)
    if written is not None and "rsp" in written:
        return True
    return _reads_rsp(insn)


def _read_canonicals(insn: capstone.CsInsn) -> set[str] | None:
    try:
        reads, _written = insn.regs_access()
    except capstone.CsError:
        return None
    canonical: set[str] = set()
    for reg in reads:
        width = _register_width(insn.reg_name(reg))
        if width is not None:
            canonical.add(width[0])
    return canonical


def _writes_memory(insn: capstone.CsInsn) -> bool:
    operands = getattr(insn, "operands", ())
    if insn.mnemonic in {"lea", "cmp", "test", "push"}:
        return False
    if not any(operand.type == capstone.x86.X86_OP_MEM for operand in operands):
        return False
    if insn.mnemonic in {"mov", "movzx", "movsx", "movsxd", "movabs"}:
        return bool(operands) and operands[0].type == capstone.x86.X86_OP_MEM
    return True


def _stored_pointer(insn: capstone.CsInsn, aliases: Mapping[str, object], slots: tuple[tuple[object, ...], ...]) -> object:
    """Pointer identity written by a full mov. Anything else can overlap a saved slot."""
    if insn.mnemonic != "mov":
        return _AMBIGUOUS
    operands = insn.operands
    if len(operands) < 2 or operands[0].type != capstone.x86.X86_OP_MEM:
        return _AMBIGUOUS
    source = operands[1]
    if source.type == capstone.x86.X86_OP_IMM:
        return None
    width = _operand_width(insn, source)
    if width is None or width[1] != 64:
        return _AMBIGUOUS
    if width[0] == "rsp":
        return _rsp_level(slots)
    if width[0] in aliases:
        return aliases[width[0]]
    return None


def _address_level(
    insn: capstone.CsInsn,
    operand: object,
    aliases: Mapping[str, object],
    slots: tuple[tuple[object, ...], ...],
) -> object:
    """Absolute stack level, ambiguous, or None when the address is not a tracked pointer."""
    base = _register_width(insn.reg_name(operand.mem.base) if operand.mem.base else None)
    index = _register_width(insn.reg_name(operand.mem.index) if operand.mem.index else None)
    if index is not None or base is None or operand.mem.disp % 8:
        if base is not None and (base[0] in aliases or base[0] == "rsp" or (index is not None and index[0] in aliases)):
            return _AMBIGUOUS
        return None
    if base[0] == "rsp":
        return _rsp_level(slots) - operand.mem.disp // 8
    if base[0] not in aliases:
        return None
    known = aliases[base[0]]
    if known == _AMBIGUOUS:
        return _AMBIGUOUS
    return int(known) - operand.mem.disp // 8


def _loaded_pointer(
    operand: object,
    insn: capstone.CsInsn,
    aliases: Mapping[str, object],
    slots: tuple[tuple[object, ...], ...],
) -> object:
    level = _address_level(insn, operand, aliases, slots)
    if level == _AMBIGUOUS:
        return _AMBIGUOUS
    if not isinstance(level, int):
        return "clear"
    slot = next((item for item in slots if item[3] == level), None)
    if slot is None or slot[2] is None:
        return "clear"
    return slot[2]


def _pointer_definitions(
    insn: capstone.CsInsn,
    aliases: Mapping[str, object],
    slots: tuple[tuple[object, ...], ...],
) -> dict[str, object] | None:
    """Supported copies of a stack address. None means an unsupported write."""
    operands = getattr(insn, "operands", ())
    if insn.mnemonic == "mov" and len(operands) == 2 and operands[0].type == capstone.x86.X86_OP_REG:
        dest = _operand_width(insn, operands[0])
        if dest is None or dest[0] == "rsp":
            return None
        source = operands[1]
        if source.type == capstone.x86.X86_OP_REG:
            src = _operand_width(insn, source)
            if src and src[0] == "rsp" and dest[1] == 64 and src[1] == 64:
                return {dest[0]: _rsp_level(slots)}
            if src and dest[1] == 64 and src[1] == 64:
                return {dest[0]: aliases[src[0]]} if src[0] in aliases else {dest[0]: "clear"}
            if src and (src[0] in aliases or src[0] == "rsp"):
                return {dest[0]: _AMBIGUOUS}
        if source.type == capstone.x86.X86_OP_IMM and dest[1] >= 32:
            return {dest[0]: "clear"}
        if source.type == capstone.x86.X86_OP_IMM and dest[0] in aliases:
            return {dest[0]: _AMBIGUOUS}
        if source.type == capstone.x86.X86_OP_MEM:
            loaded = _loaded_pointer(source, insn, aliases, slots)
            if isinstance(loaded, int) and dest[1] == 64:
                return {dest[0]: loaded}
            if loaded == "clear" and (dest[1] >= 32 or dest[0] not in aliases):
                return {dest[0]: "clear"}
            return {dest[0]: _AMBIGUOUS}
        if dest[0] in aliases and dest[1] == 32:
            return {dest[0]: "clear"}
        if dest[0] in aliases:
            return {dest[0]: _AMBIGUOUS}
        if dest[1] >= 32:
            return {dest[0]: "clear"}
        return {}
    if insn.mnemonic == "lea" and len(operands) == 2 and operands[0].type == capstone.x86.X86_OP_REG:
        dest = _operand_width(insn, operands[0])
        if dest is None or dest[1] != 64:
            return {dest[0]: _AMBIGUOUS} if dest is not None and dest[0] in aliases else {}
        mem = operands[1]
        if mem.type != capstone.x86.X86_OP_MEM:
            return {dest[0]: _AMBIGUOUS}
        base = _register_width(insn.reg_name(mem.mem.base) if mem.mem.base else None)
        index = _register_width(insn.reg_name(mem.mem.index) if mem.mem.index else None)
        if index is not None or base is None:
            return {dest[0]: _AMBIGUOUS}
        if mem.mem.disp % 8:
            return {dest[0]: _AMBIGUOUS}
        if base[0] == "rsp":
            return {dest[0]: _rsp_level(slots) - mem.mem.disp // 8}
        if base[0] not in aliases:
            return {dest[0]: "clear"}
        level = aliases[base[0]]
        if level == _AMBIGUOUS:
            return {dest[0]: _AMBIGUOUS}
        return {dest[0]: int(level) - mem.mem.disp // 8}
    if insn.mnemonic in {"add", "sub"} and len(operands) == 2 and operands[0].type == capstone.x86.X86_OP_REG:
        dest = _operand_width(insn, operands[0])
        source = _operand_width(insn, operands[1]) if operands[1].type == capstone.x86.X86_OP_REG else None
        source_is_pointer = source is not None and (source[0] in aliases or source[0] == "rsp")
        if dest is None:
            return None
        if dest[0] in aliases and operands[1].type == capstone.x86.X86_OP_IMM and dest[1] == 64 and operands[1].imm % 8 == 0:
            level = aliases[dest[0]]
            if level == _AMBIGUOUS:
                return {dest[0]: _AMBIGUOUS}
            delta = int(operands[1].imm) // 8
            return {dest[0]: int(level) + (delta if insn.mnemonic == "sub" else -delta)}
        if dest[0] in aliases or source_is_pointer:
            return None
        return {}
    if insn.mnemonic == "xor" and len(operands) == 2:
        dest = _operand_width(insn, operands[0])
        src = _operand_width(insn, operands[1])
        if dest and src and dest[0] == src[0] and dest[1] >= 32:
            return {dest[0]: "clear"}
        if (dest and dest[0] in aliases) or (src and (src[0] in aliases or src[0] == "rsp")):
            return None
        return {}
    return None


def _apply_alias_instruction(
    insn: capstone.CsInsn,
    aliases: Mapping[str, object],
    slots: tuple[tuple[object, ...], ...],
) -> tuple[dict[str, object], tuple[tuple[object, ...], ...]]:
    """Update saved slots and stack-address copies. Unsupported addresses poison every slot."""
    tracked = dict(aliases)
    updated = slots
    if _writes_memory(insn):
        for operand in insn.operands:
            if operand.type != capstone.x86.X86_OP_MEM:
                continue
            base = _register_width(insn.reg_name(operand.mem.base) if operand.mem.base else None)
            index = _register_width(insn.reg_name(operand.mem.index) if operand.mem.index else None)
            base_name = None if base is None else base[0]
            involved = base_name in tracked or base_name == "rsp" or (index is not None and index[0] in tracked)
            if not involved:
                continue
            if index is not None or base is None or operand.mem.disp % 8:
                updated = _poison_slots(updated)
                continue
            if base_name == "rsp":
                level = _rsp_level(updated) - operand.mem.disp // 8
            else:
                known = tracked[base_name]
                if known == _AMBIGUOUS:
                    updated = _poison_slots(updated)
                    continue
                level = int(known) - operand.mem.disp // 8
            if operand.size > 8:
                updated = _poison_slots(updated)
                continue
            pointer = _AMBIGUOUS if operand.size != 8 else _stored_pointer(insn, tracked, updated)
            updated, hit = _write_slot(updated, level, pointer)
            if not hit and pointer is not None:
                updated = _poison_slots(updated)
    defined = _pointer_definitions(insn, tracked, updated)
    written = _written_canonicals(insn)
    reads = _read_canonicals(insn)
    if defined is None or written is None or reads is None or len(tracked) > _MAX_ALIAS_REGISTERS:
        if written is None or reads is None or len(tracked) > _MAX_ALIAS_REGISTERS:
            for name in list(tracked):
                tracked[name] = _AMBIGUOUS
            return tracked, _poison_slots(updated)
        if any(name in tracked or name == "rsp" for name in reads):
            for name in written:
                tracked[name] = _AMBIGUOUS
            return tracked, updated
        for name in list(tracked):
            if name in written:
                tracked[name] = _AMBIGUOUS
        return tracked, updated
    for name, action in defined.items():
        if action == "clear":
            tracked.pop(name, None)
        else:
            tracked[name] = action
    for name in written:
        if name in tracked and name not in defined:
            tracked[name] = _AMBIGUOUS
    if len(tracked) > _MAX_ALIAS_REGISTERS:
        return {name: _AMBIGUOUS for name in tracked}, _poison_slots(updated)
    return tracked, updated


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

    A push records a stack slot. A later store can replace that slot, and a pop
    restores the slot's current contents. A copied stack address keeps its
    level across pushes. A call or an uncaptured branch leaves the path unresolved.
    The walk state is finite.
    """
    by_address = {insn.address: insn for insn in instructions}
    seen: set[tuple] = set()
    pending: list[tuple] = [(entry, _ENTRY, _ENTRY, (), (), False)]
    returns: list[dict[str, object]] = []
    unresolved: list[str] = []
    calls: list[dict[str, str]] = []
    pushes: list[dict[str, str]] = []
    pops: list[dict[str, str]] = []
    overwrites: list[dict[str, str]] = []
    budget_exhausted = False
    while pending:
        address, r14, rbx, slots, aliases, broken = pending.pop()
        key = (address, r14, rbx, slots, aliases, broken)
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
                # push rsp stores the address of the current top, before rsp moves.
                pointer = _rsp_level(slots) if saved == "rsp" else dict(aliases).get(saved)
                slots = slots + ((saved, values.get(saved, _OTHER), pointer, _rsp_level(slots) + 1),)
        elif insn.mnemonic == "leave":
            broken = True
        elif insn.mnemonic == "pop":
            operand = _operand_register(insn)
            if operand is None or operand[1] != 64 or broken or not slots or slots[-1][0] == "pad":
                broken = True
            else:
                restored = operand[0]
                saved_reg, saved_value, saved_ptr, _level = slots[-1]
                slots = slots[:-1]
                tracked = dict(aliases)
                if restored in values:
                    values[restored] = saved_value if saved_reg == restored else _OTHER
                if saved_ptr == _AMBIGUOUS:
                    tracked[restored] = _AMBIGUOUS
                elif isinstance(saved_ptr, int):
                    tracked[restored] = saved_ptr
                else:
                    tracked.pop(restored, None)
                aliases = _alias_key(tracked)
                restores_entry = restored in values and values[restored] == _ENTRY
                pops.append({"address": hex(insn.address), "register": restored, "restores_entry": restores_entry})
        elif insn.mnemonic in {"add", "sub"} and insn.op_str.startswith("rsp,"):
            delta = _adjust_rsp(insn)
            if delta is None or broken:
                broken = True
            elif delta > 0:
                level = _rsp_level(slots)
                slots = slots + tuple(("pad", _OTHER, None, level + step) for step in range(1, delta + 1))
            else:
                for _ in range(-delta):
                    if not slots:
                        broken = True
                        break
                    slots = slots[:-1]
        elif insn.mnemonic in {"mov", "lea"} and insn.op_str.startswith("rsp"):
            broken = True
        elif not broken and not insn.mnemonic.startswith("j") and insn.mnemonic not in {"call", "ret"}:
            tracked, slots = _apply_alias_instruction(insn, dict(aliases), slots)
            aliases = _alias_key(tracked)
        if broken:
            aliases = ()
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
            for reg in _TRACKED:
                values[reg] = _OTHER
            pending.append((insn.address + insn.size, values["r14"], values["rbx"], slots, (), True))
            continue
        if insn.mnemonic.startswith("j"):
            target = _direct_target(insn)
            if target is None:
                unresolved.append(hex(insn.address))
                broken = True
                aliases = ()
            else:
                pending.append((target, values["r14"], values["rbx"], slots, aliases, broken))
            if insn.mnemonic != "jmp":
                pending.append((insn.address + insn.size, values["r14"], values["rbx"], slots, () if broken else aliases, broken))
            continue
        pending.append((insn.address + insn.size, values["r14"], values["rbx"], slots, aliases, broken))
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
