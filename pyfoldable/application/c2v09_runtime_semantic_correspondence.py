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


def _result_bits_stored(instructions: list[capstone.CsInsn]) -> bool:
    """A scalar result moved into a general register and stored at ob_fval."""
    moved: set[str] = set()
    for insn in instructions:
        if insn.mnemonic == "movq" and ", xmm" in insn.op_str:
            moved.add(insn.op_str.split(",", 1)[0].strip())
        if insn.mnemonic == "mov" and "+ 0x10]" in insn.op_str and "," in insn.op_str:
            if insn.op_str.split(",", 1)[1].strip() in moved:
                return True
    return False


def _store_kind(
    instructions: list[capstone.CsInsn],
    from_double: int | None,
    from_double_end: int | None = None,
) -> str:
    reaches_from = False
    inplace = False
    end = from_double + 1 if from_double is not None and from_double_end is None else from_double_end
    for insn in instructions:
        if insn.mnemonic in {"call", "jmp"} and insn.op_str.startswith("0x") and from_double is not None and end is not None:
            target = int(insn.op_str, 16)
            if from_double <= target < end:
                reaches_from = True
        if insn.mnemonic == "movsd" and "+ 0x10]" in insn.op_str and ", xmm" in insn.op_str:
            inplace = True
    stored = _result_bits_stored(instructions)
    if reaches_from and (inplace or stored):
        return "in-place ob_fval or PyFloat_FromDouble"
    if reaches_from:
        return "PyFloat_FromDouble"
    if inplace or stored:
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
            }
        )
        _attach_continuations(grouped[kind][-1])
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
    for insn in instructions:
        if insn.mnemonic == "ret" or (insn.mnemonic == "jmp" and insn.op_str.startswith("0x")):
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
        "excluded_branches": [
            {
                "target": "slow-path",
                "assumption": (
                    f"integer operands of index + 1 are in 1..{declared} because the "
                    "immutable candidate declaration sets annulus_count and index iterates below it"
                ),
            }
        ],
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


def capture_observations(root: Path) -> dict[str, object]:
    """Read this process only. Do not call cosine, nextafter, ulp or the evaluator."""
    thread_id = _thread_id()
    wrapper = _c_function_address(math.cos)
    image = None if wrapper is None else _image_of(wrapper)
    controls = _feature_record(None, None)
    probed = _probe_words(root / PROBE_SOURCE)
    if probed is not None:
        controls = _feature_record(probed[0], _fegetround())
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
    same_thread = controls.get("thread_id") == thread_id
    return {
        "pid": os.getpid(),
        "thread_id": thread_id,
        "single_process_thread": same_thread and probed is not None,
        "output_sampled": False,
        "version_label": sys.version.split()[0],
        "version_label_establishes_semantics": False,
        "approval_receipt_establishes_semantics": False,
        "sample_outputs_establish_semantics": False,
        "controls": controls,
        "arithmetic": {
            "operations": _capture_operations(),
            "generic_handlers": generic,
            "specialized_handlers": specialized,
            "specialized_scan": scan,
            "unclassified_scalar_sites": unclassified,
            "declared_annulus_count": _declared_annulus_count(root),
            "integer_add": _capture_integer_add(image or "", _declared_annulus_count(root)),
        },
        "conversion": conversion,
        "terminal_guard": observe_bound_nextafter(),
        "cosine_function_calls": 0,
        "ulp_function_calls": 0,
        "nextafter_function_calls": 0,
    }


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


def _is_store_instruction(insn: capstone.CsInsn, from_double: int | None, from_double_end: int | None) -> bool:
    if insn.mnemonic == "movsd" and "+ 0x10]" in insn.op_str and ", xmm" in insn.op_str:
        return True
    if insn.mnemonic in {"call", "jmp"} and insn.op_str.startswith("0x") and from_double is not None:
        target = int(insn.op_str, 16)
        end = from_double_end if from_double_end is not None else from_double + 1
        return from_double <= target < end
    return False


