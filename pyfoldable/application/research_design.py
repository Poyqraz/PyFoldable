"""One source-bound design for planar preview, strict open BEM and optional PY-05.

The caller supplies a selected stored family; this module never runs a provider.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile

from pyfoldable.core import load_design_config
from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.config import tomllib
from pyfoldable.core.units import normalize_quantity
from pyfoldable.core.bem_rotor import _interpolate_station
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS, load_project_airfoil
from pyfoldable.dynamics.mechanism_contracts import ContactPolicy, DryFriction
from pyfoldable.dynamics.mechanism_transient import DriveHistory, SolverControls

from . import design_analysis, mechanism_transient as transient, provider_design_analysis as managed
from .design_draft import DesignDraftArtifact, DesignDraftInputs, build_design_draft
from .folding_mechanism import MechanismGeometryInputs, build_mechanism_geometry_audit
from .mechanism_binding import RadialMassSample, TipMassDistribution, bind_mechanism_draft
from .mechanism_transient import prepare_bound_mechanism_transient, run_bound_mechanism_transient
from .polar_upload import inspect_polar_bundle
from .profile_bem_comparison import add_record, assess_comparison, snapshot_failure
from ..core.models import PropellerDesign

TEMPLATES = {
    "axial_800": ("configs/designs/RESEARCH_AXIAL_800_V1.toml", "either_order"),
    "project_250": ("configs/designs/TIP_HINGED_250_CANONICAL.toml", "proximal_longer"),
}
MAX_SAVED_RESULT_BYTES = 6 * 1024 * 1024


@dataclass(frozen=True)
class ResearchInputs:
    template_id: str
    profile: str
    diameter_mm: float
    hub_mm: float
    root_mm: float | None
    root_meaning: str
    root_source: str
    root_kind: str
    hinge_mm: float
    blade_count: int
    chord_scale: float
    twist_scale: float
    fold_deg: float
    stow_limit_deg: float
    stowed_target_mm: float
    rpm: float
    inflow_m_s: float
    density_kg_m3: float
    viscosity_pa_s: float
    temperature_k: float
    pressure_pa: float
    annulus_count: int = 40


@dataclass(frozen=True)
class ResearchDesign:
    inputs: ResearchInputs
    template: managed.TemplateDeclaration
    length_order_policy: str
    draft: DesignDraftArtifact
    design: PropellerDesign
    root: managed.RootDatum | None
    coordinate_sha256: str

    @property
    def exposed_lengths_m(self):
        h = self.design.hinge.radius_m
        return (None if self.root is None else h - self.root.value / 1000,
                self.design.blade.radius_m - h)

    @property
    def identity(self):
        return _digest({"inputs": asdict(self.inputs), "draft": self.draft.draft_sha256,
                        "template_source": self.template.source_identity, "length_order_policy": self.length_order_policy})


@dataclass(frozen=True)
class MechanismInputs:
    """One equivalent CG mass with explicit intrinsic inertia, linear drive ramp."""
    mass_g: float | None
    cg_from_hinge_mm: float | None
    intrinsic_inertia_kg_m2: float | None
    source: str
    start_rpm: float
    duration_s: float
    initial_velocity_rad_s: float
    spring_nm_rad: float
    rest_deg: float
    damping_nm_s_rad: float
    applied_torque_nm: float
    friction_mode: str
    coulomb_nm: float
    transition_rad_s: float


def _digest(value):
    return hashlib.sha256(managed._json(value).encode()).hexdigest()


def defaults(root: Path, template_id: str = "axial_800") -> ResearchInputs:
    path, _ = TEMPLATES[template_id]
    design = load_design_config(root / path)
    cond, hinge = design.operating_conditions[0], design.hinge
    axial = template_id == "axial_800"
    declared_root = json.loads((root / "configs/polars/RESEARCH_AXIAL_800_V1.json").read_bytes())["root"] if axial else {}
    return ResearchInputs(
        template_id, "NACA2412", design.blade.diameter_m * 1000,
        design.blade.hub_radius_m * 1000, declared_root.get("value"),
        declared_root.get("meaning", ""), declared_root.get("source_identity", ""),
        declared_root.get("declaration_kind", "study_assumption"), hinge.radius_m * 1000, design.blade.blade_count, 1., 1.,
        -110.0 if axial else -90.0, math.degrees(hinge.stowed_angle_rad),
        600.0 if axial else 140.0, 2400.0 if axial else 7100.0, cond.forward_speed_m_s,
        cond.air_density_kg_m3, cond.dynamic_viscosity_pa_s, cond.temperature_k, cond.pressure_pa,
    )


def build_research_design(root: Path, inputs: ResearchInputs) -> ResearchDesign:
    if inputs.template_id not in TEMPLATES or inputs.profile not in PROJECT_AIRFOIL_IDS:
        raise ValueError("Select a declared template and catalog profile.")
    if not -180 <= inputs.stow_limit_deg < 0 or not inputs.stow_limit_deg <= inputs.fold_deg <= 0:
        raise ValueError("Require -180° ≤ stow limit < 0° and preview within the declared travel.")
    if not 1 <= inputs.blade_count <= 8 or not 4 <= inputs.annulus_count <= 80:
        raise ValueError("Supported blade/annulus counts are 1..8 and 4..80.")
    path, order = TEMPLATES[inputs.template_id]
    source = root / path
    template = managed.TemplateDeclaration(inputs.template_id, source.read_bytes(), f"repository:{path}")
    foil = load_project_airfoil(inputs.profile)
    draft = build_design_draft(source, DesignDraftInputs(
        diameter=f"{inputs.diameter_mm} mm", hub_radius=f"{inputs.hub_mm} mm",
        hinge_radius=f"{inputs.hinge_mm} mm", blade_count=inputs.blade_count,
        airfoil_id=inputs.profile, chord_scale=inputs.chord_scale, twist_scale=inputs.twist_scale,
        # Preview/stow is an independent pose; never send it to fully-open BEM.
        preview_fold_angle="0 deg", stowed_angle=f"{inputs.stow_limit_deg} deg",
        stowed_envelope_requirement=f"{inputs.stowed_target_mm} mm",
        angular_speed=f"{inputs.rpm} rpm", forward_speed=f"{inputs.inflow_m_s} m/s",
        air_density=f"{inputs.density_kg_m3} kg/m^3", dynamic_viscosity=f"{inputs.viscosity_pa_s} Pa*s",
        temperature=f"{inputs.temperature_k} K", pressure=f"{inputs.pressure_pa} Pa",
    ), airfoil_definition=foil)
    design, _ = design_analysis._load_geometry(draft)
    root_datum = None
    if inputs.root_mm is not None:
        if not math.isfinite(inputs.root_mm) or not 0 <= inputs.root_mm / 1000 < design.hinge.radius_m:
            raise ValueError("Declared blade root must be nonnegative and inside the hinge.")
        root_datum = managed.RootDatum(inputs.root_mm, "mm", inputs.root_meaning, inputs.root_source, inputs.root_kind)
    return ResearchDesign(inputs, template, order, draft, design, root_datum, airfoil_coordinate_sha256(foil))


def geometry_result(active: ResearchDesign):
    d, i = active.design, active.inputs
    audit = build_mechanism_geometry_audit(MechanismGeometryInputs(
        d.blade.diameter_m, d.blade.hub_radius_m, d.hinge.radius_m,
        i.fold_deg, i.stowed_target_mm / 1000,
    ), tuple(s.r_over_R for s in d.blade.stations))
    proximal, distal = active.exposed_lengths_m
    stow_tip_radius = math.hypot(
        d.hinge.radius_m + distal * math.cos(math.radians(i.stow_limit_deg)),
        distal * math.sin(math.radians(i.stow_limit_deg)),
    )
    return {"status": "computed", "scope": "planar_centerline_only_no_surface_clearance",
            "length_order_policy": active.length_order_policy,
            "declared_root": None if active.root is None else asdict(active.root),
            "first_aerodynamic_station_m": d.blade.stations[0].r_over_R * d.blade.radius_m,
            "proximal_m": proximal, "distal_m": distal,
            "proximal_longer": None if proximal is None else proximal > distal,
            "shaft_origin_proximal_longer": d.hinge.radius_m > d.blade.radius_m / 2,
            "declared_stow_limit_deg": i.stow_limit_deg,
            "declared_stow_limit_centerline_envelope_m": 2 * max(d.hinge.radius_m, stow_tip_radius),
            "legacy_audit_full_stow_fields_scope": "Hypothetical 0 to -180 degrees, not the adjustable declared travel limit.",
            "centerline": asdict(audit)}


def selection_for(active: ResearchDesign, family):
    policy = {} if family is None else managed.request_policy(family.requests[0], family.provider)
    return managed.ProviderDesignSelection(
        active.draft, active.template, active.root, "not_selected" if family is None else family.family_id,
        managed._json(policy), active.inputs.annulus_count,
        None if family is None or family.stored_version is None else family.stored_version.content_sha256,
        active.length_order_policy,
    )


def prepare_aero(active, family, repository):
    first_station = active.design.blade.stations[0].r_over_R * active.design.blade.radius_m
    if active.root is not None and active.root.value / 1000 > first_station:
        raise managed.ProviderDesignPreparationError(
            "aerodynamic_station_before_physical_root",
            "The declared physical blade root lies outside the first retained station; "
            "the template span must be declared consistently, without trimming or extrapolation.",
        )
    if family is None:
        raise managed.ProviderDesignPreparationError("missing_applicable_family", "Choose a matching stored family version.")
    if family.stored_version is None:
        raise managed.ProviderDesignPreparationError("stored_version_required", "A retained store version is required.")
    return managed.prepare_provider_design_analysis(selection_for(active, family), repository)


def initial_query_ranges(active):
    """Conditional no-induction queries at the selected station-span midpoints."""
    b, c = active.design.blade, active.design.operating_conditions[0]
    start = b.stations[0].r_over_R * b.radius_m
    end = b.stations[-1].r_over_R * b.radius_m
    count = active.inputs.annulus_count
    sound = math.sqrt(1.4 * 287.05 * c.temperature_k)
    rows = []
    for index in range(count):
        radius = start + (index + .5) * (end - start) / count
        station, _ = _interpolate_station(b, radius)
        u, v = c.forward_speed_m_s, c.angular_speed_rad_s * radius
        speed = math.hypot(u, v)
        rows.append((station.twist_rad - math.atan2(u, v),
                     c.air_density_kg_m3 * speed * station.chord_m / c.dynamic_viscosity_pa_s,
                     speed / sound))
    return tuple((min(col), max(col)) for col in zip(*rows))


def declared_grid_covers_initial(family, initial):
    """A readiness hint for the declared grid, not admission or proof of trial coverage."""
    grid = (tuple(set.intersection(*(set(r.alpha_rad) for r in family.requests))),
            tuple(r.reynolds for r in family.requests), tuple(r.mach for r in family.requests))
    return all(values and min(values) <= lo <= hi <= max(values)
               for values, (lo, hi) in zip(grid, initial))


_MECHANISM_SCOPE = "one_planar_rigid_tip_prescribed_rpm_first_contact_no_aero_feedback"


def _bind_mechanics(active, inputs, **policy):
    if (active.root is None or not active.root.meaning.strip() or not active.root.source_identity.strip()
            or active.length_order_policy == "proximal_longer"
            and not active.exposed_lengths_m[0] > active.exposed_lengths_m[1]):
        raise ValueError("Declared root and named template length rule are required for mechanism preparation.")
    if not 0 < inputs.duration_s <= 5 or not 0 <= inputs.start_rpm <= 20000:
        raise ValueError("Mechanism ramp is bounded to 5 s and nonnegative RPM up to 20000.")
    distribution = TipMassDistribution((RadialMassSample(inputs.cg_from_hinge_mm / 1000,
        inputs.mass_g / 1000, inputs.source, inputs.intrinsic_inertia_kg_m2),),
        inputs.source, "engineering_assumption")
    drive = DriveHistory((0., inputs.duration_s), (inputs.start_rpm, active.inputs.rpm),
                         (inputs.applied_torque_nm, inputs.applied_torque_nm))
    friction = DryFriction(inputs.friction_mode, inputs.coulomb_nm, inputs.transition_rad_s, inputs.source)
    return bind_mechanism_draft(active.draft, distribution,
        spring_stiffness_nm_rad=inputs.spring_nm_rad, rest_angle_rad=math.radians(inputs.rest_deg),
        viscous_damping_nm_s_rad=inputs.damping_nm_s_rad,
        initial_angle_rad=math.radians(active.inputs.fold_deg), initial_angular_velocity_rad_s=inputs.initial_velocity_rad_s,
        drive=drive, mechanical_source=inputs.source, dry_friction=friction, **policy)


def mechanism_result(active, inputs: MechanismInputs | None):
    scope = _MECHANISM_SCOPE
    if inputs is None:
        return {"status": "missing_inputs", "scope": scope, "requested": False}
    if None in (inputs.mass_g, inputs.cg_from_hinge_mm, inputs.intrinsic_inertia_kg_m2) or not inputs.source.strip():
        return {"status": "missing_inputs", "scope": scope, "requested": True, "inputs": asdict(inputs)}
    try:
        binding = _bind_mechanics(active, inputs)
        prepared = prepare_bound_mechanism_transient(binding)
        result = run_bound_mechanism_transient(binding, expected_request_sha256=prepared.request_sha256)
    except (ValueError, TypeError, ArithmeticError, OSError, RuntimeError) as exc:
        return {"status": "blocked_or_failed", "scope": scope, "inputs": asdict(inputs), "reason": str(exc)}
    return {"status": "computed", "scope": scope, "inputs": asdict(inputs),
            "report_sha256": result.report_sha256, "report_text": result.report_json}


def run_research(active, family, repository, mechanics, *, unavailable_reason=None):
    """Explicit action. One fresh admitted BEM invocation at most."""
    geometry = geometry_result(active)
    selection = selection_for(active, family)
    try:
        if unavailable_reason:
            raise managed.ProviderDesignPreparationError("provider_store_unavailable", unavailable_reason)
        prepared = prepare_aero(active, family, repository)
        outcome = managed.run_provider_design_analysis(prepared, active_selection=selection, repository=repository)
        aerodynamic = outcome.record
    except managed.ProviderDesignPreparationError as exc:
        aerodynamic = managed.preparation_failure_record(selection, exc)
    except (ValueError, OSError) as exc:
        aerodynamic = managed.preparation_failure_record(selection, managed.ProviderDesignPreparationError("admission_failed", str(exc)))
    body = {"schema_version": 1, "artifact_class": "pyfoldable_research_result",
            "input_sha256": active.identity, "inputs": asdict(active.inputs),
            "draft_toml": active.draft.toml, "draft_sha256": active.draft.draft_sha256,
            "template_toml": active.template.source_bytes.decode("utf-8"),
            "geometry": geometry, "aerodynamics": aerodynamic, "mechanism": mechanism_result(active, mechanics),
            "reference_agreement": "NOT_ASSESSED", "joint_loss_model": "NOT_MODELED", "physical_qualification": False}
    return json.loads(managed._json({**body, "result_sha256": _digest(body)}))


def saved_result_json(row):
    return managed._json(row) + "\n"


def _require_match(actual, expected, field):
    if managed._json(actual) != managed._json(expected):
        raise ValueError(f"Saved {field} contradicts the retained inputs or request.")


def _require_si(actual, expected, field):
    # The draft serializes SI through display units at 17 digits. Unit conversion
    # and reparse can introduce a few ULPs, not a physical tolerance.
    if not math.isclose(actual, expected, rel_tol=0, abs_tol=4 * max(math.ulp(actual), math.ulp(expected))):
        raise ValueError(f"Saved {field} contradicts the retained draft.")


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Expected a finite saved numerical input.")
    return value


def _attempt_context(context, inputs, draft):
    attempted = context["attempted_selection"]
    _require_match(context["attempted_selection_sha256"], _digest(attempted), "attempted selection digest")
    retained_draft = attempted["draft"]
    for name, value in {
        "toml": draft.toml, "declared_draft_sha256": draft.draft_sha256,
        "observed_toml_sha256": draft.draft_sha256, "declared_source_sha256": draft.source_sha256,
    }.items():
        _require_match(retained_draft[name], value, f"attempted draft {name}")
    template = attempted["template"]
    _require_match(template["template_id"], inputs.template_id, "template id")
    _require_match(template["observed_source_sha256"], draft.source_sha256, "template source")
    if not isinstance(template["source_identity"], str) or not template["source_identity"].strip():
        raise ValueError("Saved template source identity is empty.")
    _require_match(attempted["annulus_count"], inputs.annulus_count, "annulus count")
    return attempted


def _restore_design(row, snapshot, context):
    inputs = ResearchInputs(**row["inputs"])
    text = row["draft_toml"]
    if row["draft_sha256"] != hashlib.sha256(text.encode()).hexdigest():
        raise ValueError("Saved draft checksum mismatch.")
    source_sha = tomllib.loads(text)["metadata"]["source_design_sha256"]
    draft = DesignDraftArtifact("saved.toml", text, source_sha, row["draft_sha256"])
    design, angle = design_analysis._load_geometry(draft)
    condition = design.operating_conditions[0]
    foil = next((f for f in design.airfoils if f.id == inputs.profile), None)
    if (foil is None or not foil.coordinates or inputs.profile not in PROJECT_AIRFOIL_IDS
            or {s.airfoil_id for s in design.blade.stations} != {inputs.profile}):
        raise ValueError("Saved profile contradicts the retained draft.")
    coordinate = airfoil_coordinate_sha256(foil)
    if (angle != 0 or type(inputs.blade_count) is not int or type(inputs.annulus_count) is not int
            or not 4 <= inputs.annulus_count <= 80 or not 1 <= inputs.blade_count <= 8
            or not -180 <= _number(inputs.stow_limit_deg) < 0
            or not inputs.stow_limit_deg <= _number(inputs.fold_deg) <= 0
            or _number(inputs.chord_scale) <= 0 or _number(inputs.twist_scale) < 0
            or not all(isinstance(v, str) for v in (inputs.root_meaning, inputs.root_source, inputs.root_kind))):
        raise ValueError("Saved research controls are outside their declared format.")
    _require_match(inputs.blade_count, design.blade.blade_count, "blade count")
    target = normalize_quantity(design.metadata["stowed_envelope_requirement"], "length", field="saved stow target").si_value
    for field, actual, unit, dimension in (
        ("diameter_mm", design.blade.diameter_m, "mm", "length"),
        ("hub_mm", design.blade.hub_radius_m, "mm", "length"),
        ("hinge_mm", design.hinge.radius_m, "mm", "length"),
        ("stowed_target_mm", target, "mm", "length"),
        ("stow_limit_deg", design.hinge.stowed_angle_rad, "deg", "angle"),
        ("rpm", condition.angular_speed_rad_s, "rpm", "angular_speed"),
        ("inflow_m_s", condition.forward_speed_m_s, "m/s", "speed"),
        ("density_kg_m3", condition.air_density_kg_m3, "kg/m^3", "density"),
        ("viscosity_pa_s", condition.dynamic_viscosity_pa_s, "Pa*s", "dynamic_viscosity"),
        ("temperature_k", condition.temperature_k, "K", "temperature"),
        ("pressure_pa", condition.pressure_pa, "Pa", "pressure"),
    ):
        expected = normalize_quantity(f"{_number(getattr(inputs, field))} {unit}", dimension, field=field).si_value
        _require_si(actual, expected, field)
    root = None
    if inputs.root_mm is not None:
        if not 0 <= _number(inputs.root_mm) / 1000 < design.hinge.radius_m:
            raise ValueError("Saved root contradicts the retained hinge.")
        root = managed.RootDatum(inputs.root_mm, "mm", inputs.root_meaning, inputs.root_source, inputs.root_kind)
    attempted = _attempt_context(context, inputs, draft)
    _require_match(attempted["root"], None if root is None else asdict(root), "root declaration")
    order = attempted.get("length_order_policy", "proximal_longer")
    if order not in {"proximal_longer", "either_order"}:
        raise ValueError("Unrecognized retained length-order rule.")
    template_bytes = b""
    if "template_toml" in row:
        template_bytes = row["template_toml"].encode("utf-8")
        _require_match(hashlib.sha256(template_bytes).hexdigest(), source_sha, "template bytes")
        _require_match(len(template_bytes), attempted["template"]["byte_count"], "template byte count")
        with tempfile.TemporaryDirectory(prefix="pyfoldable-saved-template-") as directory:
            path = Path(directory) / "template.toml"
            path.write_bytes(template_bytes)
            source = load_design_config(path)
        _require_match(source.id, design.metadata["source_design_id"], "source design id")
        if len(source.blade.stations) != len(design.blade.stations):
            raise ValueError("Saved station count contradicts the retained template.")
        scale = normalize_quantity(f"{inputs.diameter_mm} mm", "length", field="diameter").si_value / source.blade.diameter_m
        for parent, station in zip(source.blade.stations, design.blade.stations):
            _require_si(station.r_over_R, parent.r_over_R, "station radius ratio")
            _require_si(station.chord_m, parent.chord_m * scale * inputs.chord_scale, "station chord scale")
            _require_si(station.twist_rad, parent.twist_rad * inputs.twist_scale, "station twist scale")
    template = managed.TemplateDeclaration(inputs.template_id, template_bytes, attempted["template"]["source_identity"])
    active = ResearchDesign(inputs, template, order, draft, design, root, coordinate)
    _require_match(row["input_sha256"], active.identity, "design input digest")
    expected_geometry = geometry_result(active)
    # Earliest v1 exports predate the separate declared travel-limit summary.
    # Validate it when present and always validate the original geometry fields.
    if "template_toml" not in row:
        for key in ("declared_stow_limit_deg", "declared_stow_limit_centerline_envelope_m",
                    "legacy_audit_full_stow_fields_scope"):
            if key not in row["geometry"]:
                expected_geometry.pop(key)
    _require_match(row["geometry"], expected_geometry, "derived geometry")
    _require_match(snapshot["airfoil_id"], inputs.profile, "snapshot profile")
    _require_match(snapshot["airfoil_coordinate_sha256"], coordinate, "snapshot coordinates")
    return active, attempted


def _check_admission(admission, attempted, active, snapshot, *, request=None):
    b, h = active.design.blade, active.design.hinge
    condition = asdict(active.design.operating_conditions[0])
    root = active.root
    expected = {
        "profile": active.inputs.profile, "coordinate_sha256": active.coordinate_sha256,
        "template": {"id": active.inputs.template_id, "source_identity": active.template.source_identity,
                     "source_sha256": active.draft.source_sha256},
        "draft_sha256": active.draft.draft_sha256,
        "root": {**asdict(root), "si_value_m": normalize_quantity(f"{root.value} mm", "length", field="r_root").si_value},
        "hub_radius_m": b.hub_radius_m, "first_aerodynamic_station_m": b.stations[0].r_over_R * b.radius_m,
        "tip_radius_m": b.radius_m, "hinge_radius_m": h.radius_m,
        "parent_stations": [asdict(s) for s in b.stations], "condition": condition,
        "shaft_origin_longer": h.radius_m > b.radius_m / 2,
    }
    geometry = admission["geometry"]
    for field, value in expected.items():
        _require_match(geometry[field], value, f"admitted geometry {field}")
    _require_si(geometry["proximal_exposed_m"], active.exposed_lengths_m[0], "admitted proximal length")
    _require_match(geometry["distal_exposed_m"], active.exposed_lengths_m[1], "admitted distal length")
    _require_match(geometry.get("length_order_policy", "proximal_longer"), active.length_order_policy, "length rule")
    _require_match(admission["family_id"], attempted["family_id"], "admitted family")
    _require_match(admission["stored_version"]["content_sha256"], attempted["stored_version_sha256"], "stored version")
    _require_match(admission["evidence_class"], snapshot["evidence_class"], "evidence class")
    _require_match(admission["provider_policy"], attempted["provider_policy"]["parsed"], "provider policy")
    _require_match(admission["bem_policy"], snapshot["prepared_policy"], "prepared BEM policy")
    _require_match(snapshot["prepared_policy"]["annulus_count"], active.inputs.annulus_count, "prepared annulus count")
    if admission["complete_family_admitted"] is not True or admission["physical_qualification"] is not False:
        raise ValueError("Saved executed request needs a complete, unqualified admission.")
    _check_cell_family(admission, snapshot, active, request)
    if request is not None:
        _require_match(request["provider_design_request_sha256"],
                       _digest({"admission": admission, "polar_run_sha256": request["ui_request_sha256"]}),
                       "admission request digest")
        _require_match(request["draft_toml"], active.draft.toml, "executed draft")
        _require_match(request["source_sha256"], active.draft.source_sha256, "executed template source")
        _require_match(request["condition_index"], 0, "executed condition index")
        _require_match(request["operating_condition"], condition, "executed operating condition")
        _require_match(snapshot["annulus_count"], active.inputs.annulus_count, "executed annulus count")


def _check_cell_family(admission, snapshot, active, request):
    """Check retained joins; raw capture bytes remain in the operator store."""
    cells = admission["cells"]
    if not isinstance(cells, list) or not 1 <= len(cells) <= 64:
        raise ValueError("Invalid retained polar cell count.")
    profile, coordinate = active.inputs.profile, active.coordinate_sha256
    tables = []
    for index, cell in enumerate(cells):
        doc = cell["returned_document"]
        result = managed._result(doc)
        declared = result.request
        _require_match(declared.airfoil.id, profile, "retained cell profile")
        _require_match(airfoil_coordinate_sha256(declared.airfoil), coordinate, "retained cell coordinates")
        _require_match(managed.request_policy(declared, result.provider), admission["provider_policy"], "cell provider policy")
        digest = result.cache_key
        for field, expected in {
            "index": index, "profile": profile, "attempted_profile": profile, "returned_profile": profile,
            "mach": declared.mach, "reynolds": declared.reynolds, "status": "admitted",
            "planned_request_sha256": digest, "attempted_request_sha256": digest,
            "returned_request_sha256": digest, "capture_request_sha256": digest,
            "returned_provider": result.provider.as_mapping(), "identity_mismatch": None, "points": doc["points"],
        }.items():
            _require_match(cell[field], expected, f"cell {index} {field}")
        receipt = cell["capture"]["receipt"]
        for field, expected in {
            "request_cache_key": digest, "request_preimage_sha256": digest, "coordinate_sha256": coordinate,
            "provider_identity": result.provider.as_mapping(), "evidence_ready": True,
        }.items():
            _require_match(receipt[field], expected, f"cell {index} receipt {field}")
        table = asdict(result.to_polar_table(require_complete=True))
        table["metadata"]["application_evidence_class"] = admission["evidence_class"]
        tables.append(table)
    payload = managed._json({"schema_version": 1, "artifact_class": "active_design_polar_bundle",
                             "physical_qualification": False, "tables": tables})
    bundle = inspect_polar_bundle(payload.encode())
    _require_match(snapshot["polar_source_sha256"], bundle.source_sha256, "polar bundle identity")
    if request is not None:
        upload = request["polar_upload"]
        _require_match(upload["source_json"], payload, "retained polar upload")
        _require_match(upload["source_sha256"], bundle.source_sha256, "retained polar upload digest")
        sorted_tables = sorted(tables, key=lambda t: (t["mach"], t["reynolds"]))
        _require_match(request["polar_families"], {profile: sorted_tables}, "executed polar family")


def _check_radial_output(row, snapshot, active):
    b = active.design.blade
    for name in ("thrust_n", "torque_nm", "shaft_power_w"):
        _number(snapshot[name])
    for name, station in (("inner_radius_m", b.stations[0]), ("outer_radius_m", b.stations[-1])):
        _require_si(_number(snapshot[name]), station.r_over_R*b.radius_m, name)
    count = snapshot["polar_query_envelope"]["query_count"]
    minimum = 0 if snapshot["evidence_class"] == "inert_fixture" else 1
    if type(count) is not int or count < minimum:
        raise ValueError("Invalid saved polar query count.")
    radial = radial_rows(row)
    if len(radial) != active.inputs.annulus_count:
        raise ValueError("Saved radial coverage contradicts the executed annulus count.")
    for index, item in enumerate(radial):
        _require_match(item["element"], index, "radial element index")
        for name in ("radius_m", "r_over_R", "inner_radius_m", "outer_radius_m", "chord_m", "twist_rad",
                     "alpha_deg", "reynolds", "mach", "cl", "cd", "thrust_n", "torque_nm",
                     "dthrust_n_per_m", "dtorque_nm_per_m"):
            _number(item[name])
    _require_si(snapshot["thrust_n"], math.fsum(item["thrust_n"] for item in radial), "thrust total")
    _require_si(snapshot["torque_nm"], math.fsum(item["torque_nm"] for item in radial), "torque total")
    omega = active.design.operating_conditions[0].angular_speed_rad_s
    _require_si(snapshot["shaft_power_w"], omega * snapshot["torque_nm"], "shaft power")
    counts = [e["solution"]["polar_query_envelope"]["query_count"] for e in snapshot["radial_elements"]]
    if any(type(v) is not int or v < minimum for v in counts) or sum(counts) != count:
        raise ValueError("Saved rotor query count contradicts the retained element counts.")


def _check_failure(snapshot, active, attempted):
    stage = snapshot["failure_stage"]
    expected = snapshot_failure(
        active.draft, reason=snapshot["failure_reason"], evidence_class=snapshot["evidence_class"],
        failure_stage=stage, prepared_policy=snapshot["prepared_policy"], ui_request_sha256=snapshot["ui_request_sha256"],
        polar_source_sha256=snapshot["polar_source_sha256"], polar_airfoil_id=snapshot["polar_airfoil_id"],
        polar_coordinate_sha256=snapshot["polar_coordinate_sha256"], polar_unavailable_reason=snapshot["polar_unavailable_reason"],
    )
    if stage == "preflight_rejection":
        attempt_sha = _digest(attempted)
        _require_match(snapshot["attempted_selection_sha256"], attempt_sha, "failed selection digest")
        rejection = snapshot["provider_design_rejection"]
        if "attempted_selection" in rejection:
            _require_match(rejection["attempted_selection"], attempted, "rejection selection")
            _require_match(rejection["attempted_selection_sha256"], attempt_sha, "rejection digest")
        _require_match(snapshot["failure_reason"], f"{rejection['code']}: {rejection['reason']}", "rejection reason")
        expected["attempt_sha256"] = attempt_sha
    else:
        _check_admission(snapshot["provider_design_admission"], attempted, active, snapshot)
        _require_match(snapshot["polar_airfoil_id"], active.inputs.profile, "failed solver profile")
        _require_match(snapshot["polar_coordinate_sha256"], active.coordinate_sha256, "failed solver coordinates")
    for name, value in expected.items():
        if name != "record_sha256":
            _require_match(snapshot[name], value, f"failure {name}")


def _check_mechanism(mech, active, unique):
    status = mech["status"]
    if (status not in {"computed", "missing_inputs", "blocked_or_failed"} or mech["scope"] != _MECHANISM_SCOPE
            or "requested" in mech and type(mech["requested"]) is not bool):
        raise ValueError("Unrecognized mechanism scope or status.")
    if status != "computed":
        if "report_text" in mech or "report_sha256" in mech:
            raise ValueError("An uncomputed mechanism cannot contain a report.")
        if "inputs" in mech:
            MechanismInputs(**mech["inputs"])
        if status == "blocked_or_failed" and not isinstance(mech["reason"], str):
            raise ValueError("Missing mechanism failure reason.")
        return
    if mech.get("requested") is False or hashlib.sha256(mech["report_text"].encode()).hexdigest() != mech["report_sha256"]:
        raise ValueError("Saved mechanism report checksum or status mismatch.")
    doc = json.loads(mech["report_text"], object_pairs_hook=unique)
    if (doc["schema_version"] != 2 or doc["artifact_class"] != "mechanism_transient_report"
            or doc["physical_qualification"] is not False):
        raise ValueError("Unsupported saved mechanism report.")
    request = doc["request"]
    _require_match(doc["request_sha256"], transient._sha(transient._json(request)), "mechanism request digest")
    retained = request["transient"]
    options = MechanismInputs(**mech["inputs"])
    # Replay only the pure binding with the recorded controls/contact policy.
    # The request's historical implementation identity and runtime stay intact.
    binding = _bind_mechanics(active, options, controls=SolverControls(**retained["controls"]),
                              contact_policy=ContactPolicy(**retained["contact_policy"]))
    expected_binding = json.loads(binding.context_json)
    (reference,) = request["provenance"]["references"]
    observed_binding = reference["binding"]
    _require_match(reference["binding_sha256"], transient._sha(transient._json(observed_binding)), "mechanism binding digest")
    for field in ("draft_toml", "draft_sha256", "source_sha256", "blade", "hinge", "airfoils",
                  "mass_distribution", "mechanical_source", "tip_segment_length_m", "transient",
                  "contact_policy", "geometry_gate", "physical_qualification", "prototype_measurement"):
        _require_match(observed_binding[field], expected_binding[field], f"mechanism {field}")
    _require_match(retained, expected_binding["transient"], "mechanism executed inputs and pose")
    result = doc["result"]
    samples = result["samples"]
    if not isinstance(samples, list) or not samples or not isinstance(result["status"], str):
        raise ValueError("Saved mechanism lacks a retained sample history.")
    first = samples[0]
    for field, value in (("time_s", 0.), ("angle_rad", retained["initial_angle_rad"]),
                         ("angular_velocity_rad_s", retained["initial_angular_velocity_rad_s"]),
                         ("rpm", options.start_rpm)):
        _require_si(_number(first[field]), value, f"mechanism initial {field}")
    previous = -math.inf
    for sample in samples:
        time = _number(sample["time_s"])
        if not previous < time <= options.duration_s:
            raise ValueError("Saved mechanism sample times contradict the declared ramp.")
        for field in ("angle_rad", "rpm", "centrifugal_torque_nm", "euler_torque_nm", "dry_friction_torque_nm"):
            _number(sample[field])
        previous = time


def read_saved_result(raw):
    """Recover a read-only snapshot from retained content, without a solver or current defaults."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_SAVED_RESULT_BYTES:
        raise ValueError("Saved result exceeds the 6 MiB limit.")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate saved result key.")
            result[key] = value
        return result

    try:
        row = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
        if not isinstance(row, dict):
            raise ValueError("Expected a saved research result object.")
        body = {key: val for key, val in row.items() if key != "result_sha256"}
        if row.get("result_sha256") != _digest(body):
            raise ValueError("Saved result checksum mismatch.")
        if (row.get("schema_version") != 1 or row.get("artifact_class") != "pyfoldable_research_result"
                or row.get("physical_qualification") is not False or row["reference_agreement"] != "NOT_ASSESSED"
                or row["joint_loss_model"] != "NOT_MODELED"):
            raise ValueError("Unsupported saved result version or scope.")
        snapshot = add_record((), row["aerodynamics"])[0]
        if snapshot["physical_qualification"] is not False or snapshot["draft_sha256"] != row["draft_sha256"]:
            raise ValueError("Saved aerodynamic snapshot does not belong to the same unqualified draft.")
        if snapshot["status"] == "success":
            report = snapshot["report_text"]
            if hashlib.sha256(report.encode()).hexdigest() != snapshot["report_sha256"]:
                raise ValueError("Saved report checksum mismatch.")
            doc = json.loads(report, object_pairs_hook=unique)
            request = doc["request"]
            if (request["draft_sha256"] != row["draft_sha256"] or doc["physical_qualification"] is not False
                    or design_analysis._sha(design_analysis._json(request)) != doc["request_sha256"]):
                raise ValueError("Saved report does not belong to the same unqualified draft.")
            reconstructed = design_analysis.DesignAnalysisArtifact(
                doc["request_sha256"], snapshot["report_sha256"], report, "research.json")
            if managed.snapshot_success(reconstructed, evidence_class=snapshot["evidence_class"]) != snapshot:
                raise ValueError("Saved snapshot contradicts the retained BEM report.")
            context = request["provider_design_admission"]
            active, attempted = _restore_design(row, snapshot, context)
            _check_admission(context, attempted, active, snapshot, request=request)
            _check_radial_output(row, snapshot, active)
            _provider_contract(snapshot)
        else:
            context = snapshot if snapshot["failure_stage"] == "preflight_rejection" else snapshot["provider_design_admission"]
            active, attempted = _restore_design(row, snapshot, context)
            _check_failure(snapshot, active, attempted)
        _check_mechanism(row["mechanism"], active, unique)
        return row
    except (KeyError, IndexError, TypeError, AttributeError, OverflowError, RecursionError) as exc:
        raise ValueError("Malformed saved research result.") from exc


