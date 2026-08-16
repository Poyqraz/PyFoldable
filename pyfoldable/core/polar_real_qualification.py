"""Review-gated capture bundles for real polar-provider qualification."""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .polar_acceptance import (
    PolarAcceptanceCriteria,
    PolarBenchmarkEntry,
    PolarBenchmarkReport,
    compare_polar_results,
)
from .providers import (
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarProvider,
    ProviderIdentity,
    generate_polar,
)


POLAR_REAL_QUALIFICATION_SCHEMA_VERSION = 1
POLAR_REAL_QUALIFICATION_COMPARISON_SCHEMA_VERSION = 1
_SAFE_FILE_COMPONENT = re.compile(r"[^a-z0-9._-]+")
_SOURCE_REVISION = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", re.IGNORECASE)


@dataclass(frozen=True)
class PolarRealQualificationCapture:
    """Immutable, unreviewed evidence captured from exact backend identities."""

    case_name: str
    source_revision: str
    captured_at_utc: str
    expected_providers: tuple[ProviderIdentity, ...]
    reference_provider: ProviderIdentity
    results: tuple[PolarGenerationResult, ...]
    wall_elapsed_s: tuple[float, ...]
    benchmark: PolarBenchmarkReport
    environment: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        frozen_environment = _validate_capture_header(
            self.case_name,
            self.source_revision,
            self.captured_at_utc,
            self.environment,
        )
        if not self.expected_providers:
            raise ValueError("expected_providers must not be empty.")
        if not all(
            isinstance(identity, ProviderIdentity)
            for identity in self.expected_providers
        ):
            raise TypeError("expected_providers must contain ProviderIdentity values.")
        if len(set(self.expected_providers)) != len(self.expected_providers):
            raise ValueError("expected_providers must be unique.")
        if self.reference_provider not in self.expected_providers:
            raise ValueError("reference_provider must be one of expected_providers.")
        if len(self.results) != len(self.expected_providers):
            raise ValueError("results must contain one result per expected provider.")
        if not all(isinstance(result, PolarGenerationResult) for result in self.results):
            raise TypeError("results must contain PolarGenerationResult values.")
        actual_providers = tuple(result.provider for result in self.results)
        if actual_providers != self.expected_providers:
            raise ValueError("result providers must exactly match expected_providers order.")
        if len(self.wall_elapsed_s) != len(self.results):
            raise ValueError("wall_elapsed_s must contain one value per result.")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or value < 0.0
            for value in self.wall_elapsed_s
        ):
            raise ValueError("wall_elapsed_s values must be non-negative and finite.")
        request = self.results[0].request
        if any(result.request != request for result in self.results[1:]):
            raise ValueError("all captured results must use the same request.")
        if not isinstance(self.benchmark, PolarBenchmarkReport):
            raise TypeError("benchmark must be a PolarBenchmarkReport.")
        expected_entries = tuple(
            (self.case_name, identity) for identity in self.expected_providers
        )
        actual_entries = tuple(
            (entry.fixture_name, entry.provider) for entry in self.benchmark.entries
        )
        if actual_entries != expected_entries:
            raise ValueError("benchmark entries must match the captured provider order.")
        if any(
            entry.acceptance is not None
            and entry.acceptance.reference_provider != self.reference_provider
            for entry in self.benchmark.entries
        ):
            raise ValueError("benchmark entries must compare against reference_provider.")
        object.__setattr__(self, "environment", frozen_environment)

    @property
    def request(self) -> PolarGenerationRequest:
        return self.results[0].request


