"""GEOM-01: bounded planar hinge/stow screening using the existing audit/mesh."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import platform
import re

from pyfoldable.core.units import normalize_quantity
from pyfoldable.visualization.propeller_25d import (
    PreviewBladeStation, PropellerPreviewSpec, build_propeller_preview_mesh,
)
from . import design_analysis as analysis, folding_mechanism as geometry
from .design_draft import DesignDraftArtifact
from .design_search import (
    Evaluation, GridSearchPlan, SearchAxis, SearchError, _json, _sha, run_grid_search,
)
from .hardware_contract import load_hardware_json

_CONSTRAINTS = ("centerline_target", "centerline_path_clearance", "station_span_complete",
                "mesh_envelope_target", "surface_path_clearance", "interblade_clearance")
_HINGE_RADIUS_LINE = re.compile(r'(?m)^radius = "[^"]+"')
_CLEARANCE_SOURCES = (
    "application/surface_clearance.py", "geometry/surface_clearance.py",
    "geometry/triangle_distance.py", "application/hardware_contract.py",
    "application/hardware_clearance.py", "geometry/hardware.py",
)
_GEOM01_UNKNOWN = "unknown_no_swept_surface_collision_model"


@dataclass(frozen=True)
class GeometrySearchRequest:
    draft: DesignDraftArtifact
    plan: GridSearchPlan
    request_sha256: str
    context_json: str
    clearance_inputs: object | None = None
    hardware_json: bytes | None = None


def _clearance_module():
    # Late import: surface_clearance already imports geometry_search._inputs.
    from . import surface_clearance
    return surface_clearance


def _draft_with_hinge_radius(draft: DesignDraftArtifact, hinge_radius_m: float) -> DesignDraftArtifact:
    """Rewrite only the [hinge] radius so clearance sees this candidate's geometry."""
    if not math.isfinite(hinge_radius_m) or hinge_radius_m <= 0:
        raise SearchError("Candidate hinge radius must be a positive finite length.")
    start = draft.toml.find("[hinge]")
    if start < 0:
        raise SearchError("Candidate draft is missing a hinge table.")
    nxt = draft.toml.find("\n[", start + 1)
    section = draft.toml[start:] if nxt < 0 else draft.toml[start:nxt]
    updated, count = _HINGE_RADIUS_LINE.subn(f'radius = "{hinge_radius_m:.17g} m"', section, count=1)
    if count != 1:
        raise SearchError("Candidate draft is missing a hinge radius.")
    text = draft.toml[:start] + updated + ("" if nxt < 0 else draft.toml[nxt:])
    return DesignDraftArtifact(draft.filename, text, draft.source_sha256,
                               hashlib.sha256(text.encode("utf-8")).hexdigest())


def _classify_scoped_geom04(report):
    """Evidence label only; never a GEOM-01 constraint value."""
    statuses = []
    modeled = report.get("modeled_surface_status")
    if modeled is not None:
        statuses.append(modeled)
    hardware = report.get("hardware_status")
    if hardware is not None:
        statuses.append(hardware)
    for query in report.get("queries") or []:
        statuses.append((query.get("result") or {}).get("status"))
    if "violation" in statuses:
        return "scoped_geom04_violation"
    if statuses and all(status == "separated" for status in statuses):
        return "scoped_geom04_separated"
    return "unknown_scoped_geom04"


def _clearance_evidence(report, *, clearance_request, artifact, geometry_request,
                        hinge_radius_m, end_angle_deg, reason=None):
    hardware = json.loads(geometry_request.context_json).get("candidate_clearance") or {}
    return {
        "surface_path_clearance_status": _GEOM01_UNKNOWN,
        "scoped_geom04_status": _classify_scoped_geom04(report),
        "scoped_geom04_reason": reason,
        "full_propeller_clearance": None,
        "physical_qualification": False,
        "candidate_hinge_radius_m": hinge_radius_m,
        "clearance_end_angle_deg": end_angle_deg,
        "clearance_request_sha256": None if clearance_request is None else clearance_request.request_sha256,
        "clearance_report_sha256": None if artifact is None else artifact.report_sha256,
        "modeled_surface_status": report.get("modeled_surface_status"),
        "hardware_status": report.get("hardware_status"),
        "clearance_queries": list(report.get("queries") or []),
        "clearance_excluded_regions": report.get("excluded_regions"),
        "clearance_node_comparisons": report.get("node_comparisons"),
        "clearance_feature_tests": report.get("feature_tests"),
        "clearance_hardware_queries": report.get("hardware_queries"),
        "clearance_hardware_raw_sha256": hardware.get("hardware_raw_sha256"),
        "clearance_hardware_canonical_sha256": hardware.get("hardware_canonical_sha256"),
    }


