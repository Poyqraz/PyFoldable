"""Fail-closed PR-10 experiment, calibration, and uncertainty contract."""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Mapping


EXPERIMENT_CONTRACT_SCHEMA_VERSION = 2
TEST_STAND_MANIFEST_SCHEMA_VERSION = 1
ExperimentRole = Literal["fixed_reference", "foldable"]
REQUIRED_UNITS = {
    "thrust": "N",
    "torque": "N*m",
    "rpm": "rpm",
    "voltage": "V",
    "current": "A",
    "temperature": "K",
    "pressure": "Pa",
}
SAMPLE_FIELDS = {
    "thrust": "thrust_n",
    "torque": "torque_nm",
    "rpm": "rpm",
    "voltage": "voltage_v",
    "current": "current_a",
    "temperature": "temperature_k",
    "pressure": "pressure_pa",
}


def _nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty.")


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


def _date(name: str, value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must use YYYY-MM-DD.") from exc


@dataclass(frozen=True)
class CalibrationIdentity:
    sensor_id: str
    quantity: str
    unit: str
    certificate_id: str
    certificate_sha256: str
    valid_from: str
    valid_until: str
    standard_uncertainty: float
    qualification: str

    def __post_init__(self) -> None:
        for name in ("sensor_id", "quantity", "unit", "certificate_id", "qualification"):
            _nonempty(name, getattr(self, name))
        if self.quantity not in REQUIRED_UNITS:
            raise ValueError(f"Unknown calibrated quantity: {self.quantity}")
        if re.fullmatch(r"[0-9a-f]{64}", self.certificate_sha256) is None:
            raise ValueError("certificate_sha256 must be a SHA-256 digest.")
        start = _date("valid_from", self.valid_from)
        end = _date("valid_until", self.valid_until)
        if end < start:
            raise ValueError("valid_until must not precede valid_from.")
        _finite("standard_uncertainty", self.standard_uncertainty)
        if self.standard_uncertainty < 0.0:
            raise ValueError("standard_uncertainty must not be negative.")

    def valid_on(self, experiment_date: str) -> bool:
        value = _date("experiment_date", experiment_date)
        return _date("valid_from", self.valid_from) <= value <= _date(
            "valid_until", self.valid_until
        )

    def as_mapping(self) -> Mapping[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ExperimentPolicy:
    minimum_repeats: int = 3
    maximum_zero_drift: Mapping[str, float] = field(default_factory=dict)
    coverage_factor: float = 2.0

    def __post_init__(self) -> None:
        if not isinstance(self.minimum_repeats, int) or isinstance(
            self.minimum_repeats, bool
        ) or self.minimum_repeats < 2:
            raise ValueError("minimum_repeats must be an integer of at least two.")
        for quantity, limit in self.maximum_zero_drift.items():
            if quantity not in {"thrust", "torque"}:
                raise ValueError("Zero-drift limits support thrust and torque only.")
            _finite(f"maximum_zero_drift.{quantity}", limit)
            if limit < 0.0:
                raise ValueError("Zero-drift limits must not be negative.")
        _finite("coverage_factor", self.coverage_factor)
        if self.coverage_factor <= 0.0:
            raise ValueError("coverage_factor must be greater than zero.")

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "minimum_repeats": self.minimum_repeats,
            "maximum_zero_drift": dict(self.maximum_zero_drift),
            "coverage_factor": self.coverage_factor,
        }


@dataclass(frozen=True)
class TestStandManifest:
    __test__ = False

    id: str
    calibrations: tuple[CalibrationIdentity, ...]
    policy: ExperimentPolicy

    def __post_init__(self) -> None:
        _nonempty("id", self.id)
        if not all(
            isinstance(value, CalibrationIdentity) for value in self.calibrations
        ):
            raise TypeError("calibrations must contain CalibrationIdentity values.")
        quantities = tuple(value.quantity for value in self.calibrations)
        if len(set(quantities)) != len(quantities):
            raise ValueError("Calibration quantities must be unique.")
        missing = set(REQUIRED_UNITS) - set(quantities)
        if missing:
            raise ValueError(f"Missing required calibration channels: {sorted(missing)}")
        by_quantity = {value.quantity: value for value in self.calibrations}
        for quantity, unit in REQUIRED_UNITS.items():
            if by_quantity[quantity].unit != unit:
                raise ValueError(
                    f"Calibration unit for {quantity} must be {unit}."
                )
        if not isinstance(self.policy, ExperimentPolicy):
            raise TypeError("policy must be ExperimentPolicy.")

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "schema_version": TEST_STAND_MANIFEST_SCHEMA_VERSION,
            "id": self.id,
            "calibrations": [dict(value.as_mapping()) for value in self.calibrations],
            "policy": dict(self.policy.as_mapping()),
        }