def capture_real_polar_qualification(
    providers: Sequence[PolarProvider],
    request: PolarGenerationRequest,
    *,
    expected_providers: Sequence[ProviderIdentity],
    reference_provider: ProviderIdentity,
    case_name: str,
    source_revision: str,
    captured_at_utc: str,
    criteria: PolarAcceptanceCriteria | None = None,
    environment: Mapping[str, Any] | None = None,
) -> PolarRealQualificationCapture:
    """Run exact provider versions once and build an unreviewed comparison capture."""
    if not providers:
        raise ValueError("providers must not be empty.")
    if not isinstance(request, PolarGenerationRequest):
        raise TypeError("request must be a PolarGenerationRequest.")
    _validate_capture_header(
        case_name,
        source_revision,
        captured_at_utc,
        environment or {},
    )
    expected = tuple(expected_providers)
    actual = tuple(provider.identity for provider in providers)
    if actual != expected:
        raise ValueError(
            "Installed provider identities do not match the pinned qualification "
            f"identities; expected={expected!r}, actual={actual!r}."
        )
    if len(set(actual)) != len(actual):
        raise ValueError("providers must have unique identities.")
    if reference_provider not in actual:
        raise ValueError("reference_provider must identify one captured provider.")
    policy = criteria or PolarAcceptanceCriteria()
    if not isinstance(policy, PolarAcceptanceCriteria):
        raise TypeError("criteria must be a PolarAcceptanceCriteria or None.")

    results: list[PolarGenerationResult] = []
    wall_elapsed: list[float] = []
    for provider in providers:
        started = time.perf_counter()
        result = generate_polar(provider, request)
        wall_elapsed.append(time.perf_counter() - started)
        results.append(result)

    reference = next(
        result for result in results if result.provider == reference_provider
    )
    entries: list[PolarBenchmarkEntry] = []
    for result, elapsed in zip(results, wall_elapsed):
        try:
            acceptance = compare_polar_results(reference, result, criteria=policy)
        except Exception as error:
            entries.append(
                PolarBenchmarkEntry(
                    fixture_name=case_name,
                    provider=result.provider,
                    wall_elapsed_s=elapsed,
                    provider_elapsed_s=None,
                    error_type=f"comparison:{type(error).__name__}",
                    error_message=_safe_error_message(error),
                )
            )
        else:
            entries.append(
                PolarBenchmarkEntry(
                    fixture_name=case_name,
                    provider=result.provider,
                    wall_elapsed_s=elapsed,
                    provider_elapsed_s=result.elapsed_s,
                    acceptance=acceptance,
                )
            )
    return PolarRealQualificationCapture(
        case_name=case_name,
        source_revision=source_revision,
        captured_at_utc=captured_at_utc,
        expected_providers=expected,
        reference_provider=reference_provider,
        results=tuple(results),
        wall_elapsed_s=tuple(wall_elapsed),
        benchmark=PolarBenchmarkReport(tuple(entries), policy),
        environment=environment or {},
    )


