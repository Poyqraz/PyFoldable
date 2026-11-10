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

from pyfoldable.core import load_design_config
from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.bem_rotor import _interpolate_station
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS, load_project_airfoil
from pyfoldable.dynamics.mechanism_contracts import DryFriction
from pyfoldable.dynamics.mechanism_transient import DriveHistory

from . import design_analysis, provider_design_analysis as managed
from .design_draft import DesignDraftArtifact, DesignDraftInputs, build_design_draft
from .folding_mechanism import MechanismGeometryInputs, build_mechanism_geometry_audit
from .mechanism_binding import RadialMassSample, TipMassDistribution, bind_mechanism_draft
from .mechanism_transient import prepare_bound_mechanism_transient, run_bound_mechanism_transient
from .profile_bem_comparison import add_record, assess_comparison
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


def mechanism_result(active, inputs: MechanismInputs | None):
    scope = "one_planar_rigid_tip_prescribed_rpm_first_contact_no_aero_feedback"
    if inputs is None:
        return {"status": "missing_inputs", "scope": scope, "requested": False}
    if None in (inputs.mass_g, inputs.cg_from_hinge_mm, inputs.intrinsic_inertia_kg_m2) or not inputs.source.strip():
        return {"status": "missing_inputs", "scope": scope, "requested": True, "inputs": asdict(inputs)}
    try:
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
        binding = bind_mechanism_draft(active.draft, distribution,
            spring_stiffness_nm_rad=inputs.spring_nm_rad, rest_angle_rad=math.radians(inputs.rest_deg),
            viscous_damping_nm_s_rad=inputs.damping_nm_s_rad,
            initial_angle_rad=math.radians(active.inputs.fold_deg), initial_angular_velocity_rad_s=inputs.initial_velocity_rad_s,
            drive=drive, mechanical_source=inputs.source, dry_friction=friction)
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
            "geometry": geometry, "aerodynamics": aerodynamic, "mechanism": mechanism_result(active, mechanics),
            "reference_agreement": "NOT_ASSESSED", "joint_loss_model": "NOT_MODELED", "physical_qualification": False}
    return json.loads(managed._json({**body, "result_sha256": _digest(body)}))


def saved_result_json(row):
    return managed._json(row) + "\n"


def read_saved_result(raw):
    """Recover only a read-only snapshot; never a prepared/active solve."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_SAVED_RESULT_BYTES:
        raise ValueError("Saved result exceeds the 6 MiB limit.")
    # This larger envelope uses the same unique-key/finite-data discipline.
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
                or row.get("physical_qualification") is not False):
            raise ValueError("Unsupported saved result version.")
        if row["draft_sha256"] != hashlib.sha256(row["draft_toml"].encode()).hexdigest():
            raise ValueError("Saved draft checksum mismatch.")
        snapshot = add_record((), row["aerodynamics"])[0]
        if snapshot["physical_qualification"] is not False or snapshot["draft_sha256"] != row["draft_sha256"]:
            raise ValueError("Saved aerodynamic snapshot does not belong to the same unqualified draft.")
        if (not isinstance(row["inputs"], dict) or not isinstance(row["geometry"], dict)
                or not isinstance(row["mechanism"], dict) or snapshot["airfoil_id"] not in PROJECT_AIRFOIL_IDS
                or snapshot["airfoil_id"] != row["inputs"].get("profile")):
            raise ValueError("Saved result input/geometry/profile shape is inconsistent.")
        report = snapshot["report_text"]
        if snapshot["status"] == "success":
            if hashlib.sha256(report.encode()).hexdigest() != snapshot["report_sha256"]:
                raise ValueError("Saved report checksum mismatch.")
            doc = json.loads(report, object_pairs_hook=unique)
            if (doc["request"]["draft_sha256"] != row["draft_sha256"]
                    or doc["physical_qualification"] is not False
                    or design_analysis._sha(design_analysis._json(doc["request"])) != doc["request_sha256"]):
                raise ValueError("Saved report does not belong to the same unqualified draft.")
            reconstructed = design_analysis.DesignAnalysisArtifact(
                doc["request_sha256"], snapshot["report_sha256"], report, "research.json")
            if managed.snapshot_success(reconstructed, evidence_class=snapshot["evidence_class"]) != snapshot:
                raise ValueError("Saved snapshot contradicts the retained BEM report.")
            radial_rows(row)  # require readable radial payload before adding to history
            _provider_contract(snapshot)  # validate nested admission shape before comparing
        elif report is not None or any(snapshot[k] is not None for k in ("thrust_n", "torque_nm", "shaft_power_w")):
            raise ValueError("Failure snapshots cannot contain report or totals.")
        mech = row["mechanism"]
        if mech.get("status") not in {"computed", "missing_inputs", "blocked_or_failed"}:
            raise ValueError("Unrecognized mechanism status.")
        if mech["status"] == "computed":
            if hashlib.sha256(mech["report_text"].encode()).hexdigest() != mech["report_sha256"]:
                raise ValueError("Saved mechanism report checksum mismatch.")
            mech_doc = json.loads(mech["report_text"], object_pairs_hook=unique)
            binding = mech_doc["request"]["provenance"]["references"][0]["binding"]
            if binding["draft_sha256"] != row["draft_sha256"] or mech_doc["physical_qualification"] is not False:
                raise ValueError("Saved mechanism report is not bound to this draft.")
        return row
    except (KeyError, TypeError, AttributeError, OverflowError, RecursionError) as exc:
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
