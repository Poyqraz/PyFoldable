"""Compare two declared hinge radii on the accepted 250 mm parent.

The parent is realized with the existing station-copy service and must match
the PR #99 canonical bundle. Pose results come from the existing folding
mechanism geometry audit. This script does not add a geometry algorithm and
does not call an aerodynamic or transient solver.
"""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pyfoldable import __version__
from pyfoldable.application.design_draft import DesignDraftInputs
from pyfoldable.application.folding_mechanism import (
    MechanismGeometryInputs,
    build_mechanism_geometry_audit,
)
from pyfoldable.application.parent_blade_generator import generate_parent_blade_cuts
from pyfoldable.core.config import load_design_config
from pyfoldable.core.profile_catalog import load_project_airfoil
from pyfoldable.core.units import normalize_quantity


ACCEPTED_PARENT_SHA256 = "1a149afec4cb192703a597e86717e5040d15e3c7fcb1697b4898ea3d26b6eada"
ACCEPTED_PACKET_HEAD = "3db6b8909aa3e929a557699d98593fccb3fe8c4a"
SOURCE_RELATIVE = "configs/designs/TIP_HINGED_250_CANONICAL.toml"
HINGES = (
    {
        "id": "schema_example_100_mm",
        "declaration": "100 mm",
        "role": "canonical schema-example reference",
    },
    {
        "id": "trial_50_mm",
        "declaration": "50 mm",
        "role": "geometry-screening trial, not an optimum or manufactured design",
    },
)
POSES_DEG = (0.0, -90.0, -180.0)
_SERVICE_PATHS = (
    "pyfoldable/application/folding_mechanism.py",
    "pyfoldable/application/parent_blade_generator.py",
    "pyfoldable/application/parent_blade_comparison.py",
    "pyfoldable/application/blade_stations.py",
    "pyfoldable/application/design_draft.py",
    "pyfoldable/core/profile_catalog.py",
)


def _canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _quantity(value: float, unit: str) -> dict[str, float | str]:
    return {"value": value, "unit": unit}


def _audit_mapping(audit: object) -> dict[str, object]:
    raw = asdict(audit)
    raw["compatibility_reasons"] = list(raw["compatibility_reasons"])
    raw["physical_qualification"] = False
    return raw