def write_polar_real_qualification_bundle(
    capture: PolarRealQualificationCapture,
    output_directory: str | Path,
) -> Path:
    """Atomically write raw results, benchmark, and a review-gated manifest."""
    if not isinstance(capture, PolarRealQualificationCapture):
        raise TypeError("capture must be a PolarRealQualificationCapture.")
    destination = Path(output_directory)
    if destination.exists():
        raise FileExistsError(
            f"Qualification output already exists and will not be overwritten: {destination}."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.staging-", dir=destination.parent
        )
    )
    try:
        result_directory = staging / "results"
        result_directory.mkdir()
        evidence_files: list[dict[str, object]] = []
        for index, result in enumerate(capture.results):
            relative = Path("results") / (
                f"{index:02d}-{_safe_component(result.provider.name)}.json"
            )
            evidence_files.append(
                _write_evidence_document(
                    staging / relative,
                    relative,
                    _result_document(capture.case_name, result),
                )
            )
        benchmark_relative = Path("benchmark.json")
        evidence_files.append(
            _write_evidence_document(
                staging / benchmark_relative,
                benchmark_relative,
                capture.benchmark.as_mapping(),
            )
        )
        request_document = _request_fingerprint_document(capture.request)
        manifest = {
            "schema_version": POLAR_REAL_QUALIFICATION_SCHEMA_VERSION,
            "kind": "polar-real-backend-qualification",
            "review_state": "unreviewed",
            "promotion_allowed": False,
            "case_name": capture.case_name,
            "source_revision": capture.source_revision,
            "captured_at_utc": capture.captured_at_utc,
            "request_sha256": _document_sha256(request_document),
            "expected_providers": tuple(
                identity.as_mapping() for identity in capture.expected_providers
            ),
            "actual_providers": tuple(
                result.provider.as_mapping() for result in capture.results
            ),
            "reference_provider": capture.reference_provider.as_mapping(),
            "environment": _thaw_json(capture.environment),
            "criteria": capture.benchmark.criteria.as_mapping(),
            "benchmark_passed": capture.benchmark.passed,
            "files": tuple(evidence_files),
        }
        _write_json(staging / "manifest.json", manifest)
        staging.rename(destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def write_polar_real_qualification_failure_bundle(
    *,
    case_name: str,
    source_revision: str,
    captured_at_utc: str,
    expected_providers: Sequence[ProviderIdentity],
    reference_provider: ProviderIdentity,
    request: PolarGenerationRequest,
    environment: Mapping[str, Any],
    error: Exception,
    output_directory: str | Path,
) -> Path:
    """Atomically preserve an unreviewed provider-execution failure."""
    frozen_environment = _validate_capture_header(
        case_name, source_revision, captured_at_utc, environment
    )
    expected = tuple(expected_providers)
    if not expected or not all(
        isinstance(identity, ProviderIdentity) for identity in expected
    ):
        raise TypeError("expected_providers must contain ProviderIdentity values.")
    if len(set(expected)) != len(expected):
        raise ValueError("expected_providers must be unique.")
    if reference_provider not in expected:
        raise ValueError("reference_provider must be one of expected_providers.")
    if not isinstance(request, PolarGenerationRequest):
        raise TypeError("request must be a PolarGenerationRequest.")
    if not isinstance(error, Exception):
        raise TypeError("error must be an Exception.")

    destination = Path(output_directory)
    if destination.exists():
        raise FileExistsError(
            f"Qualification output already exists and will not be overwritten: {destination}."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.staging-", dir=destination.parent
        )
    )
    try:
        failure_relative = Path("failure.json")
        failure_file = _write_evidence_document(
            staging / failure_relative,
            failure_relative,
            {
                "schema_version": POLAR_REAL_QUALIFICATION_SCHEMA_VERSION,
                "kind": "polar-provider-capture-failure",
                "case_name": case_name,
                "request": _request_document(request),
                "expected_providers": tuple(
                    identity.as_mapping() for identity in expected
                ),
                "error_type": type(error).__name__,
                "error_message": _safe_error_message(error),
            },
        )
        manifest = {
            "schema_version": POLAR_REAL_QUALIFICATION_SCHEMA_VERSION,
            "kind": "polar-real-backend-qualification",
            "review_state": "unreviewed",
            "promotion_allowed": False,
            "capture_failed": True,
            "case_name": case_name,
            "source_revision": source_revision,
            "captured_at_utc": captured_at_utc,
            "request_sha256": _document_sha256(
                _request_fingerprint_document(request)
            ),
            "expected_providers": tuple(
                identity.as_mapping() for identity in expected
            ),
            "actual_providers": (),
            "reference_provider": reference_provider.as_mapping(),
            "environment": _thaw_json(frozen_environment),
            "benchmark_passed": False,
            "files": (failure_file,),
        }
        _write_json(staging / "manifest.json", manifest)
        staging.rename(destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def compare_polar_real_qualification_bundles(
    first_directory: str | Path,
    second_directory: str | Path,
) -> dict[str, object]:
    """Verify and compare two captures while excluding telemetry-only fields."""
    first_root, first_manifest, first_documents = _load_verified_bundle(
        first_directory
    )
    second_root, second_manifest, second_documents = _load_verified_bundle(
        second_directory
    )
    first_semantic = _semantic_bundle_document(first_manifest, first_documents)
    second_semantic = _semantic_bundle_document(second_manifest, second_documents)
    differences = _json_differences(first_semantic, second_semantic)
    return {
        "schema_version": POLAR_REAL_QUALIFICATION_COMPARISON_SCHEMA_VERSION,
        "kind": "polar-real-backend-qualification-comparison",
        "reproducible": not differences,
        "promotion_allowed": False,
        "first_bundle": {
            "path": str(first_root),
            "captured_at_utc": first_manifest["captured_at_utc"],
            "semantic_sha256": _document_sha256(first_semantic),
        },
        "second_bundle": {
            "path": str(second_root),
            "captured_at_utc": second_manifest["captured_at_utc"],
            "semantic_sha256": _document_sha256(second_semantic),
        },
        "ignored_telemetry_fields": (
            "manifest.captured_at_utc",
            "manifest.files",
            "results.*.elapsed_s",
            "benchmark.**.*elapsed_s",
        ),
        "differences": differences,
    }


def write_polar_real_qualification_comparison(
    first_directory: str | Path,
    second_directory: str | Path,
    output_file: str | Path,
) -> tuple[Path, dict[str, object]]:
    """Write a non-overwriting, review-only reproducibility comparison report."""
    destination = Path(output_file)
    if destination.exists():
        raise FileExistsError(
            f"Qualification comparison already exists and will not be overwritten: "
            f"{destination}."
        )
    report = compare_polar_real_qualification_bundles(
        first_directory, second_directory
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(_json_bytes(report))
    return destination, report


def _result_document(
    case_name: str, result: PolarGenerationResult
) -> dict[str, object]:
    return {
        "schema_version": POLAR_REAL_QUALIFICATION_SCHEMA_VERSION,
        "kind": "polar-provider-raw-result",
        "case_name": case_name,
        "request": _request_document(result.request),
        "provider": result.provider.as_mapping(),
        "points": tuple(
            {
                "alpha_rad": point.alpha_rad,
                "status": point.status,
                "cl": point.cl,
                "cd": point.cd,
                "cm": point.cm,
                "confidence": point.confidence,
                "iterations": point.iterations,
                "message": point.message,
            }
            for point in result.points
        ),
        "elapsed_s": result.elapsed_s,
        "warnings": result.warnings,
        "metadata": _thaw_json(result.metadata),
        "complete": result.complete,
        "cache_key": result.cache_key,
    }


def _load_verified_bundle(
    directory: str | Path,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    root = _resolve_bundle_root(Path(directory))
    manifest = _read_json_object(root / "manifest.json")
    if manifest.get("schema_version") != POLAR_REAL_QUALIFICATION_SCHEMA_VERSION:
        raise ValueError(f"Unsupported qualification schema in {root}.")
    if manifest.get("kind") != "polar-real-backend-qualification":
        raise ValueError(f"Unexpected qualification kind in {root}.")
    if manifest.get("capture_failed", False):
        raise ValueError(f"Failed qualification capture cannot be compared: {root}.")
    if manifest.get("benchmark_passed") is not True:
        raise ValueError(f"Qualification benchmark did not pass: {root}.")
    if manifest.get("review_state") != "unreviewed":
        raise ValueError(f"Qualification bundle is not unreviewed: {root}.")
    if manifest.get("promotion_allowed") is not False:
        raise ValueError(f"Qualification bundle unexpectedly allows promotion: {root}.")
    captured_at = manifest.get("captured_at_utc")
    if not isinstance(captured_at, str) or not captured_at.endswith("Z"):
        raise ValueError(f"Qualification capture time is invalid: {root}.")

    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"Qualification file manifest is empty: {root}.")
    documents: dict[str, Any] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"Qualification file entry is invalid: {root}.")
        relative = entry.get("path")
        expected_size = entry.get("size_bytes")
        expected_sha256 = entry.get("sha256")
        if not isinstance(relative, str):
            raise ValueError(f"Qualification file path is invalid: {root}.")
        relative_path = Path(relative)
        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
            or relative_path.as_posix() != relative
        ):
            raise ValueError(f"Unsafe qualification file path: {relative!r}.")
        if relative in documents:
            raise ValueError(f"Duplicate qualification file path: {relative!r}.")
        payload_path = root / relative_path
        if not payload_path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Qualification file escapes its bundle: {payload_path}.")
        try:
            payload = payload_path.read_bytes()
        except OSError as error:
            raise ValueError(f"Qualification file cannot be read: {payload_path}.") from error
        if expected_size != len(payload):
            raise ValueError(f"Qualification file size mismatch: {payload_path}.")
        if not isinstance(expected_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", expected_sha256
        ):
            raise ValueError(f"Qualification file hash is invalid: {payload_path}.")
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise ValueError(f"Qualification file hash mismatch: {payload_path}.")
        documents[relative] = _read_json_object(payload_path)

    if "benchmark.json" not in documents:
        raise ValueError(f"Qualification bundle has no benchmark.json: {root}.")
    result_paths = sorted(
        path for path in documents if path.startswith("results/")
    )
    expected_providers = manifest.get("expected_providers")
    if not isinstance(expected_providers, list) or len(result_paths) != len(
        expected_providers
    ):
        raise ValueError(f"Qualification result count does not match providers: {root}.")
    if set(documents) != {"benchmark.json", *result_paths}:
        raise ValueError(f"Qualification bundle contains unexpected evidence files: {root}.")
    return root, manifest, documents


