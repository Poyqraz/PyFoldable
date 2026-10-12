"""Bounded PyFloat_FromDouble result-storage evidence.

This module reads one LD_BIND_NOW process. It does not call the evaluator,
motor, BEM source, mapper, partition, selection, seal, or trajectory, and it
does not admit the readiness hypotheses. Archived addresses are not evidence.
"""

from __future__ import annotations

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

from pyfoldable.application.c2v09_cosine_path_certificate import (
    PROBE_SOURCE,
    _c_function_address,
    _elf_bytes,
    _fegetround,
    _feature_record,
    _probe_words,
    _readable_process_bytes,
    _runtime_to_vaddr,
    _section,
    _symbol_text,
)
from pyfoldable.application.c2v09_ordered_declaration import (
    CANDIDATE29_DISPOSITION,
    canonical_bytes,
    sha256_bytes,
)
from pyfoldable.application.c2v09_runtime_semantic_correspondence import (
    NOT_ESTABLISHED,
    _decode_complete,
    _defined_symbol,
    _direct_target,
    _git_identity,
    _image_of,
    _symbol_runtime,
)

_MAX_SYMBOL_BYTES = 512
_PREFIX_BUDGET = 64
_NOT_A_SUCCESS = "not_a_successful_result"


def _thread_id() -> str:
    native = getattr(threading, "get_native_id", None)
    return str(native() if native is not None else threading.get_ident())


def _defined_by_vaddr(path: str) -> dict[int, tuple[str, int]]:
    """Exact dynsym value match. A name is recorded only when the table has it."""
    data = Path(path).read_bytes()
    symbols = _section(data, ".dynsym")
    strings = _section(data, ".dynstr")
    found: dict[int, tuple[str, int]] = {}
    if symbols is None or strings is None or symbols[9] != 24:
        return found
    for index in range(symbols[5] // 24):
        name_index, _info, _other, section, value, size = struct.unpack_from(
            "<IBBHQQ", data, symbols[4] + index * 24
        )
        if section == 0 or not value:
            continue
        name = _symbol_text(data, strings, name_index)
        if not name:
            continue
        current = found.get(int(value))
        if current is None or (current[1] <= 0 < int(size)):
            found[int(value)] = (name, int(size))
    return found


def _instruction_rows(instructions: list[capstone.CsInsn]) -> list[dict[str, object]]:
    return [
        {
            "address": hex(insn.address),
            "bytes": insn.bytes.hex(),
            "mnemonic": insn.mnemonic,
            "operands": insn.op_str,
        }
        for insn in instructions
    ]


def _in_span(address: int, start: int, end: int) -> bool:
    return start <= address < end


def _control(insn: capstone.CsInsn) -> bool:
    return insn.mnemonic == "ret" or insn.mnemonic.startswith("j")


def _carrier(instructions: list[capstone.CsInsn]) -> tuple[str, int] | None:
    for insn in instructions:
        if insn.mnemonic == "movq" and insn.op_str.endswith(", xmm0") and insn.op_str.startswith("r"):
            register = insn.op_str.split(",", 1)[0].strip()
            return register, insn.address
    return None


def _writes_register(insn: capstone.CsInsn, register: str) -> bool:
    text = insn.op_str.replace(",", " ")
    dest = text.split()[0] if text else ""
    return dest == register and insn.mnemonic not in {"push", "cmp", "test"}


def _closed_prefix(
    blob: bytes,
    address: int,
    body_start: int,
    body_end: int,
) -> tuple[list[capstone.CsInsn], str]:
    decoded = list(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64).disasm(blob, address))
    if not decoded:
        return [], "undecoded"
    for count in range(1, len(decoded) + 1):
        piece = decoded[:count]
        end = piece[-1].address + piece[-1].size
        if end - address > len(blob):
            break
        if _decode_complete(blob[: end - address], address) is None:
            continue
        leaves = False
        complete = True
        for insn in piece:
            if not _control(insn):
                continue
            target = _direct_target(insn)
            if insn.mnemonic.startswith("j") and insn.mnemonic != "jmp":
                fallthrough = insn.address + insn.size
                if not any(item.address == fallthrough for item in piece):
                    complete = False
            if insn.mnemonic == "ret":
                continue
            if target is None or not (
                _in_span(target, address, end) or _in_span(target, body_start, body_end)
            ):
                leaves = True
                complete = False
        last = piece[-1]
        if complete and not leaves and (last.mnemonic == "ret" or last.mnemonic.startswith("j")):
            return piece, "closed"
    transfer: list[capstone.CsInsn] = []
    for insn in decoded:
        transfer.append(insn)
        if _control(insn) or insn.mnemonic == "call":
            break
    return transfer, "transfer"


