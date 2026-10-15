"""Intermediate centerline screening for the existing 50 mm hinge.

Closed-form envelope and contact angles are derived independently and then
compared with the existing planar geometry audit. The archived PR #100 study
is not rewritten.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
from dataclasses import asdict
from decimal import Decimal, ROUND_HALF_UP
from importlib.metadata import version
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pyfoldable import __version__
from pyfoldable.application.folding_mechanism import (
    MechanismGeometryInputs,
    build_mechanism_geometry_audit,
)


ARCHIVED_STUDY = "reports/hinge_location_geometry_screening/study.json"
ARCHIVED_HEAD = "56a3b52a439c408cbdd13ae3baf8c43fa577bf71"
ACCEPTED_PARENT_SHA256 = "1a149afec4cb192703a597e86717e5040d15e3c7fcb1697b4898ea3d26b6eada"
HINGE_M = 0.05
HUB_M = 0.018
DIAMETER_M = 0.25
REQUIREMENT_M = 0.140
STATION_RATIOS = (0.20, 0.40, 0.60, 0.80, 0.98)
REPORT_ANGLES_DEG = (-120.0, -135.0, -150.0)
CANONICAL_STOW_DEG = -180.0
# Slightly less folded than the envelope root. The 1e-9 m audit rule can still
# pass here; analytic membership must not.
TOLERANCE_WITNESS_DEG = -115.46756004247239
AUDIT_TOLERANCE_M = max(1.0e-9, (DIAMETER_M / 2.0) * 1.0e-9)
_PATH_MINIMUM_PROOF = (
    "From deployment at 0 deg to -90 deg, the perpendicular foot lies before the "
    "hinge, so the closest point on the movable centerline is the hinge and hub "
    "clearance is constant at hinge radius minus hub radius. From -90 deg to "
    "-180 deg, t = -hinge*cos(theta) stays on the 75 mm segment because the hinge "
    "radius is smaller than the tip length, and clearance is -hinge*sin(theta) - hub. "
    "Its derivative -hinge*cos(theta) is positive on that interval, so clearance "
    "increases as theta increases. The minimum from deployment to a stop is "
    "therefore the clearance at that stop. That continuous-path minimum is a "
    "different quantity from the instantaneous clearance at another angle and "
    "from the canonical full-stow diagnostic, which remains the separate -180 deg "
    "path finding."
)


def _canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _round_half_up(degrees: float) -> str:
    """Round a degree value half away from zero to two decimal places."""
    return str(Decimal(str(degrees)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _derived_angles() -> dict[str, float]:
    """Solve the centerline envelope and hub-tangent contact angles.

    The movable centerline runs from the hinge at ``(R, 0)`` through a tip of
    length ``L`` at fold angle ``theta`` in ``[-pi, 0]``. Its tip-center
    distance is ``sqrt(R^2 + L^2 + 2 R L cos(theta))``. The 140 mm envelope
    holds when that distance is at most 70 mm. Hub contact for a tip long
    enough to reach the tangent point is ``theta = -pi + asin(hub / R)``.
    """
    radius = DIAMETER_M / 2.0
    length = radius - HINGE_M
    cosine = ((REQUIREMENT_M / 2.0) ** 2 - HINGE_M**2 - length**2) / (
        2.0 * HINGE_M * length
    )
    if not -1.0 <= cosine <= 1.0:
        raise ValueError("Envelope angle is not real for this hinge.")
    envelope = -math.acos(cosine)
    tangent = math.sqrt(HINGE_M**2 - HUB_M**2)
    if length < tangent:
        raise ValueError("The movable segment does not reach the hub tangent point.")
    contact = -math.pi + math.asin(HUB_M / HINGE_M)
    return {
        "tip_length_m": length,
        "envelope_cosine": cosine,
        "envelope_rad": envelope,
        "envelope_deg": math.degrees(envelope),
        "tangent_length_m": tangent,
        "contact_rad": contact,
        "contact_deg": math.degrees(contact),
    }


def _analytic_hub_clearance_m(angle_deg: float) -> float:
    """Movable-centerline hub clearance from the closed-form segment distance.

    The formula is the perpendicular distance only while the foot stays on the
    segment. This hinge satisfies that from -90 deg through -180 deg because
    the hinge radius is smaller than the tip length.
    """
    theta = math.radians(angle_deg)
    length = DIAMETER_M / 2.0 - HINGE_M
    foot = -HINGE_M * math.cos(theta)
    if angle_deg > -90.0:
        if foot > 1.0e-12:
            raise ValueError("Deployed-side foot is not at the hinge.")
        return HINGE_M - HUB_M
    if foot < -1.0e-12 or foot > length:
        raise ValueError(
            "Perpendicular foot leaves the movable segment; the closed form does not apply."
        )
    return -HINGE_M * math.sin(theta) - HUB_M


def _audit(angle_deg: float, derived: dict[str, float]) -> dict[str, object]:
    audit = build_mechanism_geometry_audit(
        MechanismGeometryInputs(
            diameter_m=DIAMETER_M,
            hub_radius_m=HUB_M,
            hinge_radius_m=HINGE_M,
            fold_angle_deg=angle_deg,
            stowed_requirement_m=REQUIREMENT_M,
        ),
        STATION_RATIOS,
    )
    mapped = asdict(audit)
    mapped["compatibility_reasons"] = list(mapped["compatibility_reasons"])
    mapped["physical_qualification"] = False
    mapped["instant_hub_clearance_strictly_positive"] = (
        mapped["hub_centerline_clearance_m"] > 0.0
    )
    mapped["tolerance_based_envelope_diagnostic"] = mapped[
        "current_envelope_requirement_met"
    ]
    mapped["inside_partial_fold_interval"] = (
        derived["contact_deg"] < angle_deg <= derived["envelope_deg"]
    )
    analytic_clearance = _analytic_hub_clearance_m(angle_deg)
    if abs(analytic_clearance - mapped["hub_centerline_clearance_m"]) > 1.0e-12:
        raise ValueError("Analytic hub clearance does not match the geometry audit.")
    mapped["analytic_hub_clearance_m"] = analytic_clearance
    mapped["deployment_to_stop_minimum_hub_clearance_m"] = analytic_clearance
    return mapped


def build_intermediate_fold_study(repository_root: Path) -> dict[str, object]:
    """Record the partial-fold interval without replacing the archived stow."""
    root = repository_root.resolve()
    archived_path = root / ARCHIVED_STUDY
    archived_bytes = archived_path.read_bytes()
    archived = json.loads(archived_bytes)
    if archived["parent"]["canonical_sha256"] != ACCEPTED_PARENT_SHA256:
        raise ValueError("Archived study parent identity changed.")
    derived = _derived_angles()
    envelope_audit = _audit(derived["envelope_deg"], derived)
    contact_audit = _audit(derived["contact_deg"], derived)
    witness = _audit(TOLERANCE_WITNESS_DEG, derived)
    if abs(envelope_audit["centerline_envelope_diameter_m"] - REQUIREMENT_M) > 1.0e-12:
        raise ValueError("Derived envelope angle does not meet the audit diameter.")
    if abs(contact_audit["hub_centerline_clearance_m"]) > 1.0e-9:
        raise ValueError("Derived contact angle is not a numerical zero clearance.")
    if contact_audit["instant_hub_clearance_strictly_positive"]:
        raise ValueError("Contact angle must be excluded from the open interval.")
    reported = [_audit(angle, derived) for angle in REPORT_ANGLES_DEG]
    canonical = _audit(CANONICAL_STOW_DEG, derived)
    required_reasons = {
        "full_stow_path_intersects_hub",
        "surface_stations_do_not_cover_hub_to_tip",
    }
    for pose in (*reported, envelope_audit, contact_audit, witness, canonical):
        if not required_reasons.issubset(pose["compatibility_reasons"]):
            raise ValueError("A partial-fold record dropped a full-stow or coverage finding.")
        if pose["deployment_to_stop_minimum_hub_clearance_m"] != pose["analytic_hub_clearance_m"]:
            raise ValueError("Path minimum must be the closed-form clearance at the stop.")
    if not envelope_audit["inside_partial_fold_interval"]:
        raise ValueError("Envelope equality must remain inside the analytic interval.")
    if contact_audit["inside_partial_fold_interval"]:
        raise ValueError("First contact must remain outside the analytic interval.")
    if not witness["tolerance_based_envelope_diagnostic"]:
        raise ValueError("Witness must pass the legacy tolerance envelope diagnostic.")
    if witness["inside_partial_fold_interval"]:
        raise ValueError("Witness must lie outside the analytic interval.")
    if witness["fold_angle_deg"] in REPORT_ANGLES_DEG:
        raise ValueError("Witness must stay out of the proposed-stop list.")
    return {
        "study_id": "intermediate_fold_50mm_centerline_screening",
        "evidence_class": "nominal_centerline_screening_not_surface_clearance",
        "physical_qualification": False,
        "qualified_winner": None,
        "archived_study": {
            "path": ARCHIVED_STUDY,
            "head": ARCHIVED_HEAD,
            "sha256": _sha256_bytes(archived_bytes),
            "modified": False,
        },
        "parent": {
            "canonical_sha256": ACCEPTED_PARENT_SHA256,
            "packet_modified": False,
        },
        "hinge": {
            "declaration": "50 mm",
            "radius_m": HINGE_M,
            "role": "existing geometry-screening trial, not an optimum or manufactured design",
        },
        "requirement_m": REQUIREMENT_M,
        "audit_tolerance_m": AUDIT_TOLERANCE_M,
        "rounding": {
            "rule": "ROUND_HALF_UP",
            "unit": "degree",
            "places": 2,
        },
        "derived": {
            **derived,
            "envelope_deg_rounded": _round_half_up(derived["envelope_deg"]),
            "contact_deg_rounded": _round_half_up(derived["contact_deg"]),
            "envelope_endpoint": "included",
            "contact_endpoint": "excluded",
            "interval": (
                "Angles more folded than the envelope root, up to but not including "
                "first contact: (contact_deg, envelope_deg]."
            ),
            "membership_rule": (
                "inside_partial_fold_interval is contact_deg < theta <= envelope_deg "
                "on the unrounded roots. Envelope equality is included. First contact "
                "is excluded. The tolerance-based envelope diagnostic is a separate field."
            ),
        },
        "boundary_audits": {
            "envelope_entry": envelope_audit,
            "first_contact": contact_audit,
        },
        "inert_tolerance_witness": {
            "role": "inert_regression_not_a_proposed_stop",
            "fold_angle_deg": TOLERANCE_WITNESS_DEG,
            "tolerance_based_envelope_diagnostic": witness[
                "tolerance_based_envelope_diagnostic"
            ],
            "inside_partial_fold_interval": witness["inside_partial_fold_interval"],
            "audit": witness,
        },
        "deployment_to_stop_minimum": {
            "quantity": (
                "minimum movable-centerline hub clearance on the continuous path "
                "from 0 deg to the posed stop"
            ),
            "proof": _PATH_MINIMUM_PROOF,
            "established_by": "closed_form_monotonicity",
            "sampled_poses_are_proof": False,
        },
        "reported_poses": reported,
        "canonical_full_stow": canonical,
        "distinctions": {
            "analytic_interval": (
                "inside_partial_fold_interval is membership in (contact_deg, envelope_deg] "
                "using the unrounded roots."
            ),
            "tolerance_based_envelope_diagnostic": (
                "current_envelope_requirement_met remains the existing audit rule that a "
                "140 mm margin of at least -1e-9 m passes. That diagnostic is separate "
                "from analytic interval membership."
            ),
            "endpoint_envelope": (
                "At the unrounded envelope root the centerline diameter equals 140 mm "
                "and the angle is inside the analytic interval."
            ),
            "path_hub_clearance": _PATH_MINIMUM_PROOF,
            "three_clearances": (
                "hub_centerline_clearance_m is the clearance at the posed angle. "
                "deployment_to_stop_minimum_hub_clearance_m is the minimum of that "
                "clearance on the continuous path from deployment to the posed stop. "
                "full_stow_path_hub_clearance_m is the canonical full-stow diagnostic "
                "and stays negative at every pose of this hinge."
            ),
        },
        "surface_clearance_inputs_still_required": [
            "chord-bearing section surfaces or solids, not only the centerline",
            "joint thickness and exposed hardware, both absent",
            "explicit root-gap and tip-gap surface treatment",
            "both blade surfaces, the hub solid, and any interblade pair",
            "a declared clearance tolerance and frame for GEOM-03 or GEOM-04",
            "manufacturing tolerances or an explicit statement that they are absent",
        ],
        "not_inferred": [
            "surface clearance",
            "controlled folding",
            "strength",
            "vibration",
            "aerodynamic validity",
            "qualification",
        ],
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


def render_intermediate_fold_report(study: dict[str, object]) -> str:
    derived = study["derived"]
    lines = [
        "# Intermediate-fold centerline screening, 50 mm hinge",
        "",
        "Nominal centerline screening of one existing trial hinge. This does not establish surface clearance, controlled folding, strength, vibration, aerodynamic validity, or qualification.",
        "",
        "physical_qualification: false",
        "Qualified winner: none",
        "",
        f"Archived PR #100 study `{study['archived_study']['head']}` SHA-256 `{study['archived_study']['sha256']}`.",
        f"Parent SHA-256 `{study['parent']['canonical_sha256']}`.",
        "",
        "## Interval",
        "",
        "The envelope root uses cosine "
        f"`{derived['envelope_cosine']!r}`, the binary64 value of "
        "`(0.070^2 - 0.050^2 - 0.075^2) / (2*0.050*0.075)`. "
        "That quotient is -0.43 in exact decimal arithmetic. "
        f"Unrounded fold angle: {derived['envelope_deg']!r} deg. "
        f"Rounded half up to 0.01 deg: {derived['envelope_deg_rounded']} deg. "
        "The analytic interval is closed at that unrounded root, so envelope equality is included.",
        "",
        "First contact solves `theta = -pi + asin(0.018 / 0.05)` because the 75 mm segment reaches the hub tangent. "
        f"Unrounded fold angle: {derived['contact_deg']!r} deg. "
        f"Rounded half up to 0.01 deg: {derived['contact_deg_rounded']} deg. "
        "The unrounded root is excluded because clearance there is numerical zero, not strictly positive. "
        "The rounded label is slightly more folded than the root and is not the interval endpoint.",
        "",
        "Open-closed interval of the unrounded roots: (first contact, envelope entry].",
        "`inside_partial_fold_interval` follows that predicate. "
        "`tolerance_based_envelope_diagnostic` keeps the existing audit rule that a 140 mm margin of at least -1e-9 m passes.",
        "Instant hub clearance can be positive inside the analytic interval while `full_stow_path_intersects_hub` and `surface_stations_do_not_cover_hub_to_tip` remain.",
        "",
        "## Inert tolerance witness",
        "",
    ]
    witness = study["inert_tolerance_witness"]
    lines.extend(
        [
            f"Fold angle {witness['fold_angle_deg']!r} deg is an inert regression, not a proposed stop.",
            "It sits slightly less folded than the envelope root.",
            f"Tolerance-based envelope diagnostic: {str(witness['tolerance_based_envelope_diagnostic']).lower()}.",
            f"Analytic interval membership: {str(witness['inside_partial_fold_interval']).lower()}.",
            "",
            "## Deployment-to-stop minimum",
            "",
            study["deployment_to_stop_minimum"]["proof"],
            "The retained value on each proposed stop is that closed-form stop clearance. Sampled poses are not the proof.",
            f"Canonical full-stow clearance on every pose: {study['canonical_full_stow']['full_stow_path_hub_clearance_m']!r} m.",
            "",
            "## Reported poses",
            "",
            "These three angles are proposed intermediate-stop alternatives. They do not replace the canonical -180 deg declaration.",
            "",
            "| Pose deg | Centerline diameter m | Instant hub clearance m | Deployment-to-stop minimum m | Canonical full-stow clearance m | Analytic interval | Tolerance envelope diagnostic | Full-stow collision retained | Missing surface retained |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for pose in study["reported_poses"]:
        reasons = set(pose["compatibility_reasons"])
        lines.append(
            "| {angle:.0f} | {diameter!r} | {instant!r} | {path_min!r} | {full_stow!r} | {member} | {tolerance} | {stow} | {surface} |".format(
                angle=pose["fold_angle_deg"],
                diameter=pose["centerline_envelope_diameter_m"],
                instant=pose["hub_centerline_clearance_m"],
                path_min=pose["deployment_to_stop_minimum_hub_clearance_m"],
                full_stow=pose["full_stow_path_hub_clearance_m"],
                member=str(pose["inside_partial_fold_interval"]).lower(),
                tolerance=str(pose["tolerance_based_envelope_diagnostic"]).lower(),
                stow=str("full_stow_path_intersects_hub" in reasons).lower(),
                surface=str("surface_stations_do_not_cover_hub_to_tip" in reasons).lower(),
            )
        )
    stow = study["canonical_full_stow"]
    lines.extend(
        [
            "",
            "## Canonical -180 deg",
            "",
            f"Centerline diameter {stow['centerline_envelope_diameter_m']!r} m.",
            f"Instant hub clearance {stow['hub_centerline_clearance_m']!r} m.",
            f"Deployment-to-stop minimum if the stop were -180 deg: {stow['deployment_to_stop_minimum_hub_clearance_m']!r} m.",
            f"Canonical full-stow clearance {stow['full_stow_path_hub_clearance_m']!r} m.",
            "Reasons: " + ", ".join(stow["compatibility_reasons"]) + ".",
            "This collision finding stays in force if an intermediate stop is later proposed.",
            "",
            "## Still required for finite-surface clearance",
            "",
        ]
    )
    for item in study["surface_clearance_inputs_still_required"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _blade_segments(pose: dict[str, object]) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    hinge = HINGE_M
    length = DIAMETER_M / 2.0 - hinge
    tip_x = float(pose["tip_center_x_m"])
    tip_y = float(pose["tip_center_y_m"])
    direction = ((tip_x - hinge) / length, tip_y / length)
    radius = DIAMETER_M / 2.0
    stations = [ratio * radius for ratio in STATION_RATIOS]
    fixed = [radius_m for radius_m in stations if radius_m <= hinge]
    movable = [radius_m - hinge for radius_m in stations if radius_m >= hinge]

    def point(distance: float) -> tuple[float, float]:
        return (hinge + distance * direction[0], distance * direction[1])

    covered = [(fixed[0], 0.0), (hinge, 0.0)]
    covered.extend(point(distance) for distance in movable)
    gaps = [((HUB_M, 0.0), (fixed[0], 0.0)), (point(movable[-1]), point(length))]
    return covered, gaps


def write_plan_panels(study: dict[str, object], path: Path) -> None:
    """Draw both opposed centerlines at the reported poses and at -180 deg."""
    poses = list(study["reported_poses"]) + [study["canonical_full_stow"]]
    figure, axes = plt.subplots(2, 2, figsize=(8.8, 9.4))
    requirement = REQUIREMENT_M / 2.0
    for axis, pose in zip(axes.ravel(), poses):
        axis.add_patch(plt.Circle((0.0, 0.0), requirement, fill=False, linestyle="--", color="black", linewidth=0.8))
        axis.add_patch(plt.Circle((0.0, 0.0), HUB_M, fill=False, color="0.35", linewidth=1.0))
        covered, gaps = _blade_segments(pose)
        for sign in (1.0, -1.0):
            xs = [sign * point[0] for point in covered]
            ys = [sign * point[1] for point in covered]
            axis.plot(xs, ys, color="#1f4e79", linewidth=1.5)
            axis.plot([sign * HINGE_M], [0.0], marker="o", color="#1f4e79", markersize=3.5)
            for start, end in gaps:
                axis.plot(
                    [sign * start[0], sign * end[0]],
                    [sign * start[1], sign * end[1]],
                    color="#a33b32",
                    linestyle=(0, (1.2, 1.0)),
                    linewidth=2.0,
                )
        angle = pose["fold_angle_deg"]
        suffix = "canonical stow; collision retained" if angle == CANONICAL_STOW_DEG else "proposed alternative"
        axis.set_title(f"{angle:.0f} deg\n{suffix}", fontsize=9)
        axis.set_aspect("equal")
        axis.set_xlim(-0.095, 0.095)
        axis.set_ylim(-0.095, 0.095)
        axis.set_xlabel("x, m", fontsize=8)
        axis.set_ylabel("y, m", fontsize=8)
    figure.suptitle(
        "Geometric screening plan view\nCenterlines only; not surface clearance or design suitability",
        fontsize=11,
    )
    figure.legend(
        handles=[
            plt.Line2D([0], [0], color="black", linestyle="--", label="140 mm requirement"),
            plt.Line2D([0], [0], color="0.35", label="hub"),
            plt.Line2D([0], [0], color="#1f4e79", marker="o", label="hinge"),
            plt.Line2D([0], [0], color="#1f4e79", label="supplied centerline"),
            plt.Line2D([0], [0], color="#a33b32", linestyle=":", label="uncovered root and tip span"),
        ],
        loc="lower center",
        ncol=2,
        frameon=False,
        fontsize=9,
        bbox_to_anchor=(0.5, 0.02),
        borderaxespad=0.0,
    )
    figure.subplots_adjust(left=0.08, right=0.98, top=0.90, bottom=0.16, hspace=0.48, wspace=0.28)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=140)
    plt.close(figure)


def write_intermediate_fold_study(repository_root: Path, output_dir: Path) -> dict[str, object]:
    study = json.loads(_canonical(build_intermediate_fold_study(repository_root)))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "study.json").write_text(_canonical(study) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(render_intermediate_fold_report(study), encoding="utf-8")
    write_plan_panels(study, output_dir / "plan_view.png")
    return study


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    write_intermediate_fold_study(root, root / "reports" / "intermediate_fold_50mm_screening")


if __name__ == "__main__":
    main()
