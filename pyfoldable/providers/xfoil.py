"""Subprocess adapter for XFOIL polar generation."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..core.airfoil import airfoil_coordinate_sha256
from ..core.providers import _canonical_value
from ..core.providers import (
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarPointResult,
    PolarProviderCapabilityError,
    PolarProviderExecutionError,
    PolarProviderTimeoutError,
    PolarProviderUnavailableError,
    ProviderCapabilities,
    ProviderIdentity,
)


_ADAPTER_VERSION = "2"
_AIRFOIL_FILENAME = "airfoil.dat"
_POLAR_FILENAME = "polar.txt"
_ALPHA_MATCH_TOLERANCE_DEG = 1.0e-3
_VERSION_PATTERN = re.compile(
    r"\bXFOIL(?:\s+Version)?\s+([0-9]+(?:\.[0-9A-Za-z.-]+)*)",
    re.IGNORECASE,
)
_CAPABILITIES = ProviderCapabilities(
    supports_mach=True,
    supports_n_crit=True,
    supports_forced_transition=True,
    supports_pointwise_confidence=False,
    supports_partial_results=True,
    supports_vectorized_alpha=False,
    supports_iteration_limit=True,
    supports_timeout=True,
)
_ALLOWED_OPTIONS = {"repanel"}
_DECLARED_XFOIL_BUILD_POLICY = {
    "source_url": "https://web.mit.edu/drela/Public/web/xfoil/xfoil6.99.tgz",
    "source_archive_sha256": "5c0250643f52ce0e75d7338ae2504ce7907f2d49a30f921826717b8ac12ebe40",
    "fortran_flags": "-O2 -fdefault-real-8 -fallow-argument-mismatch",
    "ubuntu_dfsg_package_allowed": False,
    "verified_against_this_executable": False,
    "role": (
        "Declared build requirement only. A capture does not rebuild XFOIL "
        "and does not prove that the executable was produced from this archive or these flags."
    ),
}


@dataclass(frozen=True)
class _PolarRow:
    alpha_deg: float
    cl: float
    cd: float
    cm: float


class XfoilProvider:
    """Generate viscous polars by driving an XFOIL executable over stdin."""

    capabilities = _CAPABILITIES

    def __init__(
        self,
        executable: str | os.PathLike[str] = "xfoil",
        *,
        backend_version: str | None = None,
        version_timeout_s: float = 5.0,
    ) -> None:
        self._executable = _resolve_executable(executable)
        if not math.isfinite(version_timeout_s) or version_timeout_s <= 0.0:
            raise ValueError("version_timeout_s must be finite and greater than zero.")
        version = backend_version or _discover_backend_version(
            self._executable,
            timeout_s=version_timeout_s,
        )
        self._identity = ProviderIdentity(
            name="xfoil-subprocess",
            adapter_version=_ADAPTER_VERSION,
            backend_name="XFOIL",
            backend_version=version,
        )

    @property
    def executable(self) -> str:
        return self._executable

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    def generate(
        self,
        request: PolarGenerationRequest,
        *,
        capture_dir: str | os.PathLike[str] | None = None,
    ) -> PolarGenerationResult:
        """Run one isolated XFOIL session and reconcile its saved polar rows.

        ``capture_dir`` is off by default. When set, the receipt is written
        outside the temporary directory before that directory is removed,
        including timeout, nonzero-exit, and unreadable-polar paths. A failed
        capture does not return an evidence-complete success.
        """
        request.validate_capabilities(self.capabilities)
        options = _validated_options(request.options)
        started = time.perf_counter()
        capture_evidence_ready: bool | None = None
        capture_request_sha256: str | None = None

        with tempfile.TemporaryDirectory(prefix="pyfoldable-xfoil-") as temporary:
            working_directory = Path(temporary)
            airfoil_path = working_directory / _AIRFOIL_FILENAME
            _write_airfoil(airfoil_path, request)
            command_script = _build_command_script(request, options)
            airfoil_bytes = airfoil_path.read_bytes()
            script_bytes = command_script.encode("utf-8")
            prelaunch_executable = _executable_identity(self.executable) if capture_dir is not None else None
            try:
                completed = subprocess.run(
                    [self.executable],
                    input=script_bytes,
                    cwd=working_directory,
                    capture_output=True,
                    timeout=request.timeout_s,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                self._persist_capture(
                    capture_dir, request, airfoil_bytes, script_bytes, working_directory,
                    process_status="timeout", returncode=None,
                    stdout=error.stdout, stderr=error.stderr, partial_streams=True,
                    points=_unavailable_points(request, "Timeout occurred before a complete polar file could be established."),
                    parsed=False, decoding_status="not_attempted",
                    prelaunch_executable=prelaunch_executable,
                )
                raise PolarProviderTimeoutError(
                    f"XFOIL exceeded the {request.timeout_s:g} s request timeout."
                ) from error
            except OSError as error:
                self._persist_capture(
                    capture_dir, request, airfoil_bytes, script_bytes, working_directory,
                    process_status="start_failed", returncode=None,
                    stdout=None, stderr=None, partial_streams=False,
                    points=_unavailable_points(request, "The executable did not start."),
                    parsed=False, decoding_status="unavailable",
                    prelaunch_executable=prelaunch_executable,
                )
                raise PolarProviderUnavailableError(
                    f"XFOIL executable could not be started: {self.executable}."
                ) from error

            elapsed_s = time.perf_counter() - started
            stdout_text = _replacement_text(completed.stdout)
            stderr_text = _replacement_text(completed.stderr)
            polar_path = working_directory / _POLAR_FILENAME
            if completed.returncode != 0:
                self._persist_capture(
                    capture_dir, request, airfoil_bytes, script_bytes, working_directory,
                    process_status="completed", returncode=completed.returncode,
                    stdout=completed.stdout, stderr=completed.stderr, partial_streams=False,
                    points=_unavailable_points(
                        request, "Nonzero exit occurred; point disposition was not inferred from a missing or unused polar."
                    ),
                    parsed=False, decoding_status="not_attempted",
                    prelaunch_executable=prelaunch_executable,
                )
                diagnostics = _diagnostic_tail(stdout_text, stderr_text)
                raise PolarProviderExecutionError(
                    f"XFOIL exited with status {completed.returncode}.{diagnostics}"
                )

            polar_read, polar_bytes, polar_read_error = _read_polar_file(polar_path)
            if polar_read == "read_failed":
                self._persist_capture(
                    capture_dir, request, airfoil_bytes, script_bytes, working_directory,
                    process_status="completed", returncode=completed.returncode,
                    stdout=completed.stdout, stderr=completed.stderr, partial_streams=False,
                    points=_unavailable_points(request, "The polar file could not be read."),
                    parsed=False, decoding_status="not_attempted",
                    prelaunch_executable=prelaunch_executable,
                    polar_read="read_failed", polar_read_error=polar_read_error,
                )
                raise PolarProviderExecutionError("XFOIL polar file could not be read.")
            if polar_read == "unavailable":
                self._persist_capture(
                    capture_dir, request, airfoil_bytes, script_bytes, working_directory,
                    process_status="completed", returncode=completed.returncode,
                    stdout=completed.stdout, stderr=completed.stderr, partial_streams=False,
                    points=_unavailable_points(request, "XFOIL exited without creating a polar file."),
                    parsed=False, decoding_status="unavailable",
                    prelaunch_executable=prelaunch_executable,
                    polar_read="unavailable",
                )
                diagnostics = _diagnostic_tail(stdout_text, stderr_text)
                raise PolarProviderExecutionError(
                    f"XFOIL did not create {_POLAR_FILENAME}.{diagnostics}"
                )
            try:
                polar_text = polar_bytes.decode("utf-8")
            except UnicodeDecodeError as error:
                self._persist_capture(
                    capture_dir, request, airfoil_bytes, script_bytes, working_directory,
                    process_status="completed", returncode=completed.returncode,
                    stdout=completed.stdout, stderr=completed.stderr, partial_streams=False,
                    points=_unavailable_points(request, "Polar bytes could not be decoded as UTF-8."),
                    parsed=False, decoding_status="failed", polar_bytes=polar_bytes,
                    polar_read="present",
                    prelaunch_executable=prelaunch_executable,
                )
                raise PolarProviderExecutionError(
                    "XFOIL polar bytes could not be decoded as UTF-8."
                ) from error
            try:
                rows, parse_warnings = _parse_polar(polar_text)
            except OSError as error:
                self._persist_capture(
                    capture_dir, request, airfoil_bytes, script_bytes, working_directory,
                    process_status="completed", returncode=completed.returncode,
                    stdout=completed.stdout, stderr=completed.stderr, partial_streams=False,
                    points=_unavailable_points(request, "The polar file could not be read."),
                    parsed=False, decoding_status="decoded", polar_bytes=polar_bytes,
                    polar_read="present",
                    prelaunch_executable=prelaunch_executable,
                )
                raise PolarProviderExecutionError(
                    "XFOIL polar output could not be read."
                ) from error
            except PolarProviderExecutionError as error:
                self._persist_capture(
                    capture_dir, request, airfoil_bytes, script_bytes, working_directory,
                    process_status="completed", returncode=completed.returncode,
                    stdout=completed.stdout, stderr=completed.stderr, partial_streams=False,
                    points=_unavailable_points(request, f"Polar output could not be parsed: {error}"),
                    parsed=False, decoding_status="decoded", polar_bytes=polar_bytes,
                    polar_read="present",
                    prelaunch_executable=prelaunch_executable,
                )
                raise

            points, reconcile_warnings = _reconcile_rows(request, rows)
            receipt = self._persist_capture(
                capture_dir, request, airfoil_bytes, script_bytes, working_directory,
                process_status="completed", returncode=completed.returncode,
                stdout=completed.stdout, stderr=completed.stderr, partial_streams=False,
                points=_ledger_from_points(points),
                parsed=True, decoding_status="decoded", polar_bytes=polar_bytes,
                polar_read="present",
                prelaunch_executable=prelaunch_executable,
            )
            if capture_dir is not None and not receipt["identity_matched"]:
                raise PolarProviderExecutionError(
                    "Executable identity was missing or changed; captured output is not evidence-ready."
                )
            if capture_dir is not None:
                capture_evidence_ready = bool(receipt["evidence_ready"])
                capture_request_sha256 = receipt["request_sha256"]
        warnings = (*parse_warnings, *reconcile_warnings)
        metadata: dict[str, Any] = {
            "adapter": "subprocess",
            "executable": self.executable,
            "polar_row_count": len(rows),
            "repanel": options["repanel"],
            "returncode": completed.returncode,
        }
        if capture_evidence_ready is not None:
            metadata["capture_evidence_ready"] = capture_evidence_ready
        if capture_request_sha256 is not None:
            metadata["capture_request_sha256"] = capture_request_sha256
        if stderr_text.strip():
            metadata["stderr_tail"] = stderr_text.strip()[-2000:]
        return PolarGenerationResult(
            request=request,
            provider=self.identity,
            points=points,
            elapsed_s=elapsed_s,
            warnings=warnings,
            metadata=metadata,
        )

    def _persist_capture(
        self,
        capture_dir: str | os.PathLike[str] | None,
        request: PolarGenerationRequest,
        airfoil_bytes: bytes,
        script_bytes: bytes,
        working_directory: Path,
        *,
        process_status: str,
        returncode: int | None,
        stdout: str | bytes | None,
        stderr: str | bytes | None,
        partial_streams: bool,
        points: list[dict[str, Any]],
        parsed: bool,
        decoding_status: str,
        prelaunch_executable: dict[str, Any] | None,
        polar_bytes: bytes | None = None,
        polar_read: str = "not_attempted",
        polar_read_error: str | None = None,
    ) -> dict[str, Any]:
        if capture_dir is None:
            return {"evidence_ready": True, "identity_matched": True, "request_sha256": None}
        if polar_read == "not_attempted":
            polar_read, polar_bytes, polar_read_error = _read_polar_file(
                working_directory / _POLAR_FILENAME
            )
        elif polar_read in {"read_failed", "unavailable"}:
            polar_bytes = None
        try:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=False)
            _write_optional_bytes(directory / "script.txt", script_bytes)
            _write_optional_bytes(directory / "airfoil_input.dat", airfoil_bytes)
            stdout_bytes = _as_bytes(stdout)
            stderr_bytes = _as_bytes(stderr)
            if stdout_bytes is not None:
                _write_optional_bytes(directory / "stdout.bin", stdout_bytes)
            if stderr_bytes is not None:
                _write_optional_bytes(directory / "stderr.bin", stderr_bytes)
            if polar_read == "present" and polar_bytes is not None:
                _write_optional_bytes(directory / "polar.bin", polar_bytes)
            postlaunch_executable = _executable_identity(self.executable)
            identity_matched = bool(
                prelaunch_executable
                and prelaunch_executable.get("sha256")
                and prelaunch_executable.get("sha256") == postlaunch_executable.get("sha256")
            )
            request_preimage = _request_preimage(request, self.identity)
            request_sha256 = hashlib.sha256(request_preimage).hexdigest()
            _write_optional_bytes(directory / "request_preimage.json", request_preimage)
            points_usable = parsed and bool(points) and all(
                point["status"] in {"converged", "low_confidence"} for point in points
            )
            evidence_ready = bool(identity_matched and points_usable and decoding_status == "decoded")
            document = {
                "schema_version": 1,
                "artifact_class": "xfoil_subprocess_capture",
                "request_cache_key": request_sha256,
                "request_preimage_sha256": request_sha256,
                "coordinate_sha256": airfoil_coordinate_sha256(request.airfoil),
                "script_sha256": hashlib.sha256(script_bytes).hexdigest(),
                "airfoil_input_sha256": hashlib.sha256(airfoil_bytes).hexdigest(),
                "declared_build_policy": dict(_DECLARED_XFOIL_BUILD_POLICY),
                "executable_identity": {
                    "prelaunch": prelaunch_executable,
                    "postlaunch": postlaunch_executable,
                    "matched": identity_matched,
                    "limits": (
                        "SHA-256 of the executable file immediately before and after this "
                        "subprocess call. This does not prove the process image, the declared "
                        "source archive, or the compiler flags."
                    ),
                },
                "provider_identity": self.identity.as_mapping(),
                "adapter_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "pyfoldable_version": _package_version(),
                "process_status": process_status,
                "returncode": returncode,
                "stdout": _byte_receipt(stdout_bytes, partial=partial_streams),
                "stderr": _byte_receipt(stderr_bytes, partial=partial_streams),
                "stream_text_is_not_raw_bytes": True,
                "polar_file": _polar_file_receipt(polar_read, polar_bytes),
                "polar_read_status": polar_read,
                "polar_read_error": polar_read_error,
                "polar_decoding_status": decoding_status,
                "polar_parsed": parsed,
                "points": points,
                "solver_output_usable": points_usable,
                "evidence_ready": evidence_ready,
                "capture_receipt_written": True,
            }
            (directory / "capture.json").write_text(
                json.dumps(document, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as error:
            raise PolarProviderExecutionError(
                "XFOIL capture could not be persisted; the run is not evidence-complete."
            ) from error
        return {
            "evidence_ready": evidence_ready,
            "identity_matched": identity_matched,
            "request_sha256": request_sha256,
        }


def _resolve_executable(executable: str | os.PathLike[str]) -> str:
    raw = os.fspath(executable)
    if not raw:
        raise ValueError("executable must not be empty.")
    expanded = os.path.expanduser(raw)
    has_directory = bool(os.path.dirname(expanded))
    resolved = str(Path(expanded).resolve()) if has_directory else shutil.which(expanded)
    if resolved is None or not Path(resolved).is_file() or not os.access(resolved, os.X_OK):
        raise PolarProviderUnavailableError(f"XFOIL executable was not found: {raw}.")
    return resolved


def _discover_backend_version(executable: str, *, timeout_s: float) -> str:
    try:
        completed = subprocess.run(
            [executable],
            input="QUIT\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _executable_fingerprint(executable)
    output = f"{completed.stdout}\n{completed.stderr}"
    match = _VERSION_PATTERN.search(output)
    return match.group(1) if match else _executable_fingerprint(executable)


def _executable_fingerprint(executable: str) -> str:
    digest = hashlib.sha256()
    try:
        with Path(executable).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise PolarProviderUnavailableError(
            f"XFOIL executable could not be fingerprinted: {executable}."
        ) from error
    return f"sha256:{digest.hexdigest()}"


def _validated_options(options: Mapping[str, Any]) -> dict[str, bool]:
    unknown = sorted(set(options) - _ALLOWED_OPTIONS)
    if unknown:
        raise PolarProviderCapabilityError(
            "Unsupported XFOIL provider options: " + ", ".join(unknown) + "."
        )
    repanel = options.get("repanel", True)
    if not isinstance(repanel, bool):
        raise PolarProviderCapabilityError("XFOIL option 'repanel' must be bool.")
    return {"repanel": repanel}


def _write_airfoil(path: Path, request: PolarGenerationRequest) -> None:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.airfoil.id).strip("_")
    label = f"_PyFoldable_{safe_id or 'airfoil'}"
    lines = [label]
    lines.extend(f"{x:.17g} {y:.17g}" for x, y in request.airfoil.coordinates)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_command_script(
    request: PolarGenerationRequest,
    options: Mapping[str, bool],
) -> str:
    commands = [
        "PLOP",
        "G F",
        "",
        f"LOAD {_AIRFOIL_FILENAME}",
    ]
    if options["repanel"]:
        commands.append("PANE")
    commands.extend(
        [
            "OPER",
            "TYPE 1",
            f"VISC {_format_real(request.reynolds)}",
            f"MACH {_format_real(request.mach)}",
            "VPAR",
            f"N {_format_real(request.n_crit)}",
            "XTR "
            f"{_format_real(request.xtr_upper)} {_format_real(request.xtr_lower)}",
            "",
        ]
    )
    if request.max_iterations is not None:
        commands.append(f"ITER {request.max_iterations}")
    # Accumulate in memory and write once at the end. XFOIL 6.99's direct
    # PACC-to-file path appends every converged point after positioning the
    # sequential file at EOF. Modern gfortran rejects the subsequent WRITE
    # unless XFOIL first issues BACKSPACE/REWIND, so that legacy path can abort
    # an otherwise successful solve. Deferred PWRT uses a fresh whole-polar
    # write and works across both legacy and current runtimes.
    commands.extend(["PACC", "", ""])
    commands.extend(
        f"ALFA {_format_real(math.degrees(alpha))}" for alpha in request.alpha_rad
    )
    commands.extend(["PACC", "PWRT 1", _POLAR_FILENAME, "", "QUIT", ""])
    return "\n".join(commands)


def _parse_polar(text: str) -> tuple[tuple[_PolarRow, ...], tuple[str, ...]]:
    lines = text.splitlines()
    header_index: int | None = None
    indices: dict[str, int] = {}
    for index, line in enumerate(lines):
        tokens = [token.casefold() for token in line.split()]
        if all(name in tokens for name in ("alpha", "cl", "cd", "cm")):
            header_index = index
            indices = {name: tokens.index(name) for name in ("alpha", "cl", "cd", "cm")}
            break
    if header_index is None:
        raise PolarProviderExecutionError("XFOIL polar output has no recognized header.")

    rows: list[_PolarRow] = []
    warnings: list[str] = []
    maximum_index = max(indices.values())
    for line_number, line in enumerate(lines[header_index + 1 :], start=header_index + 2):
        stripped = line.strip()
        if not stripped or set(stripped) <= {"-", "="}:
            continue
        tokens = stripped.split()
        if len(tokens) <= maximum_index:
            if _looks_numeric(tokens):
                warnings.append(f"Ignored incomplete XFOIL polar row at line {line_number}.")
            continue
        try:
            values = {
                name: _parse_float(tokens[position])
                for name, position in indices.items()
            }
            row = _PolarRow(
                alpha_deg=values["alpha"],
                cl=values["cl"],
                cd=values["cd"],
                cm=values["cm"],
            )
            if not all(math.isfinite(value) for value in row.__dict__.values()):
                raise ValueError
            if row.cd < 0.0:
                raise ValueError
        except (TypeError, ValueError):
            if _looks_numeric(tokens):
                warnings.append(f"Ignored invalid XFOIL polar row at line {line_number}.")
            continue
        rows.append(row)
    return tuple(rows), tuple(warnings)


def _parse_float(value: str) -> float:
    return float(value.replace("D", "E").replace("d", "e"))


def _format_real(value: float) -> str:
    return format(value, ".12g")


def _looks_numeric(tokens: list[str]) -> bool:
    if not tokens:
        return False
    try:
        _parse_float(tokens[0])
    except ValueError:
        return False
    return True


def _reconcile_rows(
    request: PolarGenerationRequest,
    rows: tuple[_PolarRow, ...],
) -> tuple[tuple[PolarPointResult, ...], tuple[str, ...]]:
    unused = set(range(len(rows)))
    points: list[PolarPointResult] = []
    for alpha_rad in request.alpha_rad:
        alpha_deg = math.degrees(alpha_rad)
        candidates = sorted(
            (
                (abs(rows[index].alpha_deg - alpha_deg), index)
                for index in unused
            ),
            key=lambda candidate: candidate[0],
        )
        if not candidates or candidates[0][0] > _ALPHA_MATCH_TOLERANCE_DEG:
            points.append(
                PolarPointResult(
                    alpha_rad=alpha_rad,
                    status="not_converged",
                    message="XFOIL did not write a polar row for this angle.",
                )
            )
            continue
        _, index = candidates[0]
        unused.remove(index)
        row = rows[index]
        points.append(
            PolarPointResult(
                alpha_rad=alpha_rad,
                status="converged",
                cl=row.cl,
                cd=row.cd,
                cm=row.cm,
            )
        )

    warnings: list[str] = []
    missing_count = sum(not point.usable for point in points)
    if missing_count:
        warnings.append(f"XFOIL did not converge at {missing_count} requested angle(s).")
    if unused:
        warnings.append(f"Ignored {len(unused)} unmatched XFOIL polar row(s).")
    return tuple(points), tuple(warnings)


def _request_preimage(request: PolarGenerationRequest, identity: ProviderIdentity) -> bytes:
    document = json.dumps(
        _canonical_value(request.cache_payload(identity)),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    if hashlib.sha256(document).hexdigest() != request.cache_key(identity):
        raise PolarProviderExecutionError(
            "Retained request preimage does not match the cache digest."
        )
    return document


def _replacement_text(value: str | bytes | None) -> str:
    """Diagnostic text only. Replacement characters are not original bytes."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.decode("utf-8", errors="replace")


