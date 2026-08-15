"""Fail-closed, non-induced blade-section analysis using generated polars.

This is deliberately not a blade-element/momentum (BEM) solver.  It applies no
induction, swirl, Prandtl root/tip loss, dynamic-stall, or compressibility model.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Literal, Mapping

from .models import OperatingCondition, PropellerDesign, SimulationResult
from .polar import PolarBoundsPolicy, PolarFamily, PolarInterpolationError
from .polar_config import PolarFamilyConfig
from .polar_family_generation import (
    PolarFamilyBatchResult,
    PolarFamilyGenerationResult,
)


POLAR_SECTION_ANALYSIS_SCHEMA_VERSION = 1
POLAR_SECTION_SOLVER_NAME = "polar-section-analysis"
POLAR_SECTION_SOLVER_VERSION = "1"

PolarFamilyProvenance = PolarFamilyGenerationResult | PolarFamilyBatchResult


class PolarSectionAnalysisError(ValueError):
    """Raised when section analysis inputs cannot be consumed safely."""


@dataclass(frozen=True)
class PolarSectionDiagnostic:
    """One station's kinematics, polar query, and distributed loads in SI."""

    station_index: int
    radius_m: float
    chord_m: float
    twist_rad: float
    tangential_speed_m_s: float
    relative_speed_m_s: float
    inflow_angle_rad: float
    alpha_rad: float
    reynolds: float
    mach: float
    cl: float
    cd: float
    lift_per_span_n_m: float
    drag_per_span_n_m: float
    axial_force_per_span_n_m: float
    torque_per_span_nm_m: float
    polar_sources: tuple[str, ...]
    interpolated_dimensions: tuple[str, ...]
    clamped_dimensions: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            isinstance(self.station_index, bool)
            or not isinstance(self.station_index, int)
            or self.station_index < 0
        ):
            raise ValueError("station_index must be a non-negative integer.")
        positive = {
            "radius_m",
            "chord_m",
            "relative_speed_m_s",
            "reynolds",
        }
        numeric_fields = (
            "radius_m",
            "chord_m",
            "twist_rad",
            "tangential_speed_m_s",
            "relative_speed_m_s",
            "inflow_angle_rad",
            "alpha_rad",
            "reynolds",
            "mach",
            "cl",
            "cd",
            "lift_per_span_n_m",
            "drag_per_span_n_m",
            "axial_force_per_span_n_m",
            "torque_per_span_nm_m",
        )
        for name in numeric_fields:
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise ValueError(f"{name} must be a finite number.")
            if name in positive and value <= 0.0:
                raise ValueError(f"{name} must be greater than zero.")
        if self.mach < 0.0 or self.cd < 0.0 or self.drag_per_span_n_m < 0.0:
            raise ValueError("Mach and drag values must be non-negative.")
        if not self.polar_sources or not all(self.polar_sources):
            raise ValueError("polar_sources must contain non-empty source names.")
        if len(set(self.polar_sources)) != len(self.polar_sources):
            raise ValueError("polar_sources must be unique and ordered.")
        allowed_dimensions = {"alpha_rad", "reynolds", "mach"}
        for name in ("interpolated_dimensions", "clamped_dimensions"):
            dimensions = getattr(self, name)
            if len(set(dimensions)) != len(dimensions) or not set(dimensions) <= (
                allowed_dimensions
            ):
                raise ValueError(f"{name} contains invalid or duplicate dimensions.")

    def as_mapping(self) -> dict[str, object]:
        """Return a JSON-serializable diagnostic mapping."""
        return asdict(self)


