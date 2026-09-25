"""Planar projected-force to material-load adapter, screening only.

This is the CMM-2 aerodynamic-load prerequisite. It does not couple a
transient, does not modify BEM, and does not establish folded-tip
aerodynamics.

Model ``planar_projected_material_load_v1`` keeps the existing
``radial_cosine_v1`` screen. For one movable tip at hinge radius ``R`` and
material distance ``s`` from the hinge:

    r_p(s) = R + s cos(theta)
    dr_p/ds = cos(theta)

with ``|theta| < pi/2`` and a strictly positive projection factor. ``s`` is
``(r_p - R) / cos(theta)``. v1 keeps this projected radius. It does not
replace it with the shaft-axis distance of the same planar point.

Whole-rotor BEM densities are per projected radial metre and already include
``blade_count``:

    T = differential_thrust_n_m          # N / m_projected
    D = differential_torque_nm_m         # N·m / m_projected

One blade of ``N`` identical blades, per material metre, on the basis
``e_z`` and ``e_t(phi)`` (not the folded section basis):

    f_z = (T / N) cos(theta)
    f_t = -(D / (N r_p)) cos(theta)
    f_r = 0

The cosine is the Jacobian ``dr_p/ds``. It is not inverted. Distributed
aerodynamic couple is none: sectional ``Cm`` is not a ``+z`` hinge term.

Generalized loads are virtual work, ``q = integral f · x_(coord) ds``.
``x_phi · e_z = 0`` and ``x_theta · e_z = 0``, so thrust does no planar ``+z``
work. ``x_phi · e_t(phi) = r_p``, therefore

    f · x_phi = -(D / N) cos(theta)
    q_phi,1 = integral f · x_phi ds = -(D / N) (b - a)

on a projected midpoint cell ``a <= r_p <= b``. For movable material
``a >= R > 0``, ``s = (r_p - R) / cos(theta)`` and ``ds = dr_p / cos(theta)``
give

    q_theta,1 = -(D / N) [(b - a) - R ln(b / a)]

Positive resisting ``D`` makes both generalized loads negative: shaft load
opposes ``+z``, and the deployed movable tip is driven toward negative
``theta``. Stations with ``r_p <= R`` are fixed to the shaft. They add to
``q_phi`` and add exactly zero to the one-tip hinge load. A midpoint cell
that straddles ``R`` is split into ``[a, R]`` and ``[R, b]`` with the same
``T`` and ``D``; no BEM re-solve is performed.

Whole-rotor shaft load is the negation of the partitioned cell resisting
torques, summed in source order with ``math.fsum``. It is not
``blade_count`` times an already whole-rotor BEM torque. Published resisting
shaft torque is the negation of that generalized shaft load.

``hinge_rate_rad_s`` is recorded and may enter the screening power diagnostic

    P_aero = Q_phi,aero * omega + N * q_theta,1 * theta_dot

The v1 force law ignores ``theta_dot``. A failed map raises
:class:`PlanarProjectedMaterialLoadError`. It does not publish a zero hinge
load.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .foldable_rotor import FoldableBEMRotorResult


LOAD_MAPPING_MODEL = "planar_projected_material_load_v1"
PROJECTION_MODEL = "radial_cosine_v1"
QUALIFICATION = "screening_only_projected_rate_independent"
DISTRIBUTED_COUPLE_MODEL = "none"
HINGE_RATE_AERODYNAMIC_MODEL = "ignored_rate_independent_quasi_steady"
SECTIONAL_AERODYNAMIC_COUPLE = "excluded_in_v1"
PLANAR_PROJECTED_MATERIAL_LOAD_SCHEMA_VERSION = 1

_MIN_PROJECTION_FACTOR = 1.0e-12
_FIXED_ROOT = "fixed_root"
_MOVABLE_TIP = "movable_tip"


class PlanarProjectedMaterialLoadError(ValueError):
    """Fail-closed planar projected material-load mapping error.

    A missing hinge load is unknown. Callers must not treat this as zero.
    """


def _real(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanarProjectedMaterialLoadError(f"{name} must be a real number.")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise PlanarProjectedMaterialLoadError(f"{name} must be finite.")
    return numeric


def _blade_count(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PlanarProjectedMaterialLoadError(
            "blade_count must be an integer greater than or equal to 1."
        )
    return value


def _projection_factor(theta_rad: float) -> float:
    theta = _real("theta_rad", theta_rad)
    if abs(theta) >= 0.5 * math.pi:
        raise PlanarProjectedMaterialLoadError(
            "projection is invalid: |theta| must be strictly below pi/2."
        )
    factor = math.cos(theta)
    if (
        not math.isfinite(factor)
        or factor <= _MIN_PROJECTION_FACTOR
        or factor > 1.0 + 1.0e-12
    ):
        raise PlanarProjectedMaterialLoadError(
            "projection factor is invalid for radial_cosine_v1."
        )
    return factor


def _positive_radius(name: str, value: float) -> float:
    radius = _real(name, value)
    if radius <= 0.0:
        raise PlanarProjectedMaterialLoadError(f"{name} must be positive.")
    return radius


def projected_radius_m(
    material_distance_m: float,
    *,
    hinge_radius_m: float,
    theta_rad: float,
) -> float:
    """Return ``r_p = R + s cos(theta)`` inside the declared projection domain."""
    factor = _projection_factor(theta_rad)
    hinge_radius = _positive_radius("hinge_radius_m", hinge_radius_m)
    material_distance = _real("material_distance_m", material_distance_m)
    if material_distance < 0.0:
        raise PlanarProjectedMaterialLoadError(
            "material distance from the hinge must be non-negative."
        )
    radius = hinge_radius + material_distance * factor
    if radius <= 0.0:
        raise PlanarProjectedMaterialLoadError(
            "non-positive projected radius in a mapped movable interval."
        )
    return radius


def one_blade_material_force_density_n_per_m(
    material_distance_m: float,
    *,
    hinge_radius_m: float,
    theta_rad: float,
    blade_count: int,
    differential_thrust_n_m: float,
    differential_torque_nm_m: float,
) -> tuple[float, float, float]:
    """Return ``(f_z, f_t, f_r)`` in newton per material metre for one blade.

    ``f_r`` is identically zero. The cosine factor converts projected-radial
    BEM densities into material-metre densities. ``theta_dot`` is not an input.
    """
    factor = _projection_factor(theta_rad)
    hinge_radius = _positive_radius("hinge_radius_m", hinge_radius_m)
    count = _blade_count(blade_count)
    material_distance = _real("material_distance_m", material_distance_m)
    if material_distance < 0.0:
        raise PlanarProjectedMaterialLoadError(
            "material distance from the hinge must be non-negative."
        )
    thrust_density = _real("differential_thrust_n_m", differential_thrust_n_m)
    torque_density = _real("differential_torque_nm_m", differential_torque_nm_m)
    projected = hinge_radius + material_distance * factor
    if projected <= 0.0:
        raise PlanarProjectedMaterialLoadError(
            "non-positive projected radius in a mapped movable interval."
        )
    f_z = (thrust_density / count) * factor
    f_t = -(torque_density / (count * projected)) * factor
    return (f_z, f_t, 0.0)


def aerodynamic_generalized_power_w(
    *,
    whole_rotor_shaft_generalized_load_nm: float,
    one_tip_hinge_generalized_torque_nm: float,
    blade_count: int,
    omega_rad_s: float,
    hinge_rate_rad_s: float,
) -> float:
    """Screening power ``Q_phi,aero * omega + N * q_theta,1 * theta_dot``.

    This is not ``-Q_a * omega`` when the hinge rate is nonzero. The force law
    does not depend on the recorded hinge rate.
    """
    shaft_load = _real(
        "whole_rotor_shaft_generalized_load_nm",
        whole_rotor_shaft_generalized_load_nm,
    )
    hinge_load = _real(
        "one_tip_hinge_generalized_torque_nm",
        one_tip_hinge_generalized_torque_nm,
    )
    count = _blade_count(blade_count)
    omega = _real("omega_rad_s", omega_rad_s)
    hinge_rate = _real("hinge_rate_rad_s", hinge_rate_rad_s)
    return shaft_load * omega + count * hinge_load * hinge_rate


@dataclass(frozen=True)
class ProjectedAnnulusLoad:
    """One whole-rotor midpoint cell in the projected radial coordinate."""

    inner_radius_m: float
    outer_radius_m: float
    differential_thrust_n_m: float
    differential_torque_nm_m: float
    geometry_extrapolated: bool = False
    source_index: int = 0


@dataclass(frozen=True)
class MappedRadialContribution:
    """Fixed-root or movable-tip piece of one projected midpoint cell."""

    role: str
    source_index: int
    inner_projected_radius_m: float
    outer_projected_radius_m: float
    source_differential_thrust_n_m: float
    source_differential_torque_nm_m: float
    whole_rotor_thrust_n: float
    whole_rotor_resisting_torque_nm: float
    one_blade_shaft_generalized_load_nm: float
    one_tip_hinge_generalized_torque_nm: float
    geometry_extrapolated: bool

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "role": self.role,
            "source_index": self.source_index,
            "inner_projected_radius_m": self.inner_projected_radius_m,
            "outer_projected_radius_m": self.outer_projected_radius_m,
            "source_differential_thrust_n_m": self.source_differential_thrust_n_m,
            "source_differential_torque_nm_m": (
                self.source_differential_torque_nm_m
            ),
            "thrust_density_measure": (
                "whole_rotor_newton_per_projected_radial_metre"
            ),
            "torque_density_measure": (
                "whole_rotor_newton_metre_per_projected_radial_metre"
            ),
            "whole_rotor_thrust_n": self.whole_rotor_thrust_n,
            "whole_rotor_resisting_torque_nm": (
                self.whole_rotor_resisting_torque_nm
            ),
            "one_blade_shaft_generalized_load_nm": (
                self.one_blade_shaft_generalized_load_nm
            ),
            "one_tip_hinge_generalized_torque_nm": (
                self.one_tip_hinge_generalized_torque_nm
            ),
            "geometry_extrapolated": self.geometry_extrapolated,
        }


@dataclass(frozen=True)
class PlanarProjectedMaterialLoadResult:
    """Auditable v1 map from a projected BEM field to planar generalized loads."""

    schema_version: int
    load_mapping_model: str
    projection_model: str
    qualification: str
    physical_qualification: bool
    distributed_couple_model: str
    hinge_rate_aerodynamic_model: str
    sectional_aerodynamic_couple: str
    blade_count: int
    hinge_radius_m: float
    theta_rad: float
    hinge_rate_rad_s: float
    projection_factor: float
    projected_tip_radius_m: float
    operating_condition_id: str
    bem_settings: Mapping[str, Any]
    polar_schedule_id: str | None
    airfoil_id: str
    scenario_id: str
    polar_sources: tuple[str, ...]
    radial_domain: str
    geometry_extended: bool
    source_inner_projected_radius_m: float
    source_outer_projected_radius_m: float
    intervals: tuple[MappedRadialContribution, ...]
    source_whole_rotor_projected_thrust_n: float
    source_whole_rotor_resisting_torque_nm: float
    whole_rotor_aerodynamic_shaft_generalized_load_nm: float
    resisting_shaft_torque_nm: float
    one_tip_hinge_generalized_torque_nm: float
    synchronous_n_times_one_tip_hinge_generalized_torque_nm: float

    def __post_init__(self) -> None:
        if self.schema_version != PLANAR_PROJECTED_MATERIAL_LOAD_SCHEMA_VERSION:
            raise PlanarProjectedMaterialLoadError("Unexpected schema version.")
        if self.load_mapping_model != LOAD_MAPPING_MODEL:
            raise PlanarProjectedMaterialLoadError("Unexpected load-mapping model.")
        if self.projection_model != PROJECTION_MODEL:
            raise PlanarProjectedMaterialLoadError("Unexpected projection model.")
        if self.qualification != QUALIFICATION:
            raise PlanarProjectedMaterialLoadError("Unexpected qualification.")
        if self.physical_qualification is not False:
            raise PlanarProjectedMaterialLoadError(
                "physical_qualification must be false."
            )
        if self.distributed_couple_model != DISTRIBUTED_COUPLE_MODEL:
            raise PlanarProjectedMaterialLoadError(
                "distributed aerodynamic couple must be none."
            )
        if self.hinge_rate_aerodynamic_model != HINGE_RATE_AERODYNAMIC_MODEL:
            raise PlanarProjectedMaterialLoadError(
                "hinge-rate aerodynamic model must stay rate-independent."
            )
        if self.sectional_aerodynamic_couple != SECTIONAL_AERODYNAMIC_COUPLE:
            raise PlanarProjectedMaterialLoadError(
                "sectional aerodynamic couple must stay excluded in v1."
            )
        if not self.operating_condition_id:
            raise PlanarProjectedMaterialLoadError(
                "operating_condition_id must not be empty."
            )
        if not self.intervals:
            raise PlanarProjectedMaterialLoadError(
                "mapped load requires at least one interval."
            )

    def aerodynamic_generalized_power_w(self, omega_rad_s: float) -> float:
        """Screening power at ``omega`` using the recorded hinge rate."""
        return aerodynamic_generalized_power_w(
            whole_rotor_shaft_generalized_load_nm=(
                self.whole_rotor_aerodynamic_shaft_generalized_load_nm
            ),
            one_tip_hinge_generalized_torque_nm=(
                self.one_tip_hinge_generalized_torque_nm
            ),
            blade_count=self.blade_count,
            omega_rad_s=omega_rad_s,
            hinge_rate_rad_s=self.hinge_rate_rad_s,
        )

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "schema_version": self.schema_version,
            "load_mapping_model": self.load_mapping_model,
            "projection_model": self.projection_model,
            "qualification": self.qualification,
            "physical_qualification": self.physical_qualification,
            "distributed_couple_model": self.distributed_couple_model,
            "hinge_rate_aerodynamic_model": self.hinge_rate_aerodynamic_model,
            "sectional_aerodynamic_couple": self.sectional_aerodynamic_couple,
            "blade_count": self.blade_count,
            "hinge_radius_m": self.hinge_radius_m,
            "theta_rad": self.theta_rad,
            "hinge_rate_rad_s": self.hinge_rate_rad_s,
            "projection_factor": self.projection_factor,
            "projected_tip_radius_m": self.projected_tip_radius_m,
            "operating_condition_id": self.operating_condition_id,
            "bem_settings": dict(self.bem_settings),
            "polar_schedule_id": self.polar_schedule_id,
            "airfoil_id": self.airfoil_id,
            "scenario_id": self.scenario_id,
            "polar_sources": list(self.polar_sources),
            "radial_domain": self.radial_domain,
            "geometry_extended": self.geometry_extended,
            "source_inner_projected_radius_m": (
                self.source_inner_projected_radius_m
            ),
            "source_outer_projected_radius_m": (
                self.source_outer_projected_radius_m
            ),
            "thrust_density_measure": (
                "whole_rotor_newton_per_projected_radial_metre"
            ),
            "torque_density_measure": (
                "whole_rotor_newton_metre_per_projected_radial_metre"
            ),
            "material_force_density_measure": (
                "one_blade_newton_per_material_metre"
            ),
            "force_basis": "e_z_and_e_t_phi",
            "intervals": [dict(interval.as_mapping()) for interval in self.intervals],
            "source_whole_rotor_projected_thrust_n": (
                self.source_whole_rotor_projected_thrust_n
            ),
            "source_whole_rotor_resisting_torque_nm": (
                self.source_whole_rotor_resisting_torque_nm
            ),
            "whole_rotor_aerodynamic_shaft_generalized_load_nm": (
                self.whole_rotor_aerodynamic_shaft_generalized_load_nm
            ),
            "resisting_shaft_torque_nm": self.resisting_shaft_torque_nm,
            "one_tip_hinge_generalized_torque_nm": (
                self.one_tip_hinge_generalized_torque_nm
            ),
            "synchronous_n_times_one_tip_hinge_generalized_torque_nm": (
                self.synchronous_n_times_one_tip_hinge_generalized_torque_nm
            ),
        }


def _spans(
    inner: float, outer: float, hinge_radius: float
) -> tuple[tuple[str, float, float], ...]:
    if outer <= hinge_radius:
        return ((_FIXED_ROOT, inner, outer),)
    if inner >= hinge_radius:
        return ((_MOVABLE_TIP, inner, outer),)
    return (
        (_FIXED_ROOT, inner, hinge_radius),
        (_MOVABLE_TIP, hinge_radius, outer),
    )


def _generalized_loads(
    *,
    role: str,
    inner: float,
    outer: float,
    torque_density: float,
    hinge_radius: float,
    blade_count: int,
) -> tuple[float, float]:
    width = outer - inner
    q_phi = -(torque_density / blade_count) * width
    if role == _FIXED_ROOT:
        return q_phi, 0.0
    if inner <= 0.0 or outer <= 0.0:
        raise PlanarProjectedMaterialLoadError(
            "non-positive projected radius in a mapped movable interval."
        )
    q_theta = -(torque_density / blade_count) * (
        width - hinge_radius * math.log(outer / inner)
    )
    return q_phi, q_theta


def map_projected_annulus(
    load: ProjectedAnnulusLoad,
    *,
    hinge_radius_m: float,
    theta_rad: float,
    blade_count: int,
) -> tuple[MappedRadialContribution, ...]:
    """Map one midpoint cell, splitting it when it straddles the hinge.

    This does not advertise a full-span hinge load. Use
    :func:`map_projected_material_loads` before publishing
    ``one_tip_hinge_generalized_torque_nm`` for a rotor.
    """
    if not isinstance(load, ProjectedAnnulusLoad):
        raise PlanarProjectedMaterialLoadError(
            "load must be a ProjectedAnnulusLoad."
        )
    _projection_factor(theta_rad)
    hinge_radius = _positive_radius("hinge_radius_m", hinge_radius_m)
    count = _blade_count(blade_count)
    inner = _real("inner_radius_m", load.inner_radius_m)
    outer = _real("outer_radius_m", load.outer_radius_m)
    thrust_density = _real(
        "differential_thrust_n_m", load.differential_thrust_n_m
    )
    torque_density = _real(
        "differential_torque_nm_m", load.differential_torque_nm_m
    )
    if not isinstance(load.geometry_extrapolated, bool):
        raise PlanarProjectedMaterialLoadError(
            "geometry_extrapolated must be boolean."
        )
    if isinstance(load.source_index, bool) or not isinstance(load.source_index, int):
        raise PlanarProjectedMaterialLoadError("source_index must be an integer.")
    if inner <= 0.0 or outer <= 0.0:
        raise PlanarProjectedMaterialLoadError(
            "projected radii must be positive."
        )
    if outer <= inner:
        raise PlanarProjectedMaterialLoadError(
            "projected interval width must be positive."
        )
    spans = _spans(inner, outer, hinge_radius)
    cell_width = outer - inner
    cell_thrust = thrust_density * cell_width
    cell_torque = torque_density * cell_width
    raw_thrust = [thrust_density * (end - start) for _, start, end in spans]
    raw_torque = [torque_density * (end - start) for _, start, end in spans]
    if len(spans) == 2:
        # Keep the original midpoint cell integral. The outer piece absorbs
        # the rounding residual so the pieces reconstruct that cell.
        raw_thrust[1] = cell_thrust - raw_thrust[0]
        raw_torque[1] = cell_torque - raw_torque[0]
    contributions: list[MappedRadialContribution] = []
    for (role, start, end), thrust_n, torque_nm in zip(spans, raw_thrust, raw_torque):
        if end <= start:
            raise PlanarProjectedMaterialLoadError(
                "projected interval width must be positive."
            )
        if role == _MOVABLE_TIP and (start <= 0.0 or end <= 0.0):
            raise PlanarProjectedMaterialLoadError(
                "non-positive projected radius in a mapped movable interval."
            )
        q_phi, q_theta = _generalized_loads(
            role=role,
            inner=start,
            outer=end,
            torque_density=torque_density,
            hinge_radius=hinge_radius,
            blade_count=count,
        )
        contributions.append(
            MappedRadialContribution(
                role=role,
                source_index=load.source_index,
                inner_projected_radius_m=start,
                outer_projected_radius_m=end,
                source_differential_thrust_n_m=thrust_density,
                source_differential_torque_nm_m=torque_density,
                whole_rotor_thrust_n=thrust_n,
                whole_rotor_resisting_torque_nm=torque_nm,
                one_blade_shaft_generalized_load_nm=q_phi,
                one_tip_hinge_generalized_torque_nm=q_theta,
                geometry_extrapolated=load.geometry_extrapolated,
            )
        )
    return tuple(contributions)


def _contiguous(annuli: Sequence[ProjectedAnnulusLoad]) -> None:
    for previous, following in zip(annuli, annuli[1:]):
        if following.inner_radius_m < previous.outer_radius_m:
            raise PlanarProjectedMaterialLoadError(
                "projected intervals overlap; the source domain is not a "
                "continuous integration domain."
            )
        if following.inner_radius_m > previous.outer_radius_m:
            raise PlanarProjectedMaterialLoadError(
                "projected intervals have a gap; the source domain is not a "
                "continuous integration domain."
            )
        if following.inner_radius_m != previous.outer_radius_m:
            raise PlanarProjectedMaterialLoadError(
                "projected intervals must meet exactly on a continuous "
                "integration domain."
            )


def map_projected_material_loads(
    annuli: Sequence[ProjectedAnnulusLoad],
    *,
    hinge_radius_m: float,
    theta_rad: float,
    blade_count: int,
    hinge_rate_rad_s: float,
    projected_tip_radius_m: float,
    operating_condition_id: str,
    bem_settings: Mapping[str, Any] | None = None,
    polar_schedule_id: str | None = None,
    airfoil_id: str = "",
    scenario_id: str = "",
    polar_sources: Sequence[str] = (),
    radial_domain: str = "declared_intervals",
    geometry_extended: bool = False,
) -> PlanarProjectedMaterialLoadResult:
    """Map a continuous projected field and fail closed on partial tip coverage."""
    factor = _projection_factor(theta_rad)
    theta = _real("theta_rad", theta_rad)
    hinge_radius = _positive_radius("hinge_radius_m", hinge_radius_m)
    count = _blade_count(blade_count)
    hinge_rate = _real("hinge_rate_rad_s", hinge_rate_rad_s)
    projected_tip = _positive_radius("projected_tip_radius_m", projected_tip_radius_m)
    if not operating_condition_id or not isinstance(operating_condition_id, str):
        raise PlanarProjectedMaterialLoadError(
            "operating_condition_id must be a non-empty string."
        )
    if polar_schedule_id is not None and not isinstance(polar_schedule_id, str):
        raise PlanarProjectedMaterialLoadError(
            "polar_schedule_id must be a string or None."
        )
    if not isinstance(airfoil_id, str) or not isinstance(scenario_id, str):
        raise PlanarProjectedMaterialLoadError(
            "airfoil_id and scenario_id must be strings."
        )
    if not isinstance(radial_domain, str) or not radial_domain:
        raise PlanarProjectedMaterialLoadError(
            "radial_domain must be a non-empty string."
        )
    if not isinstance(geometry_extended, bool):
        raise PlanarProjectedMaterialLoadError(
            "geometry_extended must be boolean."
        )
    if bem_settings is None:
        settings: Mapping[str, Any] = {}
    elif isinstance(bem_settings, Mapping):
        settings = dict(bem_settings)
    else:
        raise PlanarProjectedMaterialLoadError("bem_settings must be a mapping.")
    if not isinstance(polar_sources, Sequence) or isinstance(polar_sources, (str, bytes)):
        raise PlanarProjectedMaterialLoadError(
            "polar_sources must be a sequence of strings."
        )
    sources = tuple(polar_sources)
    if not all(isinstance(source, str) for source in sources):
        raise PlanarProjectedMaterialLoadError(
            "polar_sources must be a sequence of strings."
        )
    cells = tuple(annuli)
    if not cells or not all(isinstance(cell, ProjectedAnnulusLoad) for cell in cells):
        raise PlanarProjectedMaterialLoadError(
            "annuli must contain at least one ProjectedAnnulusLoad."
        )
    if projected_tip <= hinge_radius:
        raise PlanarProjectedMaterialLoadError(
            "hinge radius lies outside the projected blade domain required "
            "for the movable-tip map."
        )
    _contiguous(cells)
    if cells[0].inner_radius_m > hinge_radius:
        raise PlanarProjectedMaterialLoadError(
            "movable-span coverage is incomplete: integration starts outboard "
            "of the hinge radius."
        )
    if cells[-1].outer_radius_m < projected_tip:
        raise PlanarProjectedMaterialLoadError(
            "movable-span coverage is incomplete: integration ends inboard "
            "of the projected tip."
        )
    pieces: list[MappedRadialContribution] = []
    for cell in cells:
        pieces.extend(
            map_projected_annulus(
                cell,
                hinge_radius_m=hinge_radius,
                theta_rad=theta,
                blade_count=count,
            )
        )
    resisting = math.fsum(
        piece.whole_rotor_resisting_torque_nm for piece in pieces
    )
    thrust = math.fsum(piece.whole_rotor_thrust_n for piece in pieces)
    one_tip = math.fsum(
        piece.one_tip_hinge_generalized_torque_nm for piece in pieces
    )
    shaft_generalized = -resisting
    return PlanarProjectedMaterialLoadResult(
        schema_version=PLANAR_PROJECTED_MATERIAL_LOAD_SCHEMA_VERSION,
        load_mapping_model=LOAD_MAPPING_MODEL,
        projection_model=PROJECTION_MODEL,
        qualification=QUALIFICATION,
        physical_qualification=False,
        distributed_couple_model=DISTRIBUTED_COUPLE_MODEL,
        hinge_rate_aerodynamic_model=HINGE_RATE_AERODYNAMIC_MODEL,
        sectional_aerodynamic_couple=SECTIONAL_AERODYNAMIC_COUPLE,
        blade_count=count,
        hinge_radius_m=hinge_radius,
        theta_rad=theta,
        hinge_rate_rad_s=hinge_rate,
        projection_factor=factor,
        projected_tip_radius_m=projected_tip,
        operating_condition_id=operating_condition_id,
        bem_settings=settings,
        polar_schedule_id=polar_schedule_id,
        airfoil_id=airfoil_id,
        scenario_id=scenario_id,
        polar_sources=sources,
        radial_domain=radial_domain,
        geometry_extended=geometry_extended,
        source_inner_projected_radius_m=cells[0].inner_radius_m,
        source_outer_projected_radius_m=cells[-1].outer_radius_m,
        intervals=tuple(pieces),
        source_whole_rotor_projected_thrust_n=thrust,
        source_whole_rotor_resisting_torque_nm=resisting,
        whole_rotor_aerodynamic_shaft_generalized_load_nm=shaft_generalized,
        resisting_shaft_torque_nm=-shaft_generalized,
        one_tip_hinge_generalized_torque_nm=one_tip,
        synchronous_n_times_one_tip_hinge_generalized_torque_nm=count * one_tip,
    )


def map_foldable_bem_aero_loads(
    result: FoldableBEMRotorResult,
    *,
    hinge_rate_rad_s: float,
) -> PlanarProjectedMaterialLoadResult:
    """Map an existing foldable BEM result without resolving BEM or CMM-1."""
    if not isinstance(result, FoldableBEMRotorResult):
        raise PlanarProjectedMaterialLoadError(
            "result must be a FoldableBEMRotorResult."
        )
    hinge_rate = _real("hinge_rate_rad_s", hinge_rate_rad_s)
    state = result.geometry.state
    theta = state.angle_from_deployed_rad
    factor = _projection_factor(theta)
    if result.geometry.projection_factor != factor:
        raise PlanarProjectedMaterialLoadError(
            "foldable projection factor does not match radial_cosine_v1."
        )
    nominal = result.geometry.nominal_blade
    effective = result.geometry.effective_blade
    if nominal.blade_count != effective.blade_count:
        raise PlanarProjectedMaterialLoadError(
            "nominal and effective blade counts differ."
        )
    rotor = result.rotor_result
    annuli = tuple(
        ProjectedAnnulusLoad(
            inner_radius_m=element.inner_radius_m,
            outer_radius_m=element.outer_radius_m,
            differential_thrust_n_m=element.solution.differential_thrust_n_m,
            differential_torque_nm_m=element.solution.differential_torque_nm_m,
            geometry_extrapolated=element.geometry_extrapolated,
            source_index=element.index,
        )
        for element in rotor.elements
    )
    return map_projected_material_loads(
        annuli,
        hinge_radius_m=state.hinge_radius_m,
        theta_rad=theta,
        blade_count=nominal.blade_count,
        hinge_rate_rad_s=hinge_rate,
        projected_tip_radius_m=effective.radius_m,
        operating_condition_id=rotor.operating_condition_id,
        bem_settings=dict(rotor.settings.as_mapping()),
        polar_schedule_id=result.polar_schedule_id,
        airfoil_id=rotor.airfoil_id,
        scenario_id=rotor.scenario_id,
        polar_sources=rotor.polar_sources,
        radial_domain=rotor.radial_domain,
        geometry_extended=rotor.geometry_extended,
    )
