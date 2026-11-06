"""Application-owned retained-provider admission and explicit fully-open BEM.

No provider construction, acquisition, retry or qualification occurs here. The
repository is populated by trusted application code, not by normal-user uploads.
Raw records are rechecked; their consistency is not proof of authenticity or of
the process image/build. Lower-layer unqualified classifications are preserved.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import base64
import hashlib
import json
import math
from pathlib import Path
import re
from typing import MutableMapping

from pyfoldable.core import BEMRotorSettings
from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.models import AirfoilDefinition
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS, load_project_airfoil
from pyfoldable.core.providers import (
    PolarGenerationRequest, PolarGenerationResult, PolarPointResult, ProviderIdentity, _canonical_value,
)
from pyfoldable.core.units import normalize_quantity
from pyfoldable.providers import xfoil
from . import design_analysis as analysis
from .design_draft import DesignDraftArtifact
from .polar_query_feasibility import _bind_returned_result
from .polar_upload import PolarRunRequest, prepare_polar_run, run_polar_run
from .profile_bem_comparison import _seal, snapshot_failure, snapshot_success


def _json(value: object) -> str:
    return json.dumps(_canonical_value(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _document(payload: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate retained JSON key")
            result[key] = value
        return result
    if not isinstance(payload, bytes) or not 0 < len(payload) <= 2 * 1024 * 1024:
        raise ValueError("Retained JSON exceeds the 2 MiB record budget")
    doc = json.loads(payload.decode("utf-8"), object_pairs_hook=unique)
    if not isinstance(doc, dict):
        raise ValueError("Expected a retained JSON object")
    _json(doc)  # finite, canonicalizable data
    return doc


class ProviderDesignPreparationError(analysis.DesignAnalysisError):
    def __init__(self, code: str, message: str, evidence: dict | None = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.evidence_json = _json({"code": code, "reason": message, **(evidence or {})})


@dataclass(frozen=True)
class RootDatum:
    value: float
    unit: str
    meaning: str
    source_identity: str
    declaration_kind: str  # declared_geometry or explicitly labeled study_assumption


@dataclass(frozen=True)
class TemplateDeclaration:
    template_id: str
    source_bytes: bytes
    source_identity: str


@dataclass(frozen=True)
class ProviderDesignSelection:
    draft: DesignDraftArtifact
    template: TemplateDeclaration
    root: RootDatum | None
    family_id: str
    provider_policy_json: str
    annulus_count: int


@dataclass(frozen=True)
class RetainedCell:
    result_json: bytes
    capture_files: tuple[tuple[str, bytes], ...]


@dataclass(frozen=True)
class UnlaunchedCell:
    """Explicit source declaration, never inferred merely from a missing result."""
    reason: str
    source_identity: str


@dataclass(frozen=True)
class ManagedProviderFamily:
    family_id: str
    provider: ProviderIdentity
    requests: tuple[PolarGenerationRequest, ...]  # independent declared plan, not inferred from results
    cells: tuple[RetainedCell | UnlaunchedCell | None, ...]  # None means unavailable, launch status unknown
    evidence_class: str                        # inert_fixture or caller_supplied_unqualified
    source_identity: str
    provenance_files: tuple[tuple[str, bytes], ...]


@dataclass(frozen=True)
class ManagedProviderRepository:
    families: tuple[ManagedProviderFamily, ...] = ()


def application_provider_repository() -> ManagedProviderRepository:
    """Deployment integration hook. No bundled success or automatic acquisition.

    An operator must register source-bound records using the types above. The
    completed partial probe cannot populate a complete family. Users never need
    to author polar JSON; no environment-driven solver discovery is performed.
    """
    return ManagedProviderRepository()


def read_retained_cell(result_path: Path, capture_directory: Path) -> RetainedCell:
    """Trusted application/operator file adapter; read only, never execute."""
    names = ("capture.json", "request_preimage.json", "script.txt", "airfoil_input.dat", "stdout.bin", "stderr.bin", "polar.bin")
    return RetainedCell(result_path.read_bytes(), tuple(
        (name, (capture_directory / name).read_bytes()) for name in names if (capture_directory / name).is_file()
    ))


def request_policy(request: PolarGenerationRequest, provider: ProviderIdentity) -> dict:
    """Explicit common numerical policy; exact grid/order live in the declared plan."""
    return {
        "provider": provider.as_mapping(), "n_crit": request.n_crit,
        "xtr_upper": request.xtr_upper, "xtr_lower": request.xtr_lower,
        "max_iterations": request.max_iterations, "timeout_s": request.timeout_s,
        "options": _canonical_value(request.options),
    }


def _geometry(selection: ProviderDesignSelection) -> dict:
    design, _ = analysis._load_open(selection.draft)
    ids = {s.airfoil_id for s in design.blade.stations}
    if len(ids) != 1 or next(iter(ids)) not in PROJECT_AIRFOIL_IDS:
        raise ProviderDesignPreparationError("catalog_profile_required", "Select one of the five catalog profiles")
    profile = next(iter(ids))
    foil = next(f for f in design.airfoils if f.id == profile)
    coordinate = airfoil_coordinate_sha256(foil)
    if coordinate != airfoil_coordinate_sha256(load_project_airfoil(profile)):
        raise ProviderDesignPreparationError("foreign_coordinates", "Draft coordinates differ from the selected catalog asset")
    template = selection.template
    if (not template.template_id.strip() or not template.source_identity.strip()
            or not isinstance(template.source_bytes, bytes) or _sha(template.source_bytes) != selection.draft.source_sha256):
        raise ProviderDesignPreparationError("template_identity", "Template bytes/source identity do not match the draft source")
    root = selection.root
    if root is None:
        raise ProviderDesignPreparationError("missing_root_declaration", "Declare r_root value, unit, meaning and source; hub/first station are separate")
    if (type(root.value) not in (float, int) or not math.isfinite(root.value) or not root.unit.strip()
            or not root.meaning.strip() or not root.source_identity.strip()
            or root.declaration_kind not in {"declared_geometry", "study_assumption"}):
        raise ProviderDesignPreparationError("invalid_root_declaration", "Root value/unit/meaning/source and labeled declaration kind are required")
    r_root = normalize_quantity(f"{root.value} {root.unit}", "length", field="r_root").si_value
    radius, hinge = design.blade.radius_m, design.hinge.radius_m
    if not 0 <= r_root < hinge < radius or not hinge - r_root > radius - hinge:
        raise ProviderDesignPreparationError("longer_proximal_required", "Require h-r_root > R-h, equivalently h > (R+r_root)/2")
    return {
        "profile": profile, "coordinate_sha256": coordinate,
        "template": {"id": template.template_id, "source_sha256": _sha(template.source_bytes), "source_identity": template.source_identity},
        "draft_sha256": selection.draft.draft_sha256,
        "root": {f.name: getattr(root, f.name) for f in fields(root)} | {"si_value_m": r_root},
        "hub_radius_m": design.blade.hub_radius_m,
        "first_aerodynamic_station_m": design.blade.stations[0].r_over_R * radius,
        "tip_radius_m": radius, "hinge_radius_m": hinge,
        "proximal_exposed_m": hinge - r_root, "distal_exposed_m": radius - hinge,
        "shaft_origin_longer": hinge > radius / 2,
        "parent_stations": [{"r_over_R": s.r_over_R, "chord_m": s.chord_m, "twist_rad": s.twist_rad, "airfoil_id": s.airfoil_id} for s in design.blade.stations],
        "condition": analysis._request(selection.draft, design)["operating_condition"],
        "scope": "single_declared_hinge_shared_parent_station_span_no_joint_loss_model",
    }


def _result(document: dict) -> PolarGenerationResult:
    if (not isinstance(document.get("request"), dict) or not isinstance(document.get("provider"), dict)
            or not isinstance(document.get("metadata"), dict) or not isinstance(document.get("points"), list)
            or not all(isinstance(p, dict) for p in document["points"])
            or not isinstance(document.get("warnings"), list) or not all(isinstance(w, str) for w in document["warnings"])):
        raise ValueError("Retained result request/provider/metadata/points/warnings have invalid shapes")
    preimage = document["request"]
    foil = preimage["airfoil"]
    if (not isinstance(foil, dict) or not isinstance(foil.get("coordinates"), list)
            or not isinstance(preimage.get("alpha_rad"), list) or not isinstance(preimage.get("options"), dict)):
        raise ValueError("Retained request airfoil/angles/options have invalid shapes")
    request = PolarGenerationRequest(
        airfoil=AirfoilDefinition(foil["id"], "retained canonical request", tuple(tuple(p) for p in foil["coordinates"])),
        alpha_rad=tuple(preimage["alpha_rad"]),
        **{key: preimage[key] for key in ("reynolds", "mach", "n_crit", "xtr_upper", "xtr_lower", "max_iterations", "timeout_s", "scenario_id", "options")},
    )
    result = PolarGenerationResult(
        request, ProviderIdentity(**document["provider"]), tuple(PolarPointResult(**p) for p in document["points"]),
        document["elapsed_s"], tuple(document["warnings"]), document["metadata"],
    )
    if _json(preimage) != _json(request.cache_payload(result.provider)) or document["request_sha256"] != result.cache_key:
        raise ValueError("Retained result request preimage/digest is contradictory")
    if document["complete"] is not result.complete:
        raise ValueError("Claimed complete flag contradicts the point ledger")
    return result


def _capture(request: PolarGenerationRequest, provider: ProviderIdentity, result: PolarGenerationResult, cell: RetainedCell) -> dict:
    files = dict(cell.capture_files)
    if len(files) != len(cell.capture_files) or sum(len(b) for b in files.values()) > 16 * 1024 * 1024:
        raise ValueError("Duplicate or oversized capture files")
    required = {"capture.json", "request_preimage.json", "script.txt", "airfoil_input.dat", "stdout.bin", "stderr.bin", "polar.bin"}
    if set(files) != required:
        raise ValueError("Complete capture requires seven retained files")
    receipt = _document(files["capture.json"])
    expected = xfoil._request_preimage(request, provider)
    if files["request_preimage.json"] != expected:
        raise ValueError("Capture canonical request does not match the declared request")
    key = request.cache_key(provider)
    for field, value in {
        "schema_version": 1, "artifact_class": "xfoil_subprocess_capture",
        "request_cache_key": key, "request_preimage_sha256": key,
        "coordinate_sha256": airfoil_coordinate_sha256(request.airfoil), "provider_identity": provider.as_mapping(),
        "process_status": "completed", "returncode": 0, "polar_read_status": "present",
        "polar_decoding_status": "decoded", "polar_parsed": True, "capture_receipt_written": True,
    }.items():
        if _json(receipt.get(field)) != _json(value):
            raise ValueError(f"Capture {field} contradicts usable retained output")
    if files["script.txt"] != xfoil._build_command_script(request, xfoil._validated_options(request.options)).encode():
        raise ValueError("Capture script differs from the reviewed adapter/request")
    label = "_PyFoldable_" + request.airfoil.id
    airfoil = (label + "\n" + "\n".join(f"{x:.17g} {y:.17g}" for x, y in request.airfoil.coordinates) + "\n").encode()
    if files["airfoil_input.dat"] != airfoil:
        raise ValueError("Capture input coordinates differ from the selected profile")
    for filename, field in (("script.txt", "script_sha256"), ("airfoil_input.dat", "airfoil_input_sha256")):
        if _sha(files[filename]) != receipt.get(field):
            raise ValueError("Capture script/airfoil receipt does not match retained bytes")
    for filename, field in (("stdout.bin", "stdout"), ("stderr.bin", "stderr"), ("polar.bin", "polar_file")):
        if receipt.get(field) != xfoil._byte_receipt(files[filename], partial=False):
            raise ValueError("Capture raw byte receipt does not match retained bytes")
    if receipt.get("adapter_source_sha256") != _sha(Path(xfoil.__file__).read_bytes()):
        raise ValueError("Capture adapter source is not the reviewed implementation")
    observations = receipt["executable_identity"]
    if (not isinstance(observations, dict) or not isinstance(observations.get("prelaunch"), dict)
            or not isinstance(observations.get("postlaunch"), dict)):
        raise ValueError("Capture executable file observations have invalid shapes")
    before, after = observations["prelaunch"], observations["postlaunch"]
    if (observations.get("matched") is not True or not isinstance(before.get("sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", before["sha256"]) is None or before["sha256"] != after.get("sha256")
            or before.get("unavailable_reason") is not None or after.get("unavailable_reason") is not None):
        raise ValueError("Capture executable file observations are missing/changed")
    parsed, _ = xfoil._parse_polar(files["polar.bin"].decode("utf-8"))
    points, _ = xfoil._reconcile_rows(request, parsed)
    # Raw polar parsing is read-only arithmetic. It does not call XFOIL.
    if _json([p.__dict__ for p in points]) != _json([p.__dict__ for p in result.points]):
        raise ValueError("Capture raw coefficients/point order differ from the returned result")
    retained_points = [{k: v for k, v in p.__dict__.items() if k not in ("confidence", "iterations")} for p in points]
    if _json(receipt.get("points")) != _json(retained_points):
        raise ValueError("Capture receipt point ledger differs from raw polar bytes")
    ready = result.complete
    if (receipt.get("solver_output_usable") is not ready or receipt.get("evidence_ready") is not ready
            or result.metadata.get("capture_evidence_ready") is not ready):
        raise ValueError("Capture readiness contradicts the raw point ledger")
    return {"receipt": receipt, "files": [{"name": n, "sha256": _sha(b), "byte_count": len(b)} for n, b in sorted(files.items())]}


@dataclass(frozen=True)
class PreparedProviderDesignAnalysis:
    selection: ProviderDesignSelection
    polar_run: PolarRunRequest
    admission_json: str
    request_sha256: str


def prepare_provider_design_analysis(selection: ProviderDesignSelection, repository: ManagedProviderRepository) -> PreparedProviderDesignAnalysis:
    """No solve. Match one declared family; admit all cells or none."""
    geometry = _geometry(selection)
    matches = [f for f in repository.families if f.family_id == selection.family_id and f.requests and f.requests[0].airfoil.id == geometry["profile"]]
    if len(matches) != 1:
        raise ProviderDesignPreparationError("missing_applicable_family", f"No unique application-managed family for {geometry['profile']} / {selection.family_id}")
    family = matches[0]
    family_context = {"family_id": family.family_id, "evidence_class": family.evidence_class, "source_identity": family.source_identity}
    if family.evidence_class not in {"inert_fixture", "caller_supplied_unqualified"} or not family.source_identity.strip() or not family.provenance_files:
        raise ProviderDesignPreparationError("missing_provenance", "Retained source identity, provenance bytes and unqualified evidence class are required", family_context)
    if (len({n for n, _ in family.provenance_files}) != len(family.provenance_files)
            or sum(len(b) for _, b in family.provenance_files) > 4 * 1024 * 1024
            or sum(len(c.result_json) + sum(len(b) for _, b in c.capture_files) for c in family.cells if isinstance(c, RetainedCell)) > 64 * 1024 * 1024):
        raise ProviderDesignPreparationError("retention_budget", "Duplicate provenance names or retained-byte budget exceeded", family_context)
    if len(family.requests) > 64 or len(family.requests) != len(family.cells):
        raise ProviderDesignPreparationError("incomplete_family", "Declared family/cell counts differ or exceed the budget", family_context)
    grids = {(r.mach, r.reynolds) for r in family.requests}
    if (len(grids) != len(family.requests) or len({r.mach for r in family.requests}) * len({r.reynolds for r in family.requests}) != len(grids)):
        raise ProviderDesignPreparationError("incomplete_family", "The independent declared family plan is not rectangular", family_context)
    try:
        selected_policy = _document(selection.provider_policy_json.encode())
    except (ValueError, TypeError) as exc:
        raise ProviderDesignPreparationError("incompatible_policy", str(exc), family_context) from exc
    for request in family.requests:
        if (_json(request_policy(request, family.provider)) != _json(selected_policy)
                or request.alpha_rad != family.requests[0].alpha_rad or request.scenario_id != family.requests[0].scenario_id):
            raise ProviderDesignPreparationError("incompatible_policy", "Selected provider policy differs from the independently declared family plan", family_context)
        if (request.airfoil.id != geometry["profile"] or airfoil_coordinate_sha256(request.airfoil) != geometry["coordinate_sha256"]):
            raise ProviderDesignPreparationError("foreign_coordinates", "Declared family coordinates differ from the selected catalog profile", family_context)
    tables, ledger, errors = [], [], []
    for index, (request, cell) in enumerate(zip(family.requests, family.cells)):
        row = {"index": index, "planned_request_sha256": request.cache_key(family.provider), "attempted_request_sha256": None, "returned_request_sha256": None,
               "profile": request.airfoil.id, "mach": request.mach, "reynolds": request.reynolds, "status": "unavailable", "points": None}
        if cell is None:
            errors.append(("incomplete_family", f"Cell {index} has no returned record; launch status is unavailable"))
        elif isinstance(cell, UnlaunchedCell):
            if cell.reason.strip() and cell.source_identity.strip():
                row.update({"status": "not_launched", "reason": cell.reason, "source_identity": cell.source_identity})
                errors.append(("incomplete_family", f"Cell {index} was not launched according to its retained source declaration"))
            else:
                errors.append(("incomplete_family", f"Cell {index} launch declaration lacks a reason/source; status remains unavailable"))
        else:
            row.update({"status": "rejected", "result_json_sha256": _sha(cell.result_json)})
            try:
                doc = _document(cell.result_json)
                row["returned_document"] = doc
                result = _result(doc)
                row.update(_bind_returned_result(request, result, family.provider))
                row["points"] = doc["points"]
                if row["identity_mismatch"] is not None:
                    raise ProviderDesignPreparationError("request_binding", row["identity_mismatch"])
                capture = _capture(request, family.provider, result, cell)
                row["capture"] = capture
                if not result.complete:
                    row["status"] = "partial"
                    raise ProviderDesignPreparationError("incomplete_family", f"Cell {index} has unavailable coefficients; no point removal or repair")
                if result.metadata.get("capture_evidence_ready") is not True:
                    raise ValueError("Capture is not evidence ready")
                table = result.to_polar_table(require_complete=True)
                table_doc = {f.name: getattr(table, f.name) for f in fields(table)}
                table_doc["metadata"] = {**table_doc["metadata"], "application_evidence_class": family.evidence_class}
                tables.append(_canonical_value(table_doc))
                row["status"] = "admitted"
            except (ValueError, TypeError, KeyError, UnicodeError, RuntimeError) as exc:
                code = exc.code if isinstance(exc, ProviderDesignPreparationError) else "invalid_capture"
                row["rejection_reason"] = str(exc)
                errors.append((code, str(exc)))
        ledger.append(row)
    provenance = [{"name": n, "sha256": _sha(b), "byte_count": len(b), "base64": base64.b64encode(b).decode()} for n, b in family.provenance_files]
    admission = {"schema_version": 1, "service_id": "pyfoldable.application.provider_design_analysis",
        "implementation_file_sha256": _sha(Path(__file__).read_bytes()),
        "family_id": family.family_id, "source_identity": family.source_identity,
        "evidence_class": family.evidence_class, "geometry": geometry, "provider_policy": selected_policy,
        "cells": ledger, "provenance": provenance, "complete_family_admitted": not errors,
        "physical_qualification": False, "genuine_comparison_status": "UNESTABLISHED",
        "identity_limits": "Retained bytes and executable file observations are not process-image/build attestation or experimental validation"}
    if errors:
        raise ProviderDesignPreparationError(errors[0][0], errors[0][1], admission)
    payload = _json({"schema_version": 1, "artifact_class": "active_design_polar_bundle", "physical_qualification": False, "tables": tables}).encode()
    run = prepare_polar_run(selection.draft, payload, annulus_count=selection.annulus_count)
    admission["bem_policy"] = json.loads(run.context_json)["settings"]
    admitted = _json(admission)
    identity = _sha(_json({"admission": admission, "polar_run_sha256": run.request_sha256}).encode())
    return PreparedProviderDesignAnalysis(selection, run, admitted, identity)


@dataclass(frozen=True)
class ProviderDesignOutcome:
    artifact: analysis.DesignAnalysisArtifact | None
    record_json: str

    @property
    def record(self) -> dict:
        return json.loads(self.record_json)


def preparation_failure_record(selection: ProviderDesignSelection, error: ProviderDesignPreparationError) -> dict:
    evidence = json.loads(error.evidence_json)
    evidence_class = evidence.get("evidence_class")
    if evidence_class not in {"inert_fixture", "caller_supplied_unqualified"}:
        evidence_class = "caller_supplied_unqualified"
    record = snapshot_failure(selection.draft, reason=str(error), evidence_class=evidence_class)
    return _seal({**record, "provider_design_rejection": evidence})


def run_provider_design_analysis(prepared: PreparedProviderDesignAnalysis, *, active_selection: ProviderDesignSelection, repository: ManagedProviderRepository) -> ProviderDesignOutcome:
    """Explicit action, one existing BEM call after fresh admission; never acquisition."""
    if not isinstance(prepared, PreparedProviderDesignAnalysis) or active_selection != prepared.selection:
        raise ProviderDesignPreparationError("stale_active_state", "Prepared request is stale for the active selection")
    fresh = prepare_provider_design_analysis(active_selection, repository)
    if fresh != prepared:
        raise ProviderDesignPreparationError("stale_active_state", "Retained records/policy/implementation changed after preparation")
    admission = json.loads(prepared.admission_json)
    try:
        artifact = run_polar_run(prepared.polar_run)
    except analysis.DesignAnalysisError as exc:
        context = json.loads(prepared.polar_run.context_json)
        bundle = json.loads(prepared.polar_run.summary_json)
        record = snapshot_failure(active_selection.draft, reason=str(exc), evidence_class=admission["evidence_class"],
            failure_stage="solver_invocation", prepared_policy=context["settings"], ui_request_sha256=prepared.polar_run.request_sha256,
            polar_source_sha256=bundle["source_sha256"], polar_airfoil_id=bundle["airfoil_id"], polar_coordinate_sha256=bundle["coordinate_sha256"])
        return ProviderDesignOutcome(None, _json(_seal({**record, "provider_design_admission": admission})))
    doc = json.loads(artifact.report_json)
    doc["request"]["provider_design_request_sha256"] = prepared.request_sha256
    doc["request"]["provider_design_admission"] = admission
    doc["request_sha256"] = _sha(analysis._json(doc["request"]).encode())
    report = analysis._json(doc) + "\n"
    artifact = analysis.DesignAnalysisArtifact(doc["request_sha256"], _sha(report.encode()), report, "provider_design_analysis.json")
    return ProviderDesignOutcome(artifact, _json(snapshot_success(artifact, evidence_class=admission["evidence_class"])))


ACTIVE_REQUEST = "provider_design_active_request"
ACTIVE_OUTCOME = "provider_design_active_outcome"


def prepare_active_provider_design(state: MutableMapping, selection: ProviderDesignSelection, repository: ManagedProviderRepository) -> PreparedProviderDesignAnalysis:
    """UI adapter: edits/rejections clear active downloads, never saved snapshots."""
    try:
        prepared = prepare_provider_design_analysis(selection, repository)
    except (ValueError, OSError):
        state.pop(ACTIVE_REQUEST, None)
        state.pop(ACTIVE_OUTCOME, None)
        raise
    if state.get(ACTIVE_REQUEST) != prepared.request_sha256:
        state.pop(ACTIVE_OUTCOME, None)
    state[ACTIVE_REQUEST] = prepared.request_sha256
    return prepared


def run_active_provider_design(state: MutableMapping, selection: ProviderDesignSelection, repository: ManagedProviderRepository) -> ProviderDesignOutcome:
    """Called only by an explicit UI action. Never silently refresh a stale run."""
    previous = state.get(ACTIVE_REQUEST)
    state.pop(ACTIVE_OUTCOME, None)
    prepared = prepare_active_provider_design(state, selection, repository)
    if previous != prepared.request_sha256:
        raise ProviderDesignPreparationError("stale_active_state", "Active inputs are stale; prepare before explicit execution")
    outcome = run_provider_design_analysis(prepared, active_selection=selection, repository=repository)
    state[ACTIVE_OUTCOME] = outcome
    return outcome
