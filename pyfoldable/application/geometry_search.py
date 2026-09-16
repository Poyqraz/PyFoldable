"""GEOM-01: bounded planar hinge/stow screening using the existing audit/mesh."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import platform

from pyfoldable.core.units import normalize_quantity
from pyfoldable.visualization.propeller_25d import (
    PreviewBladeStation, PropellerPreviewSpec, build_propeller_preview_mesh,
)
from . import design_analysis as analysis, folding_mechanism as geometry
from .design_draft import DesignDraftArtifact
from .design_search import (
    Evaluation, GridSearchPlan, SearchAxis, SearchError, _json, _sha, run_grid_search,
)

_CONSTRAINTS = ("centerline_target", "centerline_path_clearance", "station_span_complete",
                "mesh_envelope_target", "surface_path_clearance", "interblade_clearance")


@dataclass(frozen=True)
class GeometrySearchRequest:
    draft: DesignDraftArtifact
    plan: GridSearchPlan
    request_sha256: str
    context_json: str


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
) -> GeometrySearchRequest:
    """Validate budgets and source identity without generating candidate meshes."""
    model, target, foil = _inputs(draft)
    if type(max_evaluations) is not int or not 1 <= max_evaluations <= 25:
        raise SearchError("Geometry evaluation budget must be an integer from 1 to 25.")
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
    root = Path(__file__).parents[1]
    sources = ("application/geometry_search.py", "application/folding_mechanism.py",
               "application/design_search.py", "application/design_analysis.py",
               "visualization/propeller_25d.py", "core/airfoil.py", "core/models.py", "core/config.py", "core/units.py")
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
    text = _json(context)
    return GeometrySearchRequest(draft, plan, _sha(text), text)


def run_geometry_search(request: GeometrySearchRequest) -> analysis.DesignAnalysisArtifact:
    """Compare proposed hinge/stowed endpoints; unknown surface constraints block selection."""
    if not isinstance(request, GeometrySearchRequest) or not isinstance(request.plan, GridSearchPlan):
        raise SearchError("Expected a prepared geometry grid.")
    axes = {axis.name: axis.values for axis in request.plan.axes}
    if set(axes) != {"hinge_radius_m", "stowed_angle_deg"}:
        raise SearchError("Geometry grid axes do not match the prepared contract.")
    fresh = prepare_geometry_search(request.draft, hinge_radii_m=axes["hinge_radius_m"],
        stowed_angles_deg=axes["stowed_angle_deg"], max_evaluations=request.plan.max_evaluations)
    if fresh != request:
        raise SearchError("Geometry request identity changed.")
    model, target, foil = _inputs(request.draft)
    blade = model.blade
    stations = tuple(PreviewBladeStation(s.r_over_R, s.chord_m, math.degrees(s.twist_rad)) for s in blade.stations)

    def evaluate(parameters):
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
            "surface_path_clearance_status": "unknown_no_swept_surface_collision_model",
            "canonical_design_modified": False,
        })

    return run_grid_search(request.plan, evaluate, evaluator_identity={
        "id": "geom01_planar_hinge_stow_v1", "geometry_request_sha256": request.request_sha256,
        "geometry_context": json.loads(request.context_json),
    })
