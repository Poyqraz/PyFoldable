"""Certificate for one process's Python math wrapper and selected cosine target.

The selected target is the qword loaded by that wrapper's cos PLT slot.
An independent libm symbol lookup is recorded beside it and is not evidence.
"""

from __future__ import annotations

import ctypes
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Mapping

import capstone
from capstone import CS_ARCH_X86, CS_MODE_64, Cs, CsError

from pyfoldable.application.c2v09_binding_collector import read_loaded_vaddr
from pyfoldable.application.c2v09_ordered_declaration import (
    RUNTIME_BINDING_SHA256,
    canonical_bytes,
    sha256_bytes,
)


CERTIFICATE_PATH = "docs/cmm2_c2v09_partition_runtime_certificate.md"
CERTIFICATE_FILE_SHA256 = "d0c9196a747ad2e49f94bb264e33bca95eec0a20e1bc900dc1bd5442d0ef5b35"
HISTORICAL_BODY_SHA256 = "f7a54037fbab80cbbf5a2c6954284f47330d936b103a0beac05913b6b1949a02"
HISTORICAL_EXECUTABLE_SHA256 = "fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7"
HISTORICAL_BODY_LENGTH = 0x155
PROBE_SOURCE = "pyfoldable/application/c2v09_cosine_path_probe.c"
IMPLEMENTATION_SOURCE = "pyfoldable/application/c2v09_cosine_path_certificate.py"
UNPARSED_STUB_METHOD = (
    "The PLT stub is not jmp [rip+disp32], with or without a leading endbr64. "
    "Disassemble that stub and record its GOT encoding. LD_BIND_NOW does not repair an unrecognized stub."
)
DIGEST_SCOPE = (
    "SHA-256 of the section 7.3 canonical bytes of canonical_payload only. "
    "canonical_sha256 and digest_scope are outside that payload."
)
_CALL = re.compile(r"^\s*[0-9a-f]+:.*\bcall\s+([0-9a-f]+)\s+<([^>]+)>", re.IGNORECASE)


def xcr0_read_permitted(leaf1_ecx: int, leaf7_ecx: int) -> bool:
    """XGETBV is permitted only when CPUID leaf 1 ECX OSXSAVE is set.

    The leaf 7 ECX argument is accepted so a set bit 27 there cannot be mistaken
    for OSXSAVE. It does not authorize the instruction.
    """
    del leaf7_ecx
    return (int(leaf1_ecx) & (1 << 27)) != 0


def attribute_loaded_wrapper(
    *,
    raw_selected: dict[str, object],
    loaded_wrapper: bytes | None,
    elf_wrapper: bytes | None,
    body_sha: str | None,
    constant_rows: list[dict[str, object]],
    features_observed: bool,
    required_bits: bool,
    body_vaddr: str | None,
    historical_vaddr: str,
) -> dict[str, object]:
    """Certify a disk PLT/GOT path only after the executing wrapper matches that ELF.

    A missing or different loaded wrapper leaves a resolved GOT pointer as a raw
    observation. It is not that wrapper's selected target, and the libm body
    argument stays blocked. An unresolved PLT result is left unchanged.
    """
    matches = loaded_wrapper is not None and elf_wrapper is not None and loaded_wrapper == elf_wrapper
    selected = dict(raw_selected)
    if not matches and selected.get("classification") == "OBSERVED":
        selected["raw_got_pointer"] = selected.get("address")
        selected["classification"] = "NOT ESTABLISHED"
        selected["address"] = None
        selected["method"] = (
            "Loaded math.cos wrapper bytes are missing or do not match the ELF bytes used for disassembly. "
            "The GOT qword remains a raw observation and is not certified as that wrapper's selected target."
        )
    return {
        "loaded_wrapper_matches_elf": matches,
        "selected_call_target": selected,
        "libm_body_argument": libm_body_verdict(
            selected_observed=matches and selected.get("classification") == "OBSERVED",
            features_observed=features_observed,
            body_sha=body_sha,
            constant_rows=constant_rows,
            required_bits=required_bits,
            body_vaddr=body_vaddr,
            historical_vaddr=historical_vaddr,
        ),
    }


def plt_got_address(stub: bytes, stub_address: int) -> int | None:
    """Runtime address of the qword used by jmp [rip+disp32], after an optional endbr64."""
    offset = 4 if stub.startswith(b"\xf3\x0f\x1e\xfa") else 0
    if len(stub) < offset + 6 or stub[offset] != 0xFF or stub[offset + 1] != 0x25:
        return None
    displacement = struct.unpack_from("<i", stub, offset + 2)[0]
    return stub_address + offset + 6 + displacement


def libm_body_verdict(
    *,
    selected_observed: bool,
    features_observed: bool,
    body_sha: str | None,
    constant_rows: list[dict[str, object]],
    required_bits: bool,
    body_vaddr: str | None,
    historical_vaddr: str,
) -> str:
    """Unknown loaded bytes stay blocked. A shifted body is not the historical argument."""
    if not selected_observed or not features_observed:
        return "BLOCKED"
    if body_sha is None or not constant_rows or any(row.get("classification") == "NOT ESTABLISHED" for row in constant_rows):
        return "BLOCKED"
    constants_match = all(row.get("classification") == "MATCH" for row in constant_rows)
    if body_sha == HISTORICAL_BODY_SHA256 and constants_match and required_bits and body_vaddr == historical_vaddr:
        return "APPLIES"
    return "DOES NOT APPLY"


def classify_selected_call(
    *,
    got_pointer: int | None,
    stub_address: int,
    cdll_pointer: int | None,
    unresolved_address: int | None = None,
) -> dict[str, object]:
    """The PLT GOT is the call target. A CDLL symbol is a separate lookup."""
    cdll = None if cdll_pointer is None else hex(cdll_pointer)
    resolver = stub_address + 6 if unresolved_address is None else unresolved_address
    unresolved = got_pointer is None or got_pointer == resolver
    if unresolved:
        return {
            "classification": "NOT ESTABLISHED",
            "address": None,
            "evidence": "python wrapper plt got",
            "method": (
                "Start this interpreter with LD_BIND_NOW=1 and reread the cos PLT GOT qword. "
                "ctypes.CDLL(libm).cos is not this observation."
            ),
            "independent_cdll_libm_cos": cdll,
            "independent_cdll_is_evidence": False,
        }
    return {
        "classification": "OBSERVED",
        "address": hex(got_pointer),
        "evidence": "python wrapper plt got",
        "method": "qword at the cos PLT slot reached from PyCFunction_GetFunction(math.cos)",
        "independent_cdll_libm_cos": cdll,
        "independent_cdll_is_evidence": False,
        "addresses_equal": got_pointer == cdll_pointer,
    }