def _load_bytes(image: str, runtime: int, size: int) -> tuple[bytes | None, bool]:
    blob = _readable_process_bytes(runtime, size)
    if blob is None or len(blob) != size:
        return None, False
    mapped = _runtime_to_vaddr(runtime)
    file_bytes = None if mapped is None else _elf_bytes(mapped[0], mapped[1], size)
    return blob, file_bytes == blob


def _continuation_record(
    image: str,
    symbols: Mapping[int, tuple[str, int]],
    runtime: int,
    body_start: int,
    body_end: int,
) -> dict[str, object] | None:
    mapped = _runtime_to_vaddr(runtime)
    if mapped is None:
        return None
    _path, vaddr = mapped
    symbol = symbols.get(vaddr)
    if symbol is not None and 0 < symbol[1] <= _MAX_SYMBOL_BYTES:
        blob, match = _load_bytes(image, runtime, symbol[1])
        if blob is None:
            return None
        instructions = _decode_complete(blob, runtime)
        return {
            "address": hex(runtime),
            "elf_vaddr": hex(vaddr),
            "image": image,
            "symbol_name": symbol[0],
            "symbol_size": symbol[1],
            "coverage": "symbol" if instructions is not None and match else "symbol_incomplete",
            "loaded_bytes_hex": blob.hex(),
            "loaded_bytes_match_file": match,
            "disassembly": [] if instructions is None else _instruction_rows(instructions),
        }
    blob, match = _load_bytes(image, runtime, _PREFIX_BUDGET)
    if blob is None:
        return None
    piece, coverage = _closed_prefix(blob, runtime, body_start, body_end)
    if not piece:
        return None
    size = piece[-1].address + piece[-1].size - runtime
    exact, exact_match = _load_bytes(image, runtime, size)
    if exact is None:
        return None
    return {
        "address": hex(runtime),
        "elf_vaddr": hex(vaddr),
        "image": image,
        "symbol_name": None,
        "symbol_size": None,
        "coverage": coverage if exact_match else "file_mismatch",
        "loaded_bytes_hex": exact.hex(),
        "loaded_bytes_match_file": exact_match,
        "disassembly": _instruction_rows(piece),
    }


def _chase_transfers(
    image: str,
    symbols: Mapping[int, tuple[str, int]],
    records: dict[int, dict[str, object]],
    body_start: int,
    body_end: int,
) -> None:
    """Follow a straight jmp into an exact symbol. Do not follow open branches."""
    seen = set(records)
    pending = list(records)
    while pending:
        address = pending.pop()
        record = records.get(address)
        if record is None or record.get("loaded_bytes_match_file") is not True:
            continue
        rows = record.get("disassembly")
        if not isinstance(rows, list) or not rows:
            continue
        straight = True
        target = None
        for row in rows:
            if not isinstance(row, Mapping):
                straight = False
                break
            mnemonic = str(row.get("mnemonic"))
            if mnemonic == "call" or (mnemonic.startswith("j") and mnemonic != "jmp"):
                straight = False
                break
            if mnemonic == "jmp":
                operands = str(row.get("operands"))
                target = int(operands, 16) if operands.startswith("0x") else None
                break
        if not straight or target is None or target in seen or _in_span(target, body_start, body_end):
            continue
        mapped = _runtime_to_vaddr(target)
        if mapped is None or mapped[1] not in symbols:
            continue
        chased = _continuation_record(image, symbols, target, body_start, body_end)
        if chased is None:
            continue
        records[target] = chased
        seen.add(target)
        pending.append(target)


