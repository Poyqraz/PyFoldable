"""Bounded, session-only polar uploads for explicit active-design screening.

Names and hashes bind caller-declared content, not experimental authenticity.
No provider execution, automatic data repair, proxy, or physical qualification.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyfoldable.core import BEMRotorSettings, PolarFamily, PolarTable
from pyfoldable.core.airfoil import airfoil_coordinate_sha256

from . import design_analysis as analysis
from .design_draft import DesignDraftArtifact


MAX_POLAR_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_POLAR_TABLES = 64
MAX_POLAR_POINTS = 721
MAX_TOTAL_POINTS = 16384
_ROOT_KEYS = {"schema_version", "artifact_class", "physical_qualification", "tables"}
_TABLE_KEYS = {"airfoil_id", "scenario_id", "reynolds", "mach", "alpha_rad", "cl", "cd", "cm", "source", "metadata"}


class PolarUploadError(analysis.DesignAnalysisError):
    """The upload/request cannot be used without guessing or exceeding a budget."""


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise PolarUploadError("Duplicate JSON key.")
        result[key] = value
    return result


def _finite_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _validate_tree(document: Any) -> None:
    pending = [(document, 0)]
    nodes = 0
    while pending:
        value, depth = pending.pop()
        nodes += 1
        if depth > 16 or nodes > 100000:
            raise PolarUploadError("Polar JSON nesting/node budget exceeded.")
        if isinstance(value, dict):
            for key, child in value.items():
                key.encode("utf-8")  # JSON escapes can decode to lone surrogates.
                if len(key) > 256:
                    raise PolarUploadError("Polar metadata key is too long.")
                if key == "physical_qualification" and child is not False:
                    raise PolarUploadError("Polar uploads cannot claim physical qualification.")
                pending.append((child, depth + 1))
        elif isinstance(value, list):
            pending.extend((child, depth + 1) for child in value)
        elif isinstance(value, float) and not math.isfinite(value):
            raise PolarUploadError("Polar JSON numbers must be finite.")
        elif isinstance(value, str):
            value.encode("utf-8")
            if len(value) > 4096:
                raise PolarUploadError("Polar JSON string budget exceeded.")


def _table(row: Any) -> PolarTable:
    if not isinstance(row, dict) or set(row) != _TABLE_KEYS:
        raise PolarUploadError("Polar table fields must match the version-1 contract.")
    for key in ("airfoil_id", "scenario_id", "source"):
        if not isinstance(row[key], str) or not row[key].strip():
            raise PolarUploadError(f"{key} must be a nonempty string.")
    for key in ("reynolds", "mach"):
        if not _finite_number(row[key]):
            raise PolarUploadError(f"{key} must be a finite number, not a string/bool.")
    arrays = {}
    for key in ("alpha_rad", "cl", "cd", "cm"):
        values = row[key]
        if (not isinstance(values, list) or not 2 <= len(values) <= MAX_POLAR_POINTS
                or not all(_finite_number(value) for value in values)):
            raise PolarUploadError(f"{key} requires 2–{MAX_POLAR_POINTS} finite numeric points.")
        arrays[key] = tuple(values)
    metadata = row["metadata"]
    if not isinstance(metadata, dict):
        raise PolarUploadError("Polar metadata must be an object.")
    digest = metadata.get("airfoil_coordinate_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise PolarUploadError("Every table requires an airfoil coordinate SHA-256.")
    if "complete" in metadata and metadata["complete"] is not True:
        raise PolarUploadError("Declared incomplete polar tables cannot be uploaded.")
    for key in ("requested_point_count", "usable_point_count"):
        if key in metadata and (type(metadata[key]) is not int or metadata[key] != len(arrays["alpha_rad"])):
            raise PolarUploadError("Declared provider point counts must match the table.")
    return PolarTable(**{**row, **arrays})


@dataclass(frozen=True)
class PolarBundle:
    source_sha256: str
    normalized_json: str
    airfoil_id: str
    coordinate_sha256: str
    table_count: int
    point_count: int

    def to_family(self) -> PolarFamily:
        """Fresh models prevent mutation of retained provenance/identity."""
        return PolarFamily(tuple(_table(row) for row in json.loads(self.normalized_json)["tables"]))


def inspect_polar_bundle(payload: bytes) -> PolarBundle:
    """Strict UTF-8 JSON with explicit radians and dimensionless coefficients.

    Full rectangular Re/Mach cells are required, but alpha coverage may differ.
    Neither rectangularity nor nominal station coverage proves BEM query coverage.
    """
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_POLAR_UPLOAD_BYTES:
        raise PolarUploadError("Invalid polar upload size; expected 1 byte to 2 MiB.")
    try:
        doc = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
        _validate_tree(doc)
        if not isinstance(doc, dict) or set(doc) != _ROOT_KEYS:
            raise PolarUploadError("Polar bundle root fields must match the version-1 contract.")
        if type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
            raise PolarUploadError("Polar bundle schema_version must be integer 1.")
        if doc["artifact_class"] != "active_design_polar_bundle" or doc["physical_qualification"] is not False:
            raise PolarUploadError("Expected an explicitly unqualified active_design_polar_bundle.")
        rows = doc["tables"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_POLAR_TABLES:
            raise PolarUploadError("Polar bundle requires 1–64 tables.")
        family = PolarFamily(tuple(_table(row) for row in rows))
        digests = {table.metadata["airfoil_coordinate_sha256"] for table in family.tables}
        if len(digests) != 1:
            raise PolarUploadError("Polar tables must have one coordinate identity.")
        if len({table.reynolds for table in family.tables}) * len({table.mach for table in family.tables}) != len(rows):
            raise PolarUploadError("A complete rectangular Reynolds/Mach grid is required.")
        points = sum(len(table.alpha_rad) for table in family.tables)
        if points > MAX_TOTAL_POINTS:
            raise PolarUploadError("Total polar point budget exceeded.")
        return PolarBundle(_sha(payload), _json(doc), family.airfoil_id, next(iter(digests)), len(rows), points)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        raise PolarUploadError(f"Invalid polar bundle: {exc}") from exc


@dataclass(frozen=True)
class PolarRunRequest:
    draft: DesignDraftArtifact
    payload: bytes
    annulus_count: int
    request_sha256: str
    summary_json: str
    context_json: str


def prepare_polar_run(draft: DesignDraftArtifact, payload: bytes, *, annulus_count: int = 40) -> PolarRunRequest:
    """Validate and bind a run without invoking BEM or a polar provider."""
    if type(annulus_count) is not int or not 4 <= annulus_count <= 80:
        raise PolarUploadError("UI annulus count must be an integer from 4 to 80.")
    bundle = inspect_polar_bundle(payload)
    design, _ = analysis._load_open(draft)
    ids = {station.airfoil_id for station in design.blade.stations}
    if ids != {bundle.airfoil_id}:
        raise PolarUploadError("Polar profile does not match the active draft.")
    foil = next(foil for foil in design.airfoils if foil.id == bundle.airfoil_id)
    if not foil.coordinates or airfoil_coordinate_sha256(foil) != bundle.coordinate_sha256:
        raise PolarUploadError("Polar coordinate SHA-256 does not match the active draft.")
    context = {
        "analysis_request": analysis._request(draft, design),
        "upload_contract_version": 1,
        "upload_implementation_sha256": _sha(Path(__file__).read_bytes()),
        "source_sha256": bundle.source_sha256,
        "normalized_sha256": _sha(bundle.normalized_json.encode()),
        "settings": BEMRotorSettings(annulus_count=annulus_count).as_mapping(),
    }
    summary = {"airfoil_id": bundle.airfoil_id, "coordinate_sha256": bundle.coordinate_sha256,
        "source_sha256": bundle.source_sha256, "table_count": bundle.table_count,
        "point_count": bundle.point_count, "solver_envelope_complete": False,
        "tables": [{key: row[key] for key in ("reynolds", "mach", "source")} | {
            "alpha_min_rad": row["alpha_rad"][0], "alpha_max_rad": row["alpha_rad"][-1],
        } for row in json.loads(bundle.normalized_json)["tables"]]}
    context_json = _json(context)
    return PolarRunRequest(draft, payload, annulus_count, _sha(context_json.encode()), _json(summary), context_json)


def run_polar_run(request: PolarRunRequest) -> analysis.DesignAnalysisArtifact:
    """Explicit action only; revalidate immutable inputs before calling BEM."""
    if not isinstance(request, PolarRunRequest):
        raise PolarUploadError("Expected a prepared polar run request.")
    fresh = prepare_polar_run(request.draft, request.payload, annulus_count=request.annulus_count)
    if fresh != request:
        raise PolarUploadError("Polar run request identity no longer matches its inputs.")
    bundle = inspect_polar_bundle(request.payload)
    result = analysis.run_design_analysis(request.draft, {bundle.airfoil_id: bundle.to_family()},
        settings=BEMRotorSettings(annulus_count=request.annulus_count))
    doc = json.loads(result.report_json)
    doc["request"].update({"ui_request_sha256": request.request_sha256,
        "ui_request": json.loads(request.context_json), "polar_upload": {
        "schema_version": 1, "source_json": request.payload.decode("utf-8"),
        "source_sha256": bundle.source_sha256,
        "normalized_sha256": _sha(bundle.normalized_json.encode()),
        "identity_scope": "caller_declared_content_not_authenticated_evidence",
    }})
    doc["request_sha256"] = _sha(_json(doc["request"]).encode())
    report = _json(doc) + "\n"
    return analysis.DesignAnalysisArtifact(doc["request_sha256"], _sha(report.encode()), report, "active_design_polar_screening.json")