def canonical_test_stand_manifest_sha256(manifest: TestStandManifest) -> str:
    """Return the stable identity of every calibration and policy input."""
    if not isinstance(manifest, TestStandManifest):
        raise TypeError("manifest must be TestStandManifest.")
    payload = json.dumps(
        manifest.as_mapping(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_mapping_sha256(document: Mapping[str, Any]) -> str:
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ExperimentSample:
    run_id: str
    role: ExperimentRole
    design_id: str
    repeat_index: int
    sample_index: int
    timestamp_s: float
    thrust_n: float
    torque_nm: float
    rpm: float
    voltage_v: float
    current_a: float
    temperature_k: float
    pressure_pa: float

    def __post_init__(self) -> None:
        for name in ("run_id", "design_id"):
            _nonempty(name, getattr(self, name))
        if self.role not in {"fixed_reference", "foldable"}:
            raise ValueError("role must be fixed_reference or foldable.")
        for name in ("repeat_index", "sample_index"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer.")
        _finite("timestamp_s", self.timestamp_s)
        if self.timestamp_s < 0.0:
            raise ValueError("timestamp_s must not be negative.")
        for name in SAMPLE_FIELDS.values():
            _finite(name, getattr(self, name))
        for name in (
            "thrust_n", "torque_nm", "rpm", "voltage_v", "current_a",
            "temperature_k", "pressure_pa",
        ):
            if getattr(self, name) < 0.0:
                raise ValueError(f"{name} must not be negative.")

    def as_mapping(self) -> Mapping[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ExperimentRun:
    id: str
    role: ExperimentRole
    design_id: str
    experiment_date: str
    raw_data_sha256: str
    zero_before: Mapping[str, float]
    zero_after: Mapping[str, float]
    samples: tuple[ExperimentSample, ...]

    def __post_init__(self) -> None:
        for name in ("id", "design_id"):
            _nonempty(name, getattr(self, name))
        if self.role not in {"fixed_reference", "foldable"}:
            raise ValueError("role must be fixed_reference or foldable.")
        _date("experiment_date", self.experiment_date)
        if re.fullmatch(r"[0-9a-f]{64}", self.raw_data_sha256) is None:
            raise ValueError("raw_data_sha256 must be a SHA-256 digest.")
        if set(self.zero_before) != {"thrust", "torque"} or set(
            self.zero_after
        ) != {"thrust", "torque"}:
            raise ValueError("zero_before/after must contain thrust and torque.")
        for mapping_name, values in (
            ("zero_before", self.zero_before), ("zero_after", self.zero_after)
        ):
            for quantity, value in values.items():
                _finite(f"{mapping_name}.{quantity}", value)
        if not self.samples or not all(
            isinstance(value, ExperimentSample) for value in self.samples
        ):
            raise TypeError("samples must contain ExperimentSample values.")
        identities = tuple(
            (value.repeat_index, value.sample_index) for value in self.samples
        )
        if len(set(identities)) != len(identities):
            raise ValueError("Sample repeat/sample identities must be unique.")
        if any(
            value.run_id != self.id
            or value.role != self.role
            or value.design_id != self.design_id
            for value in self.samples
        ):
            raise ValueError("Sample run, role, and design identities must match.")

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "design_id": self.design_id,
            "experiment_date": self.experiment_date,
            "raw_data_sha256": self.raw_data_sha256,
            "zero_before": dict(self.zero_before),
            "zero_after": dict(self.zero_after),
            "samples": [dict(value.as_mapping()) for value in self.samples],
        }


@dataclass(frozen=True)
class UncertaintyMetric:
    mean: float
    standard_uncertainty_type_a: float
    standard_uncertainty_calibration: float
    standard_uncertainty_zero_drift: float
    combined_standard_uncertainty: float
    expanded_uncertainty: float
    unit: str

    def as_mapping(self) -> Mapping[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ExperimentSummary:
    run_id: str
    role: str
    repeat_count: int
    metrics: Mapping[str, UncertaintyMetric]

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "run_id": self.run_id,
            "role": self.role,
            "repeat_count": self.repeat_count,
            "metrics": {
                key: dict(value.as_mapping()) for key, value in self.metrics.items()
            },
        }


def canonical_experiment_summary_sha256(summary: ExperimentSummary) -> str:
    """Return the stable identity of an assessed run summary."""
    if not isinstance(summary, ExperimentSummary):
        raise TypeError("summary must be ExperimentSummary.")
    return _canonical_mapping_sha256(summary.as_mapping())


@dataclass(frozen=True)
class ExperimentRunDecision:
    run_id: str
    failures: tuple[str, ...]
    raw_data_sha256: str | None = None
    design_id: str | None = None
    experiment_date: str | None = None
    summary_sha256: str | None = None

    def __post_init__(self) -> None:
        identities = (
            self.raw_data_sha256,
            self.design_id,
            self.experiment_date,
            self.summary_sha256,
        )
        if all(value is None for value in identities):
            return
        if any(value is None for value in identities):
            raise ValueError("Run evidence identity fields must be supplied together.")
        if re.fullmatch(r"[0-9a-f]{64}", self.raw_data_sha256 or "") is None:
            raise ValueError("raw_data_sha256 must be a SHA-256 digest.")
        if re.fullmatch(r"[0-9a-f]{64}", self.summary_sha256 or "") is None:
            raise ValueError("summary_sha256 must be a SHA-256 digest.")
        _nonempty("design_id", self.design_id or "")
        if len(self.design_id or "") > 4096:
            raise ValueError("design_id must be a bounded string.")
        _date("experiment_date", self.experiment_date or "")

    @property
    def passed(self) -> bool:
        return not self.failures

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "run_id": self.run_id,
            "passed": self.passed,
            "failures": list(self.failures),
            "raw_data_sha256": self.raw_data_sha256,
            "design_id": self.design_id,
            "experiment_date": self.experiment_date,
            "summary_sha256": self.summary_sha256,
        }


@dataclass(frozen=True)
class ExperimentBundleDecision:
    stand_id: str
    runs: tuple[ExperimentRunDecision, ...]
    summaries: tuple[ExperimentSummary, ...]
    missing_roles: tuple[str, ...]
    test_stand_manifest_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.test_stand_manifest_sha256 is not None and re.fullmatch(
            r"[0-9a-f]{64}", self.test_stand_manifest_sha256
        ) is None:
            raise ValueError("test_stand_manifest_sha256 must be a SHA-256 digest.")

    @property
    def software_gate_passed(self) -> bool:
        return not self.missing_roles and bool(self.runs) and all(
            value.passed for value in self.runs
        )

    @property
    def physical_qualification(self) -> bool:
        return False

    @property
    def state(self) -> str:
        if self.software_gate_passed:
            return "software_pass_physical_measurements_pending"
        return "blocked_incomplete_or_invalid_experiment_evidence"

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "schema_version": EXPERIMENT_CONTRACT_SCHEMA_VERSION,
            "stand_id": self.stand_id,
            "state": self.state,
            "software_gate_passed": self.software_gate_passed,
            "physical_qualification": self.physical_qualification,
            "test_stand_manifest_sha256": self.test_stand_manifest_sha256,
            "missing_roles": list(self.missing_roles),
            "runs": [dict(value.as_mapping()) for value in self.runs],
            "summaries": [dict(value.as_mapping()) for value in self.summaries],
        }


def _summary(
    run: ExperimentRun,
    manifest: TestStandManifest,
) -> ExperimentSummary:
    calibrations = {value.quantity: value for value in manifest.calibrations}
    repeat_indices = sorted({sample.repeat_index for sample in run.samples})
    metrics: dict[str, UncertaintyMetric] = {}
    for quantity, field_name in SAMPLE_FIELDS.items():
        repeat_means = []
        for repeat_index in repeat_indices:
            values = [
                getattr(sample, field_name)
                for sample in run.samples
                if sample.repeat_index == repeat_index
            ]
            repeat_means.append(statistics.fmean(values))
        mean = statistics.fmean(repeat_means)
        type_a = (
            statistics.stdev(repeat_means) / math.sqrt(len(repeat_means))
            if len(repeat_means) > 1 else 0.0
        )
        calibration = calibrations[quantity].standard_uncertainty
        zero = 0.0
        if quantity in {"thrust", "torque"}:
            zero = abs(run.zero_after[quantity] - run.zero_before[quantity]) / math.sqrt(3.0)
        combined = math.sqrt(type_a * type_a + calibration * calibration + zero * zero)
        metrics[quantity] = UncertaintyMetric(
            mean, type_a, calibration, zero, combined,
            combined * manifest.policy.coverage_factor, REQUIRED_UNITS[quantity]
        )
    voltage = metrics["voltage"]
    current = metrics["current"]
    power_mean = voltage.mean * current.mean
    power_type_a = math.hypot(
        current.mean * voltage.standard_uncertainty_type_a,
        voltage.mean * current.standard_uncertainty_type_a,
    )
    power_calibration = math.hypot(
        current.mean * voltage.standard_uncertainty_calibration,
        voltage.mean * current.standard_uncertainty_calibration,
    )
    power_zero = 0.0
    power_combined = math.hypot(power_type_a, power_calibration)
    metrics["electrical_power"] = UncertaintyMetric(
        power_mean,
        power_type_a,
        power_calibration,
        power_zero,
        power_combined,
        power_combined * manifest.policy.coverage_factor,
        "W",
    )
    return ExperimentSummary(run.id, run.role, len(repeat_indices), metrics)


def assess_experiment_bundle(
    manifest: TestStandManifest,
    runs: tuple[ExperimentRun, ...],
) -> ExperimentBundleDecision:
    """Assess raw experiment identities, quality gates, and uncertainty budgets."""
    if not isinstance(manifest, TestStandManifest):
        raise TypeError("manifest must be TestStandManifest.")
    if not all(isinstance(run, ExperimentRun) for run in runs):
        raise TypeError("runs must contain ExperimentRun values.")
    ids = tuple(run.id for run in runs)
    if len(set(ids)) != len(ids):
        raise ValueError("Experiment run ids must be unique.")
    calibrations = {value.quantity: value for value in manifest.calibrations}
    decisions: list[ExperimentRunDecision] = []
    summaries: list[ExperimentSummary] = []
    for run in runs:
        failures: list[str] = []
        repeats = {sample.repeat_index for sample in run.samples}
        if len(repeats) < manifest.policy.minimum_repeats:
            failures.append("repeat_count_below_minimum")
        for quantity, calibration in calibrations.items():
            if not calibration.valid_on(run.experiment_date):
                failures.append(
                    f"calibration_invalid_on_experiment_date:{quantity}"
                )
        for quantity, limit in manifest.policy.maximum_zero_drift.items():
            drift = abs(run.zero_after[quantity] - run.zero_before[quantity])
            if drift > limit:
                failures.append(f"zero_drift_above_limit:{quantity}")
        summary = _summary(run, manifest)
        summaries.append(summary)
        decisions.append(
            ExperimentRunDecision(
                run.id,
                tuple(failures),
                run.raw_data_sha256,
                run.design_id,
                run.experiment_date,
                canonical_experiment_summary_sha256(summary),
            )
        )
    roles = {run.role for run in runs}
    missing_roles = tuple(sorted({"fixed_reference", "foldable"} - roles))
    return ExperimentBundleDecision(
        manifest.id,
        tuple(decisions),
        tuple(summaries),
        missing_roles,
        canonical_test_stand_manifest_sha256(manifest),
    )
