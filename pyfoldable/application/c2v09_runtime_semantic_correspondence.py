"""Scoped argument for the three remaining pre-call semantic hypotheses.

Observations are loaded bytes, addresses and control state. A version label,
a sample output or a self-issued receipt does not establish them. This module
does not admit the hypotheses and does not call the evaluator, source, mapper,
partition, selection, seal or trajectory.
"""

from __future__ import annotations

import dis
import json
import math
import os
import struct
import subprocess
import sys
import threading
from pathlib import Path
from typing import Mapping

import capstone
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

from pyfoldable.application.c2v09_cosine_path_certificate import (
    PROBE_SOURCE,
    _c_function_address,
    _elf_bytes,
    _feature_record,
    _fegetround,
    _probe_words,
    _readable_process_bytes,
    _runtime_to_vaddr,
    _section,
    _symbol_text,
    _vaddr_to_runtime,
    observe_ulp_terminal_guard,
    plt_got_address,
)
from pyfoldable.application.c2v09_declared_operations import (
    ARITHMETIC_QUALNAMES,
    arithmetic_operation_record,
    resolve_qualname,
)
from pyfoldable.application.c2v09_ordered_declaration import (
    RUNTIME_BINDING_SHA256,
    TECHNICAL_HEAD,
    canonical_bytes,
    sha256_bytes,
)

ESTABLISHED_CONDITIONALLY = "ESTABLISHED CONDITIONALLY"
MISMATCHED = "MISMATCHED"
NOT_ESTABLISHED = "NOT ESTABLISHED"
_HYPOTHESES = (
    "interpreter binary64 arithmetic semantics",
    "PyFloat_AsDouble conversion semantics",
    "selected nextafter semantics",
)
_KIND_BY_OPCODE = {
    "BINARY_OP +": "add",
    "BINARY_ADD": "add",
    "BINARY_OP -": "sub",
    "BINARY_SUBTRACT": "sub",
    "BINARY_OP *": "mul",
    "BINARY_MULTIPLY": "mul",
    "BINARY_OP /": "div",
    "BINARY_TRUE_DIVIDE": "div",
}
_KIND_BY_MNEMONIC = {
    "addsd": "add",
    "vaddsd": "add",
    "subsd": "sub",
    "vsubsd": "sub",
    "mulsd": "mul",
    "vmulsd": "mul",
    "divsd": "div",
    "vdivsd": "div",
}
_SCALAR = frozenset(_KIND_BY_MNEMONIC)
_SLOT_INDEX = {"add": 0, "sub": 1, "mul": 2, "div": 30}
_CONVERT = frozenset({"cvtsi2sd", "vcvtsi2sd", "cvtss2sd", "vcvtss2sd", "cvtsd2ss", "vcvtsd2ss"})


def _thread_id() -> str:
    native = getattr(threading, "get_native_id", None)
    return str(native() if native is not None else threading.get_ident())


def _decoder() -> Cs:
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = False
    return decoder


def _disassemble(blob: bytes, base: int) -> list[capstone.CsInsn]:
    return list(_decoder().disasm(blob, base))


def _is_fma(mnemonic: str) -> bool:
    return mnemonic.startswith(("vfmadd", "vfnmadd", "vfmsub", "vfnmsub"))


