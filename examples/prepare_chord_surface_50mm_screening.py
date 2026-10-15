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
from importlib.metadata import version
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from pyfoldable import __version__
from pyfoldable.application.blade_stations import parse_station_bundle
from pyfoldable.application.design_draft import (
    DesignDraftInputs,
    DraftUnitSelection,
    build_design_draft,
)
from pyfoldable.application.surface_clearance import (
    SurfaceClearanceInputs,
    prepare_surface_clearance,
    run_surface_clearance,
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


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    write_chord_surface_study(root, root / "reports" / "chord_surface_50mm_screening")


if __name__ == "__main__":
    main()
