"""GEOM-03: source-bound continuous bounds on explicitly retained preview surfaces.

Contact bands are declared exclusions, not inferred hardware. Separation applies
only to the retained triangular surfaces under synchronous planar motion, never
to CAD solids, omitted joints, asynchronous blades or physical qualification.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import platform

from pyfoldable.geometry.surface_clearance import (
    ClearanceControls, SurfacePart, hub_clearance, pair_clearance,
)
from pyfoldable.visualization.propeller_25d import (
    PreviewBladeStation, PropellerPreviewSpec, build_propeller_preview_mesh,
)
from .design_analysis import DesignAnalysisArtifact, _json, _sha
from .design_draft import DesignDraftArtifact
from .folding_mechanism import MechanismGeometryInputs, build_mechanism_geometry_audit
from .geometry_search import _inputs


@dataclass(frozen=True)
class SurfaceClearanceInputs:
    end_angle_deg: float = -180.
    required_clearance_m: float = .0005
    root_attachment_m: float = 0.
    hinge_attachment_m: float = 0.
    contact_source: str = ""
    max_depth: int = 6
    max_intervals: int = 127
    max_node_comparisons: int = 50000

    def __post_init__(self):
        for name in ("end_angle_deg", "required_clearance_m", "root_attachment_m", "hinge_attachment_m"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number.")
        if not -180 <= self.end_angle_deg <= 0:
            raise ValueError("End angle must lie between -180 and zero degrees.")
        if not 0 <= self.required_clearance_m <= .1 or min(self.root_attachment_m, self.hinge_attachment_m) < 0:
            raise ValueError("Clearance must be 0–0.1 m and contact widths nonnegative.")
        if not isinstance(self.contact_source, str) or len(self.contact_source) > 2048:
            raise ValueError("Contact source must be bounded text.")
        self.contact_source.encode("utf-8")
        if (self.root_attachment_m or self.hinge_attachment_m) and not self.contact_source.strip():
            raise ValueError("Excluded contact regions require an explicit source/revision reference.")
        for name, lo, hi in (("max_depth", 0, 8), ("max_intervals", 1, 255),
                             ("max_node_comparisons", 1, 200000)):
            if type(getattr(self, name)) is not int or not lo <= getattr(self, name) <= hi:
                raise ValueError(f"{name} must be an integer within [{lo}, {hi}].")


@dataclass(frozen=True)
class SurfaceClearanceRequest:
    draft: DesignDraftArtifact
    inputs: SurfaceClearanceInputs
    request_sha256: str
    context_json: str


def prepare_surface_clearance(draft: DesignDraftArtifact, inputs: SurfaceClearanceInputs) -> SurfaceClearanceRequest:
    if not isinstance(inputs, SurfaceClearanceInputs):
        raise ValueError("Expected explicit surface-clearance inputs.")
    SurfaceClearanceInputs(**asdict(inputs))
    model, _, foil = _inputs(draft)
    blade, hinge = model.blade, model.hinge
    radius = blade.diameter_m / 2
    if inputs.end_angle_deg < math.degrees(hinge.stowed_angle_rad):
        raise ValueError("Proposed path exceeds the declared hinge travel.")
    if inputs.root_attachment_m > (hinge.radius_m - blade.hub_radius_m) / 4:
        raise ValueError("Root exclusion cannot exceed a quarter of the root span.")
    if inputs.hinge_attachment_m > min(hinge.radius_m - blade.hub_radius_m, radius - hinge.radius_m) / 4:
        raise ValueError("Hinge exclusion cannot exceed a quarter of either segment span.")
    if not 0 < blade.diameter_m <= 2 or blade.blade_count > 8:
        raise ValueError("Surface screening supports diameters up to 2 m and at most eight blades.")
    # A clipped triangle generates at most three triangles. Bound before meshing.
    triangle_bound = 6 * (len(blade.stations) + 1) * len(foil.coordinates) * blade.blade_count
    if triangle_bound > 12000:
        raise ValueError("Surface screening triangle budget exceeded (12000).")
    if any(abs(s.chord_m) > 2 for s in blade.stations):
        raise ValueError("Surface screening supports section chords up to 2 m.")
    root = Path(__file__).parents[1]
    paths = ("application/surface_clearance.py", "geometry/surface_clearance.py",
             "application/geometry_search.py", "application/design_analysis.py",
             "application/folding_mechanism.py", "visualization/propeller_25d.py",
             "core/models.py", "core/config.py", "core/airfoil.py", "core/units.py")
    context = {
        "schema_version": 1, "draft_toml": draft.toml, "draft_sha256": draft.draft_sha256,
        "source_sha256": draft.source_sha256, "inputs": asdict(inputs),
        "motion": "synchronous_planar_rigid_tips_from_zero_to_declared_endpoint",
        "hub_obstacle": "infinite_cylinder_conservative_envelope",
        "model_scope": "retained_open_preview_triangle_surfaces_not_solid_bodies",
        "maximum_triangles": triangle_bound,
        "airfoil_coordinate_sha256": foil.metadata["airfoil_coordinate_sha256"],
        "physical_qualification": False,
        "implementation_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths},
        "python": platform.python_version(),
    }
    text = _json(context)
    return SurfaceClearanceRequest(draft, inputs, _sha(text), text)


def _clip_triangle(triangle, *, minimum_x, maximum_x):
    """Clip the existing planar triangle, never interpolate a new blade section."""
    polygon = list(triangle)
    for cut, sign in ((minimum_x, 1), (maximum_x, -1)):
        output = []
        if not polygon:
            break
        for start, end in zip(polygon, polygon[1:] + polygon[:1]):
            inside_start, inside_end = sign * (start[0] - cut) >= 0, sign * (end[0] - cut) >= 0
            if inside_start:
                output.append(start)
            if inside_start != inside_end:
                fraction = (cut - start[0]) / (end[0] - start[0])
                output.append((cut, *(start[k] + fraction * (end[k] - start[k]) for k in (1, 2))))
        polygon = output
    return tuple((polygon[0], polygon[i], polygon[i + 1]) for i in range(1, len(polygon) - 1))


def _parts(model, foil, inputs):
    blade, hinge = model.blade, model.hinge
    mesh = build_propeller_preview_mesh(PropellerPreviewSpec(
        blade.diameter_m, blade.hub_radius_m, 1, hinge.radius_m, 0.,
        airfoil_id=foil.id, airfoil_definition=foil),
        tuple(PreviewBladeStation(s.r_over_R, s.chord_m, math.degrees(s.twist_rad)) for s in blade.stations))
    root_triangles, tip_triangles = [], []
    boundary = mesh.hinge_tip_station_index * mesh.section_vertex_count
    for face in mesh.faces:
        triangle = tuple(mesh.vertices[i] for i in face)
        root_face = max(face) < boundary
        clipped = _clip_triangle(triangle,
            minimum_x=blade.hub_radius_m + inputs.root_attachment_m if root_face else hinge.radius_m + inputs.hinge_attachment_m,
            maximum_x=hinge.radius_m - inputs.hinge_attachment_m if root_face else blade.diameter_m / 2)
        (root_triangles if root_face else tip_triangles).extend(clipped)
    if not root_triangles or not tip_triangles:
        raise ValueError("Declared exclusions leave an empty root or tip surface.")
    parts = []
    for index in range(blade.blade_count):
        angle = 2 * math.pi * index / blade.blade_count
        c, s = math.cos(angle), math.sin(angle)
        def rotated(point):
            x, y, z = point
            return (c*x - s*y, s*x + c*y, z)
        for name, triangles, moving in (("root", root_triangles, False), ("tip", tip_triangles, True)):
            parts.append(SurfacePart(f"blade_{index + 1}_{name}",
                tuple(tuple(rotated(p) for p in tri) for tri in triangles),
                rotated((hinge.radius_m, 0., 0.)), moving))
    if sum(len(p.triangles) for p in parts) > 12000:
        raise ValueError("Clipped surface triangle budget exceeded.")
    return tuple(parts), len(mesh.faces) * blade.blade_count


def run_surface_clearance(request: SurfaceClearanceRequest) -> DesignAnalysisArtifact:
    if not isinstance(request, SurfaceClearanceRequest):
        raise ValueError("Expected prepared surface-clearance request.")
    if prepare_surface_clearance(request.draft, request.inputs) != request:
        raise ValueError("Surface-clearance request identity changed.")
    model, target, foil = _inputs(request.draft)
    inputs = request.inputs
    parts, original_count = _parts(model, foil, inputs)
    audit = build_mechanism_geometry_audit(MechanismGeometryInputs(model.blade.diameter_m,
        model.blade.hub_radius_m, model.hinge.radius_m, inputs.end_angle_deg, target),
        tuple(s.r_over_R for s in model.blade.stations))
    jobs = [("hub", p, None) for p in parts]
    for i, a in enumerate(parts):
        for j, b in enumerate(parts[i + 1:], i + 1):
            jobs.append(("own_root_tip" if i // 2 == j // 2 else "interblade", a, b))
    rows, used = [], 0
    for kind, a, b in jobs:
        remaining = inputs.max_node_comparisons - used
        if remaining <= 0:
            result = {"status": "unknown", "lower_bound_m": None, "witness_clearance_m": None,
                      "node_comparisons": 0, "intervals": [], "reason": "global_budget_exhausted"}
        else:
            options = dict(angle_min_rad=math.radians(inputs.end_angle_deg), angle_max_rad=0.,
                clearance_m=inputs.required_clearance_m,
                controls=ClearanceControls(inputs.max_depth, inputs.max_intervals, remaining))
            result = asdict(hub_clearance(a, model.blade.hub_radius_m, **options) if b is None
                            else pair_clearance(a, b, **options))
            used += result["node_comparisons"]
        rows.append({"kind": kind, "a": a.name, "b": "hub_envelope" if b is None else b.name, "result": result})
    states = {r["result"]["status"] for r in rows}
    status = "violation" if "violation" in states else "unknown" if "unknown" in states else "separated"
    document = {
        "schema_version": 1, "request": json.loads(request.context_json),
        "request_sha256": request.request_sha256, "physical_qualification": False,
        "classification": "failed" if status == "violation" else "blocked" if status == "unknown" or not audit.station_span_complete else "screening-only",
        "modeled_surface_status": status, "full_propeller_clearance": None,
        "station_span_complete": audit.station_span_complete,
        "root_gap_m": audit.root_surface_gap_m, "tip_gap_m": audit.tip_surface_gap_m,
        "excluded_regions": {"root_radial_width_m": inputs.root_attachment_m,
            "hinge_half_width_m": inputs.hinge_attachment_m, "source": inputs.contact_source,
            "status": "not_evaluated", "scope": "declared_reference_radial_bands_move_with_each_rigid_part"},
        "original_triangle_count": original_count,
        "retained_triangle_count": sum(len(p.triangles) for p in parts),
        "node_comparisons": used, "queries": rows,
        "limitations": ["open_triangle_surfaces_not_solid_containment", "excluded_contact_regions_not_evaluated",
                        "synchronous_blades_only", "hub_is_infinite_cylinder_bound_not_measured_solid",
                        "interval_bounds_are_floating_point_screening_not_formal_or_physical_certification"],
    }
    text = _json(document)
    return DesignAnalysisArtifact(request.request_sha256, _sha(text), text, "surface_clearance_screening.json")
