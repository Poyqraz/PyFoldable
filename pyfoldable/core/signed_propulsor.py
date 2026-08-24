"""Sign-safe operating modes for propulsors and passive tip-mounted rotors."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal, Mapping


PropulsorMode = Literal[
    "propulsive",
    "powered_drag",
    "energy_extracting_drag",
    "energy_extracting_thrust",
    "near_neutral",
]


class SignedPropulsorError(ValueError):
    """Raised when a signed propulsor assessment receives invalid inputs."""


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SignedPropulsorError(f"{name} must be numeric and not boolean.")
    result = float(value)
    if not math.isfinite(result):
        raise SignedPropulsorError(f"{name} must be finite.")
    return result


@dataclass(frozen=True)
class TipMountedInflow:
    """Vector components of the screening-only jointed-tip inflow relation."""

    forward_component_m_s: float
    tangential_component_m_s: float
    magnitude_m_s: float
    evidence_class: str = "methodology_only_tip_jointed_system"

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "forward_component_m_s": self.forward_component_m_s,
            "tangential_component_m_s": self.tangential_component_m_s,
            "magnitude_m_s": self.magnitude_m_s,
            "evidence_class": self.evidence_class,
        }


def tip_mounted_effective_inflow(
    forward_speed_m_s: float,
    main_angular_speed_rad_s: float,
    main_tip_radius_m: float,
) -> TipMountedInflow:
    """Evaluate ``hypot(V_inf, omega_main * R_main)`` without claiming validation."""
    forward = _finite("forward_speed_m_s", forward_speed_m_s)
    angular_speed = _finite("main_angular_speed_rad_s", main_angular_speed_rad_s)
    radius = _finite("main_tip_radius_m", main_tip_radius_m)
    if forward < 0.0 or angular_speed < 0.0 or radius <= 0.0:
        raise SignedPropulsorError(
            "forward speed/angular speed must be nonnegative and radius positive."
        )
    tangential = angular_speed * radius
    return TipMountedInflow(forward, tangential, math.hypot(forward, tangential))


@dataclass(frozen=True)
class SignedPropulsorAssessment:
    """Operating-mode decision with fail-closed propulsive efficiency."""

    thrust_n: float
    power_w: float
    forward_speed_m_s: float
    mode: PropulsorMode
    propulsive_efficiency: float | None
    raw_thrust_power_ratio: float | None
    warnings: tuple[str, ...]

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "thrust_n": self.thrust_n,
            "power_w": self.power_w,
            "forward_speed_m_s": self.forward_speed_m_s,
            "mode": self.mode,
            "propulsive_efficiency": self.propulsive_efficiency,
            "raw_thrust_power_ratio": self.raw_thrust_power_ratio,
            "warnings": list(self.warnings),
        }


def assess_signed_propulsor_state(
    thrust_n: float,
    power_w: float,
    forward_speed_m_s: float,
    *,
    zero_tolerance: float = 1.0e-9,
    efficiency_tolerance: float = 1.0e-9,
) -> SignedPropulsorAssessment:
    """Classify signed thrust/power and expose efficiency only when meaningful."""
    thrust = _finite("thrust_n", thrust_n)
    power = _finite("power_w", power_w)
    speed = _finite("forward_speed_m_s", forward_speed_m_s)
    zero = _finite("zero_tolerance", zero_tolerance)
    efficiency_bound = _finite("efficiency_tolerance", efficiency_tolerance)
    if speed < 0.0 or zero < 0.0 or efficiency_bound < 0.0:
        raise SignedPropulsorError(
            "forward speed and tolerances must be nonnegative."
        )

    if abs(thrust) <= zero or abs(power) <= zero:
        mode: PropulsorMode = "near_neutral"
    elif thrust > 0.0 and power > 0.0:
        mode = "propulsive"
    elif thrust < 0.0 and power > 0.0:
        mode = "powered_drag"
    elif thrust < 0.0 and power < 0.0:
        mode = "energy_extracting_drag"
    else:
        mode = "energy_extracting_thrust"

    raw_ratio = None if abs(power) <= zero else thrust * speed / power
    warnings: list[str] = []
    efficiency: float | None = None
    if mode == "propulsive":
        if speed <= zero:
            warnings.append("static_efficiency_undefined")
        elif raw_ratio is None or raw_ratio < 0.0 or raw_ratio > 1.0 + efficiency_bound:
            warnings.append("propulsive_efficiency_out_of_bounds")
        else:
            efficiency = raw_ratio
    else:
        warnings.append("propulsive_efficiency_not_applicable")

    return SignedPropulsorAssessment(
        thrust,
        power,
        speed,
        mode,
        efficiency,
        raw_ratio,
        tuple(warnings),
    )