def _continuations_return(handler: Mapping[str, object], inside: set[int]) -> dict[int, int]:
    """External stubs that jump back into the claimed range. Other destinations stay unresolved."""
    rows = handler.get("continuations")
    returns: dict[int, int] = {}
    if not isinstance(rows, list):
        return returns
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        address = _hex_int(row.get("address"))
        blob = row.get("loaded_bytes_hex")
        if address is None or not isinstance(blob, str):
            continue
        try:
            instructions = _decode_complete(bytes.fromhex(blob), address)
        except ValueError:
            continue
        if not instructions or any(insn.mnemonic in _SCALAR or _is_fma(insn.mnemonic) for insn in instructions):
            continue
        last = instructions[-1]
        if last.mnemonic != "jmp" or not last.op_str.startswith("0x"):
            continue
        target = int(last.op_str, 16)
        if target in inside:
            returns[address] = target
    return returns


def _excluded_targets(handler: Mapping[str, object]) -> set[int]:
    rows = handler.get("excluded_branches")
    found: set[int] = set()
    if not isinstance(rows, list):
        return found
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        assumption = row.get("assumption")
        target = _hex_int(row.get("target"))
        if target is None or not isinstance(assumption, str) or not assumption:
            continue
        found.add(target)
    return found


def _returning_calls(handler: Mapping[str, object]) -> set[int]:
    """Callees whose captured bytes return without another binary64 operation."""
    rows = handler.get("continuations")
    found: set[int] = set()
    if not isinstance(rows, list):
        return found
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        address = _hex_int(row.get("address"))
        blob = row.get("loaded_bytes_hex")
        if address is None or not isinstance(blob, str):
            continue
        try:
            instructions = _decode_complete(bytes.fromhex(blob), address)
        except ValueError:
            continue
        if not instructions or any(insn.mnemonic in _SCALAR or _is_fma(insn.mnemonic) for insn in instructions):
            continue
        if instructions[-1].mnemonic == "ret":
            found.add(address)
    return found


def _handler_path_status(handler: Mapping[str, object], kind: str) -> str:
    """Storage has to sit on a completed path. Claimed names are not evidence."""
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
    returns = _continuations_return(handler, inside)
    calls = _returning_calls(handler)
    excluded = _excluded_targets(handler)
    successors: dict[int, list[int]] = {}
    for index, insn in enumerate(instructions):
        mnemonic = insn.mnemonic
        next_address = insn.address + insn.size
        if mnemonic == "ret":
            continue
        if mnemonic == "call" and insn.op_str.startswith("0x"):
            target = int(insn.op_str, 16)
            end = from_double_end if from_double is not None and from_double_end is not None else None
            in_from = from_double is not None and end is not None and from_double <= target < end
            if not in_from and target not in calls:
                continue
        if mnemonic == "jmp" or (mnemonic.startswith("j") and mnemonic != "jmp"):
            if not insn.op_str.startswith("0x"):
                continue
            target = int(insn.op_str, 16)
            if target in inside:
                successors.setdefault(index, []).append(target)
            elif target in returns:
                successors.setdefault(index, []).append(returns[target])
            elif target in excluded and mnemonic != "jmp":
                pass
            if mnemonic != "jmp" and next_address in inside:
                successors.setdefault(index, []).append(next_address)
            continue
        if next_address in inside:
            successors.setdefault(index, []).append(next_address)
    by_address = {insn.address: index for index, insn in enumerate(instructions)}
    seen: set[tuple[int, int, bool, tuple[str, ...]]] = set()
    stack: list[tuple[int, int, bool, tuple[str, ...]]] = [(0, 0, False, ())]
    completed = False
    while stack:
        index, scalars, stored, moved = stack.pop()
        state = (index, scalars, stored, moved)
        if state in seen:
            continue
        seen.add(state)
        insn = instructions[index]
        next_scalars = scalars + (1 if insn.mnemonic in _SCALAR else 0)
        if next_scalars > 1:
            return NOT_ESTABLISHED
        next_moved = set(moved)
        if insn.mnemonic == "movq" and ", xmm" in insn.op_str:
            next_moved.add(insn.op_str.split(",", 1)[0].strip())
        bit_store = (
            insn.mnemonic == "mov"
            and "+ 0x10]" in insn.op_str
            and "," in insn.op_str
            and insn.op_str.split(",", 1)[1].strip() in next_moved
        )
        next_stored = stored or (
            next_scalars == 1 and (_is_store_instruction(insn, from_double, from_double_end) or bit_store)
        )
        if insn.mnemonic == "ret":
            if next_scalars == 1 and next_stored:
                completed = True
            continue
        packed = tuple(sorted(next_moved))
        for target in successors.get(index, []):
            stack.append((by_address[target], next_scalars, next_stored, packed))
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
    has_add = any(insn.mnemonic == "add" and "," in insn.op_str and not insn.op_str.endswith(", 1") for insn in instructions)
    has_bound = any(insn.mnemonic == "cmp" and "0xf" in insn.op_str for insn in instructions)
    rows = handler.get("excluded_branches")
    assumption_ok = isinstance(rows, list) and any(
        isinstance(row, Mapping)
        and "integer" in str(row.get("assumption"))
        and str(declared) in str(row.get("assumption"))
        for row in rows
    )
    if has_add and has_bound and assumption_ok:
        return ESTABLISHED_CONDITIONALLY
    return NOT_ESTABLISHED


