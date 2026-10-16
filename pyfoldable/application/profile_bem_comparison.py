"""Immutable catalog-profile BEM comparison on the existing fully-open path.

This module does not solve, upload, or rank. A snapshot copies the admitted
solver policy and the retained report. It does not rebuild that policy from
annulus count and defaults, and it does not treat repeated runs of one
coordinate identity as a profile comparison.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from typing import Mapping

from pyfoldable.application.design_analysis import DesignAnalysisArtifact, DesignAnalysisError, _load, _load_open
from pyfoldable.application.design_draft import DesignDraftArtifact
from pyfoldable.core.airfoil import airfoil_coordinate_sha256


class ProfileComparisonError(ValueError):
    """A comparison snapshot cannot be built without inventing a result."""


_EVIDENCE = {"inert_fixture", "caller_supplied_unqualified"}
_STAGES = {"preflight_rejection", "solver_invocation"}
_COORDINATE = re.compile(r"[0-9a-f]{64}")
_POLICY_KEYS = frozenset({
    "annulus_count", "radial_domain", "annulus_settings", "bounds", "solved_pose",
})
_EXECUTED_KEYS = frozenset({"annulus_count", "radial_domain", "annulus_settings"})
_ANNULUS_KEYS = frozenset({
    "bracket_samples", "max_iterations", "angle_tolerance_rad", "residual_tolerance_m2_s",
    "relative_residual_tolerance", "minimum_tip_loss_factor", "include_tip_loss",
    "include_root_loss", "loading_branch", "rotational_augmentation",
})
_AUGMENTATION_KEYS = frozenset({
    "model_id", "kind", "lift_curve_slope_per_rad", "zero_lift_angle_rad",
    "maximum_chord_over_radius", "maximum_absolute_alpha_rad", "source",
})
_SUMMARY_FIELDS = (
    "airfoil_id",
    "airfoil_coordinate_sha256",
    "draft_sha256",
    "geometry_sha256",
    "planform_sha256",
    "condition_sha256",
    "pose_sha256",
    "settings_sha256",
    "admitted_policy_sha256",
    "polar_source_sha256",
    "polar_airfoil_id",
    "polar_coordinate_sha256",
    "annulus_count",
    "status",
    "failure_stage",
    "failure_reason",
    "thrust_n",
    "torque_nm",
    "shaft_power_w",
    "inner_radius_m",
    "outer_radius_m",
    "evidence_class",
    "physical_qualification",
)
_REFERENCE_FIELDS = (
    "analysis_request_sha256",
    "ui_request_sha256",
    "report_sha256",
    "attempt_sha256",
    "prepared_policy_sha256",
)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _evidence(value: str) -> str:
    if value not in _EVIDENCE:
        raise ProfileComparisonError("Comparison evidence class is not recognized.")
    return value


def _valid_coordinate(value: object) -> bool:
    return isinstance(value, str) and _COORDINATE.fullmatch(value) is not None


def _sha_or_null(value: object) -> str | None:
    if value is None:
        return None
    if not _valid_coordinate(value):
        raise ProfileComparisonError("A request or report reference must be a SHA-256 or null.")
    return value


def _draft_identity(draft: DesignDraftArtifact) -> dict[str, object]:
    """Separate shared planform, pose and condition from the airfoil surface."""
    if not isinstance(draft, DesignDraftArtifact):
        raise ProfileComparisonError("Expected a design draft artifact.")
    design, angle = _load(draft)
    open_error = None
    try:
        _load_open(draft)
        fully_open = True
    except DesignAnalysisError as exc:
        fully_open = False
        open_error = str(exc)
    hinge = design.hinge
    if hinge is None or not design.operating_conditions:
        raise ProfileComparisonError("The draft has no hinge or operating condition.")
    identities = {station.airfoil_id for station in design.blade.stations}
    if len(identities) != 1:
        raise ProfileComparisonError("Fully-open screening accepts one profile at a time.")
    airfoil_id = next(iter(identities))
    foil = next(item for item in design.airfoils if item.id == airfoil_id)
    coordinate = airfoil_coordinate_sha256(foil) if foil.coordinates else None
    planform = {
        "diameter_m": design.blade.diameter_m,
        "hub_radius_m": design.blade.hub_radius_m,
        "hinge_radius_m": hinge.radius_m,
        "blade_count": design.blade.blade_count,
        "stations": [
            {"r_over_R": station.r_over_R, "chord_m": station.chord_m, "twist_rad": station.twist_rad}
            for station in design.blade.stations
        ],
    }
    geometry = {**planform, "airfoil_id": airfoil_id, "airfoil_coordinate_sha256": coordinate}
    condition = {
        "angular_speed_rad_s": design.operating_conditions[0].angular_speed_rad_s,
        "forward_speed_m_s": design.operating_conditions[0].forward_speed_m_s,
        "air_density_kg_m3": design.operating_conditions[0].air_density_kg_m3,
        "dynamic_viscosity_pa_s": design.operating_conditions[0].dynamic_viscosity_pa_s,
        "temperature_k": design.operating_conditions[0].temperature_k,
        "pressure_pa": design.operating_conditions[0].pressure_pa,
    }
    pose = {
        "preview_fold_angle_rad": angle,
        "deployed_angle_rad": hinge.deployed_angle_rad,
        "axial_offset_m": hinge.axial_offset_m,
        "tangential_offset_m": hinge.tangential_offset_m,
        "fully_open_zero_offset": fully_open,
    }
    return {
        "airfoil_id": airfoil_id,
        "airfoil_coordinate_sha256": coordinate,
        "draft_sha256": draft.draft_sha256,
        "geometry_sha256": _sha(_canonical(geometry)),
        "planform_sha256": _sha(_canonical(planform)),
        "condition_sha256": _sha(_canonical(condition)),
        "pose_sha256": _sha(_canonical(pose)),
        "fully_open_zero_offset": fully_open,
        "open_error": open_error,
        "physical_qualification": False,
    }


def identities_for_draft(draft: DesignDraftArtifact, *, annulus_count: int) -> dict[str, object]:
    """Return draft identity. ``annulus_count`` is not a solver policy."""
    if type(annulus_count) is not int or isinstance(annulus_count, bool) or annulus_count < 2:
        raise ProfileComparisonError("Annulus count must be an integer of at least 2.")
    return _draft_identity(draft)


def _seal(body: dict[str, object]) -> dict[str, object]:
    sealed = dict(body)
    sealed.pop("record_sha256", None)
    sealed["record_sha256"] = _sha(_canonical(sealed))
    return json.loads(_canonical(sealed))


def _complete_annulus(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != _ANNULUS_KEYS:
        raise ProfileComparisonError(f"The {label} annulus settings are incomplete.")
    for name in ("include_tip_loss", "include_root_loss"):
        if type(value[name]) is not bool:
            raise ProfileComparisonError(f"The {label} field {name} is missing or not boolean.")
    if not isinstance(value["rotational_augmentation"], dict) or set(value["rotational_augmentation"]) != _AUGMENTATION_KEYS:
        raise ProfileComparisonError(f"The {label} rotational augmentation settings are incomplete.")
    return json.loads(_canonical(value))


def _complete_executed_settings(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != _EXECUTED_KEYS:
        raise ProfileComparisonError(f"The {label} solver settings are incomplete.")
    checked = dict(value)
    checked["annulus_settings"] = _complete_annulus(value["annulus_settings"], label=label)
    return json.loads(_canonical(checked))


def _complete_admitted_policy(policy: object, executed: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(policy, dict) or set(policy) != _POLICY_KEYS:
        raise ProfileComparisonError("The admitted solver policy is incomplete.")
    admitted = dict(policy)
    admitted["annulus_settings"] = _complete_annulus(policy["annulus_settings"], label="admitted")
    for key in _EXECUTED_KEYS:
        if _canonical(admitted[key]) != _canonical(executed[key]):
            raise ProfileComparisonError("Request policy contradicts the result settings.")
    return json.loads(_canonical(admitted))


def _attempt_sha(body: Mapping[str, object]) -> str:
    return _sha(_canonical({"scope": "preflight_rejection_attempt", **body}))


def _blank_execution() -> dict[str, object]:
    return {
        "admitted_policy": None,
        "admitted_policy_sha256": None,
        "settings_sha256": None,
        "executed_policy": None,
        "prepared_policy": None,
        "prepared_policy_sha256": None,
        "analysis_request_sha256": None,
        "ui_request_sha256": None,
        "report_sha256": None,
        "report_text": None,
        "annulus_count": None,
        "polar_query_envelope": None,
        "radial_elements": None,
        "thrust_n": None,
        "torque_nm": None,
        "shaft_power_w": None,
        "inner_radius_m": None,
        "outer_radius_m": None,
    }


def snapshot_failure(
    draft: DesignDraftArtifact,
    *,
    reason: str,
    evidence_class: str,
    failure_stage: str = "preflight_rejection",
    annulus_count: int | None = None,
    polar_source_sha256: str | None = None,
    polar_airfoil_id: str | None = None,
    polar_coordinate_sha256: str | None = None,
    polar_unavailable_reason: str | None = None,
    prepared_policy: Mapping[str, object] | None = None,
    ui_request_sha256: str | None = None,
) -> dict[str, object]:
    """Record an explicit failed attempt without performance totals.

    ``annulus_count`` remains accepted so existing callers compile. It is not
    turned into a solver policy. A preflight rejection has no executed request.
    """
    if not isinstance(reason, str) or not reason.strip():
        raise ProfileComparisonError("A failure record needs an explicit reason.")
    if failure_stage not in _STAGES:
        raise ProfileComparisonError("Failure stage is not recognized.")
    if annulus_count is not None and (type(annulus_count) is not int or isinstance(annulus_count, bool)):
        raise ProfileComparisonError("Declared annulus count must be an integer when supplied.")
    if failure_stage == "preflight_rejection" and (prepared_policy is not None or ui_request_sha256 is not None):
        raise ProfileComparisonError("A preflight rejection has no prepared solver request.")
    if polar_unavailable_reason is not None and (polar_airfoil_id is not None or polar_coordinate_sha256 is not None):
        raise ProfileComparisonError("An uninspectable upload cannot also declare a polar identity.")
    if (polar_airfoil_id is None) != (polar_coordinate_sha256 is None):
        raise ProfileComparisonError("A declared polar identity needs both profile and coordinate.")
    if polar_coordinate_sha256 is not None and not _valid_coordinate(polar_coordinate_sha256):
        raise ProfileComparisonError("Declared polar coordinate identity is not a SHA-256.")
    if polar_airfoil_id is not None and (not isinstance(polar_airfoil_id, str) or not polar_airfoil_id.strip()):
        raise ProfileComparisonError("Declared polar profile identity is empty.")
    checked_policy = None
    if prepared_policy is not None:
        checked_policy = _complete_executed_settings(dict(prepared_policy), label="prepared")
    identity = _draft_identity(draft)
    identity.pop("open_error", None)
    identity.pop("fully_open_zero_offset", None)
    attempt = None
    if failure_stage == "preflight_rejection":
        attempt = _attempt_sha({
            "draft_sha256": identity["draft_sha256"],
            "failure_reason": reason,
            "polar_source_sha256": polar_source_sha256,
            "polar_airfoil_id": polar_airfoil_id,
            "polar_coordinate_sha256": polar_coordinate_sha256,
            "polar_unavailable_reason": polar_unavailable_reason,
        })
    return _seal({
        "record_schema_version": 2,
        **identity,
        **_blank_execution(),
        "status": "failure",
        "failure_stage": failure_stage,
        "failure_reason": reason,
        "evidence_class": _evidence(evidence_class),
        "prepared_policy": checked_policy,
        "prepared_policy_sha256": None if checked_policy is None else _sha(_canonical(checked_policy)),
        "ui_request_sha256": _sha_or_null(ui_request_sha256),
        "attempt_sha256": attempt,
        "polar_source_sha256": _sha_or_null(polar_source_sha256),
        "polar_airfoil_id": polar_airfoil_id,
        "polar_coordinate_sha256": polar_coordinate_sha256,
        "polar_unavailable_reason": polar_unavailable_reason,
    })


def snapshot_success(artifact: DesignAnalysisArtifact, *, evidence_class: str) -> dict[str, object]:
    """Copy one explicit BEM artifact, including its admitted policy and report."""
    if not isinstance(artifact, DesignAnalysisArtifact):
        raise ProfileComparisonError("Expected a design-analysis artifact.")
    if hashlib.sha256(artifact.report_json.encode("utf-8")).hexdigest() != artifact.report_sha256:
        raise ProfileComparisonError("The report hash does not match the retained report text.")
    document = json.loads(artifact.report_json)
    rotor = document.get("rotor")
    request = document.get("request")
    if not isinstance(rotor, dict) or not isinstance(request, dict):
        raise ProfileComparisonError("A success snapshot requires the retained rotor and request.")
    for name in ("thrust_n", "torque_nm", "shaft_power_w", "inner_radius_m", "outer_radius_m", "elements", "polar_query_envelope"):
        if name not in rotor:
            raise ProfileComparisonError("The BEM result is missing a required field.")
    executed = _complete_executed_settings(rotor.get("settings"), label="result")
    admitted = _complete_admitted_policy(request.get("policy"), executed)
    elements = rotor["elements"]
    if not isinstance(elements, list) or not elements:
        raise ProfileComparisonError("The BEM result has no radial elements.")
    for element in elements:
        solution = element.get("solution") if isinstance(element, dict) else None
        if not isinstance(solution, dict) or not isinstance(solution.get("polar_query_envelope"), dict):
            raise ProfileComparisonError("A radial element is missing its query envelope.")
        if _canonical(solution.get("settings")) != _canonical(executed["annulus_settings"]):
            raise ProfileComparisonError("An element solver setting contradicts the admitted policy.")
    if rotor.get("polar_bounds") != admitted["bounds"]:
        raise ProfileComparisonError("Request policy contradicts the result bounds.")
    draft = DesignDraftArtifact(
        "snapshot.toml", request["draft_toml"], request["source_sha256"], request["draft_sha256"],
    )
    identity = _draft_identity(draft)
    if identity["airfoil_id"] != rotor.get("airfoil_id"):
        raise ProfileComparisonError("Result airfoil does not match the draft identity.")
    if not identity["fully_open_zero_offset"]:
        raise ProfileComparisonError("A success snapshot requires the fully-open zero-offset pose.")
    ui_request_sha256 = request.get("ui_request_sha256")
    analysis_request_sha256 = request.get("analysis_request_sha256")
    if ui_request_sha256 is None and analysis_request_sha256 is None:
        analysis_request_sha256 = artifact.request_sha256
    elif analysis_request_sha256 is None:
        raise ProfileComparisonError("The originating analysis request identity is missing.")
    if ui_request_sha256 is not None and analysis_request_sha256 == ui_request_sha256:
        raise ProfileComparisonError("Analysis and UI request identities were collapsed.")
    prepared = None
    ui_request = request.get("ui_request")
    if isinstance(ui_request, dict) and "settings" in ui_request:
        prepared = _complete_executed_settings(ui_request["settings"], label="prepared")
    polar_upload = request.get("polar_upload") if isinstance(request.get("polar_upload"), dict) else {}
    identity.pop("open_error", None)
    identity.pop("fully_open_zero_offset", None)
    policy_sha = _sha(_canonical(admitted))
    return _seal({
        "record_schema_version": 2,
        **identity,
        "status": "success",
        "failure_stage": None,
        "failure_reason": None,
        "evidence_class": _evidence(evidence_class),
        "admitted_policy": admitted,
        "admitted_policy_sha256": policy_sha,
        "settings_sha256": policy_sha,
        "executed_policy": executed,
        "prepared_policy": prepared,
        "prepared_policy_sha256": None if prepared is None else _sha(_canonical(prepared)),
        "analysis_request_sha256": _sha_or_null(analysis_request_sha256),
        "ui_request_sha256": _sha_or_null(ui_request_sha256),
        "attempt_sha256": None,
        "report_sha256": artifact.report_sha256,
        "report_text": artifact.report_json,
        "polar_source_sha256": _sha_or_null(polar_upload.get("source_sha256")),
        "polar_airfoil_id": rotor.get("airfoil_id"),
        "polar_coordinate_sha256": identity["airfoil_coordinate_sha256"],
        "polar_unavailable_reason": None,
        "annulus_count": admitted["annulus_count"],
        "polar_query_envelope": rotor["polar_query_envelope"],
        "radial_elements": elements,
        "thrust_n": rotor["thrust_n"],
        "torque_nm": rotor["torque_nm"],
        "shaft_power_w": rotor["shaft_power_w"],
        "inner_radius_m": rotor["inner_radius_m"],
        "outer_radius_m": rotor["outer_radius_m"],
    })


def add_record(records: tuple[Mapping[str, object], ...] | list[Mapping[str, object]], record: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    """Append a sealed snapshot. Existing records are not rewritten."""
    if not isinstance(record, Mapping) or record.get("status") not in {"success", "failure"}:
        raise ProfileComparisonError("Only a sealed success or failure snapshot can be added.")
    if record.get("record_sha256") != _sha(_canonical({key: value for key, value in record.items() if key != "record_sha256"})):
        raise ProfileComparisonError("Comparison record identity does not match its contents.")
    if record.get("record_schema_version") == 2 and record.get("status") == "success":
        if record.get("admitted_policy_sha256") != _sha(_canonical(record.get("admitted_policy"))):
            raise ProfileComparisonError("Admitted policy hash does not match the retained policy.")
        if record.get("settings_sha256") != record.get("admitted_policy_sha256"):
            raise ProfileComparisonError("Settings hash does not match the admitted policy.")
    preserved = tuple(json.loads(_canonical(dict(item))) for item in records)
    return preserved + (json.loads(_canonical(dict(record))),)


def _policy_token(row: Mapping[str, object]) -> tuple[str, object]:
    if row.get("record_schema_version") != 2:
        return ("legacy", None)
    return ("admitted", row.get("admitted_policy_sha256"))


def assess_comparison(records: tuple[Mapping[str, object], ...] | list[Mapping[str, object]]) -> dict[str, object]:
    """Separate shared settings from distinct coordinate-bound profiles."""
    rows = tuple(records)
    reasons: list[str] = []
    profile_reasons: list[str] = []
    if len(rows) < 2:
        reasons.append("fewer_than_two_records")
    else:
        base = rows[0]
        for index, row in enumerate(rows[1:], start=1):
            for field in ("planform_sha256", "condition_sha256", "pose_sha256"):
                if row.get(field) != base.get(field):
                    reasons.append(f"record_{index}_{field}")
            if _policy_token(row) != _policy_token(base):
                reasons.append(f"record_{index}_admitted_policy_sha256")
            elif _policy_token(base)[1] is None:
                reasons.append(f"record_{index}_admitted_policy_unavailable")
        if any(row.get("record_schema_version") != 2 for row in rows):
            reasons.append("legacy_record_schema")
    settings_compatible = len(rows) >= 2 and not reasons
    coordinates = [row.get("airfoil_coordinate_sha256") for row in rows]
    valid = [value for value in coordinates if _valid_coordinate(value)]
    distinct = len(set(valid))
    if len(rows) >= 2 and not all(_valid_coordinate(value) for value in coordinates):
        profile_reasons.append("missing_coordinate_identity")
    elif len(rows) >= 2 and distinct < 2:
        profile_reasons.append("repeated_coordinate_identity")
    if any(row.get("status") != "success" for row in rows):
        profile_reasons.append("failure_record_present")
    software_controlled = (
        settings_compatible
        and not profile_reasons
        and distinct >= 2
        and all(row.get("status") == "success" for row in rows)
    )
    return {
        "settings_compatible": settings_compatible,
        "software_controlled_comparison": software_controlled,
        "distinct_coordinate_count": distinct,
        "mismatch_reasons": reasons,
        "profile_reasons": profile_reasons,
        "qualified_winner": None,
        "physical_qualification": False,
        "ranking_metric": None,
    }


def comparison_document(
    records: tuple[Mapping[str, object], ...] | list[Mapping[str, object]],
    *,
    evidence_class: str,
) -> dict[str, object]:
    """Build export schema 2 in insertion order, without a performance ranking."""
    rows: tuple[dict[str, object], ...] = ()
    for record in records:
        rows = add_record(rows, record)
    assessment = assess_comparison(rows)
    return {
        "schema_version": 2,
        "artifact_class": "catalog_profile_bem_comparison",
        "physical_qualification": False,
        "qualified_winner": None,
        "ranking_metric": None,
        "evidence_class": _evidence(evidence_class),
        "evidence_note": "Inert or caller-supplied coefficients exercise the software workflow only.",
        "genuine_comparison_status": "BLOCKED_no_matching_real_provider_polar_bundle",
        "genuine_comparison_note": (
            "This repository does not contain matching real-provider polar bundles "
            "for a controlled catalog comparison. Inert or caller-supplied tables "
            "exercise the software workflow only."
        ),
        "settings_compatible": assessment["settings_compatible"],
        "software_controlled_comparison": assessment["software_controlled_comparison"],
        "distinct_coordinate_count": assessment["distinct_coordinate_count"],
        "profile_reasons": assessment["profile_reasons"],
        "performance_comparison": False,
        "mismatch_reasons": assessment["mismatch_reasons"],
        "records": list(rows),
    }


def comparison_csv(document: Mapping[str, object]) -> str:
    """Export one row per snapshot. Radial elements stay in the JSON record."""
    if document.get("artifact_class") != "catalog_profile_bem_comparison":
        raise ProfileComparisonError("Expected a catalog profile comparison document.")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=(
        "record_sha256",
        *_SUMMARY_FIELDS,
        *_REFERENCE_FIELDS,
        "settings_compatible",
        "software_controlled_comparison",
        "performance_comparison",
        "genuine_comparison_status",
        "mismatch_reasons",
        "profile_reasons",
    ))
    writer.writeheader()
    for record in document["records"]:
        row = {"record_sha256": record["record_sha256"]}
        for field in (*_SUMMARY_FIELDS, *_REFERENCE_FIELDS):
            value = record.get(field)
            row[field] = "null" if value is None else value
        row["settings_compatible"] = document["settings_compatible"]
        row["software_controlled_comparison"] = document["software_controlled_comparison"]
        row["performance_comparison"] = document["performance_comparison"]
        row["genuine_comparison_status"] = document["genuine_comparison_status"]
        row["mismatch_reasons"] = ";".join(document["mismatch_reasons"])
        row["profile_reasons"] = ";".join(document.get("profile_reasons", []))
        writer.writerow(row)
    return buffer.getvalue()