def build_hinge_location_study(repository_root: Path) -> dict[str, object]:
    """Run the existing copy and centerline audits for the two declared hinges."""
    root = repository_root.resolve()
    source_path = root / SOURCE_RELATIVE
    source_bytes = source_path.read_bytes()
    model = load_design_config(source_path)
    if model.hinge is None or not model.operating_conditions:
        raise ValueError("The schema example has no hinge or operating condition.")
    requirement_m = normalize_quantity(
        model.metadata["stowed_envelope_requirement"],
        "length",
        field="stowed_envelope_requirement",
    ).si_value
    condition = model.operating_conditions[0]
    inputs = DesignDraftInputs(
        _quantity(model.blade.diameter_m, "m"),
        _quantity(model.blade.hub_radius_m, "m"),
        _quantity(model.hinge.radius_m, "m"),
        model.blade.blade_count,
        model.blade.stations[0].airfoil_id,
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
    profile = load_project_airfoil(inputs.airfoil_id)
    hinges_m = tuple(
        normalize_quantity(item["declaration"], "length", field="hinge").si_value
        for item in HINGES
    )
    generated = generate_parent_blade_cuts(
        source_path,
        inputs,
        profile,
        hinge_radii_m=hinges_m,
        frame_id="schema-example-deployed-shaft",
        evidence_label=(
            "hinge-location geometry screening; schema-example parent; "
            "not a selected or manufactured joint"
        ),
    )
    if source_path.read_bytes() != source_bytes:
        raise ValueError("The canonical source changed during station copy.")
    generated_doc = json.loads(generated.canonical_json)
    if generated_doc["parent_canonical_sha256"] != ACCEPTED_PARENT_SHA256:
        raise ValueError("Realized parent does not match the accepted PR #99 bundle.")
    parent_bundle = generated_doc["parent_bundle"]
    station_ratios = tuple(
        station["radius"] / (parent_bundle["diameter"] / 2.0)
        for station in parent_bundle["stations"]
    )
    hinge_records = []
    for spec, placement in zip(HINGES, generated_doc["placements"]):
        radius_m = placement["hinge_radius_m"]
        necessary_diameter_m = 2.0 * radius_m
        poses = []
        for angle in POSES_DEG:
            audit = build_mechanism_geometry_audit(
                MechanismGeometryInputs(
                    diameter_m=parent_bundle["diameter"],
                    hub_radius_m=parent_bundle["hub_radius"],
                    hinge_radius_m=radius_m,
                    fold_angle_deg=angle,
                    stowed_requirement_m=requirement_m,
                ),
                station_ratios,
            )
            mapped = _audit_mapping(audit)
            if mapped["centerline_envelope_diameter_m"] + 1.0e-12 < necessary_diameter_m:
                raise ValueError("Centerline envelope is below the hinge-diameter bound.")
            poses.append(mapped)
        comparison = placement["comparison"]
        hinge_records.append(
            {
                "id": spec["id"],
                "declaration": spec["declaration"],
                "role": spec["role"],
                "radius_m": radius_m,
                "hinge_station_present": placement["hinge_station_present"],
                "necessary_fixed_section_bound_diameter_m": necessary_diameter_m,
                "necessary_bound_versus_requirement_m": requirement_m - necessary_diameter_m,
                "inherited_rows": {
                    role: {
                        "parent_indices": component["parent_indices"],
                        "station_rows": component["station_rows"],
                    }
                    for role, component in placement["components"].items()
                },
                "station_comparison": comparison["station_comparison"],
                "comparison_rows": comparison["rows"],
                "coverage": comparison["coverage"],
                "missing_parent_stations": comparison["missing_parent_stations"],
                "poses": poses,
            }
        )
    return {
        "study_id": "hinge_location_geometry_screening",
        "evidence_class": "geometric_screening_not_clearance_or_design_suitability",
        "physical_qualification": False,
        "qualified_winner": None,
        "accepted_parent": {
            "pull_request": 99,
            "head": ACCEPTED_PACKET_HEAD,
            "canonical_sha256": ACCEPTED_PARENT_SHA256,
            "packet_modified": False,
        },
        "source": {
            "path": SOURCE_RELATIVE,
            "sha256": _sha256_bytes(source_bytes),
            "stowed_envelope_requirement": model.metadata["stowed_envelope_requirement"],
            "stowed_requirement_m": requirement_m,
        },
        "parent": {
            "canonical_sha256": generated_doc["parent_canonical_sha256"],
            "bundle": parent_bundle,
            "airfoil_id": parent_bundle["airfoil_id"],
            "airfoil_coordinate_sha256": parent_bundle["airfoil_coordinate_sha256"],
        },
        "controls": {
            "chord_scale": 1.0,
            "twist_scale": 1.0,
            "preview_fold_angle_rad": 0.0,
            "hinge_order": [item["declaration"] for item in HINGES],
            "poses_deg": list(POSES_DEG),
        },
        "hinges": hinge_records,
        "distinctions": {
            "radial_projection": (
                "projected_effective_diameter_m is twice the larger of the hinge radius "
                "and the tip center's axial coordinate. A tip that folds inward of the hinge "
                "does not reduce this diameter below twice the hinge radius."
            ),
            "centerline_envelope": (
                "centerline_envelope_diameter_m is twice the larger of the hinge radius "
                "and the tip center's distance from the shaft."
            ),
            "chord_hardware_envelope": (
                "A complete envelope including chord, thickness, and hardware is unsupported. "
                "This study does not compute one."
            ),
            "solver_domains": (
                "These poses are geometric audits. They are not aerodynamic projection solves "
                "and not transient trajectories."
            ),
        },
        "unresolved": [
            "joint thickness",
            "exposed hardware",
            "root-to-tip surface contact",
            "interblade contact",
            "chord-inclusive envelope",
            "strength",
            "vibration",
            "mass, inertia, stiffness, damping, friction, backlash, and restraint",
        ],
        "not_executed": ["polar provider", "BEM", "CFD", "FEA", "transient", "qualification"],
        "services": {
            "station_copy": "pyfoldable.application.parent_blade_generator.generate_parent_blade_cuts",
            "station_comparison": "pyfoldable.application.parent_blade_comparison.compare_parent_blade_stations",
            "geometry_audit": "pyfoldable.application.folding_mechanism.build_mechanism_geometry_audit",
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
            "matplotlib": version("matplotlib"),
            "physical_qualification": False,
        },
    }


def render_hinge_location_report(study: dict[str, object]) -> str:
    """Render the readable comparison without naming a winner."""
    lines = [
        "# Hinge-location geometry screening",
        "",
        "Geometric screening of two declared hinge radii on one immutable 250 mm parent. This is not clearance qualification and not a design selection.",
        "",
        "physical_qualification: false",
        "Qualified winner: none",
        "",
        f"Accepted parent SHA-256 `{study['parent']['canonical_sha256']}`.",
        f"Profile {study['parent']['airfoil_id']} coordinates `{study['parent']['airfoil_coordinate_sha256']}`.",
        f"Declared stowed requirement: {study['source']['stowed_envelope_requirement']}.",
        "",
        "A centerline result does not establish full clearance. Chord, thickness, hardware, root-tip contact, and interblade contact remain unresolved.",
        "",
        "Radial projection is twice the larger of the hinge radius and the tip center's axial coordinate. The centerline envelope is twice the larger of the hinge radius and the tip center's distance from the shaft. A chord-inclusive or hardware-inclusive envelope is not computed.",
        "",
    ]
    for hinge in study["hinges"]:
        lines.extend(
            [
                f"## {hinge['declaration']}",
                "",
                hinge["role"],
                "",
                f"Necessary fixed-section bound: D_envelope >= {hinge['necessary_fixed_section_bound_diameter_m']:.8g} m.",
                f"Requirement minus that bound: {hinge['necessary_bound_versus_requirement_m']:.8g} m.",
                f"Hinge station present in the parent: {str(hinge['hinge_station_present']).lower()}.",
                f"Station comparison: {hinge['station_comparison']}.",
                "Copied chord and twist match the parent wherever a row is marked equal. "
                "A gap status retains missing station coverage; it is not a twist reset.",
                "",
                "| Component | Child index | Parent index | Radius m | Chord m | Twist rad |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in hinge["comparison_rows"]:
            lines.append(
                "| {component} | {child_index} | {parent_index} | {radius:.8g} | {chord:.8g} | {twist:.8g} |".format(
                    component=row["component"],
                    child_index=row["child_index"],
                    parent_index=row["parent_index"],
                    radius=row["child"]["radius_m"],
                    chord=row["child"]["chord_m"],
                    twist=row["child"]["twist_rad"],
                )
            )
        lines.extend(
            [
                "",
                "| Pose deg | Projected diameter m | Centerline envelope m | Hub centerline clearance m | Full-stow hub clearance m | Collision-free minimum envelope m | Requirement margin m | Requirement met | Reasons |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for pose in hinge["poses"]:
            reasons = ", ".join(pose["compatibility_reasons"]) or "none"
            lines.append(
                "| {angle:.8g} | {projected:.8g} | {centerline:.8g} | {hub:.8g} | {stow:.8g} | {minimum:.8g} | {margin:.8g} | {met} | {reasons} |".format(
                    angle=pose["fold_angle_deg"],
                    projected=pose["projected_effective_diameter_m"],
                    centerline=pose["centerline_envelope_diameter_m"],
                    hub=pose["hub_centerline_clearance_m"],
                    stow=pose["full_stow_path_hub_clearance_m"],
                    minimum=pose["collision_free_minimum_envelope_diameter_m"],
                    margin=pose["current_requirement_margin_m"],
                    met=str(pose["current_envelope_requirement_met"]).lower(),
                    reasons=reasons,
                )
            )
        coverage = hinge["coverage"]["parent"]
        lines.extend(
            [
                "",
                f"Parent root coverage gap: {coverage['root_gap_m']!r} m.",
                f"Parent tip coverage gap: {coverage['tip_gap_m']!r} m.",
                "No joint modification was declared. An empty modification list is not a flush joint.",
                "",
            ]
        )
    lines.extend(
        [
            "## Unresolved",
            "",
        ]
    )
    for item in study["unresolved"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_plan_view(study: dict[str, object], path: Path) -> None:
    """Draw centerlines from the recorded audit coordinates."""
    figure, axis = plt.subplots(figsize=(6.2, 6.2))
    requirement = study["source"]["stowed_requirement_m"] / 2.0
    hub = study["parent"]["bundle"]["hub_radius"]
    axis.add_patch(plt.Circle((0.0, 0.0), requirement, fill=False, linestyle="--", color="black", label="140 mm requirement"))
    axis.add_patch(plt.Circle((0.0, 0.0), hub, fill=False, color="0.4", label="hub"))
    colors = ("#1f4e79", "#b85c38")
    styles = {0.0: "-", -90.0: "--", -180.0: ":"}
    for hinge, color in zip(study["hinges"], colors):
        for pose in hinge["poses"]:
            axis.plot(
                [0.0, hinge["radius_m"], pose["tip_center_x_m"]],
                [0.0, 0.0, pose["tip_center_y_m"]],
                color=color,
                linestyle=styles[pose["fold_angle_deg"]],
                linewidth=1.4,
                label=f"{hinge['declaration']}, {pose['fold_angle_deg']:.0f} deg",
            )
    axis.set_aspect("equal")
    axis.set_xlabel("x, m")
    axis.set_ylabel("y, m")
    axis.set_title("Geometric screening plan view\nCenterlines only; not clearance or design suitability")
    axis.legend(frameon=False, fontsize=8)
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=120)
    plt.close(figure)


def write_hinge_location_study(repository_root: Path, output_dir: Path) -> dict[str, object]:
    study = json.loads(_canonical(build_hinge_location_study(repository_root)))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "study.json").write_text(_canonical(study) + "\n", encoding="utf-8")
    (output_dir / "comparison.md").write_text(
        render_hinge_location_report(study), encoding="utf-8"
    )
    write_plan_view(study, output_dir / "plan_view.png")
    return study


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    write_hinge_location_study(root, root / "reports" / "hinge_location_geometry_screening")


if __name__ == "__main__":
    main()
