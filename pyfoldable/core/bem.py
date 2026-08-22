"""Fail-closed local blade-element/momentum annulus solution.

This module implements the hover-capable flow-angle parameterization from QPROP.
It deliberately stops at one annulus: radial geometry interpolation, root loss, and
whole-rotor integration belong to the next development increment.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from scipy.optimize import brentq

from .models import BladeGeometry, BladeStation, OperatingCondition
from .polar import PolarBoundsPolicy, PolarFamily, PolarQueryResult


BEM_ANNULUS_SCHEMA_VERSION = 1
_AIR_GAMMA = 1.4
_AIR_GAS_CONSTANT_J_KG_K = 287.05


class BEMAnnulusError(ValueError):
    """Raised when an annulus request lies outside the supported physical domain."""


class BEMConvergenceError(RuntimeError):
    """Raised when no supported propulsive annulus solution can be bracketed."""


@dataclass(frozen=True)
class BEMAnnulusSettings:
    """Numerical and loss-model controls for one annulus solution."""

    bracket_samples: int = 128
    max_iterations: int = 100
    angle_tolerance_rad: float = 1.0e-10
    residual_tolerance_m2_s: float = 1.0e-8
    minimum_tip_loss_factor: float = 1.0e-6
    include_tip_loss: bool = True

    def __post_init__(self) -> None:
        if self.bracket_samples < 2:
            raise ValueError("bracket_samples must be at least 2.")
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be at least 1.")
        for name in (
            "angle_tolerance_rad",
            "residual_tolerance_m2_s",
            "minimum_tip_loss_factor",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and greater than zero.")
        if self.minimum_tip_loss_factor > 1.0:
            raise ValueError("minimum_tip_loss_factor cannot exceed one.")


@dataclass(frozen=True)
class BEMAnnulusResult:
    """Converged local induced-flow state and loads per unit radius."""

    schema_version: int
    operating_condition_id: str
    airfoil_id: str
    scenario_id: str
    radius_m: float
    r_over_R: float
    chord_m: float
    twist_rad: float
    iterations: int
    psi_rad: float
    inflow_angle_rad: float
    angle_of_attack_rad: float
    axial_induced_velocity_m_s: float
    tangential_induced_velocity_m_s: float
    relative_speed_m_s: float
    reynolds: float
    mach: float
    cl: float
    cd: float
    circulation_m2_s: float
    tip_loss_factor: float
    differential_thrust_n_m: float
    differential_torque_nm_m: float
    residual_m2_s: float
    polar_sources: tuple[str, ...]
    interpolated_dimensions: tuple[str, ...]
    clamped_dimensions: tuple[str, ...]

    @property
    def converged(self) -> bool:
        return True

    def as_mapping(self) -> Mapping[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "schema_version": self.schema_version,
            "operating_condition_id": self.operating_condition_id,
            "airfoil_id": self.airfoil_id,
            "scenario_id": self.scenario_id,
            "radius_m": self.radius_m,
            "r_over_R": self.r_over_R,
            "chord_m": self.chord_m,
            "twist_rad": self.twist_rad,
            "converged": self.converged,
            "iterations": self.iterations,
            "psi_rad": self.psi_rad,
            "inflow_angle_rad": self.inflow_angle_rad,
            "angle_of_attack_rad": self.angle_of_attack_rad,
            "axial_induced_velocity_m_s": self.axial_induced_velocity_m_s,
            "tangential_induced_velocity_m_s": self.tangential_induced_velocity_m_s,
            "relative_speed_m_s": self.relative_speed_m_s,
            "reynolds": self.reynolds,
            "mach": self.mach,
            "cl": self.cl,
            "cd": self.cd,
            "circulation_m2_s": self.circulation_m2_s,
            "tip_loss_factor": self.tip_loss_factor,
            "differential_thrust_n_m": self.differential_thrust_n_m,
            "differential_torque_nm_m": self.differential_torque_nm_m,
            "residual_m2_s": self.residual_m2_s,
            "polar_sources": list(self.polar_sources),
            "interpolated_dimensions": list(self.interpolated_dimensions),
            "clamped_dimensions": list(self.clamped_dimensions),
        }


@dataclass(frozen=True)
class _AnnulusState:
    psi: float
    wa: float
    wt: float
    va: float
    vt: float
    relative_speed: float
    phi: float
    reynolds: float
    mach: float
    polar: PolarQueryResult
    tip_loss: float
    circulation_swirl: float
    circulation_blade: float

    @property
    def residual(self) -> float:
        return self.circulation_swirl - self.circulation_blade


def _tip_loss_factor(
    *, blade_count: int, r_over_R: float, wa: float, wt: float, minimum: float
) -> tuple[float, float]:
    wake_ratio = r_over_R * wa / wt
    if wake_ratio <= 1.0e-15:
        return 1.0, wake_ratio
    exponent = -0.5 * blade_count * (1.0 - r_over_R) / wake_ratio
    factor = (2.0 / math.pi) * math.acos(math.exp(exponent))
    return max(factor, minimum), wake_ratio


def solve_bem_annulus(
    blade: BladeGeometry,
    station: BladeStation,
    condition: OperatingCondition,
    polar_family: PolarFamily,
    *,
    bounds: PolarBoundsPolicy = "error",
    settings: BEMAnnulusSettings | None = None,
) -> BEMAnnulusResult:
    """Solve one propulsive axial-flow annulus with QPROP's psi parameterization.

    The supported domain is positive shaft speed, non-negative axial freestream,
    and an annulus strictly between hub and tip. Windmilling and descent solutions
    are intentionally rejected until their solution branches are modeled explicitly.
    """
    controls = settings or BEMAnnulusSettings()
    if bounds not in {"error", "clamp"}:
        raise BEMAnnulusError("bounds must be 'error' or 'clamp'.")
    if condition.angular_speed_rad_s <= 0.0:
        raise BEMAnnulusError("angular_speed_rad_s must be greater than zero.")
    if condition.forward_speed_m_s < 0.0:
        raise BEMAnnulusError("Negative forward speed is outside the supported domain.")
    if station.airfoil_id != polar_family.airfoil_id:
        raise BEMAnnulusError(
            "Blade station airfoil_id does not match the polar family airfoil_id."
        )

    radius = station.r_over_R * blade.radius_m
    if radius <= blade.hub_radius_m or station.r_over_R >= 1.0:
        raise BEMAnnulusError("Annulus radius must lie strictly between hub and blade tip.")

    axial_external = condition.forward_speed_m_s
    tangential_external = condition.angular_speed_rad_s * radius
    external_speed = math.hypot(axial_external, tangential_external)
    no_induction_psi = math.atan2(axial_external, tangential_external)
    speed_of_sound = math.sqrt(
        _AIR_GAMMA * _AIR_GAS_CONSTANT_J_KG_K * condition.temperature_k
    )

    def evaluate(psi: float) -> _AnnulusState:
        wa = 0.5 * axial_external + 0.5 * external_speed * math.sin(psi)
        wt = 0.5 * tangential_external + 0.5 * external_speed * math.cos(psi)
        va = wa - axial_external
        vt = tangential_external - wt
        relative_speed = math.hypot(wa, wt)
        phi = math.atan2(wa, wt)
        reynolds = (
            condition.air_density_kg_m3
            * relative_speed
            * station.chord_m
            / condition.dynamic_viscosity_pa_s
        )
        mach = relative_speed / speed_of_sound
        polar = polar_family.query(
            alpha_rad=station.twist_rad - phi,
            reynolds=reynolds,
            mach=mach,
            bounds=bounds,
        )
        if controls.include_tip_loss:
            tip_loss, wake_ratio = _tip_loss_factor(
                blade_count=blade.blade_count,
                r_over_R=station.r_over_R,
                wa=wa,
                wt=wt,
                minimum=controls.minimum_tip_loss_factor,
            )
        else:
            tip_loss = 1.0
            wake_ratio = station.r_over_R * wa / wt
        correction = math.sqrt(
            1.0
            + (
                4.0
                * wake_ratio
                * blade.radius_m
                / (math.pi * blade.blade_count * radius)
            )
            ** 2
        )
        circulation_swirl = (
            vt * (4.0 * math.pi * radius / blade.blade_count) * tip_loss * correction
        )
        circulation_blade = 0.5 * relative_speed * station.chord_m * polar.cl
        return _AnnulusState(
            psi,
            wa,
            wt,
            va,
            vt,
            relative_speed,
            phi,
            reynolds,
            mach,
            polar,
            tip_loss,
            circulation_swirl,
            circulation_blade,
        )

    lower_state = evaluate(no_induction_psi)
    if abs(lower_state.residual) <= controls.residual_tolerance_m2_s:
        solution = lower_state
        iterations = 0
    else:
        upper_psi = 0.5 * math.pi - controls.angle_tolerance_rad
        previous = lower_state
        bracket: tuple[float, float] | None = None
        for index in range(1, controls.bracket_samples + 1):
            psi = no_induction_psi + (upper_psi - no_induction_psi) * (
                index / controls.bracket_samples
            )
            current = evaluate(psi)
            if previous.residual * current.residual <= 0.0:
                bracket = (previous.psi, current.psi)
                break
            previous = current
        if bracket is None:
            raise BEMConvergenceError(
                "No positive-loading propulsive annulus solution was bracketed."
            )
        try:
            root, details = brentq(
                lambda psi: evaluate(psi).residual,
                *bracket,
                xtol=controls.angle_tolerance_rad,
                maxiter=controls.max_iterations,
                full_output=True,
                disp=False,
            )
        except (RuntimeError, ValueError) as exc:
            raise BEMConvergenceError("Annulus root solve did not converge.") from exc
        if not details.converged:
            raise BEMConvergenceError("Annulus root solve did not converge.")
        solution = evaluate(root)
        iterations = details.iterations

    if abs(solution.residual) > controls.residual_tolerance_m2_s:
        raise BEMConvergenceError(
            "Annulus circulation residual exceeds residual_tolerance_m2_s."
        )

    dynamic_force = (
        blade.blade_count
        * 0.5
        * condition.air_density_kg_m3
        * solution.relative_speed**2
        * station.chord_m
    )
    differential_thrust = dynamic_force * (
        solution.polar.cl * math.cos(solution.phi)
        - solution.polar.cd * math.sin(solution.phi)
    )
    differential_torque = dynamic_force * (
        solution.polar.cl * math.sin(solution.phi)
        + solution.polar.cd * math.cos(solution.phi)
    ) * radius

    return BEMAnnulusResult(
        schema_version=BEM_ANNULUS_SCHEMA_VERSION,
        operating_condition_id=condition.id,
        airfoil_id=station.airfoil_id,
        scenario_id=polar_family.scenario_id,
        radius_m=radius,
        r_over_R=station.r_over_R,
        chord_m=station.chord_m,
        twist_rad=station.twist_rad,
        iterations=iterations,
        psi_rad=solution.psi,
        inflow_angle_rad=solution.phi,
        angle_of_attack_rad=station.twist_rad - solution.phi,
        axial_induced_velocity_m_s=solution.va,
        tangential_induced_velocity_m_s=solution.vt,
        relative_speed_m_s=solution.relative_speed,
        reynolds=solution.reynolds,
        mach=solution.mach,
        cl=solution.polar.cl,
        cd=solution.polar.cd,
        circulation_m2_s=solution.circulation_blade,
        tip_loss_factor=solution.tip_loss,
        differential_thrust_n_m=differential_thrust,
        differential_torque_nm_m=differential_torque,
        residual_m2_s=solution.residual,
        polar_sources=solution.polar.sources,
        interpolated_dimensions=solution.polar.interpolated_dimensions,
        clamped_dimensions=solution.polar.clamped_dimensions,
    )
