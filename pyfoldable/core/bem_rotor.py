"""Midpoint radial integration built on the fail-closed local BEM annulus kernel."""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from .bem import (
    BEMAnnulusError,
    BEMAnnulusResult,
    BEMAnnulusSettings,
    BEMConvergenceError,
    BEMPolarQueryEnvelope,
    solve_bem_annulus,
)
from .models import BladeGeometry, BladeStation, OperatingCondition
from .polar import PolarBoundsPolicy, PolarFamily, PolarInterpolationError
from .polar_spanwise import SpanwisePolarSchedule
from .rotational_augmentation import RotationalAugmentationDomainError


BEM_ROTOR_SCHEMA_VERSION = 5
BEMRadialDomain = Literal["station_span", "hub_to_tip"]


class BEMRotorError(ValueError):
    """Raised when a rotor integration request is ambiguous or unsupported."""


class BEMRotorElementError(RuntimeError):
    """Raised when one annulus fails and no partial rotor result is returned."""


@dataclass(frozen=True)
class BEMRotorSettings:
    """Radial quadrature and local-solver settings.

    ``station_span`` is the fail-closed default: no geometry is invented outside
    the declared station range. ``hub_to_tip`` explicitly holds the endpoint
    chord/twist values constant over uncovered root or tip spans.
    """

    annulus_count: int = 40
    radial_domain: BEMRadialDomain = "station_span"
    annulus_settings: BEMAnnulusSettings = field(default_factory=BEMAnnulusSettings)

    def __post_init__(self) -> None:
        if not isinstance(self.annulus_count, int) or isinstance(
            self.annulus_count, bool
        ):
            raise TypeError("annulus_count must be an integer.")
        if self.annulus_count < 2:
            raise ValueError("annulus_count must be at least 2.")
        if self.radial_domain not in {"station_span", "hub_to_tip"}:
            raise ValueError(
                "radial_domain must be 'station_span' or 'hub_to_tip'."
            )
        if not isinstance(self.annulus_settings, BEMAnnulusSettings):
            raise TypeError("annulus_settings must be a BEMAnnulusSettings instance.")

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "annulus_count": self.annulus_count,
            "radial_domain": self.radial_domain,
            "annulus_settings": dict(self.annulus_settings.as_mapping()),
        }


@dataclass(frozen=True)
class BEMRotorElement:
    """One midpoint-rule radial element and its converged local solution."""

    index: int
    inner_radius_m: float
    outer_radius_m: float
    geometry_extrapolated: bool
    solution: BEMAnnulusResult

    @property
    def width_m(self) -> float:
        return self.outer_radius_m - self.inner_radius_m

    @property
    def thrust_n(self) -> float:
        return self.solution.differential_thrust_n_m * self.width_m

    @property
    def torque_nm(self) -> float:
        return self.solution.differential_torque_nm_m * self.width_m

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "index": self.index,
            "inner_radius_m": self.inner_radius_m,
            "outer_radius_m": self.outer_radius_m,
            "width_m": self.width_m,
            "geometry_extrapolated": self.geometry_extrapolated,
            "thrust_n": self.thrust_n,
            "torque_nm": self.torque_nm,
            "solution": dict(self.solution.as_mapping()),
        }


@dataclass(frozen=True)
class BEMRotorResult:
    """Integrated rotor loads and nondimensional performance coefficients."""

    schema_version: int
    operating_condition_id: str
    airfoil_id: str
    scenario_id: str
    radial_domain: BEMRadialDomain
    inner_radius_m: float
    outer_radius_m: float
    geometry_extended: bool
    polar_bounds: PolarBoundsPolicy
    settings: BEMRotorSettings
    elements: tuple[BEMRotorElement, ...]
    thrust_n: float
    torque_nm: float
    shaft_power_w: float
    thrust_coefficient: float
    torque_coefficient: float
    power_coefficient: float
    propulsive_efficiency: float | None
    maximum_residual_m2_s: float
    polar_sources: tuple[str, ...]
    interpolated_dimensions: tuple[str, ...]
    clamped_dimensions: tuple[str, ...]
    polar_query_envelope: BEMPolarQueryEnvelope

    @property
    def annulus_count(self) -> int:
        return len(self.elements)

    def as_mapping(self) -> Mapping[str, Any]:
        """Return the complete JSON-serializable result and audit trail."""
        return {
            "schema_version": self.schema_version,
            "operating_condition_id": self.operating_condition_id,
            "airfoil_id": self.airfoil_id,
            "scenario_id": self.scenario_id,
            "radial_domain": self.radial_domain,
            "integration_method": "midpoint",
            "geometry_interpolation": "linear_chord_twist",
            "inner_radius_m": self.inner_radius_m,
            "outer_radius_m": self.outer_radius_m,
            "geometry_extended": self.geometry_extended,
            "polar_bounds": self.polar_bounds,
            "settings": dict(self.settings.as_mapping()),
            "annulus_count": self.annulus_count,
            "elements": [dict(element.as_mapping()) for element in self.elements],
            "thrust_n": self.thrust_n,
            "torque_nm": self.torque_nm,
            "shaft_power_w": self.shaft_power_w,
            "thrust_coefficient": self.thrust_coefficient,
            "torque_coefficient": self.torque_coefficient,
            "power_coefficient": self.power_coefficient,
            "propulsive_efficiency": self.propulsive_efficiency,
            "maximum_residual_m2_s": self.maximum_residual_m2_s,
            "polar_sources": list(self.polar_sources),
            "interpolated_dimensions": list(self.interpolated_dimensions),
            "clamped_dimensions": list(self.clamped_dimensions),
            "polar_query_envelope": dict(self.polar_query_envelope.as_mapping()),
        }


