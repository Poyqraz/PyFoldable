"""GEOM-01 negative clearance gate policy v1.

This module only interprets an already accepted GEOM-04 report. It does not
execute clearance, authenticate artifacts, read the filesystem, or mutate
evidence. A gate is False or None, never True.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re

POLICY_ID = "geom01_negative_clearance_v1"
MOTION_DOMAIN = "synchronous_planar_rigid_tips_from_zero_to_declared_endpoint"
_SEMANTICS = "negative_only"
_PART = re.compile(r"^blade_([1-8])_(root|tip)$")
_CONTACT = frozenset({
    "rounded_pose_contact", "nominal_pose_contact", "intersecting",
    "penetrating", "confirmed", "contact",
})
_SURFACE_KINDS = frozenset({"surface", "finite_hub"})
_INTERBLADE_KINDS = frozenset({"interblade"})


class ClearancePolicyError(ValueError):
    """The accepted report cannot be interpreted by this policy version."""


def _finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


@dataclass(frozen=True)
class NegativeClearancePolicy:
    """Explicit negative-only decision over accepted GEOM-04 evidence."""

    required_clearance_m: float
    enabled: bool = True
    policy_id: str = POLICY_ID
    motion_domain: str = MOTION_DOMAIN
    semantics: str = _SEMANTICS

    def __post_init__(self):
        if (self.policy_id != POLICY_ID or self.motion_domain != MOTION_DOMAIN
                or self.semantics != _SEMANTICS):
            raise ClearancePolicyError("Only geom01_negative_clearance_v1 is supported.")
        if type(self.enabled) is not bool:
            raise ClearancePolicyError("Negative-clearance policy enablement must be a boolean.")
        if not _finite(self.required_clearance_m) or not 0 <= self.required_clearance_m <= 0.1:
            raise ClearancePolicyError(
                "Negative-clearance threshold must be finite and within 0–0.1 m.")

    def declaration(self):
        return {
            "policy_id": self.policy_id,
            "enabled": self.enabled,
            "required_clearance_m": self.required_clearance_m,
            "motion_domain": self.motion_domain,
            "semantics": self.semantics,
        }


@dataclass(frozen=True)
class GateDecision:
    value: bool | None
    reason: str
    query_index: int | None = None
    interval_index: int | None = None

    def __post_init__(self):
        if self.value is not False and self.value is not None:
            raise ClearancePolicyError("A negative clearance gate cannot be true.")
        if self.value is False:
            if type(self.query_index) is not int or self.query_index < 0:
                raise ClearancePolicyError("A negative gate requires its query index.")
            if type(self.interval_index) is not int or self.interval_index < 0:
                raise ClearancePolicyError("A negative gate requires its interval index.")
        elif self.query_index is not None or self.interval_index is not None:
            raise ClearancePolicyError("An unresolved gate has no witness index.")


@dataclass(frozen=True)
class NegativeClearanceDecision:
    policy_id: str
    surface_path_clearance: GateDecision
    interblade_clearance: GateDecision


def _both(reason):
    gate = GateDecision(None, reason)
    return NegativeClearanceDecision(POLICY_ID, gate, gate)


def _part(name):
    match = _PART.fullmatch(name) if isinstance(name, str) else None
    if match is None:
        return None
    return int(match.group(1)), match.group(2)


def _hardware_bodies(request):
    hardware = request.get("hardware") if isinstance(request, dict) else None
    if hardware is None:
        return []
    if not isinstance(hardware, dict) or not isinstance(hardware.get("bodies"), list):
        raise ClearancePolicyError("Candidate clearance policy rejected the hardware declaration.")
    bodies = []
    for body in hardware["bodies"]:
        if not isinstance(body, dict) or not isinstance(body.get("name"), str):
            raise ClearancePolicyError("Candidate clearance policy rejected a hardware body.")
        if any(existing["name"] == body["name"] for existing in bodies):
            raise ClearancePolicyError("Candidate clearance policy rejected duplicate hardware names.")
        bodies.append(body)
    return bodies


def _is_finite_hub(body):
    geometry = body.get("geometry")
    return (body.get("binding") == "hub" and isinstance(geometry, dict)
            and geometry.get("kind") == "finite_cylinder")


def _classify(query, bodies):
    if not isinstance(query, dict):
        raise ClearancePolicyError("Candidate clearance policy rejected a query.")
    kind, a, b = query.get("kind"), query.get("a"), query.get("b")
    left, right = _part(a), _part(b)
    by_name = {body["name"]: body for body in bodies}
    if kind == "own_root_tip":
        if (left is None or right is None or left[0] != right[0]
                or {left[1], right[1]} != {"root", "tip"}):
            raise ClearancePolicyError("Candidate clearance query identity contradicts own_root_tip.")
        return "surface"
    if kind == "interblade":
        if left is None or right is None or left[0] == right[0]:
            raise ClearancePolicyError("Candidate clearance query identity contradicts interblade.")
        return "interblade"
    if kind == "hub":
        if left is not None and b == "hub_envelope":
            return "infinite_hub"
        raise ClearancePolicyError("Candidate clearance query identity contradicts hub.")
    if kind == "hardware_surface":
        # Producer role, not name shape: a is the retained surface, b is the hardware body.
        body = by_name.get(b) if isinstance(b, str) else None
        if left is None or body is None:
            raise ClearancePolicyError("Candidate clearance query identity contradicts hardware_surface.")
        if _is_finite_hub(body):
            return "finite_hub"
        return "irrelevant"
    if kind == "hardware_pair":
        if (isinstance(a, str) and isinstance(b, str) and a != b
                and a in by_name and b in by_name):
            return "irrelevant"
        raise ClearancePolicyError("Candidate clearance query identity contradicts hardware_pair.")
    raise ClearancePolicyError("Candidate clearance policy rejected an unsupported query kind.")


def _threshold_matches(policy, request):
    inputs = request.get("inputs") if isinstance(request, dict) else None
    if not isinstance(inputs, dict) or "required_clearance_m" not in inputs:
        return False
    reported = inputs["required_clearance_m"]
    return _finite(reported) and reported == policy.required_clearance_m


def _path_radians(request):
    inputs = request.get("inputs")
    if not isinstance(inputs, dict) or not _finite(inputs.get("end_angle_deg")):
        raise ClearancePolicyError("Candidate path endpoint is not a supported stow angle.")
    end = inputs["end_angle_deg"]
    if not -180 <= end <= 0:
        raise ClearancePolicyError("Candidate path endpoint is not a supported stow angle.")
    return math.radians(float(end)), 0.0


def _require_consistent_violation(result, path_min, path_max, threshold):
    """Fail closed unless the producer violation proves the policy threshold.

    Surface and hardware producers write one violation interval and copy that
    same witness onto the query result. Equality of those two values is exact.
    A witness equal to the threshold does not prove a violation.
    """
    if not isinstance(result, dict):
        raise ClearancePolicyError("Candidate clearance policy rejected a query result.")
    intervals = result.get("intervals")
    if not isinstance(intervals, list):
        raise ClearancePolicyError("A violation is missing its interval ledger.")
    query_witness = result.get("witness_clearance_m")
    if not _finite(query_witness) or not query_witness < threshold:
        raise ClearancePolicyError("A violation witness does not prove the policy clearance threshold.")
    found = None
    for index, interval in enumerate(intervals):
        if not isinstance(interval, dict) or interval.get("status") != "violation":
            continue
        if found is not None:
            raise ClearancePolicyError("A violation has more than one producer violation interval.")
        found = index
    if found is None:
        raise ClearancePolicyError("A violation has no producer violation interval.")
    interval = intervals[found]
    clearance = interval.get("witness_clearance_m")
    angle = interval.get("witness_angle_rad")
    start = interval.get("angle_min_rad")
    stop = interval.get("angle_max_rad")
    if not all(_finite(value) for value in (clearance, angle, start, stop)):
        raise ClearancePolicyError("A violation witness is not finite.")
    if clearance != query_witness or not clearance < threshold:
        raise ClearancePolicyError("A violation witness does not prove the policy clearance threshold.")
    if not (start <= angle <= stop and path_min <= angle <= path_max):
        raise ClearancePolicyError("A violation has no usable witness inside the candidate path.")
    return found


def _gate(rows, relevant, *, infinite_hub_violation):
    saw_relevant = saw_unknown = saw_contact = saw_separated = False
    for index, kind, query, interval_index in rows:
        if kind not in relevant:
            continue
        saw_relevant = True
        result = query.get("result")
        if not isinstance(result, dict):
            raise ClearancePolicyError("Candidate clearance policy rejected a query result.")
        status = result.get("status")
        if status == "violation":
            return GateDecision(False, "relevant_violation_witness", index, interval_index)
        if status == "unknown":
            contact = result.get("contact_status")
            if isinstance(contact, str) and contact in _CONTACT:
                saw_contact = True
            else:
                saw_unknown = True
        elif status == "separated":
            saw_separated = True
        else:
            raise ClearancePolicyError("Candidate clearance query status is not interpretable.")
    if not saw_relevant:
        if infinite_hub_violation and relevant is _SURFACE_KINDS:
            return GateDecision(None, "infinite_hub_violation_not_finite_hub_proof")
        return GateDecision(None, "no_relevant_violation")
    if saw_unknown:
        return GateDecision(None, "relevant_numerics_unresolved")
    if saw_contact:
        return GateDecision(None, "contact_only_unresolved")
    if infinite_hub_violation and relevant is _SURFACE_KINDS:
        return GateDecision(None, "infinite_hub_violation_not_finite_hub_proof")
    if saw_separated:
        return GateDecision(None, "true_promotion_disabled")
    return GateDecision(None, "no_relevant_violation")


def decide_negative_clearance(policy, report, *, evidence_status="completed"):
    """Return the v1 negative decision for one accepted evidence state."""
    if not isinstance(policy, NegativeClearancePolicy):
        raise ClearancePolicyError("Expected the negative clearance policy.")
    if not policy.enabled:
        return _both("policy_not_enabled")
    if evidence_status == "no_evidence":
        return _both("no_evidence")
    if evidence_status == "candidate_validation_failed":
        return _both("candidate_validation_failed")
    if evidence_status == "evidence_unavailable_oversize":
        return _both("evidence_unavailable_oversize")
    if evidence_status != "completed":
        raise ClearancePolicyError("Unsupported candidate clearance evidence state.")
    if not isinstance(report, dict):
        return _both("no_evidence")
    request = report.get("request")
    if not isinstance(request, dict) or request.get("motion") != policy.motion_domain:
        return _both("motion_scope_mismatch")
    if not _threshold_matches(policy, request):
        return _both("clearance_threshold_mismatch")
    queries = report.get("queries")
    if not isinstance(queries, list):
        raise ClearancePolicyError("Candidate clearance policy rejected the query ledger.")
    bodies = _hardware_bodies(request)
    path_min, path_max = _path_radians(request)
    rows = []
    infinite_hub_violation = False
    for index, query in enumerate(queries):
        kind = _classify(query, bodies)
        result = query.get("result") if isinstance(query, dict) else None
        if not isinstance(result, dict):
            raise ClearancePolicyError("Candidate clearance policy rejected a query result.")
        interval_index = None
        if result.get("status") == "violation":
            interval_index = _require_consistent_violation(
                result, path_min, path_max, policy.required_clearance_m)
        rows.append((index, kind, query, interval_index))
        if kind == "infinite_hub" and result.get("status") == "violation":
            infinite_hub_violation = True
    return NegativeClearanceDecision(
        POLICY_ID,
        _gate(rows, _SURFACE_KINDS, infinite_hub_violation=infinite_hub_violation),
        _gate(rows, _INTERBLADE_KINDS, infinite_hub_violation=False),
    )
