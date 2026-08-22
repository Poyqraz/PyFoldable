"""PR-06D fold-state geometry boundary for fixed-limit BEM equivalence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .bem_rotor import BEMRotorResult, BEMRotorSettings, solve_bem_rotor
from .models import BladeGeometry, BladeStation, OperatingCondition
from .polar import PolarBoundsPolicy, PolarFamily
from .polar_spanwise import SpanwisePolarAnchor, SpanwisePolarSchedule


FOLDABLE_BEM_ROTOR_SCHEMA_VERSION = 1


class FoldableRotorGeometryError(ValueError):
    """Raised when a fold state cannot form a valid axisymmetric BEM geometry."""


def _finite(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number.")
    if not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite.")


@dataclass(frozen=True)
class FoldableRotorState:
    """One prescribed hinge state using a radial cosine-projection screen."""

    id: str
    hinge_radius_m: float
    opening_angle_rad: float
    deployed_angle_rad: float = 0.0

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("FoldableRotorState.id must not be empty.")
        for name in (
            "hinge_radius_m",
            "opening_angle_rad",
            "deployed_angle_rad",
        ):
            _finite(name, getattr(self, name))
        if self.hinge_radius_m <= 0.0:
            raise ValueError("hinge_radius_m must be greater than zero.")

    @property
    def angle_from_deployed_rad(self) -> float:
        return self.opening_angle_rad - self.deployed_angle_rad

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "id": self.id,
            "hinge_radius_m": self.hinge_radius_m,
            "opening_angle_rad": self.opening_angle_rad,
            "deployed_angle_rad": self.deployed_angle_rad,
            "angle_from_deployed_rad": self.angle_from_deployed_rad,
            "projection_model": "radial_cosine_v1",
        }


@dataclass(frozen=True)
class FoldableStationProjection:
    """Material-station identity before and after radial projection."""

    nominal_radius_m: float
    effective_radius_m: float
    nominal_r_over_R: float
    effective_r_over_R: float
    chord_m: float
    twist_rad: float
    airfoil_id: str

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "nominal_radius_m": self.nominal_radius_m,
            "effective_radius_m": self.effective_radius_m,
            "nominal_r_over_R": self.nominal_r_over_R,
            "effective_r_over_R": self.effective_r_over_R,
            "chord_m": self.chord_m,
            "twist_rad": self.twist_rad,
            "airfoil_id": self.airfoil_id,
        }


@dataclass(frozen=True)
class FoldableBladeProjection:
    """Nominal/effective blade pair and auditable station correspondence."""

    state: FoldableRotorState
    nominal_blade: BladeGeometry
    effective_blade: BladeGeometry
    projection_factor: float
    stations: tuple[FoldableStationProjection, ...]
    inserted_hinge_station: bool

    @property
    def fixed_limit_equivalent(self) -> bool:
        return self.effective_blade is self.nominal_blade

    def effective_radius_for_nominal(self, nominal_radius_m: float) -> float:
        _finite("nominal_radius_m", nominal_radius_m)
        if nominal_radius_m < 0.0 or nominal_radius_m > self.nominal_blade.radius_m:
            raise FoldableRotorGeometryError(
                "nominal_radius_m lies outside the nominal blade."
            )
        if nominal_radius_m <= self.state.hinge_radius_m:
            return nominal_radius_m
        return self.state.hinge_radius_m + (
            nominal_radius_m - self.state.hinge_radius_m
        ) * self.projection_factor

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "state": dict(self.state.as_mapping()),
            "projection_factor": self.projection_factor,
            "fixed_limit_equivalent": self.fixed_limit_equivalent,
            "inserted_hinge_station": self.inserted_hinge_station,
            "nominal_geometry": _blade_mapping(self.nominal_blade),
            "effective_geometry": _blade_mapping(self.effective_blade),
            "stations": [dict(station.as_mapping()) for station in self.stations],
        }


@dataclass(frozen=True)
class FoldableBEMRotorResult:
    """Fold-state provenance wrapped around the unchanged BEM rotor result."""

    schema_version: int
    geometry: FoldableBladeProjection
    rotor_result: BEMRotorResult
    polar_schedule_id: str | None

    @property
    def fixed_limit_equivalent(self) -> bool:
        return self.geometry.fixed_limit_equivalent

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "schema_version": self.schema_version,
            "state": dict(self.geometry.state.as_mapping()),
            "projection_factor": self.geometry.projection_factor,
            "fixed_limit_equivalent": self.fixed_limit_equivalent,
            "nominal_geometry": _blade_mapping(self.geometry.nominal_blade),
            "effective_geometry": _blade_mapping(self.geometry.effective_blade),
            "station_projection": [
                dict(station.as_mapping()) for station in self.geometry.stations
            ],
            "polar_schedule_id": self.polar_schedule_id,
            "rotor_result": dict(self.rotor_result.as_mapping()),
            "qualification": "screening_only_until_pr06c_passes",
        }


@dataclass(frozen=True)
class FixedLimitEquivalenceCase:
    """One exact fixed-versus-fully-deployed comparison."""

    operating_condition_id: str
    rotor_mapping_equal: bool
    thrust_delta_n: float
    torque_delta_nm: float
    thrust_coefficient_delta: float
    power_coefficient_delta: float

    def __post_init__(self) -> None:
        if not self.operating_condition_id:
            raise ValueError("operating_condition_id must not be empty.")
        if not isinstance(self.rotor_mapping_equal, bool):
            raise TypeError("rotor_mapping_equal must be boolean.")
        for name in (
            "thrust_delta_n",
            "torque_delta_nm",
            "thrust_coefficient_delta",
            "power_coefficient_delta",
        ):
            _finite(name, getattr(self, name))

    @property
    def passed(self) -> bool:
        return (
            self.rotor_mapping_equal
            and self.thrust_delta_n == 0.0
            and self.torque_delta_nm == 0.0
            and self.thrust_coefficient_delta == 0.0
            and self.power_coefficient_delta == 0.0
        )

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "operating_condition_id": self.operating_condition_id,
            "passed": self.passed,
            "rotor_mapping_equal": self.rotor_mapping_equal,
            "thrust_delta_n": self.thrust_delta_n,
            "torque_delta_nm": self.torque_delta_nm,
            "thrust_coefficient_delta": self.thrust_coefficient_delta,
            "power_coefficient_delta": self.power_coefficient_delta,
        }


@dataclass(frozen=True)
class FixedLimitEquivalenceEvidence:
    """Machine-readable PR-06D entry gate over declared operating conditions."""

    state: FoldableRotorState
    cases: tuple[FixedLimitEquivalenceCase, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.state, FoldableRotorState):
            raise TypeError("state must be a FoldableRotorState.")
        if not self.cases:
            raise ValueError("Fixed-limit evidence requires at least one case.")
        if not all(isinstance(case, FixedLimitEquivalenceCase) for case in self.cases):
            raise TypeError("cases must contain FixedLimitEquivalenceCase values.")
        case_ids = tuple(case.operating_condition_id for case in self.cases)
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("Fixed-limit operating condition ids must be unique.")

    @property
    def point_count(self) -> int:
        return len(self.cases)

    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)

    @property
    def maximum_absolute_thrust_delta_n(self) -> float:
        return max(abs(case.thrust_delta_n) for case in self.cases)

    @property
    def maximum_absolute_torque_delta_nm(self) -> float:
        return max(abs(case.torque_delta_nm) for case in self.cases)

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "schema_version": 1,
            "kind": "pr06d-fixed-limit-equivalence",
            "passed": self.passed,
            "point_count": self.point_count,
            "state": dict(self.state.as_mapping()),
            "maximum_absolute_thrust_delta_n": (
                self.maximum_absolute_thrust_delta_n
            ),
            "maximum_absolute_torque_delta_nm": (
                self.maximum_absolute_torque_delta_nm
            ),
            "cases": [dict(case.as_mapping()) for case in self.cases],
            "qualification": "software_equivalence_not_physical_accuracy",
        }


def _blade_mapping(blade: BladeGeometry) -> Mapping[str, Any]:
    return {
        "diameter_m": blade.diameter_m,
        "radius_m": blade.radius_m,
        "hub_radius_m": blade.hub_radius_m,
        "blade_count": blade.blade_count,
        "stations": [
            {
                "r_over_R": station.r_over_R,
                "radius_m": station.r_over_R * blade.radius_m,
                "chord_m": station.chord_m,
                "twist_rad": station.twist_rad,
                "airfoil_id": station.airfoil_id,
            }
            for station in blade.stations
        ],
    }


def _station_at_hinge(
    blade: BladeGeometry, hinge_radius_m: float
) -> BladeStation | None:
    ratio = hinge_radius_m / blade.radius_m
    for station in blade.stations:
        if math.isclose(station.r_over_R, ratio, rel_tol=0.0, abs_tol=1.0e-12):
            return None
    for lower, upper in zip(blade.stations, blade.stations[1:]):
        if lower.r_over_R < ratio < upper.r_over_R:
            if lower.airfoil_id != upper.airfoil_id:
                raise FoldableRotorGeometryError(
                    "A hinge between different airfoil ids requires an explicit "
                    "blade station."
                )
            weight = (ratio - lower.r_over_R) / (
                upper.r_over_R - lower.r_over_R
            )
            return BladeStation(
                ratio,
                lower.chord_m + weight * (upper.chord_m - lower.chord_m),
                lower.twist_rad + weight * (upper.twist_rad - lower.twist_rad),
                lower.airfoil_id,
            )
    return None


def project_foldable_blade(
    blade: BladeGeometry, state: FoldableRotorState
) -> FoldableBladeProjection:
    """Project a prescribed fold state into the axisymmetric BEM rotor plane."""
    if not isinstance(blade, BladeGeometry):
        raise TypeError("blade must be a BladeGeometry.")
    if not isinstance(state, FoldableRotorState):
        raise TypeError("state must be a FoldableRotorState.")
    if not blade.hub_radius_m < state.hinge_radius_m < blade.radius_m:
        raise FoldableRotorGeometryError(
            "hinge_radius_m must lie between hub and nominal blade tip."
        )
    delta = state.angle_from_deployed_rad
    if abs(delta) >= 0.5 * math.pi:
        if math.isclose(abs(delta), 0.5 * math.pi, abs_tol=1.0e-12):
            raise FoldableRotorGeometryError(
                "The selected fold state has no positive radial projection."
            )
        raise FoldableRotorGeometryError(
            "The axisymmetric projection requires opening within 90 degrees "
            "of deployed."
        )
    projection_factor = math.cos(delta)
    if projection_factor <= 1.0e-12:
        raise FoldableRotorGeometryError(
            "The selected fold state has no positive radial projection."
        )
    if projection_factor > 1.0 + 1.0e-12:
        raise FoldableRotorGeometryError("Invalid radial projection factor.")
    if delta == 0.0:
        stations = tuple(
            FoldableStationProjection(
                station.r_over_R * blade.radius_m,
                station.r_over_R * blade.radius_m,
                station.r_over_R,
                station.r_over_R,
                station.chord_m,
                station.twist_rad,
                station.airfoil_id,
            )
            for station in blade.stations
        )
        return FoldableBladeProjection(
            state, blade, blade, 1.0, stations, False
        )

    hinge_station = _station_at_hinge(blade, state.hinge_radius_m)
    nominal_stations = list(blade.stations)
    if hinge_station is not None:
        nominal_stations.append(hinge_station)
        nominal_stations.sort(key=lambda station: station.r_over_R)
    effective_radius = state.hinge_radius_m + (
        blade.radius_m - state.hinge_radius_m
    ) * projection_factor
    if effective_radius <= blade.hub_radius_m:
        raise FoldableRotorGeometryError(
            "Effective blade radius must remain outside the hub."
        )

    projections: list[FoldableStationProjection] = []
    effective_stations: list[BladeStation] = []
    for station in nominal_stations:
        nominal_radius = station.r_over_R * blade.radius_m
        local_radius = (
            nominal_radius
            if nominal_radius <= state.hinge_radius_m
            else state.hinge_radius_m
            + (nominal_radius - state.hinge_radius_m) * projection_factor
        )
        local_ratio = local_radius / effective_radius
        effective_stations.append(
            BladeStation(
                local_ratio,
                station.chord_m,
                station.twist_rad,
                station.airfoil_id,
            )
        )
        projections.append(
            FoldableStationProjection(
                nominal_radius,
                local_radius,
                station.r_over_R,
                local_ratio,
                station.chord_m,
                station.twist_rad,
                station.airfoil_id,
            )
        )
    effective_blade = BladeGeometry(
        diameter_m=2.0 * effective_radius,
        hub_radius_m=blade.hub_radius_m,
        blade_count=blade.blade_count,
        stations=tuple(effective_stations),
    )
    return FoldableBladeProjection(
        state,
        blade,
        effective_blade,
        projection_factor,
        tuple(projections),
        hinge_station is not None,
    )


def project_spanwise_polar_schedule(
    schedule: SpanwisePolarSchedule,
    nominal_blade: BladeGeometry,
    projection: FoldableBladeProjection,
) -> SpanwisePolarSchedule:
    """Map polar anchors by material radius so airfoil identity cannot drift."""
    if not isinstance(schedule, SpanwisePolarSchedule):
        raise TypeError("schedule must be a SpanwisePolarSchedule.")
    if projection.nominal_blade != nominal_blade:
        raise FoldableRotorGeometryError(
            "Polar projection nominal blade does not match the geometry projection."
        )
    if projection.fixed_limit_equivalent:
        return schedule
    anchors = tuple(
        SpanwisePolarAnchor(
            projection.effective_radius_for_nominal(
                anchor.r_over_R * nominal_blade.radius_m
            )
            / projection.effective_blade.radius_m,
            anchor.family,
        )
        for anchor in schedule.anchors
    )
    return SpanwisePolarSchedule(
        f"{schedule.id}@fold:{projection.state.id}", anchors
    )


def solve_foldable_bem_rotor(
    blade: BladeGeometry,
    state: FoldableRotorState,
    condition: OperatingCondition,
    polar_families: Mapping[str, PolarFamily] | SpanwisePolarSchedule,
    *,
    bounds: PolarBoundsPolicy = "error",
    settings: BEMRotorSettings | None = None,
) -> FoldableBEMRotorResult:
    """Solve a prescribed fold state while retaining the fixed BEM core."""
    projection = project_foldable_blade(blade, state)
    solver_polars = (
        project_spanwise_polar_schedule(polar_families, blade, projection)
        if isinstance(polar_families, SpanwisePolarSchedule)
        else polar_families
    )
    rotor_result = solve_bem_rotor(
        projection.effective_blade,
        condition,
        solver_polars,
        bounds=bounds,
        settings=settings,
    )
    return FoldableBEMRotorResult(
        schema_version=FOLDABLE_BEM_ROTOR_SCHEMA_VERSION,
        geometry=projection,
        rotor_result=rotor_result,
        polar_schedule_id=(
            solver_polars.id
            if isinstance(solver_polars, SpanwisePolarSchedule)
            else None
        ),
    )


def assess_fixed_limit_equivalence(
    blade: BladeGeometry,
    state: FoldableRotorState,
    conditions: Sequence[OperatingCondition],
    polar_families: Mapping[str, PolarFamily] | SpanwisePolarSchedule,
    *,
    bounds: PolarBoundsPolicy = "error",
    settings: BEMRotorSettings | None = None,
) -> FixedLimitEquivalenceEvidence:
    """Prove exact equality between fixed and fully deployed fold-state paths."""
    if not isinstance(state, FoldableRotorState):
        raise TypeError("state must be a FoldableRotorState.")
    if state.angle_from_deployed_rad != 0.0:
        raise FoldableRotorGeometryError(
            "Fixed-limit evidence requires the fully deployed state."
        )
    condition_tuple = tuple(conditions)
    if not condition_tuple or not all(
        isinstance(condition, OperatingCondition) for condition in condition_tuple
    ):
        raise TypeError(
            "conditions must contain at least one OperatingCondition."
        )
    if len({condition.id for condition in condition_tuple}) != len(condition_tuple):
        raise ValueError("Fixed-limit operating condition ids must be unique.")

    cases: list[FixedLimitEquivalenceCase] = []
    for condition in condition_tuple:
        fixed = solve_bem_rotor(
            blade,
            condition,
            polar_families,
            bounds=bounds,
            settings=settings,
        )
        foldable = solve_foldable_bem_rotor(
            blade,
            state,
            condition,
            polar_families,
            bounds=bounds,
            settings=settings,
        ).rotor_result
        cases.append(
            FixedLimitEquivalenceCase(
                operating_condition_id=condition.id,
                rotor_mapping_equal=(
                    foldable.as_mapping() == fixed.as_mapping()
                ),
                thrust_delta_n=foldable.thrust_n - fixed.thrust_n,
                torque_delta_nm=foldable.torque_nm - fixed.torque_nm,
                thrust_coefficient_delta=(
                    foldable.thrust_coefficient - fixed.thrust_coefficient
                ),
                power_coefficient_delta=(
                    foldable.power_coefficient - fixed.power_coefficient
                ),
            )
        )
    return FixedLimitEquivalenceEvidence(state, tuple(cases))
