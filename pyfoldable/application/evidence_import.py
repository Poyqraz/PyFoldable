"""Session-only, fail-closed inspection of UI-05 evidence uploads."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from pyfoldable.core.cfd_reference import (
    CFDReferenceFixture,
    CFDReferencePoint,
    CFDReferenceSource,
)
from pyfoldable.core.experiment_contract import (
    CalibrationIdentity,
    ExperimentPolicy,
    TestStandManifest,
)
from pyfoldable.core.fea_contract import (
    CADRevisionIdentity,
    FEAAcceptancePolicy,
    FEALoadCase,
    FEAMaterialIdentity,
    FEAProjectManifest,
)


EvidenceImportKind = Literal[
    "cfd_reference",
    "fea_contract_report",
    "experiment_contract_report",
]
MAX_EVIDENCE_UPLOAD_BYTES = 5 * 1024 * 1024
_KINDS = {
    "cfd_reference",
    "fea_contract_report",
    "experiment_contract_report",
}
_CANONICAL_IDENTITIES = {
    "cfd_reference": "apcsf-10x4.7-published-cfd-v1",
    "fea_contract_report": "pr09-fea-contract-software-fixture-v1",
    "experiment_contract_report": "pr10-synthetic-test-stand-v1",
}
_CANONICAL_SHA256 = {
    "cfd_reference": "5d6c7ab93022d576d7aa2fe03391f8d0a874aec6ebe732810624ed9f5cb7f5d7",
    "fea_contract_report": "359e4934370e30394967a2d763a8be546d51a203f864b2175f680bbc4e3a3545",
    "experiment_contract_report": "f8d18827bfe1c1a905e42307b854fd0918741980f1f69bd36d95ea1ca03fea54",
}
_FEA_METRIC_UNITS = {
    "maximum_von_mises_stress": "Pa",
    "maximum_total_deformation": "m",
    "minimum_safety_factor": "1",
    "maximum_contact_pressure": "Pa",
    "hinge_pin_shear_stress": "Pa",
    "bearing_reaction_force": "N",
    "first_natural_frequency": "Hz",
    "minimum_frequency_separation_percent": "%",
    "fatigue_life": "cycle",
    "fatigue_damage": "1",
}


class EvidenceImportError(ValueError):
    """Raised when an uploaded evidence file violates its selected contract."""


@dataclass(frozen=True)
class EvidenceImportArtifact:
    kind: EvidenceImportKind
    filename: str
    source_sha256: str
    size_bytes: int
    schema_version: int
    identity: str
    classification: str
    qualification: str
    physical_qualification: bool
    summary: tuple[tuple[str, object], ...]


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidenceImportError(f"{field} must be a JSON object.")
    return value


def _sequence(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise EvidenceImportError(f"{field} must be a JSON array.")
    return value


def _schema(document: Mapping[str, Any], field: str = "schema_version") -> int:
    value = document.get("schema_version")
    if value != 1 or isinstance(value, bool):
        raise EvidenceImportError(f"{field} must be 1.")
    return 1


def _required(document: Mapping[str, Any], key: str, field: str) -> Any:
    if key not in document:
        raise EvidenceImportError(f"{field}.{key} is required.")
    return document[key]


def _require_physical_false(document: Mapping[str, Any], field: str) -> None:
    if document.get("physical_qualification") is not False:
        raise EvidenceImportError(
            f"{field}.physical_qualification must be explicitly false."
        )


def _validate_json_tree(value: object) -> None:
    stack: list[tuple[object, int]] = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > 100:
            raise EvidenceImportError("Evidence JSON nesting exceeds 100 levels.")
        if isinstance(current, Mapping):
            for key, child in current.items():
                if key == "physical_qualification" and child is not False:
                    raise EvidenceImportError(
                        "Uploaded evidence cannot claim physical qualification."
                    )
                stack.append((child, depth + 1))
        elif isinstance(current, list):
            stack.extend((child, depth + 1) for child in current)
        elif isinstance(current, float) and not math.isfinite(current):
            raise EvidenceImportError("Evidence JSON numbers must be finite.")


def _inspect_cfd(document: Mapping[str, Any]) -> tuple[str, str, str, tuple]:
    _schema(document)
    if document.get("independent_project_review") is not False:
        raise EvidenceImportError("CFD reference cannot claim independent project review.")
    sources = tuple(
        CFDReferenceSource(**_mapping(item, "sources[]"))
        for item in _sequence(document.get("sources"), "sources")
    )
    points_list = []
    for item in _sequence(document.get("points"), "points"):
        point_document = _mapping(item, "points[]")
        if point_document.get("qualification_eligible") is not False:
            raise EvidenceImportError(
                "points[].qualification_eligible must be literal false."
            )
        points_list.append(CFDReferencePoint(**point_document))
    points = tuple(points_list)
    fixture = CFDReferenceFixture(
        id=document.get("id", ""),
        target_geometry_id=document.get("target_geometry_id", ""),
        rights_scope=document.get("rights_scope", ""),
        independent_project_review=document.get("independent_project_review", False),
        qualification=document.get("qualification", ""),
        sources=sources,
        points=points,
    )
    if fixture.id != _CANONICAL_IDENTITIES["cfd_reference"]:
        raise EvidenceImportError("CFD identity is not canonical.")
    summary = (
        ("Hedef geometri", fixture.target_geometry_id),
        ("Kaynak sayısı", len(fixture.sources)),
        ("Tablolu nokta", len(fixture.points)),
        ("Bağımsız proje review", fixture.independent_project_review),
    )
    return (
        fixture.id,
        "published_cfd_model_form_context_only",
        fixture.qualification,
        summary,
    )


def _inspect_fea(document: Mapping[str, Any]) -> tuple[str, str, str, tuple]:
    manifest_document = _mapping(document.get("manifest"), "manifest")
    _schema(manifest_document, "manifest.schema_version")
    cad = CADRevisionIdentity(**_mapping(manifest_document.get("cad"), "manifest.cad"))
    materials_list = []
    for item in _sequence(manifest_document.get("materials"), "manifest.materials"):
        material_document = _mapping(item, "manifest.materials[]")
        property_names = _sequence(
            material_document.get("property_names"),
            "manifest.materials[].property_names",
        )
        if material_document.get("qualification") != (
            "software_fixture_not_material_evidence"
        ):
            raise EvidenceImportError("Unexpected FEA material qualification.")
        materials_list.append(
            FEAMaterialIdentity(
                **{
                    **material_document,
                    "property_names": tuple(property_names),
                }
            )
        )
    materials = tuple(materials_list)
    load_cases = []
    for item in _sequence(manifest_document.get("load_cases"), "manifest.load_cases"):
        case_document = _mapping(item, "manifest.load_cases[]")
        units = _mapping(
            case_document.get("required_metric_units"),
            "manifest.load_cases[].required_metric_units",
        )
        for metric, unit in units.items():
            if _FEA_METRIC_UNITS.get(metric) != unit:
                raise EvidenceImportError(f"FEA metric unit mismatch: {metric}")
        load_cases.append(
            FEALoadCase(
                id=case_document.get("id", ""),
                analysis_type=case_document.get("analysis_type", ""),
                load_source_id=case_document.get("load_source_id", ""),
                required_metric_units=dict(units),
            )
        )
    policy_document = _mapping(manifest_document.get("policy"), "manifest.policy")
    limits_document = _mapping(
        policy_document.get("metric_limits"),
        "manifest.policy.metric_limits",
    )
    policy = FEAAcceptancePolicy(
        maximum_mesh_change_percent=_required(
            policy_document, "maximum_mesh_change_percent", "manifest.policy"
        ),
        maximum_force_balance_error_percent=_required(
            policy_document,
            "maximum_force_balance_error_percent",
            "manifest.policy",
        ),
        metric_limits={
            metric: (
                _mapping(bounds, f"metric_limits.{metric}").get("minimum"),
                _mapping(bounds, f"metric_limits.{metric}").get("maximum"),
            )
            for metric, bounds in limits_document.items()
        },
    )
    manifest = FEAProjectManifest(
        id=manifest_document.get("id", ""),
        cad=cad,
        materials=materials,
        load_cases=tuple(load_cases),
        policy=policy,
    )
    if manifest.id != _CANONICAL_IDENTITIES["fea_contract_report"]:
        raise EvidenceImportError("FEA manifest identity is not canonical.")
    fixture = _mapping(
        document.get("software_fixture_decision"),
        "software_fixture_decision",
    )
    readiness = _mapping(document.get("project_readiness"), "project_readiness")
    _require_physical_false(fixture, "software_fixture_decision")
    _require_physical_false(readiness, "project_readiness")
    _schema(fixture, "software_fixture_decision.schema_version")
    if fixture.get("manifest_id") != manifest.id:
        raise EvidenceImportError("FEA manifest identity mismatch.")
    if fixture.get("software_gate_passed") is not True or fixture.get("state") != (
        "software_pass_physical_evidence_pending"
    ):
        raise EvidenceImportError("Unexpected FEA software fixture state.")
    missing_case_ids = _sequence(
        fixture.get("missing_case_ids"), "software_fixture_decision.missing_case_ids"
    )
    if missing_case_ids:
        raise EvidenceImportError("FEA fixture cannot pass with missing case ids.")
    case_documents = _sequence(
        fixture.get("cases"), "software_fixture_decision.cases"
    )
    declared_case_ids = {case.id for case in manifest.load_cases}
    fixture_case_ids: list[str] = []
    for item in case_documents:
        case = _mapping(item, "software_fixture_decision.cases[]")
        case_id = case.get("case_id")
        fixture_case_ids.append(case_id)
        if case.get("passed") is not True or _sequence(
            case.get("failures"), "software_fixture_decision.cases[].failures"
        ):
            raise EvidenceImportError("FEA fixture contains a failed case.")
    if (
        not fixture_case_ids
        or len(fixture_case_ids) != len(set(fixture_case_ids))
        or set(fixture_case_ids) != declared_case_ids
    ):
        raise EvidenceImportError("FEA fixture cases must exactly cover the manifest.")
    if document.get("decision") != "pr09_software_contract_complete_physical_evidence_pending":
        raise EvidenceImportError("Unexpected FEA contract decision.")
    if readiness.get("state") != "blocked_waiting_for_real_structural_inputs":
        raise EvidenceImportError("FEA project readiness must remain blocked.")
    if not _sequence(readiness.get("missing_inputs"), "project_readiness.missing_inputs"):
        raise EvidenceImportError("FEA readiness must declare missing physical inputs.")
    summary = (
        ("CAD revision", f"{cad.design_id} / {cad.revision}"),
        ("Malzeme kartı", len(manifest.materials)),
        ("Yük vakası", len(manifest.load_cases)),
        ("Fixture software gate", fixture.get("software_gate_passed")),
    )
    return (
        manifest.id,
        "fea_software_contract_physical_evidence_pending",
        str(readiness["state"]),
        summary,
    )


def _inspect_experiment(document: Mapping[str, Any]) -> tuple[str, str, str, tuple]:
    manifest_document = _mapping(document.get("manifest"), "manifest")
    _schema(manifest_document, "manifest.schema_version")
    calibrations_list = []
    for item in _sequence(
        manifest_document.get("calibrations"), "manifest.calibrations"
    ):
        calibration = _mapping(item, "manifest.calibrations[]")
        if calibration.get("qualification") != (
            "software_fixture_not_calibration_evidence"
        ):
            raise EvidenceImportError("Unexpected experiment calibration qualification.")
        calibrations_list.append(CalibrationIdentity(**calibration))
    calibrations = tuple(calibrations_list)
    policy_document = _mapping(manifest_document.get("policy"), "manifest.policy")
    manifest = TestStandManifest(
        id=manifest_document.get("id", ""),
        calibrations=calibrations,
        policy=ExperimentPolicy(
            minimum_repeats=_required(
                policy_document, "minimum_repeats", "manifest.policy"
            ),
            maximum_zero_drift=dict(
                _mapping(
                    _required(
                        policy_document, "maximum_zero_drift", "manifest.policy"
                    ),
                    "manifest.policy.maximum_zero_drift",
                )
            ),
            coverage_factor=_required(
                policy_document, "coverage_factor", "manifest.policy"
            ),
        ),
    )
    if manifest.id != _CANONICAL_IDENTITIES["experiment_contract_report"]:
        raise EvidenceImportError("Experiment stand identity is not canonical.")
    fixture = _mapping(
        document.get("software_fixture_decision"),
        "software_fixture_decision",
    )
    readiness = _mapping(document.get("project_readiness"), "project_readiness")
    _require_physical_false(fixture, "software_fixture_decision")
    _require_physical_false(readiness, "project_readiness")
    _schema(fixture, "software_fixture_decision.schema_version")
    if fixture.get("stand_id") != manifest.id:
        raise EvidenceImportError("Experiment stand identity mismatch.")
    if fixture.get("software_gate_passed") is not True or fixture.get("state") != (
        "software_pass_physical_measurements_pending"
    ):
        raise EvidenceImportError("Unexpected experiment software fixture state.")
    if _sequence(fixture.get("missing_roles"), "software_fixture_decision.missing_roles"):
        raise EvidenceImportError("Experiment fixture cannot pass with missing roles.")
    run_documents = _sequence(fixture.get("runs"), "software_fixture_decision.runs")
    summary_documents = _sequence(
        fixture.get("summaries"), "software_fixture_decision.summaries"
    )
    run_ids: list[str] = []
    for item in run_documents:
        run = _mapping(item, "software_fixture_decision.runs[]")
        run_ids.append(run.get("run_id"))
        if run.get("passed") is not True or _sequence(
            run.get("failures"), "software_fixture_decision.runs[].failures"
        ):
            raise EvidenceImportError("Experiment fixture contains a failed run.")
    summary_ids: list[str] = []
    roles: list[str] = []
    for item in summary_documents:
        summary_document = _mapping(item, "software_fixture_decision.summaries[]")
        summary_ids.append(summary_document.get("run_id"))
        roles.append(summary_document.get("role"))
    if (
        not run_ids
        or len(run_ids) != len(set(run_ids))
        or set(summary_ids) != set(run_ids)
        or len(summary_ids) != len(set(summary_ids))
        or set(roles) != {"fixed_reference", "foldable"}
    ):
        raise EvidenceImportError(
            "Experiment fixture runs and summaries must exactly cover both roles."
        )
    if document.get("decision") != "pr10_software_contract_complete_physical_measurements_pending":
        raise EvidenceImportError("Unexpected experiment contract decision.")
    if readiness.get("state") != "blocked_waiting_for_calibrated_raw_measurements":
        raise EvidenceImportError("Experiment project readiness must remain blocked.")
    if not _sequence(readiness.get("missing_inputs"), "project_readiness.missing_inputs"):
        raise EvidenceImportError(
            "Experiment readiness must declare missing physical measurements."
        )
    summary = (
        ("Test stand", manifest.id),
        ("Kalibrasyon kanalı", len(manifest.calibrations)),
        ("Minimum tekrar", manifest.policy.minimum_repeats),
        ("Fixture koşumu", len(_sequence(fixture.get("runs"), "fixture.runs"))),
    )
    return (
        manifest.id,
        "experiment_software_contract_measurements_pending",
        str(readiness["state"]),
        summary,
    )


def inspect_evidence_upload(
    content: bytes,
    filename: str,
    kind: EvidenceImportKind,
) -> EvidenceImportArtifact:
    """Inspect one uploaded JSON in memory without persisting or promoting it."""
    if not isinstance(kind, str) or kind not in _KINDS:
        raise EvidenceImportError(f"Unsupported evidence kind: {kind!r}")
    if (
        not isinstance(filename, str)
        or not filename
        or "/" in filename
        or "\\" in filename
        or "\x00" in filename
        or Path(filename).name != filename
        or Path(filename).suffix.lower() != ".json"
    ):
        raise EvidenceImportError("Upload must use a plain JSON filename.")
    if not isinstance(content, bytes) or not content:
        raise EvidenceImportError("Evidence upload must not be empty.")
    if len(content) > MAX_EVIDENCE_UPLOAD_BYTES:
        raise EvidenceImportError("Evidence upload exceeds the 5 MiB maximum size.")

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant {value}")

    def finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"JSON number must be finite: {value}")
        return parsed

    def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        document: dict[str, Any] = {}
        for key, value in pairs:
            if key in document:
                raise ValueError(f"duplicate JSON key {key!r}")
            document[key] = value
        return document

    try:
        text = content.decode("utf-8")
        document = json.loads(
            text,
            parse_constant=reject_constant,
            parse_float=finite_float,
            object_pairs_hook=strict_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise EvidenceImportError(f"Evidence upload is not strict JSON: {exc}") from exc
    root = _mapping(document, "Evidence root")
    try:
        _validate_json_tree(root)
        if kind == "cfd_reference":
            identity, classification, qualification, summary = _inspect_cfd(root)
        elif kind == "fea_contract_report":
            identity, classification, qualification, summary = _inspect_fea(root)
        else:
            identity, classification, qualification, summary = _inspect_experiment(root)
    except (EvidenceImportError, KeyError, TypeError, ValueError, RecursionError) as exc:
        label = {
            "cfd_reference": "CFD",
            "fea_contract_report": "FEA",
            "experiment_contract_report": "Experiment",
        }[kind]
        raise EvidenceImportError(f"{label} evidence violates its contract: {exc}") from exc
    source_sha256 = hashlib.sha256(content).hexdigest()
    if source_sha256 != _CANONICAL_SHA256[kind]:
        raise EvidenceImportError(
            f"{kind} evidence SHA-256 does not match the canonical versioned artifact."
        )
    return EvidenceImportArtifact(
        kind=kind,
        filename=filename,
        source_sha256=source_sha256,
        size_bytes=len(content),
        schema_version=1,
        identity=identity,
        classification=classification,
        qualification=qualification,
        physical_qualification=False,
        summary=summary,
    )
