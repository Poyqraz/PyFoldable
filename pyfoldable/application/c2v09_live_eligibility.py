"""Live eligibility gate for the reviewed C2V-09 scope-A certificate.

Version labels, archived replay, sampled outputs and caller-supplied records
do not establish eligibility. This slice stops before source, mapper,
selection, sealing and trajectory entry.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import secrets
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Mapping

from pyfoldable.application.c2v09_binding_collector import (
    collect_binding_record,
    resolve_loaded_cos_vaddr,
)
from pyfoldable.application.c2v09_ordered_declaration import (
    CANDIDATE28_MANIFEST_SHA256,
    CANDIDATE29_MANIFEST_SHA256,
    EXTENDED_DECLARATION_SHA256,
    ORIGINAL_MANIFEST_SHA256,
    TECHNICAL_HEAD,
    ReviewedMaterials,
    build_extended_declaration,
    load_reviewed_materials,
    sha256_bytes,
)


CONTRACT_BLOCKED = "CONTRACT BLOCKED"
_PROCESS_NONCE = secrets.token_hex(32)


def _git_text(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _library_path(token: str) -> Path | None:
    maps = Path("/proc/self/maps")
    if not maps.is_file():
        return None
    for line in maps.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 6 or not parts[-1].startswith("/"):
            continue
        if parts[-1].rsplit("/", 1)[-1].startswith(token):
            return Path(parts[-1])
    return None


def _file_sha256(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    return sha256_bytes(path.read_bytes())


def _fegetround() -> str | None:
    try:
        libm = ctypes.CDLL("libm.so.6")
        libm.fegetround.restype = ctypes.c_int
        return str(libm.fegetround())
    except (OSError, AttributeError):
        return None


def _cpu_identity() -> tuple[str, str, str] | None:
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.is_file():
        return None
    fields: dict[str, str] = {}
    for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields.setdefault(key.strip(), value.strip())
    family = fields.get("cpu family")
    model = fields.get("model")
    stepping = fields.get("stepping")
    if family is None or model is None or stepping is None:
        return None
    return family, model, stepping


def observe_execution_context(root: Path) -> dict[str, object]:
    """Read the executing process. Missing probes stay None."""
    return {
        "executing_head": _git_text(root, "rev-parse", "HEAD"),
        "python_version": sys.version.split()[0],
        "executable_sha256": _file_sha256(Path(sys.executable)),
        "libm_sha256": _file_sha256(_library_path("libm.so")),
        "libc_sha256": _file_sha256(_library_path("libc.so")),
        "loader_sha256": _file_sha256(_library_path("ld-linux")),
        "cpu_family_model_stepping": _cpu_identity(),
        "fegetround": _fegetround(),
        "loaded_cosine_instruction_bytes": None,
        "returned_source_object": None,
    }


def _token(status: str, mismatches: tuple[str, ...], unestablished: tuple[str, ...], context_id: str, invalidated: bool) -> str:
    payload = "\n".join((_PROCESS_NONCE, status, context_id, str(invalidated), *mismatches, *unestablished))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _context_id(observations: Mapping[str, object]) -> str:
    text = "|".join(
        str(observations.get(name))
        for name in ("executable_sha256", "libm_sha256", "libc_sha256", "loader_sha256", "fegetround", "executing_head")
    )
    return hashlib.sha256(f"{text}|{os.getpid()}".encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Acceptance:
    accepted: bool
    reason: str


@dataclass(frozen=True)
class LiveEligibilityRecord:
    status: str
    matches: tuple[str, ...]
    mismatches: tuple[str, ...]
    unestablished: tuple[str, ...]
    observations: Mapping[str, object]
    executing_head: str
    context_id: str
    invalidated: bool
    partial_record: Mapping[str, object]
    token: str
    root: Path

    def authentic(self) -> bool:
        return self.token == _token(self.status, self.mismatches, self.unestablished, self.context_id, self.invalidated)

    def accept(self, *, context_id: str) -> Acceptance:
        try:
            current = _context_id(observe_execution_context(self.root))
        except (OSError, subprocess.CalledProcessError) as exc:
            return Acceptance(False, f"execution context unavailable: {exc}")
        if current != self.context_id or context_id != current:
            return Acceptance(False, "stale eligibility context")
        if not self.authentic():
            return Acceptance(False, "not live execution evidence")
        if self.invalidated or self.status != "ELIGIBLE":
            return Acceptance(False, self.status)
        return Acceptance(False, "eligibility is not established")

    def check_after(self, *, fegetround: str) -> "LiveEligibilityRecord":
        try:
            observed = observe_execution_context(self.root)
            current = _context_id(observed)
            live_rounding = None if observed.get("fegetround") is None else str(observed.get("fegetround"))
        except (OSError, subprocess.CalledProcessError):
            current = ""
            live_rounding = None
        recorded = None if self.observations.get("fegetround") is None else str(self.observations.get("fegetround"))
        changed = current != self.context_id or live_rounding != fegetround or recorded != fegetround
        if not changed:
            return self
        mismatches = self.mismatches + ("post-call numerical-control change",)
        updated = replace(self, status=CONTRACT_BLOCKED, mismatches=mismatches, invalidated=True, token="")
        return replace(
            updated,
            token=_token(updated.status, updated.mismatches, updated.unestablished, updated.context_id, updated.invalidated),
        )


@dataclass(frozen=True)
class DependentCallReport:
    record: LiveEligibilityRecord
    source_calls: int
    mapper_calls: int
    selection_calls: int
    seal_calls: int
    trajectory_calls: int


def _blocked(root: Path, reason: str) -> LiveEligibilityRecord:
    try:
        observations: Mapping[str, object] = observe_execution_context(root)
        executing_head = str(observations.get("executing_head") or "")
        context_id = _context_id(observations)
    except (OSError, subprocess.CalledProcessError):
        observations = {}
        executing_head = ""
        context_id = "unavailable"
    mismatches = (f"technical-head artifact bytes unavailable: {reason}",)
    unestablished = (
        "returned source object",
        "loaded cosine instruction bytes",
        "MXCSR",
        "DAZ/FTZ",
        "CPU family/model/stepping",
        "CPU features",
        "selected dispatch",
        "loader identity",
    )
    return LiveEligibilityRecord(
        CONTRACT_BLOCKED,
        (),
        mismatches,
        unestablished,
        observations,
        executing_head,
        context_id,
        False,
        {"selection": None, "sealed": False, "trajectory_entered": False, "declaration_sha256": None},
        _token(CONTRACT_BLOCKED, mismatches, unestablished, context_id, False),
        root,
    )


def _compare_bytes(name: str, data: bytes, expected: str, matches: list[str], mismatches: list[str]) -> None:
    if sha256_bytes(data) == expected:
        matches.append(name)
        return
    mismatches.append(f"{name} digest")


def _compare_identity(name: str, observed: object, expected: str, matches: list[str], mismatches: list[str], unestablished: list[str]) -> None:
    if observed is None:
        unestablished.append(name)
        return
    if str(observed) == expected:
        matches.append(name)
        return
    mismatches.append(name)


def _technical_authority_bytes(root: Path, path: str) -> bytes | None:
    """Load one artifact at the frozen technical HEAD. Absence is not a mismatch."""
    try:
        return subprocess.check_output(
            ["git", "show", f"{TECHNICAL_HEAD}:{path}"],
            cwd=root,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None


def assess_live_eligibility(
    root: Path,
    *,
    materials: ReviewedMaterials | None = None,
    theta0: tuple[str, str] | None = None,
    uncertainty_hex: tuple[str, ...] | None = None,
    source_sha256: str | None = None,
    caller_claims: Mapping[str, object] | None = None,
    waive_source_mismatch: bool = False,
    claimed_record: Mapping[str, object] | None = None,
) -> LiveEligibilityRecord:
    """Compare the executing context with the reviewed bindings.

    ``waive_source_mismatch`` is accepted and ignored. Caller-supplied
    materials are claims. They are compared with the pinned declaration.
    """
    del waive_source_mismatch
    try:
        return _assess(
            root,
            materials=materials,
            theta0=theta0,
            uncertainty_hex=uncertainty_hex,
            source_sha256=source_sha256,
            caller_claims=caller_claims,
            claimed_record=claimed_record,
        )
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        return _blocked(root, str(exc))


def _classify_actual(name: str, supplied, pinned_value, matches: list[str], mismatches: list[str], unestablished: list[str], mismatch_text: str) -> None:
    """Pinned defaults are not live observations."""
    if supplied is None:
        unestablished.append(name)
        return
    if supplied != pinned_value:
        mismatches.append(mismatch_text)
        return
    matches.append(name)


def _assess(
    root: Path,
    *,
    materials: ReviewedMaterials | None,
    theta0: tuple[str, str] | None,
    uncertainty_hex: tuple[str, ...] | None,
    source_sha256: str | None,
    caller_claims: Mapping[str, object] | None,
    claimed_record: Mapping[str, object] | None,
) -> LiveEligibilityRecord:
    pinned = load_reviewed_materials(root)
    claimed = pinned if materials is None else materials
    declaration = build_extended_declaration(root)
    observations = observe_execution_context(root)
    binding = collect_binding_record(root)
    if "selected_dispatch" not in observations:
        observations["selected_dispatch"] = resolve_loaded_cos_vaddr()
    if "mxcsr" not in observations and binding["observations"]["mxcsr"] is not None:
        observations["mxcsr"] = binding["observations"]["mxcsr"]
    if "cpu_feature_flags" not in observations:
        observations["cpu_feature_flags"] = binding["observations"]["cpu_feature_flags"]
    runtime = pinned.certificate_runtime
    matches: list[str] = []
    mismatches: list[str] = []
    unestablished: list[str] = [
        "returned source object",
        "loaded cosine instruction bytes",
        "MXCSR",
        "DAZ/FTZ",
        "CPU features",
        "selected dispatch",
    ]
    closure_provenance: list[str] = []

    if claimed_record is not None:
        mismatches.append("caller-supplied record is not live execution evidence")

    _compare_bytes("original 00-27 manifest", claimed.original_bytes, ORIGINAL_MANIFEST_SHA256, matches, mismatches)
    _compare_bytes("candidate28 manifest", claimed.candidate28_bytes, CANDIDATE28_MANIFEST_SHA256, matches, mismatches)
    _compare_bytes("candidate29 manifest", claimed.candidate29_bytes, CANDIDATE29_MANIFEST_SHA256, matches, mismatches)

    for path, pinned_digest in pinned.artifact_digests.items():
        if claimed.artifact_digests.get(path) != pinned_digest:
            mismatches.append(f"artifact identity {path}")
        else:
            matches.append(f"artifact {path}")
        loaded = _technical_authority_bytes(root, path)
        if loaded is None:
            unestablished.append(f"technical authority {path}")
        elif sha256_bytes(loaded) != pinned_digest:
            mismatches.append(f"technical authority {path}")
        else:
            matches.append(f"technical authority {path}")
        current = root / path
        if current.is_file() and sha256_bytes(current.read_bytes()) != pinned_digest:
            closure_provenance.append(path)

    supplied_theta = theta0
    if supplied_theta is None and materials is not None and materials.theta0 != pinned.theta0:
        supplied_theta = materials.theta0
    _classify_actual(
        "Theta0",
        None if supplied_theta is None else tuple(supplied_theta),
        tuple(pinned.theta0),
        matches,
        mismatches,
        unestablished,
        "Theta0 scale binding",
    )
    supplied_uncertainty = uncertainty_hex
    if supplied_uncertainty is None and materials is not None and materials.uncertainty_hex != pinned.uncertainty_hex:
        supplied_uncertainty = materials.uncertainty_hex
    _classify_actual(
        "stored center uncertainty",
        None if supplied_uncertainty is None else tuple(supplied_uncertainty),
        tuple(pinned.uncertainty_hex),
        matches,
        mismatches,
        unestablished,
        "stored center uncertainty",
    )
    supplied_source = source_sha256
    if supplied_source is None and materials is not None and materials.candidate29_source_sha256 != pinned.candidate29_source_sha256:
        supplied_source = materials.candidate29_source_sha256
    _classify_actual(
        "candidate29 source bytes",
        supplied_source,
        pinned.candidate29_source_sha256,
        matches,
        mismatches,
        unestablished,
        "candidate29 source hash",
    )

    executing_head = str(observations["executing_head"])
    observations["technical_head"] = TECHNICAL_HEAD
    observations["closure_provenance"] = tuple(closure_provenance)
    observations["caller_claims"] = dict(caller_claims or {})

    _compare_identity("cpython executable", observations["executable_sha256"], runtime["executable_sha256"], matches, mismatches, unestablished)
    _compare_identity("cpython version", observations["python_version"], runtime["python_version"], matches, mismatches, unestablished)
    _compare_identity("libm identity", observations["libm_sha256"], runtime["libm_sha256"], matches, mismatches, unestablished)
    _compare_identity("libc identity", observations["libc_sha256"], runtime["libc_sha256"], matches, mismatches, unestablished)
    _compare_identity("loader identity", observations["loader_sha256"], runtime["loader_sha256"], matches, mismatches, unestablished)
    _compare_identity("fegetround", observations["fegetround"], runtime["fegetround"], matches, mismatches, unestablished)
    cpu = observations["cpu_family_model_stepping"]
    expected_cpu = (runtime["cpu_family"], runtime["cpu_model"], runtime["cpu_stepping"])
    if cpu is None:
        unestablished.append("CPU family/model/stepping")
    elif tuple(cpu) != expected_cpu:
        mismatches.append("CPU family/model/stepping")
    else:
        matches.append("CPU family/model/stepping")
    if observations.get("selected_dispatch") is not None:
        unestablished.remove("selected dispatch")
        if str(observations["selected_dispatch"]) == runtime["cos_vaddr"]:
            matches.append("selected dispatch")
        else:
            mismatches.append("selected dispatch")
    if observations.get("mxcsr"):
        unestablished.remove("MXCSR")
        unestablished.remove("DAZ/FTZ")
        if str(observations["mxcsr"]).lower() == str(runtime["mxcsr_hex"]).lower():
            matches.append("MXCSR")
        else:
            mismatches.append("MXCSR")
        control = int(str(observations["mxcsr"]), 16)
        daz = str(bool(control & 0x40))
        ftz = str(bool(control & 0x8000))
        if daz == runtime["mxcsr_daz"] and ftz == runtime["mxcsr_ftz"]:
            matches.append("DAZ/FTZ")
        else:
            mismatches.append("DAZ/FTZ")

    if declaration.sha256 != EXTENDED_DECLARATION_SHA256:
        mismatches.append("extended declaration digest")
    else:
        matches.append("extended declaration digest")

    status = CONTRACT_BLOCKED if mismatches or unestablished else "ELIGIBLE"
    partial = {
        "selection": None,
        "sealed": False,
        "trajectory_entered": False,
        "declaration_sha256": declaration.sha256,
        "binding_record": binding,
    }
    context_id = _context_id(observations)
    mismatch_tuple = tuple(mismatches)
    unestablished_tuple = tuple(unestablished)
    return LiveEligibilityRecord(
        status,
        tuple(matches),
        mismatch_tuple,
        unestablished_tuple,
        observations,
        executing_head,
        context_id,
        False,
        partial,
        _token(status, mismatch_tuple, unestablished_tuple, context_id, False),
        root,
    )


def run_certificate_dependent(
    record: LiveEligibilityRecord,
    *,
    source: Callable[[], object] | None = None,
    mapper: Callable[[], object] | None = None,
    select: Callable[[], object] | None = None,
    seal: Callable[[], object] | None = None,
    trajectory: Callable[[], object] | None = None,
) -> DependentCallReport:
    """Count certificate-dependent calls. This slice does not invoke them."""
    refused = (source, mapper, select, seal, trajectory)
    counts = {name: 0 for name, _callback in zip(("source", "mapper", "selection", "seal", "trajectory"), refused, strict=True)}
    if record.authentic() and record.status == "ELIGIBLE" and not record.invalidated:
        raise RuntimeError("Certificate-dependent execution is not part of this preparation slice.")
    return DependentCallReport(
        record,
        counts["source"],
        counts["mapper"],
        counts["selection"],
        counts["seal"],
        counts["trajectory"],
    )