def _capture_continuations(
    image: str,
    instructions: list[capstone.CsInsn],
    body_start: int,
    body_end: int,
) -> list[dict[str, object]]:
    symbols = _defined_by_vaddr(image)
    records: dict[int, dict[str, object]] = {}
    for insn in instructions:
        if not _control(insn) and insn.mnemonic != "call":
            continue
        target = _direct_target(insn)
        if target is None or _in_span(target, body_start, body_end) or target in records:
            continue
        record = _continuation_record(image, symbols, target, body_start, body_end)
        if record is not None:
            records[target] = record
    _chase_transfers(image, symbols, records, body_start, body_end)
    return [records[key] for key in sorted(records)]


def _decoded_continuations(
    rows: list[dict[str, object]],
) -> dict[int, list[capstone.CsInsn]]:
    found: dict[int, list[capstone.CsInsn]] = {}
    for row in rows:
        if row.get("loaded_bytes_match_file") is not True or row.get("coverage") in {"symbol_incomplete", "file_mismatch", "undecoded"}:
            continue
        address = int(str(row["address"]), 16)
        blob = bytes.fromhex(str(row["loaded_bytes_hex"]))
        instructions = _decode_complete(blob, address)
        if instructions is not None:
            found[address] = instructions
    return found


def _rip_sites(instructions: list[capstone.CsInsn], image: str) -> list[dict[str, object]]:
    sites: list[dict[str, object]] = []
    for insn in instructions:
        text = insn.op_str
        if "rip + " not in text and "rip - " not in text:
            continue
        sign = -1 if "rip - " in text else 1
        marker = "rip - " if sign < 0 else "rip + "
        token = text[text.find(marker) + len(marker):].split("]", 1)[0].split()[0]
        if not token.startswith("0x"):
            continue
        address = insn.address + insn.size + sign * int(token, 16)
        width = 1 if insn.mnemonic == "test" and "byte ptr" in text else 4 if "dword ptr" in text else 8
        blob, match = _load_bytes(image, address, width)
        mapped = _runtime_to_vaddr(address)
        sites.append(
            {
                "instruction": hex(insn.address),
                "address": hex(address),
                "width": width,
                "loaded_bytes_hex": None if blob is None else blob.hex(),
                "loaded_bytes_match_file": match,
                "elf_vaddr": None if mapped is None else hex(mapped[1]),
                "image": image,
            }
        )
    return sites


def _edge_role(
    instructions: list[capstone.CsInsn],
    index: int,
    carrier: str | None,
) -> str:
    insn = instructions[index]
    previous = instructions[index - 1] if index else None
    if insn.mnemonic == "call":
        if previous is not None and previous.mnemonic == "mov" and previous.op_str.startswith("edi, 0x"):
            return "allocation_call"
        return "reference_call" if carrier is not None else "call"
    if insn.mnemonic in {"je", "jz"} and previous is not None and previous.mnemonic == "test":
        if previous.op_str.replace(" ", "") in {"rax,rax", "eax,eax"}:
            return "allocation_null"
        if "byte ptr [rip" in previous.op_str:
            return "type_flag"
        return "free_list_miss"
    if insn.mnemonic.startswith("j") and previous is not None and previous.mnemonic == "test" and "byte ptr [rip" in previous.op_str:
        return "type_flag"
    if insn.mnemonic == "jmp":
        return "cold_transfer"
    if insn.mnemonic == "ret":
        return "return"
    return "branch"


def _zeroes_eax(insn: capstone.CsInsn) -> bool:
    compact = insn.op_str.replace(" ", "")
    return insn.mnemonic == "xor" and compact in {"eax,eax", "rax,rax"}


def _locate_continuation(
    continuations: Mapping[int, list[capstone.CsInsn]],
    target: int,
) -> tuple[int, int] | None:
    for base, instructions in continuations.items():
        if not instructions:
            continue
        end = instructions[-1].address + instructions[-1].size
        if not _in_span(target, base, end):
            continue
        for index, insn in enumerate(instructions):
            if insn.address == target:
                return base, index
        return None
    return None


