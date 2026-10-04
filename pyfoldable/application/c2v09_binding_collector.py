"""Zero-source-call observations for the reviewed C2V-09 runtime binding.

File hashes, CPU feature labels and caller claims do not establish loaded
instructions or dispatch. Unreadable ranges stay NOT ESTABLISHED.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import platform
import struct
import subprocess
import sys
import threading
from pathlib import Path

from pyfoldable.application.c2v09_ordered_declaration import (
    CANDIDATE29_MANIFEST_SHA256,
    CONNECTION_RECORD_SHA256,
    COSINE_RECORD_SHA256,
    PRIOR_GEOMETRIC_RECORD_SHA256,
    RUNTIME_BINDING_SHA256,
    canonical_bytes,
    sha256_bytes,
)


LIMITATIONS = (
    "file hashes do not establish loaded instructions",
    "CPU feature labels do not establish dispatch",
    "caller claims are excluded from observations",
    "unavailable ranges stay NOT ESTABLISHED",
    "resolved libm cos symbol is not wrapper or selected-call dispatch",
    "file identity is not loaded-code identity or operation-graph applicability",
    "a blocked observation is a recorded outcome, not eligibility evidence",
)
DIGEST_SCOPE = (
    "SHA-256 of the section 7.3 canonical bytes of canonical_payload only. "
    "canonical_sha256 and digest_scope are outside that payload."
)
CERTIFICATE_SOURCE_COUNT = 21
UNHISTORICAL_MODULES = (
    ("dense", "pyfoldable/dynamics/cmm2_radau_dense.py", "python_source"),
    ("declaration", "pyfoldable/application/c2v09_ordered_declaration.py", "python_source"),
    ("eligibility", "pyfoldable/application/c2v09_live_eligibility.py", "python_source"),
    ("collector", "pyfoldable/application/c2v09_binding_collector.py", "python_source"),
    ("applicability", "pyfoldable/application/c2v09_runtime_applicability.py", "python_source"),
    ("cosine_certificate", "pyfoldable/application/c2v09_cosine_path_certificate.py", "python_source"),
    ("probe_source", "pyfoldable/application/c2v09_cosine_path_probe.c", "c_source"),
)
if len({path for _role, path, _kind in UNHISTORICAL_MODULES}) != len(UNHISTORICAL_MODULES):
    raise RuntimeError("Unhistorical inventory paths are not unique.")


def _git_text(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _map_rows(name_prefix: str) -> list[tuple[int, int, int, str]]:
    maps = Path("/proc/self/maps")
    if not maps.is_file():
        return []
    rows = []
    for line in maps.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 6 or not parts[-1].startswith("/"):
            continue
        if not Path(parts[-1]).name.startswith(name_prefix):
            continue
        start_text, end_text = parts[0].split("-")
        rows.append((int(start_text, 16), int(end_text, 16), int(parts[2], 16), parts[-1]))
    return rows


def _pt_loads(path: str) -> list[tuple[int, int, int, int]]:
    data = Path(path).read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2:
        return []
    e_phoff = struct.unpack_from("<Q", data, 32)[0]
    e_phentsize = struct.unpack_from("<H", data, 54)[0]
    e_phnum = struct.unpack_from("<H", data, 56)[0]
    loads = []
    for index in range(e_phnum):
        offset = e_phoff + index * e_phentsize
        p_type, _flags, p_offset, p_vaddr, _paddr, p_filesz, p_memsz, _align = struct.unpack_from(
            "<IIQQQQQQ", data, offset
        )
        if p_type == 1:
            loads.append((p_offset, p_vaddr, p_filesz, p_memsz))
    return loads


def _library_path(name_prefix: str) -> str | None:
    rows = _map_rows(name_prefix)
    if not rows:
        return None
    return rows[0][3]


def read_loaded_vaddr(path: str, vaddr: int, length: int) -> bytes | None:
    """Read bytes mapped at an ELF virtual address. Failure is not a guess."""
    try:
        loads = _pt_loads(path)
        rows = [row for row in _map_rows(Path(path).name) if row[3] == path]
    except OSError:
        return None
    for p_offset, p_vaddr, _p_filesz, p_memsz in loads:
        if not p_vaddr <= vaddr < p_vaddr + p_memsz:
            continue
        for start, end, file_offset, _mapped in rows:
            if file_offset != p_offset:
                continue
            runtime = start + (vaddr - p_vaddr)
            if runtime < start or runtime + length > end:
                return None
            try:
                return ctypes.string_at(runtime, length)
            except (OSError, ValueError):
                return None
    return None


def resolve_loaded_cos_vaddr() -> str | None:
    """Virtual address of ctypes.CDLL(libm).cos. This is not wrapper dispatch."""
    path = _library_path("libm.so")
    if path is None:
        return None
    try:
        library = ctypes.CDLL(path)
        address = ctypes.cast(library.cos, ctypes.c_void_p).value
        loads = _pt_loads(path)
    except (OSError, AttributeError):
        return None
    if address is None:
        return None
    owner = next((row for row in _map_rows("libm.so") if row[3] == path and row[0] <= address < row[1]), None)
    if owner is None:
        return None
    file_offset = owner[2] + (address - owner[0])
    for p_offset, p_vaddr, p_filesz, _p_memsz in loads:
        if p_offset <= file_offset < p_offset + p_filesz:
            return hex(p_vaddr + (file_offset - p_offset))
    return None


def _cpu_feature_flags() -> list[str] | None:
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.is_file():
        return None
    for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("flags") or line.startswith("Features"):
            _key, value = line.split(":", 1)
            flags = value.split()
            return flags or None
    return None


def _numerical_controls() -> dict[str, str | None]:
    result: dict[str, str | None] = {"fegetround": None, "mxcsr": None, "x87_control": None}
    try:
        libm = ctypes.CDLL("libm.so.6")
        libm.fegetround.restype = ctypes.c_int
        result["fegetround"] = str(libm.fegetround())
    except (OSError, AttributeError):
        return result
    libc_name = platform.libc_ver()[0]
    machine = platform.machine()
    if libc_name != "glibc" or machine not in {"x86_64", "amd64"}:
        return result

    class Fenv(ctypes.Structure):
        _fields_ = [
            ("control", ctypes.c_ushort),
            ("res1", ctypes.c_ushort),
            ("status", ctypes.c_ushort),
            ("res2", ctypes.c_ushort),
            ("tags", ctypes.c_ushort),
            ("res3", ctypes.c_ushort),
            ("eip", ctypes.c_uint),
            ("cs_opcode", ctypes.c_uint),
            ("data_offset", ctypes.c_uint),
            ("data_selector", ctypes.c_ushort),
            ("res5", ctypes.c_ushort),
            ("mxcsr", ctypes.c_uint),
        ]

    if ctypes.sizeof(Fenv) != 32:
        return result
    environment = Fenv()
    libm.fegetenv.argtypes = [ctypes.POINTER(Fenv)]
    libm.fegetenv.restype = ctypes.c_int
    try:
        if libm.fegetenv(ctypes.byref(environment)) != 0:
            return result
    except (OSError, AttributeError):
        return result
    result["mxcsr"] = hex(environment.mxcsr)
    result["x87_control"] = hex(environment.control)
    return result


def _json_body(text: str, index: int) -> str:
    parts = text.split("```json\n")
    if len(parts) <= index + 1:
        raise RuntimeError(f"Reviewed certificate is missing JSON fence {index}.")
    return parts[index + 1].split("```", 1)[0]


def _current_file_sha(root: Path, relative: str) -> str | None:
    if not relative or relative.startswith("/") or "\\" in relative or ".." in Path(relative).parts:
        return None
    path = root / relative
    if not path.is_file():
        return None
    return sha256_bytes(path.read_bytes())


def _identity_row(
    path: str,
    historical: str | None,
    current: str | None,
    file_identity: str,
    identity_kind: str,
) -> dict[str, object]:
    native = "NOT ESTABLISHED" if identity_kind == "c_source" else "NOT A COMPILED IMAGE"
    return {
        "path": path,
        "historical_sha256": historical,
        "current_file_sha256": current,
        "file_identity": file_identity,
        "identity_kind": identity_kind,
        "compiled_loaded_native_identity": native,
        "loaded_code_identity": "NOT ESTABLISHED",
        "operation_graph_applicability": "NOT ESTABLISHED",
    }


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def pinned_certificate_sources(root: Path) -> tuple[tuple[str, str], ...]:
    """Return the digest-verified historical source paths and hashes, in certificate order."""
    certificate = (root / "docs/cmm2_c2v09_partition_runtime_certificate.md").read_text(encoding="utf-8")
    body = _json_body(certificate, 2)
    if sha256_bytes(body.encode("utf-8")) != CONNECTION_RECORD_SHA256:
        raise RuntimeError("Connection record does not match the reviewed digest.")
    parsed = json.loads(body)
    rows = parsed.get("source_code_hashes")
    if not isinstance(rows, list) or len(rows) != CERTIFICATE_SOURCE_COUNT:
        raise RuntimeError("Certificate source inventory is not the reviewed 21 paths.")
    pins: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not _is_sha256(row.get("sha256")):
            raise RuntimeError("Certificate source row is incomplete.")
        path = row["path"]
        if path in seen:
            raise RuntimeError("Certificate source paths are not unique.")
        seen.add(path)
        pins.append((path, row["sha256"]))
    return tuple(pins)


def _python_inventory(root: Path) -> dict[str, object]:
    certificate_sources = []
    for path, historical in pinned_certificate_sources(root):
        current = _current_file_sha(root, path)
        if current is None:
            file_identity = "NOT ESTABLISHED"
        elif current == historical:
            file_identity = "MATCH"
        else:
            file_identity = "MISMATCH"
        certificate_sources.append(_identity_row(path, historical, current, file_identity, "python_source"))
    modules = []
    for role, path, kind in UNHISTORICAL_MODULES:
        current = _current_file_sha(root, path)
        file_identity = "NO HISTORICAL RECORD" if current is not None else "NOT ESTABLISHED"
        modules.append({"role": role, **_identity_row(path, None, current, file_identity, kind)})
    return {
        "certificate_sources": certificate_sources,
        "modules_without_historical_record": modules,
        "identity_separation": {
            "file_identity": "historical file hash compared with current file bytes",
            "loaded_code_identity": "NOT ESTABLISHED",
            "operation_graph_applicability": "NOT ESTABLISHED",
        },
    }


def _binding(root: Path) -> dict[str, object]:
    text = (root / "docs/cmm2_c2v09_partition_runtime_certificate.md").read_text(encoding="utf-8")
    body = text.split("```json\n", 1)[1].split("```", 1)[0]
    if sha256_bytes(body.encode("utf-8")) != RUNTIME_BINDING_SHA256:
        raise RuntimeError("Runtime-binding record does not match the reviewed digest.")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise RuntimeError("Runtime-binding record is not an object.")
    return parsed


def _classify_bytes(name: str, observed: bytes | None, expected: bytes, matches: list[str], mismatches: list[str], missing: list[str]) -> str:
    if observed is None:
        missing.append(name)
        return "NOT ESTABLISHED"
    if observed == expected:
        matches.append(name)
        return "MATCH"
    mismatches.append(name)
    return "MISMATCH"


def collect_binding_record(root: Path) -> dict[str, object]:
    """Observe the executing process without a motor, load, or integration call."""
    binding = _binding(root)
    matches: list[str] = []
    mismatches: list[str] = []
    missing: list[str] = []
    libm_path = _library_path("libm.so")
    libc_path = _library_path("libc.so")
    loader_path = _library_path("ld-linux")
    executable = Path(sys.executable)
    controls = _numerical_controls()
    flags = _cpu_feature_flags()
    resolved = resolve_loaded_cos_vaddr()
    expected_vaddr = str(binding["resolved_cos_body_vaddr"])
    missing.append("wrapper/selected-call dispatch")
    if resolved is None:
        missing.append("resolved libm cos symbol")
    elif resolved == expected_vaddr:
        matches.append("resolved libm cos symbol")
    else:
        mismatches.append("resolved libm cos symbol")

    expected_body = bytes.fromhex(str(binding["resolved_cos_body_bytes_hex"]))
    loaded_body = None
    if libm_path is not None:
        loaded_body = read_loaded_vaddr(libm_path, int(expected_vaddr, 16), len(expected_body))
    body_class = _classify_bytes("loaded certificate cos body", loaded_body, expected_body, matches, mismatches, missing)

    constants = binding["constants"]
    constant_rows = []
    if isinstance(constants, dict):
        for vaddr, spec in constants.items():
            if not isinstance(spec, dict):
                missing.append(f"loaded constant {vaddr}")
                constant_rows.append({"vaddr": vaddr, "classification": "NOT ESTABLISHED"})
                continue
            expected = bytes.fromhex(str(spec["little_endian_bytes_hex"]))
            observed = None if libm_path is None else read_loaded_vaddr(libm_path, int(vaddr, 16), len(expected))
            classification = _classify_bytes(f"loaded constant {vaddr}", observed, expected, matches, mismatches, missing)
            constant_rows.append({"vaddr": str(vaddr), "classification": classification})

    certificate_executable = binding["artifacts"]["CPython_builtin_math"]["sha256"]
    certificate_libm = binding["artifacts"]["libm"]["sha256"]
    executable_sha = sha256_bytes(executable.read_bytes()) if executable.is_file() else None
    libm_sha = sha256_bytes(Path(libm_path).read_bytes()) if libm_path else None
    _classify_bytes(
        "executable file identity",
        None if executable_sha is None else bytes.fromhex(executable_sha),
        bytes.fromhex(str(certificate_executable)),
        matches,
        mismatches,
        missing,
    )
    _classify_bytes(
        "libm file identity",
        None if libm_sha is None else bytes.fromhex(libm_sha),
        bytes.fromhex(str(certificate_libm)),
        matches,
        mismatches,
        missing,
    )

    additional = []
    for name in ("numpy", "scipy"):
        module = sys.modules.get(name)
        if module is None:
            continue
        additional.append({"name": name, "file": getattr(module, "__file__", None)})

    thread_id = str(threading.get_native_id()) if hasattr(threading, "get_native_id") else str(threading.get_ident())
    payload = {
        "outcome": "recorded partial observation",
        "eligibility_evidence": False,
        "physical_qualification": False,
        "checkout_sha": _git_text(root, "rev-parse", "HEAD"),
        "tree_sha": _git_text(root, "rev-parse", "HEAD^{tree}"),
        "runtime": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "executable": str(executable),
        },
        "historical_capsules": {
            "runtime_binding_sha256": RUNTIME_BINDING_SHA256,
            "cosine_record_sha256": COSINE_RECORD_SHA256,
            "prior_geometric_record_sha256": PRIOR_GEOMETRIC_RECORD_SHA256,
            "connection_record_sha256": CONNECTION_RECORD_SHA256,
            "candidate29_manifest_sha256": CANDIDATE29_MANIFEST_SHA256,
        },
        "reviewed_conditional_graph": {
            "cos_body_vaddr": expected_vaddr,
            "cos_body_length": len(expected_body),
            "wrapper_vaddr": str(binding.get("math_cos_wrapper_vaddr")),
            "constant_vaddrs": [str(vaddr) for vaddr in constants] if isinstance(constants, dict) else [],
        },
        "executing_dependencies": {
            "executable": {"path": str(executable), "file_sha256": executable_sha},
            "libm": {"path": libm_path, "file_sha256": libm_sha},
            "libc": {"path": libc_path, "file_sha256": sha256_bytes(Path(libc_path).read_bytes()) if libc_path else None},
            "loader": {
                "path": loader_path,
                "file_sha256": sha256_bytes(Path(loader_path).read_bytes()) if loader_path else None,
            },
            "additional": additional,
        },
        "python_dependency_inventory": _python_inventory(root),
        "observations": {
            "resolved_libm_cos_symbol_vaddr": resolved,
            "wrapper_selected_call_dispatch": None,
            "loaded_cos_body": body_class,
            "loaded_constants": constant_rows,
            "cpu_feature_flags": flags,
            "thread_id": thread_id,
            "fegetround": controls["fegetround"],
            "mxcsr": controls["mxcsr"],
            "x87_control": controls["x87_control"],
            "loaded_dispatch_inferred_from_cpu": False,
        },
        "classifications": {
            "matches": matches,
            "mismatches": mismatches,
            "not_established": missing,
        },
        "limitations": list(LIMITATIONS),
        "source_callbacks": 0,
    }
    return {
        "digest_scope": DIGEST_SCOPE,
        "canonical_payload": payload,
        "canonical_sha256": sha256_bytes(canonical_bytes(payload)),
    }