def _mixed_conversion_bound(arithmetic: Mapping[str, object], kind: str) -> bool:
    handlers = arithmetic.get("generic_handlers")
    declared = arithmetic.get("declared_annulus_count")
    if not isinstance(handlers, Mapping) or isinstance(declared, bool) or not isinstance(declared, int):
        return False
    handler = handlers.get(kind)
    if not isinstance(handler, Mapping) or _handler_status(handler, kind) != ESTABLISHED_CONDITIONALLY:
        return False
    rows = handler.get("conversion_continuations")
    if not isinstance(rows, list) or not rows:
        rows = handler.get("continuations")
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        address = _hex_int(row.get("address"))
        blob = row.get("loaded_bytes_hex")
        if address is None or not isinstance(blob, str):
            continue
        try:
            instructions = _decode_complete(bytes.fromhex(blob), address)
        except ValueError:
            continue
        if (
            instructions
            and instructions[-1].mnemonic == "ret"
            and any(insn.mnemonic in {"cvtsi2sd", "vcvtsi2sd"} for insn in instructions)
            and not any(insn.mnemonic in _SCALAR or _is_fma(insn.mnemonic) for insn in instructions)
        ):
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
            gaps.append(f"generic {kind} handler does not show one scalar operation and a float store on the completed path")
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
                    gaps.append(f"specialized {kind} site is not a separate binary64 operation")
                    status = NOT_ESTABLISHED
                else:
                    evidence.append(f"specialized {kind} at {site.get('scalar_address', site.get('address'))}: {_decoded_store(site)}")
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


def _fromdouble_stores_result(instructions: list[capstone.CsInsn]) -> bool:
    return _result_bits_stored(instructions)


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
        if _fromdouble_stores_result(fromdouble):
            evidence.append("PyFloat_FromDouble bytes store the binary64 result")
        else:
            gaps.append("PyFloat_FromDouble bytes do not store the result at ob_fval")
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
    stub_text = guard.get("plt_stub_bytes_hex")
    plt_address = _hex_int(guard.get("plt_address"))
    selected = _hex_int(guard.get("selected_address"))
    stub_bytes = b""
    if isinstance(stub_text, str):
        try:
            stub_bytes = bytes.fromhex(stub_text)
        except ValueError:
            stub_bytes = b""
    if (
        plt_address is None
        or selected is None
        or not stub_bytes
        or not nextafter_got_resolved(plt_address, selected, stub_bytes)
    ):
        gaps.append("the nextafter GOT is unresolved, so the selected implementation bytes are not bound")
    if guard.get("independent_symbol_establishes_selected_path") is not False:
        gaps.append("an independent symbol lookup was treated as the selected path")
    if guard.get("unchanged_guard_ulps") != 2 or guard.get("allowance_recomputed") is not False:
        gaps.append("the two-ULP guard allowance was recomputed or replaced")
    if not _controls_ok(observations):
        gaps.append("required numerical controls were not observed on this process and thread")
    status = ESTABLISHED_CONDITIONALLY if not gaps else NOT_ESTABLISHED
    conditions = [
        "the value is a positive normal strictly below its binade endpoint",
        "the certificate's required binade, not a sampled ulp, is the one under that endpoint",
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
    return argument


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
