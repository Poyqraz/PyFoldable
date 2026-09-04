"""Fail-closed active-design binding for the PY-05 mechanism transient.

Only geometry that is already explicit in a validated design draft is reused.
Mass properties and every mechanical/drive input remain caller supplied; this
adapter never derives them from blade shape, material, CAD, BEM or motor data.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pyfoldable.application.design_draft import DesignDraftArtifact
from pyfoldable.application.folding_mechanism import (
    MechanismGeometryInputs,
    build_mechanism_geometry_audit,
)
from pyfoldable.core import load_design_config
from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.units import normalize_quantity
from pyfoldable.dynamics.mechanism_contracts import ContactPolicy, DryFriction
from pyfoldable.dynamics.mechanism_transient import (
    DriveHistory,
    MechanismParameters,
    SolverControls,
    TransientRequest,
)


MAX_DRAFT_BYTES = 1_000_000
MASS_CLASSIFICATIONS = frozenset({
    "engineering_assumption",
    "literature_derived_unqualified",
    "synthetic_test_fixture",
})


class MechanismBindingError(ValueError):
    """A draft cannot be bound without guessing or changing declared inputs."""


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MechanismBindingError(f"{name} must be a finite scalar.")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MechanismBindingError(f"{name} must be a finite scalar.") from exc
    if not math.isfinite(result):
        raise MechanismBindingError(f"{name} must be a finite scalar.")
    return result


def _source(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise MechanismBindingError(f"{name} source must be a nonempty string.")
    return value


@dataclass(frozen=True)
class RadialMassSample:
    """One explicit point/quadrature contribution for one movable blade tip."""

    distance_from_hinge_m: float
    mass_kg: float
    source: str
    intrinsic_inertia: float = 0.0

    def __post_init__(self) -> None:
        distance = _finite("distance_from_hinge_m", self.distance_from_hinge_m)
        mass = _finite("mass_kg", self.mass_kg)
        inertia = _finite("intrinsic_inertia", self.intrinsic_inertia)
        _source("RadialMassSample", self.source)
        if distance < 0.0:
            raise MechanismBindingError("distance_from_hinge_m must be nonnegative.")
        if mass <= 0.0:
            raise MechanismBindingError("mass_kg must be positive.")
        if inertia < 0.0:
            raise MechanismBindingError("intrinsic_inertia must be nonnegative (kg m²).")


@dataclass(frozen=True)
class TipMassDistribution:
    """Bounded, source-labelled mass quadrature for exactly one movable tip."""

    samples: tuple[RadialMassSample, ...]
    source: str
    classification: str

    def __post_init__(self) -> None:
        if not isinstance(self.samples, tuple) or not 1 <= len(self.samples) <= 4096:
            raise MechanismBindingError("Mass samples must be an immutable tuple of 1 to 4096 entries.")
        if any(not isinstance(sample, RadialMassSample) for sample in self.samples):
            raise MechanismBindingError("Every mass sample must be a RadialMassSample.")
        _source("TipMassDistribution", self.source)
        if not isinstance(self.classification, str) or self.classification not in MASS_CLASSIFICATIONS:
            raise MechanismBindingError(
                "Mass distribution classification must be an explicit unqualified class."
            )


@dataclass(frozen=True)
class MechanismBinding:
    """Exact active-draft/mechanism request identity."""

    draft: DesignDraftArtifact
    distribution: TipMassDistribution
    request: TransientRequest
    mechanical_source: str
    contact_policy: ContactPolicy
    context_json: str
    request_sha256: str

    @property
    def parameters(self) -> MechanismParameters:
        return self.request.parameters


def _json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MechanismBindingError("Binding context must contain finite JSON-safe data.") from exc


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_draft(draft: DesignDraftArtifact):
    if not isinstance(draft, DesignDraftArtifact):
        raise MechanismBindingError("Expected a validated DesignDraftArtifact.")
    if not isinstance(draft.toml, str) or len(draft.toml.encode("utf-8")) > MAX_DRAFT_BYTES:
        raise MechanismBindingError("Draft TOML is invalid or oversized.")
    if not isinstance(draft.draft_sha256, str) or _sha(draft.toml) != draft.draft_sha256:
        raise MechanismBindingError("Draft SHA-256 does not match exact TOML content.")
    if not isinstance(draft.source_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", draft.source_sha256
    ):
        raise MechanismBindingError("Source SHA-256 is invalid.")
    try:
        with tempfile.TemporaryDirectory(prefix="pyfoldable-mechanism-binding-") as directory:
            path = Path(directory) / "draft.toml"
            path.write_text(draft.toml, encoding="utf-8")
            design = load_design_config(path)
    except (OSError, TypeError, ValueError, KeyError) as exc:
        raise MechanismBindingError(f"Invalid design draft: {exc}") from exc
    if design.metadata.get("artifact_class") != "unqualified_design_draft":
        raise MechanismBindingError("Input is not an unqualified design draft.")
    if design.metadata.get("source_design_sha256") != draft.source_sha256:
        raise MechanismBindingError("Source SHA-256 does not match draft metadata.")
    return design


def _validate_geometry(design, initial_angle_rad: float):
    hinge = design.hinge
    if hinge is None:
        raise MechanismBindingError("A planar tip hinge is required.")
    zero_fields = (
        hinge.axis_azimuth_rad,
        hinge.axial_offset_m,
        hinge.tangential_offset_m,
        hinge.deployed_angle_rad,
        hinge.stop_angle_rad,
    )
    if not math.isclose(hinge.axis_elevation_rad, math.pi / 2.0, rel_tol=0.0, abs_tol=1e-12):
        raise MechanismBindingError("Only a +z planar hinge axis is supported.")
    if any(not math.isclose(value, 0.0, rel_tol=0.0, abs_tol=1e-12) for value in zero_fields):
        raise MechanismBindingError(
            "The planar binding requires zero axis azimuth/offsets and radial zero deployed/stop angles."
        )
    if not -math.pi - 1e-12 <= hinge.stowed_angle_rad < 0.0:
        raise MechanismBindingError("Stowed hinge angle must lie in [-pi, 0).")
    radius = design.blade.radius_m
    if not 0.0 < design.blade.hub_radius_m < hinge.radius_m < radius:
        raise MechanismBindingError("Hinge radius must lie strictly between hub and blade tip.")
    requirement = design.metadata.get("stowed_envelope_requirement")
    if requirement is None:
        raise MechanismBindingError("Draft must declare a stowed envelope requirement.")
    try:
        requirement_m = normalize_quantity(
            requirement, "length", field="stowed_envelope_requirement"
        ).si_value
        audit = build_mechanism_geometry_audit(
            MechanismGeometryInputs(
                design.blade.diameter_m,
                design.blade.hub_radius_m,
                hinge.radius_m,
                math.degrees(initial_angle_rad),
                requirement_m,
            ),
            tuple(station.r_over_R for station in design.blade.stations),
        )
    except (TypeError, ValueError) as exc:
        raise MechanismBindingError(f"Invalid planar geometry gate: {exc}") from exc
    return hinge, audit


def _mass_properties(distribution: TipMassDistribution, tip_length_m: float) -> tuple[float, float, float]:
    if not isinstance(distribution, TipMassDistribution):
        raise MechanismBindingError("Expected a validated TipMassDistribution.")
    if any(
        sample.distance_from_hinge_m
        > tip_length_m
        + 8 * max(math.ulp(tip_length_m), math.ulp(sample.distance_from_hinge_m))
        for sample in distribution.samples
    ):
        raise MechanismBindingError("Every radial mass sample must lie within the movable tip.")
    try:
        mass = math.fsum(sample.mass_kg for sample in distribution.samples)
        first = math.fsum(
            sample.mass_kg * sample.distance_from_hinge_m for sample in distribution.samples
        )
        inertia = math.fsum(
            sample.mass_kg * sample.distance_from_hinge_m**2
            + sample.intrinsic_inertia
            for sample in distribution.samples
        )
    except (ArithmeticError, OverflowError) as exc:
        raise MechanismBindingError("Mass-property reduction overflowed.") from exc
    if not all(math.isfinite(value) for value in (mass, first, inertia)) or mass <= 0.0 or inertia <= 0.0:
        raise MechanismBindingError("Derived one-tip mass properties must be finite and positive.")
    cg = first / mass
    if not math.isfinite(cg):
        raise MechanismBindingError("Derived one-tip center of mass is not finite.")
    return mass, cg, inertia


def _airfoil_context(design) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for airfoil in design.airfoils:
        coordinate_sha = airfoil_coordinate_sha256(airfoil) if airfoil.coordinates else None
        rows.append({
            "id": airfoil.id,
            "source": airfoil.source,
            "coordinate_sha256": coordinate_sha,
        })
    return rows


def bind_mechanism_draft(
    draft: DesignDraftArtifact,
    distribution: TipMassDistribution,
    *,
    spring_stiffness_nm_rad: float,
    rest_angle_rad: float,
    viscous_damping_nm_s_rad: float,
    initial_angle_rad: float,
    initial_angular_velocity_rad_s: float,
    drive: DriveHistory,
    mechanical_source: str,
    controls: SolverControls = SolverControls(),
    dry_friction: DryFriction = DryFriction(),
    contact_policy: ContactPolicy = ContactPolicy(),
) -> MechanismBinding:
    """Bind an exact active draft to explicit one-tip mechanism inputs."""
    design = _load_draft(draft)
    initial_angle = _finite("initial_angle_rad", initial_angle_rad)
    initial_velocity = _finite(
        "initial_angular_velocity_rad_s", initial_angular_velocity_rad_s
    )
    source = _source("mechanical_source", mechanical_source)
    if not isinstance(drive, DriveHistory):
        raise MechanismBindingError("drive must be a validated DriveHistory.")
    if not isinstance(controls, SolverControls):
        raise MechanismBindingError("controls must be validated SolverControls.")
    if not isinstance(dry_friction, DryFriction):
        raise MechanismBindingError("dry_friction must be a validated DryFriction.")
    if not isinstance(contact_policy, ContactPolicy):
        raise MechanismBindingError("contact_policy must be a validated ContactPolicy.")
    hinge, geometry_gate = _validate_geometry(design, initial_angle)
    tip_length = design.blade.radius_m - hinge.radius_m
    mass, cg, inertia = _mass_properties(distribution, tip_length)
    try:
        parameters = MechanismParameters(
            mass_kg=mass,
            cg_distance_m=cg,
            hinge_inertia_kg_m2=inertia,
            hinge_radius_m=hinge.radius_m,
            spring_stiffness_nm_rad=spring_stiffness_nm_rad,
            rest_angle_rad=rest_angle_rad,
            viscous_damping_nm_s_rad=viscous_damping_nm_s_rad,
            lower_stop_rad=hinge.stowed_angle_rad,
            upper_stop_rad=hinge.stop_angle_rad,
            dry_friction=dry_friction,
        )
        request = TransientRequest(
            parameters, drive, initial_angle, initial_velocity, controls, contact_policy
        )
    except (TypeError, ValueError) as exc:
        raise MechanismBindingError(f"Invalid mechanism request: {exc}") from exc

    context = {
        "schema_version": 1,
        "artifact_class": "active_design_mechanism_binding",
        "physical_qualification": False,
        "prototype_measurement": False,
        "classification": "unqualified_planar_mechanism_screening_only",
        "draft_toml": draft.toml,
        "draft_sha256": draft.draft_sha256,
        "source_sha256": draft.source_sha256,
        "source_identity_scope": "declared_source_hash_not_external_authentication",
        "blade": asdict(design.blade),
        "hinge": asdict(hinge),
        "airfoils": _airfoil_context(design),
        "tip_segment_length_m": tip_length,
        "mass_distribution": asdict(distribution),
        "transient": asdict(request),
        "contact_policy": asdict(contact_policy),
        "mechanical_source": source,
        "input_assumptions": {
            "mass_cg_inertia": "Caller-supplied radial samples for one movable tip only.",
            "spring_damping_drive_initial_state": "Caller-supplied SI inputs; not inferred from the draft.",
            "controls": "Explicit bounded numerical policy.",
            "hinge_and_stops": "Read from the exact draft after planar topology validation.",
            "friction": "Explicit dry-friction contract; no inferred coefficient.",
            "contact": "First contact is terminal; no reaction, rebound or latch model.",
            "rigid_body_scope": "Single planar rigid tip with prescribed shaft rotation.",
        },
        "geometry_gate": asdict(geometry_gate),
        "limitations": [
            "Mass and inertia inputs are unqualified and are not prototype measurements.",
            "No CAD geometry or material property is inferred.",
            "No BEM, aerodynamic hinge load, motor or shaft-feedback coupling is included.",
            "No static friction, stiction, breakaway or nonterminal impact is modeled.",
            "The centerline gate is necessary only; it is not full collision or strength evidence.",
            "This binding does not resolve the declared 140 mm stowed-envelope failure.",
        ],
    }
    context_json = _json(context)
    return MechanismBinding(
        draft=draft,
        distribution=distribution,
        request=request,
        mechanical_source=source,
        contact_policy=contact_policy,
        context_json=context_json,
        request_sha256=_sha(context_json),
    )


def validate_mechanism_binding(binding: MechanismBinding) -> MechanismBinding:
    """Rebuild every derived field and reject any stale or tampered binding."""
    if not isinstance(binding, MechanismBinding):
        raise MechanismBindingError("Expected a MechanismBinding.")
    p = binding.request.parameters
    try:
        rebuilt = bind_mechanism_draft(
            binding.draft,
            binding.distribution,
            spring_stiffness_nm_rad=p.spring_stiffness_nm_rad,
            rest_angle_rad=p.rest_angle_rad,
            viscous_damping_nm_s_rad=p.viscous_damping_nm_s_rad,
            initial_angle_rad=binding.request.initial_angle_rad,
            initial_angular_velocity_rad_s=binding.request.initial_angular_velocity_rad_s,
            drive=binding.request.drive,
            mechanical_source=binding.mechanical_source,
            controls=binding.request.controls,
            dry_friction=p.dry_friction,
            contact_policy=binding.contact_policy,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise MechanismBindingError(f"Binding cannot be rebuilt: {exc}") from exc
    if rebuilt != binding:
        raise MechanismBindingError("Binding identity changed or does not match current inputs.")
    return binding


__all__ = [
    "ContactPolicy",
    "MechanismBinding",
    "MechanismBindingError",
    "RadialMassSample",
    "TipMassDistribution",
    "bind_mechanism_draft",
    "validate_mechanism_binding",
]
