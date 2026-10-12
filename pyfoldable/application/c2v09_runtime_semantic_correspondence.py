"""Scoped argument for the three remaining pre-call semantic hypotheses.

Observations are loaded bytes, addresses and control state. A version label,
a sample output or a self-issued receipt does not establish them. This module
does not admit the hypotheses and does not call the evaluator, source, mapper,
partition, selection, seal or trajectory.
"""

from __future__ import annotations

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
from pyfoldable.application.c2v09_declared_operations import ARITHMETIC_QUALNAMES, arithmetic_operation_record
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
        blob = _readable_process_bytes(address, length)
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
    return handlers


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
        grouped[kind].append(
            {
                "kind": kind,
                "address": hex(insn.address),
                "elf_vaddr": hex(vaddr + (insn.address - runtime)),
                "image": image,
                "loaded_bytes_hex": None if window is None else window.hex(),
                "loaded_bytes_match_file": True,
                "scalar_mnemonics": [insn.mnemonic],
                "paths_execute_one_scalar_op": True,
                "fma_mnemonics": [],
                "store": "in-place ob_fval or PyFloat_FromDouble" if inplace else "PyFloat_FromDouble",
                "ob_fval_load": True,
                "from_double_address": None if from_double is None else hex(from_double),
                "from_double_end": None if from_double_end is None else hex(from_double_end),
                "decoder": "capstone",
                "decoder_version": capstone.__version__,
                "mode": "64-bit",
                "coverage": "complete",
            }
        )
    return grouped, "complete", unclassified


def _capture_operations() -> list[dict[str, object]]:
    rows = []
    for qualname in ARITHMETIC_QUALNAMES:
        record = arithmetic_operation_record(qualname)
        opcodes = record.get("opcodes")
        if not isinstance(opcodes, list):
            opcodes = []
        kinds = [_KIND_BY_OPCODE[text] for text in opcodes if isinstance(text, str) and text in _KIND_BY_OPCODE]
        rows.append(
            {
                "qualname": qualname,
                "opcodes": opcodes,
                "kinds": kinds,
                "bytecode_window_establishes_semantics": False,
                "output_sampled": False,
            }
        )
    return rows


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
    wrapper_blob = _readable_process_bytes(wrapper, 0x120)
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
    return {
        "wrapper_calls_defined_symbol": calls_symbol,
        "loaded_bytes_match_file": True,
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
        },
        "conversion": conversion,
        "terminal_guard": _capture_terminal_guard(image or ""),
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


def _instructions_from_handler(handler: Mapping[str, object]) -> list[capstone.CsInsn] | None:
    blob = handler.get("loaded_bytes_hex")
    address = handler.get("address")
    if not isinstance(blob, str) or not blob or not isinstance(address, str):
        return None
    try:
        instructions = _cut_at_next_function(_disassemble(bytes.fromhex(blob), int(address, 16)))
    except ValueError:
        return None
    return instructions or None


def _handler_status(handler: Mapping[str, object], kind: str) -> str:
    has_bytes = isinstance(handler.get("loaded_bytes_hex"), str) and bool(handler.get("loaded_bytes_hex"))
    instructions = _instructions_from_handler(handler)
    if has_bytes and not instructions:
        return NOT_ESTABLISHED
    if instructions is not None:
        mnemonics = [insn.mnemonic for insn in instructions if insn.mnemonic in _SCALAR]
        fma = [insn.mnemonic for insn in instructions if _is_fma(insn.mnemonic)]
        one_path = _one_scalar_per_path(instructions)
        loads_ob_fval = any(insn.mnemonic == "movsd" and "+ 0x10]" in insn.op_str for insn in instructions)
        from_double_text = handler.get("from_double_address")
        end_text = handler.get("from_double_end")
        try:
            from_double = int(from_double_text, 16) if isinstance(from_double_text, str) else None
            from_double_end = int(end_text, 16) if isinstance(end_text, str) else None
        except ValueError:
            from_double = None
            from_double_end = None
        store = _store_kind(instructions, from_double, from_double_end)
    else:
        claimed = handler.get("scalar_mnemonics")
        mnemonics = [str(item) for item in claimed] if isinstance(claimed, list) else []
        claimed_fma = handler.get("fma_mnemonics")
        fma = [str(item) for item in claimed_fma] if isinstance(claimed_fma, list) else []
        one_path = handler.get("paths_execute_one_scalar_op")
        loads_ob_fval = handler.get("ob_fval_load") is True
        store = handler.get("store")
    if fma:
        return MISMATCHED
    if not mnemonics or any(_KIND_BY_MNEMONIC.get(item) != kind for item in mnemonics):
        return MISMATCHED if mnemonics else NOT_ESTABLISHED
    if one_path is not True or loads_ob_fval is not True or handler.get("loaded_bytes_match_file") is not True:
        return NOT_ESTABLISHED
    if store not in {"PyFloat_FromDouble", "in-place ob_fval", "in-place ob_fval or PyFloat_FromDouble", "ob_fval"}:
        return NOT_ESTABLISHED
    return ESTABLISHED_CONDITIONALLY


