"""Fail-closed local blade-element/momentum annulus solution.

This module implements the hover-capable flow-angle parameterization from QPROP.
It deliberately stops at one annulus; radial interpolation and integration are in
``bem_rotor``. The optional root factor is an explicit extension to QPROP's modified
tip-loss relation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from scipy.optimize import brentq

from .models import BladeGeometry, BladeStation, OperatingCondition
from .polar import PolarBoundsPolicy, PolarFamily, PolarQueryResult
from .polar_spanwise import SpanwisePolarSection
from .rotational_augmentation import (
    RotationalAugmentationModel,
    RotationalAugmentationResult,
)


BEM_ANNULUS_SCHEMA_VERSION = 5
BEMLoadingBranch = Literal["positive_only", "signed_nonreversed"]
BEMLoadingRegime = Literal["negative", "zero", "positive"]
_AIR_GAMMA = 1.4
_AIR_GAS_CONSTANT_J_KG_K = 287.05


class BEMAnnulusError(ValueError):
    """Raised when an annulus request lies outside the supported physical domain."""


class BEMConvergenceError(RuntimeError):
    """Raised when a supported propulsive annulus solution is not obtained."""


@dataclass(frozen=True)
class BEMPolarQueryEnvelope:
    """Complete polar-query envelope traversed by one or more root solves."""

    query_count: int
    alpha_rad_min: float
    alpha_rad_max: float
    reynolds_min: float
    reynolds_max: float
    mach_min: float
    mach_max: float
    sources: tuple[str, ...]
    interpolated_dimensions: tuple[str, ...]
    clamped_dimensions: tuple[str, ...]

    @classmethod
    def from_queries(
        cls, queries: tuple[PolarQueryResult, ...]
    ) -> "BEMPolarQueryEnvelope":
        if not queries:
            raise ValueError("Polar query envelope requires at least one query.")
        return cls(
            query_count=len(queries),
            alpha_rad_min=min(query.alpha_rad for query in queries),
            alpha_rad_max=max(query.alpha_rad for query in queries),
            reynolds_min=min(query.reynolds for query in queries),
            reynolds_max=max(query.reynolds for query in queries),
            mach_min=min(query.mach for query in queries),
            mach_max=max(query.mach for query in queries),
            sources=tuple(
                dict.fromkeys(source for query in queries for source in query.sources)
            ),
            interpolated_dimensions=tuple(
                sorted(
                    {
                        dimension
                        for query in queries
                        for dimension in query.interpolated_dimensions
                    }
                )
            ),
            clamped_dimensions=tuple(
                sorted(
                    {
                        dimension
                        for query in queries
                        for dimension in query.clamped_dimensions
                    }
                )
            ),
        )

    @classmethod
    def combine(
        cls, envelopes: tuple["BEMPolarQueryEnvelope", ...]
    ) -> "BEMPolarQueryEnvelope":
        if not envelopes:
            raise ValueError("Polar query envelope combination cannot be empty.")
        return cls(
            query_count=sum(envelope.query_count for envelope in envelopes),
            alpha_rad_min=min(envelope.alpha_rad_min for envelope in envelopes),
            alpha_rad_max=max(envelope.alpha_rad_max for envelope in envelopes),
            reynolds_min=min(envelope.reynolds_min for envelope in envelopes),
            reynolds_max=max(envelope.reynolds_max for envelope in envelopes),
            mach_min=min(envelope.mach_min for envelope in envelopes),
            mach_max=max(envelope.mach_max for envelope in envelopes),
            sources=tuple(
                dict.fromkeys(
                    source for envelope in envelopes for source in envelope.sources
                )
            ),
            interpolated_dimensions=tuple(
                sorted(
                    {
                        dimension
                        for envelope in envelopes
                        for dimension in envelope.interpolated_dimensions
                    }
                )
            ),
            clamped_dimensions=tuple(
                sorted(
                    {
                        dimension
                        for envelope in envelopes
                        for dimension in envelope.clamped_dimensions
                    }
                )
            ),
        )

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "query_count": self.query_count,
            "alpha_rad_min": self.alpha_rad_min,
            "alpha_rad_max": self.alpha_rad_max,
            "reynolds_min": self.reynolds_min,
            "reynolds_max": self.reynolds_max,
            "mach_min": self.mach_min,
            "mach_max": self.mach_max,
            "sources": list(self.sources),
            "interpolated_dimensions": list(self.interpolated_dimensions),
            "clamped_dimensions": list(self.clamped_dimensions),
        }


@dataclass(frozen=True)
class BEMAnnulusSettings:
    """Numerical and loss-model controls for one annulus solution."""

    bracket_samples: int = 128
    max_iterations: int = 100
    angle_tolerance_rad: float = 1.0e-10
    residual_tolerance_m2_s: float = 1.0e-8
    relative_residual_tolerance: float = 1.0e-10
    minimum_tip_loss_factor: float = 1.0e-6
    include_tip_loss: bool = True
    include_root_loss: bool = False
    loading_branch: BEMLoadingBranch = "positive_only"
    rotational_augmentation: RotationalAugmentationModel = field(
        default_factory=RotationalAugmentationModel.disabled
    )

    def __post_init__(self) -> None:
        if not isinstance(self.bracket_samples, int) or isinstance(
            self.bracket_samples, bool
        ):
            raise TypeError("bracket_samples must be an integer.")
        if not isinstance(self.max_iterations, int) or isinstance(
            self.max_iterations, bool
        ):
            raise TypeError("max_iterations must be an integer.")
        if self.bracket_samples < 2:
            raise ValueError("bracket_samples must be at least 2.")
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be at least 1.")
        for name in (
            "angle_tolerance_rad",
            "residual_tolerance_m2_s",
            "relative_residual_tolerance",
            "minimum_tip_loss_factor",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and greater than zero.")
        if self.minimum_tip_loss_factor > 1.0:
            raise ValueError("minimum_tip_loss_factor cannot exceed one.")
        if not isinstance(self.include_tip_loss, bool):
            raise TypeError("include_tip_loss must be boolean.")
        if not isinstance(self.include_root_loss, bool):
            raise TypeError("include_root_loss must be boolean.")
        if not isinstance(self.loading_branch, str):
            raise TypeError("loading_branch must be a string.")
        if self.loading_branch not in {"positive_only", "signed_nonreversed"}:
            raise ValueError(
                "loading_branch must be 'positive_only' or 'signed_nonreversed'."
            )
        if not isinstance(
            self.rotational_augmentation, RotationalAugmentationModel
        ):
            raise TypeError(
                "rotational_augmentation must be a RotationalAugmentationModel."
            )

    def as_mapping(self) -> Mapping[str, Any]:
        """Return the complete numerical/loss-model contract."""
        return {
            "bracket_samples": self.bracket_samples,
            "max_iterations": self.max_iterations,
            "angle_tolerance_rad": self.angle_tolerance_rad,
            "residual_tolerance_m2_s": self.residual_tolerance_m2_s,
            "relative_residual_tolerance": self.relative_residual_tolerance,
            "minimum_tip_loss_factor": self.minimum_tip_loss_factor,
            "include_tip_loss": self.include_tip_loss,
            "include_root_loss": self.include_root_loss,
            "loading_branch": self.loading_branch,
            "rotational_augmentation": dict(
                self.rotational_augmentation.as_mapping()
            ),
        }


@dataclass(frozen=True)
class BEMAnnulusResult:
    """Converged local induced-flow state and loads per unit radius."""

    schema_version: int
    operating_condition_id: str
    airfoil_id: str
    scenario_id: str
    polar_bounds: PolarBoundsPolicy
    settings: BEMAnnulusSettings
    radius_m: float
    r_over_R: float
    chord_m: float
    twist_rad: float
    loading_regime: BEMLoadingRegime
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
    raw_polar_cl: float
    raw_polar_cd: float
    rotational_augmentation: Mapping[str, Any]
    circulation_m2_s: float
    tip_loss_factor: float
    root_loss_factor: float
    combined_loss_factor: float
    differential_thrust_n_m: float
    differential_torque_nm_m: float
    residual_m2_s: float
    polar_sources: tuple[str, ...]
    interpolated_dimensions: tuple[str, ...]
    clamped_dimensions: tuple[str, ...]
    polar_query_envelope: BEMPolarQueryEnvelope

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
            "polar_bounds": self.polar_bounds,
            "settings": dict(self.settings.as_mapping()),
            "radius_m": self.radius_m,
            "r_over_R": self.r_over_R,
            "chord_m": self.chord_m,
            "twist_rad": self.twist_rad,
            "loading_regime": self.loading_regime,
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
            "raw_polar_cl": self.raw_polar_cl,
            "raw_polar_cd": self.raw_polar_cd,
            "rotational_augmentation": dict(self.rotational_augmentation),
            "circulation_m2_s": self.circulation_m2_s,
            "tip_loss_factor": self.tip_loss_factor,
            "root_loss_factor": self.root_loss_factor,
            "combined_loss_factor": self.combined_loss_factor,
            "differential_thrust_n_m": self.differential_thrust_n_m,
            "differential_torque_nm_m": self.differential_torque_nm_m,
            "residual_m2_s": self.residual_m2_s,
            "polar_sources": list(self.polar_sources),
            "interpolated_dimensions": list(self.interpolated_dimensions),
            "clamped_dimensions": list(self.clamped_dimensions),
            "polar_query_envelope": dict(self.polar_query_envelope.as_mapping()),
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
    augmentation: RotationalAugmentationResult
    tip_loss: float
    root_loss: float
    combined_loss: float
    circulation_swirl: float
    circulation_blade: float

    @property
    def residual(self) -> float:
        return self.circulation_swirl - self.circulation_blade


def _prandtl_factor(exponent_argument: float, minimum: float) -> float:
    factor = (2.0 / math.pi) * math.acos(math.exp(-max(exponent_argument, 0.0)))
    return max(factor, minimum)


def _loss_factors(
    *,
    blade: BladeGeometry,
    radius: float,
    wa: float,
    wt: float,
    settings: BEMAnnulusSettings,
) -> tuple[float, float, float, float]:
    r_over_R = radius / blade.radius_m
    wake_ratio = r_over_R * wa / wt
    if wake_ratio <= 1.0e-15:
        return 1.0, 1.0, 1.0, wake_ratio

    if settings.include_tip_loss:
        tip_argument = (
            0.5 * blade.blade_count * (1.0 - r_over_R) / wake_ratio
        )
        tip_loss = _prandtl_factor(
            tip_argument, settings.minimum_tip_loss_factor
        )
    else:
        tip_loss = 1.0

    if settings.include_root_loss:
        sine_phi = wa / math.hypot(wa, wt)
        root_argument = (
            0.5
            * blade.blade_count
            * (radius - blade.hub_radius_m)
            / (blade.hub_radius_m * sine_phi)
        )
        root_loss = _prandtl_factor(
            root_argument, settings.minimum_tip_loss_factor
        )
    else:
        root_loss = 1.0

    return tip_loss, root_loss, tip_loss * root_loss, wake_ratio


def _residual_limit(state: _AnnulusState, settings: BEMAnnulusSettings) -> float:
    scale = max(
        abs(state.circulation_swirl),
        abs(state.circulation_blade),
        1.0e-30,
    )
    return (
        settings.residual_tolerance_m2_s
        + settings.relative_residual_tolerance * scale
    )


def solve_bem_annulus(
    blade: BladeGeometry,
    station: BladeStation,
    condition: OperatingCondition,
    polar_family: PolarFamily | SpanwisePolarSection,
    *,
    bounds: PolarBoundsPolicy = "error",
    settings: BEMAnnulusSettings | None = None,
) -> BEMAnnulusResult:
    """Solve one axial-flow annulus with QPROP's psi parameterization.

    The supported domain is positive shaft speed, non-negative axial freestream,
    and an annulus strictly between hub and tip. ``signed_nonreversed`` additionally
    permits locally unloaded or negative-loaded sections while requiring positive
    through-disk axial and blade-relative tangential velocities. Reversed flow and
    descent remain outside the modeled branch.
    """
    controls = BEMAnnulusSettings() if settings is None else settings
    if not isinstance(controls, BEMAnnulusSettings):
        raise BEMAnnulusError("settings must be a BEMAnnulusSettings instance.")
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
    if controls.include_root_loss and blade.hub_radius_m <= 0.0:
        raise BEMAnnulusError(
            "include_root_loss requires a strictly positive hub_radius_m."
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
    polar_queries: list[PolarQueryResult] = []

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
        polar_queries.append(polar)
        augmentation = controls.rotational_augmentation.apply(
            alpha_rad=station.twist_rad - phi,
            cl_2d=polar.cl,
            cd_2d=polar.cd,
            chord_over_radius=station.chord_m / radius,
        )
        tip_loss, root_loss, combined_loss, wake_ratio = _loss_factors(
            blade=blade,
            radius=radius,
            wa=wa,
            wt=wt,
            settings=controls,
        )
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
            vt
            * (4.0 * math.pi * radius / blade.blade_count)
            * combined_loss
            * correction
        )
        circulation_blade = (
            0.5 * relative_speed * station.chord_m * augmentation.cl
        )
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
            augmentation,
            tip_loss,
            root_loss,
            combined_loss,
            circulation_swirl,
            circulation_blade,
        )

    no_induction_state = evaluate(no_induction_psi)
    if abs(no_induction_state.residual) <= _residual_limit(
        no_induction_state, controls
    ):
        solution = no_induction_state
        iterations = 0
    else:
        positive_loading = no_induction_state.residual < 0.0
        if positive_loading or controls.loading_branch == "positive_only":
            terminal_psi = 0.5 * math.pi - controls.angle_tolerance_rad
        else:
            minimum_nonreversed_psi = math.asin(
                max(-1.0, min(1.0, -axial_external / external_speed))
            )
            terminal_psi = (
                minimum_nonreversed_psi + controls.angle_tolerance_rad
            )
        if abs(terminal_psi - no_induction_psi) <= controls.angle_tolerance_rad:
            raise BEMConvergenceError(
                "The QPROP psi search interval collapsed for the selected loading branch."
            )
        previous = no_induction_state
        bracket: tuple[float, float] | None = None
        scanned_root: _AnnulusState | None = None
        for index in range(1, controls.bracket_samples + 1):
            psi = no_induction_psi + (terminal_psi - no_induction_psi) * (
                index / controls.bracket_samples
            )
            current = evaluate(psi)
            if abs(current.residual) <= _residual_limit(current, controls):
                scanned_root = current
                break
            if previous.residual * current.residual <= 0.0:
                bracket = tuple(sorted((previous.psi, current.psi)))
                break
            previous = current
        if scanned_root is not None:
            solution = scanned_root
            iterations = 0
        elif bracket is None:
            raise BEMConvergenceError(
                "No annulus solution was bracketed on the selected loading branch."
            )
        else:
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
                raise BEMConvergenceError(
                    "Annulus root solve did not converge."
                ) from exc
            if not details.converged:
                raise BEMConvergenceError("Annulus root solve did not converge.")
            solution = evaluate(root)
            iterations = details.iterations

    if abs(solution.residual) > _residual_limit(solution, controls):
        raise BEMConvergenceError(
            "Annulus circulation residual exceeds the configured tolerance."
        )

    residual_limit = _residual_limit(solution, controls)
    if (
        controls.loading_branch == "positive_only"
        and solution.circulation_blade < -residual_limit
    ):
        raise BEMConvergenceError(
            "Converged root is not on the supported non-negative circulation branch."
        )
    flow_tolerance = controls.angle_tolerance_rad * max(
        solution.relative_speed, 1.0
    )
    if controls.loading_branch == "positive_only" and (
        solution.va < -flow_tolerance or solution.vt < -flow_tolerance
    ):
        raise BEMConvergenceError(
            "Converged root is not on the supported propulsive induced-flow branch."
        )
    if controls.loading_branch == "signed_nonreversed":
        if solution.wa <= flow_tolerance or solution.wt <= flow_tolerance:
            raise BEMConvergenceError(
                "Converged root leaves the supported non-reversed-flow branch."
            )
        circulation_sign = (
            1
            if solution.circulation_blade > residual_limit
            else -1
            if solution.circulation_blade < -residual_limit
            else 0
        )
        if circulation_sign and (
            circulation_sign * solution.va < -flow_tolerance
            or circulation_sign * solution.vt < -flow_tolerance
        ):
            raise BEMConvergenceError(
                "Induced-flow signs are inconsistent with signed circulation."
            )

    if solution.circulation_blade > residual_limit:
        loading_regime: BEMLoadingRegime = "positive"
    elif solution.circulation_blade < -residual_limit:
        loading_regime = "negative"
    else:
        loading_regime = "zero"

    dynamic_force = (
        blade.blade_count
        * 0.5
        * condition.air_density_kg_m3
        * solution.relative_speed**2
        * station.chord_m
    )
    differential_thrust = dynamic_force * (
        solution.augmentation.cl * math.cos(solution.phi)
        - solution.augmentation.cd * math.sin(solution.phi)
    )
    differential_torque = dynamic_force * (
        solution.augmentation.cl * math.sin(solution.phi)
        + solution.augmentation.cd * math.cos(solution.phi)
    ) * radius

    return BEMAnnulusResult(
        schema_version=BEM_ANNULUS_SCHEMA_VERSION,
        operating_condition_id=condition.id,
        airfoil_id=station.airfoil_id,
        scenario_id=polar_family.scenario_id,
        polar_bounds=bounds,
        settings=controls,
        radius_m=radius,
        r_over_R=station.r_over_R,
        chord_m=station.chord_m,
        twist_rad=station.twist_rad,
        loading_regime=loading_regime,
        iterations=iterations,
        psi_rad=solution.psi,
        inflow_angle_rad=solution.phi,
        angle_of_attack_rad=station.twist_rad - solution.phi,
        axial_induced_velocity_m_s=solution.va,
        tangential_induced_velocity_m_s=solution.vt,
        relative_speed_m_s=solution.relative_speed,
        reynolds=solution.reynolds,
        mach=solution.mach,
        cl=solution.augmentation.cl,
        cd=solution.augmentation.cd,
        raw_polar_cl=solution.polar.cl,
        raw_polar_cd=solution.polar.cd,
        rotational_augmentation=solution.augmentation.as_mapping(),
        circulation_m2_s=solution.circulation_blade,
        tip_loss_factor=solution.tip_loss,
        root_loss_factor=solution.root_loss,
        combined_loss_factor=solution.combined_loss,
        differential_thrust_n_m=differential_thrust,
        differential_torque_nm_m=differential_torque,
        residual_m2_s=solution.residual,
        polar_sources=solution.polar.sources,
        interpolated_dimensions=solution.polar.interpolated_dimensions,
        clamped_dimensions=solution.polar.clamped_dimensions,
        polar_query_envelope=BEMPolarQueryEnvelope.from_queries(tuple(polar_queries)),
    )
