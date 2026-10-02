"""Live eligibility gate for the reviewed C2V-09 scope-A certificate.

Version labels, archived replay, sampled outputs and caller-supplied records
do not establish eligibility. This slice stops before source, mapper,
selection, sealing and trajectory entry.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Mapping

from pyfoldable.application.c2v09_ordered_declaration import (
    CANDIDATE28_MANIFEST_SHA256,
    CANDIDATE29_MANIFEST_SHA256,
    ORIGINAL_MANIFEST_SHA256,
    TECHNICAL_HEAD,
    ReviewedMaterials,
    build_extended_declaration,
    load_reviewed_materials,
    sha256_bytes,
    technical_file_bytes,
)


CERTIFICATE_EXECUTABLE_SHA256 = "fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7"
CERTIFICATE_LIBM_SHA256 = "f06f2ce1f1833df5f41cf13b6447ff07bea993ad9b27297d3428c2f70ab3f0e7"
CERTIFICATE_PYTHON_VERSION = "3.12.14"
CONTRACT_BLOCKED = "CONTRACT BLOCKED"


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


def observe_execution_context(root: Path) -> dict[str, object]:
    """Read the executing process. Missing probes stay None."""
    executable = Path(sys.executable)
    libm = _library_path("libm.so")
    libc = _library_path("libc.so")
    return {
        "executing_head": _git_text(root, "rev-parse", "HEAD"),
        "python_version": sys.version.split()[0],
        "executable_sha256": _file_sha256(executable),
        "libm_sha256": _file_sha256(libm),
        "libc_sha256": _file_sha256(libc),
        "fegetround": _fegetround(),
        "mxcsr": None,
        "loaded_cosine_instruction_bytes": None,
        "returned_source_object": None,
    }


def _token(status: str, mismatches: tuple[str, ...], unestablished: tuple[str, ...], context_id: str, invalidated: bool) -> str:
    payload = "\n".join((status, context_id, str(invalidated), *mismatches, *unestablished))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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

    def authentic(self) -> bool:
        return self.token == _token(self.status, self.mismatches, self.unestablished, self.context_id, self.invalidated)

    def accept(self, *, context_id: str) -> Acceptance:
        if context_id != self.context_id:
            return Acceptance(False, "stale eligibility context")
        if not self.authentic():
            return Acceptance(False, "not live execution evidence")
        if self.invalidated or self.status != "ELIGIBLE":
            return Acceptance(False, self.status)
        return Acceptance(False, "eligibility is not established")

    def check_after(self, *, fegetround: str) -> "LiveEligibilityRecord":
        observed = self.observations.get("fegetround")
        if fegetround == (None if observed is None else str(observed)):
            return self
        mismatches = self.mismatches + ("post-call numerical-control change",)
        updated = replace(self, status=CONTRACT_BLOCKED, mismatches=mismatches, invalidated=True, token="")
        return replace(updated, token=_token(updated.status, updated.mismatches, updated.unestablished, updated.context_id, updated.invalidated))


@dataclass(frozen=True)
class DependentCallReport:
    record: LiveEligibilityRecord
    source_calls: int = 0
    mapper_calls: int = 0
    selection_calls: int = 0
    seal_calls: int = 0
    trajectory_calls: int = 0


def _context_id(observations: Mapping[str, object]) -> str:
    text = "|".join(
        str(observations.get(name))
        for name in ("executable_sha256", "libm_sha256", "fegetround", "executing_head")
    )
    text = f"{text}|{os.getpid()}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def assess_live_eligibility(
    root: Path,
    *,
    materials: ReviewedMaterials | None = None,
    theta0: tuple[str, str] | None = None,
    uncertainty_hex: tuple[str, ...] | None = None,
    source_sha256: str | None = None,
    waive_source_mismatch: bool = False,
    claimed_record: Mapping[str, object] | None = None,
) -> LiveEligibilityRecord:
    """Compare the executing context with the reviewed bindings.

    ``waive_source_mismatch`` is accepted and ignored. A caller cannot waive
    a source, runtime, scale or artifact mismatch.
    """
    del waive_source_mismatch
    reviewed = load_reviewed_materials(root) if materials is None else materials
    declaration = build_extended_declaration(root)
    observations = observe_execution_context(root)
    matches: list[str] = []
    mismatches: list[str] = []
    unestablished: list[str] = ["returned source object", "loaded cosine instruction bytes"]

    if claimed_record is not None:
        mismatches.append("caller-supplied record is not live execution evidence")

    _compare_bytes("original 00-27 manifest", reviewed.original_bytes, ORIGINAL_MANIFEST_SHA256, matches, mismatches)
    _compare_bytes("candidate28 manifest", reviewed.candidate28_bytes, CANDIDATE28_MANIFEST_SHA256, matches, mismatches)
    _compare_bytes("candidate29 manifest", reviewed.candidate29_bytes, CANDIDATE29_MANIFEST_SHA256, matches, mismatches)

    for path, claimed in reviewed.artifact_digests.items():
        technical = technical_file_bytes(root, path)
        if claimed != sha256_bytes(technical):
            mismatches.append(f"artifact identity {path}")
        else:
            matches.append(f"artifact {path}")
        current = root / path
        if not current.is_file() or current.read_bytes() != technical:
            mismatches.append(f"executing artifact bytes differ from technical head {path}")

    supplied_theta = reviewed.theta0 if theta0 is None else theta0
    if tuple(supplied_theta) != reviewed.theta0:
        mismatches.append("Theta0 scale binding")
    else:
        matches.append("Theta0")

    if uncertainty_hex is not None and tuple(uncertainty_hex) != reviewed.uncertainty_hex:
        mismatches.append("stored center uncertainty")
    else:
        matches.append("stored center uncertainty")

    expected_source = reviewed.candidate29_source_sha256
    supplied_source = expected_source if source_sha256 is None else source_sha256
    if supplied_source != expected_source:
        mismatches.append("candidate29 source hash")
    else:
        matches.append("candidate29 source hash")

    executing_head = str(observations["executing_head"])
    if executing_head != TECHNICAL_HEAD:
        mismatches.append("reviewed technical head")
    else:
        matches.append("reviewed technical head")

    if observations["executable_sha256"] != CERTIFICATE_EXECUTABLE_SHA256:
        mismatches.append("cpython executable")
    else:
        matches.append("cpython executable")

    if observations["python_version"] != CERTIFICATE_PYTHON_VERSION:
        mismatches.append("cpython version")
    else:
        matches.append("cpython version")

    if observations["mxcsr"] is None:
        unestablished.append("MXCSR")
    if observations["fegetround"] is None:
        unestablished.append("fegetround")
    elif observations["fegetround"] == "0":
        matches.append("fegetround")
    else:
        mismatches.append("fegetround")
    if observations["libm_sha256"] is None:
        unestablished.append("libm identity")
    elif observations["libm_sha256"] != CERTIFICATE_LIBM_SHA256:
        mismatches.append("libm identity")
    else:
        matches.append("libm identity")

    if declaration.sha256 != build_extended_declaration(root).sha256:
        mismatches.append("extended declaration digest")
    else:
        matches.append("extended declaration digest")

    status = CONTRACT_BLOCKED if mismatches or unestablished else "ELIGIBLE"
    partial = {
        "selection": None,
        "sealed": False,
        "trajectory_entered": False,
        "declaration_sha256": declaration.sha256,
    }
    context_id = _context_id(observations)
    mismatch_tuple = tuple(mismatches)
    unestablished_tuple = tuple(unestablished)
    token = _token(status, mismatch_tuple, unestablished_tuple, context_id, False)
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
        token,
    )


def _compare_bytes(name: str, data: bytes, expected: str, matches: list[str], mismatches: list[str]) -> None:
    if sha256_bytes(data) == expected:
        matches.append(name)
        return
    mismatches.append(f"{name} digest")


def run_certificate_dependent(
    record: LiveEligibilityRecord,
    *,
    source: Callable[[], object] | None = None,
    mapper: Callable[[], object] | None = None,
    select: Callable[[], object] | None = None,
    seal: Callable[[], object] | None = None,
    trajectory: Callable[[], object] | None = None,
) -> DependentCallReport:
    """Refuse certificate-dependent work unless a live eligible record exists.

    This preparation slice never calls the supplied functions. A forged
    eligible record is not live evidence.
    """
    del source, mapper, select, seal, trajectory
    if record.authentic() and record.status == "ELIGIBLE" and not record.invalidated:
        raise RuntimeError("Certificate-dependent execution is not part of this preparation slice.")
    return DependentCallReport(record)