def _continuation_walk(
    continuations: Mapping[int, list[capstone.CsInsn]],
    entry: int,
    body_start: int,
    body_end: int,
) -> dict[str, object]:
    null_return = False
    rejoins: list[str] = []
    unresolved: list[str] = []
    calls: list[str] = []
    seen: set[tuple[int, int, bool]] = set()
    stack = [(entry, 0, False)]
    while stack:
        base, index, zeroed = stack.pop()
        instructions = continuations.get(base)
        key = (base, index, zeroed)
        if key in seen:
            continue
        seen.add(key)
        if instructions is None or index >= len(instructions):
            unresolved.append(hex(base))
            continue
        insn = instructions[index]
        next_zeroed = zeroed or _zeroes_eax(insn)
        if insn.mnemonic == "ret":
            if next_zeroed:
                null_return = True
            continue
        if insn.mnemonic == "call":
            calls.append(hex(insn.address))
            stack.append((base, index + 1, next_zeroed))
            continue
        if insn.mnemonic.startswith("j"):
            target = _direct_target(insn)
            located = None if target is None else _locate_continuation(continuations, target)
            if target is None:
                unresolved.append(hex(insn.address))
            elif _in_span(target, body_start, body_end):
                rejoins.append(hex(target))
            elif located is not None:
                stack.append((located[0], located[1], next_zeroed))
            else:
                unresolved.append(hex(target))
            if insn.mnemonic != "jmp":
                stack.append((base, index + 1, next_zeroed))
            continue
        stack.append((base, index + 1, next_zeroed))
    return {
        "null_return_reachable": null_return,
        "rejoins": sorted(set(rejoins)),
        "unresolved": sorted(set(unresolved)),
        "calls_before_return": sorted(set(calls)),
    }


def _reference_preservation(
    instructions: list[capstone.CsInsn] | None,
    carrier: str | None,
) -> str:
    if instructions is None or carrier is None:
        return "not_captured"
    writes = any(_writes_register(insn, carrier) for insn in instructions)
    call = any(insn.mnemonic == "call" for insn in instructions)
    direct_return = any(insn.mnemonic == "ret" for insn in instructions)
    if writes:
        return "carrier_written"
    if call and direct_return:
        return "preserved_on_no_call_return_call_side_unresolved"
    if direct_return and not call:
        return "preserved"
    return "unresolved"


def _edge_result(role: str, effect: Mapping[str, object] | None, internal: bool) -> str:
    if internal:
        return "stays_in_constructor"
    if role == "return":
        return "finite_return_if_carrier_preserved"
    if role == "allocation_call":
        return "callee_not_followed"
    if role == "reference_call":
        return "call_before_store"
    if effect is None:
        return "unresolved"
    rejoins = effect.get("rejoins")
    unresolved = effect.get("unresolved")
    if role == "allocation_null":
        return _NOT_A_SUCCESS
    if isinstance(rejoins, list) and rejoins and not unresolved:
        return "rejoins_store_prelude"
    if isinstance(rejoins, list) and rejoins and unresolved:
        return "rejoin_with_unresolved_sibling"
    return "unresolved"