def _package_version() -> str:
    # Deferred: importing the package while this provider module is loading is circular.
    import pyfoldable

    return pyfoldable.__version__


def _as_bytes(value: str | bytes | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8", errors="replace")


def _read_polar_file(path: Path) -> tuple[str, bytes | None, str | None]:
    """Read polar bytes once. Existence checks and reads share one error boundary."""
    try:
        if not path.is_file():
            return "unavailable", None, None
        return "present", path.read_bytes(), None
    except FileNotFoundError:
        return "unavailable", None, None
    except OSError as error:
        try:
            os.chmod(path.parent, 0o700)
        except OSError:
            pass
        return "read_failed", None, f"{type(error).__name__}: {error}"


def _polar_file_receipt(polar_read: str, payload: bytes | None) -> dict[str, Any]:
    if polar_read == "read_failed":
        return {"status": "read_failed", "sha256": None, "byte_count": None}
    if polar_read != "present" or payload is None:
        return {"status": "unavailable", "sha256": None, "byte_count": None}
    return _byte_receipt(payload, partial=False)


def _byte_receipt(payload: bytes | None, *, partial: bool) -> dict[str, Any]:
    if payload is None:
        return {"status": "unavailable", "sha256": None, "byte_count": None}
    if len(payload) == 0:
        status = "empty"
    elif partial:
        status = "partial"
    else:
        status = "present"
    return {
        "status": status,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
    }


def _write_optional_bytes(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)


def _executable_identity(executable: str) -> dict[str, Any]:
    try:
        payload = Path(executable).read_bytes()
    except OSError as error:
        return {"path": executable, "sha256": None, "unavailable_reason": str(error)}
    return {
        "path": executable,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "unavailable_reason": None,
    }


def _unavailable_points(request: PolarGenerationRequest, reason: str) -> list[dict[str, Any]]:
    return [
        {
            "alpha_rad": alpha,
            "status": "unavailable",
            "cl": None,
            "cd": None,
            "cm": None,
            "message": reason,
        }
        for alpha in request.alpha_rad
    ]


def _ledger_from_points(points: tuple[PolarPointResult, ...]) -> list[dict[str, Any]]:
    return [
        {
            "alpha_rad": point.alpha_rad,
            "status": point.status,
            "cl": point.cl,
            "cd": point.cd,
            "cm": point.cm,
            "message": point.message,
        }
        for point in points
    ]


def _diagnostic_tail(stdout: str, stderr: str) -> str:
    combined = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
    if not combined:
        return ""
    return " Output tail: " + combined[-2000:]
