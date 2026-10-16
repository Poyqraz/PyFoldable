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
from matplotlib.ticker import FormatStrFormatter, MaxNLocator
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

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
    SurfacePart,
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
            "The JSON file retains every interval. A separated row is a continuous lower bound between those two retained triangle sets on the synchronous path from 0 deg to -135 deg. It leaves the original own-root/tip result UNKNOWN, leaves the station span incomplete, and leaves full_propeller_clearance null.",
            "",
            "## Views and the deployed shared boundary",
            "",
            "assembly_view.png and hinge_closeup.png are historical XY projections. assembly_oblique.png is the historical oblique assembly of both blades. hinge_region_views.png is the earlier hinge figure: its panels still received every blade part, and the axis limits did not remove the opposed blade. Its YZ projection can superimpose that opposed blade after the X axis is suppressed.",
            "",
            "hinge_region_views_blade1.png is the corrected close-up. It draws blade 1's fixed root and moving tip only. The faces are complete hinge-neighborhood triangles. Faces omitted from that selection are absent from the panel; they are not sliced into display endcaps. Both blades remain in the assembly views.",
            "",
            "The preview mesh copies the hinge station twice, once onto the fixed root and once onto the moving tip. At 0 deg the tip rotation is the identity, so those copies occupy one section. That coincidence is the deployed shared boundary of the open mesh.",
            "",
            "A nonzero fold rotates only the moving copy about the hinge pivot's z axis. The fixed copy stays in place. Where an XY projection shows the tip outline crossing the root outline, that crossing is a projection. It is not a contact finding and it is not a separation finding. The own-root/tip queries remain UNKNOWN. The four separated interblade bounds cover only the named retained pairs on the synchronous path from 0 deg to -135 deg. A picture at -150 deg does not extend that query. The canonical -180 deg collision finding remains the archived full-stow result. No joint relief, offset, hardware, endcap, or permitted-contact exclusion is added. Hub height remains absent.",
            "",
        ]
    )
    return "\n".join(lines)


def reconcile_owner_segment_lengths(repository_root: Path) -> dict[str, object]:
    """Compare declared hinge trials with the long-main and 140 mm conditions.

    The arithmetic uses retained parent and study values. It does not run a
    clearance query and it does not select a hinge.
    """
    root = repository_root.resolve()
    packet = _load_pin(root, PARENT_PACKET, PARENT_PACKET_SHA256)
    hinge_study = _load_pin(root, HINGE_STUDY, HINGE_STUDY_SHA256)
    fold_study = _load_pin(root, FOLD_STUDY, FOLD_STUDY_SHA256)
    bundle = packet["parent"]["bundle"]
    radius = bundle["diameter"] / 2.0
    hub = bundle["hub_radius"]
    requirement = fold_study["requirement_m"]
    long_main_lower = radius / 2.0
    fixed_point_upper = requirement / 2.0
    positive_clearance_lower = (radius + hub) / 2.0
    if not long_main_lower < fixed_point_upper < positive_clearance_lower:
        raise ValueError("The necessary range and the full-fold clearance threshold overlap.")
    trials = []
    for item in hinge_study["hinges"]:
        hinge = item["radius_m"]
        distal = radius - hinge
        if hinge > distal:
            full_fold_clearance = (2.0 * hinge - radius) - hub
        else:
            full_fold_clearance = -hub
        trials.append(
            {
                "id": item["id"],
                "declaration": item["declaration"],
                "hinge_m": hinge,
                "main_segment_m": hinge,
                "distal_segment_m": distal,
                "exposed_proximal_span_m": hinge - hub,
                "long_main": hinge > distal,
                "opposed_hinge_point_span_m": 2.0 * hinge,
                "opposed_points_fit_requirement": 2.0 * hinge <= requirement,
                "zero_offset_full_fold_centerline_hub_clearance_m": full_fold_clearance,
            }
        )
    first = bundle["stations"][0]["radius"]
    last = bundle["stations"][-1]["radius"]
    return {
        "pdf_available": False,
        "pdf_name": "2209_B_arastirma_onerisi_formu_18112025 (1).pdf",
        "pdf_sha256": "e16db4182fe5171dc7d06bb05c74875e0e80fac726cd8be52df366c29a7e1541",
        "deployed_radius_m": radius,
        "hub_radius_m": hub,
        "folded_requirement_m": requirement,
        "retained_surface_inner_m": first,
        "retained_surface_outer_m": last,
        "root_gap_m": first - hub,
        "tip_gap_m": radius - last,
        "long_main_requires_hinge_m_greater_than": long_main_lower,
        "fixed_opposed_points_require_hinge_m_at_most": fixed_point_upper,
        "positive_full_fold_centerline_clearance_requires_hinge_m_greater_than": positive_clearance_lower,
        "necessary_range": "62.5 mm < h <= 70 mm",
        "necessary_range_meets_positive_full_fold_clearance": False,
        "trials": trials,
        "canonical_stow_deg": fold_study["canonical_full_stow"]["fold_angle_deg"],
        "canonical_stow_reasons": list(fold_study["canonical_full_stow"]["compatibility_reasons"]),
    }