def _resolve_bundle_root(directory: Path) -> Path:
    if not directory.is_dir():
        raise ValueError(f"Qualification bundle directory does not exist: {directory}.")
    direct = directory / "manifest.json"
    if direct.is_file():
        return directory
    matches = tuple(directory.rglob("manifest.json"))
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one qualification bundle below {directory}; "
            f"found {len(matches)}."
        )
    return matches[0].parent


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Qualification JSON cannot be read: {path}.") from error
    if not isinstance(document, dict):
        raise ValueError(f"Qualification JSON must contain an object: {path}.")
    return document


def _semantic_bundle_document(
    manifest: Mapping[str, Any], documents: Mapping[str, Any]
) -> dict[str, Any]:
    normalized_manifest = dict(manifest)
    normalized_manifest.pop("captured_at_utc", None)
    normalized_manifest.pop("files", None)
    normalized_documents: dict[str, Any] = {}
    for path, document in sorted(documents.items()):
        normalized = _thaw_json(document)
        if path == "benchmark.json":
            if not isinstance(normalized.get("entries"), list):
                raise ValueError("Qualification benchmark entries are invalid.")
            normalized = _without_elapsed_telemetry(normalized)
        elif path.startswith("results/"):
            normalized.pop("elapsed_s", None)
            request = normalized.get("request")
            if not isinstance(request, dict):
                raise ValueError("Qualification result request is invalid.")
            airfoil = request.get("airfoil")
            if not isinstance(airfoil, dict):
                raise ValueError("Qualification result airfoil is invalid.")
            airfoil.pop("source", None)
            airfoil.pop("metadata", None)
        normalized_documents[path] = normalized
    return {
        "manifest": normalized_manifest,
        "documents": normalized_documents,
    }


