"""Chord-bearing surface screening for the existing 50 mm hinge.

Dimensions, stations, and the NACA2412 coordinate identity are read from the
pinned parent packet. The hinge radius is read from the pinned PR #100 study.
The three path endpoints are the proposed stops in the pinned PR #101 study.
Preview meshes and GEOM-03 reports come from the merged services. This script
does not add a clearance algorithm and does not call a solver.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from pyfoldable import __version__
from pyfoldable.application.blade_stations import parse_station_bundle
from pyfoldable.application.design_draft import (
    DesignDraftInputs,
    DraftUnitSelection,
    build_design_draft,
)
from pyfoldable.application.geometry_search import _inputs
from pyfoldable.application.surface_clearance import (
    SurfaceClearanceInputs,
    _parts,
    prepare_surface_clearance,
    run_surface_clearance,
)
from pyfoldable.geometry.surface_clearance import (
    ClearanceControls,
    _rotate,
    pair_clearance,
)
from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.config import load_design_config
from pyfoldable.core.profile_catalog import load_project_airfoil
from pyfoldable.visualization.propeller_25d import (
    PreviewBladeStation,
    PropellerPreviewSpec,
    build_propeller_preview_mesh,
)


PARENT_PACKET = "reports/retained_pins/jvp01_geometry_identity/packet.json"
HINGE_STUDY = "reports/retained_pins/hinge_location_geometry_screening/study.json"
FOLD_STUDY = "reports/retained_pins/intermediate_fold_50mm_screening/study.json"
SOURCE_RELATIVE = "configs/designs/TIP_HINGED_250_CANONICAL.toml"
PARENT_HEAD = "3db6b8909aa3e929a557699d98593fccb3fe8c4a"
HINGE_HEAD = "56a3b52a439c408cbdd13ae3baf8c43fa577bf71"
FOLD_HEAD = "3ed68e9b8a2f1c9424204f1fb39404e000f539cf"
PARENT_SHA256 = "1a149afec4cb192703a597e86717e5040d15e3c7fcb1697b4898ea3d26b6eada"
PARENT_PACKET_SHA256 = "5df16176a8774b02a0b2d3bd5dfc3b98c2e272761714f5f7b5c743d7f1388531"
HINGE_STUDY_SHA256 = "f3c3e927c0ede938e5e770cce2eab405ca8413cec997eb17ab620b5fe22a7124"
FOLD_STUDY_SHA256 = "8d219acb44aa7cdd5fcf7d858ab1a59636d9aa413214d0756384102a8e4e2815"
MAIN_HEAD = "022b466303c59b8c0adb02f935f9c2f065b0e2b5"
REVIEWED_SURFACE_HEAD = "284a2e4f3b33f999fddcb9d8eb0b3a98ebf53c26"
STUDY_DRAFT_SHA256 = "89dfdd1907e9fe2221adea7ffa193f1849fbc1d6052dced1dafe5d20279c07d1"
ORIGINAL_STUDY_SHA256 = "ae2f3434fea0687f79fbbe9a9b5d7e0e4efe488c276e53d5fb3423e411738718"
ORIGINAL_REPORT_SHA256 = "546e95e1b61bd19ea57a00741cd429d338dd2f0aefc1b2c34169506a95729537"
ORIGINAL_PLAN_SHA256 = "434990960aeec4f2e27c3dba8e29e75c5040e91ebee45ea2b4cf177703f36244"
ORIGINAL_SURFACE_SHA256 = "8b88f5a8f03852f540e63f91ad770f8e9d8c6f34c9e85d7bd22d45a7e6a15c52"
DIAGNOSTIC_END_DEG = -135.0
INTERBLADE_PAIRS = (
    ("blade_1_root", "blade_2_root"),
    ("blade_1_root", "blade_2_tip"),
    ("blade_1_tip", "blade_2_root"),
    ("blade_1_tip", "blade_2_tip"),
)
PAIR_NODE_COMPARISONS = 50000
PAIR_FEATURE_TESTS = 2048
PAIR_MAX_DEPTH = 6
PAIR_MAX_INTERVALS = 127
AGGREGATE_NODE_COMPARISONS = 200000
AGGREGATE_FEATURE_TESTS = 8192
_BUDGET_FIELDS = (
    "max_depth",
    "max_intervals",
    "max_node_comparisons",
    "max_feature_tests",
    "max_hardware_queries",
    "root_attachment_m",
    "hinge_attachment_m",
    "contact_source",
)


def _canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _quantity(value: float, unit: str) -> dict[str, float | str]:
    return {"value": value, "unit": unit}


def _load_pin(root: Path, relative: str, expected_sha256: str) -> dict[str, object]:
    payload = (root / relative).read_bytes()
    digest = _sha256_bytes(payload)
    if digest != expected_sha256:
        raise ValueError(f"Retained input {relative} no longer matches its pin.")
    return json.loads(payload)


def _parent_bundle(packet: dict[str, object]):
    parent = packet["parent"]
    if parent["canonical_sha256"] != PARENT_SHA256:
        raise ValueError("Pinned parent identity changed.")
    bundle = parent["bundle"]
    parsed = parse_station_bundle(_canonical(bundle).encode("utf-8"))
    if parsed.canonical_sha256 != PARENT_SHA256:
        raise ValueError("Reparsed parent bundle does not match the pinned identity.")
    return bundle, parsed


def _study_draft(root: Path, packet: dict[str, object], hinge_study: dict[str, object]):
    bundle, parsed = _parent_bundle(packet)
    profile_id = bundle["airfoil_id"]
    profile = load_project_airfoil(profile_id)
    coordinate_sha = airfoil_coordinate_sha256(profile)
    if coordinate_sha != packet["profile"]["airfoil_coordinate_sha256"]:
        raise ValueError("Catalog NACA identity does not match the retained parent profile.")
    if coordinate_sha != bundle["airfoil_coordinate_sha256"]:
        raise ValueError("Parent bundle coordinate identity does not match the catalog profile.")
    trial = next(item for item in hinge_study["hinges"] if item["id"] == "trial_50_mm")
    reference = next(item for item in hinge_study["hinges"] if item["id"] == "schema_example_100_mm")
    if trial["radius_m"] == reference["radius_m"]:
        raise ValueError("The 50 mm study hinge is not distinct from the schema-example hinge.")
    source_path = root / SOURCE_RELATIVE
    source_bytes = source_path.read_bytes()
    if _sha256_bytes(source_bytes) != packet["source"]["sha256"]:
        raise ValueError("Canonical source bytes do not match the retained parent packet.")
    source = load_design_config(source_path)
    if source.hinge is None or not source.operating_conditions:
        raise ValueError("The canonical source has no hinge or operating condition.")
    condition = source.operating_conditions[0]
    units = bundle["units"]
    inputs = DesignDraftInputs(
        _quantity(bundle["diameter"], units["length"]),
        _quantity(bundle["hub_radius"], units["length"]),
        _quantity(trial["radius_m"], units["length"]),
        source.blade.blade_count,
        profile_id,
        1.0,
        1.0,
        "0 rad",
        _quantity(condition.angular_speed_rad_s, "rad/s"),
        _quantity(condition.forward_speed_m_s, "m/s"),
        _quantity(condition.air_density_kg_m3, "kg/m^3"),
        _quantity(condition.dynamic_viscosity_pa_s, "Pa*s"),
        _quantity(condition.temperature_k, "K"),
        _quantity(condition.pressure_pa, "Pa"),
    )
    draft = build_design_draft(
        source_path,
        inputs,
        units=DraftUnitSelection(
            length=units["length"],
            angle=units["angle"],
            angular_speed="rad/s",
        ),
        airfoil_definition=profile,
        station_bundle=parsed,
    )
    if source_path.read_bytes() != source_bytes:
        raise ValueError("The canonical source changed while building the study draft.")
    if draft.draft_sha256 == PARENT_SHA256 or draft.draft_sha256 == packet["draft"]["sha256"]:
        raise ValueError("The 50 mm study draft must stay distinct from the parent identity.")
    return bundle, parsed, profile, trial, draft, source.blade.blade_count


def _preview_stations(bundle: dict[str, object]) -> tuple[PreviewBladeStation, ...]:
    radius = bundle["diameter"] / 2.0
    return tuple(
        PreviewBladeStation(
            station["radius"] / radius,
            station["chord"],
            math.degrees(station["twist"]),
        )
        for station in bundle["stations"]
    )


def _mesh(bundle, profile, hinge_radius_m: float, blade_count: int, angle_deg: float):
    return build_propeller_preview_mesh(
        PropellerPreviewSpec(
            bundle["diameter"],
            bundle["hub_radius"],
            blade_count,
            hinge_radius_m,
            angle_deg,
            airfoil_id=bundle["airfoil_id"],
            airfoil_definition=profile,
        ),
        _preview_stations(bundle),
    )


def _mesh_record(mesh, pinned_diameter_m: float | None) -> dict[str, object]:
    axial = tuple(vertex[2] for vertex in mesh.vertices)
    record = {
        "qualification": mesh.qualification,
        "centerline_envelope_radius_m": mesh.centerline_envelope_radius_m,
        "mesh_envelope_radius_m": mesh.mesh_envelope_radius_m,
        "projected_effective_radius_m": mesh.effective_radius_m,
        "axial_min_m": min(axial),
        "axial_max_m": max(axial),
        "triangle_count": len(mesh.faces),
        "airfoil_coordinate_sha256": mesh.airfoil_coordinate_sha256,
    }
    if pinned_diameter_m is not None:
        if abs(mesh.centerline_envelope_radius_m - pinned_diameter_m / 2.0) > 1.0e-12:
            raise ValueError("Preview centerline radius does not match the pinned centerline study.")
        record["pinned_centerline_diameter_m"] = pinned_diameter_m
    if record["mesh_envelope_radius_m"] == record["centerline_envelope_radius_m"]:
        raise ValueError("Mesh radial envelope collapsed onto the centerline radius.")
    return record


def _clearance_inputs(angle_deg: float) -> SurfaceClearanceInputs:
    defaults = SurfaceClearanceInputs()
    chosen = SurfaceClearanceInputs(end_angle_deg=angle_deg, required_clearance_m=0.0)
    for name in _BUDGET_FIELDS:
        if getattr(chosen, name) != getattr(defaults, name):
            raise ValueError("A surface report changed a default budget or attachment exclusion.")
    return chosen


def _expected_pairs(blade_count: int) -> set[tuple[str, str, str]]:
    names = [
        f"blade_{index}_{part}"
        for index in range(1, blade_count + 1)
        for part in ("root", "tip")
    ]
    expected = {("hub", name, "hub_envelope") for name in names}
    for left_index, left in enumerate(names):
        for right in names[left_index + 1 :]:
            kind = "own_root_tip" if left.split("_")[1] == right.split("_")[1] else "interblade"
            expected.add((kind, left, right))
    return expected


def build_chord_surface_study(repository_root: Path) -> dict[str, object]:
    """Run three default-budget GEOM reports and record the preview-mesh extents."""
    root = repository_root.resolve()
    packet = _load_pin(root, PARENT_PACKET, PARENT_PACKET_SHA256)
    packet_sha = PARENT_PACKET_SHA256
    hinge_study = _load_pin(root, HINGE_STUDY, HINGE_STUDY_SHA256)
    fold_study = _load_pin(root, FOLD_STUDY, FOLD_STUDY_SHA256)
    if hinge_study["parent"]["canonical_sha256"] != PARENT_SHA256:
        raise ValueError("Pinned hinge study parent identity changed.")
    if fold_study["parent"]["canonical_sha256"] != PARENT_SHA256:
        raise ValueError("Pinned intermediate-fold parent identity changed.")
    if fold_study["archived_study"]["sha256"] != HINGE_STUDY_SHA256:
        raise ValueError("Pinned intermediate-fold study no longer points at the hinge study.")
    bundle, _parsed, profile, trial, draft, blade_count = _study_draft(root, packet, hinge_study)
    stops = [pose["fold_angle_deg"] for pose in fold_study["reported_poses"]]
    if len(stops) != 3:
        raise ValueError("The pinned fold study does not contain exactly three proposed stops.")
    pinned_diameter = {
        pose["fold_angle_deg"]: pose["centerline_envelope_diameter_m"]
        for pose in fold_study["reported_poses"]
    }
    deployment_mesh = _mesh(bundle, profile, trial["radius_m"], blade_count, 0.0)
    reports = []
    for angle in stops:
        inputs = _clearance_inputs(angle)
        artifact = run_surface_clearance(prepare_surface_clearance(draft, inputs))
        document = json.loads(artifact.report_json)
        if document["full_propeller_clearance"] is not None or document["physical_qualification"]:
            raise ValueError("A surface report promoted full propeller clearance or qualification.")
        if document["request"]["hub_obstacle"] != "infinite_cylinder_conservative_envelope":
            raise ValueError("The conservative hub obstacle was replaced.")
        if document["hardware_status"] is not None:
            raise ValueError("An undeclared hardware solid entered the surface report.")
        pairs = {(row["kind"], row["a"], row["b"]) for row in document["queries"]}
        if pairs != _expected_pairs(blade_count):
            raise ValueError("A surface report dropped a hub, own-root/tip, or interblade query.")
        reports.append(
            {
                "end_angle_deg": angle,
                "role": "proposed intermediate stop, not a selected design",
                "geom_report": document,
                "preview_mesh": _mesh_record(
                    _mesh(bundle, profile, trial["radius_m"], blade_count, angle),
                    pinned_diameter[angle],
                ),
            }
        )
    return {
        "study_id": "chord_bearing_surface_screening_50mm",
        "evidence_class": "retained_preview_mesh_geom03_screening_not_qualification",
        "physical_qualification": False,
        "qualified_winner": None,
        "full_propeller_clearance": None,
        "pins": {
            "main_head": MAIN_HEAD,
            "parent_packet": {
                "head": PARENT_HEAD,
                "path": PARENT_PACKET,
                "sha256": packet_sha,
                "canonical_sha256": PARENT_SHA256,
            },
            "hinge_location_study": {
                "head": HINGE_HEAD,
                "path": HINGE_STUDY,
                "sha256": HINGE_STUDY_SHA256,
            },
            "intermediate_fold_study": {
                "head": FOLD_HEAD,
                "path": FOLD_STUDY,
                "sha256": FOLD_STUDY_SHA256,
            },
        },
        "parent_identity": {
            "canonical_sha256": PARENT_SHA256,
            "modified": False,
        },
        "study_draft": {
            "sha256": draft.draft_sha256,
            "source_sha256": draft.source_sha256,
            "hinge_id": trial["id"],
            "hinge_declaration": trial["declaration"],
            "hinge_radius_m": trial["radius_m"],
            "hinge_role": trial["role"],
            "distinct_from_parent": True,
        },
        "clearance_declaration": {
            "required_clearance_m": 0.0,
            "meaning": (
                "Requested clearance is 0 m so the existing service can report modeled "
                "contact. It is not a manufacturing acceptance margin."
            ),
            "root_attachment_m": 0.0,
            "hinge_attachment_m": 0.0,
            "contact_source": "",
            "budgets": "SurfaceClearanceInputs defaults except the endpoint and requested clearance",
            "automatic_retries": False,
            "budget_increases": False,
        },
        "hub_obstacle": {
            "kind": "infinite_cylinder_conservative_envelope",
            "limitation": (
                "Measured hub height is not available. The obstacle is an infinite cylinder "
                "of the retained hub radius. A bound against it is not collision evidence "
                "for a real finite hub, and a separated bound does not cover unmeshed span."
            ),
        },
        "not_invented": [
            "joint relief",
            "hardware",
            "hub height",
            "endcaps",
            "gap-filling surfaces",
        ],
        "deployment_preview": {
            "fold_angle_deg": 0.0,
            "geom_report": None,
            "preview_mesh": _mesh_record(deployment_mesh, None),
        },
        "stops": reports,
        "distinctions": {
            "mesh_versus_centerline": (
                "mesh_envelope_radius_m is the largest radial distance of a preview-mesh "
                "vertex. centerline_envelope_radius_m is the preview centerline radius. "
                "At the three stops that radius equals half the pinned PR #101 centerline "
                "diameter. axial_min_m and axial_max_m are the mesh vertex z extent."
            ),
            "shared_hinge": (
                "Attachment exclusions stay zero, so the shared hinge boundary remains "
                "inside the own-root/tip query. An unresolved result stays unresolved."
            ),
        },
        "not_executed": ["polar provider", "BEM", "CFD", "FEA", "transient"],
        "runtime": {
            "python": platform.python_version(),
            "pyfoldable_version": __version__,
            "numpy": version("numpy"),
            "scipy": version("scipy"),
            "matplotlib": version("matplotlib"),
            "physical_qualification": False,
        },
    }


def _query_summary(document: dict[str, object]) -> list[str]:
    lines = [
        "| Kind | A | B | Status | Contact | Reason | Intervals | Lower bound m | Witness m |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in document["queries"]:
        result = row["result"]
        lines.append(
            "| {kind} | {a} | {b} | {status} | {contact} | {reason} | {intervals} | {lower} | {witness} |".format(
                kind=row["kind"],
                a=row["a"],
                b=row["b"],
                status=result["status"],
                contact=result.get("contact_status"),
                reason=result.get("reason") or "",
                intervals=len(result["intervals"]),
                lower=result["lower_bound_m"] if result["lower_bound_m"] is not None else "",
                witness=result["witness_clearance_m"] if result["witness_clearance_m"] is not None else "",
            )
        )
    return lines


def render_chord_surface_report(study: dict[str, object]) -> str:
    draft = study["study_draft"]
    lines = [
        "# Chord-bearing surface screening, 50 mm hinge",
        "",
        "Retained preview-mesh and GEOM-03 screening of one existing trial hinge. This does not establish finite-hub clearance, controlled folding, strength, vibration, aerodynamic validity, or qualification.",
        "",
        "physical_qualification: false",
        "Qualified winner: none",
        "full_propeller_clearance: null",
        "",
        f"Main head `{study['pins']['main_head']}`.",
        f"Parent packet head `{study['pins']['parent_packet']['head']}` SHA-256 `{study['pins']['parent_packet']['sha256']}`.",
        f"Parent canonical SHA-256 `{study['parent_identity']['canonical_sha256']}`.",
        f"PR #100 study head `{study['pins']['hinge_location_study']['head']}` SHA-256 `{study['pins']['hinge_location_study']['sha256']}`.",
        f"PR #101 study head `{study['pins']['intermediate_fold_study']['head']}` SHA-256 `{study['pins']['intermediate_fold_study']['sha256']}`.",
        f"Study draft SHA-256 `{draft['sha256']}`, hinge `{draft['hinge_declaration']}` from `{draft['hinge_id']}`.",
        "The study-draft identity is separate from the parent canonical identity.",
        "",
        "## Declaration",
        "",
        study["clearance_declaration"]["meaning"],
        "Attachment exclusions remain 0 m. No contact-band source is declared. Budgets are the existing defaults. There is no automatic retry and no budget increase.",
        study["hub_obstacle"]["limitation"],
        "Nothing in this run adds joint relief, hardware, hub height, endcaps, or a surface across the uncovered root or tip span.",
        "",
        "## Deployment preview",
        "",
        "Deployment is a preview mesh at 0 deg. It is not a fourth GEOM report.",
        "",
    ]
    lines.extend(_mesh_lines(study["deployment_preview"]["preview_mesh"]))
    lines.extend(["", "## Proposed stops", ""])
    for stop in study["stops"]:
        document = stop["geom_report"]
        lines.extend(
            [
                f"### {stop['end_angle_deg']:.0f} deg",
                "",
                f"modeled_surface_status: {document['modeled_surface_status']}",
                f"classification: {document['classification']}",
                f"station_span_complete: {str(document['station_span_complete']).lower()}",
                f"root_gap_m: {document['root_gap_m']!r}",
                f"tip_gap_m: {document['tip_gap_m']!r}",
                f"node_comparisons: {document['node_comparisons']}",
                f"feature_tests: {document['feature_tests']}",
                f"full_propeller_clearance: null",
                "",
                "Preview mesh, separate from the centerline quantity:",
                "",
            ]
        )
        lines.extend(_mesh_lines(stop["preview_mesh"]))
        lines.extend(["", "Complete query ledger:", ""])
        lines.extend(_query_summary(document))
        lines.append("")
    lines.extend(
        [
            "## Reading the blocked result",
            "",
            "Every path is unknown and blocked. Hub rows that say separated are continuous lower bounds of the retained triangles against the infinite cylinder. They leave the uncovered root and tip span, the shared hinge, and the interblade pairs unresolved. The first own-root/tip query exhausts the default node and feature budgets without a separation or violation witness. Later own-root/tip and interblade rows stay unknown because the shared global budget is exhausted. Zero attachment exclusion keeps the shared hinge inside that unresolved query.",
            "",
            "The mesh radial envelope is not the centerline radius. At deployment the meshed stations stop short of the blade radius, so the mesh envelope is inside the centerline radius. At the folded stops the chord and thickness put mesh vertices outside the centerline radius. Axial extent is the vertex z range of this planar preview; the same range appears at every recorded pose.",
            "",
        ]
    )
    return "\n".join(lines)


def _mesh_lines(record: dict[str, object]) -> list[str]:
    lines = [
        f"centerline_envelope_radius_m: {record['centerline_envelope_radius_m']!r}",
        f"mesh_envelope_radius_m: {record['mesh_envelope_radius_m']!r}",
        f"axial_min_m: {record['axial_min_m']!r}",
        f"axial_max_m: {record['axial_max_m']!r}",
    ]
    if "pinned_centerline_diameter_m" in record:
        lines.append(f"pinned_centerline_diameter_m: {record['pinned_centerline_diameter_m']!r}")
    return lines


def _blade_loops(mesh):
    per_section = mesh.section_vertex_count
    per_blade = mesh.station_count * per_section
    loops = []
    for blade in range(mesh.blade_count):
        base = blade * per_blade
        for station in range(mesh.station_count):
            start = base + station * per_section
            loop = [mesh.vertices[start + index] for index in range(per_section)]
            loop.append(loop[0])
            loops.append(loop)
    return loops


def _uncovered_segments(bundle: dict[str, object], hinge_radius_m: float, angle_deg: float):
    radius = bundle["diameter"] / 2.0
    hub = bundle["hub_radius"]
    first = bundle["stations"][0]["radius"]
    last = bundle["stations"][-1]["radius"]
    theta = math.radians(angle_deg)

    def point(span: float) -> tuple[float, float, float]:
        if span <= hinge_radius_m:
            return (span, 0.0, 0.0)
        outward = span - hinge_radius_m
        return (
            hinge_radius_m + outward * math.cos(theta),
            outward * math.sin(theta),
            0.0,
        )

    return (point(hub), point(first)), (point(last), point(radius))


def _draw_plan(axis, mesh, bundle, hinge_radius_m: float, angle_deg: float) -> None:
    for loop in _blade_loops(mesh):
        axis.fill(
            [point[0] for point in loop],
            [point[1] for point in loop],
            facecolor="#1f4e79",
            edgecolor="#1f4e79",
            linewidth=0.8,
            alpha=0.85,
            zorder=2,
        )
    axis.add_patch(plt.Circle((0.0, 0.0), bundle["hub_radius"], fill=False, color="0.35", linewidth=1.0))
    for sign in (1.0, -1.0):
        for segment in _uncovered_segments(bundle, hinge_radius_m, angle_deg):
            axis.plot(
                [sign * segment[0][0], sign * segment[1][0]],
                [sign * segment[0][1], sign * segment[1][1]],
                color="#a33b32",
                linestyle=(0, (1.2, 1.0)),
                linewidth=2.0,
            )
        axis.plot([sign * hinge_radius_m], [0.0], marker="o", color="#1f4e79", markersize=3.5)
    limit = bundle["diameter"] / 2.0 * 1.15
    axis.set_xlim(-limit, limit)
    axis.set_ylim(-limit, limit)
    axis.set_aspect("equal")
    axis.set_xlabel("x, m", fontsize=8)
    axis.set_ylabel("y, m", fontsize=8)


def _draw_section(axis, mesh, angle_deg: float) -> None:
    """Draw one tip section face-on, with one metre having the same screen length on each axis."""
    station = mesh.station_count - 1
    per_section = mesh.section_vertex_count
    start = station * per_section
    loop = [mesh.vertices[start + index] for index in range(per_section)]
    loop.append(loop[0])
    collection = Poly3DCollection([loop], alpha=0.55, facecolor="#1f4e79", edgecolor="#c47b2b", linewidths=0.8)
    axis.add_collection3d(collection)
    axis.plot(
        [point[0] for point in loop],
        [point[1] for point in loop],
        [point[2] for point in loop],
        color="#c47b2b",
        linewidth=0.8,
    )
    xs = [point[0] for point in loop]
    ys = [point[1] for point in loop]
    zs = [point[2] for point in loop]
    span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1.0e-6)
    pad = 0.2 * span
    limits = (
        (min(xs) - pad, max(xs) + pad),
        (min(ys) - pad, max(ys) + pad),
        (min(zs) - pad, max(zs) + pad),
    )
    axis.set_xlim(*limits[0])
    axis.set_ylim(*limits[1])
    axis.set_zlim(*limits[2])
    axis.set_box_aspect(tuple(high - low for low, high in limits))
    axis.set_proj_type("ortho")
    axis.view_init(elev=0, azim=angle_deg)
    axis.set_zlabel("z, m", fontsize=7)
    axis.tick_params(labelsize=7)
    theta = math.radians(angle_deg)
    # x and y tick labels share the section plane and overlap. The z ticks keep the metre scale.
    axis.set_xticks([])
    axis.set_yticks([])
    axis.set_xlabel("")
    axis.set_ylabel("")
    axis.figure.canvas.draw()
    matrix = axis.get_proj()

    def screen_length(vector: tuple[float, float, float]) -> float:
        start_point = matrix @ (0.0, 0.0, 0.0, 1.0)
        end_point = matrix @ (*vector, 1.0)
        start_xy = start_point[:2] / start_point[3]
        end_xy = end_point[:2] / end_point[3]
        return math.hypot(float(end_xy[0] - start_xy[0]), float(end_xy[1] - start_xy[1]))

    chord_direction = (-math.sin(theta), math.cos(theta), 0.0)
    thickness_direction = (0.0, 0.0, 1.0)
    chord_pixels = screen_length(chord_direction)
    thickness_pixels = screen_length(thickness_direction)
    if chord_pixels <= 0.0 or abs(thickness_pixels - chord_pixels) / chord_pixels > 0.02:
        raise ValueError("Tip-station view does not use equal metre scale.")


def write_views(repository_root: Path, output_dir: Path) -> None:
    """Draw the full-rotor plan and face-on tip sections at four poses."""
    root = repository_root.resolve()
    packet = json.loads((root / PARENT_PACKET).read_text(encoding="utf-8"))
    hinge_study = json.loads((root / HINGE_STUDY).read_text(encoding="utf-8"))
    fold_study = json.loads((root / FOLD_STUDY).read_text(encoding="utf-8"))
    bundle, _parsed, profile, trial, _draft, blade_count = _study_draft(root, packet, hinge_study)
    angles = [0.0, *[pose["fold_angle_deg"] for pose in fold_study["reported_poses"]]]
    meshes = [_mesh(bundle, profile, trial["radius_m"], blade_count, angle) for angle in angles]
    titles = ["0 deg\ndeployment preview"] + [
        f"{angle:.0f} deg\nproposed stop" for angle in angles[1:]
    ]
    plan, plan_axes = plt.subplots(2, 2, figsize=(8.8, 9.2))
    for axis, mesh, title, angle in zip(plan_axes.ravel(), meshes, titles, angles):
        _draw_plan(axis, mesh, bundle, trial["radius_m"], angle)
        axis.set_title(title, fontsize=9)
    plan.suptitle(
        "Geometric screening plan view\nChord-bearing preview mesh; not surface qualification",
        fontsize=11,
    )
    plan.legend(
        handles=[
            plt.Line2D([0], [0], color="#1f4e79", linewidth=4, label="chord-bearing section"),
            plt.Line2D([0], [0], color="0.35", label="hub radius"),
            plt.Line2D([0], [0], color="#1f4e79", marker="o", label="hinge"),
            plt.Line2D([0], [0], color="#a33b32", linestyle=(0, (1.2, 1.0)), label="uncovered root and tip span"),
        ],
        loc="lower center",
        ncol=2,
        frameon=False,
        fontsize=9,
        bbox_to_anchor=(0.5, 0.02),
        borderaxespad=0.0,
    )
    plan.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.16, hspace=0.46, wspace=0.28)
    surface, surface_axes = plt.subplots(2, 2, figsize=(8.8, 9.0), subplot_kw={"projection": "3d"})
    for axis, mesh, title, angle in zip(surface_axes.ravel(), meshes, titles, angles):
        _draw_section(axis, mesh, angle)
        axis.set_title(title, fontsize=9)
    surface.suptitle(
        "Tip station, face-on orthographic view\nEqual metres on the section axes; not a solid or a clearance result",
        fontsize=11,
    )
    surface.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.06, hspace=0.28, wspace=0.12)
    output_dir.mkdir(parents=True, exist_ok=True)
    plan.savefig(output_dir / "plan_view.png", dpi=140)
    surface.savefig(output_dir / "surface_view.png", dpi=140)
    plt.close(plan)
    plt.close(surface)


def write_chord_surface_study(repository_root: Path, output_dir: Path) -> dict[str, object]:
    study = json.loads(_canonical(build_chord_surface_study(repository_root)))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "study.json").write_text(_canonical(study) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(render_chord_surface_report(study), encoding="utf-8")
    write_views(repository_root, output_dir)
    return study


def _original_bytes(root: Path) -> dict[str, bytes]:
    directory = root / "reports" / "chord_surface_50mm_screening"
    return {
        "study.json": (directory / "study.json").read_bytes(),
        "report.md": (directory / "report.md").read_bytes(),
        "plan_view.png": (directory / "plan_view.png").read_bytes(),
        "surface_view.png": (directory / "surface_view.png").read_bytes(),
    }


def _require_original_bytes(root: Path) -> dict[str, bytes]:
    payload = _original_bytes(root)
    expected = {
        "study.json": ORIGINAL_STUDY_SHA256,
        "report.md": ORIGINAL_REPORT_SHA256,
        "plan_view.png": ORIGINAL_PLAN_SHA256,
        "surface_view.png": ORIGINAL_SURFACE_SHA256,
    }
    for name, digest in expected.items():
        if _sha256_bytes(payload[name]) != digest:
            raise ValueError(f"Original surface artifact {name} is no longer the reviewed bytes.")
    for relative, digest in (
        (PARENT_PACKET, PARENT_PACKET_SHA256),
        (HINGE_STUDY, HINGE_STUDY_SHA256),
        (FOLD_STUDY, FOLD_STUDY_SHA256),
    ):
        if _sha256_bytes((root / relative).read_bytes()) != digest:
            raise ValueError(f"Retained input {relative} changed.")
    return payload


def _retained_parts(root: Path):
    packet = _load_pin(root, PARENT_PACKET, PARENT_PACKET_SHA256)
    hinge_study = _load_pin(root, HINGE_STUDY, HINGE_STUDY_SHA256)
    bundle, _parsed, _profile, trial, draft, _blade_count = _study_draft(root, packet, hinge_study)
    if draft.draft_sha256 != STUDY_DRAFT_SHA256:
        raise ValueError("Retained study-draft identity changed.")
    model, _target, foil = _inputs(draft)
    inputs = SurfaceClearanceInputs(end_angle_deg=DIAGNOSTIC_END_DEG, required_clearance_m=0.0)
    defaults = SurfaceClearanceInputs()
    if inputs.root_attachment_m != defaults.root_attachment_m or inputs.hinge_attachment_m != defaults.hinge_attachment_m:
        raise ValueError("Diagnostic attachments differ from the retained zero exclusions.")
    if inputs.required_clearance_m != 0.0:
        raise ValueError("Diagnostic clearance must stay at zero.")
    parts, _original_count = _parts(model, foil, inputs)
    return bundle, trial, draft, parts


def _pair_controls() -> ClearanceControls:
    return ClearanceControls(
        max_depth=PAIR_MAX_DEPTH,
        max_intervals=PAIR_MAX_INTERVALS,
        max_node_comparisons=PAIR_NODE_COMPARISONS,
        max_feature_tests=PAIR_FEATURE_TESTS,
    )


def build_interblade_pair_diagnostic(repository_root: Path) -> dict[str, object]:
    """Run four separate interblade pair queries without touching the original reports."""
    root = repository_root.resolve()
    original = _require_original_bytes(root)
    study = json.loads(original["study.json"])
    if study["study_draft"]["sha256"] != STUDY_DRAFT_SHA256:
        raise ValueError("Pinned study draft does not match the reviewed surface record.")
    stop_angles = [stop["end_angle_deg"] for stop in study["stops"]]
    if DIAGNOSTIC_END_DEG not in stop_angles:
        raise ValueError("The diagnostic endpoint is not one of the recorded proposed stops.")
    original_stop = next(stop for stop in study["stops"] if stop["end_angle_deg"] == DIAGNOSTIC_END_DEG)
    original_report = original_stop["geom_report"]
    if original_report["full_propeller_clearance"] is not None or original_report["physical_qualification"]:
        raise ValueError("The original report no longer preserves the null clearance gate.")
    own_rows = [row for row in original_report["queries"] if row["kind"] == "own_root_tip"]
    if len(own_rows) != 2 or any(row["result"]["status"] != "unknown" for row in own_rows):
        raise ValueError("The original own-root/tip UNKNOWN findings are no longer intact.")
    bundle, trial, draft, parts = _retained_parts(root)
    lookup = {part.name: part for part in parts}
    if tuple(lookup) != tuple(part.name for part in parts):
        raise ValueError("Retained part names are not unique.")
    for left, right in INTERBLADE_PAIRS:
        if left not in lookup or right not in lookup:
            raise ValueError("A declared interblade pair is missing from the retained surfaces.")
    controls = _pair_controls()
    angle_min = math.radians(DIAGNOSTIC_END_DEG)
    if angle_min >= 0.0 or abs(angle_min) > math.pi:
        raise ValueError("The diagnostic path is outside the kernel's continuous interval.")
    used_nodes = 0
    used_features = 0
    rows = []
    for left, right in INTERBLADE_PAIRS:
        if used_nodes + controls.max_node_comparisons > AGGREGATE_NODE_COMPARISONS:
            raise ValueError("Aggregate comparison ceiling would be increased.")
        if used_features + controls.max_feature_tests > AGGREGATE_FEATURE_TESTS:
            raise ValueError("Aggregate feature-test ceiling would be increased.")
        result = pair_clearance(
            lookup[left],
            lookup[right],
            angle_min_rad=angle_min,
            angle_max_rad=0.0,
            clearance_m=0.0,
            controls=controls,
        )
        mapped = json.loads(_canonical(asdict(result)))
        if mapped["node_comparisons"] > PAIR_NODE_COMPARISONS or mapped["feature_tests"] > PAIR_FEATURE_TESTS:
            raise ValueError("A pair query exceeded its declared budget.")
        used_nodes += mapped["node_comparisons"]
        used_features += mapped["feature_tests"]
        rows.append({"a": left, "b": right, "result": mapped})
    if used_nodes > AGGREGATE_NODE_COMPARISONS or used_features > AGGREGATE_FEATURE_TESTS:
        raise ValueError("Aggregate diagnostic ceiling exceeded.")
    return {
        "record_id": "interblade_pair_diagnostic_50mm_m135",
        "evidence_class": "additional_pair_level_diagnostic_not_the_original_global_report",
        "physical_qualification": False,
        "qualified_winner": None,
        "selected_stop": None,
        "selected_hinge": None,
        "full_propeller_clearance": None,
        "reviewed_surface_head": REVIEWED_SURFACE_HEAD,
        "study_draft_sha256": draft.draft_sha256,
        "parent_canonical_sha256": PARENT_SHA256,
        "hinge_declaration": trial["declaration"],
        "path": {
            "start_deg": 0.0,
            "end_deg": DIAGNOSTIC_END_DEG,
            "meaning": "continuous kernel interval from deployment to this recorded pose; not a selected stop",
        },
        "declaration": {
            "required_clearance_m": 0.0,
            "root_attachment_m": 0.0,
            "hinge_attachment_m": 0.0,
            "calls_per_pair": 1,
            "retries": False,
            "automatic_budget_increases": False,
            "per_pair": {
                "max_node_comparisons": PAIR_NODE_COMPARISONS,
                "max_feature_tests": PAIR_FEATURE_TESTS,
                "max_depth": PAIR_MAX_DEPTH,
                "max_intervals": PAIR_MAX_INTERVALS,
            },
            "aggregate_ceiling": {
                "max_node_comparisons": AGGREGATE_NODE_COMPARISONS,
                "max_feature_tests": AGGREGATE_FEATURE_TESTS,
            },
        },
        "retained_parts": [
            {
                "name": part.name,
                "moving": part.moving,
                "pivot_m": list(part.pivot),
                "triangle_count": len(part.triangles),
            }
            for part in parts
        ],
        "preserved_original_m135": {
            "source": "reports/chord_surface_50mm_screening/study.json",
            "sha256": ORIGINAL_STUDY_SHA256,
            "modeled_surface_status": original_report["modeled_surface_status"],
            "classification": original_report["classification"],
            "station_span_complete": original_report["station_span_complete"],
            "root_gap_m": original_report["root_gap_m"],
            "tip_gap_m": original_report["tip_gap_m"],
            "full_propeller_clearance": original_report["full_propeller_clearance"],
            "own_root_tip": [
                {
                    "a": row["a"],
                    "b": row["b"],
                    "status": row["result"]["status"],
                    "reason": row["result"]["reason"],
                }
                for row in own_rows
            ],
        },
        "aggregate_used": {
            "node_comparisons": used_nodes,
            "feature_tests": used_features,
            "pair_calls": len(rows),
        },
        "pairs": rows,
        "not_executed": ["polar provider", "BEM", "CFD", "FEA", "transient", "original_three_surface_reports"],
        "runtime": {
            "python": platform.python_version(),
            "pyfoldable_version": __version__,
            "physical_qualification": False,
        },
    }


def render_interblade_pair_report(record: dict[str, object]) -> str:
    lines = [
        "# Interblade pair diagnostic, 50 mm hinge, 0 deg to -135 deg",
        "",
        "Additional pair-level diagnostic on the retained surfaces. This is not the original globally budgeted GEOM-03 report, and it does not select a stop or a hinge.",
        "",
        "physical_qualification: false",
        "Qualified winner: none",
        "Selected stop: none",
        "Selected hinge: none",
        "full_propeller_clearance: null",
        "",
        f"Reviewed surface head `{record['reviewed_surface_head']}`.",
        f"Study draft SHA-256 `{record['study_draft_sha256']}`.",
        f"Parent canonical SHA-256 `{record['parent_canonical_sha256']}`.",
        "Requested clearance remains 0 m. Attachment exclusions remain 0 m. Each pair is allowed one call and at most 50000 node comparisons, 2048 feature tests, depth 6 and 127 intervals. The additional aggregate ceiling is 200000 comparisons and 8192 feature tests. There is no retry and no automatic increase.",
        "",
        "## Preserved original -135 deg findings",
        "",
        f"Original study SHA-256 `{record['preserved_original_m135']['sha256']}`.",
        f"modeled_surface_status: {record['preserved_original_m135']['modeled_surface_status']}",
        f"classification: {record['preserved_original_m135']['classification']}",
        f"station_span_complete: {str(record['preserved_original_m135']['station_span_complete']).lower()}",
        f"root_gap_m: {record['preserved_original_m135']['root_gap_m']!r}",
        f"tip_gap_m: {record['preserved_original_m135']['tip_gap_m']!r}",
    ]
    for row in record["preserved_original_m135"]["own_root_tip"]:
        lines.append(f"own_root_tip {row['a']} / {row['b']}: {row['status']}; {row['reason']}")
    lines.extend(
        [
            "",
            "## Pair results",
            "",
            f"Aggregate node comparisons: {record['aggregate_used']['node_comparisons']}",
            f"Aggregate feature tests: {record['aggregate_used']['feature_tests']}",
            f"Pair calls: {record['aggregate_used']['pair_calls']}",
            "",
            "| A | B | Status | Contact | Nodes | Feature tests | Intervals | Lower bound m | Witness m | Reason |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in record["pairs"]:
        result = row["result"]
        lines.append(
            "| {a} | {b} | {status} | {contact} | {nodes} | {features} | {intervals} | {lower} | {witness} | {reason} |".format(
                a=row["a"],
                b=row["b"],
                status=result["status"],
                contact=result["contact_status"],
                nodes=result["node_comparisons"],
                features=result["feature_tests"],
                intervals=len(result["intervals"]),
                lower="" if result["lower_bound_m"] is None else result["lower_bound_m"],
                witness="" if result["witness_clearance_m"] is None else result["witness_clearance_m"],
                reason=result["reason"],
            )
        )
    lines.extend(
        [
            "",
            "The JSON file retains every interval. A separated row is a continuous lower bound between those two retained triangle sets only. It does not close the original own-root/tip result, the missing station span, or full propeller clearance.",
            "",
        ]
    )
    return "\n".join(lines)


def _posed_triangles(part, angle_rad: float) -> list[list[tuple[float, float, float]]]:
    posed = []
    for triangle in part.triangles:
        posed.append([_rotate(point, part, angle_rad) for point in triangle])
    return posed


def _boundary_segments(triangles: list[list[tuple[float, float, float]]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    counts: dict[tuple[tuple[float, float, float], tuple[float, float, float]], int] = {}
    for triangle in triangles:
        for start, end in zip(triangle, triangle[1:] + triangle[:1]):
            key = tuple(sorted((
                tuple(round(float(coord), 12) for coord in start),
                tuple(round(float(coord), 12) for coord in end),
            )))
            counts[key] = counts.get(key, 0) + 1
    segments = []
    for key, count in counts.items():
        if count == 1:
            segments.append(((key[0][0], key[0][1]), (key[1][0], key[1][1])))
    return segments


def _draw_assembly(axis, parts, bundle: dict[str, object], hinge_radius_m: float, angle_deg: float) -> None:
    angle_rad = math.radians(angle_deg)
    for part in parts:
        triangles = _posed_triangles(part, angle_rad)
        color = "#c47b2b" if part.moving else "#1f4e79"
        axis.add_collection(
            PolyCollection(
                [[(point[0], point[1]) for point in triangle] for triangle in triangles],
                facecolors=color,
                edgecolors="none",
                alpha=0.72,
                zorder=2,
            )
        )
        for start, end in _boundary_segments(triangles):
            axis.plot(
                [start[0], end[0]],
                [start[1], end[1]],
                color="#7a2f2a",
                linewidth=0.45,
                solid_capstyle="round",
                zorder=3,
            )
    axis.add_patch(plt.Circle((0.0, 0.0), bundle["hub_radius"], fill=False, color="0.35", linewidth=1.0, zorder=4))
    for sign in (1.0, -1.0):
        for segment in _uncovered_segments(bundle, hinge_radius_m, angle_deg):
            axis.plot(
                [sign * segment[0][0], sign * segment[1][0]],
                [sign * segment[0][1], sign * segment[1][1]],
                color="#a33b32",
                linestyle=(0, (1.2, 1.0)),
                linewidth=1.8,
                zorder=5,
            )
    axis.set_aspect("equal")
    axis.set_xlabel("x, m", fontsize=8)
    axis.set_ylabel("y, m", fontsize=8)


def write_assembly_views(parts, bundle: dict[str, object], hinge_radius_m: float, output_dir: Path) -> None:
    """Draw retained triangles at the recorded poses and a hinge-region close-up."""
    angles = [0.0, -120.0, DIAGNOSTIC_END_DEG, -150.0]
    titles = ["0 deg\ndeployment"] + [
        f"{angle:.0f} deg\nproposed pose, not selected" for angle in angles[1:]
    ]
    assembly, axes = plt.subplots(2, 2, figsize=(8.8, 9.2))
    limit = bundle["diameter"] / 2.0 * 1.15
    for axis, angle, title in zip(axes.ravel(), angles, titles):
        _draw_assembly(axis, parts, bundle, hinge_radius_m, angle)
        axis.set_xlim(-limit, limit)
        axis.set_ylim(-limit, limit)
        axis.set_title(title, fontsize=9)
    assembly.suptitle(
        "Retained-triangle assembly\nFixed root and moving tip; open boundaries; not a solid or a selected design",
        fontsize=11,
    )
    assembly.legend(
        handles=[
            plt.Line2D([0], [0], color="#1f4e79", linewidth=4, label="fixed root triangles"),
            plt.Line2D([0], [0], color="#c47b2b", linewidth=4, label="moving tip triangles"),
            plt.Line2D([0], [0], color="#7a2f2a", label="open boundary"),
            plt.Line2D([0], [0], color="0.35", label="hub radius"),
            plt.Line2D([0], [0], color="#a33b32", linestyle=(0, (1.2, 1.0)), label="uncovered root and tip span"),
        ],
        loc="lower center",
        ncol=2,
        frameon=False,
        fontsize=8,
        bbox_to_anchor=(0.5, 0.02),
        borderaxespad=0.0,
    )
    assembly.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.16, hspace=0.42, wspace=0.28)
    pivot = next(part.pivot for part in parts if part.name == "blade_1_root")
    half = abs(pivot[0]) - bundle["hub_radius"]
    close, close_axes = plt.subplots(2, 2, figsize=(8.8, 9.2))
    for axis, angle, title in zip(close_axes.ravel(), angles, titles):
        _draw_assembly(axis, parts, bundle, hinge_radius_m, angle)
        axis.set_xlim(pivot[0] - half, pivot[0] + half)
        axis.set_ylim(pivot[1] - half, pivot[1] + half)
        axis.set_title(title, fontsize=9)
    close.suptitle(
        "Blade 1 hinge region at equal metres\nOpen root/tip boundary; no endcap or added hardware",
        fontsize=11,
    )
    close.legend(
        handles=[
            plt.Line2D([0], [0], color="#1f4e79", linewidth=4, label="fixed root triangles"),
            plt.Line2D([0], [0], color="#c47b2b", linewidth=4, label="moving tip triangles"),
            plt.Line2D([0], [0], color="#7a2f2a", label="open boundary"),
            plt.Line2D([0], [0], color="#a33b32", linestyle=(0, (1.2, 1.0)), label="uncovered root and tip span"),
        ],
        loc="lower center",
        ncol=2,
        frameon=False,
        fontsize=8,
        bbox_to_anchor=(0.5, 0.02),
        borderaxespad=0.0,
    )
    close.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.16, hspace=0.42, wspace=0.28)
    output_dir.mkdir(parents=True, exist_ok=True)
    assembly.savefig(output_dir / "assembly_view.png", dpi=140)
    close.savefig(output_dir / "hinge_closeup.png", dpi=140)
    plt.close(assembly)
    plt.close(close)


def write_interblade_pair_diagnostic(repository_root: Path, output_dir: Path) -> dict[str, object]:
    before = _require_original_bytes(repository_root)
    record = build_interblade_pair_diagnostic(repository_root)
    stored = json.loads(_canonical(record))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "interblade_pair_diagnostic.json").write_text(_canonical(stored) + "\n", encoding="utf-8")
    (output_dir / "interblade_pair_diagnostic.md").write_text(
        render_interblade_pair_report(stored),
        encoding="utf-8",
    )
    bundle, trial, _draft, parts = _retained_parts(repository_root)
    write_assembly_views(parts, bundle, trial["radius_m"], output_dir)
    if _original_bytes(repository_root) != before:
        raise ValueError("The diagnostic writer changed an original surface artifact.")
    return stored


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    write_interblade_pair_diagnostic(root, root / "reports" / "chord_surface_50mm_screening")


if __name__ == "__main__":
    main()
