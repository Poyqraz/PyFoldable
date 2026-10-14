"""Realize the JVP-01 geometry identity packet from the 250 mm schema example.

This uses the existing draft, catalog, and station services. It does not add a
product schema, validator, or physics model, and it does not call a solver.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import tempfile
from importlib.metadata import version
from pathlib import Path

from pyfoldable import __version__
from pyfoldable.application.blade_stations import audit_station_bundle, parse_station_bundle
from pyfoldable.application.design_draft import (
    DesignDraftInputs,
    DraftUnitSelection,
    build_design_draft,
)
from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.config import load_design_config
from pyfoldable.core.profile_catalog import load_project_airfoil


SOURCE_RELATIVE = "configs/designs/TIP_HINGED_250_CANONICAL.toml"
HINGE_DECLARATION = "100 mm"
PROFILE_ID = "NACA2412"
CONTRACT_HEAD = "0d1e78ee3c80ddc05ea8f2b2aa1c329088821369"
CONTRACT_TREE = "206f4980c4cac7df5d5e5ff2df06565363f19dd0"
_SERVICE_PATHS = (
    "pyfoldable/application/blade_stations.py",
    "pyfoldable/application/design_draft.py",
    "pyfoldable/core/airfoil.py",
    "pyfoldable/core/config.py",
    "pyfoldable/core/profile_catalog.py",
    "pyfoldable/core/units.py",
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_text(payload: str) -> str:
    return _sha256_bytes(payload.encode("utf-8"))


def _canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _quantity(value: float, unit: str) -> dict[str, float | str]:
    return {"value": value, "unit": unit}


def _absent(name: str) -> dict[str, object]:
    return {
        "name": name,
        "status": "absent",
        "value": None,
        "source": None,
        "method": None,
        "uncertainty": None,
        "note": (
            "No joint measurement or joint-geometry declaration was supplied. "
            "A schema zero or an UNDEFINED modification field is not this measurement."
        ),
    }


def build_jvp01_packet(repository_root: Path) -> dict[str, object]:
    """Build the schema-example packet from validated source services."""
    root = repository_root.resolve()
    source_path = root / SOURCE_RELATIVE
    source_bytes = source_path.read_bytes()
    source = load_design_config(source_path)
    if source.hinge is None or not source.operating_conditions:
        raise ValueError("The schema example has no hinge or operating condition.")
    if source.blade.stations[0].airfoil_id != PROFILE_ID:
        raise ValueError("The schema example parent profile is not NACA2412.")
    profile = load_project_airfoil(PROFILE_ID)
    coordinate_sha = airfoil_coordinate_sha256(profile)
    condition = source.operating_conditions[0]
    inputs = DesignDraftInputs(
        _quantity(source.blade.diameter_m, "m"),
        _quantity(source.blade.hub_radius_m, "m"),
        _quantity(source.hinge.radius_m, "m"),
        source.blade.blade_count,
        PROFILE_ID,
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
        airfoil_definition=profile,
        units=DraftUnitSelection(length="m", angle="rad", angular_speed="rad/s"),
    )
    if source_path.read_bytes() != source_bytes:
        raise ValueError("The canonical source changed while realizing the parent.")
    with tempfile.TemporaryDirectory(prefix="pyfoldable-jvp01-") as directory:
        draft_path = Path(directory) / "parent.toml"
        draft_path.write_text(draft.toml, encoding="utf-8")
        model = load_design_config(draft_path)
    reloaded = next(item for item in model.airfoils if item.id == PROFILE_ID)
    if airfoil_coordinate_sha256(reloaded) != coordinate_sha:
        raise ValueError("Draft coordinate identity changed.")
    diameter_m = model.blade.diameter_m
    parent_input = {
        "schema_version": 1,
        "units": {"length": "m", "angle": "rad"},
        "diameter": diameter_m,
        "hub_radius": model.blade.hub_radius_m,
        "airfoil_id": PROFILE_ID,
        "airfoil_coordinate_sha256": coordinate_sha,
        "provenance": {
            "kind": "declared_design",
            "reference": model.id,
            "locator": "internal design draft " + draft.draft_sha256,
            "revision": "parent_station_realization_v1",
        },
        "stations": [
            {
                "radius": station.r_over_R * (diameter_m / 2.0),
                "chord": station.chord_m,
                "twist": station.twist_rad,
            }
            for station in model.blade.stations
        ],
    }
    # The draft scales are one, so the source stations are the realized parent.
    # Parse the explicit station JSON through the existing GEOM-02 validator.
    parent = parse_station_bundle(_canonical(parent_input).encode("utf-8"))
    if parent.airfoil_coordinate_sha256 != coordinate_sha:
        raise ValueError("Parent coordinate hash does not match the catalog profile.")
    hinge_radius_m = source.hinge.radius_m
    coverage = audit_station_bundle(
        parent,
        diameter_m=parent.diameter_m,
        hub_radius_m=parent.hub_radius_m,
        hinge_radius_m=hinge_radius_m,
        airfoil_id=PROFILE_ID,
    )
    stations = [
        {
            "radius_m": station.radius_m,
            "r_over_R": station.radius_m / (parent.diameter_m / 2.0),
            "chord_m": station.chord_m,
            "twist_rad": station.twist_rad,
        }
        for station in parent.stations
    ]
    hinge_station = next(
        (
            station
            for station in stations
            if abs(station["radius_m"] - hinge_radius_m)
            <= 8 * max(math.ulp(station["radius_m"]), math.ulp(hinge_radius_m))
        ),
        None,
    )
    parent_bundle = json.loads(parent.canonical_json)
    packet: dict[str, object] = {
        "packet_id": "JVP-01",
        "evidence_class": "schema_example_geometry_identity_not_selected_or_as_built",
        "physical_qualification": False,
        "contract": {
            "path": "docs/jointed_blade_performance_validation_contract.md",
            "reviewed_head": CONTRACT_HEAD,
            "reviewed_tree": CONTRACT_TREE,
            "repository_status": "Draft PR #98; this packet does not modify that documentation",
        },
        "scenario": {
            "id": "250_mm_schema_example",
            "thirteen_inch_included": False,
        },
        "intent": (
            "Canonical 250 mm schema example and its declared 100 mm hinge. "
            "This is schema-example intent, not a selected optimum and not as-built evidence."
        ),
        "source": {
            "path": SOURCE_RELATIVE,
            "sha256": _sha256_bytes(source_bytes),
            "design_id": source.id,
        },
        "draft": {
            "sha256": draft.draft_sha256,
            "source_sha256": draft.source_sha256,
            "chord_scale": 1.0,
            "twist_scale": 1.0,
            "preview_fold_angle_rad": 0.0,
        },
        "profile": {
            "id": PROFILE_ID,
            "airfoil_coordinate_sha256": coordinate_sha,
            "catalog_filename": f"{PROFILE_ID}.dat",
        },
        "parent": {
            "canonical_sha256": parent.canonical_sha256,
            "raw_sha256": parent.raw_sha256,
            "bundle": parent_bundle,
        },
        "case_A": {
            "role": "monolithic_reference",
            "identity": "canonical_bytes_equal_parent_bundle",
            "canonical_sha256": parent.canonical_sha256,
            "bundle": parent_bundle,
        },
        "frame": {
            "id": "schema_example_deployed_shaft",
            "radial_origin": "shaft_axis",
            "pose": "deployed",
            "radius_coordinate": "global_shaft_radius",
            "length_unit": "m",
            "angle_unit": "rad",
            "hinge_axis_elevation_rad": source.hinge.axis_elevation_rad,
            "hinge_axis_azimuth_rad": source.hinge.axis_azimuth_rad,
        },
        "stations": stations,
        "coverage": {
            "root_gap_m": coverage.root_gap_m,
            "tip_gap_m": coverage.tip_gap_m,
            "span_complete": coverage.span_complete,
            "hinge_inside_station_span": coverage.hinge_covered,
            "surface_path_clearance": coverage.surface_path_clearance,
            "interblade_clearance": coverage.interblade_clearance,
            "note": (
                "Root and tip gaps are uncovered station span. "
                "They are not a joint radial gap."
            ),
        },
        "hinge": {
            "radius_m": hinge_radius_m,
            "declaration": HINGE_DECLARATION,
            "source": f"{SOURCE_RELATIVE} [hinge].radius",
            "label": "schema_example_declared_hinge_not_selected_optimum",
            "existing_station_matched": hinge_station,
            "station_inserted": False,
            "schema_axial_offset_m": source.hinge.axial_offset_m,
            "schema_tangential_offset_m": source.hinge.tangential_offset_m,
            "schema_offset_meaning": (
                "The schema file sets these offsets to zero. Those zeros are not a "
                "measurement that the joint is flush."
            ),
        },
        "geometric_inventory": {
            "radial_gap": _absent("radial_gap"),
            "surface_step": _absent("surface_step"),
            "fold_misalignment": _absent("fold_misalignment"),
            "pitch_misalignment": _absent("pitch_misalignment"),
            "sweep_misalignment": _absent("sweep_misalignment"),
            "exposed_hardware": _absent("exposed_hardware"),
            "joint_tolerances": _absent("joint_tolerances"),
        },
        "mechanical_properties": {
            "mass": "unestablished",
            "center_of_mass": "unestablished",
            "inertia": "unestablished",
            "materials": "unestablished",
            "stiffness": "unestablished",
            "damping": "unestablished",
            "friction": "unestablished",
            "backlash": "unestablished",
            "restraint": "unestablished",
            "stop_latch": "unestablished",
        },
        "case_C": {
            "status": "unsolved",
            "motion": "absent",
            "clearance": "absent",
            "contact": "absent",
            "latch": "absent",
            "release": "absent",
            "closed_envelope": "absent",
        },
        "missing_inputs": [
            "joint radial gap",
            "surface step",
            "fold misalignment",
            "pitch misalignment",
            "sweep misalignment",
            "exposed hardware identity and envelope",
            "joint tolerances",
            "measurement source, method, and uncertainty for every geometric field",
            "mass, center, and inertia",
            "materials",
            "stiffness, damping, friction, backlash, restraint, and stop or latch calibration",
            "Case C motion, clearance, contact, latch, release, and closed envelope",
            "as-built joint evidence",
            "acceptance limits",
        ],
        "not_executed": [
            "BEM",
            "polar provider",
            "CFD",
            "FEA",
            "trajectory",
            "qualification change",
        ],
        "services": {
            "parent_bundle_reused": False,
            "reason": (
                "No committed immutable parent bundle was present. "
                "The parent was realized from the canonical TOML through "
                "build_design_draft, load_project_airfoil, parse_station_bundle, "
                "and audit_station_bundle."
            ),
            "two_cut_generator_used": False,
            "two_cut_generator_reason": (
                "generate_parent_blade_cuts requires two hinge radii. "
                "This packet declares only the schema example's 100 mm hinge, "
                "so no second hinge was invented."
            ),
            "source_files_sha256": {
                relative: _sha256_bytes((root / relative).read_bytes())
                for relative in _SERVICE_PATHS
            },
        },
        "runtime": {
            "python": platform.python_version(),
            "pyfoldable_version": __version__,
            "numpy": version("numpy"),
            "scipy": version("scipy"),
            "physical_qualification": False,
        },
    }
    if packet["case_A"]["bundle"] != packet["parent"]["bundle"]:
        raise ValueError("Case A does not match the parent bundle.")
    if packet["case_A"]["canonical_sha256"] != packet["parent"]["canonical_sha256"]:
        raise ValueError("Case A hash does not match the parent hash.")
    return packet


def render_jvp01_report(packet: dict[str, object]) -> str:
    """Render the short readable packet report."""
    parent = packet["parent"]
    profile = packet["profile"]
    source = packet["source"]
    hinge = packet["hinge"]
    coverage = packet["coverage"]
    lines = [
        "# JVP-01 geometry identity",
        "",
        "Schema-example intent for the canonical 250 mm blade and its declared 100 mm hinge. This is not a selected joint and not as-built evidence.",
        "",
        "physical_qualification: false",
        "",
        "## Identities",
        "",
        f"- Source `{source['path']}` SHA-256 `{source['sha256']}`.",
        f"- Draft SHA-256 `{packet['draft']['sha256']}`. Chord scale and twist scale are 1.",
        f"- Profile {profile['id']} coordinate SHA-256 `{profile['airfoil_coordinate_sha256']}`.",
        f"- Parent canonical SHA-256 `{parent['canonical_sha256']}`.",
        f"- Case A canonical SHA-256 `{packet['case_A']['canonical_sha256']}`.",
        "- Case A bytes are the parent bundle.",
        "",
        "## Stations",
        "",
        "Frame `schema_example_deployed_shaft`: global shaft radius, deployed pose, metres and radians.",
        "",
        "| Radius m | r/R | Chord m | Twist rad |",
        "| --- | --- | --- | --- |",
    ]
    for station in packet["stations"]:
        lines.append(
            f"| {station['radius_m']:.8g} | {station['r_over_R']:.8g} | "
            f"{station['chord_m']:.8g} | {station['twist_rad']:.8g} |"
        )
    lines.extend(
        [
            "",
            f"Root coverage gap: {coverage['root_gap_m']!r} m.",
            f"Tip coverage gap: {coverage['tip_gap_m']!r} m.",
            f"Station span complete: {str(coverage['span_complete']).lower()}.",
            "These are the validated station-span gaps. The JSON file retains the same floats. They are missing parent stations, not a joint gap.",
            "",
            "## Hinge",
            "",
            f"Declared radius {hinge['radius_m']:.8g} m from `{hinge['source']}` = {hinge['declaration']}.",
            "Label: schema-example hinge, not a selected optimum.",
            "No station was inserted. The radius matches an existing parent station."
            if hinge["existing_station_matched"] is not None
            else "No existing station matches this radius, and none was invented.",
            "The schema file sets axial and tangential offsets to 0 mm. Those zeros are not a flush-joint measurement.",
            "",
            "## Geometric inventory",
            "",
            "| Field | Status |",
            "| --- | --- |",
        ]
    )
    for name, field in packet["geometric_inventory"].items():
        lines.append(f"| {name} | {field['status']} |")
    lines.extend(
        [
            "",
            "No geometric field is measured, so no measurement source, method, or uncertainty is recorded.",
            "",
            "## Mechanical properties",
            "",
        ]
    )
    for name, status in packet["mechanical_properties"].items():
        lines.append(f"- {name}: {status}")
    lines.extend(
        [
            "",
            "Shared parent lineage does not establish that Case A equals a jointed Case B.",
            "",
            "## Case C",
            "",
            "Unsolved. Motion, clearance, contact, latch, release, and the closed envelope are absent.",
            "",
            "## Missing inputs",
            "",
        ]
    )
    for item in packet["missing_inputs"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "Reviewed contract head "
            f"`{packet['contract']['reviewed_head']}`, tree "
            f"`{packet['contract']['reviewed_tree']}`. This packet does not modify that document.",
            "",
        ]
    )
    return "\n".join(lines)


def write_jvp01_packet(repository_root: Path, output_dir: Path) -> dict[str, object]:
    packet = json.loads(_canonical(build_jvp01_packet(repository_root)))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "packet.json").write_text(_canonical(packet) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(render_jvp01_report(packet), encoding="utf-8")
    return packet


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    write_jvp01_packet(root, root / "reports" / "jvp01_geometry_identity")


if __name__ == "__main__":
    main()
