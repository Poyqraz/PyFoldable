"""Source-bound, explicit-unit blade station inputs for GEOM-02.

Hashes identify supplied geometry; they do not authenticate measurements. Partial
span datasets remain partial. No section, material or collision result is inferred.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re


MAX_STATION_UPLOAD_BYTES = 128 * 1024
_LENGTH_FACTORS = {"m": 1., "mm": .001, "cm": .01, "in": .0254}
_ANGLE_FACTORS = {"rad": 1., "deg": math.pi / 180.}


class StationBundleError(ValueError):
    """The station payload or its active-design binding is invalid."""


@dataclass(frozen=True)
class StationPoint:
    radius_m: float
    chord_m: float
    twist_rad: float


@dataclass(frozen=True)
class StationProvenance:
    kind: str
    reference: str
    locator: str
    revision: str
    parent_sha256: str | None = None


@dataclass(frozen=True)
class StationBundle:
    stations: tuple[StationPoint, ...]
    diameter_m: float
    hub_radius_m: float
    airfoil_id: str
    airfoil_coordinate_sha256: str
    provenance: StationProvenance
    raw_bytes: bytes
    raw_sha256: str
    canonical_json: str
    canonical_sha256: str


@dataclass(frozen=True)
class StationCoverageAudit:
    root_gap_m: float
    tip_gap_m: float
    span_complete: bool
    hinge_covered: bool
    surface_path_clearance: None = None
    interblade_clearance: None = None


def _keys(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise StationBundleError("Station JSON contains missing or unsupported fields.")


def _number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StationBundleError(f"{field} must be numeric.")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise StationBundleError(f"{field} must be finite.") from exc
    if not math.isfinite(result):
        raise StationBundleError(f"{field} must be finite.")
    return result


def _text(value, field, limit=2048):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise StationBundleError(f"{field} requires bounded, nonempty text.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise StationBundleError(f"{field} requires valid Unicode.") from exc
    return value


def _sha(value, field):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise StationBundleError(f"{field} requires a lowercase SHA-256 digest.")
    return value


def _tolerance(a, b):
    return 8 * max(math.ulp(a), math.ulp(b))


def _close(a, b):
    return abs(a - b) <= _tolerance(a, b)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise StationBundleError("Station JSON contains duplicate keys.")
        result[key] = value
    return result


def _constant(_value):
    raise StationBundleError("Station JSON cannot contain non-finite constants.")


def parse_station_bundle(raw: bytes) -> StationBundle:
    """Parse strict bounded UTF-8 JSON, normalize SI and preserve exact input bytes."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_STATION_UPLOAD_BYTES:
        raise StationBundleError("Station upload must be bytes within the size limit.")
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_object, parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise StationBundleError("Station upload must be valid, finite, unique-key UTF-8 JSON.") from exc
    _keys(doc, {"schema_version", "units", "diameter", "hub_radius", "airfoil_id",
        "airfoil_coordinate_sha256", "provenance", "stations"})
    if type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
        raise StationBundleError("Unsupported station schema_version.")
    _keys(doc["units"], {"length", "angle"})
    length_unit, angle_unit = doc["units"]["length"], doc["units"]["angle"]
    if not isinstance(length_unit, str) or length_unit not in _LENGTH_FACTORS:
        raise StationBundleError("Unsupported explicit length unit.")
    if not isinstance(angle_unit, str) or angle_unit not in _ANGLE_FACTORS:
        raise StationBundleError("Unsupported explicit angle unit.")
    length, angle = _LENGTH_FACTORS[length_unit], _ANGLE_FACTORS[angle_unit]
    diameter = _number(doc["diameter"], "diameter") * length
    hub = _number(doc["hub_radius"], "hub_radius") * length
    radius = diameter / 2
    if not math.isfinite(diameter) or diameter <= 0 or radius <= 0 or not 0 <= hub < radius:
        raise StationBundleError("Diameter and hub radius must define a positive blade span.")
    airfoil_id = _text(doc["airfoil_id"], "airfoil_id", 128)
    coordinate_sha = _sha(doc["airfoil_coordinate_sha256"], "airfoil_coordinate_sha256")
    provenance_doc = doc["provenance"]
    _keys(provenance_doc, {"kind", "reference", "locator", "revision"}, {"parent_sha256"})
    kind = provenance_doc["kind"]
    if not isinstance(kind, str) or kind not in {"declared_design", "literature_geometry", "project_measurement", "derived_geometry"}:
        raise StationBundleError("Unsupported station provenance kind.")
    parent = provenance_doc.get("parent_sha256")
    if "parent_sha256" in provenance_doc:
        parent = _sha(parent, "parent_sha256")
    if kind == "derived_geometry" and parent is None:
        raise StationBundleError("Derived geometry requires its parent_sha256.")
    provenance = StationProvenance(kind, *(_text(provenance_doc[key], key)
        for key in ("reference", "locator", "revision")), parent)
    rows = doc["stations"]
    if not isinstance(rows, list) or not 2 <= len(rows) <= 64:
        raise StationBundleError("Station bundles require 2 to 64 stations.")
    stations = []
    for row in rows:
        _keys(row, {"radius", "chord", "twist"})
        point = StationPoint(_number(row["radius"], "radius") * length,
            _number(row["chord"], "chord") * length,
            _number(row["twist"], "twist") * angle)
        if not all(math.isfinite(v) for v in asdict(point).values()) or point.radius_m <= 0 or point.chord_m <= 0:
            raise StationBundleError("Station radius and chord must be positive and all values finite.")
        if point.radius_m < hub and not _close(point.radius_m, hub):
            raise StationBundleError("Station radius penetrates the hub.")
        if point.radius_m > radius and not _close(point.radius_m, radius):
            raise StationBundleError("Station radius exceeds the blade tip.")
        if stations and point.radius_m <= stations[-1].radius_m:
            raise StationBundleError("Station radii must be strictly increasing.")
        stations.append(point)
    provenance_payload = asdict(provenance)
    if parent is None:
        provenance_payload.pop("parent_sha256")
    canonical = json.dumps({"schema_version": 1, "units": {"length": "m", "angle": "rad"},
        "diameter": diameter, "hub_radius": hub, "airfoil_id": airfoil_id,
        "airfoil_coordinate_sha256": coordinate_sha, "provenance": provenance_payload,
        "stations": [{"radius": s.radius_m, "chord": s.chord_m, "twist": s.twist_rad} for s in stations]},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return StationBundle(tuple(stations), diameter, hub, airfoil_id, coordinate_sha,
        provenance, raw, hashlib.sha256(raw).hexdigest(), canonical,
        hashlib.sha256(canonical.encode("utf-8")).hexdigest())


def _verify(bundle):
    if not isinstance(bundle, StationBundle) or parse_station_bundle(bundle.raw_bytes) != bundle:
        raise StationBundleError("Station bundle identity no longer matches its source bytes.")


def export_station_bundle(bundle: StationBundle) -> str:
    """Return deterministic, explicitly SI JSON (UTF-8 encoding defines its hash)."""
    _verify(bundle)
    return bundle.canonical_json


def audit_station_bundle(bundle: StationBundle, *, diameter_m: float,
    hub_radius_m: float, hinge_radius_m: float, airfoil_id: str) -> StationCoverageAudit:
    """Check binding and coverage; uncovered hinges and gaps remain diagnostics."""
    _verify(bundle)
    diameter = _number(diameter_m, "diameter_m")
    hub = _number(hub_radius_m, "hub_radius_m")
    hinge = _number(hinge_radius_m, "hinge_radius_m")
    if not _close(diameter, bundle.diameter_m) or not _close(hub, bundle.hub_radius_m) or airfoil_id != bundle.airfoil_id:
        raise StationBundleError("Station geometry is bound to a different envelope or profile; values must match.")
    if not hub < hinge < diameter / 2:
        raise StationBundleError("Hinge must remain strictly inside the hub-to-tip span.")
    root, tip = bundle.stations[0].radius_m, bundle.stations[-1].radius_m
    root_gap, tip_gap = root - hub, diameter / 2 - tip
    root_complete, tip_complete = _close(root, hub), _close(tip, diameter / 2)
    return StationCoverageAudit(0. if root_complete else root_gap, 0. if tip_complete else tip_gap,
        root_complete and tip_complete, root < hinge < tip)