def nextafter_got_resolved(target: int, qword: int, stub: bytes) -> bool:
    """An unresolved PLT slot, including an endbr64 stub, is not the selected body."""
    if not stub or qword == 0:
        return False
    prefix = 4 if stub.startswith(b"\xf3\x0f\x1e\xfa") else 0
    if qword == target or qword == target + prefix + 6 or target <= qword < target + len(stub):
        return False
    return plt_got_address(stub, target) is not None


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
    for row in operations:
        if not isinstance(row, Mapping) or row.get("bytecode_window_establishes_semantics") is not False:
            gaps.append("a bytecode window was treated as the arithmetic semantics")
            return _argument(name, NOT_ESTABLISHED, gaps, evidence, [])
        row_kinds = row.get("kinds")
        if not isinstance(row_kinds, list) or not row_kinds:
            gaps.append(f"{row.get('qualname')} has no bound binary operation")
            return _argument(name, NOT_ESTABLISHED, gaps, evidence, [])
        kinds.extend(str(item) for item in row_kinds)
        evidence.append(f"{row.get('qualname')}: {', '.join(str(item) for item in row_kinds)}")
    status = ESTABLISHED_CONDITIONALLY
    for kind in sorted(set(kinds)):
        handler = generic.get(kind)
        if not isinstance(handler, Mapping):
            gaps.append(f"generic {kind} handler was not read")
            status = NOT_ESTABLISHED
            continue
        handler_status = _handler_status(handler, kind)
        if handler_status == MISMATCHED:
            return _argument(name, MISMATCHED, [f"generic {kind} handler is not one separate binary64 operation"], evidence, [])
        if handler_status != ESTABLISHED_CONDITIONALLY:
            gaps.append(f"generic {kind} handler does not show one scalar operation and a float store")
            status = NOT_ESTABLISHED
        else:
            evidence.append(f"generic {kind}: {', '.join(str(item) for item in handler.get('scalar_mnemonics') or [])} -> {handler.get('store')}")
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
                    evidence.append(f"specialized {kind} at {site.get('address')}: {site.get('store')}")
    if not _controls_ok(observations):
        gaps.append("required numerical controls were not observed on this process and thread")
        status = NOT_ESTABLISHED
    conditions = [
        "each consumed Python add, subtract, multiply and divide is a separate scalar binary64 operation",
        "generic and specialized paths store one binary64 float result and do not fuse across Python operations",
        "controls stay RNE, DAZ off and FTZ off in this process and thread",
    ]
    post_return = [
        "POST-RETURN ONLY: the actual operand objects passed by the returned source are not observed before that return",
    ]
    if status != ESTABLISHED_CONDITIONALLY:
        conditions = []
    return _argument(name, status, gaps, evidence, post_return, conditions)


def _conversion_argument(observations: Mapping[str, object]) -> dict[str, object]:
    name = _HYPOTHESES[1]
    conversion = observations.get("conversion")
    if not isinstance(conversion, Mapping):
        return _argument(name, NOT_ESTABLISHED, ["conversion observations are missing"], [], [])
    evidence = []
    gaps = []
    if conversion.get("wrapper_calls_defined_symbol") is True and conversion.get("loaded_bytes_match_file") is True:
        evidence.append(f"wrapper calls defined PyFloat_AsDouble at {conversion.get('symbol_address')}")
    else:
        gaps.append("the cosine wrapper's PyFloat_AsDouble call is not bound to the defined symbol")
    if conversion.get("builtin_float_path") == "movsd [obj+0x10]; ret" and conversion.get("fast_path_has_no_convert") is True:
        evidence.append("builtin-float path loads the stored binary64 and returns it")
    else:
        gaps.append("the builtin-float path was not isolated from a converting path")
    if conversion.get("finite_result_store") == "PyFloat_FromDouble":
        evidence.append("wrapper finite result is stored by PyFloat_FromDouble")
    else:
        gaps.append("finite-result storage from the wrapper was not traced")
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


def _guard_argument(observations: Mapping[str, object]) -> dict[str, object]:
    name = _HYPOTHESES[2]
    guard = observations.get("terminal_guard")
    if not isinstance(guard, Mapping):
        return _argument(name, NOT_ESTABLISHED, ["terminal-guard observations are missing"], [], [])
    evidence = []
    gaps = []
    if guard.get("ulp_function_calls") != 0 or guard.get("nextafter_function_calls") != 0 or guard.get("output_sampled") is not False:
        gaps.append("a nextafter or ulp sample was treated as the semantics")
    if guard.get("wrapper_matches_file") is True and guard.get("wrapper_calls_nextafter_plt") is True:
        evidence.append("math.ulp wrapper calls nextafter through its loaded PLT stub")
    else:
        gaps.append("the loaded math.ulp wrapper call was not matched to nextafter")
    if guard.get("wrapper_subtraction") == "subsd":
        evidence.append("wrapper contains subsd after the nextafter call")
    else:
        gaps.append("the wrapper subtraction was not decoded")
    if guard.get("got_resolved") is not True:
        gaps.append("the nextafter GOT is unresolved, so the selected implementation bytes are not bound")
    elif guard.get("selected_body_bound") is not True:
        gaps.append("the resolved nextafter bytes do not match the mapped file")
    elif guard.get("integer_increment_in_selected_body") is not True:
        gaps.append("the selected nextafter body does not show an integer increment of a positive normal")
    else:
        evidence.append(f"selected nextafter at {guard.get('selected_address')} increments the integer bit pattern")
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
