"""Fail-closed PY-06A matched experiment comparison contract."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from datetime import date
from types import MappingProxyType
from typing import Any, Mapping

from pyfoldable.core.experiment_contract import (
    REQUIRED_UNITS,
    ExperimentBundleDecision,
    ExperimentRunDecision,
    ExperimentSummary,
    TestStandManifest,
    UncertaintyMetric,
    canonical_experiment_summary_sha256,
    canonical_test_stand_manifest_sha256,
)


MEASUREMENT_COMPARISON_SCHEMA_VERSION = 1
_CONTEXT_CLASSES = frozenset({"software_fixture", "project_measurement_unqualified"})
_METRICS = {
    "thrust": ("thrust", "N"),
    "rotor_shaft_torque": ("torque", "N*m"),
    "dc_electrical_input_power": ("electrical_power", "W"),
}
_CONDITION_METRICS = {"rpm": "rpm", "temperature": "K", "pressure": "Pa"}


class MeasurementComparisonError(ValueError):
    """Matched comparison cannot be evaluated without changing its meaning."""


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite scalar.")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite scalar.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite scalar.")
    return result


def _nonempty(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(f"{name} must be a bounded nonempty string.")
    return value


@dataclass(frozen=True)
class RunComparisonContext:
    """Explicit geometry and channel meaning for one PR-10 run summary."""

    run_id: str
    open_diameter_m: float
    forward_speed_m_s: float
    torque_channel: str
    electrical_power_channel: str
    source: str
    classification: str

    def __post_init__(self) -> None:
        _nonempty("run_id", self.run_id)
        diameter = _finite("open_diameter_m", self.open_diameter_m)
        speed = _finite("forward_speed_m_s", self.forward_speed_m_s)
        _nonempty("source", self.source)
        if diameter <= 0.0:
            raise ValueError("open_diameter_m must be positive.")
        if speed < 0.0:
            raise ValueError("forward_speed_m_s must be nonnegative.")
        if self.torque_channel != "rotor_shaft_torque":
            raise ValueError(
                "torque_channel must be rotor_shaft_torque; hinge or generic torque is unsupported."
            )
        if self.electrical_power_channel != "dc_electrical_input_power":
            raise ValueError(
                "electrical_power_channel must be dc_electrical_input_power, not shaft power."
            )
        if self.classification not in _CONTEXT_CLASSES:
            raise ValueError("Run context requires an explicit unqualified classification.")

    def as_mapping(self) -> Mapping[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ComparisonPolicy:
    maximum_diameter_delta_m: float
    maximum_rpm_relative_delta: float
    maximum_forward_speed_delta_m_s: float
    maximum_temperature_delta_k: float
    maximum_pressure_delta_pa: float
    thrust_uncertainty_correlation: float
    rotor_shaft_torque_uncertainty_correlation: float
    dc_electrical_input_power_uncertainty_correlation: float
    target_thrust_ratio: float = 0.85

    def __post_init__(self) -> None:
        values = {
            name: _finite(name, getattr(self, name))
            for name in vars(self)
        }
        for name in (
            "maximum_diameter_delta_m", "maximum_rpm_relative_delta",
            "maximum_forward_speed_delta_m_s", "maximum_temperature_delta_k",
            "maximum_pressure_delta_pa",
        ):
            if values[name] < 0.0:
                raise ValueError("Comparison tolerances must be nonnegative.")
        if not 0.0 < values["target_thrust_ratio"] <= 2.0:
            raise ValueError("target_thrust_ratio must lie in (0, 2].")
        for name in (
            "thrust_uncertainty_correlation",
            "rotor_shaft_torque_uncertainty_correlation",
            "dc_electrical_input_power_uncertainty_correlation",
        ):
            if not -1.0 <= values[name] <= 1.0:
                raise ValueError("Uncertainty correlation coefficients must lie in [-1, 1].")
        if (values["maximum_diameter_delta_m"] > 1.0
                or values["maximum_rpm_relative_delta"] > 0.5
                or values["maximum_forward_speed_delta_m_s"] > 100.0
                or values["maximum_temperature_delta_k"] > 100.0
                or values["maximum_pressure_delta_pa"] > 100_000.0):
            raise ValueError("Comparison tolerances exceed the bounded policy domain.")

    def as_mapping(self) -> Mapping[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ComparisonMetric:
    quantity: str
    unit: str
    fixed_mean: float
    foldable_mean: float
    difference: float
    standard_uncertainty_difference: float
    ratio: float
    standard_uncertainty_ratio: float
    expanded_uncertainty_ratio: float
    ratio_interval_lower: float
    ratio_interval_upper: float

    def as_mapping(self) -> Mapping[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MatchedExperimentComparison:
    stand_id: str
    test_stand_manifest_sha256: str
    fixed_context: RunComparisonContext
    foldable_context: RunComparisonContext
    selected_run_identities: Mapping[str, Mapping[str, str]]
    policy: ComparisonPolicy
    coverage_factor: float
    condition_matches: Mapping[str, bool]
    condition_deltas: Mapping[str, float]
    failures: tuple[str, ...]
    metrics: Mapping[str, ComparisonMetric]
    target_decision: str

    @property
    def physical_qualification(self) -> bool:
        return False

    @property
    def target_fitting_performed(self) -> bool:
        return False

    @property
    def state(self) -> str:
        if self.failures:
            return "blocked_unmatched_or_invalid_experiment_evidence"
        return "screening_comparison_complete_physical_evidence_pending"

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "schema_version": MEASUREMENT_COMPARISON_SCHEMA_VERSION,
            "artifact_class": "matched_experiment_comparison",
            "state": self.state,
            "qualification": "screening_only",
            "physical_qualification": False,
            "target_fitting_performed": False,
            "stand_id": self.stand_id,
            "test_stand_manifest_sha256": self.test_stand_manifest_sha256,
            "fixed_context": dict(self.fixed_context.as_mapping()),
            "foldable_context": dict(self.foldable_context.as_mapping()),
            "selected_run_identities": {
                role: dict(identity)
                for role, identity in self.selected_run_identities.items()
            },
            "policy": dict(self.policy.as_mapping()),
            "coverage_factor": self.coverage_factor,
            "condition_matches": dict(self.condition_matches),
            "condition_deltas": dict(self.condition_deltas),
            "failures": list(self.failures),
            "metrics": {
                name: dict(value.as_mapping()) for name, value in self.metrics.items()
            },
            "target_decision": self.target_decision,
            "limitations": [
                "Pairwise covariance uses the policy's declared per-quantity correlation coefficients.",
                "DC electrical input power is not motor shaft power.",
                "Rotor shaft torque is not hinge-axis torque.",
                "The target is classified after comparison and is not a fitted model parameter.",
            ],
        }


def _validated_metric(
    summary: ExperimentSummary,
    key: str,
    unit: str,
    coverage_factor: float,
) -> UncertaintyMetric:
    value = summary.metrics.get(key) if isinstance(summary.metrics, Mapping) else None
    if not isinstance(value, UncertaintyMetric):
        raise MeasurementComparisonError(f"Missing uncertainty metric: {key}.")
    if value.unit != unit:
        raise MeasurementComparisonError(f"Unexpected unit for {key}: expected {unit}.")
    numeric_names = (
        "mean", "standard_uncertainty_type_a",
        "standard_uncertainty_calibration", "standard_uncertainty_zero_drift",
        "combined_standard_uncertainty", "expanded_uncertainty",
    )
    try:
        numbers = {name: _finite(f"{key}.{name}", getattr(value, name)) for name in numeric_names}
    except ValueError as exc:
        raise MeasurementComparisonError(f"{key} must contain finite uncertainty values.") from exc
    if numbers["mean"] < 0.0 or any(
        numbers[name] < 0.0 for name in numeric_names if name != "mean"
    ):
        raise MeasurementComparisonError(f"{key} uncertainty values must be nonnegative.")
    expected_combined = math.hypot(
        numbers["standard_uncertainty_type_a"],
        numbers["standard_uncertainty_calibration"],
        numbers["standard_uncertainty_zero_drift"],
    )
    if not math.isclose(
        numbers["combined_standard_uncertainty"], expected_combined,
        rel_tol=1e-12, abs_tol=16 * math.ulp(max(expected_combined, 0.0)),
    ):
        raise MeasurementComparisonError(f"{key} combined uncertainty is inconsistent.")
    expected_expanded = coverage_factor * expected_combined
    if not math.isfinite(expected_combined) or not math.isfinite(expected_expanded):
        raise MeasurementComparisonError(f"{key} uncertainty overflowed and is not finite.")
    if not math.isclose(
        numbers["expanded_uncertainty"], expected_expanded,
        rel_tol=1e-12, abs_tol=16 * math.ulp(max(expected_expanded, 0.0)),
    ):
        raise MeasurementComparisonError(f"{key} expanded uncertainty is inconsistent.")
    return UncertaintyMetric(
        numbers["mean"],
        numbers["standard_uncertainty_type_a"],
        numbers["standard_uncertainty_calibration"],
        numbers["standard_uncertainty_zero_drift"],
        numbers["combined_standard_uncertainty"],
        numbers["expanded_uncertainty"],
        value.unit,
    )


def _validated_pr10_summary(
    summary: ExperimentSummary,
    manifest: TestStandManifest,
    coverage_factor: float,
) -> Mapping[str, UncertaintyMetric]:
    """Validate direct calibration channels and the derived V*I power metric."""
    expected_metric_keys = set(REQUIRED_UNITS) | {"electrical_power"}
    if (
        not isinstance(summary.metrics, Mapping)
        or set(summary.metrics) != expected_metric_keys
        or any(
            not isinstance(key, str) or not isinstance(value, UncertaintyMetric)
            for key, value in summary.metrics.items()
        )
    ):
        raise MeasurementComparisonError(
            "Experiment summary metric keys and values must exactly match PR-10."
        )
    calibration_by_quantity = {
        value.quantity: value for value in manifest.calibrations
    }
    metrics = {
        name: _validated_metric(summary, name, unit, coverage_factor)
        for name, unit in REQUIRED_UNITS.items()
    }
    for name, metric in metrics.items():
        expected = calibration_by_quantity[name].standard_uncertainty
        if not math.isclose(
            metric.standard_uncertainty_calibration,
            expected,
            rel_tol=1e-12,
            abs_tol=16 * math.ulp(max(abs(expected), 0.0)),
        ):
            raise MeasurementComparisonError(
                f"{name} calibration uncertainty does not match the bound manifest."
            )
    voltage = metrics["voltage"]
    current = metrics["current"]
    power = _validated_metric(summary, "electrical_power", "W", coverage_factor)
    try:
        expected = {
            "mean": voltage.mean * current.mean,
            "standard_uncertainty_type_a": math.hypot(
                current.mean * voltage.standard_uncertainty_type_a,
                voltage.mean * current.standard_uncertainty_type_a,
            ),
            "standard_uncertainty_calibration": math.hypot(
                current.mean * voltage.standard_uncertainty_calibration,
                voltage.mean * current.standard_uncertainty_calibration,
            ),
            "standard_uncertainty_zero_drift": 0.0,
        }
    except (ArithmeticError, OverflowError, ValueError) as exc:
        raise MeasurementComparisonError(
            "PR-10 electrical power derivation overflowed."
        ) from exc
    if any(not math.isfinite(value) for value in expected.values()):
        raise MeasurementComparisonError("PR-10 electrical power derivation overflowed.")
    for name, value in expected.items():
        actual = getattr(power, name)
        if not math.isclose(
            actual,
            value,
            rel_tol=1e-12,
            abs_tol=16 * math.ulp(max(abs(value), 0.0)),
        ):
            raise MeasurementComparisonError(
                "PR-10 electrical power must preserve the voltage-current derivation."
            )
    return MappingProxyType({**metrics, "electrical_power": power})


def _select_summary(
    decision: ExperimentBundleDecision,
    run_id: str,
    role: str,
    minimum_repeats: int,
) -> ExperimentSummary:
    if not isinstance(decision.summaries, tuple):
        raise MeasurementComparisonError("Experiment summaries must be immutable.")
    if any(not isinstance(value, ExperimentSummary) for value in decision.summaries):
        raise MeasurementComparisonError("Experiment summaries must be typed.")
    try:
        summary_ids = tuple(
            _nonempty("experiment summary run_id", value.run_id)
            for value in decision.summaries
        )
    except ValueError as exc:
        raise MeasurementComparisonError(
            "Experiment summary run ids must be bounded strings."
        ) from exc
    if len(set(summary_ids)) != len(summary_ids):
        raise MeasurementComparisonError("Experiment summary run ids must be unique.")
    matches = [value for value in decision.summaries if value.run_id == run_id]
    if len(matches) != 1:
        raise MeasurementComparisonError(f"Selected run id is absent or ambiguous: {run_id}.")
    summary = matches[0]
    if summary.role != role:
        raise MeasurementComparisonError(f"Selected {role} run has the wrong role.")
    if (isinstance(summary.repeat_count, bool)
            or not isinstance(summary.repeat_count, int)
            or summary.repeat_count < minimum_repeats):
        raise MeasurementComparisonError("Selected summary repeat count is below policy.")
    return summary


def _comparison_metric(
    quantity: str,
    unit: str,
    fixed: UncertaintyMetric,
    foldable: UncertaintyMetric,
    coverage_factor: float,
    correlation: float,
) -> ComparisonMetric:
    fixed_mean = float(fixed.mean)
    foldable_mean = float(foldable.mean)
    if fixed_mean <= 0.0:
        raise MeasurementComparisonError(f"{quantity} fixed denominator must be positive.")
    fixed_u = float(fixed.combined_standard_uncertainty)
    foldable_u = float(foldable.combined_standard_uncertainty)
    try:
        difference = foldable_mean - fixed_mean
        difference_a = foldable_u
        difference_b = fixed_u
        ratio = foldable_mean / fixed_mean
        ratio_a = foldable_u / fixed_mean
        ratio_b = foldable_mean * fixed_u / fixed_mean**2
        difference_variance = (
            difference_a**2 + difference_b**2
            - 2.0 * correlation * difference_a * difference_b
        )
        ratio_variance = (
            ratio_a**2 + ratio_b**2
            - 2.0 * correlation * ratio_a * ratio_b
        )
        difference_scale = difference_a**2 + difference_b**2 + 2 * difference_a * difference_b
        ratio_scale = ratio_a**2 + ratio_b**2 + 2 * ratio_a * ratio_b
        if difference_variance < -32 * math.ulp(max(difference_scale, 0.0)):
            raise MeasurementComparisonError(f"{quantity} difference covariance is invalid.")
        if ratio_variance < -32 * math.ulp(max(ratio_scale, 0.0)):
            raise MeasurementComparisonError(f"{quantity} ratio covariance is invalid.")
        difference_u = math.sqrt(max(0.0, difference_variance))
        ratio_u = math.sqrt(max(0.0, ratio_variance))
        expanded_ratio_u = coverage_factor * ratio_u
        lower = ratio - expanded_ratio_u
        upper = ratio + expanded_ratio_u
    except (ArithmeticError, OverflowError, ValueError) as exc:
        raise MeasurementComparisonError(f"{quantity} comparison overflowed.") from exc
    for name, value in (
        ("difference", difference), ("difference uncertainty", difference_u),
        ("ratio", ratio), ("ratio uncertainty", ratio_u),
        ("expanded ratio uncertainty", expanded_ratio_u),
        ("ratio lower", lower), ("ratio upper", upper),
    ):
        try:
            _finite(f"{quantity} {name}", value)
        except ValueError as exc:
            raise MeasurementComparisonError(f"{quantity} comparison is not finite.") from exc
    return ComparisonMetric(
        quantity, unit, fixed_mean, foldable_mean, difference, difference_u,
        ratio, ratio_u, expanded_ratio_u, lower, upper,
    )


def build_matched_experiment_comparison(
    manifest: TestStandManifest,
    decision: ExperimentBundleDecision,
    fixed_context: RunComparisonContext,
    foldable_context: RunComparisonContext,
    policy: ComparisonPolicy,
) -> MatchedExperimentComparison:
    """Compare exact fixed/foldable PR-10 summaries without target fitting."""
    if not isinstance(manifest, TestStandManifest):
        raise MeasurementComparisonError("manifest must be a TestStandManifest.")
    if not isinstance(decision, ExperimentBundleDecision):
        raise MeasurementComparisonError("decision must be an ExperimentBundleDecision.")
    if not isinstance(fixed_context, RunComparisonContext) or not isinstance(
        foldable_context, RunComparisonContext
    ):
        raise MeasurementComparisonError("Both run comparison contexts are required.")
    if not isinstance(policy, ComparisonPolicy):
        raise MeasurementComparisonError("policy must be a ComparisonPolicy.")
    if manifest.id != decision.stand_id:
        raise MeasurementComparisonError("Manifest and decision test-stand identity mismatch.")
    try:
        expected_manifest_sha256 = canonical_test_stand_manifest_sha256(manifest)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MeasurementComparisonError(
            "Test-stand manifest cannot be canonically identified."
        ) from exc
    if (
        not isinstance(decision.test_stand_manifest_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", decision.test_stand_manifest_sha256) is None
        or decision.test_stand_manifest_sha256 != expected_manifest_sha256
    ):
        raise MeasurementComparisonError(
            "Experiment decision manifest digest is missing or mismatched."
        )
    if (not isinstance(decision.runs, tuple)
            or not decision.runs
            or any(not isinstance(value, ExperimentRunDecision) for value in decision.runs)):
        raise MeasurementComparisonError("Experiment run decisions must be immutable and typed.")
    for value in decision.runs:
        try:
            _nonempty("run decision run_id", value.run_id)
        except ValueError as exc:
            raise MeasurementComparisonError("Experiment run decision ids are invalid.") from exc
        if (not isinstance(value.failures, tuple)
                or any(not isinstance(item, str) or not item for item in value.failures)):
            raise MeasurementComparisonError("Experiment run decision failures must be a string tuple.")
        if (
            not isinstance(value.raw_data_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", value.raw_data_sha256) is None
        ):
            raise MeasurementComparisonError("Experiment run raw-data digest is invalid.")
        if (
            not isinstance(value.summary_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", value.summary_sha256) is None
        ):
            raise MeasurementComparisonError("Experiment run summary digest is invalid.")
        try:
            _nonempty("run decision design_id", value.design_id)
            date.fromisoformat(value.experiment_date or "")
        except (TypeError, ValueError) as exc:
            raise MeasurementComparisonError(
                "Experiment run design identity or date is invalid."
            ) from exc
    if (not isinstance(decision.missing_roles, tuple)
            or any(not isinstance(role, str)
                   or role not in {"fixed_reference", "foldable"}
                   for role in decision.missing_roles)
            or len(set(decision.missing_roles)) != len(decision.missing_roles)):
        raise MeasurementComparisonError("Experiment missing roles must be an immutable role tuple.")
    if not decision.software_gate_passed:
        raise MeasurementComparisonError("Experiment bundle software gate has not passed.")
    if fixed_context.run_id == foldable_context.run_id:
        raise MeasurementComparisonError("Fixed and foldable run ids must differ.")
    run_decisions = {value.run_id: value for value in decision.runs}
    if len(run_decisions) != len(decision.runs):
        raise MeasurementComparisonError("Experiment decision run ids must be unique.")
    for run_id in (fixed_context.run_id, foldable_context.run_id):
        run_decision = run_decisions.get(run_id)
        if run_decision is None:
            raise MeasurementComparisonError(f"Selected run id is absent: {run_id}.")
        if not run_decision.passed:
            raise MeasurementComparisonError("Selected run failed the experiment software gate.")
        invalid_calibrations = tuple(
            calibration.quantity
            for calibration in manifest.calibrations
            if not calibration.valid_on(run_decision.experiment_date or "")
        )
        if invalid_calibrations:
            raise MeasurementComparisonError(
                "Selected run calibration is invalid on its experiment date: "
                + ", ".join(invalid_calibrations)
                + "."
            )
    selected_run_identities = MappingProxyType({
        role: MappingProxyType({
            "run_id": run_decision.run_id,
            "raw_data_sha256": run_decision.raw_data_sha256,
            "design_id": run_decision.design_id,
            "experiment_date": run_decision.experiment_date,
            "summary_sha256": run_decision.summary_sha256,
        })
        for role, run_decision in (
            ("fixed", run_decisions[fixed_context.run_id]),
            ("foldable", run_decisions[foldable_context.run_id]),
        )
    })

    fixed = _select_summary(
        decision, fixed_context.run_id, "fixed_reference", manifest.policy.minimum_repeats
    )
    foldable = _select_summary(
        decision, foldable_context.run_id, "foldable", manifest.policy.minimum_repeats
    )
    coverage_factor = _finite("coverage_factor", manifest.policy.coverage_factor)
    fixed_metrics = _validated_pr10_summary(fixed, manifest, coverage_factor)
    foldable_metrics = _validated_pr10_summary(foldable, manifest, coverage_factor)
    for summary, run_decision in (
        (fixed, run_decisions[fixed_context.run_id]),
        (foldable, run_decisions[foldable_context.run_id]),
    ):
        try:
            actual_summary_sha256 = canonical_experiment_summary_sha256(summary)
        except (TypeError, ValueError, OverflowError) as exc:
            raise MeasurementComparisonError(
                "Experiment summary cannot be canonically identified."
            ) from exc
        if actual_summary_sha256 != run_decision.summary_sha256:
            raise MeasurementComparisonError(
                "Experiment summary digest does not match the assessed run decision."
            )
    validated = {
        output_name: (fixed_metrics[summary_name], foldable_metrics[summary_name])
        for output_name, (summary_name, _unit) in _METRICS.items()
    }
    condition_values = {
        summary_name: (fixed_metrics[summary_name], foldable_metrics[summary_name])
        for summary_name in _CONDITION_METRICS
    }

    fixed_rpm = float(condition_values["rpm"][0].mean)
    foldable_rpm = float(condition_values["rpm"][1].mean)
    if fixed_rpm <= 0.0 or foldable_rpm <= 0.0:
        raise MeasurementComparisonError("Matched comparison requires positive RPM means.")
    for name in ("temperature", "pressure"):
        if any(value.mean <= 0.0 for value in condition_values[name]):
            raise MeasurementComparisonError(
                f"Matched comparison requires positive {name} means."
            )
    deltas = {
        "diameter": abs(foldable_context.open_diameter_m - fixed_context.open_diameter_m),
        "rpm": abs(foldable_rpm - fixed_rpm) / fixed_rpm,
        "forward_speed": abs(
            foldable_context.forward_speed_m_s - fixed_context.forward_speed_m_s
        ),
        "temperature": abs(
            condition_values["temperature"][1].mean
            - condition_values["temperature"][0].mean
        ),
        "pressure": abs(
            condition_values["pressure"][1].mean
            - condition_values["pressure"][0].mean
        ),
    }
    if any(not math.isfinite(value) for value in deltas.values()):
        raise MeasurementComparisonError("Matched-condition delta must be finite.")
    limits = {
        "diameter": policy.maximum_diameter_delta_m,
        "rpm": policy.maximum_rpm_relative_delta,
        "forward_speed": policy.maximum_forward_speed_delta_m_s,
        "temperature": policy.maximum_temperature_delta_k,
        "pressure": policy.maximum_pressure_delta_pa,
    }
    matches = {name: deltas[name] <= limits[name] for name in deltas}
    failures = tuple(f"condition_mismatch:{name}" for name, passed in matches.items() if not passed)
    if failures:
        metrics: Mapping[str, ComparisonMetric] = MappingProxyType({})
        target_decision = "blocked"
    else:
        metric_values = {
            name: _comparison_metric(
                name,
                _METRICS[name][1],
                pair[0],
                pair[1],
                coverage_factor,
                getattr(policy, f"{name}_uncertainty_correlation"),
            )
            for name, pair in validated.items()
        }
        metrics = MappingProxyType(metric_values)
        thrust = metric_values["thrust"]
        if thrust.ratio_interval_lower >= policy.target_thrust_ratio:
            target_decision = "screening_target_met"
        elif thrust.ratio_interval_upper < policy.target_thrust_ratio:
            target_decision = "screening_target_not_met"
        else:
            target_decision = "screening_target_indeterminate"
    return MatchedExperimentComparison(
        decision.stand_id,
        expected_manifest_sha256,
        fixed_context,
        foldable_context,
        selected_run_identities,
        policy,
        coverage_factor,
        MappingProxyType(matches),
        MappingProxyType(deltas),
        failures,
        metrics,
        target_decision,
    )


__all__ = [
    "ComparisonMetric",
    "ComparisonPolicy",
    "MEASUREMENT_COMPARISON_SCHEMA_VERSION",
    "MatchedExperimentComparison",
    "MeasurementComparisonError",
    "RunComparisonContext",
    "build_matched_experiment_comparison",
]