def _without_elapsed_telemetry(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_elapsed_telemetry(item)
            for key, item in value.items()
            if not key.endswith("elapsed_s")
        }
    if isinstance(value, list):
        return [_without_elapsed_telemetry(item) for item in value]
    return value


def _json_differences(first: Any, second: Any, path: str = "$") -> list[str]:
    if type(first) is not type(second):
        return [f"{path}: type {type(first).__name__} != {type(second).__name__}"]
    if isinstance(first, dict):
        differences: list[str] = []
        first_keys = set(first)
        second_keys = set(second)
        for key in sorted(first_keys - second_keys):
            differences.append(f"{path}.{key}: missing from second bundle")
        for key in sorted(second_keys - first_keys):
            differences.append(f"{path}.{key}: missing from first bundle")
        for key in sorted(first_keys & second_keys):
            differences.extend(
                _json_differences(first[key], second[key], f"{path}.{key}")
            )
        return differences
    if isinstance(first, list):
        differences = []
        if len(first) != len(second):
            differences.append(f"{path}: length {len(first)} != {len(second)}")
        for index, (left, right) in enumerate(zip(first, second)):
            differences.extend(_json_differences(left, right, f"{path}[{index}]"))
        return differences
    if first != second:
        return [f"{path}: {first!r} != {second!r}"]
    return []