def storage_inventory(
    body: bytes,
    address: int,
    continuation_rows: list[dict[str, object]],
    *,
    type_address: int | None = None,
    flag_sites: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Exit inventory for one loaded constructor. Failure is not a successful store."""
    instructions = _decode_complete(body, address)
    gaps = []
    if instructions is None:
        return {
            "status": NOT_ESTABLISHED,
            "readiness_admitted": False,
            "gaps": ["the constructor bytes do not decode completely"],
            "branch_table": [],
            "bit_trace": {},
            "paths": [],
            "conditions": [],
        }
    end = address + len(body)
    found = _carrier(instructions)
    carrier = None if found is None else found[0]
    carrier_at = None if found is None else found[1]
    if carrier is None:
        gaps.append("the constructor does not copy xmm0 into a full 64-bit register")
    stores = [
        insn
        for insn in instructions
        if insn.mnemonic == "mov"
        and "+ 0x10]" in insn.op_str
        and carrier is not None
        and insn.op_str.endswith(carrier)
    ]
    if not stores:
        gaps.append("the constructor does not store the captured register at offset 0x10")
    continuations = _decoded_continuations(continuation_rows)
    by_address = {int(str(row["address"]), 16): row for row in continuation_rows}
    table: list[dict[str, object]] = []
    for index, insn in enumerate(instructions):
        if not _control(insn) and insn.mnemonic != "call":
            continue
        target = _direct_target(insn)
        internal = target is not None and _in_span(target, address, end)
        role = _edge_role(instructions, index, carrier)
        record = None if target is None else by_address.get(target)
        effect = None
        if target is not None and not internal and target in continuations:
            effect = _continuation_walk(continuations, target, address, end)
        result = _edge_result(role, effect, internal)
        if role == "allocation_null" and result == "finite_return_if_carrier_preserved":
            result = _NOT_A_SUCCESS
        symbol_name = None if record is None else record.get("symbol_name")
        table.append(
            {
                "address": hex(insn.address),
                "bytes": insn.bytes.hex(),
                "mnemonic": insn.mnemonic,
                "operands": insn.op_str,
                "target": None if target is None else hex(target),
                "role": role,
                "symbol_name": symbol_name,
                "continuation_coverage": None if record is None else record.get("coverage"),
                "continuation_matches_file": None if record is None else record.get("loaded_bytes_match_file"),
                "result": result,
                "null_return_reachable": False if effect is None else effect.get("null_return_reachable"),
                "rejoins": [] if effect is None else effect.get("rejoins"),
                "unresolved": [] if effect is None else effect.get("unresolved"),
            }
        )
    reference = next((row for row in table if row["role"] == "reference_call"), None)
    reference_body = None
    if reference is not None and reference.get("target") is not None:
        reference_body = continuations.get(int(str(reference["target"]), 16))
    preservation = _reference_preservation(reference_body, carrier)
    if preservation != "preserved":
        gaps.append(
            "preservation of the captured binary64 bits across the reference call is not established for every path"
        )
    nulls = [row for row in table if row["role"] == "allocation_null"]
    if not nulls:
        gaps.append("no allocation-null test was decoded, so a failed allocation is not a closed exit")
    for row in nulls:
        if row["result"] != _NOT_A_SUCCESS:
            gaps.append("the allocation-null edge is not classified as a non-result")
        if not row.get("null_return_reachable"):
            gaps.append("the allocation-null continuation does not show a captured null return")
        if row.get("unresolved"):
            gaps.append("the allocation-failure continuation still has an unresolved sibling")
    if any(row["role"] == "allocation_call" for row in table):
        gaps.append("the allocation callee's internal exits are outside this result-storage argument")
    type_immediates = []
    for insn in instructions:
        if insn.mnemonic == "mov" and "+ 8]" in insn.op_str:
            token = insn.op_str.split(",")[-1].strip()
            if token.startswith("0x"):
                type_immediates.append(int(token, 16))
    type_equal = type_address is not None and bool(type_immediates) and all(item == type_address for item in type_immediates)
    if type_address is None or not type_equal:
        gaps.append("the stored type immediate is not tied to the PyFloat_Type symbol in this process")
    flags = [] if flag_sites is None else flag_sites
    if any(site.get("loaded_bytes_match_file") is not True for site in flags):
        gaps.append("a rip-relative flag byte does not match the file image")
    finite = bool(stores) and carrier is not None and any(row["role"] == "return" for row in table)
    paths = []
    if finite:
        paths.append(
            {
                "name": "finite_store",
                "result": "finite_store_under_conditions",
                "store": hex(stores[0].address),
                "carrier": carrier,
                "conditions": [
                    "the constructor received the binary64 bits in xmm0",
                    "allocation or the free list produced an object",
                    "the reference call returned",
                    "the captured register still held those bits at the store",
                ],
            }
        )
    if nulls:
        paths.append(
            {
                "name": "allocation_failure",
                "result": _NOT_A_SUCCESS,
                "null_return_reachable": any(row.get("null_return_reachable") is True for row in nulls),
                "unresolved_sibling": any(bool(row.get("unresolved")) for row in nulls),
                "conditions": [
                    "a captured fallthrough that clears eax and returns is not a float result",
                    "calls on that fallthrough are assumed to return only where the bytes show the later xor",
                    "a sibling branch without a captured body remains unresolved",
                ],
            }
        )
    status = "ESTABLISHED CONDITIONALLY" if finite and not gaps else NOT_ESTABLISHED
    return {
        "status": status,
        "readiness_admitted": False,
        "gaps": gaps,
        "branch_table": table,
        "disassembly": _instruction_rows(instructions),
        "bit_trace": {
            "source": "xmm0",
            "carrier": carrier,
            "capture": None if carrier_at is None else hex(carrier_at),
            "store": None if not stores else hex(stores[0].address),
            "store_operands": None if not stores else stores[0].op_str,
            "reference_preservation": preservation,
            "returned_register": "rax",
        },
        "type_immediate": {
            "values": [hex(item) for item in type_immediates],
            "pyfloat_type": None if type_address is None else hex(type_address),
            "equal": type_equal,
        },
        "flag_sites": flags,
        "paths": paths,
        "conditions": [
            "finite storage is conditional on a non-null object and on the captured bits surviving until the store",
            "the allocation-null path is not a successful result",
            "post-return validation of the object is outside this package",
            "which operand reached xmm0 is outside this package",
        ],
    }


def _inventory_from_observation(observation: Mapping[str, object]) -> dict[str, object]:
    constructor = observation.get("constructor")
    rows = observation.get("continuations")
    if not isinstance(constructor, Mapping) or not isinstance(rows, list):
        return storage_inventory(b"", 0, [])
    blob = bytes.fromhex(str(constructor.get("loaded_bytes_hex") or ""))
    address = int(str(constructor.get("address")), 16)
    clean_rows = [row for row in rows if isinstance(row, dict)]
    type_address = observation.get("pyfloat_type_address")
    parsed = int(str(type_address), 16) if isinstance(type_address, str) else None
    flags = observation.get("flag_sites")
    return storage_inventory(
        blob,
        address,
        clean_rows,
        type_address=parsed,
        flag_sites=[site for site in flags if isinstance(site, dict)] if isinstance(flags, list) else [],
    )


def capture_fromdouble_storage_here(root: Path) -> dict[str, object]:
    """Read this process only. Do not sample a float result or call cosine."""
    pid = os.getpid()
    thread_id = _thread_id()
    probed = _probe_words(root / PROBE_SOURCE)
    controls = _feature_record(None if probed is None else probed[0], _fegetround())
    controls["pid"] = pid
    controls["bind_now"] = os.environ.get("LD_BIND_NOW") == "1"
    wrapper = _c_function_address(math.cos)
    image = None if wrapper is None else _image_of(wrapper)
    head, tree = _git_identity(root)
    located = None if image is None else _symbol_runtime(image, "PyFloat_FromDouble")
    type_symbol = None if image is None else _symbol_runtime(image, "PyFloat_Type")
    gaps = []
    constructor: dict[str, object] = {}
    continuations: list[dict[str, object]] = []
    inventory: dict[str, object] = {
        "status": NOT_ESTABLISHED,
        "readiness_admitted": False,
        "gaps": ["PyFloat_FromDouble was not located in this process"],
        "branch_table": [],
        "paths": [],
    }
    if image is None or located is None:
        gaps.append("PyFloat_FromDouble was not located in this process")
    else:
        runtime, vaddr, size = located
        blob, match = _load_bytes(image, runtime, size)
        symbol = _defined_symbol(image, "PyFloat_FromDouble")
        if blob is None or symbol is None:
            gaps.append("the constructor bytes could not be read")
        else:
            instructions = _decode_complete(blob, runtime)
            constructor = {
                "address": hex(runtime),
                "end": hex(runtime + size),
                "elf_vaddr": hex(vaddr),
                "image": image,
                "symbol_name": "PyFloat_FromDouble",
                "symbol_size": size,
                "loaded_bytes_hex": blob.hex(),
                "loaded_bytes_match_file": match,
                "file_symbol_vaddr": hex(symbol[0]),
            }
            if instructions is None or not match:
                gaps.append("the constructor bytes do not match the file or do not decode")
            else:
                continuations = _capture_continuations(image, instructions, runtime, runtime + size)
                flag_sites = _rip_sites(instructions, image)
                inventory = storage_inventory(
                    blob,
                    runtime,
                    continuations,
                    type_address=None if type_symbol is None else type_symbol[0],
                    flag_sites=flag_sites,
                )
    if controls.get("classification") != "OBSERVED" or controls.get("required_bits_ok") is not True:
        gaps.append("required numerical controls were not observed in this process")
    if controls.get("thread_id") != thread_id:
        gaps.append("controls are not from this thread")
    combined = list(dict.fromkeys([*inventory.get("gaps", []), *gaps])) if isinstance(inventory.get("gaps"), list) else gaps
    status = NOT_ESTABLISHED if combined else inventory.get("status", NOT_ESTABLISHED)
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
        "bind_now": controls.get("bind_now") is True,
        "pid": pid,
        "thread_id": thread_id,
        "single_process_thread": controls.get("thread_id") == thread_id and probed is not None,
        "controls": controls,
        "archived_reference_not_evidence": {
            "constructor": "0x556110",
            "store": "0x556166",
            "used_as_evidence": False,
        },
        "constructor": constructor,
        "pyfloat_type_address": None if type_symbol is None else hex(type_symbol[0]),
        "flag_sites": inventory.get("flag_sites", []),
        "continuations": continuations,
        "inventory": inventory,
        "status": status,
        "gaps": combined,
    }


def capture_fromdouble_storage(root: Path) -> dict[str, object]:
    """One LD_BIND_NOW process. This process's controls are not reused for another pid."""
    if os.environ.get("LD_BIND_NOW") != "1":
        script = (
            "import json, sys\n"
            "from pathlib import Path\n"
            "from pyfoldable.application.c2v09_fromdouble_storage import capture_fromdouble_storage_here\n"
            "print(json.dumps(capture_fromdouble_storage_here(Path(sys.argv[1]))))\n"
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
            return {
                "status": NOT_ESTABLISHED,
                "readiness_hypotheses_admitted": False,
                "accept_closed": True,
                "candidate29_disposition": CANDIDATE29_DISPOSITION,
                "eligibility_evidence": False,
                "physical_qualification": False,
                "bind_now": False,
                "pid": None,
                "gaps": ["the bound process did not return an observation"],
                "inventory": {"branch_table": [], "paths": [], "status": NOT_ESTABLISHED},
            }
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            parsed = None
        if not isinstance(parsed, dict) or parsed.get("bind_now") is not True or parsed.get("pid") is None:
            return {
                "status": NOT_ESTABLISHED,
                "readiness_hypotheses_admitted": False,
                "accept_closed": True,
                "candidate29_disposition": CANDIDATE29_DISPOSITION,
                "eligibility_evidence": False,
                "physical_qualification": False,
                "bind_now": False,
                "pid": None,
                "gaps": ["the bound observation was not from one LD_BIND_NOW process"],
                "inventory": {"branch_table": [], "paths": [], "status": NOT_ESTABLISHED},
            }
        return parsed
    return capture_fromdouble_storage_here(root)


def fromdouble_storage_document(root: Path) -> dict[str, object]:
    payload = capture_fromdouble_storage(root)
    return {
        "canonical_sha256": sha256_bytes(canonical_bytes(payload)),
        "digest_scope": (
            "SHA-256 of the section 7.3 canonical bytes of canonical_payload only. "
            "canonical_sha256 and digest_scope are outside that payload."
        ),
        "canonical_payload": payload,
    }