def _radial_limits(
    blade: BladeGeometry, radial_domain: BEMRadialDomain
) -> tuple[float, float, bool]:
    first = blade.stations[0].r_over_R * blade.radius_m
    last = blade.stations[-1].r_over_R * blade.radius_m
    if radial_domain == "station_span":
        return first, last, False
    extended = (
        first > blade.hub_radius_m + 1.0e-12
        or last < blade.radius_m - 1.0e-12
    )
    return blade.hub_radius_m, blade.radius_m, extended


def _interpolate_station(
    blade: BladeGeometry,
    radius_m: float,
    *,
    airfoil_id_override: str | None = None,
) -> tuple[BladeStation, bool]:
    ratio = radius_m / blade.radius_m
    stations = blade.stations
    ratios = tuple(station.r_over_R for station in stations)
    if ratio <= ratios[0]:
        source = stations[0]
        return BladeStation(
            ratio,
            source.chord_m,
            source.twist_rad,
            airfoil_id_override or source.airfoil_id,
        ), (
            ratio < ratios[0] - 1.0e-12
        )
    if ratio >= ratios[-1]:
        source = stations[-1]
        return BladeStation(
            ratio,
            source.chord_m,
            source.twist_rad,
            airfoil_id_override or source.airfoil_id,
        ), (
            ratio > ratios[-1] + 1.0e-12
        )

    upper_index = bisect_right(ratios, ratio)
    lower = stations[upper_index - 1]
    upper = stations[upper_index]
    if lower.airfoil_id != upper.airfoil_id and airfoil_id_override is None:
        raise BEMRotorError(
            "PR-06B does not interpolate across different station airfoil_id values."
        )
    weight = (ratio - lower.r_over_R) / (upper.r_over_R - lower.r_over_R)
    return (
        BladeStation(
            r_over_R=ratio,
            chord_m=lower.chord_m + weight * (upper.chord_m - lower.chord_m),
            twist_rad=lower.twist_rad + weight * (upper.twist_rad - lower.twist_rad),
            airfoil_id=airfoil_id_override or lower.airfoil_id,
        ),
        False,
    )


