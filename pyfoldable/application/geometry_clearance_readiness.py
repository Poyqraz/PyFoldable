"""GEOM-01 positive-clearance readiness diagnostic v1.

This module only reads an already accepted GEOM-04 evidence state. It does not
execute clearance, build meshes, read files, hash reports, or mutate evidence.
`preconditions_satisfied` means the current evidence meets this question's
proof prerequisites. It is not a constraint value and it never means True.

One-blade rotors have no interblade obligations, so that gate is
`not_applicable` before evidence availability is considered. Every dimension
on that gate is `not_applicable`. Question and candidate fields stay on the
parent result.

A claimed `separated` query is always checked against the producer threshold
in `request.inputs.required_clearance_m`. That check does not depend on the
readiness question. The question threshold is compared afterwards, and a
mismatch is only `threshold_mismatch`.

Each gate publishes the fixed dimensions with a state: `satisfied`,
`blocked`, `not_assessed`, or `not_applicable`. Evidence that was never
read does not mark downstream dimensions satisfied. Surface-path readiness
always carries `shared_hinge_contact_domain_unresolved` once a completed
report is assessed: the supported open-surface model duplicates the hinge
station and this question does not treat that contact as permitted.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re

DIAGNOSTIC_ID = "geom01_positive_readiness_v1"
MOTION_DOMAIN = "synchronous_planar_rigid_tips_from_zero_to_declared_endpoint"
MODEL_SCOPE = "retained_open_preview_triangle_surfaces_not_solid_bodies"
EFFECT = "diagnostic_only_does_not_alter_geom01_constraints"
HUB_NOT_ESTABLISHED = "not_established"
HUB_NOMINAL_CONTAINMENT = "infinite_envelope_under_nominal_containment"
DIMENSIONS = (
    "question_compatibility",
    "candidate_binding",
    "radial_coverage",
    "exclusions",
    "pair_coverage",
    "angular_coverage",
    "numerical_resolution",
    "separation_support",
    "hub_suitability",
    "model_compatibility",
    "contact_domain",
)
_PROOF_BASIS = "numerical_open_surface_prerequisite_diagnostic_not_a_constraint_value"
_NOT_APPLICABLE_BASIS = "no_interblade_obligations_for_a_one_blade_rotor"
_PART = re.compile(r"^blade_([1-8])_(root|tip)$")
_CONTACT = frozenset({
    "rounded_pose_contact", "nominal_pose_contact", "intersecting",
    "penetrating", "confirmed", "contact",
})
_INFINITE_HUB = "infinite_cylinder_conservative_envelope"
_FINITE_HUB = "declared_finite_cylinder"
_UNAVAILABLE = {
    "no_evidence": "absent",
    "candidate_validation_failed": "candidate_validation_failed",
    "evidence_unavailable_oversize": "oversize",
}


class ClearanceReadinessError(ValueError):
    """Accepted evidence contradicts this diagnostic and the search must abort."""


def _finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


@dataclass(frozen=True)
class FuturePositiveQuestionV1:
    """Fixed question a later policy would have to ask before considering True."""

    required_clearance_m: float
    hub_containment: str = HUB_NOT_ESTABLISHED
    diagnostic_id: str = DIAGNOSTIC_ID
    motion_domain: str = MOTION_DOMAIN
    model_scope: str = MODEL_SCOPE
    effect: str = EFFECT

    def __post_init__(self):
        if (self.diagnostic_id != DIAGNOSTIC_ID or self.motion_domain != MOTION_DOMAIN
                or self.model_scope != MODEL_SCOPE or self.effect != EFFECT):
            raise ClearanceReadinessError("Only geom01_positive_readiness_v1 is supported.")
        if self.hub_containment not in {HUB_NOT_ESTABLISHED, HUB_NOMINAL_CONTAINMENT}:
            raise ClearanceReadinessError("Unsupported hub containment interpretation.")
        if not _finite(self.required_clearance_m) or not 0 <= self.required_clearance_m <= 0.1:
            raise ClearanceReadinessError(
                "Readiness threshold must be finite and within 0–0.1 m.")

    def declaration(self):
        return {
            "diagnostic_id": self.diagnostic_id,
            "required_clearance_m": self.required_clearance_m,
            "motion_domain": self.motion_domain,
            "model_scope": self.model_scope,
            "hub_containment": self.hub_containment,
            "effect": self.effect,
        }


@dataclass(frozen=True)
class CandidateClearanceFacts:
    """Candidate geometry the accepted report is checked against."""

    blade_count: int
    end_angle_deg: float
    hub_radius_m: float
    hinge_radius_m: float
    tip_radius_m: float
    first_station_radius_m: float
    last_station_radius_m: float
    root_exclusion_width_m: float | None = None
    hinge_exclusion_width_m: float | None = None

    def __post_init__(self):
        if type(self.blade_count) is not int or not 1 <= self.blade_count <= 8:
            raise ClearanceReadinessError("Candidate blade count is outside the readiness domain.")
        if not _finite(self.end_angle_deg) or not -180 <= self.end_angle_deg <= 0:
            raise ClearanceReadinessError("Candidate endpoint is not a supported stow angle.")
        radii = (
            self.hub_radius_m, self.hinge_radius_m, self.tip_radius_m,
            self.first_station_radius_m, self.last_station_radius_m,
        )
        if any(not _finite(value) for value in radii):
            raise ClearanceReadinessError("Candidate radii must be finite.")
        if not 0 < self.hub_radius_m < self.hinge_radius_m < self.tip_radius_m:
            raise ClearanceReadinessError("Candidate hub, hinge, and tip radii are not ordered.")
        if not self.first_station_radius_m < self.last_station_radius_m:
            raise ClearanceReadinessError("Candidate stations are not ordered.")
        for name in ("root_exclusion_width_m", "hinge_exclusion_width_m"):
            value = getattr(self, name)
            if value is not None and (not _finite(value) or value < 0):
                raise ClearanceReadinessError("Candidate exclusion widths must be nonnegative.")


@dataclass(frozen=True)
class DimensionReadiness:
    """One fixed proof dimension and its machine-readable state."""

    name: str
    state: str


@dataclass(frozen=True)
class ReadinessBlocker:
    code: str
    dimension: str
    pair_key: tuple = ()
    interval_index: int | None = None
    region: str | None = None
    cause: str | None = None
    evidence_detail: str | None = None


@dataclass(frozen=True)
class GateReadiness:
    assessment: str
    primary_reason: str | None
    blockers: tuple
    dimensions: tuple
    proof_basis: str


@dataclass(frozen=True)
class PositiveClearanceReadiness:
    diagnostic_id: str
    effect: str
    question: FuturePositiveQuestionV1
    evidence_status: str
    surface_path: GateReadiness
    interblade: GateReadiness


def _blocker(code, dimension, **fields):
    return ReadinessBlocker(code, dimension, **fields)


def _sort_key(blocker):
    return (
        DIMENSIONS.index(blocker.dimension),
        tuple(str(part) for part in blocker.pair_key),
        blocker.region or "",
        blocker.cause or "",
        blocker.evidence_detail or "",
        blocker.code,
        -1 if blocker.interval_index is None else blocker.interval_index,
    )


_ALWAYS_EVALUATED = frozenset({
    "question_compatibility",
    "candidate_binding",
    "radial_coverage",
    "exclusions",
    "pair_coverage",
    "model_compatibility",
})
_INTERBLADE_NOT_APPLICABLE = frozenset({"hub_suitability", "contact_domain"})


def _dimension_rows(blockers, *, not_applicable, evaluated):
    blocked = {blocker.dimension for blocker in blockers}
    rows = []
    for name in DIMENSIONS:
        if name in not_applicable:
            if name in blocked:
                raise ClearanceReadinessError("A blocker was recorded outside this gate's dimensions.")
            state = "not_applicable"
        elif name in blocked:
            state = "blocked"
        elif name in evaluated:
            state = "satisfied"
        else:
            state = "not_assessed"
        rows.append(DimensionReadiness(name, state))
    return tuple(rows)


def _unavailable_dimensions():
    return tuple(
        DimensionReadiness(name, "blocked" if name == "candidate_binding" else "not_assessed")
        for name in DIMENSIONS)


def _not_applicable_dimensions():
    return tuple(DimensionReadiness(name, "not_applicable") for name in DIMENSIONS)


def _evaluated_dimensions(queries, *, complete, surface):
    evaluated = set(_ALWAYS_EVALUATED)
    if surface:
        evaluated.update(("hub_suitability", "contact_domain"))
    if complete:
        evaluated.update(("angular_coverage", "numerical_resolution"))
        if all(query["result"]["status"] == "separated" for query in queries):
            evaluated.add("separation_support")
    return evaluated


def _gate(blockers, *, applicable, dimensions):
    if not applicable:
        return GateReadiness(
            "not_applicable", None, (), _not_applicable_dimensions(), _NOT_APPLICABLE_BASIS)
    ordered = tuple(sorted(blockers, key=_sort_key))
    if not ordered:
        unresolved = [row.name for row in dimensions if row.state not in {"satisfied", "not_applicable"}]
        if unresolved:
            raise ClearanceReadinessError("Preconditions cannot hide an unresolved dimension.")
        return GateReadiness("preconditions_satisfied", None, (), dimensions, _PROOF_BASIS)
    if not any(row.state == "blocked" for row in dimensions):
        raise ClearanceReadinessError("Blocked readiness is missing a blocked dimension.")
    return GateReadiness("blocked", ordered[0].code, ordered, dimensions, _PROOF_BASIS)


def _part(name):
    match = _PART.fullmatch(name) if isinstance(name, str) else None
    if match is None:
        return None
    return int(match.group(1)), match.group(2)


def _canonical_surface(left, right):
    def key(part):
        return (part[0], 0 if part[1] == "root" else 1)
    first, second = sorted((left, right), key=key)
    return ("surface", first[0], first[1], "surface", second[0], second[1])


def _hardware_bodies(request):
    hardware = request.get("hardware")
    if hardware is None:
        return []
    if not isinstance(hardware, dict) or not isinstance(hardware.get("bodies"), list):
        raise ClearanceReadinessError("Accepted hardware declaration is malformed.")
    bodies = []
    for body in hardware["bodies"]:
        if not isinstance(body, dict) or not isinstance(body.get("name"), str):
            raise ClearanceReadinessError("Accepted hardware declaration is malformed.")
        if any(existing["name"] == body["name"] for existing in bodies):
            raise ClearanceReadinessError("Accepted hardware declaration repeats a body name.")
        bodies.append(body)
    return bodies


def _is_finite_hub(body):
    geometry = body.get("geometry")
    return (body.get("binding") == "hub" and isinstance(geometry, dict)
            and geometry.get("kind") == "finite_cylinder")


def _require_in_range(part, blade_count):
    if part[0] > blade_count:
        raise ClearanceReadinessError("Accepted query names a blade outside the candidate.")


def _classify(query, bodies, blade_count):
    if not isinstance(query, dict):
        raise ClearanceReadinessError("Accepted query ledger is malformed.")
    kind, left_name, right_name = query.get("kind"), query.get("a"), query.get("b")
    left, right = _part(left_name), _part(right_name)
    by_name = {body["name"]: body for body in bodies}
    if kind == "own_root_tip":
        if (left is None or right is None or left[0] != right[0]
                or {left[1], right[1]} != {"root", "tip"}):
            raise ClearanceReadinessError("Accepted query identity contradicts own_root_tip.")
        _require_in_range(left, blade_count)
        return "own", _canonical_surface(left, right)
    if kind == "interblade":
        if left is None or right is None or left[0] == right[0]:
            raise ClearanceReadinessError("Accepted query identity contradicts interblade.")
        _require_in_range(left, blade_count)
        _require_in_range(right, blade_count)
        return "interblade", _canonical_surface(left, right)
    if kind == "hub":
        if left is None or right_name != "hub_envelope":
            raise ClearanceReadinessError("Accepted query identity contradicts hub.")
        _require_in_range(left, blade_count)
        return "infinite_hub", ("surface", left[0], left[1], "hub_envelope")
    if kind == "hardware_surface":
        body = by_name.get(right_name) if isinstance(right_name, str) else None
        if left is None or body is None:
            raise ClearanceReadinessError("Accepted query identity contradicts hardware_surface.")
        _require_in_range(left, blade_count)
        if _is_finite_hub(body):
            return "finite_hub", ("surface", left[0], left[1], "hardware", right_name)
        return "irrelevant", None
    if kind == "hardware_pair":
        if (isinstance(left_name, str) and isinstance(right_name, str) and left_name != right_name
                and left_name in by_name and right_name in by_name):
            return "irrelevant", None
        raise ClearanceReadinessError("Accepted query identity contradicts hardware_pair.")
    raise ClearanceReadinessError("Accepted query kind is not a producer role.")


def _expected_pairs(blade_count, mode, hub_name):
    parts = [(blade, part) for blade in range(1, blade_count + 1) for part in ("root", "tip")]
    own = set()
    hub = set()
    inter = set()
    for blade, part in parts:
        partner = (blade, "tip" if part == "root" else "root")
        if part == "root":
            own.add(_canonical_surface((blade, part), partner))
        if mode == _INFINITE_HUB:
            hub.add(("surface", blade, part, "hub_envelope"))
        else:
            hub.add(("surface", blade, part, "hardware", hub_name))
    for index, left in enumerate(parts):
        for right in parts[index + 1:]:
            if left[0] != right[0]:
                inter.add(_canonical_surface(left, right))
    return own, hub, inter


def _span(candidate):
    """Same 8-ULP station rule as the mechanism geometry audit."""
    root_gap = candidate.first_station_radius_m - candidate.hub_radius_m
    tip_gap = candidate.tip_radius_m - candidate.last_station_radius_m
    root_ok = abs(root_gap) <= 8 * max(
        math.ulp(candidate.first_station_radius_m), math.ulp(candidate.hub_radius_m))
    tip_ok = abs(tip_gap) <= 8 * max(
        math.ulp(candidate.last_station_radius_m), math.ulp(candidate.tip_radius_m))
    hinge_ok = (
        candidate.first_station_radius_m < candidate.hinge_radius_m < candidate.last_station_radius_m)
    return root_gap, tip_gap, root_ok, tip_ok, hinge_ok


def _dyadic_angles(start, stop, max_depth):
    allowed = set()
    stack = [(start, stop, 0)]
    seen = set()
    while stack:
        low, high, depth = stack.pop()
        key = (low, high, depth)
        if key in seen:
            continue
        seen.add(key)
        allowed.add(low)
        allowed.add(high)
        if depth < max_depth and high > low:
            middle = (low + high) / 2.0
            stack.append((low, middle, depth + 1))
            stack.append((middle, high, depth + 1))
    return allowed


def _coverage(intervals, start, max_depth, max_intervals):
    if len(intervals) > max_intervals:
        raise ClearanceReadinessError("Interval ledger exceeds the declared interval budget.")
    allowed = _dyadic_angles(start, 0.0, max_depth)
    positive = []
    points = []
    seen_positive = set()
    for index, interval in enumerate(intervals):
        if not isinstance(interval, dict):
            raise ClearanceReadinessError("Interval ledger is malformed.")
        low, high = interval.get("angle_min_rad"), interval.get("angle_max_rad")
        if not _finite(low) or not _finite(high):
            raise ClearanceReadinessError("Interval endpoints are not finite.")
        if low > high:
            raise ClearanceReadinessError("Interval is not ordered.")
        if low < start or high > 0.0:
            raise ClearanceReadinessError("Interval is outside the candidate path.")
        if low == high:
            if low not in allowed:
                raise ClearanceReadinessError(
                    "Zero-width interval is not a bounded subdivision singleton.")
            points.append(low)
            continue
        identity = (low, high)
        if identity in seen_positive:
            raise ClearanceReadinessError("Duplicate positive-width interval.")
        seen_positive.add(identity)
        positive.append((low, high, index))
    positive.sort(key=lambda row: (row[0], row[1], row[2]))
    for previous, following in zip(positive, positive[1:]):
        if following[0] < previous[1]:
            raise ClearanceReadinessError("Positive-width intervals overlap.")
    if start == 0.0:
        return "complete" if any(point == 0.0 for point in points) else "incomplete"
    if not positive or positive[0][0] != start or positive[-1][1] != 0.0:
        return "incomplete"
    for previous, following in zip(positive, positive[1:]):
        if previous[1] != following[0]:
            return "incomplete"
    return "complete"


def _cause(result):
    if result.get("contact_status") in _CONTACT:
        return "contact"
    for interval in result.get("intervals") or []:
        if isinstance(interval, dict) and interval.get("contact_status") in _CONTACT:
            return "contact"
    texts = [result.get("reason"), result.get("method")]
    for interval in result.get("intervals") or []:
        if isinstance(interval, dict):
            texts.extend((interval.get("reason"), interval.get("method")))
    blob = " ".join(text.lower() for text in texts if isinstance(text, str))
    if "budget" in blob:
        return "budget"
    if "precision" in blob:
        return "precision"
    return "unspecified"


def _require_separation(result, intervals, threshold):
    if result.get("contact_status") != "separated":
        raise ClearanceReadinessError("Separated query has a contradictory contact state.")
    lowers = []
    for interval in intervals:
        if interval.get("status") != "separated" or interval.get("contact_status") != "separated":
            raise ClearanceReadinessError("Separated query contains contradictory interval evidence.")
        lower = interval.get("lower_bound_m")
        if not _finite(lower):
            raise ClearanceReadinessError("Separated lower bound is missing or non-finite.")
        if not _finite(threshold) or not lower > threshold:
            raise ClearanceReadinessError(
                "Separated lower bound does not strictly exceed the producer clearance.")
        lowers.append(lower)
    query_lower = result.get("lower_bound_m")
    if not lowers or not _finite(query_lower) or query_lower != min(lowers):
        raise ClearanceReadinessError("Query lower bound is inconsistent with its interval minima.")


def _budgets(inputs):
    depth = inputs.get("max_depth")
    limit = inputs.get("max_intervals")
    if type(depth) is not int or not 0 <= depth <= 8:
        raise ClearanceReadinessError("Declared subdivision depth is not a producer budget.")
    if type(limit) is not int or not 1 <= limit <= 255:
        raise ClearanceReadinessError("Declared interval budget is not a producer budget.")
    return depth, limit


def _inspect(query, pair_key, start, threshold, depth, limit):
    result = query.get("result")
    if not isinstance(result, dict):
        raise ClearanceReadinessError("Accepted query is missing its result.")
    status = result.get("status")
    if status not in {"separated", "unknown", "violation"}:
        raise ClearanceReadinessError("Accepted query status is not interpretable.")
    intervals = result.get("intervals")
    if not isinstance(intervals, (list, tuple)):
        raise ClearanceReadinessError("Accepted query is missing its interval ledger.")
    covered = _coverage(intervals, start, depth, limit)
    blockers = []
    if covered != "complete":
        if status == "separated":
            raise ClearanceReadinessError("Separated query does not cover the candidate path.")
        blockers.append(_blocker(
            "angular_coverage_incomplete", "angular_coverage", pair_key=pair_key))
    if status == "separated":
        _require_separation(result, intervals, threshold)
    elif status == "unknown":
        blockers.append(_blocker(
            "relevant_query_unresolved", "numerical_resolution",
            pair_key=pair_key, cause=_cause(result)))
    else:
        blockers.append(_blocker(
            "relevant_query_violation", "separation_support", pair_key=pair_key))
    return blockers


def _common_blockers(question, report, candidate, thresholds_match):
    blockers = []
    request = report.get("request")
    if not isinstance(request, dict):
        raise ClearanceReadinessError("Accepted report is missing its request.")
    inputs = request.get("inputs")
    if not isinstance(inputs, dict):
        raise ClearanceReadinessError("Accepted report is missing its inputs.")
    reported_angle = inputs.get("end_angle_deg")
    if not _finite(reported_angle) or reported_angle != candidate.end_angle_deg:
        raise ClearanceReadinessError("Candidate endpoint contradicts the accepted report.")
    reported_threshold = inputs.get("required_clearance_m")
    if not thresholds_match:
        blockers.append(_blocker("threshold_mismatch", "question_compatibility"))
    if request.get("motion") != question.motion_domain:
        blockers.append(_blocker("motion_scope_mismatch", "question_compatibility"))
    if request.get("model_scope") != question.model_scope:
        blockers.append(_blocker("proof_scope_incomplete", "model_compatibility"))
    root_gap, tip_gap, root_ok, tip_ok, hinge_ok = _span(candidate)
    if report.get("root_gap_m") != root_gap or report.get("tip_gap_m") != tip_gap:
        raise ClearanceReadinessError("Report span metadata contradicts the candidate.")
    if report.get("station_span_complete") is not (root_ok and tip_ok and hinge_ok):
        raise ClearanceReadinessError("Report span metadata contradicts the candidate.")
    if not root_ok:
        blockers.append(_blocker("root_span_missing", "radial_coverage"))
    if not tip_ok:
        blockers.append(_blocker("tip_span_missing", "radial_coverage"))
    if not hinge_ok:
        blockers.append(_blocker("proof_scope_incomplete", "model_compatibility"))
    excluded = report.get("excluded_regions")
    if not isinstance(excluded, dict):
        raise ClearanceReadinessError("Report exclusion metadata is malformed.")
    root_width = excluded.get("root_radial_width_m")
    hinge_width = excluded.get("hinge_half_width_m")
    if not _finite(root_width) or not _finite(hinge_width) or root_width < 0 or hinge_width < 0:
        raise ClearanceReadinessError("Report exclusion widths are not usable.")
    if candidate.root_exclusion_width_m is not None and candidate.root_exclusion_width_m != root_width:
        raise ClearanceReadinessError("Report exclusion metadata contradicts the candidate.")
    if candidate.hinge_exclusion_width_m is not None and candidate.hinge_exclusion_width_m != hinge_width:
        raise ClearanceReadinessError("Report exclusion metadata contradicts the candidate.")
    if root_width > 0:
        blockers.append(_blocker("excluded_region", "exclusions", region="root", pair_key=("region", "root")))
    if hinge_width > 0:
        blockers.append(_blocker("excluded_region", "exclusions", region="hinge", pair_key=("region", "hinge")))
    return blockers, inputs


def _hub_mode(request, bodies):
    mode = request.get("hub_obstacle")
    if mode not in {_INFINITE_HUB, _FINITE_HUB}:
        raise ClearanceReadinessError("Accepted hub mode is not a producer mode.")
    finite = [body for body in bodies if _is_finite_hub(body)]
    if mode == _FINITE_HUB:
        if len(finite) != 1:
            raise ClearanceReadinessError("Finite-hub evidence does not identify one cylinder.")
        if any(body.get("name") == "hub_envelope" for body in bodies):
            raise ClearanceReadinessError("Finite-hub evidence reuses the infinite envelope name.")
        return mode, finite[0]["name"]
    if finite:
        raise ClearanceReadinessError("Infinite-envelope evidence also declares a finite hub.")
    return mode, None


def assess_positive_clearance_readiness(question, *, evidence_status, report, candidate):
    """Diagnose whether accepted evidence meets this question's prerequisites."""
    if not isinstance(question, FuturePositiveQuestionV1):
        raise ClearanceReadinessError("Expected the positive-clearance readiness question.")
    if not isinstance(candidate, CandidateClearanceFacts):
        raise ClearanceReadinessError("Expected candidate clearance facts.")
    interblade_applies = candidate.blade_count != 1
    if evidence_status in _UNAVAILABLE:
        detail = _UNAVAILABLE[evidence_status]
        unavailable = [_blocker("evidence_unavailable", "candidate_binding", evidence_detail=detail)]
        unavailable_dimensions = _unavailable_dimensions()
        return PositiveClearanceReadiness(
            DIAGNOSTIC_ID, EFFECT, question, evidence_status,
            _gate(unavailable, applicable=True, dimensions=unavailable_dimensions),
            _gate(unavailable, applicable=interblade_applies, dimensions=unavailable_dimensions),
        )
    if evidence_status != "completed":
        raise ClearanceReadinessError("Unsupported candidate clearance evidence state.")
    if not isinstance(report, dict):
        raise ClearanceReadinessError("Completed evidence is missing its report.")
    request = report.get("request")
    inputs = request.get("inputs") if isinstance(request, dict) else None
    reported_threshold = inputs.get("required_clearance_m") if isinstance(inputs, dict) else None
    if not _finite(reported_threshold):
        raise ClearanceReadinessError("Accepted report is missing its required clearance.")
    thresholds_match = reported_threshold == question.required_clearance_m
    common, inputs = _common_blockers(question, report, candidate, thresholds_match)
    bodies = _hardware_bodies(request)
    mode, hub_name = _hub_mode(request, bodies)
    own_keys, hub_keys, inter_keys = _expected_pairs(candidate.blade_count, mode, hub_name)
    expected = {"own": own_keys, "interblade": inter_keys, "infinite_hub": hub_keys, "finite_hub": hub_keys}
    role_mode = {"infinite_hub": _INFINITE_HUB, "finite_hub": _FINITE_HUB}
    queries = report.get("queries")
    if not isinstance(queries, list):
        raise ClearanceReadinessError("Accepted report is missing its query ledger.")
    seen = {}
    relevant = []
    for query in queries:
        role, key = _classify(query, bodies, candidate.blade_count)
        if role == "irrelevant":
            continue
        if role_mode.get(role, mode) != mode or key not in expected[role]:
            raise ClearanceReadinessError("Accepted report contains an unexpected relevant pair.")
        if key in seen:
            raise ClearanceReadinessError("Accepted report repeats a relevant pair.")
        seen[key] = query
        relevant.append((role, key, query))
    depth, limit = _budgets(inputs)
    start = math.radians(float(candidate.end_angle_deg))
    surface = list(common)
    interblade = [] if not interblade_applies else list(common)
    for role, key, query in relevant:
        found = _inspect(query, key, start, reported_threshold, depth, limit)
        if role == "interblade":
            interblade.extend(found)
        else:
            surface.extend(found)
    for key in sorted(own_keys | hub_keys, key=lambda item: tuple(str(part) for part in item)):
        if key not in seen:
            surface.append(_blocker("relevant_pair_missing", "pair_coverage", pair_key=key))
    if interblade_applies:
        for key in sorted(inter_keys, key=lambda item: tuple(str(part) for part in item)):
            if key not in seen:
                interblade.append(_blocker("relevant_pair_missing", "pair_coverage", pair_key=key))
    if mode == _INFINITE_HUB and question.hub_containment != HUB_NOMINAL_CONTAINMENT:
        surface.append(_blocker("hub_model_not_positive_sufficient", "hub_suitability"))
    surface.append(_blocker("shared_hinge_contact_domain_unresolved", "contact_domain"))
    surface_queries = [query for role, _key, query in relevant if role != "interblade"]
    inter_queries = [query for role, _key, query in relevant if role == "interblade"]
    surface_dimensions = _dimension_rows(
        surface, not_applicable=frozenset(),
        evaluated=_evaluated_dimensions(
            surface_queries, complete=(own_keys | hub_keys) <= set(seen), surface=True))
    inter_dimensions = _dimension_rows(
        interblade, not_applicable=_INTERBLADE_NOT_APPLICABLE,
        evaluated=_evaluated_dimensions(
            inter_queries, complete=inter_keys <= set(seen), surface=False))
    return PositiveClearanceReadiness(
        DIAGNOSTIC_ID, EFFECT, question, evidence_status,
        _gate(surface, applicable=True, dimensions=surface_dimensions),
        _gate(interblade, applicable=interblade_applies, dimensions=inter_dimensions),
    )


