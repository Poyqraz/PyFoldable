"""Fail-closed PY-06C correlation of PR-10, PR-07 and dynamometer evidence."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import date
from types import MappingProxyType
from typing import Any, Mapping

from .experiment_contract import (
    CalibrationIdentity,
    ExperimentBundleDecision,
    TestStandManifest,
    UncertaintyMetric,
)
from .measurement_comparison import (
    MeasurementComparisonError,
    ValidatedExperimentRunMeasurement,
    validate_experiment_run_measurement,
)
from .motor_bem_coupling import (
    COUPLED_OPERATING_POINT_SCHEMA_VERSION,
    CoupledOperatingPoint,
    canonical_coupled_operating_point_sha256,
)


MOTOR_ROTOR_CORRELATION_SCHEMA_VERSION = 1
MOTOR_TERMINAL_DC_INPUT = "motor_terminal_dc_input"
_DYNAMOMETER_UNITS = {
    "torque": "N*m",
    "rpm": "rpm",
    "voltage": "V",
    "current": "A",
    "temperature": "K",
    "pressure": "Pa",
}
_EVIDENCE_CLASSES = frozenset({
    "software_fixture",
    "independent_dynamometer_measurement_unqualified",
})
_CONTEXT_CLASSES = frozenset({"software_fixture", "project_measurement_unqualified"})


class MotorRotorCorrelationError(ValueError):
    """Evidence cannot be correlated without weakening the PY-06C contract."""


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite scalar.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite scalar.")
    return result


def _nonempty(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(f"{name} must be a bounded nonempty string.")
    return value


def _sha256(name: str, value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{name} must be a SHA-256 digest.")
    return value


def _close(actual: float, expected: float) -> bool:
    return math.isclose(
        actual,
        expected,
        rel_tol=1.0e-10,
        abs_tol=max(1.0e-10, 32 * math.ulp(max(abs(expected), 0.0))),
    )


@dataclass(frozen=True)
class MotorRotorRunContext:
    run_id: str
    expected_role: str
    design_id: str
    run_open_diameter_m: float
    run_forward_speed_m_s: float
    torque_channel: str
    motor_id: str
    motor_serial: str
    esc_id: str
    dc_power_measurement_location: str
    pr07_source_id: str
    pr07_source_sha256: str
    pr07_case_sha256: str
    pr07_design_id: str
    pr07_open_diameter_m: float
    pr07_forward_speed_m_s: float
    pr07_dc_power_location: str
    pr07_temperature_k: float
    pr07_pressure_pa: float
    source: str
    classification: str

    def __post_init__(self) -> None:
        for name in (
            "run_id", "design_id", "motor_id", "motor_serial", "esc_id",
            "dc_power_measurement_location", "pr07_source_id",
            "pr07_dc_power_location", "pr07_design_id", "source",
        ):
            _nonempty(name, getattr(self, name))
        if self.expected_role not in {"fixed_reference", "foldable"}:
            raise ValueError("expected_role must be fixed_reference or foldable.")
        if self.torque_channel != "rotor_shaft_torque":
            raise ValueError("torque_channel must be rotor_shaft_torque.")
        if self.classification not in _CONTEXT_CLASSES:
            raise ValueError("Run context classification is unsupported.")
        _sha256("pr07_source_sha256", self.pr07_source_sha256)
        _sha256("pr07_case_sha256", self.pr07_case_sha256)
        if _finite("pr07_temperature_k", self.pr07_temperature_k) <= 0.0:
            raise ValueError("pr07_temperature_k must be positive.")
        if _finite("pr07_pressure_pa", self.pr07_pressure_pa) <= 0.0:
            raise ValueError("pr07_pressure_pa must be positive.")
        for name in ("run_open_diameter_m", "pr07_open_diameter_m"):
            if _finite(name, getattr(self, name)) <= 0.0:
                raise ValueError(f"{name} must be positive.")
        for name in ("run_forward_speed_m_s", "pr07_forward_speed_m_s"):
            if _finite(name, getattr(self, name)) < 0.0:
                raise ValueError(f"{name} must be nonnegative.")

    def as_mapping(self) -> Mapping[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MotorDynamometerEvidence:
    evidence_id: str
    motor_id: str
    motor_serial: str
    esc_id: str
    experiment_date: str
    raw_data_sha256: str
    summary_sha256: str
    calibrations: tuple[CalibrationIdentity, ...]
    metrics: Mapping[str, UncertaintyMetric]
    coverage_factor: float
    dc_power_measurement_location: str
    source: str
    classification: str

    def __post_init__(self) -> None:
        for name in (
            "evidence_id", "motor_id", "motor_serial", "esc_id",
            "dc_power_measurement_location", "source",
        ):
            _nonempty(name, getattr(self, name))
        try:
            date.fromisoformat(self.experiment_date)
        except (TypeError, ValueError) as exc:
            raise ValueError("experiment_date must use YYYY-MM-DD.") from exc
        _sha256("raw_data_sha256", self.raw_data_sha256)
        _sha256("summary_sha256", self.summary_sha256)
        if not isinstance(self.calibrations, tuple) or any(
            not isinstance(value, CalibrationIdentity) for value in self.calibrations
        ):
            raise TypeError("calibrations must be a CalibrationIdentity tuple.")
        if not isinstance(self.metrics, Mapping) or any(
            not isinstance(key, str) or not isinstance(value, UncertaintyMetric)
            for key, value in self.metrics.items()
        ):
            raise TypeError("metrics must map strings to UncertaintyMetric values.")
        if self.classification not in _EVIDENCE_CLASSES:
            raise ValueError("Dynamometer evidence classification is unsupported.")
        if _finite("coverage_factor", self.coverage_factor) <= 0.0:
            raise ValueError("coverage_factor must be positive.")
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "motor_id": self.motor_id,
            "motor_serial": self.motor_serial,
            "esc_id": self.esc_id,
            "experiment_date": self.experiment_date,
            "raw_data_sha256": self.raw_data_sha256,
            "summary_sha256": self.summary_sha256,
            "calibrations": [dict(value.as_mapping()) for value in self.calibrations],
            "metrics": {
                key: dict(value.as_mapping()) for key, value in self.metrics.items()
            },
            "coverage_factor": self.coverage_factor,
            "dc_power_measurement_location": self.dc_power_measurement_location,
            "source": self.source,
            "classification": self.classification,
        }


def canonical_motor_dynamometer_evidence_sha256(
    evidence: MotorDynamometerEvidence,
) -> str:
    """Bind all dynamometer summary semantics independently of the raw-data digest."""
    if not isinstance(evidence, MotorDynamometerEvidence):
        raise TypeError("evidence must be MotorDynamometerEvidence.")
    document = dict(evidence.as_mapping())
    document.pop("summary_sha256")
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class MotorRotorCorrelationPolicy:
    maximum_rpm_relative_delta: float
    maximum_voltage_delta_v: float
    maximum_current_delta_a: float
    maximum_temperature_delta_k: float
    maximum_pressure_delta_pa: float
    maximum_diameter_delta_m: float
    maximum_forward_speed_delta_m_s: float
    coverage_factor: float
    dyno_voltage_current_correlation: float
    dyno_torque_rpm_correlation: float
    measured_torque_rpm_correlation: float
    dyno_shaft_dc_power_correlation: float
    dyno_measured_shaft_power_correlation: float
    dyno_measured_torque_correlation: float

    def __post_init__(self) -> None:
        values = {name: _finite(name, getattr(self, name)) for name in vars(self)}
        tolerance_names = (
            "maximum_rpm_relative_delta", "maximum_voltage_delta_v",
            "maximum_current_delta_a", "maximum_temperature_delta_k",
            "maximum_pressure_delta_pa", "maximum_diameter_delta_m",
            "maximum_forward_speed_delta_m_s",
        )
        if any(values[name] < 0.0 for name in tolerance_names):
            raise ValueError("Correlation tolerances must be nonnegative.")
        if (
            values["maximum_rpm_relative_delta"] > 0.5
            or values["maximum_voltage_delta_v"] > 100.0
            or values["maximum_current_delta_a"] > 1000.0
            or values["maximum_temperature_delta_k"] > 100.0
            or values["maximum_pressure_delta_pa"] > 100_000.0
            or values["maximum_diameter_delta_m"] > 1.0
            or values["maximum_forward_speed_delta_m_s"] > 100.0
        ):
            raise ValueError("Correlation tolerances exceed the bounded policy domain.")
        if values["coverage_factor"] <= 0.0 or values["coverage_factor"] > 10.0:
            raise ValueError("coverage_factor must lie in (0, 10].")
        for name, value in values.items():
            if name.endswith("_correlation") and not -1.0 <= value <= 1.0:
                raise ValueError("Uncertainty correlation coefficients must lie in [-1, 1].")

    def as_mapping(self) -> Mapping[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MotorCorrelationMetric:
    quantity: str
    unit: str
    reference: float
    observed: float
    residual: float
    standard_uncertainty_residual: float | None
    expanded_uncertainty_residual: float | None
    residual_interval_lower: float | None
    residual_interval_upper: float | None
    decision: str

    def as_mapping(self) -> Mapping[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MotorRotorCorrelationResult:
    stand_id: str
    run_context: MotorRotorRunContext
    selected_run_identity: Mapping[str, str]
    pr07_case_sha256: str
    dynamometer_identity: Mapping[str, str]
    policy: MotorRotorCorrelationPolicy
    condition_matches: Mapping[str, bool]
    condition_deltas: Mapping[str, float]
    failures: tuple[str, ...]
    derived: Mapping[str, float]
    metrics: Mapping[str, MotorCorrelationMetric]
    _state: str

    def __post_init__(self) -> None:
        if not isinstance(self.run_context, MotorRotorRunContext):
            raise TypeError("run_context must be MotorRotorRunContext.")
        if not isinstance(self.policy, MotorRotorCorrelationPolicy):
            raise TypeError("policy must be MotorRotorCorrelationPolicy.")
        if not isinstance(self.failures, tuple) or any(
            not isinstance(value, str) or not value for value in self.failures
        ):
            raise TypeError("failures must be an immutable string tuple.")
        if any(not isinstance(value, bool) for value in self.condition_matches.values()):
            raise TypeError("condition_matches values must be booleans.")
        if any(not isinstance(value, MotorCorrelationMetric) for value in self.metrics.values()):
            raise TypeError("metrics values must be MotorCorrelationMetric values.")
        for name, values in (
            ("selected_run_identity", self.selected_run_identity),
            ("dynamometer_identity", self.dynamometer_identity),
        ):
            if any(not isinstance(key, str) or not isinstance(value, str)
                   for key, value in values.items()):
                raise TypeError(f"{name} must contain string identities.")
        for name, values in (
            ("condition_deltas", self.condition_deltas),
            ("derived", self.derived),
        ):
            if any(not isinstance(key, str) or not math.isfinite(_finite(key, value))
                   for key, value in values.items()):
                raise TypeError(f"{name} must contain finite scalar values.")
        for name in (
            "selected_run_identity", "dynamometer_identity", "condition_matches",
            "condition_deltas", "derived", "metrics",
        ):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))

    @property
    def state(self) -> str:
        return self._state

    @property
    def physical_qualification(self) -> bool:
        return False

    @property
    def target_fitting_performed(self) -> bool:
        return False

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "schema_version": MOTOR_ROTOR_CORRELATION_SCHEMA_VERSION,
            "artifact_class": "motor_rotor_correlation",
            "state": self.state,
            "qualification": "screening_only",
            "physical_qualification": False,
            "target_fitting_performed": False,
            "stand_id": self.stand_id,
            "run_context": dict(self.run_context.as_mapping()),
            "selected_run_identity": dict(self.selected_run_identity),
            "pr07_case_sha256": self.pr07_case_sha256,
            "dynamometer_identity": dict(self.dynamometer_identity),
            "policy": dict(self.policy.as_mapping()),
            "condition_matches": dict(self.condition_matches),
            "condition_deltas": dict(self.condition_deltas),
            "failures": list(self.failures),
            "derived": dict(self.derived),
            "metrics": {
                name: dict(value.as_mapping()) for name, value in self.metrics.items()
            },
            "limitations": [
                "PR-07 model residuals omit unavailable model-form uncertainty.",
                "Battery discharge efficiency is not used as motor efficiency.",
                "Software fixtures and unreviewed measurements cannot qualify physics.",
            ],
        }


def _validate_metric(
    name: str,
    value: UncertaintyMetric,
    unit: str,
    coverage_factor: float,
    calibration_uncertainty: float,
) -> UncertaintyMetric:
    if not isinstance(value, UncertaintyMetric) or value.unit != unit:
        raise MotorRotorCorrelationError(f"Dynamometer {name} metric or unit is invalid.")
    numeric_names = (
        "mean", "standard_uncertainty_type_a",
        "standard_uncertainty_calibration", "standard_uncertainty_zero_drift",
        "combined_standard_uncertainty", "expanded_uncertainty",
    )
    try:
        numbers = {key: _finite(f"{name}.{key}", getattr(value, key)) for key in numeric_names}
    except ValueError as exc:
        raise MotorRotorCorrelationError(f"Dynamometer {name} uncertainty is not finite.") from exc
    if numbers["mean"] < 0.0 or any(
        numbers[key] < 0.0 for key in numeric_names if key != "mean"
    ):
        raise MotorRotorCorrelationError(f"Dynamometer {name} values must be nonnegative.")
    expected_u = math.hypot(
        numbers["standard_uncertainty_type_a"],
        numbers["standard_uncertainty_calibration"],
        numbers["standard_uncertainty_zero_drift"],
    )
    if not _close(numbers["combined_standard_uncertainty"], expected_u):
        raise MotorRotorCorrelationError(f"Dynamometer {name} combined uncertainty is inconsistent.")
    if not _close(numbers["expanded_uncertainty"], coverage_factor * expected_u):
        raise MotorRotorCorrelationError(f"Dynamometer {name} expanded uncertainty is inconsistent.")
    if not _close(numbers["standard_uncertainty_calibration"], calibration_uncertainty):
        raise MotorRotorCorrelationError(
            f"Dynamometer {name} calibration uncertainty is not certificate-bound."
        )
    return value


def _validate_dynamometer(
    evidence: MotorDynamometerEvidence,
    policy: MotorRotorCorrelationPolicy,
) -> Mapping[str, UncertaintyMetric]:
    if not isinstance(evidence, MotorDynamometerEvidence):
        raise MotorRotorCorrelationError("dynamometer must be MotorDynamometerEvidence.")
    try:
        actual_summary_sha256 = canonical_motor_dynamometer_evidence_sha256(evidence)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MotorRotorCorrelationError(
            "Dynamometer summary cannot be canonically identified."
        ) from exc
    if actual_summary_sha256 != evidence.summary_sha256:
        raise MotorRotorCorrelationError("Dynamometer summary digest is mismatched.")
    quantities = tuple(value.quantity for value in evidence.calibrations)
    if len(quantities) != len(set(quantities)) or set(quantities) != set(_DYNAMOMETER_UNITS):
        raise MotorRotorCorrelationError("Dynamometer calibration quantities must exactly match the contract.")
    if set(evidence.metrics) != set(_DYNAMOMETER_UNITS):
        raise MotorRotorCorrelationError("Dynamometer metric keys must exactly match the contract.")
    if not _close(evidence.coverage_factor, policy.coverage_factor):
        raise MotorRotorCorrelationError("Dynamometer and policy coverage factors must match.")
    by_quantity = {value.quantity: value for value in evidence.calibrations}
    for name, unit in _DYNAMOMETER_UNITS.items():
        calibration = by_quantity[name]
        if calibration.unit != unit:
            raise MotorRotorCorrelationError(f"Dynamometer {name} calibration unit is invalid.")
        if not calibration.valid_on(evidence.experiment_date):
            raise MotorRotorCorrelationError(
                f"Dynamometer {name} calibration is invalid on the experiment date."
            )
    metrics = {
        name: _validate_metric(
            name, evidence.metrics[name], unit, evidence.coverage_factor,
            by_quantity[name].standard_uncertainty,
        )
        for name, unit in _DYNAMOMETER_UNITS.items()
    }
    for name in ("rpm", "voltage", "current", "temperature", "pressure"):
        if metrics[name].mean <= 0.0:
            raise MotorRotorCorrelationError(f"Dynamometer {name} mean must be positive.")
    return MappingProxyType(metrics)


def _validate_pr07_point(point: CoupledOperatingPoint, context: MotorRotorRunContext) -> None:
    if not isinstance(point, CoupledOperatingPoint):
        raise MotorRotorCorrelationError("pr07_point must be a CoupledOperatingPoint.")
    try:
        digest = canonical_coupled_operating_point_sha256(point)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MotorRotorCorrelationError("PR-07 point cannot be canonically identified.") from exc
    if digest != context.pr07_case_sha256:
        raise MotorRotorCorrelationError("PR-07 point digest does not match the run context.")
    if point.schema_version != COUPLED_OPERATING_POINT_SCHEMA_VERSION or isinstance(
        point.schema_version, bool
    ):
        raise MotorRotorCorrelationError("PR-07 schema version is invalid.")
    if point.converged is not True or point.feasible is not True or point.infeasible_reason is not None:
        raise MotorRotorCorrelationError("PR-07 point is not a converged feasible equilibrium.")
    if (
        point.qualification != "software_only_pending_measured_correlation"
        or point.physical_correlation_state != "pending"
    ):
        raise MotorRotorCorrelationError("PR-07 qualification state is invalid.")
    try:
        values = {
            name: _finite(name, value)
            for name, value in {
                "rpm": point.rpm,
                "motor rpm": point.motor_state.rpm,
                "aero rpm": point.aero.rpm,
                "throttle": point.throttle,
                "motor torque": point.motor_state.torque_nm,
                "aero torque": point.aero.torque_nm,
                "motor shaft power": point.motor_state.shaft_power_w,
                "aero shaft power": point.aero.shaft_power_w,
                "electrical input power": point.motor_state.electrical_input_power_w,
                "applied voltage": point.motor_state.applied_voltage_v,
                "back emf": point.motor_state.back_emf_v,
                "current": point.motor_state.current_a,
                "torque residual": point.torque_residual_nm,
                "torque tolerance": point.torque_tolerance_nm,
                "voltage residual": point.voltage_residual_v,
                "state voltage residual": point.motor_state.voltage_residual_v,
                "energy residual": point.energy_residual_w,
                "energy tolerance": point.energy_tolerance_w,
                "motor kv": point.motor.kv_rpm_per_v,
                "motor resistance": point.motor.resistance_ohm,
                "motor current limit": point.motor.current_max_a,
                "motor kt kv ratio": point.motor.torque_constant_kv_ratio,
                "system resistance": point.system.resistance_ohm,
                "battery voltage": point.battery.voltage_v,
            }.items()
        }
    except ValueError as exc:
        raise MotorRotorCorrelationError("PR-07 point contains invalid numeric state.") from exc
    if values["rpm"] <= 0.0 or not (
        _close(values["rpm"], values["motor rpm"])
        and _close(values["rpm"], values["aero rpm"])
    ):
        raise MotorRotorCorrelationError("PR-07 RPM identities are inconsistent.")
    if not 0.0 < values["throttle"] <= 1.0:
        raise MotorRotorCorrelationError("PR-07 throttle is outside (0, 1].")
    if values["torque tolerance"] <= 0.0 or values["energy tolerance"] <= 0.0:
        raise MotorRotorCorrelationError("PR-07 residual tolerances must be positive.")
    if any(
        values[name] < 0.0
        for name in (
            "motor torque", "aero torque", "motor shaft power", "aero shaft power",
            "applied voltage", "back emf", "current", "electrical input power",
        )
    ):
        raise MotorRotorCorrelationError("PR-07 motoring electrical/mechanical state must be nonnegative.")
    if (
        values["motor kv"] <= 0.0
        or values["motor resistance"] <= 0.0
        or values["motor current limit"] <= 0.0
        or values["motor kt kv ratio"] <= 0.0
        or values["system resistance"] < 0.0
        or values["battery voltage"] <= 0.0
    ):
        raise MotorRotorCorrelationError("PR-07 motor-system parameter domain is invalid.")
    if values["current"] > values["motor current limit"]:
        raise MotorRotorCorrelationError("PR-07 feasible state exceeds the motor current limit.")
    if not _close(
        values["applied voltage"], values["throttle"] * point.battery.voltage_v
    ):
        raise MotorRotorCorrelationError("PR-07 applied-voltage identity is inconsistent.")
    omega = values["rpm"] * math.pi / 30.0
    expected_back_emf = (values["rpm"] / values["motor kv"]) * (
        1.0 + point.motor.magnetic_lag_tau * omega
    )
    if not math.isfinite(expected_back_emf) or not _close(
        values["back emf"], expected_back_emf
    ):
        raise MotorRotorCorrelationError("PR-07 back-EMF identity is inconsistent.")
    try:
        no_load_current = _finite(
            "PR-07 no-load current", point.motor.get_no_load_current(values["rpm"])
        )
        expected_motor_torque = 30.0 / (
            math.pi * values["motor kv"] * values["motor kt kv ratio"]
        ) * (values["current"] - no_load_current)
    except (ArithmeticError, OverflowError, ValueError) as exc:
        raise MotorRotorCorrelationError("PR-07 motor torque model is invalid.") from exc
    if no_load_current < 0.0 or values["current"] < no_load_current or not _close(
        values["motor torque"], expected_motor_torque
    ):
        raise MotorRotorCorrelationError("PR-07 motor torque identity is inconsistent.")
    if not _close(values["motor shaft power"], values["motor torque"] * omega):
        raise MotorRotorCorrelationError("PR-07 motor shaft power identity is inconsistent.")
    if not _close(values["aero shaft power"], values["aero torque"] * omega):
        raise MotorRotorCorrelationError("PR-07 aerodynamic shaft power identity is inconsistent.")
    if not _close(
        values["electrical input power"], values["applied voltage"] * values["current"]
    ):
        raise MotorRotorCorrelationError("PR-07 electrical input power identity is inconsistent.")
    if not _close(
        values["torque residual"], values["motor torque"] - values["aero torque"]
    ) or abs(values["torque residual"]) > values["torque tolerance"]:
        raise MotorRotorCorrelationError("PR-07 torque residual is invalid.")
    if not _close(
        values["energy residual"], values["motor shaft power"] - values["aero shaft power"]
    ) or abs(values["energy residual"]) > values["energy tolerance"]:
        raise MotorRotorCorrelationError("PR-07 energy residual is invalid.")
    if not _close(values["voltage residual"], values["state voltage residual"]):
        raise MotorRotorCorrelationError("PR-07 voltage residual is invalid.")
    expected_voltage_residual = values["applied voltage"] - point.motor_state.back_emf_v - (
        values["current"]
        * (
            point.motor.get_winding_resistance(values["current"])
            + point.system.resistance_ohm
        )
    )
    if not _close(values["voltage residual"], expected_voltage_residual) or not _close(
        values["voltage residual"], 0.0
    ):
        raise MotorRotorCorrelationError("PR-07 voltage closure is invalid.")
    if point.aero.source_id != context.pr07_source_id:
        raise MotorRotorCorrelationError("PR-07 aerodynamic source identity is mismatched.")


def _variance(terms: tuple[float, float], correlation: float, sign: float) -> float:
    first, second = terms
    if any(not math.isfinite(value) for value in (first, second, correlation, sign)):
        raise MotorRotorCorrelationError("Uncertainty propagation input is not finite.")
    value = first * first + second * second + sign * 2.0 * correlation * first * second
    scale = first * first + second * second + 2.0 * abs(first * second)
    if not math.isfinite(value) or not math.isfinite(scale):
        raise MotorRotorCorrelationError("Uncertainty propagation overflowed.")
    if value < -32 * math.ulp(max(scale, 0.0)):
        raise MotorRotorCorrelationError("Declared covariance produces negative variance.")
    value = max(0.0, value)
    return value


def _product(value_a: float, u_a: float, value_b: float, u_b: float, rho: float) -> tuple[float, float]:
    try:
        value = value_a * value_b
        uncertainty = math.sqrt(_variance((value_b * u_a, value_a * u_b), rho, 1.0))
    except (ArithmeticError, OverflowError, ValueError) as exc:
        raise MotorRotorCorrelationError("Product uncertainty propagation failed.") from exc
    if not math.isfinite(value):
        raise MotorRotorCorrelationError("Derived product is not finite.")
    return value, uncertainty


def _ratio(value_a: float, u_a: float, value_b: float, u_b: float, rho: float) -> tuple[float, float]:
    if value_b <= 0.0:
        raise MotorRotorCorrelationError("Efficiency denominator must be positive.")
    try:
        value = value_a / value_b
        uncertainty = math.sqrt(_variance(
            (u_a / value_b, value_a * u_b / value_b**2), rho, -1.0
        ))
    except (ArithmeticError, OverflowError, ValueError) as exc:
        raise MotorRotorCorrelationError("Ratio uncertainty propagation failed.") from exc
    if not math.isfinite(value):
        raise MotorRotorCorrelationError("Derived ratio is not finite.")
    return value, uncertainty


def _residual_metric(
    quantity: str,
    unit: str,
    reference: float,
    observed: float,
    reference_u: float,
    observed_u: float,
    correlation: float,
    coverage_factor: float,
) -> MotorCorrelationMetric:
    residual = observed - reference
    uncertainty = math.sqrt(_variance((observed_u, reference_u), correlation, -1.0))
    expanded = coverage_factor * uncertainty
    lower = residual - expanded
    upper = residual + expanded
    if any(not math.isfinite(value) for value in (residual, uncertainty, expanded, lower, upper)):
        raise MotorRotorCorrelationError(f"{quantity} residual is not finite.")
    decision = (
        "consistent_with_zero_expanded_interval"
        if lower <= 0.0 <= upper
        else "inconsistent_with_zero_expanded_interval"
    )
    return MotorCorrelationMetric(
        quantity, unit, reference, observed, residual, uncertainty, expanded,
        lower, upper, decision,
    )


def _model_metric(quantity: str, unit: str, reference: float, observed: float) -> MotorCorrelationMetric:
    residual = observed - reference
    if not math.isfinite(residual):
        raise MotorRotorCorrelationError(f"{quantity} model residual is not finite.")
    return MotorCorrelationMetric(
        quantity, unit, reference, observed, residual, None, None, None, None,
        "screening_indeterminate_missing_model_uncertainty",
    )


def _empty_result(
    selected: ValidatedExperimentRunMeasurement,
    context: MotorRotorRunContext,
    policy: MotorRotorCorrelationPolicy,
    state: str,
    failures: tuple[str, ...],
    matches: Mapping[str, bool] | None = None,
    deltas: Mapping[str, float] | None = None,
    dynamometer_identity: Mapping[str, str] | None = None,
) -> MotorRotorCorrelationResult:
    return MotorRotorCorrelationResult(
        selected.stand_id,
        context,
        selected.identity,
        context.pr07_case_sha256,
        MappingProxyType(dict(dynamometer_identity or {})),
        policy,
        MappingProxyType(dict(matches or {})),
        MappingProxyType(dict(deltas or {})),
        failures,
        MappingProxyType({}),
        MappingProxyType({}),
        state,
    )


def assess_motor_rotor_correlation(
    manifest: TestStandManifest,
    decision: ExperimentBundleDecision,
    run_context: MotorRotorRunContext,
    pr07_point: CoupledOperatingPoint,
    dynamometer: MotorDynamometerEvidence | None,
    policy: MotorRotorCorrelationPolicy,
) -> MotorRotorCorrelationResult:
    """Correlate one source-bound run; never promote it to physical qualification."""
    if not isinstance(run_context, MotorRotorRunContext):
        raise MotorRotorCorrelationError("run_context must be MotorRotorRunContext.")
    if not isinstance(policy, MotorRotorCorrelationPolicy):
        raise MotorRotorCorrelationError("policy must be MotorRotorCorrelationPolicy.")
    try:
        selected = validate_experiment_run_measurement(
            manifest, decision, run_context.run_id, run_context.expected_role
        )
    except MeasurementComparisonError as exc:
        raise MotorRotorCorrelationError(f"PR-10 run evidence is invalid: {exc}") from exc
    _validate_pr07_point(pr07_point, run_context)
    if dynamometer is None:
        return _empty_result(
            selected, run_context, policy,
            "blocked_missing_independent_motor_evidence",
            ("missing_independent_dynamometer_evidence",),
        )
    dyno = _validate_dynamometer(dynamometer, policy)
    measured = selected.metrics
    if measured["rpm"].mean <= 0.0:
        raise MotorRotorCorrelationError("PR-10 measured RPM must be positive.")

    identity_matches = {
        "design_id": selected.identity["design_id"] == run_context.design_id,
        "pr07_design_id": run_context.pr07_design_id == run_context.design_id,
        "motor_id": dynamometer.motor_id == run_context.motor_id,
        "motor_serial": dynamometer.motor_serial == run_context.motor_serial,
        "esc_id": dynamometer.esc_id == run_context.esc_id,
        "experiment_date": dynamometer.experiment_date == selected.identity["experiment_date"],
        "pr10_power_location": (
            run_context.dc_power_measurement_location == MOTOR_TERMINAL_DC_INPUT
        ),
        "pr07_power_location": run_context.pr07_dc_power_location == MOTOR_TERMINAL_DC_INPUT,
        "dynamometer_power_location": (
            dynamometer.dc_power_measurement_location == MOTOR_TERMINAL_DC_INPUT
        ),
    }
    rpm_reference = measured["rpm"].mean
    deltas = {
        "diameter": abs(
            run_context.pr07_open_diameter_m - run_context.run_open_diameter_m
        ),
        "forward_speed": abs(
            run_context.pr07_forward_speed_m_s - run_context.run_forward_speed_m_s
        ),
        "pr07_rpm": abs(pr07_point.rpm - rpm_reference) / rpm_reference,
        "dynamometer_rpm": abs(dyno["rpm"].mean - rpm_reference) / rpm_reference,
        "pr07_voltage": abs(
            pr07_point.motor_state.applied_voltage_v - measured["voltage"].mean
        ),
        "pr07_current": abs(
            pr07_point.motor_state.current_a - measured["current"].mean
        ),
        "voltage": abs(dyno["voltage"].mean - measured["voltage"].mean),
        "current": abs(dyno["current"].mean - measured["current"].mean),
        "pr07_temperature": abs(run_context.pr07_temperature_k - measured["temperature"].mean),
        "pr07_pressure": abs(run_context.pr07_pressure_pa - measured["pressure"].mean),
        "dynamometer_temperature": abs(dyno["temperature"].mean - measured["temperature"].mean),
        "dynamometer_pressure": abs(dyno["pressure"].mean - measured["pressure"].mean),
    }
    if any(not math.isfinite(value) for value in deltas.values()):
        raise MotorRotorCorrelationError("Motor/rotor condition delta is not finite.")
    matches = {
        **identity_matches,
        "diameter": deltas["diameter"] <= policy.maximum_diameter_delta_m,
        "forward_speed": (
            deltas["forward_speed"] <= policy.maximum_forward_speed_delta_m_s
        ),
        "pr07_rpm": deltas["pr07_rpm"] <= policy.maximum_rpm_relative_delta,
        "dynamometer_rpm": deltas["dynamometer_rpm"] <= policy.maximum_rpm_relative_delta,
        "pr07_voltage": deltas["pr07_voltage"] <= policy.maximum_voltage_delta_v,
        "pr07_current": deltas["pr07_current"] <= policy.maximum_current_delta_a,
        "voltage": deltas["voltage"] <= policy.maximum_voltage_delta_v,
        "current": deltas["current"] <= policy.maximum_current_delta_a,
        "pr07_temperature": deltas["pr07_temperature"] <= policy.maximum_temperature_delta_k,
        "pr07_pressure": deltas["pr07_pressure"] <= policy.maximum_pressure_delta_pa,
        "dynamometer_temperature": (
            deltas["dynamometer_temperature"] <= policy.maximum_temperature_delta_k
        ),
        "dynamometer_pressure": (
            deltas["dynamometer_pressure"] <= policy.maximum_pressure_delta_pa
        ),
    }
    failures = tuple(f"mismatch:{name}" for name, passed in matches.items() if not passed)
    calibration_identity = {
        f"calibration_{calibration.quantity}_{field}": getattr(calibration, field)
        for calibration in dynamometer.calibrations
        for field in ("sensor_id", "certificate_id", "certificate_sha256")
    }
    dyno_identity = MappingProxyType({
        "evidence_id": dynamometer.evidence_id,
        "raw_data_sha256": dynamometer.raw_data_sha256,
        "summary_sha256": dynamometer.summary_sha256,
        "experiment_date": dynamometer.experiment_date,
        "motor_id": dynamometer.motor_id,
        "motor_serial": dynamometer.motor_serial,
        "esc_id": dynamometer.esc_id,
        "source": dynamometer.source,
        "classification": dynamometer.classification,
        **calibration_identity,
    })
    if failures:
        return _empty_result(
            selected, run_context, policy,
            "blocked_unmatched_motor_rotor_conditions", failures,
            matches, deltas, dyno_identity,
        )

    omega_factor = math.pi / 30.0
    dyno_omega = dyno["rpm"].mean * omega_factor
    dyno_omega_u = dyno["rpm"].combined_standard_uncertainty * omega_factor
    measured_omega = measured["rpm"].mean * omega_factor
    measured_omega_u = measured["rpm"].combined_standard_uncertainty * omega_factor
    dyno_dc_power, dyno_dc_power_u = _product(
        dyno["voltage"].mean, dyno["voltage"].combined_standard_uncertainty,
        dyno["current"].mean, dyno["current"].combined_standard_uncertainty,
        policy.dyno_voltage_current_correlation,
    )
    dyno_shaft_power, dyno_shaft_power_u = _product(
        dyno["torque"].mean, dyno["torque"].combined_standard_uncertainty,
        dyno_omega, dyno_omega_u, policy.dyno_torque_rpm_correlation,
    )
    measured_shaft_power, measured_shaft_power_u = _product(
        measured["torque"].mean, measured["torque"].combined_standard_uncertainty,
        measured_omega, measured_omega_u, policy.measured_torque_rpm_correlation,
    )
    efficiency, efficiency_u = _ratio(
        dyno_shaft_power, dyno_shaft_power_u, dyno_dc_power, dyno_dc_power_u,
        policy.dyno_shaft_dc_power_correlation,
    )
    if not 0.0 <= efficiency <= 1.0:
        raise MotorRotorCorrelationError("Derived dynamometer motor efficiency is outside [0, 1].")
    derived_values = {
        "dynamometer_dc_input_power_w": dyno_dc_power,
        "dynamometer_dc_input_power_standard_uncertainty_w": dyno_dc_power_u,
        "dynamometer_dc_input_power_expanded_uncertainty_w": (
            policy.coverage_factor * dyno_dc_power_u
        ),
        "dynamometer_shaft_power_w": dyno_shaft_power,
        "dynamometer_shaft_power_standard_uncertainty_w": dyno_shaft_power_u,
        "dynamometer_shaft_power_expanded_uncertainty_w": (
            policy.coverage_factor * dyno_shaft_power_u
        ),
        "dynamometer_efficiency": efficiency,
        "dynamometer_efficiency_standard_uncertainty": efficiency_u,
        "dynamometer_efficiency_expanded_uncertainty": (
            policy.coverage_factor * efficiency_u
        ),
        "dynamometer_efficiency_interval_lower": (
            efficiency - policy.coverage_factor * efficiency_u
        ),
        "dynamometer_efficiency_interval_upper": (
            efficiency + policy.coverage_factor * efficiency_u
        ),
        "measured_rotor_shaft_power_w": measured_shaft_power,
        "measured_rotor_shaft_power_standard_uncertainty_w": measured_shaft_power_u,
        "measured_rotor_shaft_power_expanded_uncertainty_w": (
            policy.coverage_factor * measured_shaft_power_u
        ),
    }
    if any(not math.isfinite(value) for value in derived_values.values()):
        raise MotorRotorCorrelationError("Derived motor quantities are not finite.")
    derived = MappingProxyType(derived_values)
    metrics = MappingProxyType({
        "dynamometer_vs_rotor_torque": _residual_metric(
            "dynamometer_vs_rotor_torque", "N*m",
            measured["torque"].mean, dyno["torque"].mean,
            measured["torque"].combined_standard_uncertainty,
            dyno["torque"].combined_standard_uncertainty,
            policy.dyno_measured_torque_correlation, policy.coverage_factor,
        ),
        "dynamometer_vs_rotor_shaft_power": _residual_metric(
            "dynamometer_vs_rotor_shaft_power", "W",
            measured_shaft_power, dyno_shaft_power,
            measured_shaft_power_u, dyno_shaft_power_u,
            policy.dyno_measured_shaft_power_correlation, policy.coverage_factor,
        ),
        "pr07_vs_experiment_rpm": _model_metric(
            "pr07_vs_experiment_rpm", "rpm", measured["rpm"].mean, pr07_point.rpm
        ),
        "pr07_vs_experiment_dc_power": _model_metric(
            "pr07_vs_experiment_dc_power", "W",
            measured["electrical_power"].mean,
            pr07_point.motor_state.electrical_input_power_w,
        ),
        "pr07_vs_experiment_rotor_torque": _model_metric(
            "pr07_vs_experiment_rotor_torque", "N*m",
            measured["torque"].mean, pr07_point.aero.torque_nm,
        ),
    })
    return MotorRotorCorrelationResult(
        selected.stand_id,
        run_context,
        selected.identity,
        run_context.pr07_case_sha256,
        dyno_identity,
        policy,
        MappingProxyType(matches),
        MappingProxyType(deltas),
        (),
        derived,
        metrics,
        "screening_motor_rotor_correlation_complete_physical_evidence_pending",
    )