def solve_bem_rotor(
    blade: BladeGeometry,
    condition: OperatingCondition,
    polar_families: Mapping[str, PolarFamily] | SpanwisePolarSchedule,
    *,
    bounds: PolarBoundsPolicy = "error",
    settings: BEMRotorSettings | None = None,
) -> BEMRotorResult:
    """Integrate converged local annuli across an explicit radial domain.

    A failure at any element aborts the result; partial rotor totals are never
    returned. A mapping preserves the original constant-airfoil contract. An
    explicit :class:`SpanwisePolarSchedule` queries and blends its endpoint polar
    families at every annulus while preserving their provenance.
    """
    controls = BEMRotorSettings() if settings is None else settings
    if not isinstance(controls, BEMRotorSettings):
        raise BEMRotorError("settings must be a BEMRotorSettings instance.")
    if bounds not in {"error", "clamp"}:
        raise BEMRotorError("bounds must be 'error' or 'clamp'.")
    schedule = (
        polar_families
        if isinstance(polar_families, SpanwisePolarSchedule)
        else None
    )
    if schedule is None:
        if not isinstance(polar_families, Mapping):
            raise BEMRotorError(
                "polar_families must be a mapping or SpanwisePolarSchedule."
            )
        airfoil_ids = {station.airfoil_id for station in blade.stations}
        if len(airfoil_ids) != 1:
            raise BEMRotorError(
                "Constant-polar mode requires one airfoil_id across all blade stations."
            )
        airfoil_id = next(iter(airfoil_ids))
        if airfoil_id not in polar_families:
            raise BEMRotorError(
                f"No polar family was supplied for airfoil_id {airfoil_id!r}."
            )
        family = polar_families[airfoil_id]
        if family.airfoil_id != airfoil_id:
            raise BEMRotorError(
                "Polar-family mapping key does not match the family's airfoil_id."
            )
        result_airfoil_id = airfoil_id
        result_scenario_id = family.scenario_id
    else:
        family = None
        result_airfoil_id = schedule.id
        result_scenario_id = ",".join(schedule.scenario_ids)

    inner_radius, outer_radius, geometry_extended = _radial_limits(
        blade, controls.radial_domain
    )
    width = (outer_radius - inner_radius) / controls.annulus_count
    elements: list[BEMRotorElement] = []
    for index in range(controls.annulus_count):
        inner = inner_radius + index * width
        outer = inner_radius + (index + 1) * width
        midpoint = 0.5 * (inner + outer)
        try:
            ratio = midpoint / blade.radius_m
            local_family = (
                schedule.section(ratio, bounds=bounds)
                if schedule is not None
                else family
            )
            if local_family is None:  # defensive type narrowing
                raise BEMRotorError("No local polar family is available.")
            station, geometry_extrapolated = _interpolate_station(
                blade,
                midpoint,
                airfoil_id_override=(
                    local_family.airfoil_id if schedule is not None else None
                ),
            )
            solution = solve_bem_annulus(
                blade,
                station,
                condition,
                local_family,
                bounds=bounds,
                settings=controls.annulus_settings,
            )
        except (
            BEMAnnulusError,
            BEMConvergenceError,
            BEMRotorError,
            PolarInterpolationError,
            RotationalAugmentationDomainError,
        ) as exc:
            raise BEMRotorElementError(
                f"Annulus {index} at r/R={ratio:.8g} failed: {exc}"
            ) from exc
        elements.append(
            BEMRotorElement(index, inner, outer, geometry_extrapolated, solution)
        )

    element_tuple = tuple(elements)
    thrust = math.fsum(element.thrust_n for element in element_tuple)
    torque = math.fsum(element.torque_nm for element in element_tuple)
    shaft_power = condition.angular_speed_rad_s * torque
    rotations_per_second = condition.angular_speed_rad_s / (2.0 * math.pi)
    coefficient_force = (
        condition.air_density_kg_m3
        * rotations_per_second**2
        * blade.diameter_m**4
    )
    coefficient_torque = coefficient_force * blade.diameter_m
    coefficient_power = (
        condition.air_density_kg_m3
        * rotations_per_second**3
        * blade.diameter_m**5
    )
    efficiency = (
        condition.forward_speed_m_s * thrust / shaft_power
        if condition.forward_speed_m_s > 0.0 and shaft_power > 0.0
        else None
    )

    sources = tuple(
        dict.fromkeys(
            source
            for element in element_tuple
            for source in element.solution.polar_sources
        )
    )
    interpolated = tuple(
        sorted(
            {
                dimension
                for element in element_tuple
                for dimension in element.solution.interpolated_dimensions
            }
        )
    )
    clamped = tuple(
        sorted(
            {
                dimension
                for element in element_tuple
                for dimension in element.solution.clamped_dimensions
            }
        )
    )

    return BEMRotorResult(
        schema_version=BEM_ROTOR_SCHEMA_VERSION,
        operating_condition_id=condition.id,
        airfoil_id=result_airfoil_id,
        scenario_id=result_scenario_id,
        radial_domain=controls.radial_domain,
        inner_radius_m=inner_radius,
        outer_radius_m=outer_radius,
        geometry_extended=geometry_extended,
        polar_bounds=bounds,
        settings=controls,
        elements=element_tuple,
        thrust_n=thrust,
        torque_nm=torque,
        shaft_power_w=shaft_power,
        thrust_coefficient=thrust / coefficient_force,
        torque_coefficient=torque / coefficient_torque,
        power_coefficient=shaft_power / coefficient_power,
        propulsive_efficiency=efficiency,
        maximum_residual_m2_s=max(
            abs(element.solution.residual_m2_s) for element in element_tuple
        ),
        polar_sources=sources,
        interpolated_dimensions=interpolated,
        clamped_dimensions=clamped,
        polar_query_envelope=BEMPolarQueryEnvelope.combine(
            tuple(element.solution.polar_query_envelope for element in element_tuple)
        ),
    )