def _defined_symbol(path: str, symbol: str) -> tuple[int, int] | None:
    data = Path(path).read_bytes()
    symbols = _section(data, ".dynsym")
    strings = _section(data, ".dynstr")
    if symbols is None or strings is None or symbols[9] != 24:
        return None
    for index in range(symbols[5] // 24):
        name_index, _info, _other, section, value, size = struct.unpack_from("<IBBHQQ", data, symbols[4] + index * 24)
        if section != 0 and value and _symbol_text(data, strings, name_index) == symbol:
            return int(value), int(size)
    return None


def _image_of(address: int) -> str | None:
    located = _runtime_to_vaddr(address)
    if located is None:
        return None
    return located[0]


def _symbol_runtime(path: str, symbol: str) -> tuple[int, int, int] | None:
    defined = _defined_symbol(path, symbol)
    if defined is None:
        return None
    vaddr, size = defined
    runtime = _vaddr_to_runtime(path, vaddr)
    if runtime is None or size <= 0:
        return None
    return runtime, vaddr, size


def _one_scalar_per_path(instructions: list[capstone.CsInsn]) -> bool | None:
    """True when no path from the entry executes two scalar binary64 operations."""
    if not instructions:
        return None
    by_address = {insn.address: index for index, insn in enumerate(instructions)}
    scalar = {index for index, insn in enumerate(instructions) if insn.mnemonic in _SCALAR}
    successors: dict[int, list[int]] = {}

    def _add(origin: int, target: int) -> bool:
        if target not in by_address:
            return False
        successors.setdefault(origin, []).append(by_address[target])
        return True

    for index, insn in enumerate(instructions):
        mnemonic = insn.mnemonic
        next_address = insn.address + insn.size
        if mnemonic == "ret":
            continue
        if mnemonic == "jmp":
            if not insn.op_str.startswith("0x"):
                return None
            _add(index, int(insn.op_str, 16))
            continue
        if mnemonic.startswith("j") and mnemonic != "jmp":
            if not insn.op_str.startswith("0x"):
                return None
            _add(index, int(insn.op_str, 16))
        if next_address in by_address:
            successors.setdefault(index, []).append(by_address[next_address])
    seen: set[tuple[int, int]] = set()
    stack = [(0, 0)]
    while stack:
        node, count = stack.pop()
        if (node, count) in seen:
            continue
        seen.add((node, count))
        next_count = count + (1 if node in scalar else 0)
        if next_count > 1:
            return False
        for successor in successors.get(node, []):
            stack.append((successor, next_count))
    return True


def _cut_at_next_function(instructions: list[capstone.CsInsn]) -> list[capstone.CsInsn]:
    for index, insn in enumerate(instructions):
        if index and insn.mnemonic == "endbr64":
            return instructions[:index]
    return instructions


_COPY_MNEMONICS = frozenset({"movsd", "movapd", "movaps", "movq", "movdqa"})
_VOLATILE = frozenset({"rax", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11"})
_GPR64 = (
    "rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi",
    "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15",
)
_GPR32 = (
    "eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi",
    "r8d", "r9d", "r10d", "r11d", "r12d", "r13d", "r14d", "r15d",
)
_GPR16 = (
    "ax", "cx", "dx", "bx", "sp", "bp", "si", "di",
    "r8w", "r9w", "r10w", "r11w", "r12w", "r13w", "r14w", "r15w",
)
_GPR8 = (
    "al", "cl", "dl", "bl", "spl", "bpl", "sil", "dil",
    "r8b", "r9b", "r10b", "r11b", "r12b", "r13b", "r14b", "r15b",
)
_REGISTER_WIDTH: dict[str, tuple[str, int]] = {}
for _index, _name in enumerate(_GPR64):
    _REGISTER_WIDTH[_name] = (_name, 64)
    _REGISTER_WIDTH[_GPR32[_index]] = (_name, 32)
    _REGISTER_WIDTH[_GPR16[_index]] = (_name, 16)
    _REGISTER_WIDTH[_GPR8[_index]] = (_name, 8)
for _name, _canonical in (("ah", "rax"), ("ch", "rcx"), ("dh", "rdx"), ("bh", "rbx")):
    _REGISTER_WIDTH[_name] = (_canonical, 8)
_REGISTER_ALIASES = {name: canonical for name, (canonical, _width) in _REGISTER_WIDTH.items()}


def _split_operand(op_str: str) -> tuple[str, str | None]:
    if "," not in op_str:
        return op_str.strip(), None
    dest, src = op_str.split(",", 1)
    return dest.strip(), src.strip()


def _leading_register(operand: str | None) -> str | None:
    if operand is None or not operand:
        return None
    if "[" in operand or operand.startswith(("qword", "dword", "word", "byte", "xmmword")):
        return None
    return operand.split()[0]


def _canonical_register(name: str | None) -> str | None:
    if name is None:
        return None
    return _REGISTER_ALIASES.get(name, name)


def _register_width(name: str | None) -> tuple[str, int] | None:
    """Canonical register and the width of this access. Aliasing does not widen a partial write."""
    if name is None:
        return None
    if name.startswith("xmm") and name[3:].isdigit():
        return name, 64
    return _REGISTER_WIDTH.get(name)


def _operand_tokens(op_str: str) -> set[str]:
    return {token.strip() for token in op_str.replace(",", " ").split() if token.strip()}


def _direct_target(insn: capstone.CsInsn) -> int | None:
    if not insn.op_str.startswith("0x"):
        return None
    return int(insn.op_str, 16)


def _scalar_dest(insn: capstone.CsInsn) -> str | None:
    dest, _src = _split_operand(insn.op_str)
    register = _canonical_register(_leading_register(dest))
    if register is not None and register.startswith("xmm"):
        return register
    return None


def _apply_transfer(registers: frozenset[str], insn: capstone.CsInsn) -> frozenset[str]:
    """Copy a full binary64 result. A 32, 16, or 8-bit transfer does not preserve it."""
    current = set(registers)
    dest_text, src_text = _split_operand(insn.op_str)
    dest = _register_width(_leading_register(dest_text))
    src = _register_width(_leading_register(src_text))
    full_copy = False
    if (
        dest is not None
        and src is not None
        and dest[1] == 64
        and src[1] == 64
        and src[0] in current
        and "[" not in dest_text
    ):
        if insn.mnemonic in _COPY_MNEMONICS or insn.mnemonic == "mov":
            current.add(dest[0])
            full_copy = True
    if insn.mnemonic == "xchg" and dest is not None and src is not None and dest[1] == 64 and src[1] == 64:
        dest_had = dest[0] in current
        src_had = src[0] in current
        if src_had:
            current.add(dest[0])
        else:
            current.discard(dest[0])
        if dest_had:
            current.add(src[0])
        else:
            current.discard(src[0])
        full_copy = True
    elif insn.mnemonic in {"xchg", "xadd"}:
        if dest is not None:
            current.discard(dest[0])
        if src is not None:
            current.discard(src[0])
        full_copy = True
    if (
        dest is not None
        and not full_copy
        and not insn.mnemonic.startswith("j")
        and insn.mnemonic not in {"cmp", "test", "ucomisd", "comisd", "vucomisd", "vcomisd"}
    ):
        current.discard(dest[0])
    if insn.mnemonic == "call":
        current = {name for name in current if not name.startswith("xmm") and name not in _VOLATILE}
    return frozenset(current)


def _slot_store(insn: capstone.CsInsn) -> bool:
    dest_text, src_text = _split_operand(insn.op_str)
    return "+ 0x10]" in dest_text and "[" in dest_text and src_text is not None


def _stores_tracked(insn: capstone.CsInsn, registers: frozenset[str] | set[str]) -> bool:
    """A result store writes the full low 64 bits. A high-half or 32-bit write does not."""
    if not _slot_store(insn) or insn.mnemonic not in {"movsd", "movq", "movlpd", "mov"}:
        return False
    dest_text, src_text = _split_operand(insn.op_str)
    if insn.mnemonic == "mov" and not dest_text.startswith("qword"):
        return False
    source = _register_width(_leading_register(src_text))
    return source is not None and source[1] == 64 and source[0] in registers


def _store_reaches_return(
    instructions: list[capstone.CsInsn],
    entry: int,
    initial: frozenset[str],
) -> bool:
    """The finite path stores the tracked bits and returns, with no open exit."""
    if not instructions:
        return False
    by_address = {insn.address: index for index, insn in enumerate(instructions)}
    if entry not in by_address:
        return False
    inside = set(by_address)
    completed = False
    seen: set[tuple[int, tuple[str, ...], bool]] = set()
    stack: list[tuple[int, frozenset[str], bool]] = [(by_address[entry], initial, False)]
    while stack:
        index, registers, stored = stack.pop()
        state = (index, tuple(sorted(registers)), stored)
        if state in seen:
            continue
        seen.add(state)
        insn = instructions[index]
        next_registers = _apply_transfer(registers, insn)
        if _slot_store(insn):
            next_stored = _stores_tracked(insn, next_registers)
        else:
            next_stored = stored
        next_address = insn.address + insn.size
        if insn.mnemonic == "ret":
            if next_stored:
                completed = True
                continue
            return False
        exits: list[int | None] = []
        if insn.mnemonic == "jmp" or (insn.mnemonic.startswith("j") and insn.mnemonic != "jmp"):
            target = _direct_target(insn)
            if target not in inside:
                return False
            exits.append(target)
            if insn.mnemonic != "jmp":
                exits.append(next_address if next_address in inside else None)
        elif insn.mnemonic == "call":
            exits.append(next_address if next_address in inside else None)
        else:
            exits.append(next_address if next_address in inside else None)
        for target in exits:
            if target is None:
                return False
            stack.append((by_address[target], next_registers, next_stored))
    return completed


def _store_kind(
    instructions: list[capstone.CsInsn],
    from_double: int | None,
    from_double_end: int | None = None,
) -> str:
    reaches_from = False
    inplace = False
    bit_store = False
    registers: frozenset[str] = frozenset()
    seen_scalar = False
    end = from_double + 1 if from_double is not None and from_double_end is None else from_double_end
    for insn in instructions:
        incoming = registers
        if insn.mnemonic in _SCALAR:
            dest = _scalar_dest(insn)
            registers = frozenset({dest}) if dest is not None else frozenset()
            seen_scalar = True
            continue
        registers = _apply_transfer(registers, insn)
        if not seen_scalar:
            continue
        if _stores_tracked(insn, registers):
            if insn.mnemonic == "movsd":
                inplace = True
            else:
                bit_store = True
        target = _direct_target(insn)
        if (
            insn.mnemonic in {"call", "jmp"}
            and target is not None
            and from_double is not None
            and end is not None
            and from_double <= target < end
            and "xmm0" in incoming
        ):
            reaches_from = True
    if reaches_from and (inplace or bit_store):
        return "in-place ob_fval or PyFloat_FromDouble"
    if reaches_from:
        return "PyFloat_FromDouble"
    if inplace or bit_store:
        return "ob_fval"
    return "not traced"


def _handler_from_bytes(
    kind: str,
    blob: bytes,
    base: int,
    *,
    file_match: bool,
    elf_vaddr: int | None,
    image: str,
    from_double: int | None,
    from_double_end: int | None = None,
) -> dict[str, object]:
    instructions = _cut_at_next_function(_disassemble(blob, base))
    scalar = [insn.mnemonic for insn in instructions if insn.mnemonic in _SCALAR]
    fma = [insn.mnemonic for insn in instructions if _is_fma(insn.mnemonic)]
    loads_ob_fval = any(insn.mnemonic == "movsd" and "+ 0x10]" in insn.op_str for insn in instructions)
    one_path = _one_scalar_per_path(instructions) if instructions else None
    return {
        "kind": kind,
        "address": hex(base),
        "elf_vaddr": None if elf_vaddr is None else hex(elf_vaddr),
        "image": image,
        "loaded_bytes_hex": blob.hex(),
        "loaded_bytes_match_file": file_match,
        "scalar_mnemonics": scalar,
        "paths_execute_one_scalar_op": one_path,
        "fma_mnemonics": fma,
        "store": _store_kind(instructions, from_double, from_double_end),
        "ob_fval_load": loads_ob_fval,
        "from_double_address": None if from_double is None else hex(from_double),
        "from_double_end": None if from_double_end is None else hex(from_double_end),
        "decoder": "capstone",
        "decoder_version": capstone.__version__,
        "mode": "64-bit",
        "coverage": "complete" if instructions and one_path is not None else "unsupported",
    }


def _float_slots(image: str) -> tuple[dict[str, int], tuple[int, int] | None] | None:
    defined = _defined_symbol(image, "PyFloat_Type")
    from_double = _symbol_runtime(image, "PyFloat_FromDouble")
    if defined is None:
        return None
    runtime = _vaddr_to_runtime(image, defined[0])
    if runtime is None:
        return None
    header = _readable_process_bytes(runtime, 0x70)
    if header is None or len(header) < 0x68:
        return None
    name_ptr = struct.unpack_from("<Q", header, 0x18)[0]
    basicsize = struct.unpack_from("<Q", header, 0x20)[0]
    name = _readable_process_bytes(name_ptr, 6)
    if name != b"float\x00" or basicsize != 24:
        return None
    number = struct.unpack_from("<Q", header, 0x60)[0]
    slots = _readable_process_bytes(number, 31 * 8)
    if slots is None:
        return None
    found = {kind: struct.unpack_from("<Q", slots, index * 8)[0] for kind, index in _SLOT_INDEX.items()}
    if any(address == 0 for address in found.values()):
        return None
    return found, None if from_double is None else (from_double[0], from_double[0] + from_double[2])


def _capture_generic_handlers(image: str) -> dict[str, dict[str, object]]:
    located = _float_slots(image)
    if located is None:
        return {}
    slots, from_double_range = located
    from_double = None if from_double_range is None else from_double_range[0]
    from_double_end = None if from_double_range is None else from_double_range[1]
    anchors = [address for address in slots.values() if address]
    if from_double is not None:
        anchors.append(from_double)
    handlers: dict[str, dict[str, object]] = {}
    for kind, address in slots.items():
        higher = [item for item in anchors if item > address]
        length = min(0x240, min(higher) - address) if higher else 0x240
        blob = _complete_slice(address, length)
        if blob is None:
            continue
        mapped = _runtime_to_vaddr(address)
        elf_vaddr = None if mapped is None else mapped[1]
        file_bytes = None if mapped is None else _elf_bytes(mapped[0], mapped[1], len(blob))
        handlers[kind] = _handler_from_bytes(
            kind,
            blob,
            address,
            file_match=file_bytes == blob,
            elf_vaddr=elf_vaddr,
            image=image,
            from_double=from_double,
            from_double_end=from_double_end,
        )
        _attach_continuations(handlers[kind])
    return handlers


def _attach_continuations(handler: dict[str, object]) -> None:
    instructions = _handler_instructions(handler)
    if not instructions:
        return
    inside = {insn.address for insn in instructions}
    rows = []
    seen: set[int] = set()
    for insn in instructions:
        if not insn.op_str.startswith("0x"):
            continue
        if insn.mnemonic not in {"call", "jmp"} and not insn.mnemonic.startswith("j"):
            continue
        target = int(insn.op_str, 16)
        if target in inside or target in seen:
            continue
        seen.add(target)
        blob = _continuation_prefix(target)
        if blob is None:
            continue
        rows.append({"address": hex(target), "loaded_bytes_hex": blob.hex()})
    if rows:
        handler["continuations"] = rows


def _follows_from_double(instructions: list[capstone.CsInsn], index: int, from_double: int) -> bool:
    by_address = {insn.address: position for position, insn in enumerate(instructions)}
    window = instructions[index + 1:index + 16]
    for insn in window:
        if insn.mnemonic in _SCALAR or _is_fma(insn.mnemonic):
            return False
        if insn.mnemonic in {"call", "jmp"} and insn.op_str.startswith("0x") and int(insn.op_str, 16) == from_double:
            return True
        if insn.mnemonic == "jne" and insn.op_str.startswith("0x"):
            target = by_address.get(int(insn.op_str, 16))
            if target is None:
                continue
            for follow in instructions[target:target + 8]:
                if follow.mnemonic in _SCALAR or _is_fma(follow.mnemonic):
                    break
                if follow.mnemonic in {"call", "jmp"} and follow.op_str.startswith("0x") and int(follow.op_str, 16) == from_double:
                    return True
    return False


def _capture_specialized_handlers(
    image: str,
    from_double: int | None,
    from_double_end: int | None = None,
) -> tuple[dict[str, list[dict[str, object]]], str, int]:
    defined = _symbol_runtime(image, "_PyEval_EvalFrameDefault")
    if defined is None or from_double is None:
        return {}, "unavailable", 0
    runtime, vaddr, size = defined
    blob = _readable_process_bytes(runtime, size)
    file_bytes = _elf_bytes(image, vaddr, size)
    if blob is None or file_bytes != blob:
        return {}, "unavailable", 0
    instructions = _disassemble(blob, runtime)
    if not instructions or instructions[-1].address + instructions[-1].size - runtime != len(blob):
        return {}, "unavailable", 0
    dispatch_at = _dispatch_addresses(instructions)
    type_defined = _defined_symbol(image, "PyFloat_Type")
    type_runtime = None if type_defined is None else _vaddr_to_runtime(image, type_defined[0])
    grouped: dict[str, list[dict[str, object]]] = {"add": [], "sub": [], "mul": [], "div": []}
    unclassified = 0
    for index, insn in enumerate(instructions):
        if insn.mnemonic not in _SCALAR:
            continue
        before = instructions[max(0, index - 16):index]
        after = instructions[index + 1:index + 16]
        loaded = any(item.mnemonic == "movsd" and "+ 0x10]" in item.op_str for item in before)
        checked = any(item.mnemonic == "cmp" for item in before)
        inplace = any(item.mnemonic == "movsd" and "+ 0x10]" in item.op_str and item.op_str.endswith(", xmm0") for item in after)
        stored = inplace or _follows_from_double(instructions, index, from_double)
        checked_before = before[-8:]
        checked_after = after[:8]
        fused = any(_is_fma(item.mnemonic) or item.mnemonic in _SCALAR for item in checked_before + checked_after)
        if not loaded or not checked or not stored or fused:
            unclassified += 1
            continue
        kind = _KIND_BY_MNEMONIC[insn.mnemonic]
        start = checked_before[0].address if checked_before else insn.address
        stop = (checked_after[-1].address + checked_after[-1].size) if checked_after else insn.address + insn.size
        for follow in instructions[index:index + 48]:
            if follow.address in dispatch_at and follow.address + follow.size <= insn.address + 0x90:
                stop = max(stop, follow.address + follow.size)
                break
        window = _readable_process_bytes(start, stop - start)
        window_vaddr = vaddr + (start - runtime)
        file_window = None if window is None else _elf_bytes(image, window_vaddr, len(window))
        grouped[kind].append(
            {
                "kind": kind,
                "address": hex(start),
                "scalar_address": hex(insn.address),
                "elf_vaddr": hex(window_vaddr),
                "image": image,
                "loaded_bytes_hex": None if window is None else window.hex(),
                "loaded_bytes_match_file": window is not None and file_window == window,
                "scalar_mnemonics": [insn.mnemonic],
                "paths_execute_one_scalar_op": True,
                "fma_mnemonics": [],
                "store": _store_kind(checked_before + [insn] + checked_after, from_double, from_double_end),
                "ob_fval_load": True,
                "from_double_address": None if from_double is None else hex(from_double),
                "from_double_end": None if from_double_end is None else hex(from_double_end),
                "decoder": "capstone",
                "decoder_version": capstone.__version__,
                "mode": "64-bit",
                "coverage": "complete",
                "completion": "next_opcode_dispatch" if any(start <= address < stop for address in dispatch_at) else "return",
                "float_type_address": None if type_runtime is None else hex(type_runtime),
            }
        )
        _attach_continuations(grouped[kind][-1])
        if grouped[kind][-1].get("completion") != "next_opcode_dispatch":
            for _address, continuation in _decoded_continuations(grouped[kind][-1]):
                if _dispatch_addresses(continuation):
                    grouped[kind][-1]["completion"] = "next_opcode_dispatch"
                    break
    return grouped, "complete", unclassified


def _operand_category(left: str, right: str, kind: str) -> str:
    pair = {left, right}
    if kind == "add" and pair == {"LOAD_FAST index", "LOAD_CONST 1"}:
        return "integer_add"
    if kind == "mul" and "LOAD_FAST width" in pair and (
        "LOAD_FAST index" in pair or left.startswith("result:integer_add")
    ):
        return "mixed_integer_float_multiply"
    if kind == "div" and "LOAD_ATTR annulus_count" in pair:
        return "mixed_float_integer_divide"
    return "float_float"


def _categories_for(opcodes: list[str]) -> tuple[list[str], list[str]]:
    stack: list[str] = []
    kinds: list[str] = []
    categories: list[str] = []
    for text in opcodes:
        if text.startswith("LOAD_"):
            stack.append(text)
            continue
        kind = _KIND_BY_OPCODE.get(text)
        if kind is None:
            if text.startswith("STORE_") and stack:
                stack.pop()
            continue
        right = stack.pop() if stack else ""
        left = stack.pop() if stack else ""
        category = _operand_category(left, right, kind)
        kinds.append(kind)
        categories.append(category)
        stack.append(f"result:{category}")
    return kinds, categories


def _capture_operations() -> list[dict[str, object]]:
    rows = []
    for qualname in ARITHMETIC_QUALNAMES:
        record = arithmetic_operation_record(qualname)
        opcodes = record.get("opcodes")
        if not isinstance(opcodes, list):
            opcodes = []
        texts = [text for text in opcodes if isinstance(text, str)]
        kinds, categories = _categories_for(texts)
        rows.append(
            {
                "qualname": qualname,
                "opcodes": texts,
                "kinds": kinds,
                "categories": categories,
                "bytecode_window_establishes_semantics": False,
                "output_sampled": False,
            }
        )
    rows.extend(_width_division_operation())
    return rows


def _width_division_operation() -> list[dict[str, object]]:
    resolved = resolve_qualname("solve_bem_rotor")
    if resolved is None:
        return []
    instructions = list(dis.get_instructions(resolved.code))
    start = None
    opcodes: list[str] = []
    for instruction in instructions:
        text = instruction.opname if not instruction.argrepr else f"{instruction.opname} {instruction.argrepr}"
        if start is None and text == "LOAD_FAST outer_radius":
            start = instruction.offset
        if start is None:
            continue
        opcodes.append(text)
        if text == "STORE_FAST width":
            break
    kinds, categories = _categories_for(opcodes)
    if "mixed_float_integer_divide" not in categories:
        return []
    return [
        {
            "qualname": "solve_bem_rotor.width",
            "opcodes": opcodes,
            "kinds": kinds,
            "categories": categories,
            "bytecode_window_establishes_semantics": False,
            "output_sampled": False,
        }
    ]


def _declared_annulus_count(root: Path) -> int | None:
    path = root / "docs/cmm2_c2v09_candidate29_proposal.md"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    marker = "```json\n"
    if marker not in text:
        return None
    body = text.split(marker, 1)[1].split("```", 1)[0]
    try:
        document = json.loads(body)
    except json.JSONDecodeError:
        return None
    binding = document.get("effective_binding") if isinstance(document, dict) else None
    settings = binding.get("bem_settings") if isinstance(binding, dict) else None
    value = settings.get("annulus_count") if isinstance(settings, dict) else None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 2:
        return value
    return None


def _fast_path(instructions: list[capstone.CsInsn]) -> tuple[bool, bool]:
    """A builtin-float return loads ob_fval and returns through a short epilogue."""
    for index, insn in enumerate(instructions):
        if insn.mnemonic != "movsd" or "+ 0x10]" not in insn.op_str or not insn.op_str.startswith("xmm"):
            continue
        for follow in instructions[index + 1:index + 8]:
            if follow.mnemonic in _CONVERT or follow.mnemonic in _SCALAR or follow.mnemonic in {"call", "jmp"}:
                break
            if follow.mnemonic == "ret":
                return True, True
            if follow.mnemonic not in {"add", "pop"}:
                break
    return False, False


def _capture_conversion(image: str, wrapper: int) -> dict[str, object]:
    defined = _symbol_runtime(image, "PyFloat_AsDouble")
    from_double = _symbol_runtime(image, "PyFloat_FromDouble")
    empty = {
        "wrapper_calls_defined_symbol": False,
        "loaded_bytes_match_file": False,
        "builtin_float_path": None,
        "fast_path_has_no_convert": False,
        "finite_result_store": "not traced",
        "non_float_paths_are_not_the_builtin_argument": False,
    }
    if defined is None or wrapper <= 0:
        return empty
    runtime, vaddr, size = defined
    blob = _readable_process_bytes(runtime, size)
    file_bytes = _elf_bytes(image, vaddr, size)
    wrapper_blob = _complete_slice(wrapper, 0x180)
    if blob is None or wrapper_blob is None or file_bytes != blob:
        return empty
    wrapper_ins = _disassemble(wrapper_blob, wrapper)
    calls_symbol = any(
        insn.mnemonic == "call" and insn.op_str.startswith("0x") and int(insn.op_str, 16) == runtime
        for insn in wrapper_ins
    )
    stores = "not traced"
    if from_double is not None and any(
        insn.mnemonic in {"call", "jmp"} and insn.op_str.startswith("0x") and int(insn.op_str, 16) == from_double[0]
        for insn in wrapper_ins
    ):
        stores = "PyFloat_FromDouble"
    instructions = _disassemble(blob, runtime)
    fast, clean = _fast_path(instructions)
    calls = [insn for insn in instructions if insn.mnemonic == "call"]
    from_blob = None if from_double is None else _readable_process_bytes(from_double[0], from_double[2])
    from_file = None
    if from_double is not None and from_blob is not None:
        from_file = _elf_bytes(image, from_double[1], len(from_blob))
    return {
        "wrapper_calls_defined_symbol": calls_symbol,
        "loaded_bytes_match_file": True,
        "wrapper_address": hex(wrapper),
        "wrapper_bytes_hex": wrapper_blob.hex(),
        "asdouble_address": hex(runtime),
        "asdouble_bytes_hex": blob.hex(),
        "fromdouble_address": None if from_double is None else hex(from_double[0]),
        "fromdouble_end": None if from_double is None else hex(from_double[0] + from_double[2]),
        "fromdouble_bytes_hex": None if from_blob is None or from_file != from_blob else from_blob.hex(),
        "symbol_address": hex(runtime),
        "elf_vaddr": hex(vaddr),
        "loaded_bytes_hex": blob.hex(),
        "builtin_float_path": "movsd [obj+0x10]; ret" if fast else None,
        "fast_path_has_no_convert": fast and clean,
        "finite_result_store": stores,
        "non_float_paths_are_not_the_builtin_argument": fast and bool(calls),
        "decoder": "capstone",
        "decoder_version": capstone.__version__,
        "mode": "64-bit",
    }


def _capture_terminal_guard(image: str) -> dict[str, object]:
    observed = observe_ulp_terminal_guard()
    record: dict[str, object] = {
        "ulp_function_calls": observed.get("ulp_function_calls"),
        "nextafter_function_calls": observed.get("nextafter_function_calls"),
        "output_sampled": observed.get("output_sampled"),
        "wrapper_matches_file": observed.get("loaded_wrapper_matches_file") is True,
        "wrapper_calls_nextafter_plt": any(
            isinstance(edge, Mapping) and edge.get("symbol") == "nextafter" and edge.get("loaded_bytes_match_file") is True
            for edge in observed.get("call_edges") or []
        ),
        "got_slot": observed.get("got_slot"),
        "got_resolved": False,
        "selected_body_bound": False,
        "integer_increment_in_selected_body": None,
        "wrapper_subtraction": None,
        "unchanged_guard_ulps": 2,
        "allowance_recomputed": False,
        "independent_symbol_establishes_selected_path": False,
        "selected_address": observed.get("selected_address"),
        "evidence": observed.get("evidence"),
    }
    wrapper = observed.get("wrapper_address")
    blob = observed.get("loaded_wrapper_bytes_hex")
    if isinstance(wrapper, str) and isinstance(blob, str) and blob:
        instructions = _disassemble(bytes.fromhex(blob), int(wrapper, 16))
        if any(insn.mnemonic == "subsd" for insn in instructions):
            record["wrapper_subtraction"] = "subsd"
    got = observed.get("got_slot")
    if isinstance(got, str):
        try:
            slot = int(got, 16)
        except ValueError:
            slot = 0
        qword_blob = _readable_process_bytes(slot, 8) if slot else None
        qword = None if qword_blob is None else struct.unpack("<Q", qword_blob)[0]
        edges = observed.get("call_edges")
        target = None
        if isinstance(edges, list) and edges and isinstance(edges[0], Mapping) and isinstance(edges[0].get("target"), str):
            target = int(str(edges[0]["target"]), 16)
        stub = _readable_process_bytes(target, 16) if target is not None else None
        if target is not None and stub is not None:
            record["plt_address"] = hex(target)
            record["plt_stub_bytes_hex"] = stub.hex()
        if qword_blob is not None:
            record["got_qword_hex"] = qword_blob.hex()
        resolved = (
            qword is not None
            and target is not None
            and stub is not None
            and nextafter_got_resolved(target, qword, stub)
        )
        record["got_resolved"] = resolved
        if resolved and qword is not None:
            body = _readable_process_bytes(qword, 0x180)
            mapped = _runtime_to_vaddr(qword)
            file_bytes = None if mapped is None or body is None else _elf_bytes(mapped[0], mapped[1], len(body))
            if body is not None and file_bytes == body:
                instructions = _cut_at_next_function(_disassemble(body, qword))
                increment = any(
                    insn.mnemonic in {"add", "lea"} and insn.op_str.endswith(", 1")
                    for insn in instructions
                ) or any(insn.mnemonic == "inc" for insn in instructions)
                record["selected_body_bound"] = True
                record["integer_increment_in_selected_body"] = increment
                record["selected_body_bytes_hex"] = body.hex()
                record["selected_address"] = hex(qword)
    _ = image
    return record


def _continuation_prefix(address: int) -> bytes | None:
    """Bytes through the first return or direct jump. A truncated tail is not included."""
    blob = _readable_process_bytes(address, 0x60)
    if blob is None:
        return None
    instructions = list(_decoder().disasm(blob, address))
    end = None
    for index, insn in enumerate(instructions):
        if insn.mnemonic == "ret" or (insn.mnemonic == "jmp" and insn.op_str.startswith("0x")):
            end = insn.address + insn.size
            break
        if insn.mnemonic == "jmp" and insn.address in _dispatch_addresses(instructions[: index + 1]):
            end = insn.address + insn.size
            break
    if end is None:
        return None
    claimed = blob[: end - address]
    if _decode_complete(claimed, address) is None:
        return None
    return claimed


def _complete_slice(address: int, size: int) -> bytes | None:
    blob = _readable_process_bytes(address, size)
    if blob is None:
        return None
    instructions = list(_decoder().disasm(blob, address))
    if not instructions:
        return None
    end = instructions[-1].address + instructions[-1].size
    for insn in instructions:
        if insn.address > address and insn.mnemonic == "endbr64":
            end = insn.address
            break
    if end <= address or end - address > len(blob):
        return None
    claimed = blob[: end - address]
    if _decode_complete(claimed, address) is None:
        return None
    return claimed


def _capture_integer_add(image: str, declared: int | None) -> dict[str, object]:
    defined = _defined_symbol(image, "PyLong_Type")
    if defined is None or declared is None:
        return {}
    runtime = _vaddr_to_runtime(image, defined[0])
    header = None if runtime is None else _readable_process_bytes(runtime, 0x70)
    if header is None or _readable_process_bytes(struct.unpack_from("<Q", header, 0x18)[0], 4) != b"int\x00":
        return {}
    number = struct.unpack_from("<Q", header, 0x60)[0]
    slots = _readable_process_bytes(number, 8)
    if slots is None:
        return {}
    address = struct.unpack_from("<Q", slots, 0)[0]
    blob = _complete_slice(address, 0x180)
    if blob is None:
        return {}
    mapped = _runtime_to_vaddr(address)
    file_bytes = None if mapped is None else _elf_bytes(mapped[0], mapped[1], len(blob))
    return {
        "address": hex(address),
        "loaded_bytes_hex": blob.hex(),
        "loaded_bytes_match_file": file_bytes == blob,
        "type_address": hex(runtime),
        "slot_index": 0,
        "slot_target": hex(address),
        "declared_annulus_count": declared,
    }


def capture_bound_nextafter() -> dict[str, object]:
    """Read the already-bound PLT slot. Do not call math.ulp or nextafter."""
    wrapper = _c_function_address(math.ulp)
    image = "" if wrapper is None else (_image_of(wrapper) or "")
    guard = _capture_terminal_guard(image)
    guard["bind_now"] = os.environ.get("LD_BIND_NOW") == "1"
    guard["ulp_function_calls"] = 0
    guard["nextafter_function_calls"] = 0
    guard["output_sampled"] = False
    guard["unchanged_guard_ulps"] = 2
    guard["allowance_recomputed"] = False
    guard["independent_symbol_establishes_selected_path"] = False
    if wrapper is not None:
        wrapper_bytes = _complete_slice(wrapper, 0x180)
        if wrapper_bytes is not None:
            guard["wrapper_address"] = hex(wrapper)
            guard["wrapper_bytes_hex"] = wrapper_bytes.hex()
    selected = _hex_int(guard.get("selected_address"))
    if selected is not None:
        body = _complete_slice(selected, 0x400)
        if body is not None:
            guard["selected_body_bytes_hex"] = body.hex()
            guard["selected_body_bound"] = True
    plt_address = _hex_int(guard.get("plt_address"))
    if plt_address is not None:
        stub = _readable_process_bytes(plt_address, 16)
        if stub is not None:
            guard["plt_stub_bytes_hex"] = stub.hex()
    wrapper_blob = guard.get("wrapper_bytes_hex")
    wrapper_address = _hex_int(guard.get("wrapper_address"))
    if isinstance(wrapper_blob, str) and wrapper_address is not None:
        try:
            wrapper_instructions = _decode_complete(bytes.fromhex(wrapper_blob), wrapper_address)
        except ValueError:
            wrapper_instructions = None
        guard["wrapper_constants"] = [] if wrapper_instructions is None else _retained_wrapper_constants(wrapper_instructions)
    else:
        guard["wrapper_constants"] = []
    guard["pid"] = os.getpid()
    guard["thread_id"] = _thread_id()
    return guard


def observe_bound_nextafter() -> dict[str, object]:
    """One interpreter started with LD_BIND_NOW=1. The slot is not warmed by a call."""
    if os.environ.get("LD_BIND_NOW") == "1":
        return capture_bound_nextafter()
    env = os.environ.copy()
    env["LD_BIND_NOW"] = "1"
    script = (
        "import json\n"
        "from pyfoldable.application.c2v09_runtime_semantic_correspondence import capture_bound_nextafter\n"
        "print(json.dumps(capture_bound_nextafter()))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return {
            "bind_now": False,
            "got_resolved": False,
            "ulp_function_calls": 0,
            "nextafter_function_calls": 0,
            "output_sampled": False,
            "unchanged_guard_ulps": 2,
            "allowance_recomputed": False,
            "independent_symbol_establishes_selected_path": False,
        }
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "bind_now": False,
            "got_resolved": False,
            "ulp_function_calls": 0,
            "nextafter_function_calls": 0,
            "output_sampled": False,
            "unchanged_guard_ulps": 2,
            "allowance_recomputed": False,
            "independent_symbol_establishes_selected_path": False,
        }
    if isinstance(parsed, dict):
        parsed["bind_now"] = True
        parsed["ulp_function_calls"] = 0
        parsed["nextafter_function_calls"] = 0
        parsed["output_sampled"] = False
        return parsed
    return {
        "bind_now": False,
        "got_resolved": False,
        "ulp_function_calls": 0,
        "nextafter_function_calls": 0,
        "output_sampled": False,
        "unchanged_guard_ulps": 2,
        "allowance_recomputed": False,
        "independent_symbol_establishes_selected_path": False,
    }


def _number_slot_record(image: str) -> dict[str, object]:
    if not image:
        return {}
    defined = _defined_symbol(image, "PyFloat_Type")
    if defined is None:
        return {}
    runtime = _vaddr_to_runtime(image, defined[0])
    if runtime is None:
        return {}
    header = _readable_process_bytes(runtime, 0x70)
    if header is None or len(header) < 0x68:
        return {}
    name = _readable_process_bytes(struct.unpack_from("<Q", header, 0x18)[0], 6)
    located = _float_slots(image)
    slots = {} if located is None else located[0]
    return {
        "type_address": hex(runtime),
        "type_name_bytes_hex": None if name is None else name.hex(),
        "basicsize": struct.unpack_from("<Q", header, 0x20)[0],
        "tp_as_number": hex(struct.unpack_from("<Q", header, 0x60)[0]),
        "slots": {
            kind: {"index": _SLOT_INDEX[kind], "target": hex(address)}
            for kind, address in slots.items()
        },
    }


def _missing_bound_observation() -> dict[str, object]:
    """A failed bound capture does not borrow this process's controls."""
    return {
        "pid": None,
        "thread_id": None,
        "single_process_thread": False,
        "output_sampled": False,
        "version_label": sys.version.split()[0],
        "version_label_establishes_semantics": False,
        "approval_receipt_establishes_semantics": False,
        "sample_outputs_establish_semantics": False,
        "controls": {"classification": "NOT ESTABLISHED", "pid": None, "thread_id": None},
        "arithmetic": {
            "operations": [],
            "generic_handlers": {},
            "specialized_handlers": {},
            "specialized_scan": "unavailable",
            "unclassified_scalar_sites": None,
            "declared_annulus_count": None,
            "integer_add": {},
            "number_slots": {},
            "pid": None,
            "thread_id": None,
        },
        "conversion": {"pid": None, "thread_id": None},
        "terminal_guard": {
            "bind_now": False,
            "pid": None,
            "thread_id": None,
            "ulp_function_calls": 0,
            "nextafter_function_calls": 0,
            "output_sampled": False,
            "unchanged_guard_ulps": 2,
            "allowance_recomputed": False,
            "independent_symbol_establishes_selected_path": False,
        },
        "cosine_function_calls": 0,
        "ulp_function_calls": 0,
        "nextafter_function_calls": 0,
    }


def _capture_bound_process(root: Path) -> dict[str, object] | None:
    env = os.environ.copy()
    env["LD_BIND_NOW"] = "1"
    script = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "from pyfoldable.application.c2v09_runtime_semantic_correspondence import capture_observations\n"
        "print(json.dumps(capture_observations(Path(sys.argv[1]))))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script, str(root)],
        env=env,
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or parsed.get("pid") is None:
        return None
    guard = parsed.get("terminal_guard")
    if not isinstance(guard, dict) or guard.get("bind_now") is not True or guard.get("pid") != parsed.get("pid"):
        return None
    return parsed


def _capture_observations_here(root: Path) -> dict[str, object]:
    """Read this bound process only. Do not call cosine, nextafter, ulp or the evaluator."""
    thread_id = _thread_id()
    pid = os.getpid()
    wrapper = _c_function_address(math.cos)
    image = None if wrapper is None else _image_of(wrapper)
    controls = _feature_record(None, None)
    probed = _probe_words(root / PROBE_SOURCE)
    if probed is not None:
        controls = _feature_record(probed[0], _fegetround())
    controls["pid"] = pid
    controls["bind_now"] = True
    generic: dict[str, dict[str, object]] = {}
    specialized: dict[str, list[dict[str, object]]] = {}
    scan = "unavailable"
    unclassified = 0
    conversion: dict[str, object] = {}
    if image is not None and wrapper is not None:
        generic = _capture_generic_handlers(image)
        from_double = _symbol_runtime(image, "PyFloat_FromDouble")
        specialized, scan, unclassified = _capture_specialized_handlers(
            image,
            None if from_double is None else from_double[0],
            None if from_double is None else from_double[0] + from_double[2],
        )
        conversion = _capture_conversion(image, wrapper)
    conversion["pid"] = pid
    conversion["thread_id"] = thread_id
    same_thread = controls.get("thread_id") == thread_id
    return {
        "pid": pid,
        "thread_id": thread_id,
        "single_process_thread": same_thread and probed is not None,
        "output_sampled": False,
        "version_label": sys.version.split()[0],
        "version_label_establishes_semantics": False,
        "approval_receipt_establishes_semantics": False,
        "sample_outputs_establish_semantics": False,
        "controls": controls,
        "arithmetic": {
            "pid": pid,
            "thread_id": thread_id,
            "operations": _capture_operations(),
            "generic_handlers": generic,
            "specialized_handlers": specialized,
            "specialized_scan": scan,
            "unclassified_scalar_sites": unclassified,
            "declared_annulus_count": _declared_annulus_count(root),
            "integer_add": _capture_integer_add(image or "", _declared_annulus_count(root)),
            "number_slots": _number_slot_record(image or ""),
        },
        "conversion": conversion,
        "terminal_guard": capture_bound_nextafter(),
        "cosine_function_calls": 0,
        "ulp_function_calls": 0,
        "nextafter_function_calls": 0,
    }


def capture_observations(root: Path) -> dict[str, object]:
    """Capture every component in one interpreter started with LD_BIND_NOW=1."""
    if os.environ.get("LD_BIND_NOW") != "1":
        bound = _capture_bound_process(root)
        if bound is None:
            return _missing_bound_observation()
        return bound
    return _capture_observations_here(root)


def _controls_ok(observations: Mapping[str, object]) -> bool:
    if observations.get("single_process_thread") is not True or observations.get("output_sampled") is not False:
        return False
    controls = observations.get("controls")
    if not isinstance(controls, Mapping):
        return False
    return (
        controls.get("classification") == "OBSERVED"
        and controls.get("required_bits_ok") is True
        and controls.get("mxcsr_ftz") is False
        and controls.get("mxcsr_daz") is False
        and controls.get("mxcsr_rounding") == "nearest ties-to-even"
        and controls.get("fegetround") == "0"
        and controls.get("pid") == observations.get("pid")
        and controls.get("thread_id") == observations.get("thread_id")
    )


def _decode_complete(blob: bytes, address: int) -> list[capstone.CsInsn] | None:
    """Every byte of a claimed range must decode. A trailing truncated opcode does not."""
    if not blob:
        return None
    instructions = list(_decoder().disasm(blob, address))
    if not instructions:
        return None
    consumed = instructions[-1].address + instructions[-1].size - address
    if consumed != len(blob):
        return None
    return instructions


def _hex_int(value: object) -> int | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def _handler_instructions(handler: Mapping[str, object]) -> list[capstone.CsInsn] | None:
    blob = handler.get("loaded_bytes_hex")
    address = _hex_int(handler.get("address"))
    if not isinstance(blob, str) or address is None:
        return None
    try:
        raw = bytes.fromhex(blob)
    except ValueError:
        return None
    return _decode_complete(raw, address)


def _from_double_bounds(handler: Mapping[str, object]) -> tuple[int | None, int | None]:
    start = _hex_int(handler.get("from_double_address"))
    end = _hex_int(handler.get("from_double_end"))
    return start, end


def _continuation_admitted(handler: Mapping[str, object], row: Mapping[str, object]) -> bool:
    """Shape is not correspondence. A continuation needs matched bytes, an image range, and one context."""
    if row.get("loaded_bytes_match_file") is not True:
        return False
    image = row.get("image")
    if not isinstance(image, str) or not image or _hex_int(row.get("elf_vaddr")) is None:
        return False
    pid = row.get("pid")
    thread = row.get("thread_id")
    if isinstance(pid, bool) or not isinstance(pid, int) or not isinstance(thread, str) or not thread:
        return False
    return handler.get("image") == image and handler.get("pid") == pid and handler.get("thread_id") == thread


def _decoded_continuations(handler: Mapping[str, object]) -> list[tuple[int, list[capstone.CsInsn]]]:
    rows = handler.get("continuations")
    found: list[tuple[int, list[capstone.CsInsn]]] = []
    if not isinstance(rows, list):
        return found
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        address = _hex_int(row.get("address"))
        blob = row.get("loaded_bytes_hex")
        if address is None or not isinstance(blob, str) or not _continuation_admitted(handler, row):
            continue
        try:
            instructions = _decode_complete(bytes.fromhex(blob), address)
        except ValueError:
            continue
        if instructions:
            found.append((address, instructions))
    return found


def _continuation_shape(instructions: list[capstone.CsInsn]) -> str:
    """A continuation is closed only when every exit stays inside, returns, or is its final jump."""
    if not instructions:
        return "open"
    inside = {insn.address for insn in instructions}
    for index, insn in enumerate(instructions):
        last = index == len(instructions) - 1
        next_address = insn.address + insn.size
        if insn.mnemonic == "ret":
            continue
        if insn.mnemonic == "call":
            return "open"
        if insn.mnemonic == "jmp" or (insn.mnemonic.startswith("j") and insn.mnemonic != "jmp"):
            target = _direct_target(insn)
            if target in inside:
                continue
            if last and insn.mnemonic == "jmp" and target is not None:
                continue
            return "open"
        if next_address not in inside and not (last and insn.mnemonic in {"ret", "jmp"}):
            return "open"
    last_insn = instructions[-1]
    if last_insn.mnemonic == "ret":
        return "return"
    if last_insn.mnemonic == "jmp" and _direct_target(last_insn) is not None:
        return "jump"
    return "open"


def _foreign_operation(instructions: list[capstone.CsInsn]) -> bool:
    return any(insn.mnemonic in _SCALAR or _is_fma(insn.mnemonic) for insn in instructions)


def _continuations_return(handler: Mapping[str, object], inside: set[int]) -> dict[int, int]:
    """External stubs that jump back into the claimed range. Other destinations stay unresolved."""
    returns: dict[int, int] = {}
    for address, instructions in _decoded_continuations(handler):
        if _foreign_operation(instructions) or _continuation_shape(instructions) != "jump":
            continue
        target = _direct_target(instructions[-1])
        if target in inside:
            returns[address] = target
    return returns


def _returning_calls(handler: Mapping[str, object]) -> set[int]:
    """Callees whose captured bytes return without another binary64 operation or an open exit."""
    found: set[int] = set()
    for address, instructions in _decoded_continuations(handler):
        if _foreign_operation(instructions) or _continuation_shape(instructions) != "return":
            continue
        found.add(address)
    return found


def _target_in_range(target: int | None, start: int | None, end: int | None) -> bool:
    if target is None or start is None:
        return False
    limit = end if end is not None else start + 1
    return start <= target < limit


def _bracket_base_disp(text: str) -> tuple[str, int] | None:
    """Base and displacement of [reg], [reg + disp], or [reg - disp]. Indexed forms are unsupported."""
    if "[" not in text or "]" not in text:
        return None
    inner = text[text.find("[") + 1:text.rfind("]")].strip()
    if "," in inner or "*" in inner or "rip" in inner:
        return None
    if " + " in inner:
        base, disp = inner.split(" + ", 1)
        try:
            return base.strip(), int(disp, 0)
        except ValueError:
            return None
    if " - " in inner:
        base, disp = inner.split(" - ", 1)
        try:
            return base.strip(), -int(disp, 0)
        except ValueError:
            return None
    if _register_width(inner) is None:
        return None
    return inner, 0


def _pointer_update(
    pointers: frozenset[tuple[str, int]],
    insn: capstone.CsInsn,
) -> frozenset[tuple[str, int]]:
    """Full-width copies and constant displacements only. Anything else drops pointer provenance."""
    if insn.mnemonic in {"cmp", "test", "ucomisd", "comisd", "vucomisd", "vcomisd", "ret", "nop", "endbr64"} or insn.mnemonic.startswith("j"):
        return pointers
    known = dict(pointers)
    if insn.mnemonic == "call":
        return frozenset((reg, offset) for reg, offset in known.items() if reg not in _VOLATILE)
    dest_text, src_text = _split_operand(insn.op_str)
    dest = _register_width(_leading_register(dest_text))
    src = _register_width(_leading_register(src_text))
    if (
        insn.mnemonic == "mov"
        and dest is not None
        and src is not None
        and dest[1] == 64
        and src[1] == 64
        and "[" not in dest_text
        and src[0] in known
    ):
        known[dest[0]] = known[src[0]]
        return frozenset(known.items())
    if insn.mnemonic == "lea" and dest is not None and dest[1] == 64 and src_text is not None:
        parsed = _bracket_base_disp(src_text)
        base = None if parsed is None else _register_width(parsed[0])
        if parsed is not None and base is not None and base[1] == 64 and base[0] in known:
            known[dest[0]] = known[base[0]] + parsed[1]
            return frozenset(known.items())
    if (
        insn.mnemonic in {"add", "sub"}
        and dest is not None
        and dest[1] == 64
        and dest[0] in known
        and src_text is not None
        and src_text.startswith(("0x", "-"))
    ):
        try:
            immediate = int(src_text, 0)
        except ValueError:
            immediate = None
        if immediate is not None:
            if insn.mnemonic == "sub":
                immediate = -immediate
            known[dest[0]] = known[dest[0]] + immediate
            return frozenset(known.items())
    return frozenset()


def _pointer_states(
    instructions: list[capstone.CsInsn],
) -> dict[int, set[tuple[frozenset[tuple[str, int]], int]]]:
    """Arrival state and the instruction that produced it. ABI rdi and rsi are the operands."""
    initial = frozenset({("rdi", 0), ("rsi", 0)})
    arriving: dict[int, set[tuple[frozenset[tuple[str, int]], int]]] = {0: {(initial, -1)}}
    seen: set[tuple[int, tuple[tuple[str, int], ...]]] = set()
    stack: list[tuple[int, frozenset[tuple[str, int]]]] = [(0, initial)]
    while stack:
        index, pointers = stack.pop()
        key = (index, tuple(sorted(pointers)))
        if key in seen or index >= len(instructions):
            continue
        seen.add(key)
        insn = instructions[index]
        updated = _pointer_update(pointers, insn)
        next_address = insn.address + insn.size
        targets: list[int] = []
        if insn.mnemonic == "ret":
            continue
        if insn.mnemonic == "jmp" or (insn.mnemonic.startswith("j") and insn.mnemonic != "jmp"):
            target = _direct_target(insn)
            if target is not None:
                targets.append(target)
            if insn.mnemonic != "jmp":
                targets.append(next_address)
        else:
            targets.append(next_address)
        by_address = {item.address: position for position, item in enumerate(instructions)}
        for target in targets:
            successor = by_address.get(target)
            if successor is None:
                continue
            arriving.setdefault(successor, set()).add((updated, index))
            stack.append((successor, updated))
    return arriving


def _compared_type_slot(compared: str, pointers: frozenset[tuple[str, int]]) -> bool:
    parsed = _bracket_base_disp(compared)
    if parsed is None or not compared.startswith("qword ptr ["):
        return False
    base = _register_width(parsed[0])
    if base is None or base[1] != 64:
        return False
    known = dict(pointers)
    if base[0] not in known:
        return False
    return known[base[0]] + parsed[1] == 8


def _exit_excluded(handler: Mapping[str, object], instructions: list[capstone.CsInsn], index: int) -> bool:
    """Exclude a not-equal branch only when every arrival compares an admitted operand's type slot."""
    insn = instructions[index]
    if insn.mnemonic not in {"jne", "jnz"} or index == 0 or _direct_target(insn) is None:
        return False
    predecessor = instructions[index - 1]
    type_address = _hex_int(handler.get("float_type_address"))
    if (
        type_address is None
        or predecessor.mnemonic != "cmp"
        or hex(type_address) not in _operand_tokens(predecessor.op_str)
    ):
        return False
    arrivals = _pointer_states(instructions).get(index, set())
    if not arrivals:
        return False
    return all(
        source == index - 1 and _compared_type_slot(predecessor.op_str, pointers)
        for pointers, source in arrivals
    )


def _dispatch_addresses(instructions: list[capstone.CsInsn]) -> set[int]:
    """An indirect jump is a next-opcode dispatch only when the loaded bytes form that sequence."""
    found: set[int] = set()
    for index, insn in enumerate(instructions):
        if insn.mnemonic != "jmp":
            continue
        dest = insn.op_str.strip()
        if not dest or dest.startswith(("0x", "qword", "dword")):
            continue
        window = instructions[max(0, index - 12):index]
        opcode_at = None
        for item in window:
            if item.mnemonic == "movzx" and "byte ptr" in item.op_str:
                opcode_at = item.address
        if opcode_at is None:
            continue
        tail = [item for item in window if item.address >= opcode_at]
        if any(item.mnemonic in _SCALAR or _is_fma(item.mnemonic) or item.mnemonic in {"call", "ret"} for item in tail):
            continue
        table = any(
            item.mnemonic == "mov" and item.op_str.startswith(dest + ",") and "*8" in item.op_str
            for item in tail
        )
        if table:
            found.add(insn.address)
    return found


def _path_exits(
    handler: Mapping[str, object],
    instructions: list[capstone.CsInsn],
    index: int,
    *,
    inside: set[int],
    returns: Mapping[int, int],
    calls: set[int],
    dispatch: set[int],
    external_dispatch: Mapping[int, list[capstone.CsInsn]],
    from_double: int | None,
    from_double_end: int | None,
) -> list[tuple[str, int | None]]:
    insn = instructions[index]
    mnemonic = insn.mnemonic
    next_address = insn.address + insn.size
    if mnemonic == "ret":
        return [("endpoint", None)]
    if mnemonic == "jmp" or (mnemonic.startswith("j") and mnemonic != "jmp"):
        if mnemonic == "jmp" and insn.address in dispatch:
            return [("endpoint", None)]
        target = _direct_target(insn)
        found: list[tuple[str, int | None]] = []
        if target is None:
            found.append(("unresolved", None))
        elif target in inside:
            found.append(("go", target))
        elif target in returns:
            found.append(("go", returns[target]))
        elif target in external_dispatch:
            found.append(("dispatch_cont", target))
        elif mnemonic == "jmp" and _target_in_range(target, from_double, from_double_end):
            found.append(("tail", target))
        elif _exit_excluded(handler, instructions, index):
            found.append(("excluded", None))
        else:
            found.append(("unresolved", None))
        if mnemonic != "jmp":
            found.append(("go", next_address) if next_address in inside else ("unresolved", None))
        return found
    if mnemonic == "call":
        target = _direct_target(insn)
        if target is not None and _target_in_range(target, from_double, from_double_end):
            return [("fromdouble", target)]
        if target is not None and target in calls and next_address in inside:
            return [("go", next_address)]
        return [("unresolved", None)]
    if next_address in inside:
        return [("go", next_address)]
    return [("unresolved", None)]


def _fromdouble_body(handler: Mapping[str, object]) -> list[capstone.CsInsn] | None:
    blob = handler.get("from_double_bytes_hex")
    address = _hex_int(handler.get("from_double_address"))
    if not isinstance(blob, str) or address is None:
        return None
    try:
        return _decode_complete(bytes.fromhex(blob), address)
    except ValueError:
        return None


def _fromdouble_store_reached(handler: Mapping[str, object], landing: int | None, registers: frozenset[str]) -> bool:
    body = _fromdouble_body(handler)
    if body is None or landing is None or "xmm0" not in registers:
        return False
    return _store_reaches_return(body, landing, frozenset({"xmm0"}))


def _dispatch_continuation_closed(
    instructions: list[capstone.CsInsn],
    registers: frozenset[str],
    stored: bool,
) -> bool:
    """The indirect dispatch is the endpoint. A later slot write must still hold the result."""
    if not stored:
        return False
    dispatch = _dispatch_addresses(instructions)
    if not dispatch:
        return False
    by_address = {insn.address: index for index, insn in enumerate(instructions)}
    inside = set(by_address)
    reached = False
    seen: set[tuple[int, tuple[str, ...], bool]] = set()
    stack: list[tuple[int, frozenset[str], bool]] = [(0, registers, stored)]
    while stack:
        index, regs, slot = stack.pop()
        state = (index, tuple(sorted(regs)), slot)
        if state in seen:
            continue
        seen.add(state)
        insn = instructions[index]
        next_registers = _apply_transfer(regs, insn)
        next_slot = _stores_tracked(insn, next_registers) if _slot_store(insn) else slot
        if insn.address in dispatch:
            if not next_slot:
                return False
            reached = True
            continue
        next_address = insn.address + insn.size
        if insn.mnemonic in _SCALAR or _is_fma(insn.mnemonic) or insn.mnemonic in {"call", "ret"}:
            return False
        targets: list[int] = []
        if insn.mnemonic == "jmp" or (insn.mnemonic.startswith("j") and insn.mnemonic != "jmp"):
            target = _direct_target(insn)
            if target not in inside:
                return False
            targets.append(target)
            if insn.mnemonic != "jmp":
                if next_address not in inside:
                    return False
                targets.append(next_address)
        elif next_address not in inside:
            return False
        else:
            targets.append(next_address)
        for target in targets:
            stack.append((by_address[target], next_registers, next_slot))
    return reached


def _handler_path_status(handler: Mapping[str, object], kind: str) -> str:
    """Every reachable exit is established or excluded by a decoded condition."""
    instructions = _handler_instructions(handler)
    if not instructions or handler.get("loaded_bytes_match_file") is not True:
        return NOT_ESTABLISHED
    if any(_is_fma(insn.mnemonic) for insn in instructions):
        return MISMATCHED
    foreign = [insn.mnemonic for insn in instructions if insn.mnemonic in _SCALAR and _KIND_BY_MNEMONIC.get(insn.mnemonic) != kind]
    if foreign:
        return MISMATCHED
    from_double, from_double_end = _from_double_bounds(handler)
    inside = {insn.address for insn in instructions}
    by_address = {insn.address: index for index, insn in enumerate(instructions)}
    returns = _continuations_return(handler, inside)
    calls = _returning_calls(handler)
    dispatch = _dispatch_addresses(instructions) if handler.get("completion") == "next_opcode_dispatch" else set()
    external_dispatch: dict[int, list[capstone.CsInsn]] = {}
    if handler.get("completion") == "next_opcode_dispatch":
        for address, continuation in _decoded_continuations(handler):
            if _dispatch_addresses(continuation):
                external_dispatch[address] = continuation
    seen: set[tuple[int, int, bool, tuple[str, ...]]] = set()
    stack: list[tuple[int, int, bool, frozenset[str]]] = [(0, 0, False, frozenset())]
    completed = False
    while stack:
        index, scalars, stored, registers = stack.pop()
        state = (index, scalars, stored, tuple(sorted(registers)))
        if state in seen:
            continue
        seen.add(state)
        insn = instructions[index]
        if insn.mnemonic in _SCALAR:
            dest = _scalar_dest(insn)
            next_registers = frozenset({dest}) if dest is not None else frozenset()
            next_scalars = scalars + 1
        else:
            next_registers = _apply_transfer(registers, insn)
            next_scalars = scalars
        if next_scalars > 1:
            return NOT_ESTABLISHED
        if _slot_store(insn):
            next_stored = next_scalars == 1 and _stores_tracked(insn, next_registers)
        else:
            next_stored = stored
        for kind_exit, target in _path_exits(
            handler,
            instructions,
            index,
            inside=inside,
            returns=returns,
            calls=calls,
            dispatch=dispatch,
            external_dispatch=external_dispatch,
            from_double=from_double,
            from_double_end=from_double_end,
        ):
            if kind_exit == "unresolved":
                return NOT_ESTABLISHED
            if kind_exit == "dispatch_cont":
                continuation = None if target is None else external_dispatch.get(target)
                if continuation is None or not _dispatch_continuation_closed(
                    continuation,
                    next_registers,
                    next_scalars == 1 and next_stored,
                ):
                    return NOT_ESTABLISHED
                completed = True
                continue
            if kind_exit in {"endpoint", "tail", "fromdouble"}:
                if kind_exit == "endpoint":
                    if next_scalars == 1 and next_stored:
                        completed = True
                        continue
                    return NOT_ESTABLISHED
                if not _fromdouble_store_reached(handler, target, registers) or next_scalars != 1:
                    return NOT_ESTABLISHED
                if kind_exit == "tail":
                    completed = True
                    continue
                next_address = insn.address + insn.size
                if next_address not in by_address:
                    return NOT_ESTABLISHED
                stack.append((by_address[next_address], next_scalars, True, next_registers))
                continue
            if kind_exit == "excluded" or target is None:
                continue
            stack.append((by_address[target], next_scalars, next_stored, next_registers))
    if not any(insn.mnemonic in _SCALAR for insn in instructions):
        return NOT_ESTABLISHED
    return ESTABLISHED_CONDITIONALLY if completed else NOT_ESTABLISHED


def _decoded_store(handler: Mapping[str, object]) -> str:
    instructions = _handler_instructions(handler)
    if not instructions:
        return "not traced"
    from_double, from_double_end = _from_double_bounds(handler)
    return _store_kind(instructions, from_double, from_double_end)


def _handler_status(handler: Mapping[str, object], kind: str) -> str:
    return _handler_path_status(handler, kind)


def nextafter_got_resolved(target: int, qword: int, stub: bytes) -> bool:
    """An unresolved PLT slot, including an endbr64 stub, is not the selected body."""
    if not stub or qword == 0:
        return False
    prefix = 4 if stub.startswith(b"\xf3\x0f\x1e\xfa") else 0
    if qword == target or qword == target + prefix + 6 or target <= qword < target + len(stub):
        return False
    return plt_got_address(stub, target) is not None


def _integer_add_status(arithmetic: Mapping[str, object]) -> str:
    handler = arithmetic.get("integer_add")
    declared = arithmetic.get("declared_annulus_count")
    if not isinstance(handler, Mapping) or isinstance(declared, bool) or not isinstance(declared, int):
        return NOT_ESTABLISHED
    if not 2 <= declared <= 15:
        return NOT_ESTABLISHED
    instructions = _handler_instructions(handler)
    if not instructions or handler.get("loaded_bytes_match_file") is not True:
        return NOT_ESTABLISHED
    if any(insn.mnemonic in _SCALAR or _is_fma(insn.mnemonic) for insn in instructions):
        return MISMATCHED
    # cmp 0xf / ja leaves this body. A prose assumption does not close that exit.
    return NOT_ESTABLISHED


def _slot_matches(arithmetic: Mapping[str, object], handler: Mapping[str, object], kind: str) -> bool:
    slots = arithmetic.get("number_slots")
    if not isinstance(slots, Mapping):
        return False
    if slots.get("type_name_bytes_hex") != "666c6f617400" or slots.get("basicsize") != 24:
        return False
    if _hex_int(slots.get("type_address")) is None or _hex_int(slots.get("tp_as_number")) is None:
        return False
    table = slots.get("slots")
    if not isinstance(table, Mapping):
        return False
    row = table.get(kind)
    if not isinstance(row, Mapping) or row.get("index") != _SLOT_INDEX.get(kind):
        return False
    return _hex_int(row.get("target")) == _hex_int(handler.get("address"))


def _source_registers(insn: capstone.CsInsn) -> set[str]:
    dest_text, src_text = _split_operand(insn.op_str)
    found: set[str] = set()
    dest = _canonical_register(_leading_register(dest_text))
    if dest is not None and dest.startswith("xmm") and not insn.mnemonic.startswith("v"):
        found.add(dest)
    if src_text is not None:
        for token in _operand_tokens(src_text):
            register = _canonical_register(token)
            if register is not None and (register.startswith("xmm") or register.startswith("r")):
                found.add(register)
    return found


def _returns_converted_xmm0(instructions: list[capstone.CsInsn]) -> bool:
    """Every return must still hold the converted bits in xmm0. An unreachable convert does not count."""
    if not instructions:
        return False
    by_address = {insn.address: index for index, insn in enumerate(instructions)}
    inside = set(by_address)
    completed = False
    seen: set[tuple[int, tuple[str, ...]]] = set()
    stack: list[tuple[int, frozenset[str]]] = [(0, frozenset())]
    while stack:
        index, registers = stack.pop()
        state = (index, tuple(sorted(registers)))
        if state in seen:
            continue
        seen.add(state)
        insn = instructions[index]
        if insn.mnemonic in {"cvtsi2sd", "vcvtsi2sd"}:
            dest = _canonical_register(_leading_register(_split_operand(insn.op_str)[0]))
            next_registers = frozenset({dest}) if dest is not None else frozenset()
        else:
            next_registers = _apply_transfer(registers, insn)
        next_address = insn.address + insn.size
        if insn.mnemonic == "ret":
            if "xmm0" not in next_registers:
                return False
            completed = True
            continue
        targets: list[int] = []
        if insn.mnemonic == "jmp" or (insn.mnemonic.startswith("j") and insn.mnemonic != "jmp"):
            target = _direct_target(insn)
            if target not in inside:
                return False
            targets.append(target)
            if insn.mnemonic != "jmp":
                if next_address not in inside:
                    return False
                targets.append(next_address)
        elif insn.mnemonic == "call" or next_address not in inside:
            return False
        else:
            targets.append(next_address)
        for target in targets:
            stack.append((by_address[target], next_registers))
    return completed


def _conversion_flows(instructions: list[capstone.CsInsn], call_target: int, source: str) -> bool:
    by_address = {insn.address: index for index, insn in enumerate(instructions)}
    inside = set(by_address)
    starts = [
        by_address[insn.address + insn.size]
        for insn in instructions
        if insn.mnemonic == "call"
        and _direct_target(insn) == call_target
        and insn.address + insn.size in by_address
    ]
    if not starts:
        return False
    consumed = False
    seen: set[tuple[int, tuple[str, ...]]] = set()
    stack: list[tuple[int, frozenset[str]]] = [(index, frozenset({source})) for index in starts]
    while stack:
        index, registers = stack.pop()
        state = (index, tuple(sorted(registers)))
        if state in seen:
            continue
        seen.add(state)
        insn = instructions[index]
        if insn.mnemonic in _SCALAR:
            if not registers & _source_registers(insn):
                return False
            consumed = True
            continue
        next_registers = _apply_transfer(registers, insn)
        next_address = insn.address + insn.size
        targets: list[int] = []
        if insn.mnemonic == "ret":
            continue
        if insn.mnemonic == "jmp" or (insn.mnemonic.startswith("j") and insn.mnemonic != "jmp"):
            target = _direct_target(insn)
            if target in inside:
                targets.append(target)
            if insn.mnemonic != "jmp" and next_address in inside:
                targets.append(next_address)
        elif next_address in inside:
            targets.append(next_address)
        for target in targets:
            stack.append((by_address[target], next_registers))
    return consumed


def _mixed_conversion_bound(arithmetic: Mapping[str, object], kind: str) -> bool:
    handlers = arithmetic.get("generic_handlers")
    declared = arithmetic.get("declared_annulus_count")
    if not isinstance(handlers, Mapping) or isinstance(declared, bool) or not isinstance(declared, int):
        return False
    handler = handlers.get(kind)
    if not isinstance(handler, Mapping) or _handler_status(handler, kind) != ESTABLISHED_CONDITIONALLY:
        return False
    if not _slot_matches(arithmetic, handler, kind):
        return False
    handler_instructions = _handler_instructions(handler)
    if not handler_instructions:
        return False
    call_targets = {
        target
        for insn in handler_instructions
        if insn.mnemonic == "call" and (target := _direct_target(insn)) is not None
    }
    for address, instructions in _decoded_continuations(handler):
        if address not in call_targets or _foreign_operation(instructions) or not _returns_converted_xmm0(instructions):
            continue
        if _conversion_flows(handler_instructions, address, "xmm0"):
            return True
    return False


def _arithmetic_argument(observations: Mapping[str, object]) -> dict[str, object]:
    name = _HYPOTHESES[0]
    arithmetic = observations.get("arithmetic")
    gaps = []
    evidence = []
    if not isinstance(arithmetic, Mapping):
        return _argument(name, NOT_ESTABLISHED, ["arithmetic observations are missing"], [], [])
    operations = arithmetic.get("operations")
    generic = arithmetic.get("generic_handlers")
    specialized = arithmetic.get("specialized_handlers")
    if not isinstance(operations, list) or not operations or not isinstance(generic, Mapping):
        gaps.append("consumed arithmetic windows are not bound to loaded handlers")
        return _argument(name, NOT_ESTABLISHED, gaps, evidence, [])
    kinds: list[str] = []
    routed: list[tuple[Mapping[str, object], list[str]]] = []
    status = ESTABLISHED_CONDITIONALLY
    for row in operations:
        if not isinstance(row, Mapping) or row.get("bytecode_window_establishes_semantics") is not False:
            gaps.append("a bytecode window was treated as the arithmetic semantics")
            return _argument(name, NOT_ESTABLISHED, gaps, evidence, [])
        row_kinds = row.get("kinds")
        categories = row.get("categories")
        if not isinstance(row_kinds, list) or not row_kinds:
            gaps.append(f"{row.get('qualname')} has no bound binary operation")
            return _argument(name, NOT_ESTABLISHED, gaps, evidence, [])
        if not isinstance(categories, list) or len(categories) != len(row_kinds):
            gaps.append(f"{row.get('qualname')} has no operand category for each binary operation")
            status_gap = True
            categories = ["unclassified"] * len(row_kinds)
        else:
            status_gap = False
        kinds.extend(str(item) for item in row_kinds)
        routed.append((row, [str(item) for item in categories]))
        evidence.append(
            f"{row.get('qualname')}: "
            + ", ".join(f"{kind}/{category}" for kind, category in zip(row_kinds, categories))
        )
        if status_gap:
            status = NOT_ESTABLISHED
    float_kinds = {
        str(kind)
        for _row, categories in routed
        for kind, category in zip(_row.get("kinds") or [], categories)
        if category in {"float_float", "mixed_integer_float_multiply", "mixed_float_integer_divide"}
    }
    for kind in sorted(set(kinds)):
        handler = generic.get(kind)
        handler_status = _handler_status(handler, kind) if isinstance(handler, Mapping) else NOT_ESTABLISHED
        if handler_status == MISMATCHED:
            return _argument(name, MISMATCHED, [f"generic {kind} handler is not one separate binary64 operation"], evidence, [])
        if isinstance(handler, Mapping) and handler_status == ESTABLISHED_CONDITIONALLY and handler.get("loaded_bytes_hex"):
            evidence.append(f"generic {kind}: {_decoded_store(handler)}")
        if kind not in float_kinds:
            continue
        if not isinstance(handler, Mapping) or handler_status != ESTABLISHED_CONDITIONALLY:
            gaps.append(f"generic {kind} handler does not establish every relevant exit and the computed-result store")
            status = NOT_ESTABLISHED
    categories_used = {category for _row, categories in routed for category in categories}
    if "integer_add" in categories_used and _integer_add_status(arithmetic) != ESTABLISHED_CONDITIONALLY:
        gaps.append("index + 1 is integer arithmetic and is not bound to the integer slot")
        status = NOT_ESTABLISHED
    if "mixed_integer_float_multiply" in categories_used and not _mixed_conversion_bound(arithmetic, "mul"):
        gaps.append("index * width is a mixed integer/float multiply and is not bound to the conversion path")
        status = NOT_ESTABLISHED
    if "mixed_float_integer_divide" in categories_used and not _mixed_conversion_bound(arithmetic, "div"):
        gaps.append("division by annulus_count is a mixed float/integer divide and is not bound to the conversion path")
        status = NOT_ESTABLISHED
    if arithmetic.get("specialized_scan") != "complete" or arithmetic.get("unclassified_scalar_sites") not in (0, None):
        gaps.append("specialized evaluator sites were not fully classified")
        status = NOT_ESTABLISHED
    elif isinstance(specialized, Mapping):
        for kind in ("add", "sub", "mul", "div"):
            sites = specialized.get(kind)
            if not isinstance(sites, list):
                continue
            if not sites:
                evidence.append(f"specialized {kind}: not present in the loaded eval function")
                continue
            for site in sites:
                if not isinstance(site, Mapping):
                    status = NOT_ESTABLISHED
                    continue
                site_status = _handler_status(site, kind)
                if site_status == MISMATCHED:
                    return _argument(name, MISMATCHED, [f"specialized {kind} site is fused or is a different operation"], evidence, [])
                if site_status != ESTABLISHED_CONDITIONALLY:
                    gaps.append(f"specialized {kind} site does not reach a return or a loaded next-opcode dispatch on every relevant path")
                    status = NOT_ESTABLISHED
                else:
                    evidence.append(f"specialized {kind} at {site.get('scalar_address', site.get('address'))}: {_decoded_store(site)}")
    if arithmetic.get("pid") != observations.get("pid") or arithmetic.get("thread_id") != observations.get("thread_id"):
        gaps.append("arithmetic observations are not associated with this process and thread")
        status = NOT_ESTABLISHED
    if not _controls_ok(observations):
        gaps.append("required numerical controls were not observed on this process and thread")
        status = NOT_ESTABLISHED
    conditions = [
        "float/float operations use the float slot; index + 1 stays on the integer slot",
        "index * width and division by the declared annulus_count convert the integer with cvtsi2sd and then one scalar operation",
        "each consumed Python operation is a separate binary64 or integer operation and does not fuse across operations",
        "the declared annulus_count bounds the integer operands; the actual operand objects are checked when they exist and are not required before the source returns",
        "controls stay RNE, DAZ off and FTZ off in this process and thread",
    ]
    post_return = [
        "POST-RETURN ONLY: the actual operand objects passed by the returned source are not observed before that return",
    ]
    if status != ESTABLISHED_CONDITIONALLY:
        conditions = []
    return _argument(name, status, gaps, evidence, post_return, conditions)


def _decode_named(record: Mapping[str, object], blob_key: str, address_key: str) -> list[capstone.CsInsn] | None:
    blob = record.get(blob_key)
    address = _hex_int(record.get(address_key))
    if not isinstance(blob, str) or address is None:
        return None
    try:
        return _decode_complete(bytes.fromhex(blob), address)
    except ValueError:
        return None


def _builtin_float_load(instructions: list[capstone.CsInsn]) -> bool:
    """The supported lemma is a load of ob_fval and a return, with no conversion in between."""
    for index, insn in enumerate(instructions):
        if insn.mnemonic != "movsd" or "+ 0x10]" not in insn.op_str or not insn.op_str.startswith("xmm"):
            continue
        saw_ret = False
        for follow in instructions[index + 1:index + 8]:
            if follow.mnemonic in _CONVERT or follow.mnemonic in _SCALAR or follow.mnemonic in {"call", "jmp"}:
                break
            if follow.mnemonic == "ret":
                saw_ret = True
                break
            if follow.mnemonic not in {"add", "pop"}:
                break
        if saw_ret:
            return True
    return False


def _post_asdouble_fromdouble_landings(
    wrapper: list[capstone.CsInsn],
    as_address: int | None,
    start: int | None,
    end: int | None,
) -> list[int]:
    """A FromDouble edge counts only after PyFloat_AsDouble has returned."""
    if not wrapper or as_address is None:
        return []
    by_address = {insn.address: index for index, insn in enumerate(wrapper)}
    inside = set(by_address)
    stack = [
        by_address[insn.address + insn.size]
        for insn in wrapper
        if insn.mnemonic == "call" and _direct_target(insn) == as_address and insn.address + insn.size in by_address
    ]
    found: list[int] = []
    seen: set[int] = set()
    while stack:
        index = stack.pop()
        if index in seen:
            continue
        seen.add(index)
        insn = wrapper[index]
        target = _direct_target(insn)
        next_address = insn.address + insn.size
        if insn.mnemonic in {"call", "jmp"} and _target_in_range(target, start, end) and target is not None:
            found.append(target)
            if insn.mnemonic == "jmp":
                continue
        if insn.mnemonic == "ret":
            continue
        if insn.mnemonic == "jmp" or (insn.mnemonic.startswith("j") and insn.mnemonic != "jmp"):
            if target in inside:
                stack.append(by_address[target])
            if insn.mnemonic != "jmp" and next_address in inside:
                stack.append(by_address[next_address])
            continue
        if next_address in inside:
            stack.append(by_address[next_address])
    return found


def _retained_wrapper_constants(instructions: list[capstone.CsInsn]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen: set[int] = set()
    for insn in instructions:
        address = _rip_constant_address(insn)
        if address is None or address in seen:
            continue
        seen.add(address)
        blob = _readable_process_bytes(address, 8)
        mapped = None if blob is None else _runtime_to_vaddr(address)
        file_bytes = None if mapped is None or blob is None else _elf_bytes(mapped[0], mapped[1], 8)
        rows.append(
            {
                "address": hex(address),
                "loaded_bytes_hex": None if blob is None else blob.hex(),
                "loaded_bytes_match_file": blob is not None and file_bytes == blob,
            }
        )
    return rows


def _rip_constant_address(insn: capstone.CsInsn) -> int | None:
    text = insn.op_str
    marker = "rip + "
    sign = 1
    if "rip - " in text:
        marker = "rip - "
        sign = -1
    elif "rip + " not in text:
        return None
    token = text[text.find(marker) + len(marker):].split("]", 1)[0].split()[0]
    if not token.startswith("0x"):
        return None
    return insn.address + insn.size + sign * int(token, 16)


def _wrapper_constants_retained(wrapper: list[capstone.CsInsn] | None, guard: Mapping[str, object]) -> bool:
    if wrapper is None:
        return False
    sites = [address for insn in wrapper if (address := _rip_constant_address(insn)) is not None]
    recorded = guard.get("wrapper_constants")
    if not sites:
        return recorded in (None, [])
    if not isinstance(recorded, list):
        return False
    by_address: dict[int | None, Mapping[str, object]] = {}
    for row in recorded:
        if isinstance(row, Mapping):
            by_address[_hex_int(row.get("address"))] = row
    for site in sites:
        row = by_address.get(site)
        blob = None if row is None else row.get("loaded_bytes_hex")
        if row is None or row.get("loaded_bytes_match_file") is not True or not isinstance(blob, str):
            return False
        try:
            raw = bytes.fromhex(blob)
        except ValueError:
            return False
        if len(raw) != 8:
            return False
    return True


def _conversion_argument(observations: Mapping[str, object]) -> dict[str, object]:
    name = _HYPOTHESES[1]
    conversion = observations.get("conversion")
    if not isinstance(conversion, Mapping):
        return _argument(name, NOT_ESTABLISHED, ["conversion observations are missing"], [], [])
    evidence = []
    gaps = []
    wrapper = _decode_named(conversion, "wrapper_bytes_hex", "wrapper_address")
    asdouble = _decode_named(conversion, "asdouble_bytes_hex", "asdouble_address")
    fromdouble = _decode_named(conversion, "fromdouble_bytes_hex", "fromdouble_address")
    as_address = _hex_int(conversion.get("asdouble_address"))
    if wrapper is None or asdouble is None or fromdouble is None or as_address is None:
        gaps.append("wrapper, PyFloat_AsDouble, or PyFloat_FromDouble bytes do not decode completely")
    else:
        calls = [
            insn for insn in wrapper
            if insn.mnemonic == "call" and insn.op_str.startswith("0x") and int(insn.op_str, 16) == as_address
        ]
        if calls:
            evidence.append(f"wrapper calls PyFloat_AsDouble at {conversion.get('asdouble_address')}")
        else:
            gaps.append("the retained wrapper bytes do not call the retained PyFloat_AsDouble address")
        if _builtin_float_load(asdouble):
            evidence.append("builtin-float path loads the stored binary64 and returns it")
        else:
            gaps.append("the builtin-float load lemma is not in the retained PyFloat_AsDouble bytes")
        from_start = _hex_int(conversion.get("fromdouble_address"))
        from_end = _hex_int(conversion.get("fromdouble_end"))
        landings = _post_asdouble_fromdouble_landings(wrapper, as_address, from_start, from_end)
        if not landings:
            gaps.append("the wrapper's finite-result path does not reach PyFloat_FromDouble")
        elif not any(_store_reaches_return(fromdouble, landing, frozenset({"xmm0"})) for landing in landings):
            gaps.append("PyFloat_FromDouble is reached, but an unresolved exit remains on the result-bit store path")
        else:
            evidence.append("the finite-result path reaches PyFloat_FromDouble and stores the result bits")
    if conversion.get("pid") != observations.get("pid") or conversion.get("thread_id") != observations.get("thread_id"):
        gaps.append("conversion observations are not associated with this process and thread")
    if not _controls_ok(observations):
        gaps.append("required numerical controls were not observed on this process and thread")
    status = ESTABLISHED_CONDITIONALLY if not gaps else NOT_ESTABLISHED
    conditions = [
        "the operand that reaches PyFloat_AsDouble is a builtin float",
        "a non-float operand takes a different path and is not this argument",
    ] if status == ESTABLISHED_CONDITIONALLY else []
    post_return = [
        "POST-RETURN ONLY: the actual cosine operand object is known only after the source returns",
    ]
    return _argument(name, status, gaps, evidence, post_return, conditions)


def _positive_normal_carry(instructions: list[capstone.CsInsn]) -> bool:
    """The finite compare's taken branch must reach the carrying bit-pattern increment."""
    starts: list[int] = []
    for index, insn in enumerate(instructions[:-1]):
        branch = instructions[index + 1]
        if (
            insn.mnemonic == "cmp"
            and "0x7fefffff" in insn.op_str
            and branch.mnemonic == "jbe"
            and branch.op_str.startswith("0x")
        ):
            starts.append(int(branch.op_str, 16))
    carry_at = {
        index
        for index, insn in enumerate(instructions[:-2])
        if insn.mnemonic == "add"
        and insn.op_str.endswith(", 1")
        and instructions[index + 1].mnemonic == "jne"
        and instructions[index + 2].mnemonic == "add"
        and instructions[index + 2].op_str.endswith(", 1")
    }
    if not starts or not carry_at:
        return False
    by_address = {insn.address: index for index, insn in enumerate(instructions)}
    for start in starts:
        if start not in by_address:
            continue
        stack = [by_address[start]]
        seen: set[int] = set()
        while stack:
            index = stack.pop()
            if index in seen:
                continue
            seen.add(index)
            if index in carry_at:
                return True
            insn = instructions[index]
            next_address = insn.address + insn.size
            if insn.mnemonic == "ret":
                continue
            if insn.mnemonic == "jmp" or insn.mnemonic.startswith("j"):
                if insn.op_str.startswith("0x"):
                    target = int(insn.op_str, 16)
                    if target in by_address:
                        stack.append(by_address[target])
                if insn.mnemonic != "jmp" and next_address in by_address:
                    stack.append(by_address[next_address])
                continue
            if next_address in by_address:
                stack.append(by_address[next_address])
    return False


def _guard_argument(observations: Mapping[str, object]) -> dict[str, object]:
    name = _HYPOTHESES[2]
    guard = observations.get("terminal_guard")
    if not isinstance(guard, Mapping):
        return _argument(name, NOT_ESTABLISHED, ["terminal-guard observations are missing"], [], [])
    evidence = []
    gaps = []
    if guard.get("ulp_function_calls") != 0 or guard.get("nextafter_function_calls") != 0 or guard.get("output_sampled") is not False:
        gaps.append("a nextafter or ulp sample was treated as the semantics")
    wrapper = _decode_named(guard, "wrapper_bytes_hex", "wrapper_address")
    stub = _decode_named(guard, "plt_stub_bytes_hex", "plt_address")
    body = _decode_named(guard, "selected_body_bytes_hex", "selected_address")
    if wrapper is None or stub is None or body is None or guard.get("bind_now") is not True:
        gaps.append("the LD_BIND_NOW wrapper, PLT, and selected body were not retained for replay")
    else:
        evidence.append("wrapper, PLT stub, and selected body bytes decode completely")
        if not _positive_normal_carry(body):
            gaps.append("the selected body does not show the positive-finite compare reaching a carrying bit-pattern increment")
        else:
            evidence.append("positive-finite compare 0x7fefffff reaches the carrying increment")
        plt_address = _hex_int(guard.get("plt_address"))
        plt_calls = [
            insn.address
            for insn in wrapper
            if insn.mnemonic == "call" and insn.op_str.startswith("0x") and plt_address is not None and int(insn.op_str, 16) == plt_address
        ]
        subtracts = [insn.address for insn in wrapper if insn.mnemonic == "subsd"]
        if plt_calls and subtracts and min(subtracts) > min(plt_calls):
            evidence.append("wrapper subsd follows the nextafter call")
        else:
            gaps.append("the wrapper subtraction is not on the path after the nextafter call")
        if _wrapper_constants_retained(wrapper, guard):
            evidence.append("wrapper constants referenced by the loaded instructions are retained")
        else:
            gaps.append("a wrapper constant referenced by the loaded instructions was not retained")
    chain_gaps, chain_evidence = _nextafter_chain(guard)
    gaps.extend(chain_gaps)
    evidence.extend(chain_evidence)
    if guard.get("independent_symbol_establishes_selected_path") is not False:
        gaps.append("an independent symbol lookup was treated as the selected path")
    if guard.get("unchanged_guard_ulps") != 2 or guard.get("allowance_recomputed") is not False:
        gaps.append("the two-ULP guard allowance was recomputed or replaced")
    controls = observations.get("controls")
    if (
        guard.get("pid") != observations.get("pid")
        or guard.get("thread_id") != observations.get("thread_id")
        or not isinstance(controls, Mapping)
        or controls.get("pid") != guard.get("pid")
        or controls.get("thread_id") != guard.get("thread_id")
    ):
        gaps.append("the nextafter observation is not associated with this process, thread, and controls")
    if not _controls_ok(observations):
        gaps.append("required numerical controls were not observed on this process and thread")
    status = ESTABLISHED_CONDITIONALLY if not gaps else NOT_ESTABLISHED
    conditions = [
        "the value is a positive normal strictly below its binade endpoint",
        "the relevant positive-normal binade has ULP 2^-56",
        "the unchanged two-ULP allowance is 2^-55 and is not recomputed",
        "FTZ stays off so the subsequent subsd is not flushed",
    ] if status == ESTABLISHED_CONDITIONALLY else []
    argument = _argument(
        name,
        status,
        gaps,
        evidence,
        ["POST-RETURN ONLY: the actual guarded source value is known only after the source returns"],
        conditions,
    )
    argument["unchanged_guard_ulps"] = 2
    argument["ulp"] = "2^-56"
    argument["two_ulp_allowance"] = "2^-55"
    argument["allowance_recomputed"] = False
    return argument


def _nextafter_chain(guard: Mapping[str, object]) -> tuple[list[str], list[str]]:
    """Recompute wrapper PLT stub, decoded GOT slot, observed qword, and selected body."""
    gaps: list[str] = []
    evidence: list[str] = []
    plt_address = _hex_int(guard.get("plt_address"))
    stub_text = guard.get("plt_stub_bytes_hex")
    try:
        stub_bytes = bytes.fromhex(stub_text) if isinstance(stub_text, str) else b""
    except ValueError:
        stub_bytes = b""
    decoded_slot = None if plt_address is None or not stub_bytes else plt_got_address(stub_bytes, plt_address)
    recorded_slot = _hex_int(guard.get("got_slot"))
    if decoded_slot is None or recorded_slot is None or decoded_slot != recorded_slot:
        gaps.append("the decoded PLT GOT slot does not match the retained slot")
    else:
        evidence.append(f"PLT stub decodes GOT slot {guard.get('got_slot')}")
    qword = None
    qword_text = guard.get("got_qword_hex")
    if not isinstance(qword_text, str):
        gaps.append("the GOT qword was not retained")
    else:
        try:
            raw = bytes.fromhex(qword_text)
        except ValueError:
            raw = b""
        if len(raw) != 8:
            gaps.append("the GOT observation is not an eight-byte qword")
        else:
            qword = struct.unpack("<Q", raw)[0]
            evidence.append("the GOT slot retains the observed eight-byte qword")
    selected = _hex_int(guard.get("selected_address"))
    if qword is None or selected is None or qword != selected:
        gaps.append("the selected body is not the observed GOT qword")
    elif plt_address is None or not stub_bytes or not nextafter_got_resolved(plt_address, qword, stub_bytes):
        gaps.append("the nextafter GOT is unresolved, so the selected implementation bytes are not bound")
    else:
        evidence.append("the selected body is the qword observed in the decoded GOT slot")
    return gaps, evidence


def _argument(
    name: str,
    status: str,
    gaps: list[str],
    evidence: list[str],
    post_return: list[str],
    conditions: list[str] | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "status": status,
        "readiness_admitted": False,
        "evidence": evidence,
        "gaps": gaps,
        "conditions": [] if conditions is None else conditions,
        "post_return_only": post_return,
    }


def replay_handler_scalars(handler: Mapping[str, object]) -> list[str]:
    """Re-decode a captured handler. The recorded mnemonic list has to match."""
    blob = handler.get("loaded_bytes_hex")
    address = handler.get("address")
    if not isinstance(blob, str) or not isinstance(address, str):
        return []
    instructions = _cut_at_next_function(_disassemble(bytes.fromhex(blob), int(address, 16)))
    return [insn.mnemonic for insn in instructions if insn.mnemonic in _SCALAR]


def classify_correspondence(observations: Mapping[str, object]) -> dict[str, object]:
    """Classify captured observations. Caller text and samples are not evidence."""
    hypotheses = [
        _arithmetic_argument(observations),
        _conversion_argument(observations),
        _guard_argument(observations),
    ]
    matrix = [
        {
            "hypothesis": row["name"],
            "status": row["status"],
            "evidence": row["evidence"],
            "gaps": row["gaps"],
            "conditions": row["conditions"],
            "post_return_only": row["post_return_only"],
        }
        for row in hypotheses
    ]
    return {
        "hypotheses": hypotheses,
        "argument_to_evidence": matrix,
        "readiness_hypotheses_admitted": False,
        "approval_receipt_establishes_semantics": False,
        "sample_outputs_establish_semantics": False,
        "version_label_establishes_semantics": False,
    }


def _git_identity(root: Path) -> tuple[str | None, str | None]:
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None, None
    return head, tree


def prepare_runtime_semantic_correspondence(root: Path) -> dict[str, object]:
    """One process/thread argument. The three readiness hypotheses stay unadmitted."""
    observations = capture_observations(root)
    classified = classify_correspondence(observations)
    head, tree = _git_identity(root)
    guard = observations.get("terminal_guard")
    return {
        "authority": {
            "frozen_head": TECHNICAL_HEAD,
            "section": "7.2",
            "runtime_certificate": "docs/cmm2_c2v09_partition_runtime_certificate.md",
            "runtime_binding_sha256": RUNTIME_BINDING_SHA256,
        },
        "measurement_implementation_head": head,
        "measurement_implementation_tree": tree,
        "record_commit_is_measurement_commit": False,
        "observations": observations,
        "arguments": classified,
        "hypotheses": classified["hypotheses"],
        "argument_to_evidence": classified["argument_to_evidence"],
        "readiness_hypotheses_admitted": False,
        "unresolved_pending_independent_review": list(_HYPOTHESES),
        "approval_receipt_establishes_semantics": False,
        "sample_outputs_establish_semantics": False,
        "version_label_establishes_semantics": False,
        "output_sampled": False,
        "cosine_function_calls": 0,
        "ulp_function_calls": 0 if not isinstance(guard, Mapping) else guard.get("ulp_function_calls"),
        "nextafter_function_calls": 0 if not isinstance(guard, Mapping) else guard.get("nextafter_function_calls"),
        "authorizes_execution": False,
        "candidate29_disposition": "NOT SELECTED",
        "eligibility_evidence": False,
        "physical_qualification": False,
        "accept_closed": True,
    }


def correspondence_document(root: Path) -> dict[str, object]:
    """Canonical digest stays outside the payload."""
    payload = prepare_runtime_semantic_correspondence(root)
    return {
        "canonical_sha256": sha256_bytes(canonical_bytes(payload)),
        "digest_scope": (
            "SHA-256 of the section 7.3 canonical bytes of canonical_payload only. "
            "canonical_sha256 and digest_scope are outside that payload."
        ),
        "canonical_payload": payload,
    }