def _inputs(draft):
    model, _ = analysis._load_geometry(draft)
    hinge = model.hinge
    if (hinge is None or not math.isclose(hinge.axis_elevation_rad, math.pi / 2, abs_tol=1e-12, rel_tol=0)
            or any(value != 0 for value in (hinge.axial_offset_m, hinge.tangential_offset_m,
                                            hinge.deployed_angle_rad, hinge.stop_angle_rad))
            or not -math.pi <= hinge.stowed_angle_rad < 0):
        raise SearchError("Geometry search requires the zero-offset planar +z hinge with radial open state.")
    if "stowed_envelope_requirement" not in model.metadata:
        raise SearchError("A source-bound stowed envelope requirement is required.")
    target = normalize_quantity(model.metadata["stowed_envelope_requirement"], "length").si_value
    if not math.isfinite(target) or target <= 0:
        raise SearchError("Stowed envelope requirement must be positive and finite.")
    ids = {station.airfoil_id for station in model.blade.stations}
    if len(ids) != 1 or len(model.blade.stations) > 64:
        raise SearchError("Geometry search supports a single profile and at most 64 stations.")
    foil = next(foil for foil in model.airfoils if foil.id in ids)
    if not foil.coordinates or len(foil.coordinates) > 601:
        raise SearchError("Geometry search requires 1–601 explicit source-bound profile coordinates.")
    return model, target, foil


