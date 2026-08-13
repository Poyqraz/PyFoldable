"""Canonical SI data models shared by future BEM, CAD, CFD, and FEA layers."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")


def _positive(name: str, value: float) -> None:
    _finite(name, value)
    if value <= 0.0:
        raise ValueError(f"{name} must be greater than zero.")


def _nonnegative(name: str, value: float) -> None:
    _finite(name, value)
    if value < 0.0:
        raise ValueError(f"{name} must be non-negative.")


@dataclass(frozen=True)
class OperatingCondition:
    """Atmosphere and shaft state; all values are canonical SI."""

    id: str
    angular_speed_rad_s: float
    forward_speed_m_s: float
    air_density_kg_m3: float
    dynamic_viscosity_pa_s: float
    temperature_k: float
    pressure_pa: float

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("OperatingCondition.id must not be empty.")
        _nonnegative("angular_speed_rad_s", self.angular_speed_rad_s)
        _finite("forward_speed_m_s", self.forward_speed_m_s)
        _positive("air_density_kg_m3", self.air_density_kg_m3)
        _positive("dynamic_viscosity_pa_s", self.dynamic_viscosity_pa_s)
        _positive("temperature_k", self.temperature_k)
        _positive("pressure_pa", self.pressure_pa)


@dataclass(frozen=True)
class AirfoilDefinition:
    """Named airfoil and optional normalized coordinate set."""

    id: str
    source: str
    coordinates: tuple[tuple[float, float], ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("AirfoilDefinition.id must not be empty.")
        for index, point in enumerate(self.coordinates):
            if len(point) != 2:
                raise ValueError(f"coordinates[{index}] must contain x and y.")
            _finite(f"coordinates[{index}].x", point[0])
            _finite(f"coordinates[{index}].y", point[1])


@dataclass(frozen=True)
class PolarTable:
    """One Reynolds/Mach polar table with radians as the canonical angle unit."""

    airfoil_id: str
    reynolds: float
    mach: float
    alpha_rad: tuple[float, ...]
    cl: tuple[float, ...]
    cd: tuple[float, ...]
    cm: tuple[float, ...]
    source: str
    scenario_id: str = "default"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.airfoil_id:
            raise ValueError("PolarTable.airfoil_id must not be empty.")
        if not self.source:
            raise ValueError("PolarTable.source must not be empty.")
        if not self.scenario_id:
            raise ValueError("PolarTable.scenario_id must not be empty.")
        _positive("reynolds", self.reynolds)
        _nonnegative("mach", self.mach)
        lengths = {len(self.alpha_rad), len(self.cl), len(self.cd), len(self.cm)}
        if len(lengths) != 1 or next(iter(lengths), 0) < 2:
            raise ValueError("Polar arrays must have the same length and at least two points.")
        if any(b <= a for a, b in zip(self.alpha_rad, self.alpha_rad[1:])):
            raise ValueError("alpha_rad must be strictly increasing.")
        for name, values in (
            ("alpha_rad", self.alpha_rad),
            ("cl", self.cl),
            ("cd", self.cd),
            ("cm", self.cm),
        ):
            for index, value in enumerate(values):
                _finite(f"{name}[{index}]", value)
        if any(value < 0.0 for value in self.cd):
            raise ValueError("cd values must be non-negative.")


@dataclass(frozen=True)
class BladeStation:
    """A radial blade definition at nondimensional radius r/R."""

    r_over_R: float
    chord_m: float
    twist_rad: float
    airfoil_id: str

    def __post_init__(self) -> None:
        _finite("r_over_R", self.r_over_R)
        if not 0.0 < self.r_over_R <= 1.0:
            raise ValueError("r_over_R must be in (0, 1].")
        _positive("chord_m", self.chord_m)
        _finite("twist_rad", self.twist_rad)
        if not self.airfoil_id:
            raise ValueError("BladeStation.airfoil_id must not be empty.")


@dataclass(frozen=True)
class BladeGeometry:
    """Open rotor geometry; lengths and angles use canonical SI."""

    diameter_m: float
    hub_radius_m: float
    blade_count: int
    stations: tuple[BladeStation, ...]

    def __post_init__(self) -> None:
        _positive("diameter_m", self.diameter_m)
        _nonnegative("hub_radius_m", self.hub_radius_m)
        if self.hub_radius_m >= self.radius_m:
            raise ValueError("hub_radius_m must be smaller than the blade radius.")
        if self.blade_count < 1:
            raise ValueError("blade_count must be at least one.")
        if len(self.stations) < 2:
            raise ValueError("BladeGeometry requires at least two stations.")
        radii = tuple(station.r_over_R for station in self.stations)
        if any(b <= a for a, b in zip(radii, radii[1:])):
            raise ValueError("Blade stations must be strictly increasing in r_over_R.")
        if radii[0] + 1.0e-12 < self.hub_radius_m / self.radius_m:
            raise ValueError("The first blade station cannot be inside the hub radius.")

    @property
    def radius_m(self) -> float:
        return self.diameter_m / 2.0


@dataclass(frozen=True)
class HingeGeometry:
    """Three-dimensional hinge definition for the movable blade segment."""

    radius_m: float
    axial_offset_m: float
    tangential_offset_m: float
    axis_azimuth_rad: float
    axis_elevation_rad: float
    stowed_angle_rad: float
    deployed_angle_rad: float
    stop_angle_rad: float

    def __post_init__(self) -> None:
        _positive("radius_m", self.radius_m)
        for name in (
            "axial_offset_m",
            "tangential_offset_m",
            "axis_azimuth_rad",
            "axis_elevation_rad",
            "stowed_angle_rad",
            "deployed_angle_rad",
            "stop_angle_rad",
        ):
            _finite(name, getattr(self, name))
        if self.stowed_angle_rad >= self.deployed_angle_rad:
            raise ValueError("stowed_angle_rad must be smaller than deployed_angle_rad.")
        if not self.stowed_angle_rad <= self.stop_angle_rad <= self.deployed_angle_rad:
            raise ValueError("stop_angle_rad must lie between stowed and deployed angles.")


@dataclass(frozen=True)
class MotorModel:
    """Minimal BLDC motor model expressed in SI units."""

    id: str
    kv_rad_s_per_v: float
    resistance_ohm: float
    no_load_current_a: float
    max_current_a: float
    max_power_w: float | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("MotorModel.id must not be empty.")
        _positive("kv_rad_s_per_v", self.kv_rad_s_per_v)
        _positive("resistance_ohm", self.resistance_ohm)
        _nonnegative("no_load_current_a", self.no_load_current_a)
        _positive("max_current_a", self.max_current_a)
        if self.max_power_w is not None:
            _positive("max_power_w", self.max_power_w)


@dataclass(frozen=True)
class MaterialModel:
    """Screening-level material card; anisotropy belongs in metadata/tests."""

    id: str
    density_kg_m3: float
    allowable_stress_pa: float | None = None
    elastic_modulus_pa: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("MaterialModel.id must not be empty.")
        _positive("density_kg_m3", self.density_kg_m3)
        if self.allowable_stress_pa is not None:
            _positive("allowable_stress_pa", self.allowable_stress_pa)
        if self.elastic_modulus_pa is not None:
            _positive("elastic_modulus_pa", self.elastic_modulus_pa)


@dataclass(frozen=True)
class ManufacturingModel:
    """Manufacturing constraints that influence CAD and optimization."""

    process: str
    min_wall_thickness_m: float
    min_trailing_edge_thickness_m: float
    build_orientation: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.process:
            raise ValueError("ManufacturingModel.process must not be empty.")
        _positive("min_wall_thickness_m", self.min_wall_thickness_m)
        _positive("min_trailing_edge_thickness_m", self.min_trailing_edge_thickness_m)
        if not self.build_orientation:
            raise ValueError("ManufacturingModel.build_orientation must not be empty.")


@dataclass(frozen=True)
class ValidationRecord:
    """One signed observation/prediction pair in a declared physical dimension."""

    id: str
    metric: str
    dimension: str
    observed_si: float
    source: str
    predicted_si: float | None = None
    uncertainty_si: float | None = None
    sign_convention: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.metric or not self.source:
            raise ValueError("ValidationRecord id, metric, and source must not be empty.")
        _finite("observed_si", self.observed_si)
        if self.predicted_si is not None:
            _finite("predicted_si", self.predicted_si)
        if self.uncertainty_si is not None:
            _nonnegative("uncertainty_si", self.uncertainty_si)


@dataclass(frozen=True)
class PropellerDesign:
    """Canonical design shared by all downstream analysis adapters."""

    id: str
    description: str
    blade: BladeGeometry
    airfoils: tuple[AirfoilDefinition, ...]
    operating_conditions: tuple[OperatingCondition, ...]
    hinge: HingeGeometry | None = None
    motor: MotorModel | None = None
    material: MaterialModel | None = None
    manufacturing: ManufacturingModel | None = None
    validation_records: tuple[ValidationRecord, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("PropellerDesign.id must not be empty.")
        airfoil_ids = [airfoil.id for airfoil in self.airfoils]
        if len(set(airfoil_ids)) != len(airfoil_ids):
            raise ValueError("AirfoilDefinition ids must be unique.")
        missing = {station.airfoil_id for station in self.blade.stations} - set(airfoil_ids)
        if missing:
            raise ValueError(f"Blade stations reference undefined airfoils: {sorted(missing)}.")
        condition_ids = [condition.id for condition in self.operating_conditions]
        if len(set(condition_ids)) != len(condition_ids):
            raise ValueError("OperatingCondition ids must be unique.")
        if self.hinge is not None and self.hinge.radius_m >= self.blade.radius_m:
            raise ValueError("Hinge radius must be inside the open blade radius.")


@dataclass(frozen=True)
class SimulationResult:
    """Solver-neutral result envelope with provenance and explicit SI fields."""

    design_id: str
    operating_condition_id: str
    solver_name: str
    solver_version: str
    git_commit: str
    converged: bool
    thrust_n: float | None = None
    torque_nm: float | None = None
    shaft_power_w: float | None = None
    polar_sources: tuple[str, ...] = ()
    model_options: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not all(
            (
                self.design_id,
                self.operating_condition_id,
                self.solver_name,
                self.solver_version,
                self.git_commit,
            )
        ):
            raise ValueError(
                "SimulationResult design, condition, solver, version, and git commit are required."
            )
        for name in ("thrust_n", "torque_nm", "shaft_power_w"):
            value = getattr(self, name)
            if value is not None:
                _finite(name, value)
