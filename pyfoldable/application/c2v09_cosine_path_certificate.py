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
UNPARSED_STUB_METHOD = (
    "The PLT stub is not jmp [rip+disp32], with or without a leading endbr64. "
    "Disassemble that stub and record its GOT encoding. LD_BIND_NOW does not repair an unrecognized stub."
)
DIGEST_SCOPE = (
    "SHA-256 of the section 7.3 canonical bytes of canonical_payload only. "
    "canonical_sha256 and digest_scope are outside that payload."
)
_CALL = re.compile(r"^\s*[0-9a-f]+:.*\bcall\s+([0-9a-f]+)\s+<([^>]+)>", re.IGNORECASE)


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


def _cos_plt_vaddr(disassembly: str) -> int | None:
    for line in disassembly.splitlines():
        match = _CALL.match(line)
        if match is None:
            continue
        symbol = match.group(2)
        if symbol == "cos@plt" or symbol.startswith("cos@GLIBC"):
            return int(match.group(1), 16)
    return None


def _calls_symbol(disassembly: str, name: str) -> bool:
    return any(match.group(2).startswith(name) for line in disassembly.splitlines() if (match := _CALL.match(line)))


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


def _probe_words(source: Path) -> list[int] | None:
    try:
        with tempfile.TemporaryDirectory(prefix="c2v09-cosine-probe-") as work:
            binary = Path(work) / "probe.so"
            compiled = subprocess.run(
                ["gcc", "-O2", "-shared", "-fPIC", "-o", str(binary), str(source)],
                capture_output=True,
                text=True,
                check=False,
            )
            if compiled.returncode != 0:
                return None
            library = ctypes.CDLL(str(binary))
            state = (ctypes.c_uint32 * 12)()
            library.read_state(state)
            return [int(word) for word in state]
    except (OSError, AttributeError):
        return None


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
    xcr0 = words[10]
    required = (
        (mxcsr & 0xE040) == 0
        and (mxcsr & 0x1F80) == 0x1F80
        and rounding == "0"
        and (ecx & (1 << 12)) != 0
        and (ecx & (1 << 27)) != 0
        and (ecx & (1 << 28)) != 0
        and (xcr0 & 6) == 6
    )
    return {
        "classification": "OBSERVED",
        "required_bits_ok": required,
        "mxcsr": hex(mxcsr),
        "mxcsr_rounding": "nearest ties-to-even" if ((mxcsr >> 13) & 3) == 0 else "not nearest ties-to-even",
        "mxcsr_daz": bool(mxcsr & 0x40),
        "mxcsr_ftz": bool(mxcsr & 0x8000),
        "x87_control": hex(words[1]),
        "fegetround": rounding,
        "cpuid_leaf1": [hex(word) for word in words[2:6]],
        "cpuid_leaf7_sub0": [hex(word) for word in words[6:10]],
        "xcr0": [hex(words[10]), hex(words[11])],
        "avx": bool(ecx & (1 << 28)),
        "fma": bool(ecx & (1 << 12)),
        "osxsave": bool(ecx & (1 << 27)),
        "xcr0_xmm_ymm": (xcr0 & 6) == 6,
        "exact_historical_xcr0_match": [hex(words[10]), hex(words[11])] == ["0xe7", "0x0"],
        "thread_id": thread_id,
    }


def prepare_cosine_path_certificate(root: Path) -> dict[str, object]:
    """Observe this process's math wrapper and its selected cosine target."""
    located = None
    wrapper = _wrapper_address()
    disassembly = None
    plt_vaddr = None
    if wrapper is not None:
        located = _runtime_to_vaddr(wrapper)
    if located is not None:
        path, vaddr = located
        disassembly = _disassemble(path, vaddr, vaddr + 0xC0)
        if disassembly is not None:
            plt_vaddr = _cos_plt_vaddr(disassembly)
    selected: dict[str, object]
    body_sha = None
    body_vaddr = None
    libm_path = None
    constants: list[dict[str, object]] = []
    if wrapper is None or located is None or disassembly is None or plt_vaddr is None:
        cdll = _cdll_cos()
        selected = {
            "classification": "NOT ESTABLISHED",
            "address": None,
            "evidence": "python wrapper plt got",
            "method": (
                "Disassemble PyCFunction_GetFunction(math.cos) with objdump and follow call cos@plt "
                "to its GOT slot. ctypes.CDLL(libm).cos is not this observation."
            ),
            "independent_cdll_libm_cos": None if cdll is None else hex(cdll),
            "independent_cdll_is_evidence": False,
        }
    else:
        path, wrapper_vaddr = located
        stub_runtime = wrapper + (plt_vaddr - wrapper_vaddr)
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
                    "classification": "NOT ESTABLISHED" if observed is None else ("MATCH" if observed == expected else "MISMATCH"),
                }
            )
    words = _probe_words(root / PROBE_SOURCE)
    rounding = _fegetround()
    features = _feature_record(words, rounding)
    libm_argument = libm_body_verdict(
        selected_observed=selected["classification"] == "OBSERVED",
        features_observed=features["classification"] == "OBSERVED",
        body_sha=body_sha,
        constant_rows=constants,
        required_bits=features["required_bits_ok"] is True,
        body_vaddr=body_vaddr,
        historical_vaddr=historical_vaddr,
    )
    executable = Path(sys.executable).resolve()
    executable_sha = sha256_bytes(executable.read_bytes()) if executable.is_file() else None
    if executable_sha == HISTORICAL_EXECUTABLE_SHA256:
        wrapper_argument = "NOT ESTABLISHED"
    elif executable_sha is None:
        wrapper_argument = "BLOCKED"
    else:
        wrapper_argument = "DOES NOT APPLY"
    loaded_wrapper = None
    if wrapper is not None and _runtime_owner(wrapper) is not None:
        loaded_wrapper = ctypes.string_at(wrapper, 0xC0)
    elf_wrapper = None
    if located is not None:
        elf_wrapper = _elf_bytes(located[0], located[1], 0xC0)
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
            "calls_cos_plt": plt_vaddr is not None,
            "disassembly_source": "objdump of the on-disk ELF; loaded bytes are compared separately",
            "disassembly": disassembly,
            "loaded_wrapper_sha256": None if loaded_wrapper is None else sha256_bytes(loaded_wrapper),
            "loaded_wrapper_matches_elf": loaded_wrapper is not None and loaded_wrapper == elf_wrapper,
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
        "historical_cpython_wrapper_argument": wrapper_argument,
        "applicability_scope": (
            "historical libm body validity predicate for this selected path only; "
            "not exact XCR0 identity, not the historical CPython wrapper, and not eligibility"
        ),
        "historical_body_sha256": HISTORICAL_BODY_SHA256,
        "probe_source_sha256": sha256_bytes((root / PROBE_SOURCE).read_bytes()),
    }
    return {
        "digest_scope": DIGEST_SCOPE,
        "canonical_payload": payload,
        "canonical_sha256": sha256_bytes(canonical_bytes(payload)),
    }
