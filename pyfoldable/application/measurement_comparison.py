"""Strict source-bound application service for PY-06 comparisons."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from pyfoldable import __version__
from pyfoldable.core.experiment_contract import (
    EXPERIMENT_CONTRACT_SCHEMA_VERSION,
    REQUIRED_UNITS,
    TEST_STAND_MANIFEST_SCHEMA_VERSION,
    CalibrationIdentity,
    ExperimentBundleDecision,
    ExperimentPolicy,
    ExperimentRunDecision,
    ExperimentSummary,
    TestStandManifest,
    UncertaintyMetric,
)
from pyfoldable.core.measurement_comparison import (
    ComparisonPolicy,
    MatchedExperimentComparison,
    MeasurementComparisonError,
    RunComparisonContext,
    build_matched_experiment_comparison,
)


SERVICE_ID = "pyfoldable.application.measurement_comparison"
SERVICE_VERSION = 1
MEASUREMENT_COMPARISON_REPORT_SCHEMA_VERSION = 1
MAX_COMPARISON_JSON_BYTES = 5 * 1024 * 1024
_MAX_COLLECTION_ITEMS = 64
_MAX_FAILURES = 256
_MAX_JSON_DEPTH = 100
_MAX_JSON_NODES = 100_000
_MAX_STRING_LENGTH = 4096
_ROOT_FIELDS = {
    "schema_version",
    "artifact_class",
    "physical_qualification",
    "manifest",
    "decision",
    "fixed_context",
    "foldable_context",
    "policy",
    "policy_sources",
}
_CALIBRATION_FIELDS = {
    "sensor_id",
    "quantity",
    "unit",
    "certificate_id",
    "certificate_sha256",
    "valid_from",
    "valid_until",
    "standard_uncertainty",
    "qualification",
}
_POLICY_FIELDS = {
    "maximum_diameter_delta_m",
    "maximum_rpm_relative_delta",
    "maximum_forward_speed_delta_m_s",
    "maximum_temperature_delta_k",
    "maximum_pressure_delta_pa",
    "thrust_uncertainty_correlation",
    "rotor_shaft_torque_uncertainty_correlation",
    "dc_electrical_input_power_uncertainty_correlation",
    "target_thrust_ratio",
}
_CONTEXT_FIELDS = {
    "run_id",
    "open_diameter_m",
    "forward_speed_m_s",
    "torque_channel",
    "electrical_power_channel",
    "source",
    "classification",
}
_METRIC_FIELDS = {
    "mean",
    "standard_uncertainty_type_a",
    "standard_uncertainty_calibration",
    "standard_uncertainty_zero_drift",
    "combined_standard_uncertainty",
    "expanded_uncertainty",
    "unit",
}
_METRIC_KEYS = set(REQUIRED_UNITS) | {"electrical_power"}


class MeasurementComparisonServiceError(ValueError):
    """A PY-06 service request cannot be evaluated without guessing."""


@dataclass(frozen=True)
class MeasurementComparisonRequest:
    manifest: TestStandManifest
    decision: ExperimentBundleDecision
    fixed_context: RunComparisonContext
    foldable_context: RunComparisonContext
    policy: ComparisonPolicy
    policy_sources: Mapping[str, str]
    input_sha256: str
    source_json_bytes: bytes = field(repr=False)


@dataclass(frozen=True)
class MeasurementComparisonReportArtifact:
    request_sha256: str
    input_sha256: str
    report_sha256: str | None
    report_json: str | None
    filename: str | None


def _sha(value: str | bytes) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


def _json(value: object) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise MeasurementComparisonServiceError(
            "Comparison request must contain finite JSON-safe data."
        ) from exc


def _exact_mapping(
    value: object, label: str, fields: set[str]
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise MeasurementComparisonServiceError(
            f"{label} fields must exactly match the versioned schema."
        )
    return value


def _bounded_string(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > _MAX_STRING_LENGTH
    ):
        raise MeasurementComparisonServiceError(
            f"{label} must be a bounded nonempty string."
        )
    return value


def _finite_number(value: object, label: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MeasurementComparisonServiceError(f"{label} must be a finite number.")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MeasurementComparisonServiceError(
            f"{label} must be a finite number."
        ) from exc
    if not math.isfinite(result):
        raise MeasurementComparisonServiceError(f"{label} must be a finite number.")
    return value


def _bounded_integer(value: object, label: str, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > maximum
    ):
        raise MeasurementComparisonServiceError(
            f"{label} must be a bounded nonnegative integer."
        )
    return value


def _bounded_list(value: object, label: str, maximum: int) -> list[Any]:
    if not isinstance(value, list) or not 1 <= len(value) <= maximum:
        raise MeasurementComparisonServiceError(
            f"{label} must be a nonempty bounded JSON array."
        )
    return value


def _validate_json_tree(value: object) -> None:
    stack: list[tuple[object, int]] = [(value, 0)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if depth > _MAX_JSON_DEPTH or nodes > _MAX_JSON_NODES:
            raise MeasurementComparisonServiceError(
                "Comparison JSON nesting or node count exceeds the bounded limit."
            )
        if isinstance(current, dict):
            for key, child in current.items():
                try:
                    key.encode("utf-8")
                except UnicodeEncodeError as exc:
                    raise MeasurementComparisonServiceError(
                        "Comparison JSON contains an invalid Unicode surrogate."
                    ) from exc
                if len(key) > _MAX_STRING_LENGTH:
                    raise MeasurementComparisonServiceError(
                        "Comparison JSON contains an oversized key."
                    )
                if key == "physical_qualification" and child is not False:
                    raise MeasurementComparisonServiceError(
                        "Comparison input cannot claim physical qualification."
                    )
                stack.append((child, depth + 1))
        elif isinstance(current, list):
            if len(current) > _MAX_JSON_NODES:
                raise MeasurementComparisonServiceError(
                    "Comparison JSON collection exceeds the bounded limit."
                )
            stack.extend((child, depth + 1) for child in current)
        elif isinstance(current, str):
            try:
                current.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise MeasurementComparisonServiceError(
                    "Comparison JSON contains an invalid Unicode surrogate."
                ) from exc
            if len(current) > _MAX_STRING_LENGTH:
                raise MeasurementComparisonServiceError(
                    "Comparison JSON contains an oversized string."
                )
        elif isinstance(current, float) and not math.isfinite(current):
            raise MeasurementComparisonServiceError(
                "Comparison JSON numbers must be finite."
            )


def _decode_json(payload: str | bytes) -> tuple[bytes, dict[str, Any]]:
    if not isinstance(payload, (str, bytes)):
        raise MeasurementComparisonServiceError(
            "Comparison JSON must be UTF-8 text or bytes."
        )
    try:
        raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    except UnicodeEncodeError as exc:
        raise MeasurementComparisonServiceError(
            "Comparison JSON must be valid UTF-8."
        ) from exc
    if not raw:
        raise MeasurementComparisonServiceError("Comparison JSON must not be empty.")
    if len(raw) > MAX_COMPARISON_JSON_BYTES:
        raise MeasurementComparisonServiceError(
            "Comparison JSON size exceeds the bounded input limit."
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MeasurementComparisonServiceError(
            "Comparison JSON must be valid UTF-8."
        ) from exc

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise MeasurementComparisonServiceError(
                    "Comparison JSON contains a duplicate key."
                )
            result[key] = value
        return result

    def reject_constant(_value: str) -> None:
        raise MeasurementComparisonServiceError(
            "Comparison JSON numbers must be finite."
        )

    def finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise MeasurementComparisonServiceError(
                "Comparison JSON numbers must be finite."
            )
        return parsed

    def bounded_int(value: str) -> int:
        if len(value.lstrip("-")) > 18:
            raise MeasurementComparisonServiceError(
                "Comparison JSON integer exceeds the bounded range."
            )
        return int(value)

    try:
        document = json.loads(
            text,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
            parse_float=finite_float,
            parse_int=bounded_int,
        )
    except MeasurementComparisonServiceError:
        raise
    except RecursionError as exc:
        raise MeasurementComparisonServiceError(
            "Comparison JSON nesting exceeds the decoder limit."
        ) from exc
    except (json.JSONDecodeError, TypeError, ValueError, OverflowError) as exc:
        raise MeasurementComparisonServiceError(
            "Comparison JSON is malformed."
        ) from exc
    _validate_json_tree(document)
    if not isinstance(document, dict):
        raise MeasurementComparisonServiceError(
            "Comparison JSON root must be an object."
        )
    return raw, document


def _parse_manifest(value: object) -> TestStandManifest:
    document = _exact_mapping(
        value,
        "manifest",
        {"schema_version", "id", "calibrations", "policy"},
    )
    if (
        type(document["schema_version"]) is not int
        or document["schema_version"] != TEST_STAND_MANIFEST_SCHEMA_VERSION
    ):
        raise MeasurementComparisonServiceError("manifest schema_version is invalid.")
    calibrations = tuple(
        CalibrationIdentity(**_exact_mapping(item, "calibration", _CALIBRATION_FIELDS))
        for item in _bounded_list(
            document["calibrations"], "manifest.calibrations", _MAX_COLLECTION_ITEMS
        )
    )
    policy_document = _exact_mapping(
        document["policy"],
        "manifest.policy",
        {"minimum_repeats", "maximum_zero_drift", "coverage_factor"},
    )
    drift = policy_document["maximum_zero_drift"]
    if not isinstance(drift, dict) or not set(drift) <= {"thrust", "torque"}:
        raise MeasurementComparisonServiceError(
            "manifest.policy.maximum_zero_drift fields are invalid."
        )
    for key, limit in drift.items():
        _finite_number(limit, f"manifest.policy.maximum_zero_drift.{key}")
    policy = ExperimentPolicy(
        minimum_repeats=policy_document["minimum_repeats"],
        maximum_zero_drift=MappingProxyType(dict(drift)),
        coverage_factor=policy_document["coverage_factor"],
    )
    return TestStandManifest(
        id=_bounded_string(document["id"], "manifest.id"),
        calibrations=calibrations,
        policy=policy,
    )


def _parse_metric(value: object, label: str) -> UncertaintyMetric:
    document = _exact_mapping(value, label, _METRIC_FIELDS)
    numbers = {
        key: _finite_number(document[key], f"{label}.{key}")
        for key in _METRIC_FIELDS - {"unit"}
    }
    return UncertaintyMetric(
        mean=numbers["mean"],
        standard_uncertainty_type_a=numbers["standard_uncertainty_type_a"],
        standard_uncertainty_calibration=numbers[
            "standard_uncertainty_calibration"
        ],
        standard_uncertainty_zero_drift=numbers[
            "standard_uncertainty_zero_drift"
        ],
        combined_standard_uncertainty=numbers["combined_standard_uncertainty"],
        expanded_uncertainty=numbers["expanded_uncertainty"],
        unit=_bounded_string(document["unit"], f"{label}.unit"),
    )


def _parse_summary(value: object) -> ExperimentSummary:
    document = _exact_mapping(
        value,
        "decision summary",
        {"run_id", "role", "repeat_count", "metrics"},
    )
    metrics_document = document["metrics"]
    if not isinstance(metrics_document, dict) or set(metrics_document) != _METRIC_KEYS:
        raise MeasurementComparisonServiceError(
            "decision summary metric fields must exactly match PR-10."
        )
    metrics = MappingProxyType(
        {
            key: _parse_metric(item, f"decision summary metric {key}")
            for key, item in metrics_document.items()
        }
    )
    return ExperimentSummary(
        run_id=_bounded_string(document["run_id"], "decision summary run_id"),
        role=_bounded_string(document["role"], "decision summary role"),
        repeat_count=_bounded_integer(
            document["repeat_count"], "decision summary repeat_count", 1_000_000
        ),
        metrics=metrics,
    )


def _parse_decision(value: object) -> ExperimentBundleDecision:
    document = _exact_mapping(
        value,
        "decision",
        {
            "schema_version",
            "stand_id",
            "state",
            "software_gate_passed",
            "physical_qualification",
            "test_stand_manifest_sha256",
            "missing_roles",
            "runs",
            "summaries",
        },
    )
    if (
        type(document["schema_version"]) is not int
        or document["schema_version"] != EXPERIMENT_CONTRACT_SCHEMA_VERSION
    ):
        raise MeasurementComparisonServiceError("decision schema_version is invalid.")
    summaries = tuple(
        _parse_summary(item)
        for item in _bounded_list(
            document["summaries"], "decision.summaries", _MAX_COLLECTION_ITEMS
        )
    )
    run_documents = _bounded_list(
        document["runs"], "decision.runs", _MAX_COLLECTION_ITEMS
    )
    runs: list[ExperimentRunDecision] = []
    run_fields = {
        "run_id",
        "passed",
        "failures",
        "raw_data_sha256",
        "design_id",
        "experiment_date",
        "summary_sha256",
    }
    for item in run_documents:
        run = _exact_mapping(item, "decision run", run_fields)
        failures_document = run["failures"]
        if not isinstance(failures_document, list) or len(failures_document) > _MAX_FAILURES:
            raise MeasurementComparisonServiceError(
                "decision run failures must be a bounded JSON array."
            )
        failures = tuple(
            _bounded_string(failure, "decision run failure")
            for failure in failures_document
        )
        decision = ExperimentRunDecision(
            run_id=_bounded_string(run["run_id"], "decision run_id"),
            failures=failures,
            raw_data_sha256=run["raw_data_sha256"],
            design_id=run["design_id"],
            experiment_date=run["experiment_date"],
            summary_sha256=run["summary_sha256"],
        )
        if not isinstance(run["passed"], bool) or run["passed"] is not decision.passed:
            raise MeasurementComparisonServiceError(
                "decision run derived passed state is inconsistent."
            )
        runs.append(decision)
    missing_document = document["missing_roles"]
    if not isinstance(missing_document, list) or len(missing_document) > 2:
        raise MeasurementComparisonServiceError(
            "decision missing_roles must be a bounded JSON array."
        )
    missing_roles = tuple(
        _bounded_string(role, "decision missing role") for role in missing_document
    )
    decision = ExperimentBundleDecision(
        stand_id=_bounded_string(document["stand_id"], "decision stand_id"),
        runs=tuple(runs),
        summaries=summaries,
        missing_roles=missing_roles,
        test_stand_manifest_sha256=document["test_stand_manifest_sha256"],
    )
    if (
        not isinstance(document["software_gate_passed"], bool)
        or document["software_gate_passed"] is not decision.software_gate_passed
        or document["state"] != decision.state
        or document["physical_qualification"] is not False
    ):
        raise MeasurementComparisonServiceError(
            "decision derived state is inconsistent."
        )
    return decision


def _parse_context(value: object, label: str) -> RunComparisonContext:
    document = _exact_mapping(value, label, _CONTEXT_FIELDS)
    return RunComparisonContext(**document)


def _parse_policy(value: object) -> ComparisonPolicy:
    document = _exact_mapping(value, "policy", _POLICY_FIELDS)
    return ComparisonPolicy(**document)


def _parse_policy_sources(value: object) -> Mapping[str, str]:
    document = _exact_mapping(value, "policy source", _POLICY_FIELDS)
    return MappingProxyType(
        {
            key: _bounded_string(source, f"policy source {key}")
            for key, source in document.items()
        }
    )


def load_measurement_comparison_json(
    payload: str | bytes,
) -> MeasurementComparisonRequest:
    """Load one exact bounded PY-06B request without trusting declared hashes."""
    raw, document = _decode_json(payload)
    document = _exact_mapping(document, "comparison request", _ROOT_FIELDS)
    if (
        type(document["schema_version"]) is not int
        or document["schema_version"] != MEASUREMENT_COMPARISON_REPORT_SCHEMA_VERSION
    ):
        raise MeasurementComparisonServiceError(
            "comparison request schema_version is invalid."
        )
    if document["artifact_class"] != "measurement_comparison_request":
        raise MeasurementComparisonServiceError(
            "comparison request artifact_class is invalid."
        )
    if document["physical_qualification"] is not False:
        raise MeasurementComparisonServiceError(
            "comparison request physical_qualification must be false."
        )
    try:
        return MeasurementComparisonRequest(
            manifest=_parse_manifest(document["manifest"]),
            decision=_parse_decision(document["decision"]),
            fixed_context=_parse_context(document["fixed_context"], "fixed_context"),
            foldable_context=_parse_context(
                document["foldable_context"], "foldable_context"
            ),
            policy=_parse_policy(document["policy"]),
            policy_sources=_parse_policy_sources(document["policy_sources"]),
            input_sha256=_sha(raw),
            source_json_bytes=bytes(raw),
        )
    except MeasurementComparisonServiceError:
        raise
    except (TypeError, ValueError, KeyError, OverflowError, ArithmeticError) as exc:
        raise MeasurementComparisonServiceError(
            f"Comparison JSON validation failed: {exc}"
        ) from exc


def _input_mapping(request: MeasurementComparisonRequest) -> dict[str, Any]:
    return {
        "schema_version": MEASUREMENT_COMPARISON_REPORT_SCHEMA_VERSION,
        "artifact_class": "measurement_comparison_request",
        "physical_qualification": False,
        "manifest": dict(request.manifest.as_mapping()),
        "decision": dict(request.decision.as_mapping()),
        "fixed_context": dict(request.fixed_context.as_mapping()),
        "foldable_context": dict(request.foldable_context.as_mapping()),
        "policy": dict(request.policy.as_mapping()),
        "policy_sources": dict(request.policy_sources),
    }


def _validated_request(
    request: MeasurementComparisonRequest,
) -> MeasurementComparisonRequest:
    if not isinstance(request, MeasurementComparisonRequest):
        raise MeasurementComparisonServiceError(
            "Expected a loaded measurement comparison request."
        )
    try:
        recovered = load_measurement_comparison_json(request.source_json_bytes)
    except MeasurementComparisonServiceError as exc:
        raise MeasurementComparisonServiceError(
            "Comparison request source identity is invalid."
        ) from exc
    try:
        identity_matches = (
            request.input_sha256 == recovered.input_sha256
            and _input_mapping(request) == _input_mapping(recovered)
        )
    except (AttributeError, TypeError, ValueError, KeyError, OverflowError) as exc:
        raise MeasurementComparisonServiceError(
            "Comparison request no longer matches its source identity."
        ) from exc
    if not identity_matches:
        raise MeasurementComparisonServiceError(
            "Comparison request no longer matches its source identity."
        )
    return recovered


def _implementation() -> Mapping[str, Any]:
    sources = {
        SERVICE_ID: Path(__file__),
        "pyfoldable.core.measurement_comparison": (
            Path(__file__).parents[1] / "core/measurement_comparison.py"
        ),
        "pyfoldable.core.experiment_contract": (
            Path(__file__).parents[1] / "core/experiment_contract.py"
        ),
    }
    try:
        hashes = {name: _sha(path.read_bytes()) for name, path in sources.items()}
    except OSError as exc:
        raise MeasurementComparisonServiceError(
            "Comparison implementation source identity is unavailable."
        ) from exc
    return {
        "source_files_sha256": hashes,
        "source_identity_scope": "disk_sources_at_request_time",
    }


def _prepare(
    request: MeasurementComparisonRequest,
) -> tuple[
    MeasurementComparisonRequest,
    MatchedExperimentComparison,
    Mapping[str, Any],
    str,
]:
    request = _validated_request(request)
    try:
        comparison = build_matched_experiment_comparison(
            request.manifest,
            request.decision,
            request.fixed_context,
            request.foldable_context,
            request.policy,
        )
    except (MeasurementComparisonError, TypeError, ValueError, ArithmeticError) as exc:
        raise MeasurementComparisonServiceError(
            f"Measurement comparison validation failed: {exc}"
        ) from exc
    document = {
        "service_id": SERVICE_ID,
        "service_version": SERVICE_VERSION,
        "pyfoldable_version": __version__,
        "implementation": dict(_implementation()),
        "input_sha256": request.input_sha256,
        "input": _input_mapping(request),
    }
    return request, comparison, document, _sha(_json(document))


def prepare_measurement_comparison_report(
    request: MeasurementComparisonRequest,
) -> MeasurementComparisonReportArtifact:
    """Validate every source and return the exact prepared request identity."""
    request, _comparison, _document, request_sha = _prepare(request)
    return MeasurementComparisonReportArtifact(
        request_sha256=request_sha,
        input_sha256=request.input_sha256,
        report_sha256=None,
        report_json=None,
        filename=None,
    )


def run_measurement_comparison_report(
    request: MeasurementComparisonRequest,
    *,
    expected_request_sha256: str | None = None,
) -> MeasurementComparisonReportArtifact:
    """Run PY-06A through the source-bound service and publish exact JSON bytes."""
    request, comparison, request_document, request_sha = _prepare(request)
    if expected_request_sha256 is not None and expected_request_sha256 != request_sha:
        raise MeasurementComparisonServiceError(
            "Prepared request identity is stale and no report was published."
        )
    result = comparison.as_mapping()
    document = {
        "schema_version": MEASUREMENT_COMPARISON_REPORT_SCHEMA_VERSION,
        "artifact_class": "measurement_comparison_report",
        "state": comparison.state,
        "qualification": "screening_only",
        "physical_qualification": False,
        "target_fitting_performed": False,
        "request_sha256": request_sha,
        "input_sha256": request.input_sha256,
        "request": request_document,
        "result": result,
    }
    payload = _json(document) + "\n"
    return MeasurementComparisonReportArtifact(
        request_sha256=request_sha,
        input_sha256=request.input_sha256,
        report_sha256=_sha(payload),
        report_json=payload,
        filename="measurement_comparison_report.json",
    )


__all__ = [
    "MAX_COMPARISON_JSON_BYTES",
    "MEASUREMENT_COMPARISON_REPORT_SCHEMA_VERSION",
    "SERVICE_ID",
    "SERVICE_VERSION",
    "MeasurementComparisonReportArtifact",
    "MeasurementComparisonRequest",
    "MeasurementComparisonServiceError",
    "load_measurement_comparison_json",
    "prepare_measurement_comparison_report",
    "run_measurement_comparison_report",
]