def prepare_geometry_search(
    draft: DesignDraftArtifact, *, hinge_radii_m: tuple[float, ...],
    stowed_angles_deg: tuple[float, ...], max_evaluations: int = 25,
    clearance_inputs=None, hardware_json: bytes | None = None,
) -> GeometrySearchRequest:
    """Validate budgets and source identity without generating candidate meshes."""
    model, target, foil = _inputs(draft)
    if type(max_evaluations) is not int or not 1 <= max_evaluations <= 25:
        raise SearchError("Geometry evaluation budget must be an integer from 1 to 25.")
    if hardware_json is not None and clearance_inputs is None:
        raise SearchError("Hardware cannot bind without clearance inputs.")
    blade = model.blade
    radius = blade.diameter_m / 2
    plan = GridSearchPlan((
        SearchAxis("hinge_radius_m", hinge_radii_m, blade.hub_radius_m, radius),
        SearchAxis("stowed_angle_deg", stowed_angles_deg, math.degrees(model.hinge.stowed_angle_rad), 0.),
    ), max_evaluations, _CONSTRAINTS)
    hinges = next(axis.values for axis in plan.axes if axis.name == "hinge_radius_m")
    if any(not blade.hub_radius_m < h < radius for h in hinges):
        raise SearchError("Hinge positions must lie strictly between hub and tip.")
    count = math.prod(len(axis.values) for axis in plan.axes)
    vertex_budget = count * (len(blade.stations) + 2) * len(foil.coordinates) * blade.blade_count
    if vertex_budget > 250_000 or blade.blade_count > 8:
        raise SearchError("Aggregate preview budget is 250000 vertices and at most eight blades.")
    binding = None
    if clearance_inputs is not None:
        clearance = _clearance_module()
        if not isinstance(clearance_inputs, clearance.SurfaceClearanceInputs):
            raise SearchError("Expected explicit surface-clearance inputs.")
        clearance.SurfaceClearanceInputs(**asdict(clearance_inputs))
        try:
            clearance.prepare_surface_clearance(
                draft, replace(clearance_inputs, end_angle_deg=min(stowed_angles_deg)),
                hardware_json=hardware_json)
        except ValueError as exc:
            raise SearchError(str(exc)) from exc
        hardware = None if hardware_json is None else load_hardware_json(hardware_json)
        binding = {
            "inputs": asdict(clearance_inputs),
            "hardware_raw_sha256": None if hardware is None else hardware.raw_sha256,
            "hardware_canonical_sha256": None if hardware is None else hardware.canonical_sha256,
            "physical_qualification": False,
            "full_propeller_clearance": None,
            "reuse_policy": "rebuild_draft_and_request_per_candidate_never_reuse_foreign_geometry",
            "end_angle_policy": "candidate_stowed_angle_within_declared_travel",
            "selection_effect": "evidence_only_does_not_alter_geom01_constraints",
        }
    root = Path(__file__).parents[1]
    sources = ("application/geometry_search.py", "application/folding_mechanism.py",
               "application/design_search.py", "application/design_analysis.py",
               "visualization/propeller_25d.py", "core/airfoil.py", "core/models.py", "core/config.py", "core/units.py")
    if binding is not None:
        sources += _CLEARANCE_SOURCES
    context = {
        "schema_version": 1, "classification": "geometry_feasibility_screening_only",
        "base_draft_toml": draft.toml, "base_draft_sha256": draft.draft_sha256,
        "source_sha256": draft.source_sha256, "plan": asdict(plan),
        "stowed_requirement_m": target,
        "topology": "single_rigid_tip_planar_z_hinge",
        "proposed_angle_semantics": "alternative_stowed_endpoint_within_existing_travel_not_current_measured_state",
        "objective": "selected_endpoint_centerline_envelope_m_minimize",
        "full_180_centerline_lower_bound_m": radius + blade.hub_radius_m,
        "full_180_target_necessary_condition_met": target >= radius + blade.hub_radius_m,
        "full_180_bound_scope": "any_hinge_position_with_centerline_hub_nonpenetration_not_surface_clearance",
        "maximum_generated_vertices": vertex_budget,
        "implementation_sha256": {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in sources},
        "python": platform.python_version(),
    }
    if binding is not None:
        context["candidate_clearance"] = binding
    text = _json(context)
    return GeometrySearchRequest(draft, plan, _sha(text), text, clearance_inputs, hardware_json)