def render_owner_intent_reconciliation(repository_root: Path) -> str:
    record = reconcile_owner_segment_lengths(repository_root)
    lines = [
        "# Owner-intent reconciliation for the 50 mm screening",
        "",
        "This note records the owner's stated design intent beside the existing trials. It does not select a hinge, a stop, or a qualified design.",
        "",
        f"The original proposal file `{record['pdf_name']}` SHA-256 `{record['pdf_sha256']}` is not in this environment. These sentences do not come from a fresh reading of that PDF. The hash is the one already cited in the 2026-09-09 roadmap entry. The owner's follow-up states the 250 mm deployed and 140 mm folded concept, rotor-parallel hinge axes, and passive opening and folding. Those intents stay distinct from the schema example. The example hub radius, the 50 mm and 100 mm hinge trials, and the -180 deg stop are not proposal requirements.",
        "",
        "In the owner's wording, the proximal main segment of one rotor blade is longer than its hinged distal segment. \"First blade\" and \"second blade\" name those two segments. They do not name the two opposed rotor blades.",
        "",
        "The intended product deploys into aligned, load-transferring blade geometry and produces thrust. It maintains acceptable rotating vibration and deformation, folds in a controlled manner, and accounts for joint and distal-segment losses with applicable models, calibration, and uncertainty. It supports reproducible profile comparisons and user-facing outputs. No acceptance number for vibration, deformation, loss, or thrust is supplied here.",
        "",
        "Lengths below use the axis-to-axis convention. `h` is the motor-axis-to-hinge length. `R-h` is the hinge-to-nominal-tip length. `h-b` is the exposed proximal span. Retained surface coverage is the parent station span and is shorter than those axis lengths.",
        "",
        f"Retained deployed radius R = `{record['deployed_radius_m']!r}` m.",
        f"Retained hub radius b = `{record['hub_radius_m']!r}` m.",
        f"Folded requirement = `{record['folded_requirement_m']!r}` m.",
        f"Retained stations run from `{record['retained_surface_inner_m']!r}` m to `{record['retained_surface_outer_m']!r}` m.",
        f"Root gap `{record['root_gap_m']!r}` m. Tip gap `{record['tip_gap_m']!r}` m.",
        "",
        f"Long-main geometry requires h greater than `{record['long_main_requires_hinge_m_greater_than']!r}` m.",
        f"Opposed hinge points fit the folded requirement only when h is at most `{record['fixed_opposed_points_require_hinge_m_at_most']!r}` m.",
        "The resulting necessary geometric condition is 62.5 mm < h <= 70 mm. It is not a selected hinge and it is not a clearance result.",
        "",
        f"Under the additional schema assumptions of zero hinge offset, this hub radius, and a -180 deg centerline fold, positive hub clearance requires h greater than `{record['positive_full_fold_centerline_clearance_requires_hinge_m_greater_than']!r}` m. That threshold lies outside 62.5 mm < h <= 70 mm. The incompatibility belongs to those combined assumptions. It does not show that the folded 140 mm concept is impossible under a different hub radius, stop angle, or offset.",
        "",
        "| Trial | h m | Main m | Distal m | Exposed proximal m | Long main | Opposed-point span m | Fits 140 mm | Zero-offset -180 deg centerline hub clearance m |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for trial in record["trials"]:
        lines.append(
            "| {declaration} | {hinge!r} | {main!r} | {distal!r} | {exposed!r} | {long_main} | {span!r} | {fits} | {clearance!r} |".format(
                declaration=trial["declaration"],
                hinge=trial["hinge_m"],
                main=trial["main_segment_m"],
                distal=trial["distal_segment_m"],
                exposed=trial["exposed_proximal_span_m"],
                long_main=str(trial["long_main"]).lower(),
                span=trial["opposed_hinge_point_span_m"],
                fits=str(trial["opposed_points_fit_requirement"]).lower(),
                clearance=trial["zero_offset_full_fold_centerline_hub_clearance_m"],
            )
        )
    lines.extend(
        [
            "",
            "In exact millimetre arithmetic on a 125 mm radius, the 50 mm hinge has a 50 mm main segment and a 75 mm distal segment. The 100 mm hinge has a 100 mm main segment and a 25 mm distal segment. The table keeps the retained floating-point subtraction. The 50 mm trial has a distal segment longer than its main segment. The 100 mm trial meets the long-main comparison, and its opposed hinge points span 0.2 m, which is already larger than the 140 mm folded requirement. Neither trial is replaced, rescaled, or given a new twist or stop.",
            "",
            f"The archived canonical stow remains {record['canonical_stow_deg']:.0f} deg with reasons: "
            + ", ".join(record["canonical_stow_reasons"])
            + ".",
            "",
            "Own-root/tip findings on the original surface reports remain UNKNOWN. The separated interblade bounds cover only the retained triangle pairs on the synchronous path from 0 deg to -135 deg. A -150 deg picture does not extend that query. full_propeller_clearance remains null. physical_qualification remains false.",
            "",
            "This geometry note does not resume the blocked real-polar comparison in Draft PR #97.",
            "",
            "Next inputs, with no invented measurements or acceptance limits:",
            "",
            "- an owner-declared motor-axis-to-hinge length, or an explicit revision of the long-main or 140 mm intent",
            "- a proposal hub radius, hinge offset, and fold-stop angle, recorded separately from the schema example",
            "- joint gap, step, hardware, and offsets; these remain absent",
            "- source, method, applicability, and uncertainty for joint and distal-segment loss models",
            "- rotating vibration and deformation evidence",
            "- controlled-fold actuation history, completion, contact, latch, and release evidence",
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


def _boundary_polylines(triangles: list[list[tuple[float, float, float]]]) -> list[list[tuple[float, float, float]]]:
    counts: dict[tuple[tuple[float, float, float], tuple[float, float, float]], int] = {}
    for triangle in triangles:
        for start, end in zip(triangle, triangle[1:] + triangle[:1]):
            key = tuple(sorted((
                tuple(round(float(coord), 12) for coord in start),
                tuple(round(float(coord), 12) for coord in end),
            )))
            counts[key] = counts.get(key, 0) + 1
    return [[key[0], key[1]] for key, count in counts.items() if count == 1]


def _equal_metre_limits(points: list[tuple[float, float, float]]) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    spans = []
    limits = []
    for axis in range(3):
        low = min(point[axis] for point in points)
        high = max(point[axis] for point in points)
        if high - low < 1.0e-9:
            high = low + 1.0e-9
        spans.append(high - low)
        limits.append((low, high))
    pad = 0.04 * max(spans)
    return tuple((low - pad, high + pad) for low, high in limits)


def _apply_equal_metres(axis, limits: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]) -> None:
    axis.set_xlim(*limits[0])
    axis.set_ylim(*limits[1])
    axis.set_zlim(*limits[2])
    axis.set_box_aspect(tuple(high - low for low, high in limits))
    axis.set_proj_type("ortho")
    axis.autoscale(False)


def _screen_length(axis, vector: tuple[float, float, float]) -> float:
    axis.figure.canvas.draw()
    matrix = axis.get_proj()
    start = matrix @ (0.0, 0.0, 0.0, 1.0)
    end = matrix @ (*vector, 1.0)
    start_xy = start[:2] / start[3]
    end_xy = end[:2] / end[3]
    return math.hypot(float(end_xy[0] - start_xy[0]), float(end_xy[1] - start_xy[1]))


def _require_orthographic_scale(axis, horizontal: tuple[float, float, float], vertical: tuple[float, float, float], hidden: tuple[float, float, float]) -> None:
    horizontal_length = _screen_length(axis, horizontal)
    vertical_length = _screen_length(axis, vertical)
    hidden_length = _screen_length(axis, hidden)
    if horizontal_length <= 0.0 or abs(vertical_length - horizontal_length) / horizontal_length > 0.02:
        raise ValueError("Orthographic view stretches one metre relative to another.")
    if hidden_length > 0.02 * horizontal_length:
        raise ValueError("Orthographic view does not look along the requested axis.")


def _open_edge_keys(triangles: list[list[tuple[float, float, float]]]) -> set[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    return {key for key, count in _edge_counts(triangles).items() if count == 1}


def _edge_counts(triangles: list[list[tuple[float, float, float]]]) -> dict[tuple[tuple[float, float, float], tuple[float, float, float]], int]:
    counts: dict[tuple[tuple[float, float, float], tuple[float, float, float]], int] = {}
    for triangle in triangles:
        for start, end in zip(triangle, triangle[1:] + triangle[:1]):
            key = tuple(sorted((
                tuple(round(float(coord), 12) for coord in start),
                tuple(round(float(coord), 12) for coord in end),
            )))
            counts[key] = counts.get(key, 0) + 1
    return counts


def _blade1_hinge_parts(parts) -> tuple[SurfacePart, ...]:
    """Return complete hinge-neighborhood triangles for blade 1 only."""
    selected = []
    for part in parts:
        if not part.name.startswith("blade_1_"):
            continue
        pivot = part.pivot
        hinge_vertices = [
            point
            for triangle in part.triangles
            for point in triangle
            if abs(point[0] - pivot[0]) <= 1.0e-9
        ]
        if not hinge_vertices:
            raise ValueError(f"{part.name} has no duplicated hinge section.")
        section_radius = max(math.dist(point, pivot) for point in hinge_vertices)
        kept = tuple(
            triangle
            for triangle in part.triangles
            if any(math.dist(point, pivot) <= section_radius + 1.0e-9 for point in triangle)
        )
        if not kept:
            raise ValueError(f"{part.name} hinge neighborhood is empty.")
        selected.append(SurfacePart(part.name, kept, part.pivot, part.moving))
    if [part.name for part in selected] != ["blade_1_root", "blade_1_tip"]:
        raise ValueError("Blade 1 hinge selection did not keep the fixed and moving parts.")
    return tuple(selected)


def _draw_retained_faces(axis, parts, angle_deg: float, boundary_parts=None) -> None:
    angle_rad = math.radians(angle_deg)
    sources = parts if boundary_parts is None else boundary_parts
    open_edges = {
        part.name: _open_edge_keys(_posed_triangles(part, angle_rad))
        for part in sources
    }
    for part in parts:
        triangles = _posed_triangles(part, angle_rad)
        axis.add_collection3d(Poly3DCollection(
            triangles,
            facecolors="#c47b2b" if part.moving else "#1f4e79",
            edgecolors="none",
            alpha=0.78,
        ))
        allowed = open_edges.get(part.name, set())
        boundaries = [
            list(key)
            for key, count in _edge_counts(triangles).items()
            if count >= 1 and key in allowed
        ]
        if boundaries:
            axis.add_collection3d(Line3DCollection(boundaries, colors="#7a2f2a", linewidths=0.7))


def _draw_spatial_annotations(
    axis,
    parts,
    bundle: dict[str, object],
    hinge_radius_m: float,
    angle_deg: float,
    *,
    include_opposed: bool = True,
    include_hub_circle: bool = True,
    proximal_gap_only: bool = False,
) -> None:
    signs = (1.0, -1.0) if include_opposed else (1.0,)
    for sign in signs:
        segments = _uncovered_segments(bundle, hinge_radius_m, angle_deg)
        if proximal_gap_only:
            segments = segments[:1]
        for segment in segments:
            axis.plot(
                [sign * segment[0][0], sign * segment[1][0]],
                [sign * segment[0][1], sign * segment[1][1]],
                [sign * segment[0][2], sign * segment[1][2]],
                color="#a33b32",
                linestyle=(0, (1.2, 1.0)),
                linewidth=1.4,
            )
    if include_hub_circle:
        hub = bundle["hub_radius"]
        circle = [
            (hub * math.cos(2.0 * math.pi * index / 80.0), hub * math.sin(2.0 * math.pi * index / 80.0), 0.0)
            for index in range(81)
        ]
        axis.plot(
            [point[0] for point in circle],
            [point[1] for point in circle],
            [point[2] for point in circle],
            color="0.35",
            linewidth=0.8,
        )
    z_low, z_high = axis.get_zlim()
    for part in parts:
        if part.name != "blade_1_root" and not (include_opposed and part.name.endswith("_root")):
            continue
        pivot = part.pivot
        axis.plot([pivot[0], pivot[0]], [pivot[1], pivot[1]], [z_low, z_high], color="#111111", linewidth=1.1)
        axis.scatter([pivot[0]], [pivot[1]], [pivot[2]], color="#111111", s=12, depthshade=False)


def _style_spatial_axis(axis, limits, title: str) -> None:
    _apply_equal_metres(axis, limits)
    axis.set_title(title, fontsize=8)
    axis.set_xlabel("x, m", fontsize=7)
    axis.set_ylabel("y, m", fontsize=7)
    axis.set_zlabel("z, m", fontsize=7, labelpad=10)
    axis.tick_params(labelsize=6)
    axis.xaxis.set_major_locator(MaxNLocator(nbins=4))
    axis.yaxis.set_major_locator(MaxNLocator(nbins=4))
    axis.zaxis.set_major_locator(MaxNLocator(nbins=3))
    axis.zaxis.set_major_formatter(FormatStrFormatter("%.3f"))


def write_spatial_views(repository_root: Path, output_dir: Path) -> None:
    """Add oblique and orthographic views without rewriting the XY figures or clearance records."""
    root = repository_root.resolve()
    before = _original_bytes(root)
    diagnostic_files = (
        "interblade_pair_diagnostic.json",
        "interblade_pair_diagnostic.md",
        "assembly_view.png",
        "hinge_closeup.png",
    )
    diagnostic_before = {
        name: (output_dir / name).read_bytes()
        for name in diagnostic_files
        if (output_dir / name).is_file()
    }
    bundle, trial, _draft, parts = _retained_parts(root)
    angles = (0.0, -120.0, DIAGNOSTIC_END_DEG, -150.0)
    posed_points = [
        point
        for angle in angles
        for part in parts
        for triangle in _posed_triangles(part, math.radians(angle))
        for point in triangle
    ]
    for angle in angles:
        for sign in (1.0, -1.0):
            for segment in _uncovered_segments(bundle, trial["radius_m"], angle):
                posed_points.extend((
                    (sign * segment[0][0], sign * segment[0][1], sign * segment[0][2]),
                    (sign * segment[1][0], sign * segment[1][1], sign * segment[1][2]),
                ))
    assembly_limits = _equal_metre_limits(posed_points)
    oblique, oblique_axes = plt.subplots(2, 2, figsize=(10.2, 10.4), subplot_kw={"projection": "3d"})
    for axis, angle in zip(oblique_axes.ravel(), angles):
        _draw_retained_faces(axis, parts, angle)
        _style_spatial_axis(axis, assembly_limits, f"fold angle {angle:.0f} deg\noblique, equal metres")
        _draw_spatial_annotations(axis, parts, bundle, trial["radius_m"], angle)
        _apply_equal_metres(axis, assembly_limits)
        axis.view_init(elev=24, azim=-58)
    oblique.suptitle(
        "Retained-triangle assembly in 3D\nBoth blades; equal metres on x, y and z; no vertical exaggeration; hardware absent",
        fontsize=11,
    )
    oblique.legend(
        handles=[
            plt.Line2D([0], [0], color="#1f4e79", linewidth=4, label="fixed root triangles"),
            plt.Line2D([0], [0], color="#c47b2b", linewidth=4, label="moving tip triangles"),
            plt.Line2D([0], [0], color="#7a2f2a", label="open boundary"),
            plt.Line2D([0], [0], color="#111111", label="hinge pivot and z axis"),
            plt.Line2D([0], [0], color="0.35", label="hub radius at z = 0"),
            plt.Line2D([0], [0], color="#a33b32", linestyle=(0, (1.2, 1.0)), label="uncovered root and tip span"),
        ],
        loc="lower center",
        ncol=2,
        frameon=False,
        fontsize=8,
        bbox_to_anchor=(0.5, 0.01),
        borderaxespad=0.0,
    )
    oblique.subplots_adjust(left=0.04, right=0.90, top=0.88, bottom=0.16, hspace=0.32, wspace=0.22)
    pivot = next(part.pivot for part in parts if part.name == "blade_1_root")
    half = abs(pivot[0]) - bundle["hub_radius"]
    window_points = [
        point
        for angle in angles
        for part in parts
        for triangle in _posed_triangles(part, math.radians(angle))
        for point in triangle
        if abs(point[0] - pivot[0]) <= half and abs(point[1] - pivot[1]) <= half
    ]
    window_points.extend((
        (pivot[0] - half, pivot[1] - half, min(point[2] for point in window_points)),
        (pivot[0] + half, pivot[1] + half, max(point[2] for point in window_points)),
    ))
    hinge_limits = _equal_metre_limits(window_points)
    hinge_limits = (
        (pivot[0] - half, pivot[0] + half),
        (pivot[1] - half, pivot[1] + half),
        hinge_limits[2],
    )
    close, close_axes = plt.subplots(4, 3, figsize=(11.4, 13.6), subplot_kw={"projection": "3d"})
    view_specs = (
        ("oblique", 24, -58, None),
        ("XZ orthographic", 0, -90, ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0))),
        ("YZ orthographic", 0, 0, ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))),
    )
    for row, angle in enumerate(angles):
        for column, (label, elev, azim, scale_check) in enumerate(view_specs):
            axis = close_axes[row, column]
            _draw_retained_faces(axis, parts, angle)
            _style_spatial_axis(axis, hinge_limits, f"fold angle {angle:.0f} deg\n{label}, equal metres")
            _draw_spatial_annotations(axis, parts, bundle, trial["radius_m"], angle)
            _apply_equal_metres(axis, hinge_limits)
            axis.view_init(elev=elev, azim=azim)
            if label.startswith("XZ"):
                axis.set_yticks([])
                axis.set_ylabel("")
                axis.set_xlabel("")
            elif label.startswith("YZ"):
                axis.set_xticks([])
                axis.set_xlabel("")
                axis.set_ylabel("")
            if scale_check is not None:
                _require_orthographic_scale(axis, *scale_check)
    close.suptitle(
        "Blade 1 hinge region\nPivot and z rotation axis; open boundaries; missing span marked; no hardware or endcap",
        fontsize=11,
    )
    close.legend(
        handles=[
            plt.Line2D([0], [0], color="#1f4e79", linewidth=4, label="fixed root triangles"),
            plt.Line2D([0], [0], color="#c47b2b", linewidth=4, label="moving tip triangles"),
            plt.Line2D([0], [0], color="#7a2f2a", label="open boundary"),
            plt.Line2D([0], [0], color="#111111", label="hinge pivot and z axis"),
            plt.Line2D([0], [0], color="#a33b32", linestyle=(0, (1.2, 1.0)), label="uncovered root and tip span"),
        ],
        loc="lower center",
        ncol=2,
        frameon=False,
        fontsize=8,
        bbox_to_anchor=(0.5, 0.005),
        borderaxespad=0.0,
    )
    close.subplots_adjust(left=0.04, right=0.96, top=0.92, bottom=0.10, hspace=0.42, wspace=0.22)
    output_dir.mkdir(parents=True, exist_ok=True)
    oblique.savefig(output_dir / "assembly_oblique.png", dpi=130)
    close.savefig(output_dir / "hinge_region_views.png", dpi=120)
    plt.close(oblique)
    plt.close(close)
    if _original_bytes(root) != before:
        raise ValueError("Spatial views changed an original surface artifact.")
    for name, payload in diagnostic_before.items():
        if (output_dir / name).read_bytes() != payload:
            raise ValueError(f"Spatial views changed {name}.")


