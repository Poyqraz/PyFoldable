"""Immutable catalog-profile BEM comparison on the existing fully-open path.

This module does not solve, upload, or rank. It snapshots an explicit run and
refuses to treat unlike planform, condition, or solver settings as one
controlled comparison.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from typing import Mapping

from pyfoldable.application.design_analysis import DesignAnalysisArtifact, DesignAnalysisError, _load, _load_open
from pyfoldable.application.design_draft import DesignDraftArtifact
from pyfoldable.core.airfoil import airfoil_coordinate_sha256


class ProfileComparisonError(ValueError):
    """A comparison snapshot cannot be built without inventing a result."""


_EVIDENCE = {"inert_fixture", "caller_supplied_unqualified"}
_SUMMARY_FIELDS = (
    "airfoil_id",
    "airfoil_coordinate_sha256",
    "draft_sha256",
    "geometry_sha256",
    "planform_sha256",
    "condition_sha256",
    "settings_sha256",
    "polar_source_sha256",
    "annulus_count",
    "status",
    "failure_reason",
    "thrust_n",
    "torque_nm",
    "shaft_power_w",
    "inner_radius_m",
    "outer_radius_m",
    "evidence_class",
    "physical_qualification",
)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _evidence(value: str) -> str:
    if value not in _EVIDENCE:
        raise ProfileComparisonError("Comparison evidence class is not recognized.")
    return value


def identities_for_draft(draft: DesignDraftArtifact, *, annulus_count: int) -> dict[str, object]:
    """Separate shared planform and condition from the airfoil-specific geometry."""
    if type(annulus_count) is not int or isinstance(annulus_count, bool) or annulus_count < 2:
        raise ProfileComparisonError("Annulus count must be an integer of at least 2.")
    if not isinstance(draft, DesignDraftArtifact):
        raise ProfileComparisonError("Expected a design draft artifact.")
    design, _angle = _load(draft)
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
    settings = {
        "annulus_count": annulus_count,
        "bounds": "error",
        "solved_pose": "fully_open_zero_offset" if fully_open else "not_fully_open_zero_offset",
        "radial_domain": "station_span",
        "preview_fold_angle_rad": _angle,
        "axial_offset_m": hinge.axial_offset_m,
        "tangential_offset_m": hinge.tangential_offset_m,
    }
    return {
        "airfoil_id": airfoil_id,
        "airfoil_coordinate_sha256": coordinate,
        "draft_sha256": draft.draft_sha256,
        "geometry_sha256": _sha(_canonical(geometry)),
        "planform_sha256": _sha(_canonical(planform)),
        "condition_sha256": _sha(_canonical(condition)),
        "settings_sha256": _sha(_canonical(settings)),
        "annulus_count": annulus_count,
        "fully_open_zero_offset": fully_open,
        "open_error": open_error,
        "physical_qualification": False,
    }


def _seal(body: dict[str, object]) -> dict[str, object]:
    sealed = dict(body)
    sealed.pop("record_sha256", None)
    sealed["record_sha256"] = _sha(_canonical(sealed))
    return json.loads(_canonical(sealed))


def snapshot_failure(
    draft: DesignDraftArtifact,
    *,
    reason: str,
    annulus_count: int,
    evidence_class: str,
    polar_source_sha256: str | None = None,
) -> dict[str, object]:
    """Record an explicit failed attempt without performance totals."""
    if not isinstance(reason, str) or not reason.strip():
        raise ProfileComparisonError("A failure record needs an explicit reason.")
    identity = identities_for_draft(draft, annulus_count=annulus_count)
    identity.pop("open_error", None)
    identity.pop("fully_open_zero_offset", None)
    return _seal({
        **identity,
        "status": "failure",
        "failure_reason": reason,
        "evidence_class": _evidence(evidence_class),
        "polar_source_sha256": polar_source_sha256,
        "thrust_n": None,
        "torque_nm": None,
        "shaft_power_w": None,
        "inner_radius_m": None,
        "outer_radius_m": None,
        "radial_elements": None,
        "report_sha256": None,
    })


def snapshot_success(artifact: DesignAnalysisArtifact, *, evidence_class: str) -> dict[str, object]:
    """Copy one explicit BEM artifact. The copy does not follow later UI edits."""
    if not isinstance(artifact, DesignAnalysisArtifact):
        raise ProfileComparisonError("Expected a design-analysis artifact.")
    document = json.loads(artifact.report_json)
    rotor = document.get("rotor")
    request = document.get("request")
    if not isinstance(rotor, dict) or not isinstance(request, dict):
        raise ProfileComparisonError("A success snapshot requires the retained rotor and request.")
    for name in ("thrust_n", "torque_nm", "shaft_power_w", "inner_radius_m", "outer_radius_m", "elements"):
        if name not in rotor:
            raise ProfileComparisonError("The BEM result is missing a required field.")
    draft = DesignDraftArtifact(
        "snapshot.toml",
        request["draft_toml"],
        request["source_sha256"],
        request["draft_sha256"],
    )
    policy = request.get("policy") if isinstance(request.get("policy"), dict) else {}
    annulus = policy.get("annulus_count", request.get("ui_request", {}).get("settings", {}).get("annulus_count"))
    identity = identities_for_draft(draft, annulus_count=annulus)
    if identity["airfoil_id"] != rotor.get("airfoil_id"):
        raise ProfileComparisonError("Result airfoil does not match the draft identity.")
    if not identity["fully_open_zero_offset"]:
        raise ProfileComparisonError("A success snapshot requires the fully-open zero-offset pose.")
    polar_upload = request.get("polar_upload") if isinstance(request.get("polar_upload"), dict) else {}
    identity.pop("open_error", None)
    identity.pop("fully_open_zero_offset", None)
    elements = rotor["elements"]
    return _seal({
        **identity,
        "status": "success",
        "failure_reason": None,
        "evidence_class": _evidence(evidence_class),
        "polar_source_sha256": polar_upload.get("source_sha256"),
        "thrust_n": rotor["thrust_n"],
        "torque_nm": rotor["torque_nm"],
        "shaft_power_w": rotor["shaft_power_w"],
        "inner_radius_m": rotor["inner_radius_m"],
        "outer_radius_m": rotor["outer_radius_m"],
        "radial_elements": elements,
        "report_sha256": artifact.report_sha256,
    })


def add_record(records: tuple[Mapping[str, object], ...] | list[Mapping[str, object]], record: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    """Append a sealed snapshot. Existing records are not rewritten."""
    if not isinstance(record, Mapping) or record.get("status") not in {"success", "failure"}:
        raise ProfileComparisonError("Only a sealed success or failure snapshot can be added.")
    if record.get("record_sha256") != _sha(_canonical({key: value for key, value in record.items() if key != "record_sha256"})):
        raise ProfileComparisonError("Comparison record identity does not match its contents.")
    preserved = tuple(json.loads(_canonical(dict(item))) for item in records)
    return preserved + (json.loads(_canonical(dict(record))),)


def assess_comparison(records: tuple[Mapping[str, object], ...] | list[Mapping[str, object]]) -> dict[str, object]:
    """Report whether the saved snapshots share one planform, condition, and setting set."""
    rows = tuple(records)
    reasons: list[str] = []
    if len(rows) < 2:
        reasons.append("fewer_than_two_records")
    else:
        base = rows[0]
        for index, row in enumerate(rows[1:], start=1):
            for field in ("planform_sha256", "condition_sha256", "settings_sha256"):
                if row.get(field) != base.get(field):
                    reasons.append(f"record_{index}_{field}")
    settings_compatible = not any(reason.endswith("_sha256") for reason in reasons) and len(rows) >= 2
    performance_comparison = settings_compatible and all(row.get("status") == "success" for row in rows)
    return {
        "settings_compatible": settings_compatible,
        "performance_comparison": performance_comparison,
        "mismatch_reasons": reasons,
        "qualified_winner": None,
        "physical_qualification": False,
        "ranking_metric": None,
    }


def comparison_document(
    records: tuple[Mapping[str, object], ...] | list[Mapping[str, object]],
    *,
    evidence_class: str,
) -> dict[str, object]:
    """Build the export document in insertion order, without a performance ranking."""
    rows: tuple[dict[str, object], ...] = ()
    for record in records:
        rows = add_record(rows, record)
    assessment = assess_comparison(rows)
    genuine = "BLOCKED_no_matching_real_provider_polar_bundle"
    return {
        "schema_version": 1,
        "artifact_class": "catalog_profile_bem_comparison",
        "physical_qualification": False,
        "qualified_winner": None,
        "ranking_metric": None,
        "evidence_class": _evidence(evidence_class),
        "genuine_comparison_status": genuine,
        "genuine_comparison_note": (
            "This repository does not contain matching real-provider polar bundles "
            "for a controlled catalog comparison. Inert or caller-supplied tables "
            "exercise the software workflow only."
        ),
        "settings_compatible": assessment["settings_compatible"],
        "software_controlled_comparison": assessment["performance_comparison"],
        "performance_comparison": False,
        "mismatch_reasons": assessment["mismatch_reasons"],
        "records": list(rows),
    }


def comparison_csv(document: Mapping[str, object]) -> str:
    """Export one row per immutable snapshot. Shaft power is not electrical power."""
    if document.get("artifact_class") != "catalog_profile_bem_comparison":
        raise ProfileComparisonError("Expected a catalog profile comparison document.")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=(
        "record_sha256",
        *_SUMMARY_FIELDS,
        "settings_compatible",
        "software_controlled_comparison",
        "performance_comparison",
        "genuine_comparison_status",
        "mismatch_reasons",
    ))
    writer.writeheader()
    for record in document["records"]:
        row = {"record_sha256": record["record_sha256"]}
        for field in _SUMMARY_FIELDS:
            value = record[field]
            row[field] = "null" if value is None else value
        row["settings_compatible"] = document["settings_compatible"]
        row["software_controlled_comparison"] = document["software_controlled_comparison"]
        row["performance_comparison"] = document["performance_comparison"]
        row["genuine_comparison_status"] = document["genuine_comparison_status"]
        row["mismatch_reasons"] = ";".join(document["mismatch_reasons"])
        writer.writerow(row)
    return buffer.getvalue()
