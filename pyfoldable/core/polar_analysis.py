"""Fail-closed, non-induced blade-section analysis using generated polars.

This is deliberately not a blade-element/momentum (BEM) solver.  It applies no
induction, swirl, Prandtl root/tip loss, dynamic-stall, or compressibility model.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Literal

from .models import OperatingCondition, PropellerDesign, SimulationResult
from .polar import PolarBoundsPolicy
from .polar_config import PolarFamilyConfig
from .polar_family_generation import PolarFamilyGenerationResult


POLAR_SECTION_ANALYSIS_SCHEMA_VERSION = 1


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

    def as_mapping(self) -> dict[str, object]:
        """Return a JSON-serializable diagnostic mapping."""
        return asdict(self)


@dataclass(frozen=True)
class PolarSectionAnalysisResult:
    """Section diagnostics and their standard solver-neutral result envelope."""

    sections: tuple[PolarSectionDiagnostic, ...]
    simulation_result: SimulationResult

    def as_mapping(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return {
            "sections": tuple(section.as_mapping() for section in self.sections),
            "simulation_result": asdict(self.simulation_result),
        }


def _reject_inconsistent_inputs(
    design: PropellerDesign,
    condition: OperatingCondition,
    generation: PolarFamilyGenerationResult,
    config: PolarFamilyConfig,
) -> None:
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
    if generation.family.airfoil_id != next(iter(airfoil_ids)):
        raise PolarSectionAnalysisError("Polar family airfoil does not match the design.")
    if generation.family.scenario_id != generation.plan.request_template.scenario_id:
        raise PolarSectionAnalysisError("Polar family scenario provenance is inconsistent.")


def analyze_generated_polar_sections(
    design: PropellerDesign,
    condition: OperatingCondition,
    generation: PolarFamilyGenerationResult,
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
    if not git_commit:
        raise PolarSectionAnalysisError("git_commit must not be empty.")
    _reject_inconsistent_inputs(design, condition, generation, polar_config)

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
        query = generation.family.query(
            alpha_rad=alpha, reynolds=reynolds, mach=mach, bounds=bounds
        )
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
    provenance = {
        "schema_version": POLAR_SECTION_ANALYSIS_SCHEMA_VERSION,
        "polar_config_sha256": polar_config.source_sha256,
        "polar_config_path": str(polar_config.source_path),
        "generation_batch": generation.as_mapping(),
        "polar_sources": sources,
        "clamped_dimensions": clamped,
    }
    simulation = SimulationResult(
        design_id=design.id, operating_condition_id=condition.id,
        solver_name="polar-section-analysis", solver_version="1",
        git_commit=git_commit, converged=True, thrust_n=thrust, torque_nm=torque,
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