def write_blade1_hinge_views(repository_root: Path, output_dir: Path) -> None:
    """Draw blade 1 hinge neighborhoods without rewriting historical figures or clearance records."""
    root = repository_root.resolve()
    before = _original_bytes(root)
    preserved = (
        "interblade_pair_diagnostic.json",
        "assembly_view.png",
        "hinge_closeup.png",
        "assembly_oblique.png",
        "hinge_region_views.png",
    )
    preserved_before = {
        name: (output_dir / name).read_bytes()
        for name in preserved
        if (output_dir / name).is_file()
    }
    bundle, trial, _draft, parts = _retained_parts(root)
    blade1 = tuple(part for part in parts if part.name.startswith("blade_1_"))
    neighborhood = _blade1_hinge_parts(parts)
    angles = (0.0, -120.0, DIAGNOSTIC_END_DEG, -150.0)
    posed_points = [
        point
        for angle in angles
        for part in neighborhood
        for triangle in _posed_triangles(part, math.radians(angle))
        for point in triangle
    ]
    root_gap = _uncovered_segments(bundle, trial["radius_m"], 0.0)[0]
    posed_points.extend(root_gap)
    hinge_limits = _equal_metre_limits(posed_points)
    close, close_axes = plt.subplots(4, 3, figsize=(11.4, 13.6), subplot_kw={"projection": "3d"})
    view_specs = (
        ("oblique", 24, -58, None),
        ("XZ orthographic", 0, -90, ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0))),
        ("YZ orthographic", 0, 0, ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))),
    )
    for row, angle in enumerate(angles):
        for column, (label, elev, azim, scale_check) in enumerate(view_specs):
            axis = close_axes[row, column]
            _draw_retained_faces(axis, neighborhood, angle, boundary_parts=blade1)
            _style_spatial_axis(
                axis,
                hinge_limits,
                f"fold angle {angle:.0f} deg\n{label}, blade 1 only, equal metres",
            )
            _draw_spatial_annotations(
                axis,
                neighborhood,
                bundle,
                trial["radius_m"],
                angle,
                include_opposed=False,
                include_hub_circle=False,
                proximal_gap_only=True,
            )
            _apply_equal_metres(axis, hinge_limits)
            axis.view_init(elev=elev, azim=azim)
            if label.startswith("XZ"):
                axis.set_yticks([])
                axis.set_ylabel("")
                axis.set_xlabel("")
            elif label.startswith("YZ"):
                axis.set_xticks([])
                axis.set_xlabel("")
                axis.set_ylabel("")
            if scale_check is not None:
                _require_orthographic_scale(axis, *scale_check)
    close.suptitle(
        "Corrected blade 1 hinge neighborhood\nComplete triangles only; equal metres; opposed blade omitted; no added endcap",
        fontsize=11,
    )
    close.legend(
        handles=[
            plt.Line2D([0], [0], color="#1f4e79", linewidth=4, label="fixed root triangles"),
            plt.Line2D([0], [0], color="#c47b2b", linewidth=4, label="moving tip triangles"),
            plt.Line2D([0], [0], color="#7a2f2a", label="open boundary of the full blade 1 mesh"),
            plt.Line2D([0], [0], color="#111111", label="blade 1 hinge pivot and z axis"),
            plt.Line2D([0], [0], color="#a33b32", linestyle=(0, (1.2, 1.0)), label="blade 1 uncovered root span"),
        ],
        loc="lower center",
        ncol=2,
        frameon=False,
        fontsize=8,
        bbox_to_anchor=(0.5, 0.005),
        borderaxespad=0.0,
    )
    close.subplots_adjust(left=0.04, right=0.96, top=0.92, bottom=0.10, hspace=0.42, wspace=0.22)
    output_dir.mkdir(parents=True, exist_ok=True)
    close.savefig(output_dir / "hinge_region_views_blade1.png", dpi=120)
    plt.close(close)
    if _original_bytes(root) != before:
        raise ValueError("Blade 1 views changed an original surface artifact.")
    for name, payload in preserved_before.items():
        if (output_dir / name).read_bytes() != payload:
            raise ValueError(f"Blade 1 views changed historical file {name}.")


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


def refresh_interblade_report(repository_root: Path, output_dir: Path) -> None:
    """Rewrite the readable diagnostic report from the retained JSON without a clearance call."""
    payload = (output_dir / "interblade_pair_diagnostic.json").read_bytes()
    record = json.loads(payload)
    (output_dir / "interblade_pair_diagnostic.md").write_text(
        render_interblade_pair_report(record),
        encoding="utf-8",
    )
    if (output_dir / "interblade_pair_diagnostic.json").read_bytes() != payload:
        raise ValueError("Refreshing the report changed the numerical diagnostic record.")


def write_owner_intent_reconciliation(repository_root: Path, output_dir: Path) -> None:
    (output_dir / "owner_intent_reconciliation.md").write_text(
        render_owner_intent_reconciliation(repository_root),
        encoding="utf-8",
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "reports" / "chord_surface_50mm_screening"
    refresh_interblade_report(root, output)
    write_owner_intent_reconciliation(root, output)
    write_blade1_hinge_views(root, output)


if __name__ == "__main__":
    main()