def radial_rows(result):
    record = result["aerodynamics"]
    rows = []
    for element in record.get("radial_elements") or ():
        sol = element["solution"]
        rows.append({
            "result_sha256": result["result_sha256"], "report_sha256": record["report_sha256"],
            "profile": record["airfoil_id"], "coordinate_sha256": record["airfoil_coordinate_sha256"],
            "element": element["index"], "radius_m": sol["radius_m"], "r_over_R": sol["r_over_R"],
            "inner_radius_m": element["inner_radius_m"], "outer_radius_m": element["outer_radius_m"],
            "chord_m": sol["chord_m"], "twist_rad": sol["twist_rad"], "alpha_deg": math.degrees(sol["angle_of_attack_rad"]),
            "reynolds": sol["reynolds"], "mach": sol["mach"], "cl": sol["cl"], "cd": sol["cd"],
            "thrust_n": element["thrust_n"], "torque_nm": element["torque_nm"],
            "dthrust_n_per_m": sol["differential_thrust_n_m"], "dtorque_nm_per_m": sol["differential_torque_nm_m"],
        })
    return rows


def records_csv(rows):
    if not rows:
        return ""
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def _provider_contract(snapshot):
    if snapshot.get("status") != "success" or snapshot.get("evidence_class") == "inert_fixture":
        return None
    report = json.loads(snapshot["report_text"])
    admission = report["request"].get("provider_design_admission", {})
    cells = admission.get("cells", [])
    if not admission.get("stored_version") or admission.get("complete_family_admitted") is not True or not cells:
        return None
    if any(cell.get("status") != "admitted" for cell in cells):
        return None
    builds = {cell["capture"]["receipt"]["executable_identity"]["prelaunch"]["sha256"] for cell in cells}
    if len(builds) != 1:
        return None
    return {"provider_policy": admission["provider_policy"], "builds": sorted(builds),
            "bem_implementation": report["request"]["implementation"],
            "grid": [{k: c["returned_document"]["request"][k] for k in ("alpha_rad", "mach", "reynolds", "scenario_id")}
                     for c in cells],
            "root": admission["geometry"]["root"], "template": admission["geometry"]["template"],
            "length_order_policy": admission["geometry"].get("length_order_policy", "proximal_longer")}


def compare_results(results):
    """Matched declared inputs and observed executable file identities, no ranking."""
    snapshots = [row["aerodynamics"] for row in results]
    assessment = assess_comparison(snapshots)
    contracts = [_provider_contract(row) for row in snapshots]
    matched_records = len(contracts) == 2 and contracts[0] is not None and contracts[0] == contracts[1]
    return {**assessment, "matching_retained_provider_contract": matched_records,
            "matched_numerical_comparison": assessment["software_controlled_comparison"] and matched_records,
            "reference_agreement": "NOT_ASSESSED", "joint_loss_model": "NOT_MODELED",
            "identity_scope": "Content consistency only; no process attestation or experimental agreement."}
