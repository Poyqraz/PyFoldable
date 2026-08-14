"""Subprocess adapter for XFOIL polar generation."""

from __future__ import annotations

import hashlib
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


_ADAPTER_VERSION = "1"
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

    def generate(self, request: PolarGenerationRequest) -> PolarGenerationResult:
        """Run one isolated XFOIL session and reconcile its saved polar rows."""
        request.validate_capabilities(self.capabilities)
        options = _validated_options(request.options)
        started = time.perf_counter()

        with tempfile.TemporaryDirectory(prefix="pyfoldable-xfoil-") as temporary:
            working_directory = Path(temporary)
            _write_airfoil(working_directory / _AIRFOIL_FILENAME, request)
            command_script = _build_command_script(request, options)
            try:
                completed = subprocess.run(
                    [self.executable],
                    input=command_script,
                    cwd=working_directory,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=request.timeout_s,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise PolarProviderTimeoutError(
                    f"XFOIL exceeded the {request.timeout_s:g} s request timeout."
                ) from error
            except OSError as error:
                raise PolarProviderUnavailableError(
                    f"XFOIL executable could not be started: {self.executable}."
                ) from error

            elapsed_s = time.perf_counter() - started
            if completed.returncode != 0:
                diagnostics = _diagnostic_tail(completed.stdout, completed.stderr)
                raise PolarProviderExecutionError(
                    f"XFOIL exited with status {completed.returncode}.{diagnostics}"
                )

            polar_path = working_directory / _POLAR_FILENAME
            if not polar_path.is_file():
                diagnostics = _diagnostic_tail(completed.stdout, completed.stderr)
                raise PolarProviderExecutionError(
                    f"XFOIL did not create {_POLAR_FILENAME}.{diagnostics}"
                )
            try:
                rows, parse_warnings = _parse_polar(polar_path.read_text(encoding="utf-8"))
            except OSError as error:
                raise PolarProviderExecutionError(
                    "XFOIL polar output could not be read."
                ) from error

        points, reconcile_warnings = _reconcile_rows(request, rows)
        warnings = (*parse_warnings, *reconcile_warnings)
        metadata: dict[str, Any] = {
            "adapter": "subprocess",
            "executable": self.executable,
            "polar_row_count": len(rows),
            "repanel": options["repanel"],
            "returncode": completed.returncode,
        }
        if completed.stderr.strip():
            metadata["stderr_tail"] = completed.stderr.strip()[-2000:]
        return PolarGenerationResult(
            request=request,
            provider=self.identity,
            points=points,
            elapsed_s=elapsed_s,
            warnings=warnings,
            metadata=metadata,
        )


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
    commands.extend(["PACC", _POLAR_FILENAME, ""])
    commands.extend(
        f"ALFA {_format_real(math.degrees(alpha))}" for alpha in request.alpha_rad
    )
    commands.extend(["PACC", "", "QUIT", ""])
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


def _diagnostic_tail(stdout: str, stderr: str) -> str:
    combined = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
    if not combined:
        return ""
    return " Output tail: " + combined[-2000:]