def run_geometry_search(request: GeometrySearchRequest) -> analysis.DesignAnalysisArtifact:
    """Compare proposed hinge/stowed endpoints; unknown surface constraints block selection.

    Optional GEOM-04 binding attaches candidate-specific evidence only. It does
    not assign True or False to surface_path_clearance or interblade_clearance.
    """
    if not isinstance(request, GeometrySearchRequest) or not isinstance(request.plan, GridSearchPlan):
        raise SearchError("Expected a prepared geometry grid.")
    axes = {axis.name: axis.values for axis in request.plan.axes}
    if set(axes) != {"hinge_radius_m", "stowed_angle_deg"}:
        raise SearchError("Geometry grid axes do not match the prepared contract.")
    fresh = prepare_geometry_search(request.draft, hinge_radii_m=axes["hinge_radius_m"],
        stowed_angles_deg=axes["stowed_angle_deg"], max_evaluations=request.plan.max_evaluations,
        clearance_inputs=request.clearance_inputs, hardware_json=request.hardware_json)
    if fresh != request:
        raise SearchError("Geometry request identity changed.")
    model, target, foil = _inputs(request.draft)
    blade = model.blade
    stations = tuple(PreviewBladeStation(s.r_over_R, s.chord_m, math.degrees(s.twist_rad)) for s in blade.stations)
    remaining_nodes = remaining_features = remaining_hardware = 0
    clearance = None
    if request.clearance_inputs is not None:
        clearance = _clearance_module()
        remaining_nodes = request.clearance_inputs.max_node_comparisons
        remaining_features = request.clearance_inputs.max_feature_tests
        remaining_hardware = request.clearance_inputs.max_hardware_queries

    def evaluate(parameters):
        nonlocal remaining_nodes, remaining_features, remaining_hardware
        h, angle = parameters["hinge_radius_m"], parameters["stowed_angle_deg"]
        audit = geometry.build_mechanism_geometry_audit(
            geometry.MechanismGeometryInputs(blade.diameter_m, blade.hub_radius_m, h, angle, target),
            tuple(s.r_over_R for s in blade.stations))
        mesh = None
        mesh_error = None
        try:
            mesh = build_propeller_preview_mesh(PropellerPreviewSpec(
                blade.diameter_m, blade.hub_radius_m, blade.blade_count, h, angle,
                airfoil_id=foil.id, airfoil_definition=foil), stations)
        except (ValueError, ArithmeticError) as exc:
            mesh_error = str(exc)[:1024]
        mesh_diameter = None if mesh is None else 2 * mesh.mesh_envelope_radius_m
        # On 0..-180 degrees every point of the moving radial centreline has
        # nonincreasing distance to the origin. Its path minimum is at the endpoint.
        path_clearance = audit.hub_centerline_clearance_m
        clearance_details = {
            "surface_path_clearance_status": _GEOM01_UNKNOWN,
            "full_propeller_clearance": None,
            "physical_qualification": False,
        }
        if clearance is not None:
            if remaining_nodes < 1:
                clearance_details.update(_clearance_evidence(
                    {}, clearance_request=None, artifact=None, geometry_request=request,
                    hinge_radius_m=h, end_angle_deg=angle,
                    reason="unknown_clearance_budget_exhausted"))
            else:
                try:
                    candidate_inputs = replace(
                        request.clearance_inputs, end_angle_deg=angle,
                        max_node_comparisons=remaining_nodes,
                        max_feature_tests=remaining_features,
                        max_hardware_queries=remaining_hardware)
                    clearance_request = clearance.prepare_surface_clearance(
                        _draft_with_hinge_radius(request.draft, h), candidate_inputs,
                        hardware_json=request.hardware_json)
                    artifact = clearance.run_surface_clearance(clearance_request)
                    report = json.loads(artifact.report_json)
                    remaining_nodes = max(0, remaining_nodes - int(report.get("node_comparisons") or 0))
                    remaining_features = max(0, remaining_features - int(report.get("feature_tests") or 0))
                    remaining_hardware = max(0, remaining_hardware - int(report.get("hardware_queries") or 0))
                    clearance_details.update(_clearance_evidence(
                        report if isinstance(report, dict) else {},
                        clearance_request=clearance_request, artifact=artifact,
                        geometry_request=request, hinge_radius_m=h, end_angle_deg=angle))
                except ValueError as exc:
                    clearance_details.update(_clearance_evidence(
                        {}, clearance_request=None, artifact=None, geometry_request=request,
                        hinge_radius_m=h, end_angle_deg=angle,
                        reason="unknown_candidate_clearance_unresolved"))
                    clearance_details["clearance_error"] = str(exc)[:1024]
        constraints = {
            "centerline_target": audit.current_envelope_requirement_met,
            "centerline_path_clearance": path_clearance > 0.0,
            "station_span_complete": audit.station_span_complete,
            "mesh_envelope_target": None if mesh is None else mesh_diameter <= target,
            "surface_path_clearance": None, "interblade_clearance": None,
        }
        return Evaluation(audit.centerline_envelope_diameter_m, constraints, {
            "audit": asdict(audit), "proposed_path_minimum_hub_clearance_m": path_clearance,
            "proposed_path_angle_interval_deg": [angle, 0.0],
            "full_180_path_hub_clearance_m": audit.full_stow_path_hub_clearance_m,
            "mesh_envelope_diameter_m": mesh_diameter, "mesh_error": mesh_error,
            "mesh_qualification": None if mesh is None else mesh.qualification,
            "airfoil_coordinate_sha256": None if mesh is None else mesh.airfoil_coordinate_sha256,
            "canonical_design_modified": False,
            **clearance_details,
        })

    return run_grid_search(request.plan, evaluate, evaluator_identity={
        "id": "geom01_planar_hinge_stow_v1", "geometry_request_sha256": request.request_sha256,
        "geometry_context": json.loads(request.context_json),
    })