def _blocker_document(blocker):
    row = {"code": blocker.code, "dimension": blocker.dimension}
    if blocker.pair_key:
        row["pair"] = list(blocker.pair_key)
    if blocker.interval_index is not None:
        row["interval_index"] = blocker.interval_index
    if blocker.region is not None:
        row["region"] = blocker.region
    if blocker.cause is not None:
        row["cause"] = blocker.cause
    if blocker.evidence_detail is not None:
        row["evidence_detail"] = blocker.evidence_detail
    return row


def _gate_document(gate):
    return {
        "assessment": gate.assessment,
        "primary_reason": gate.primary_reason,
        "blockers": [_blocker_document(blocker) for blocker in gate.blockers],
        "dimensions": [{"name": item.name, "state": item.state} for item in gate.dimensions],
        "proof_basis": gate.proof_basis,
    }


def readiness_document(result):
    """JSON-safe diagnostic. It contains no constraint boolean."""
    if not isinstance(result, PositiveClearanceReadiness):
        raise ClearanceReadinessError("Expected a positive-clearance readiness result.")
    return {
        "diagnostic_id": result.diagnostic_id,
        "effect": result.effect,
        "question": result.question.declaration(),
        "evidence_status": result.evidence_status,
        "surface_path": _gate_document(result.surface_path),
        "interblade": _gate_document(result.interblade),
    }