@dataclass(frozen=True)
class PolarSectionAnalysisResult:
    """Section diagnostics and their standard solver-neutral result envelope."""

    sections: tuple[PolarSectionDiagnostic, ...]
    simulation_result: SimulationResult

    def __post_init__(self) -> None:
        if len(self.sections) < 2 or not all(
            isinstance(section, PolarSectionDiagnostic) for section in self.sections
        ):
            raise ValueError("sections must contain at least two diagnostics.")
        if tuple(section.station_index for section in self.sections) != tuple(
            range(len(self.sections))
        ):
            raise ValueError("Section indices must be contiguous and zero-based.")
        radii = tuple(section.radius_m for section in self.sections)
        if any(upper <= lower for lower, upper in zip(radii, radii[1:])):
            raise ValueError("Section radii must be strictly increasing.")
        if not isinstance(self.simulation_result, SimulationResult):
            raise TypeError("simulation_result must be a SimulationResult.")
        if (
            self.simulation_result.solver_name != POLAR_SECTION_SOLVER_NAME
            or self.simulation_result.solver_version != POLAR_SECTION_SOLVER_VERSION
            or not self.simulation_result.converged
        ):
            raise ValueError("SimulationResult solver identity is inconsistent.")
        sources = tuple(dict.fromkeys(
            source for section in self.sections for source in section.polar_sources
        ))
        if self.simulation_result.polar_sources != sources:
            raise ValueError("SimulationResult polar sources do not match sections.")
        provenance = self.simulation_result.metadata.get("polar_provenance")
        if not isinstance(provenance, Mapping) or provenance.get("sections") != tuple(
            section.as_mapping() for section in self.sections
        ):
            raise ValueError("SimulationResult section provenance is inconsistent.")

    def as_mapping(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return {
            "sections": tuple(section.as_mapping() for section in self.sections),
            "simulation_result": asdict(self.simulation_result),
        }


def _reject_inconsistent_inputs(
    design: PropellerDesign,
    condition: OperatingCondition,
    generation: PolarFamilyProvenance,
    config: PolarFamilyConfig,
) -> PolarFamily:
    if not isinstance(design, PropellerDesign):
        raise TypeError("design must be a PropellerDesign.")
    if not isinstance(condition, OperatingCondition):
        raise TypeError("condition must be an OperatingCondition.")
    if not isinstance(
        generation, (PolarFamilyGenerationResult, PolarFamilyBatchResult)
    ):
        raise TypeError(
            "generation must be PolarFamilyGenerationResult or PolarFamilyBatchResult."
        )
    if not isinstance(config, PolarFamilyConfig):
        raise TypeError("config must be a PolarFamilyConfig.")
    airfoil_ids = {station.airfoil_id for station in design.blade.stations}
    if len(airfoil_ids) != 1:
        raise PolarSectionAnalysisError("Mixed-airfoil blade designs are unsupported.")
    if condition.forward_speed_m_s < 0.0:
        raise PolarSectionAnalysisError("Negative forward speed is unsupported.")
    if condition.angular_speed_rad_s <= 0.0:
        raise PolarSectionAnalysisError("Shaft speed must be greater than zero.")
    if condition not in design.operating_conditions:
        raise PolarSectionAnalysisError(
            "Operating condition does not belong to the supplied design."
        )
    if generation.plan != config.plan:
        raise PolarSectionAnalysisError(
            "Generation plan does not match polar configuration provenance."
        )
    family = generation.family
    if family is None:
        raise PolarSectionAnalysisError(
            "Generation batch did not materialize a safe rectangular family."
        )
    if family.airfoil_id != next(iter(airfoil_ids)):
        raise PolarSectionAnalysisError("Polar family airfoil does not match the design.")
    if family.scenario_id != generation.plan.request_template.scenario_id:
        raise PolarSectionAnalysisError("Polar family scenario provenance is inconsistent.")
    return family


def analyze_generated_polar_sections(
    design: PropellerDesign,
    condition: OperatingCondition,
    generation: PolarFamilyProvenance,
    polar_config: PolarFamilyConfig,
    *,
    bounds: PolarBoundsPolicy = "error",
    git_commit: str,
) -> PolarSectionAnalysisResult:
    """Integrate quasi-steady section loads from a generated ``PolarFamily``.

    Only the radial interval bounded by the first and last declared stations is
    integrated, using the trapezoidal rule, then multiplied by ``blade_count``.
    This is a non-induced section model, not a complete BEM implementation.
    """
    if bounds not in {"error", "clamp"}:
        raise PolarSectionAnalysisError(f"Unsupported bounds policy {bounds!r}.")
    if not isinstance(git_commit, str) or not git_commit.strip():
        raise PolarSectionAnalysisError("git_commit must not be empty.")
    family = _reject_inconsistent_inputs(design, condition, generation, polar_config)

    speed_of_sound = math.sqrt(1.4 * 287.05287 * condition.temperature_k)
    sections: list[PolarSectionDiagnostic] = []
    warnings: list[str] = []
    for index, station in enumerate(design.blade.stations):
        radius = station.r_over_R * design.blade.radius_m
        tangential = condition.angular_speed_rad_s * radius
        relative = math.hypot(tangential, condition.forward_speed_m_s)
        inflow = math.atan2(condition.forward_speed_m_s, tangential)
        alpha = station.twist_rad - inflow
        reynolds = (
            condition.air_density_kg_m3
            * relative
            * station.chord_m
            / condition.dynamic_viscosity_pa_s
        )
        mach = relative / speed_of_sound
        try:
            query = family.query(
                alpha_rad=alpha, reynolds=reynolds, mach=mach, bounds=bounds
            )
        except PolarInterpolationError as error:
            raise PolarSectionAnalysisError(
                f"Station {index} at r/R={station.r_over_R:g} cannot be resolved: "
                f"{error}"
            ) from error
        if query.clamped_dimensions:
            warnings.append(
                f"station {index} polar query clamped: "
                + ", ".join(query.clamped_dimensions)
            )
        dynamic_pressure = 0.5 * condition.air_density_kg_m3 * relative**2
        lift = dynamic_pressure * station.chord_m * query.cl
        drag = dynamic_pressure * station.chord_m * query.cd
        axial = lift * math.cos(inflow) - drag * math.sin(inflow)
        torque = radius * (lift * math.sin(inflow) + drag * math.cos(inflow))
        values = (relative, reynolds, mach, lift, drag, axial, torque)
        if not all(math.isfinite(value) for value in values):
            raise PolarSectionAnalysisError("Section calculation produced non-finite output.")
        sections.append(PolarSectionDiagnostic(
            station_index=index, radius_m=radius, chord_m=station.chord_m,
            twist_rad=station.twist_rad, tangential_speed_m_s=tangential,
            relative_speed_m_s=relative, inflow_angle_rad=inflow, alpha_rad=alpha,
            reynolds=reynolds, mach=mach, cl=query.cl, cd=query.cd,
            lift_per_span_n_m=lift, drag_per_span_n_m=drag,
            axial_force_per_span_n_m=axial, torque_per_span_nm_m=torque,
            polar_sources=query.sources,
            interpolated_dimensions=query.interpolated_dimensions,
            clamped_dimensions=query.clamped_dimensions,
        ))

    def integrate(field: Literal["axial_force_per_span_n_m", "torque_per_span_nm_m"]) -> float:
        return design.blade.blade_count * sum(
            0.5 * (getattr(left, field) + getattr(right, field))
            * (right.radius_m - left.radius_m)
            for left, right in zip(sections, sections[1:])
        )

    thrust = integrate("axial_force_per_span_n_m")
    torque = integrate("torque_per_span_nm_m")
    sources = tuple(dict.fromkeys(
        source for section in sections for source in section.polar_sources
    ))
    clamped = tuple(sorted({
        dimension for section in sections for dimension in section.clamped_dimensions
    }))
    batch_complete = (
        generation.complete
        if isinstance(generation, PolarFamilyBatchResult)
        else True
    )
    if isinstance(generation, PolarFamilyBatchResult) and not generation.complete:
        warnings.append(
            "Analysis used an explicitly materialized partial polar-family sub-grid."
        )
    first_radius = sections[0].radius_m
    last_radius = sections[-1].radius_m
    if (
        first_radius > design.blade.hub_radius_m + 1.0e-12
        or last_radius < design.blade.radius_m - 1.0e-12
    ):
        warnings.append(
            "Loads outside the first/last declared blade station were not estimated."
        )
    provenance = {
        "schema_version": POLAR_SECTION_ANALYSIS_SCHEMA_VERSION,
        "polar_config_sha256": polar_config.source_sha256,
        "polar_config_path": str(polar_config.source_path),
        "generation_batch": generation.as_mapping(),
        "generation_complete": batch_complete,
        "polar_sources": sources,
        "clamped_dimensions": clamped,
        "integration_radius_m": (first_radius, last_radius),
        "sections": tuple(section.as_mapping() for section in sections),
    }
    simulation = SimulationResult(
        design_id=design.id, operating_condition_id=condition.id,
        solver_name=POLAR_SECTION_SOLVER_NAME,
        solver_version=POLAR_SECTION_SOLVER_VERSION,
        git_commit=git_commit.strip(), converged=True, thrust_n=thrust, torque_nm=torque,
        shaft_power_w=torque * condition.angular_speed_rad_s,
        polar_sources=sources,
        model_options={
            "bounds": bounds, "induction": False, "swirl": False,
            "prandtl_root_tip_loss": False, "dynamic_stall": False,
            "compressibility_correction": False,
            "integration": "trapezoidal_first_to_last_station",
        },
        warnings=tuple(warnings), metadata={"polar_provenance": provenance},
    )
    return PolarSectionAnalysisResult(tuple(sections), simulation)
