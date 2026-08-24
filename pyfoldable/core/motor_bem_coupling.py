"""Fail-closed motor/rotor torque equilibrium for PR-07.

The aerodynamic boundary is a callable so the numerical contract can be tested
without claiming that an unqualified polar family is physical evidence.  A caller
may wrap :func:`solve_bem_rotor` or :func:`solve_foldable_bem_rotor` and return an
``AeroLoadSample`` at every requested RPM.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from scipy.optimize import root_scalar

from pythrust.propulsion.models import BatterySpec, MotorSpec, SystemSpec

from .models import OperatingCondition


COUPLED_OPERATING_POINT_SCHEMA_VERSION = 1


class CoupledEquilibriumError(RuntimeError):
    """Base class for a motor/rotor equilibrium that cannot be accepted."""


class NoEquilibriumError(CoupledEquilibriumError):
    """Raised when the declared RPM interval contains no torque equilibrium."""


class AmbiguousEquilibriumError(CoupledEquilibriumError):
    """Raised when more than one distinct equilibrium is present."""


class InvalidAeroLoadError(CoupledEquilibriumError):
    """Raised when an aerodynamic callback violates its load contract."""


def _real_finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


@dataclass(frozen=True)
class AeroLoadSample:
    """One rotor load evaluation at a candidate shaft speed."""

    rpm: float
    thrust_n: float
    torque_nm: float
    shaft_power_w: float
    source_id: str
    qualification: str

    def __post_init__(self) -> None:
        try:
            for name in ("rpm", "thrust_n", "torque_nm", "shaft_power_w"):
                _real_finite(name, getattr(self, name))
        except (TypeError, ValueError) as exc:
            raise InvalidAeroLoadError(str(exc)) from exc
        if self.rpm < 0.0:
            raise InvalidAeroLoadError("rpm must not be negative.")
        if self.torque_nm < 0.0 or self.shaft_power_w < 0.0:
            raise InvalidAeroLoadError(
                "Propulsive torque and shaft power must not be negative."
            )
        if not self.source_id or not self.qualification:
            raise InvalidAeroLoadError(
                "source_id and qualification must not be empty."
            )
        expected_power = self.torque_nm * self.rpm * math.pi / 30.0
        tolerance = max(1.0e-8, abs(expected_power) * 1.0e-8)
        if abs(self.shaft_power_w - expected_power) > tolerance:
            raise InvalidAeroLoadError(
                "shaft_power_w must equal torque_nm * angular speed."
            )

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "rpm": self.rpm,
            "thrust_n": self.thrust_n,
            "torque_nm": self.torque_nm,
            "shaft_power_w": self.shaft_power_w,
            "source_id": self.source_id,
            "qualification": self.qualification,
        }


@dataclass(frozen=True)
class CoupledSolverSettings:
    """Numerical domain and acceptance tolerances for the common root."""

    rpm_min: float = 100.0
    rpm_max: float | None = None
    scan_points: int = 129
    rpm_tolerance: float = 1.0e-6
    torque_absolute_tolerance_nm: float = 1.0e-8
    torque_relative_tolerance: float = 1.0e-7
    energy_relative_tolerance: float = 1.0e-7
    max_iterations: int = 100

    def __post_init__(self) -> None:
        _real_finite("rpm_min", self.rpm_min)
        if self.rpm_max is not None:
            _real_finite("rpm_max", self.rpm_max)
            if self.rpm_max <= self.rpm_min:
                raise ValueError("rpm_max must be greater than rpm_min.")
        if self.rpm_min < 0.0:
            raise ValueError("rpm_min must not be negative.")
        if not isinstance(self.scan_points, int) or isinstance(self.scan_points, bool):
            raise TypeError("scan_points must be an integer.")
        if self.scan_points < 25:
            raise ValueError("scan_points must be at least 25.")
        if not isinstance(self.max_iterations, int) or self.max_iterations < 1:
            raise ValueError("max_iterations must be a positive integer.")
        for name in (
            "rpm_tolerance",
            "torque_absolute_tolerance_nm",
            "torque_relative_tolerance",
            "energy_relative_tolerance",
        ):
            _real_finite(name, getattr(self, name))
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be greater than zero.")

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "rpm_min": self.rpm_min,
            "rpm_max": self.rpm_max,
            "scan_points": self.scan_points,
            "rpm_tolerance": self.rpm_tolerance,
            "torque_absolute_tolerance_nm": self.torque_absolute_tolerance_nm,
            "torque_relative_tolerance": self.torque_relative_tolerance,
            "energy_relative_tolerance": self.energy_relative_tolerance,
            "max_iterations": self.max_iterations,
            "root_scan": "global_linear_bracket_v1",
        }


@dataclass(frozen=True)
class MotorState:
    rpm: float
    applied_voltage_v: float
    back_emf_v: float
    current_a: float
    torque_nm: float
    shaft_power_w: float
    electrical_input_power_w: float
    winding_loss_w: float
    line_loss_w: float
    voltage_residual_v: float

    def as_mapping(self) -> Mapping[str, float]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class CoupledOperatingPoint:
    schema_version: int
    rpm: float
    throttle: float
    converged: bool
    feasible: bool
    infeasible_reason: str | None
    motor: MotorSpec
    battery: BatterySpec
    system: SystemSpec
    motor_state: MotorState
    aero: AeroLoadSample
    settings: CoupledSolverSettings
    torque_residual_nm: float
    torque_tolerance_nm: float
    voltage_residual_v: float
    energy_residual_w: float
    energy_tolerance_w: float
    initial_guess_rpm: float | None
    qualification: str = "software_only_pending_measured_correlation"
    physical_correlation_state: str = "pending"

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "schema_version": self.schema_version,
            "rpm": self.rpm,
            "throttle": self.throttle,
            "converged": self.converged,
            "feasible": self.feasible,
            "infeasible_reason": self.infeasible_reason,
            "motor": dict(self.motor.__dict__),
            "battery": dict(self.battery.__dict__),
            "system": dict(self.system.__dict__),
            "motor_state": dict(self.motor_state.as_mapping()),
            "aero": dict(self.aero.as_mapping()),
            "settings": dict(self.settings.as_mapping()),
            "torque_residual_nm": self.torque_residual_nm,
            "torque_tolerance_nm": self.torque_tolerance_nm,
            "voltage_residual_v": self.voltage_residual_v,
            "energy_residual_w": self.energy_residual_w,
            "energy_tolerance_w": self.energy_tolerance_w,
            "initial_guess_rpm": self.initial_guess_rpm,
            "qualification": self.qualification,
            "physical_correlation_state": self.physical_correlation_state,
        }


AeroLoadFunction = Callable[[float], AeroLoadSample]
RotorSolverFunction = Callable[[OperatingCondition], Any]


def make_bem_aero_load_callback(
    rotor_solver: RotorSolverFunction,
    *,
    forward_speed_m_s: float,
    air_density_kg_m3: float,
    dynamic_viscosity_pa_s: float,
    temperature_k: float,
    pressure_pa: float,
    source_id: str,
    qualification: str,
) -> AeroLoadFunction:
    """Adapt a fixed or foldable BEM solver to the PR-07 RPM callback.

    ``rotor_solver`` receives a freshly constructed ``OperatingCondition``.  It
    may return ``BEMRotorResult`` directly or a ``FoldableBEMRotorResult`` with a
    ``rotor_result`` member.
    """
    if not callable(rotor_solver):
        raise TypeError("rotor_solver must be callable.")
    for name, value in (
        ("forward_speed_m_s", forward_speed_m_s),
        ("air_density_kg_m3", air_density_kg_m3),
        ("dynamic_viscosity_pa_s", dynamic_viscosity_pa_s),
        ("temperature_k", temperature_k),
        ("pressure_pa", pressure_pa),
    ):
        _real_finite(name, value)
    if air_density_kg_m3 <= 0.0 or dynamic_viscosity_pa_s <= 0.0:
        raise ValueError("Density and dynamic viscosity must be greater than zero.")
    if temperature_k <= 0.0 or pressure_pa <= 0.0:
        raise ValueError("Temperature and pressure must be greater than zero.")
    if not source_id or not qualification:
        raise ValueError("source_id and qualification must not be empty.")

    def evaluate(rpm: float) -> AeroLoadSample:
        rpm_value = _real_finite("rpm", rpm)
        condition = OperatingCondition(
            id=f"pr07-{rpm_value:.9f}-rpm",
            angular_speed_rad_s=rpm_value * math.pi / 30.0,
            forward_speed_m_s=forward_speed_m_s,
            air_density_kg_m3=air_density_kg_m3,
            dynamic_viscosity_pa_s=dynamic_viscosity_pa_s,
            temperature_k=temperature_k,
            pressure_pa=pressure_pa,
        )
        result = rotor_solver(condition)
        rotor_result = getattr(result, "rotor_result", result)
        try:
            return AeroLoadSample(
                rpm=rpm_value,
                thrust_n=rotor_result.thrust_n,
                torque_nm=rotor_result.torque_nm,
                shaft_power_w=rotor_result.shaft_power_w,
                source_id=source_id,
                qualification=qualification,
            )
        except AttributeError as exc:
            raise InvalidAeroLoadError(
                "BEM result must expose thrust_n, torque_nm and shaft_power_w."
            ) from exc

    return evaluate


@dataclass(frozen=True)
class CoupledMultistartCase:
    """Auditable initial guesses and resulting roots for one throttle."""

    throttle: float
    initial_guesses_rpm: tuple[float, ...]
    converged_roots_rpm: tuple[float, ...]

    def __post_init__(self) -> None:
        _real_finite("throttle", self.throttle)
        if not 0.0 < self.throttle <= 1.0:
            raise ValueError("throttle must satisfy 0 < throttle <= 1.")
        if len(self.initial_guesses_rpm) < 2:
            raise ValueError("At least two initial guesses are required.")
        if len(self.initial_guesses_rpm) != len(self.converged_roots_rpm):
            raise ValueError("Every initial guess must have one converged root.")
        if len(set(self.initial_guesses_rpm)) != len(self.initial_guesses_rpm):
            raise ValueError("Initial guesses must be unique.")
        for guess in self.initial_guesses_rpm:
            _real_finite("initial_guesses_rpm", guess)
        for root in self.converged_roots_rpm:
            _real_finite("converged_roots_rpm", root)

    @property
    def spread_rpm(self) -> float:
        return max(self.converged_roots_rpm) - min(self.converged_roots_rpm)

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "throttle": self.throttle,
            "initial_guesses_rpm": list(self.initial_guesses_rpm),
            "converged_roots_rpm": list(self.converged_roots_rpm),
            "spread_rpm": self.spread_rpm,
        }


@dataclass(frozen=True)
class CoupledEquilibriumEvidence:
    """Machine-readable PR-07 numerical gate over declared throttle cases."""

    evidence_id: str
    cases: tuple[CoupledOperatingPoint, ...]
    multistart_cases: tuple[CoupledMultistartCase, ...]

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise ValueError("evidence_id must not be empty.")
        if not self.cases or not all(
            isinstance(case, CoupledOperatingPoint) for case in self.cases
        ):
            raise TypeError("cases must contain CoupledOperatingPoint values.")
        throttles = tuple(case.throttle for case in self.cases)
        if len(set(throttles)) != len(throttles):
            raise ValueError("Evidence throttle cases must be unique.")
        if not self.multistart_cases or not all(
            isinstance(case, CoupledMultistartCase)
            for case in self.multistart_cases
        ):
            raise TypeError(
                "multistart_cases must contain CoupledMultistartCase values."
            )
        multistart_throttles = tuple(
            case.throttle for case in self.multistart_cases
        )
        if len(set(multistart_throttles)) != len(multistart_throttles):
            raise ValueError("Multistart throttle cases must be unique.")
        if set(throttles) != set(multistart_throttles):
            raise ValueError("Evidence and multistart throttle cases must match.")

    @property
    def maximum_multistart_spread_rpm(self) -> float:
        return max(case.spread_rpm for case in self.multistart_cases)

    @property
    def numerical_gate_passed(self) -> bool:
        return (
            all(
                case.converged
                and case.feasible
                and abs(case.torque_residual_nm) <= case.torque_tolerance_nm
                and abs(case.energy_residual_w) <= case.energy_tolerance_w
                for case in self.cases
            )
            and self.maximum_multistart_spread_rpm
            <= min(case.settings.rpm_tolerance for case in self.cases)
            and all(
                max(
                    abs(root - next(
                        case.rpm
                        for case in self.cases
                        if case.throttle == multistart.throttle
                    ))
                    for root in multistart.converged_roots_rpm
                )
                <= next(
                    case.settings.rpm_tolerance
                    for case in self.cases
                    if case.throttle == multistart.throttle
                )
                for multistart in self.multistart_cases
            )
        )

    @property
    def physical_gate_passed(self) -> bool:
        return False

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "schema_version": COUPLED_OPERATING_POINT_SCHEMA_VERSION,
            "evidence_id": self.evidence_id,
            "numerical_gate": "passed" if self.numerical_gate_passed else "failed",
            "physical_gate": "pending_measured_correlation",
            "maximum_multistart_spread_rpm": self.maximum_multistart_spread_rpm,
            "multistart_cases": [
                dict(case.as_mapping()) for case in self.multistart_cases
            ],
            "cases": [dict(case.as_mapping()) for case in self.cases],
        }


def _motor_state(
    motor: MotorSpec,
    battery: BatterySpec,
    system: SystemSpec,
    throttle: float,
    rpm: float,
) -> MotorState:
    applied = throttle * battery.voltage_v
    omega = rpm * math.pi / 30.0
    back_emf = (rpm / motor.kv_rpm_per_v) * (
        1.0 + motor.magnetic_lag_tau * omega
    )
    voltage_head = applied - back_emf
    if voltage_head <= 0.0:
        current = 0.0
    elif motor.resistance_quadratic <= 0.0:
        current = voltage_head / (motor.resistance_ohm + system.resistance_ohm)
    else:
        def voltage_equation(current_a: float) -> float:
            resistance = motor.get_winding_resistance(current_a)
            return current_a * (resistance + system.resistance_ohm) - voltage_head

        upper = max(1.0, voltage_head / max(motor.resistance_ohm, 1.0e-12))
        current = float(root_scalar(
            voltage_equation,
            bracket=(0.0, upper),
            method="brentq",
        ).root)
    winding_resistance = motor.get_winding_resistance(current)
    no_load_current = motor.get_no_load_current(rpm)
    kt = 30.0 / (
        math.pi * motor.kv_rpm_per_v * motor.torque_constant_kv_ratio
    )
    torque = kt * (current - no_load_current)
    shaft_power = torque * omega
    winding_loss = current * current * winding_resistance
    line_loss = current * current * system.resistance_ohm
    voltage_residual = applied - back_emf - current * (
        winding_resistance + system.resistance_ohm
    )
    return MotorState(
        rpm=rpm,
        applied_voltage_v=applied,
        back_emf_v=back_emf,
        current_a=current,
        torque_nm=torque,
        shaft_power_w=shaft_power,
        electrical_input_power_w=applied * current,
        winding_loss_w=winding_loss,
        line_loss_w=line_loss,
        voltage_residual_v=voltage_residual,
    )


def solve_coupled_operating_point(
    *,
    motor: MotorSpec,
    battery: BatterySpec,
    system: SystemSpec,
    throttle: float,
    aero_load: AeroLoadFunction,
    settings: CoupledSolverSettings | None = None,
    initial_guess_rpm: float | None = None,
) -> CoupledOperatingPoint:
    """Solve the unique common root of motor and aerodynamic torque curves."""
    if not isinstance(motor, MotorSpec):
        raise TypeError("motor must be a MotorSpec.")
    if not isinstance(battery, BatterySpec):
        raise TypeError("battery must be a BatterySpec.")
    if not isinstance(system, SystemSpec):
        raise TypeError("system must be a SystemSpec.")
    for name, value in (
        ("motor.kv_rpm_per_v", motor.kv_rpm_per_v),
        ("motor.resistance_ohm", motor.resistance_ohm),
        ("motor.no_load_current_a", motor.no_load_current_a),
        ("motor.current_max_a", motor.current_max_a),
        ("motor.torque_constant_kv_ratio", motor.torque_constant_kv_ratio),
        ("battery.voltage_v", battery.voltage_v),
        ("battery.discharge_efficiency", battery.discharge_efficiency),
        ("system.resistance_ohm", system.resistance_ohm),
    ):
        _real_finite(name, value)
    if motor.kv_rpm_per_v <= 0.0 or motor.resistance_ohm <= 0.0:
        raise ValueError("Motor Kv and resistance must be greater than zero.")
    if motor.no_load_current_a < 0.0 or motor.current_max_a <= 0.0:
        raise ValueError("Motor currents violate the declared physical domain.")
    if motor.torque_constant_kv_ratio <= 0.0:
        raise ValueError("motor.torque_constant_kv_ratio must be greater than zero.")
    if battery.voltage_v <= 0.0 or not 0.0 < battery.discharge_efficiency <= 1.0:
        raise ValueError("Battery voltage/efficiency violate the physical domain.")
    if system.resistance_ohm < 0.0:
        raise ValueError("System resistance must not be negative.")
    throttle_value = _real_finite("throttle", throttle)
    if throttle_value <= 0.0 or throttle_value > 1.0:
        raise ValueError("throttle must satisfy 0 < throttle <= 1.")
    if not callable(aero_load):
        raise TypeError("aero_load must be callable.")
    controls = settings or CoupledSolverSettings()
    if not isinstance(controls, CoupledSolverSettings):
        raise TypeError("settings must be CoupledSolverSettings.")
    if initial_guess_rpm is not None:
        _real_finite("initial_guess_rpm", initial_guess_rpm)

    rpm_max = controls.rpm_max
    if rpm_max is None:
        rpm_max = motor.kv_rpm_per_v * battery.voltage_v * throttle_value
    if rpm_max <= controls.rpm_min:
        raise NoEquilibriumError("The electrical no-load limit is below rpm_min.")
    if initial_guess_rpm is not None and not (
        controls.rpm_min <= initial_guess_rpm <= rpm_max
    ):
        raise ValueError("initial_guess_rpm must lie inside the RPM search interval.")

    cache: dict[float, tuple[MotorState, AeroLoadSample, float]] = {}

    def evaluate(rpm: float) -> tuple[MotorState, AeroLoadSample, float]:
        key = float(rpm)
        if key in cache:
            return cache[key]
        motor_value = _motor_state(motor, battery, system, throttle_value, key)
        try:
            aero_value = aero_load(key)
        except InvalidAeroLoadError:
            raise
        except Exception as exc:
            raise InvalidAeroLoadError(
                f"Aerodynamic callback failed at {key:.9g} rpm: {exc}"
            ) from exc
        if not isinstance(aero_value, AeroLoadSample):
            raise InvalidAeroLoadError(
                "Aerodynamic callback must return AeroLoadSample."
            )
        if abs(aero_value.rpm - key) > max(1.0e-9, abs(key) * 1.0e-12):
            raise InvalidAeroLoadError(
                "Aerodynamic sample RPM does not match the requested RPM."
            )
        residual = motor_value.torque_nm - aero_value.torque_nm
        if not math.isfinite(residual):
            raise InvalidAeroLoadError("Torque residual must be finite.")
        cache[key] = (motor_value, aero_value, residual)
        return cache[key]

    step = (rpm_max - controls.rpm_min) / (controls.scan_points - 1)
    scan_rpms = [controls.rpm_min + index * step for index in range(controls.scan_points)]
    scan_values = [evaluate(rpm)[2] for rpm in scan_rpms]
    roots: list[float] = []
    brackets: list[tuple[float, float]] = []
    for index, value in enumerate(scan_values):
        if abs(value) <= controls.torque_absolute_tolerance_nm:
            roots.append(scan_rpms[index])
        if index == 0:
            continue
        previous = scan_values[index - 1]
        if previous * value < 0.0:
            brackets.append((scan_rpms[index - 1], scan_rpms[index]))
    if initial_guess_rpm is not None:
        brackets.sort(
            key=lambda bracket: abs((bracket[0] + bracket[1]) / 2.0 - initial_guess_rpm)
        )
    for bracket in brackets:
        solved = root_scalar(
            lambda rpm: evaluate(rpm)[2],
            bracket=bracket,
            method="brentq",
            xtol=controls.rpm_tolerance,
            rtol=1.0e-12,
            maxiter=controls.max_iterations,
        )
        if not solved.converged:
            raise NoEquilibriumError("Torque root did not converge.")
        roots.append(float(solved.root))

    roots.sort()
    unique_roots: list[float] = []
    for root in roots:
        if not unique_roots or abs(root - unique_roots[-1]) > controls.rpm_tolerance:
            unique_roots.append(root)
    if not unique_roots:
        raise NoEquilibriumError(
            "No torque equilibrium exists in the declared RPM interval."
        )
    if len(unique_roots) != 1:
        raise AmbiguousEquilibriumError(
            f"Expected one equilibrium, found {len(unique_roots)}."
        )

    rpm = unique_roots[0]
    motor_value, aero_value, torque_residual = evaluate(rpm)
    torque_tolerance = max(
        controls.torque_absolute_tolerance_nm,
        abs(aero_value.torque_nm) * controls.torque_relative_tolerance,
    )
    energy_residual = motor_value.shaft_power_w - aero_value.shaft_power_w
    energy_tolerance = max(
        torque_tolerance * rpm * math.pi / 30.0,
        abs(aero_value.shaft_power_w) * controls.energy_relative_tolerance,
    )
    if abs(torque_residual) > torque_tolerance:
        raise NoEquilibriumError("Converged root violates the torque residual gate.")
    if abs(energy_residual) > energy_tolerance:
        raise NoEquilibriumError("Converged root violates the shaft-energy gate.")

    reason: str | None = None
    if motor_value.current_a > motor.current_max_a:
        reason = "current_limit"
    elif motor_value.current_a < motor.get_no_load_current(rpm):
        reason = "non_motoring_current"
    feasible = reason is None
    return CoupledOperatingPoint(
        schema_version=COUPLED_OPERATING_POINT_SCHEMA_VERSION,
        rpm=rpm,
        throttle=throttle_value,
        converged=True,
        feasible=feasible,
        infeasible_reason=reason,
        motor=motor,
        battery=battery,
        system=system,
        motor_state=motor_value,
        aero=aero_value,
        settings=controls,
        torque_residual_nm=torque_residual,
        torque_tolerance_nm=torque_tolerance,
        voltage_residual_v=motor_value.voltage_residual_v,
        energy_residual_w=energy_residual,
        energy_tolerance_w=energy_tolerance,
        initial_guess_rpm=initial_guess_rpm,
    )