def _git_text(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _pt_loads(path: str) -> list[tuple[int, int, int]]:
    data = Path(path).read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2:
        return []
    phoff = struct.unpack_from("<Q", data, 32)[0]
    entsize, count = struct.unpack_from("<HH", data, 54)
    loads = []
    for index in range(count):
        offset = phoff + index * entsize
        kind, _flags, file_off, vaddr, _paddr, filesz, _memsz, _align = struct.unpack_from("<IIQQQQQQ", data, offset)
        if kind == 1:
            loads.append((file_off, vaddr, filesz))
    return loads


def _map_rows() -> list[tuple[int, int, int, str]]:
    rows = []
    maps = Path("/proc/self/maps")
    if not maps.is_file():
        return rows
    for line in maps.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 6 or not parts[-1].startswith("/"):
            continue
        start_text, end_text = parts[0].split("-")
        rows.append((int(start_text, 16), int(end_text, 16), int(parts[2], 16), parts[-1]))
    return rows


def _runtime_owner(address: int) -> tuple[int, int, int, str] | None:
    for start, end, file_off, path in _map_rows():
        if start <= address < end:
            return start, end, file_off, path
    return None


def _runtime_to_vaddr(address: int) -> tuple[str, int] | None:
    owner = _runtime_owner(address)
    if owner is None:
        return None
    start, _end, map_off, path = owner
    file_off = map_off + (address - start)
    for load_off, vaddr, filesz in _pt_loads(path):
        if load_off <= file_off < load_off + filesz:
            return path, vaddr + (file_off - load_off)
    return None


def _wrapper_address() -> int | None:
    getter = ctypes.pythonapi.PyCFunction_GetFunction
    getter.argtypes = [ctypes.py_object]
    getter.restype = ctypes.c_void_p
    value = getter(math.cos)
    if not value:
        ctypes.pythonapi.PyErr_Clear()
        return None
    return int(value)


def _cdll_cos() -> int | None:
    try:
        library = ctypes.CDLL("libm.so.6")
        value = ctypes.cast(library.cos, ctypes.c_void_p).value
    except (OSError, AttributeError):
        return None
    if value is None:
        return None
    return int(value)


def _disassemble(path: str, start: int, stop: int) -> str | None:
    try:
        return subprocess.check_output(
            ["objdump", "-d", "-M", "intel", f"--start-address={start}", f"--stop-address={stop}", path],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None


def _calls_symbol(disassembly: str, name: str) -> bool:
    return any(match.group(2).startswith(name) for line in disassembly.splitlines() if (match := _CALL.match(line)))


def _readable_process_bytes(address: int, length: int) -> bytes | None:
    if _runtime_owner(address) is None:
        return None
    try:
        return ctypes.string_at(address, length)
    except (OSError, ValueError):
        return None


_CALL_PREFIXES = frozenset({0xF0, 0xF2, 0xF3, 0x2E, 0x36, 0x3E, 0x26, 0x64, 0x65, 0x66, 0x67})


def _decoder_record(coverage: str, classification: str, edges: list[dict[str, object]]) -> dict[str, object]:
    return {
        "classification": classification,
        "decoder": "capstone",
        "decoder_version": capstone.__version__,
        "mode": "64-bit",
        "coverage": coverage,
        "edges": edges,
    }


def _capstone_call_edge(instruction: capstone.CsInsn, base: int) -> dict[str, object] | None:
    raw = bytes(instruction.bytes)
    index = 0
    while index < len(raw) and raw[index] in _CALL_PREFIXES:
        index += 1
    if index < len(raw) and 0x40 <= raw[index] <= 0x4F:
        index += 1
    body = raw[index:]
    offset = instruction.address - base
    if body.startswith(b"\xe8") and len(body) >= 5:
        displacement = int.from_bytes(body[1:5], "little", signed=True)
        target = instruction.address + instruction.size + displacement
        return _call_edge("direct", "e8", offset, target, None, None)
    marker = body.find(b"\xff\x15")
    if marker >= 0 and marker + 6 == len(body):
        displacement = int.from_bytes(body[marker + 2:marker + 6], "little", signed=True)
        target = instruction.address + instruction.size + displacement
        return _call_edge("indirect", "ff15", offset, target, target, None)
    return None


def decode_loaded_calls(code: bytes, base: int) -> dict[str, object]:
    """Decode captured bytes with Capstone. An incomplete sweep establishes no call."""
    if not code:
        return _decoder_record("truncated", "NOT ESTABLISHED", [])
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = True
    try:
        instructions = list(decoder.disasm(code, base))
    except CsError:
        return _decoder_record("unsupported", "NOT ESTABLISHED", [])
    edges: list[dict[str, object]] = []
    consumed = 0
    for instruction in instructions:
        if instruction.address != base + consumed:
            return _decoder_record("unsupported", "NOT ESTABLISHED", [])
        if instruction.mnemonic == "call" or instruction.mnemonic.endswith(" call"):
            edge = _capstone_call_edge(instruction, base)
            if edge is None:
                return _decoder_record("unsupported", "NOT ESTABLISHED", [])
            edges.append(edge)
        consumed += instruction.size
    if consumed != len(code):
        coverage = "truncated" if consumed == 0 and code[0] == 0xE8 else "unsupported"
        return _decoder_record(coverage, "NOT ESTABLISHED", [])
    return _decoder_record("complete", "OBSERVED", edges)


def _call_edge(
    kind: str,
    opcode: str,
    offset: int,
    target: int,
    plt_destination: int | None,
    resolved_callee: int | None,
) -> dict[str, object]:
    return {
        "kind": kind,
        "opcode": opcode,
        "offset": offset,
        "target": hex(target),
        "source": "loaded bytes",
        "plt_destination": None if plt_destination is None else hex(plt_destination),
        "resolved_callee": None if resolved_callee is None else hex(resolved_callee),
        "symbol_bytes_establish_edge": False,
    }


def _undecoded(coverage: str) -> dict[str, object]:
    return _decoder_record(coverage, "NOT ESTABLISHED", [])


def call_edges_from_loaded_bytes(code: bytes, base: int) -> list[dict[str, object]]:
    """Established call edges only. An incomplete decode contributes none."""
    record = decode_loaded_calls(code, base)
    if record["classification"] != "OBSERVED":
        return []
    return list(record["edges"])


def _section_headers(data: bytes) -> list[tuple[str, tuple[int, ...]]] | None:
    if len(data) < 64 or data[:4] != b"\x7fELF" or data[4] != 2:
        return None
    section_offset = struct.unpack_from("<Q", data, 40)[0]
    entry_size, count, strings_index = struct.unpack_from("<HHH", data, 58)
    if section_offset <= 0 or count <= 0 or strings_index >= count:
        return None

    def header(index: int) -> tuple[int, ...]:
        return struct.unpack_from("<IIQQQQIIQQ", data, section_offset + index * entry_size)

    names = header(strings_index)

    def text(index: int) -> str:
        start = names[4] + index
        stop = data.find(b"\0", start)
        return data[start:stop].decode("ascii", "replace")

    return [(text(header(index)[0]), header(index)) for index in range(count)]


def _section(data: bytes, name: str) -> tuple[int, ...] | None:
    headers = _section_headers(data)
    if headers is None:
        return None
    for section_name, header in headers:
        if section_name == name:
            return header
    return None


def _symbol_text(data: bytes, strings: tuple[int, ...], name_index: int) -> str:
    start = strings[4] + name_index
    stop = data.find(b"\0", start)
    return data[start:stop].decode("ascii", "replace")


def _jump_slot_vaddr(path: str, symbol: str) -> int | None:
    data = Path(path).read_bytes()
    symbols = _section(data, ".dynsym")
    strings = _section(data, ".dynstr")
    relocations = _section(data, ".rela.plt")
    if symbols is None or strings is None or relocations is None or symbols[9] != 24 or relocations[9] != 24:
        return None
    for index in range(relocations[5] // 24):
        slot, info, _addend = struct.unpack_from("<QQq", data, relocations[4] + index * 24)
        if (info & 0xFFFFFFFF) != 7:
            continue
        name_index = struct.unpack_from("<I", data, symbols[4] + (info >> 32) * 24)[0]
        if _symbol_text(data, strings, name_index) == symbol:
            return int(slot)
    return None


def _defined_symbol_vaddr(path: str, symbol: str) -> int | None:
    data = Path(path).read_bytes()
    symbols = _section(data, ".dynsym")
    strings = _section(data, ".dynstr")
    if symbols is None or strings is None or symbols[9] != 24:
        return None
    for index in range(symbols[5] // 24):
        name_index, _info, _other, section, value, _size = struct.unpack_from("<IBBHQQ", data, symbols[4] + index * 24)
        if section != 0 and value and _symbol_text(data, strings, name_index) == symbol:
            return int(value)
    return None


def _vaddr_to_runtime(path: str, vaddr: int) -> int | None:
    file_offset = _file_offset_for_vaddr(Path(path), vaddr)
    if file_offset is None:
        return None
    for start, end, map_offset, mapped in _map_rows():
        if mapped == path and map_offset <= file_offset < map_offset + (end - start):
            return start + (file_offset - map_offset)
    return None


def _loaded_direct_calls(loaded: bytes, file_bytes: bytes, base: int, accept: object) -> list[dict[str, object]]:
    if loaded != file_bytes or not callable(accept):
        return []
    found = []
    for edge in call_edges_from_loaded_bytes(loaded, base):
        if edge["kind"] != "direct" or not accept(edge):
            continue
        recorded = dict(edge)
        offset = int(recorded["offset"])
        recorded["loaded_instruction_bytes_hex"] = loaded[offset:offset + 5].hex()
        recorded["file_instruction_bytes_hex"] = file_bytes[offset:offset + 5].hex()
        recorded["loaded_bytes_match_file"] = True
        recorded["disk_disassembly_is_proof"] = False
        found.append(recorded)
    return found


def _loaded_jump_slot_calls(path: str, loaded: bytes, file_bytes: bytes, base: int, symbol: str) -> list[dict[str, object]]:
    """Direct calls whose loaded stub uses this symbol's JUMP_SLOT."""
    slot = _jump_slot_vaddr(path, symbol)
    runtime = None if slot is None else _vaddr_to_runtime(path, slot)
    if runtime is None:
        return []

    def accept(edge: dict[str, object]) -> bool:
        target = int(str(edge["target"]), 16)
        stub = _readable_process_bytes(target, 16)
        return stub is not None and plt_got_address(stub, target) == runtime

    edges = _loaded_direct_calls(loaded, file_bytes, base, accept)
    for edge in edges:
        edge["symbol"] = symbol
    return edges


def _executable_images(data: bytes) -> list[tuple[str, int, bytes]]:
    headers = _section_headers(data)
    if headers is None:
        return []
    images = []
    for name, header in headers:
        address = header[3]
        size = header[5]
        if address == 0 or size <= 0 or size > 8_000_000:
            continue
        if not (name.startswith(".plt") or (header[2] & 4)):
            continue
        images.append((name, address, data[header[4]:header[4] + size]))
    images.sort(key=lambda item: (not item[0].startswith(".plt"), item[0]))
    return images


def _plt_entry_vaddr(path: str, slot_vaddr: int) -> int | None:
    """File vaddr of the stub whose RIP-relative jump uses this GOT slot."""
    data = Path(path).read_bytes()
    endbr = b"\xf3\x0f\x1e\xfa"
    for _name, base, blob in _executable_images(data):
        for index in range(len(blob) - 6):
            if blob[index] != 0xFF or blob[index + 1] != 0x25:
                continue
            displacement = int.from_bytes(blob[index + 2:index + 6], "little", signed=True)
            if base + index + 6 + displacement != slot_vaddr:
                continue
            entry = index - 4 if index >= 4 and blob[index - 4:index] == endbr else index
            return base + entry
    return None


def _raw_jump_slot_pointer(path: str, symbol: str) -> str | None:
    """A GOT qword without a matched loaded call. It does not establish the path."""
    slot = _jump_slot_vaddr(path, symbol)
    entry = None if slot is None else _plt_entry_vaddr(path, slot)
    runtime = None if entry is None else _vaddr_to_runtime(path, entry)
    if runtime is None or _runtime_owner(runtime) is None:
        return None
    try:
        stub = ctypes.string_at(runtime, 16)
    except (OSError, ValueError):
        return None
    got = plt_got_address(stub, runtime)
    pointer = None if got is None else _read_qword(got)
    return None if pointer is None else hex(pointer)


def _loaded_defined_symbol_calls(path: str, loaded: bytes, file_bytes: bytes, base: int, symbol: str) -> list[dict[str, object]]:
    """Direct calls whose loaded target is this defined symbol."""
    vaddr = _defined_symbol_vaddr(path, symbol)
    runtime = None if vaddr is None else _vaddr_to_runtime(path, vaddr)
    if runtime is None:
        return []

    def accept(edge: dict[str, object]) -> bool:
        return int(str(edge["target"]), 16) == runtime

    edges = _loaded_direct_calls(loaded, file_bytes, base, accept)
    for edge in edges:
        edge["symbol"] = symbol
    return edges


def _read_qword(address: int) -> int | None:
    if _runtime_owner(address) is None:
        return None
    try:
        value = ctypes.c_void_p.from_address(address).value
    except (OSError, ValueError):
        return None
    if value is None:
        return None
    return int(value)


PROBE_BUILD_FLAGS = ("-O2", "-shared", "-fPIC")
INSPECTED_PREFIX_LENGTH = 64


def classify_loaded_correspondence(
    file_bytes: bytes,
    loaded_bytes: bytes | None,
    *,
    address: int,
    file_offset: int,
) -> dict[str, object]:
    """A prefix comparison does not establish whole-image correspondence."""
    if loaded_bytes is None or file_offset < 0 or file_offset + len(loaded_bytes) > len(file_bytes):
        inspected = "NOT ESTABLISHED"
        difference = "unavailable"
        length = 0 if loaded_bytes is None else len(loaded_bytes)
    elif file_bytes[file_offset:file_offset + len(loaded_bytes)] == loaded_bytes:
        inspected = "MATCH"
        difference = None
        length = len(loaded_bytes)
    else:
        inspected = "MISMATCH"
        difference = "observed"
        length = len(loaded_bytes)
    covers_file = file_offset == 0 and loaded_bytes is not None and len(loaded_bytes) == len(file_bytes) and length == len(file_bytes)
    if covers_file and inspected == "MATCH":
        whole = "MATCH"
        coverage = "whole file"
    elif covers_file and inspected == "MISMATCH":
        whole = "MISMATCH"
        coverage = "whole file"
    else:
        whole = "NOT ESTABLISHED"
        coverage = "entrypoint prefix"
    return {
        "inspected_address": hex(address),
        "inspected_end_address": None if loaded_bytes is None else hex(address + len(loaded_bytes)),
        "inspected_file_offset": file_offset,
        "inspected_length": length,
        "inspected_correspondence": inspected,
        "difference": difference,
        "correspondence_coverage": coverage,
        "loaded_code_correspondence": whole,
    }


def _probe_words(source: Path) -> tuple[list[int], dict[str, object]] | None:
    """Compile, load, and call read_state. Record that image before cleanup."""
    try:
        with tempfile.TemporaryDirectory(prefix="c2v09-cosine-probe-") as work:
            binary = Path(work) / "probe.so"
            compiled = subprocess.run(
                ["gcc", *PROBE_BUILD_FLAGS, "-o", str(binary), str(source)],
                capture_output=True,
                text=True,
                check=False,
            )
            if compiled.returncode != 0 or not binary.is_file():
                return None
            library = ctypes.CDLL(str(binary))
            symbols = {}
            for name in ("read_state", "xcr0_read_permitted"):
                value = ctypes.cast(getattr(library, name), ctypes.c_void_p).value
                symbols[name] = None if value is None else int(value)
            address = symbols.get("read_state")
            measurement = _measurement_image(source, binary, address, symbols)
            state = (ctypes.c_uint32 * 12)()
            library.read_state(state)
            measurement["read_state_calls"] = 1
            _bind_probe_helper_edges(measurement)
            return [int(word) for word in state], measurement
    except (OSError, AttributeError):
        return None


def _measurement_image(
    source: Path,
    binary: Path,
    address: int | None,
    symbols: Mapping[str, int | None] | None = None,
) -> dict[str, object]:
    """File digest and loaded-byte correspondence are separate facts."""
    file_bytes = binary.read_bytes()
    file_sha = sha256_bytes(file_bytes)
    source_sha = sha256_bytes(source.read_bytes())
    loaded_path = None
    owner = None if address is None else _runtime_owner(address)
    inspected = classify_loaded_correspondence(b"", None, address=0, file_offset=0)
    if owner is not None and address is not None:
        start, end, map_off, path = owner
        loaded_path = path
        file_off = map_off + (address - start)
        length = min(INSPECTED_PREFIX_LENGTH, end - address)
        try:
            mapped = Path(path).read_bytes()
        except OSError:
            mapped = None
        loaded = None if length <= 0 else _readable_process_bytes(address, length)
        reference = mapped if mapped is not None and sha256_bytes(mapped) == file_sha else None
        inspected = classify_loaded_correspondence(
            b"" if reference is None else reference,
            None if reference is None else loaded,
            address=address,
            file_offset=file_off,
        )
    record = {
        "role": "actual loaded probe image used for read_state",
        "compiler": "gcc",
        "flags": list(PROBE_BUILD_FLAGS),
        "source_path": PROBE_SOURCE,
        "source_sha256": source_sha,
        "file_image_sha256": file_sha,
        "file_image_identity": "OBSERVED",
        "loaded_path": loaded_path,
        "read_state_address": None if address is None else hex(address),
        "handle_associated": address is not None,
        "second_compilation_is_evidence": False,
        "source_hash_is_the_image": False,
        "cosine_function_calls": 0,
        "read_state_calls": 0,
    }
    record.update(inspected)
    record["consumed_instruction_ranges"] = _consumed_symbol_ranges(binary, symbols or {})
    record["whole_elf_required"] = False
    return record


def _file_offset_for_vaddr(path: Path, vaddr: int) -> int | None:
    for load_off, load_vaddr, filesz in _pt_loads(str(path)):
        if load_vaddr <= vaddr < load_vaddr + filesz:
            return load_off + (vaddr - load_vaddr)
    return None


def _nm_symbols(binary: Path) -> dict[str, tuple[int, int]]:
    try:
        text = subprocess.check_output(["nm", "-P", str(binary)], text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return {}
    found: dict[str, tuple[int, int]] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        name, _kind, value, size = parts[0], parts[1], parts[2], parts[3]
        if name not in {"read_state", "xcr0_read_permitted"}:
            continue
        try:
            found[name] = (int(value, 16), int(size, 16))
        except ValueError:
            continue
    return found


def _consumed_symbol_ranges(binary: Path, symbols: Mapping[str, int | None]) -> list[dict[str, object]]:
    """Compare only the reached probe symbols. This is not whole-ELF equality."""
    table = _nm_symbols(binary)
    data = binary.read_bytes()
    rows = []
    for name, address in symbols.items():
        spec = table.get(name)
        if address is None or spec is None:
            rows.append({"name": name, "correspondence": "NOT ESTABLISHED", "coverage": "symbol range", "whole_elf": False})
            continue
        file_off = _file_offset_for_vaddr(binary, spec[0])
        size = spec[1]
        loaded = None if size <= 0 or file_off is None else _readable_process_bytes(address, size)
        file_slice = b"" if file_off is None or file_off + size > len(data) else data[file_off:file_off + size]
        if loaded is None or file_off is None or file_off + size > len(data):
            correspondence = "NOT ESTABLISHED"
            difference = "unavailable"
            decoded = _undecoded("truncated" if loaded is not None else "unavailable")
        elif file_slice == loaded:
            correspondence = "MATCH"
            difference = None
            decoded = decode_loaded_calls(loaded, address)
        else:
            correspondence = "MISMATCH"
            difference = "observed"
            decoded = decode_loaded_calls(loaded, address)
        edges = list(decoded["edges"]) if decoded.get("classification") == "OBSERVED" else []
        mapped = _runtime_to_vaddr(address)
        rows.append(
            {
                "name": name,
                "address": hex(address),
                "file_offset": file_off,
                "length": size,
                "end_address": hex(address + size),
                "file_bytes_hex": None if not file_slice else file_slice.hex(),
                "loaded_bytes_hex": None if loaded is None else loaded.hex(),
                "call_decode": decoded,
                "call_edges": edges,
                "call_edges_decoded_from_loaded_bytes": decoded.get("classification") == "OBSERVED" and decoded.get("coverage") == "complete",
                "symbol_bytes_establish_edge": False,
                "helper_call_established": False,
                "address_to_elf": {
                    "runtime_address": hex(address),
                    "mapped_file": None if mapped is None else mapped[0],
                    "elf_vaddr": None if mapped is None else hex(mapped[1]),
                    "file_offset": file_off,
                },
                "correspondence": correspondence,
                "difference": difference,
                "coverage": "symbol range",
                "whole_elf": False,
                "disk_disassembly_is_proof": False,
            }
        )
    return rows


def _annotate_loaded_edge(edge: Mapping[str, object]) -> dict[str, object]:
    """A direct call may land on a PLT stub. That stub is not the resolved callee."""
    recorded = dict(edge)
    recorded["symbol_bytes_establish_edge"] = False
    if recorded.get("kind") != "direct":
        return recorded
    target = int(str(recorded["target"]), 16)
    stub = _readable_process_bytes(target, 16)
    got = None if stub is None else plt_got_address(stub, target)
    if got is None:
        recorded["plt_destination"] = None
        recorded["resolved_callee"] = recorded["target"]
        return recorded
    pointer = _read_qword(got)
    recorded["plt_destination"] = recorded["target"]
    recorded["resolved_callee"] = None if pointer is None else hex(pointer)
    return recorded


def _hex_bytes(value: object) -> bytes:
    if not isinstance(value, str) or not value:
        return b""
    try:
        return bytes.fromhex(value)
    except ValueError:
        return b""


def assess_helper_connection(evidence: Mapping[str, object]) -> dict[str, object]:
    """Recompute the call, stub, GOT, qword, and helper range. Annotations are ignored."""
    blocked = {
        "classification": "NOT ESTABLISHED",
        "address_annotation_establishes_connection": False,
    }
    read_bytes = evidence.get("read_state_bytes")
    read_address = evidence.get("read_state_address")
    stubs = evidence.get("stub_bytes_by_address")
    qwords = evidence.get("qword_by_slot")
    helper_address = evidence.get("helper_address")
    helper_range = evidence.get("helper_range_bytes")
    helper_file = evidence.get("helper_file_bytes")
    if (
        not isinstance(read_bytes, (bytes, bytearray))
        or not isinstance(read_address, int)
        or not isinstance(stubs, Mapping)
        or not isinstance(qwords, Mapping)
        or not isinstance(helper_address, int)
        or not isinstance(helper_range, (bytes, bytearray))
        or not isinstance(helper_file, (bytes, bytearray))
        or not helper_range
        or bytes(helper_range) != bytes(helper_file)
    ):
        return blocked
    decoded = decode_loaded_calls(bytes(read_bytes), read_address)
    if decoded.get("classification") != "OBSERVED" or decoded.get("coverage") != "complete":
        return blocked
    for edge in decoded.get("edges") or []:
        if not isinstance(edge, Mapping) or edge.get("kind") != "direct" or not isinstance(edge.get("target"), str):
            continue
        target = int(str(edge["target"]), 16)
        stub = stubs.get(target)
        if not isinstance(stub, (bytes, bytearray)) or len(stub) < 6:
            continue
        got = plt_got_address(bytes(stub), target)
        qword = None if got is None else qwords.get(got)
        if got is None or not isinstance(qword, int) or qword != helper_address:
            continue
        return {
            "classification": "OBSERVED",
            "call_offset": edge.get("offset"),
            "plt_destination": hex(target),
            "plt_stub_bytes_hex": bytes(stub).hex(),
            "got_slot": hex(got),
            "observed_qword": hex(qword),
            "helper_address": hex(helper_address),
            "helper_range_matches": True,
            "resolved_callee": hex(qword),
            "address_annotation_establishes_connection": False,
        }
    return blocked


def _bind_probe_helper_edges(measurement: dict[str, object]) -> None:
    """Re-read GOT slots after read_state. Symbol bytes do not create the edge."""
    ranges = measurement.get("consumed_instruction_ranges")
    if not isinstance(ranges, list):
        return
    rows = {row.get("name"): row for row in ranges if isinstance(row, dict)}
    reader = rows.get("read_state")
    helper = rows.get("xcr0_read_permitted")
    if not isinstance(reader, dict):
        return
    annotated = [_annotate_loaded_edge(edge) for edge in reader.get("call_edges") or [] if isinstance(edge, dict)]
    reader["call_edges"] = annotated
    reader["symbol_bytes_establish_edge"] = False
    read_address = int(reader["address"], 16) if isinstance(reader.get("address"), str) else None
    helper_address = int(helper["address"], 16) if isinstance(helper, dict) and isinstance(helper.get("address"), str) else None
    stubs: dict[int, bytes] = {}
    qwords: dict[int, int] = {}
    read_bytes = _hex_bytes(reader.get("loaded_bytes_hex"))
    if read_address is not None:
        decoded = decode_loaded_calls(read_bytes, read_address)
        for edge in decoded.get("edges") or []:
            if not isinstance(edge, Mapping) or edge.get("kind") != "direct" or not isinstance(edge.get("target"), str):
                continue
            target = int(str(edge["target"]), 16)
            stub = _readable_process_bytes(target, 16)
            if stub is None:
                continue
            stubs[target] = stub
            got = plt_got_address(stub, target)
            pointer = None if got is None else _read_qword(got)
            if got is not None and pointer is not None:
                qwords[got] = pointer
    connection = assess_helper_connection(
        {
            "read_state_bytes": read_bytes,
            "read_state_address": read_address,
            "stub_bytes_by_address": stubs,
            "qword_by_slot": qwords,
            "helper_address": helper_address,
            "helper_range_bytes": _hex_bytes(helper.get("loaded_bytes_hex")) if isinstance(helper, dict) else b"",
            "helper_file_bytes": _hex_bytes(helper.get("file_bytes_hex")) if isinstance(helper, dict) else b"",
        }
    )
    reader["observed_plt_stubs"] = [
        {"address": hex(address), "bytes_hex": blob.hex()} for address, blob in sorted(stubs.items())
    ]
    reader["observed_got_qwords"] = [
        {"slot": hex(slot), "qword": hex(value)} for slot, value in sorted(qwords.items())
    ]
    reader["helper_connection"] = connection
    reader["helper_call_established"] = connection["classification"] == "OBSERVED"


def _c_function_address(function: object) -> int | None:
    getter = ctypes.pythonapi.PyCFunction_GetFunction
    getter.argtypes = [ctypes.py_object]
    getter.restype = ctypes.c_void_p
    try:
        value = getter(function)
    except (OSError, ValueError, TypeError):
        return None
    if not value:
        ctypes.pythonapi.PyErr_Clear()
        return None
    return int(value)


def observe_ulp_terminal_guard() -> dict[str, object]:
    """Follow the loaded math.ulp wrapper. Do not call math.ulp or nextafter."""
    address = _c_function_address(math.ulp)
    located = None if address is None else _runtime_to_vaddr(address)
    loaded = None if address is None else _readable_process_bytes(address, 0x180)
    file_bytes = None if located is None else _elf_bytes(located[0], located[1], 0x180)
    matches = loaded is not None and file_bytes is not None and loaded == file_bytes
    record: dict[str, object] = {
        "ulp_function_calls": 0,
        "nextafter_function_calls": 0,
        "output_sampled": False,
        "wrapper_address": None if address is None else hex(address),
        "wrapper_address_establishes_path": False,
        "disk_disassembly_is_proof": False,
        "loaded_wrapper_bytes_hex": None if loaded is None else loaded.hex(),
        "file_wrapper_bytes_hex": None if file_bytes is None else file_bytes.hex(),
        "loaded_wrapper_matches_file": matches,
        "address_to_elf": None
        if located is None or address is None
        else {
            "runtime_address": hex(address),
            "mapped_file": located[0],
            "elf_vaddr": hex(located[1]),
            "file_offset": _file_offset_for_vaddr(Path(located[0]), located[1]),
        },
        "call_edges": [],
        "loaded_stub_bytes_hex": None,
        "got_slot": None,
        "selected_address": None,
        "evidence": None,
        "calls_nextafter_plt": False,
        "selected_nextafter": "NOT ESTABLISHED",
        "historical_equality_assumed": False,
        "settles_applicability": False,
    }
    if address is None or located is None or not matches or loaded is None or file_bytes is None:
        return record
    edges = _loaded_jump_slot_calls(located[0], loaded, file_bytes, address, "nextafter")
    record["call_edges"] = edges
    if not edges:
        return record
    target = int(str(edges[0]["target"]), 16)
    stub = _readable_process_bytes(target, 16)
    if stub is None:
        return record
    record["loaded_stub_bytes_hex"] = stub.hex()
    got = plt_got_address(stub, target)
    if got is None:
        return record
    record["got_slot"] = hex(got)
    pointer = _read_qword(got)
    prefix = 4 if stub.startswith(b"\xf3\x0f\x1e\xfa") else 0
    selected = classify_selected_call(
        got_pointer=pointer,
        stub_address=target,
        cdll_pointer=None,
        unresolved_address=target + prefix + 6,
    )
    owner = None if pointer is None else _runtime_owner(pointer)
    if selected["classification"] == "OBSERVED" and owner is not None and owner[3] != located[0] and pointer is not None:
        record["calls_nextafter_plt"] = True
        record["selected_nextafter"] = "OBSERVED"
        record["selected_address"] = hex(pointer)
        record["evidence"] = "loaded wrapper plt got"
    return record


def _fegetround() -> str | None:
    try:
        library = ctypes.CDLL("libm.so.6")
        library.fegetround.restype = ctypes.c_int
        return str(library.fegetround())
    except (OSError, AttributeError):
        return None


def _elf_bytes(path: str, vaddr: int, length: int) -> bytes | None:
    for load_off, load_vaddr, filesz in _pt_loads(path):
        if load_vaddr <= vaddr < load_vaddr + filesz and vaddr + length <= load_vaddr + filesz:
            data = Path(path).read_bytes()
            start = load_off + (vaddr - load_vaddr)
            return data[start:start + length]
    return None


def _binding_reference(root: Path) -> tuple[dict[str, bytes], str]:
    data = (root / CERTIFICATE_PATH).read_bytes()
    if sha256_bytes(data) != CERTIFICATE_FILE_SHA256:
        raise RuntimeError("Historical certificate bytes changed.")
    text = data.decode("utf-8")
    body = text.split("```json\n", 1)[1].split("```", 1)[0]
    if sha256_bytes(body.encode("utf-8")) != RUNTIME_BINDING_SHA256:
        raise RuntimeError("Runtime-binding record does not match the reviewed digest.")
    parsed = json.loads(body)
    constants = parsed["constants"]
    encoded = {str(vaddr): bytes.fromhex(str(spec["little_endian_bytes_hex"])) for vaddr, spec in constants.items()}
    return encoded, str(parsed["resolved_cos_body_vaddr"])


def _feature_record(words: list[int] | None, rounding: str | None) -> dict[str, object]:
    thread_id = str(threading.get_native_id()) if hasattr(threading, "get_native_id") else str(threading.get_ident())
    if words is None or rounding is None:
        return {
            "classification": "NOT ESTABLISHED",
            "required_bits_ok": False,
            "thread_id": thread_id,
            "method": "Compile c2v09_cosine_path_probe.c with gcc -O2 -shared -fPIC and call read_state. Do not evaluate cosine.",
        }
    mxcsr = words[0]
    ecx = words[4]
    permitted = xcr0_read_permitted(ecx, words[8])
    xcr0 = words[10] if permitted else None
    required = False
    if xcr0 is not None:
        required = (
            (mxcsr & 0xE040) == 0
            and (mxcsr & 0x1F80) == 0x1F80
            and rounding == "0"
            and (ecx & (1 << 12)) != 0
            and (ecx & (1 << 27)) != 0
            and (ecx & (1 << 28)) != 0
            and (xcr0 & 6) == 6
        )
    record: dict[str, object] = {
        "classification": "OBSERVED" if permitted else "NOT ESTABLISHED",
        "xcr0_classification": "OBSERVED" if permitted else "NOT ESTABLISHED",
        "required_bits_ok": required,
        "mxcsr": hex(mxcsr),
        "mxcsr_rounding": "nearest ties-to-even" if ((mxcsr >> 13) & 3) == 0 else "not nearest ties-to-even",
        "mxcsr_daz": bool(mxcsr & 0x40),
        "mxcsr_ftz": bool(mxcsr & 0x8000),
        "x87_control": hex(words[1]),
        "fegetround": rounding,
        "cpuid_leaf1": [hex(word) for word in words[2:6]],
        "cpuid_leaf7_sub0": [hex(word) for word in words[6:10]],
        "xcr0": None if xcr0 is None else [hex(words[10]), hex(words[11])],
        "avx": bool(ecx & (1 << 28)),
        "fma": bool(ecx & (1 << 12)),
        "osxsave": bool(ecx & (1 << 27)),
        "xcr0_xmm_ymm": None if xcr0 is None else (xcr0 & 6) == 6,
        "exact_historical_xcr0_match": False if xcr0 is None else [hex(words[10]), hex(words[11])] == ["0xe7", "0x0"],
        "thread_id": thread_id,
    }
    if not permitted:
        record["method"] = (
            "CPUID leaf 1 ECX OSXSAVE is clear, so XGETBV was not executed. "
            "Leaf 7 ECX bit 27 does not authorize XGETBV. "
            "The XCR0 register was not observed, and a zeroed output slot is not register zero."
        )
    return record


def prepare_cosine_path_certificate(root: Path) -> dict[str, object]:
    """Observe this process's math wrapper and its selected cosine target."""
    located = None
    wrapper = _wrapper_address()
    disassembly = None
    if wrapper is not None:
        located = _runtime_to_vaddr(wrapper)
    if located is not None:
        path, vaddr = located
        disassembly = _disassemble(path, vaddr, vaddr + 0xC0)
    loaded_wrapper = None if wrapper is None else _readable_process_bytes(wrapper, 0xC0)
    elf_wrapper = None if located is None else _elf_bytes(located[0], located[1], 0xC0)
    wrapper_matches = loaded_wrapper is not None and elf_wrapper is not None and loaded_wrapper == elf_wrapper
    cosine_edges: list[dict[str, object]] = []
    conversion_edges: list[dict[str, object]] = []
    if wrapper is not None and located is not None and wrapper_matches and loaded_wrapper is not None and elf_wrapper is not None:
        cosine_edges = _loaded_jump_slot_calls(located[0], loaded_wrapper, elf_wrapper, wrapper, "cos")
        conversion_edges = _loaded_defined_symbol_calls(located[0], loaded_wrapper, elf_wrapper, wrapper, "PyFloat_AsDouble")
    selected: dict[str, object]
    body_sha = None
    body_bytes = None
    body_vaddr = None
    libm_path = None
    constants: list[dict[str, object]] = []
    if not cosine_edges or located is None:
        cdll = _cdll_cos()
        selected = {
            "classification": "NOT ESTABLISHED",
            "address": None,
            "raw_got_pointer": None if located is None else _raw_jump_slot_pointer(located[0], "cos"),
            "evidence": "python wrapper plt got",
            "method": (
                "The loaded wrapper bytes do not contain a matched direct call to the cos JUMP_SLOT. "
                "A GOT qword read from the PLT entry is a raw observation and is not the selected target. "
                "Disk disassembly is not this observation."
            ),
            "independent_cdll_libm_cos": None if cdll is None else hex(cdll),
            "independent_cdll_is_evidence": False,
        }
    else:
        path = located[0]
        stub_runtime = int(str(cosine_edges[0]["target"]), 16)
        stub = b"" if _runtime_owner(stub_runtime) is None else ctypes.string_at(stub_runtime, 16)
        got = plt_got_address(stub, stub_runtime)
        if got is None:
            cdll = _cdll_cos()
            selected = {
                "classification": "NOT ESTABLISHED",
                "address": None,
                "evidence": "python wrapper plt got",
                "method": UNPARSED_STUB_METHOD,
                "independent_cdll_libm_cos": None if cdll is None else hex(cdll),
                "independent_cdll_is_evidence": False,
                "plt_stub": hex(stub_runtime),
                "plt_stub_bytes_hex": stub.hex(),
                "plt_jmp_bytes_hex": None,
            }
        else:
            got_pointer = _read_qword(got)
            prefix = 4 if stub.startswith(b"\xf3\x0f\x1e\xfa") else 0
            selected = classify_selected_call(
                got_pointer=got_pointer,
                stub_address=stub_runtime,
                cdll_pointer=_cdll_cos(),
                unresolved_address=stub_runtime + prefix + 6,
            )
            selected["plt_stub"] = hex(stub_runtime)
            selected["plt_stub_bytes_hex"] = stub.hex()
            selected["plt_jmp_bytes_hex"] = stub[prefix:prefix + 6].hex()
            selected["got_slot"] = hex(got)
            owner = None if got_pointer is None else _runtime_owner(got_pointer)
            if selected["classification"] == "OBSERVED" and (owner is None or owner[3] == path):
                selected["classification"] = "NOT ESTABLISHED"
                selected["address"] = None
                selected["method"] = (
                    "The GOT qword does not point at a mapped library other than the interpreter image. "
                    "Disassemble the stub and confirm the slot is resolved into libm."
                )
            elif selected["classification"] == "OBSERVED" and owner is not None and got_pointer is not None:
                if got_pointer + HISTORICAL_BODY_LENGTH <= owner[1]:
                    libm_path = owner[3]
                    body = ctypes.string_at(got_pointer, HISTORICAL_BODY_LENGTH)
                    body_bytes = body
                    body_sha = sha256_bytes(body)
                    mapped = _runtime_to_vaddr(got_pointer)
                    body_vaddr = None if mapped is None else hex(mapped[1])
    historical_vaddr = "0x7bad0"
    expected_constants: dict[str, bytes] = {}
    if libm_path is not None:
        expected_constants, historical_vaddr = _binding_reference(root)
        for vaddr, expected in expected_constants.items():
            observed = read_loaded_vaddr(libm_path, int(vaddr, 16), len(expected))
            constants.append(
                {
                    "vaddr": vaddr,
                    "match": observed == expected,
                    "observed_bytes_hex": None if observed is None else observed.hex(),
                    "classification": "NOT ESTABLISHED" if observed is None else ("MATCH" if observed == expected else "MISMATCH"),
                }
            )
    probed = _probe_words(root / PROBE_SOURCE)
    words = None if probed is None else probed[0]
    measurement_image = None if probed is None else probed[1]
    rounding = _fegetround()
    features = _feature_record(words, rounding)
    executable = Path(sys.executable).resolve()
    executable_sha = sha256_bytes(executable.read_bytes()) if executable.is_file() else None
    if executable_sha == HISTORICAL_EXECUTABLE_SHA256:
        wrapper_argument = "NOT ESTABLISHED"
    elif executable_sha is None:
        wrapper_argument = "BLOCKED"
    else:
        wrapper_argument = "DOES NOT APPLY"
    attributed = attribute_loaded_wrapper(
        raw_selected=selected,
        loaded_wrapper=loaded_wrapper,
        elf_wrapper=elf_wrapper,
        body_sha=body_sha,
        constant_rows=constants,
        features_observed=features["classification"] == "OBSERVED",
        required_bits=features["required_bits_ok"] is True,
        body_vaddr=body_vaddr,
        historical_vaddr=historical_vaddr,
    )
    selected = attributed["selected_call_target"]
    libm_argument = attributed["libm_body_argument"]
    conversion: dict[str, object]
    if conversion_edges:
        conversion = dict(conversion_edges[0])
        conversion["classification"] = "OBSERVED"
    else:
        conversion = {
            "classification": "NOT ESTABLISHED",
            "source": "loaded bytes",
            "disk_disassembly_is_proof": False,
        }
    runtime_correspondence = {
        "recording_pid": os.getpid(),
        "recording_thread_id": features["thread_id"],
        "disk_disassembly_is_proof": False,
        "whole_elf_required": False,
        "cosine": {
            "loaded_wrapper_bytes_hex": None if loaded_wrapper is None else loaded_wrapper.hex(),
            "file_wrapper_bytes_hex": None if elf_wrapper is None else elf_wrapper.hex(),
            "loaded_wrapper_matches_file": attributed["loaded_wrapper_matches_elf"] is True,
            "conversion": conversion,
            "cosine_call_edges": cosine_edges,
            "plt_stub": selected.get("plt_stub"),
            "plt_stub_bytes_hex": selected.get("plt_stub_bytes_hex"),
            "plt_jmp_bytes_hex": selected.get("plt_jmp_bytes_hex"),
            "got_slot": selected.get("got_slot"),
            "selected_address": selected.get("address"),
            "evidence": selected.get("evidence"),
            "selected_classification": selected.get("classification"),
            "body_sha256": body_sha,
            "body_bytes_hex": None if body_bytes is None else body_bytes.hex(),
            "body_elf_vaddr": body_vaddr,
            "constants": constants,
            "controls_classification": features.get("classification"),
            "required_bits_ok": features.get("required_bits_ok"),
            "mxcsr": features.get("mxcsr"),
            "fegetround": features.get("fegetround"),
            "x87_control": features.get("x87_control"),
            "xcr0": features.get("xcr0"),
            "cosine_function_calls": 0,
            "libm_body_argument": libm_argument,
            "disk_disassembly_is_proof": False,
        },
    }
    payload = {
        "status": "ONE RUNTIME PATH CERTIFICATE",
        "eligibility_evidence": False,
        "physical_qualification": False,
        "baseline_ci_is_eligibility": False,
        "cosine_function_calls": 0,
        "returned_source_object": "NOT IN THIS CERTIFICATE",
        "changed_python_operation_graph": "NOT IN THIS CERTIFICATE",
        "checkout_sha": _git_text(root, "rev-parse", "HEAD"),
        "tree_sha": _git_text(root, "rev-parse", "HEAD^{tree}"),
        "ld_bind_now": os.environ.get("LD_BIND_NOW"),
        "python_version": sys.version,
        "executable": {"path": str(executable), "file_sha256": executable_sha},
        "python_wrapper": {
            "address": None if wrapper is None else hex(wrapper),
            "mapped_file": None if located is None else located[0],
            "elf_vaddr": None if located is None else hex(located[1]),
            "calls_pyfloat_asdouble": bool(disassembly and _calls_symbol(disassembly, "PyFloat_AsDouble")),
            "calls_cos_plt": bool(cosine_edges),
            "disassembly_source": "objdump of the on-disk ELF; loaded bytes are compared separately",
            "disassembly": disassembly,
            "loaded_wrapper_sha256": None if loaded_wrapper is None else sha256_bytes(loaded_wrapper),
            "loaded_wrapper_matches_elf": attributed["loaded_wrapper_matches_elf"],
        },
        "selected_call_target": selected,
        "loaded_body": {
            "length": HISTORICAL_BODY_LENGTH,
            "sha256": body_sha,
            "elf_vaddr": body_vaddr,
            "matches_historical_body": None if body_sha is None else body_sha == HISTORICAL_BODY_SHA256,
            "libm_path": libm_path,
        },
        "loaded_constants": constants,
        "numerical_controls_and_features": features,
        "libm_body_argument": libm_argument,
        "runtime_correspondence": runtime_correspondence,
        "historical_cpython_wrapper_argument": wrapper_argument,
        "applicability_scope": (
            "historical libm body validity predicate for this selected path only; "
            "not exact XCR0 identity, not the historical CPython wrapper, and not eligibility"
        ),
        "historical_body_sha256": HISTORICAL_BODY_SHA256,
        "probe_source_sha256": sha256_bytes((root / PROBE_SOURCE).read_bytes()),
        "measurement_image": measurement_image or {
            "role": "actual loaded probe image used for read_state",
            "file_image_identity": "NOT ESTABLISHED",
            "loaded_code_correspondence": "NOT ESTABLISHED",
            "handle_associated": False,
            "second_compilation_is_evidence": False,
            "source_hash_is_the_image": False,
            "cosine_function_calls": 0,
        },
        "implementation_sha256": sha256_bytes((root / IMPLEMENTATION_SOURCE).read_bytes()),
    }
    return {
        "digest_scope": DIGEST_SCOPE,
        "canonical_payload": payload,
        "canonical_sha256": sha256_bytes(canonical_bytes(payload)),
    }