def _request_document(request: PolarGenerationRequest) -> dict[str, object]:
    return {
        "airfoil": {
            "id": request.airfoil.id,
            "source": request.airfoil.source,
            "coordinates": request.airfoil.coordinates,
            "metadata": _thaw_json(request.airfoil.metadata),
        },
        "alpha_rad": request.alpha_rad,
        "reynolds": request.reynolds,
        "mach": request.mach,
        "n_crit": request.n_crit,
        "xtr_upper": request.xtr_upper,
        "xtr_lower": request.xtr_lower,
        "max_iterations": request.max_iterations,
        "timeout_s": request.timeout_s,
        "scenario_id": request.scenario_id,
        "options": _thaw_json(request.options),
    }


def _request_fingerprint_document(
    request: PolarGenerationRequest,
) -> dict[str, object]:
    """Return only solver inputs, excluding environment-specific source metadata."""
    document = _request_document(request)
    airfoil = dict(document["airfoil"])
    airfoil.pop("source")
    airfoil.pop("metadata")
    document["airfoil"] = airfoil
    return document


def _safe_component(value: str) -> str:
    component = _SAFE_FILE_COMPONENT.sub("-", value.casefold()).strip("-.")
    if not component:
        raise ValueError("Provider name cannot form a safe evidence filename.")
    return component


def _safe_error_message(error: Exception) -> str:
    try:
        message = str(error)
    except Exception:
        message = "error message unavailable"
    return (" ".join(message.split()) or "error message unavailable")[:512]


def _validate_capture_header(
    case_name: str,
    source_revision: str,
    captured_at_utc: str,
    environment: Mapping[str, Any],
) -> Mapping[str, Any]:
    if not isinstance(case_name, str) or not case_name.strip():
        raise ValueError("case_name must be a non-empty string.")
    if not isinstance(source_revision, str) or not _SOURCE_REVISION.fullmatch(
        source_revision
    ):
        raise ValueError("source_revision must be a 40- or 64-character hex digest.")
    if not isinstance(captured_at_utc, str) or not captured_at_utc.endswith("Z"):
        raise ValueError("captured_at_utc must be an ISO-8601 UTC string ending in Z.")
    try:
        captured_at = datetime.fromisoformat(
            captured_at_utc.removesuffix("Z") + "+00:00"
        )
    except ValueError as error:
        raise ValueError(
            "captured_at_utc must be an ISO-8601 UTC string ending in Z."
        ) from error
    if captured_at.utcoffset() != timedelta(0):
        raise ValueError("captured_at_utc must represent UTC.")
    frozen_environment = _freeze_json(environment, "environment")
    if not isinstance(frozen_environment, Mapping):
        raise TypeError("environment must be a JSON-compatible mapping.")
    return frozen_environment


def _write_evidence_document(
    path: Path,
    relative_path: Path,
    document: Mapping[str, Any],
) -> dict[str, object]:
    payload = _json_bytes(document)
    path.write_bytes(payload)
    return {
        "path": relative_path.as_posix(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def _write_json(path: Path, document: Mapping[str, Any]) -> None:
    path.write_bytes(_json_bytes(document))


def _json_bytes(document: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            document,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _document_sha256(document: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _freeze_json(value: Any, name: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{name} must not contain non-finite floats.")
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError(f"{name} mapping keys must be strings.")
        return MappingProxyType(
            {key: _freeze_json(item, name) for key, item in value.items()}
        )
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_json(item, name) for item in value)
    raise TypeError(f"{name} contains unsupported type {type(value).__name__}.")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_thaw_json(item) for item in value]
    return value
