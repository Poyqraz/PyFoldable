"""GEOM-01: bounded planar hinge/stow screening using the existing audit/mesh."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import platform
import re

from pyfoldable.core.units import normalize_quantity
from pyfoldable.geometry.hardware import CylinderEnvelope
from pyfoldable.visualization.propeller_25d import (
    PreviewBladeStation, PropellerPreviewSpec, build_propeller_preview_mesh,
)
from . import design_analysis as analysis, folding_mechanism as geometry
from .design_draft import DesignDraftArtifact
from .design_search import (
    Evaluation, GridSearchPlan, SearchAxis, SearchError, _json, _sha, run_grid_search,
)
from .geometry_clearance_policy import (
    ClearancePolicyError, NegativeClearancePolicy, decide_negative_clearance,
)
from .geometry_clearance_readiness import (
    CandidateClearanceFacts, ClearanceReadinessError, FuturePositiveQuestionV1,
    assess_positive_clearance_readiness, readiness_document,
)
from .hardware_contract import load_hardware_json

_CONSTRAINTS = ("centerline_target", "centerline_path_clearance", "station_span_complete",
                "mesh_envelope_target", "surface_path_clearance", "interblade_clearance")
_HINGE_RADIUS_LINE = re.compile(r'(?m)^radius = "[^"]+"')
_CLEARANCE_SOURCES = (
    "application/surface_clearance.py", "geometry/surface_clearance.py",
    "geometry/triangle_distance.py", "application/hardware_contract.py",
    "application/hardware_clearance.py", "geometry/hardware.py",
)
_GEOM01_UNKNOWN = "unknown_no_swept_surface_collision_model"
_POLICY_SURFACE_FAILURE = "negative_clearance_policy_relevant_violation"
_SEARCH_DETAILS_BUDGET = 256 * 1024
_PAIR_STATUSES = frozenset({"violation", "unknown", "separated"})
_CLASSIFICATIONS = frozenset({"failed", "blocked", "screening-only"})
_SURFACE_QUERY_KINDS = frozenset({"hub", "own_root_tip", "interblade"})
_HARDWARE_QUERY_KINDS = frozenset({"hardware_surface", "hardware_pair"})
_REPORT_REQUIRED_KEYS = (
    "schema_version", "request", "request_sha256", "physical_qualification",
    "classification", "modeled_surface_status", "full_propeller_clearance",
    "station_span_complete", "root_gap_m", "tip_gap_m", "excluded_regions",
    "original_triangle_count", "retained_triangle_count", "node_comparisons",
    "feature_tests", "queries", "hardware_queries", "hardware_status",
    "limitations",
)
_EXCLUDED_REGION_REQUIRED_KEYS = (
    "root_radial_width_m", "hinge_half_width_m", "source", "status", "scope",
)


@dataclass(frozen=True)
class GeometrySearchRequest:
    draft: DesignDraftArtifact
    plan: GridSearchPlan
    request_sha256: str
    context_json: str
    clearance_inputs: object | None = None
    hardware_json: bytes | None = None
    clearance_policy: NegativeClearancePolicy | None = None
    readiness_question: FuturePositiveQuestionV1 | None = None


def _clearance_module():
    # Late import: surface_clearance already imports geometry_search._inputs.
    from . import surface_clearance
    return surface_clearance


def _draft_with_hinge_radius(draft: DesignDraftArtifact, hinge_radius_m: float) -> DesignDraftArtifact:
    """Rewrite only the [hinge] radius so clearance sees this candidate's geometry."""
    if not math.isfinite(hinge_radius_m) or hinge_radius_m <= 0:
        raise SearchError("Candidate hinge radius must be a positive finite length.")
    start = draft.toml.find("[hinge]")
    if start < 0:
        raise SearchError("Candidate draft is missing a hinge table.")
    nxt = draft.toml.find("\n[", start + 1)
    section = draft.toml[start:] if nxt < 0 else draft.toml[start:nxt]
    updated, count = _HINGE_RADIUS_LINE.subn(f'radius = "{hinge_radius_m:.17g} m"', section, count=1)
    if count != 1:
        raise SearchError("Candidate draft is missing a hinge radius.")
    text = draft.toml[:start] + updated + ("" if nxt < 0 else draft.toml[nxt:])
    return DesignDraftArtifact(draft.filename, text, draft.source_sha256,
                               hashlib.sha256(text.encode("utf-8")).hexdigest())


def _classify_scoped_geom04(report):
    """Evidence label only; never a GEOM-01 constraint value."""
    if not report:
        return "unknown_scoped_geom04"
    statuses = []
    modeled = report.get("modeled_surface_status")
    if modeled is not None:
        statuses.append(modeled)
    hardware = report.get("hardware_status")
    if hardware is not None:
        statuses.append(hardware)
    for query in report.get("queries") or []:
        statuses.append((query.get("result") or {}).get("status"))
    if "violation" in statuses:
        return "scoped_geom04_violation"
    if statuses and all(status == "separated" for status in statuses):
        return "scoped_geom04_separated"
    return "unknown_scoped_geom04"


def _static_hardware_binding(blade, hardware_json):
    """Request-level hardware checks that do not depend on a grid hinge radius."""
    if hardware_json is None:
        return None
    try:
        hardware = load_hardware_json(hardware_json)
    except ValueError as exc:
        raise SearchError(str(exc)) from exc
    finite_hubs = []
    for body in hardware.bodies:
        if body.binding != "hub" and int(body.binding.split("_")[1]) > blade.blade_count:
            raise SearchError("Hardware binding refers to a blade outside the active design.")
        if isinstance(body.solid, CylinderEnvelope):
            finite_hubs.append(body)
            if abs(body.solid.radius_m - blade.hub_radius_m) > 1e-12:
                raise SearchError("Declared finite hub radius must match the active design hub radius.")
            rotation, translation = body.rotation, body.translation_m
            if max(abs(translation[0]), abs(translation[1]), abs(rotation[0][2]),
                   abs(rotation[1][2]), abs(rotation[2][0]), abs(rotation[2][1])) > 1e-12:
                raise SearchError("Finite hub axis must coincide with the active rotor z axis.")
    if len(finite_hubs) > 1:
        raise SearchError("At most one declared finite hub is supported.")
    return hardware


def _geom04_namespace(*, execution_status, hinge_radius_m, end_angle_deg, reason=None,
                      clearance_request=None, artifact=None, report=None, error=None):
    return {
        "execution_status": execution_status,
        "candidate_hinge_radius_m": hinge_radius_m,
        "clearance_end_angle_deg": end_angle_deg,
        "clearance_request_sha256": None if clearance_request is None else clearance_request.request_sha256,
        "artifact_request_sha256": None if artifact is None else artifact.request_sha256,
        "artifact_report_sha256": None if artifact is None else artifact.report_sha256,
        "report": report,
        "failure_reason": reason,
        "candidate_validation_error": error,
        "scoped_geom04_status": _classify_scoped_geom04(report),
    }


def _details_size(details):
    return len(_json(dict(details)).encode())


def _reject_json_constant(token):
    raise ValueError(f"non-standard JSON number {token}")


def _schema_error():
    raise SearchError("Candidate clearance report schema is invalid.")


def _accounting_error():
    raise SearchError("Candidate clearance accounting is internally inconsistent.")


def _nonneg_int(value):
    if type(value) is not int or value < 0:
        _accounting_error()
    return value


def _schema_nonneg_int(value):
    if type(value) is not int or value < 0:
        _schema_error()
    return value


def _finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        _schema_error()
    return value


def _optional_finite_number(value):
    if value is None:
        return None
    return _finite_number(value)


def _optional_point(value):
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        _schema_error()
    for coordinate in value:
        _finite_number(coordinate)
    return value


def _assert_finite_json(value):
    pending = [value]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
        elif isinstance(node, bool) or node is None or isinstance(node, str):
            continue
        elif isinstance(node, (int, float)):
            if not math.isfinite(node):
                raise SearchError("Candidate clearance report contains non-finite numbers.")
        else:
            _schema_error()


def _assert_clearance_interval(interval):
    if not isinstance(interval, dict):
        _schema_error()
    required = (
        "angle_min_rad", "angle_max_rad", "status", "lower_bound_m",
        "witness_clearance_m", "witness_angle_rad", "method",
        "contact_status", "point_a", "point_b",
    )
    if any(key not in interval for key in required):
        _schema_error()
    _finite_number(interval["angle_min_rad"])
    _finite_number(interval["angle_max_rad"])
    if interval["status"] not in _PAIR_STATUSES:
        _schema_error()
    _optional_finite_number(interval["lower_bound_m"])
    _optional_finite_number(interval["witness_clearance_m"])
    _optional_finite_number(interval["witness_angle_rad"])
    if not isinstance(interval["method"], str):
        _schema_error()
    if not isinstance(interval["contact_status"], str):
        _schema_error()
    _optional_point(interval["point_a"])
    _optional_point(interval["point_b"])


def _assert_clearance_query(query):
    if not isinstance(query, dict):
        _schema_error()
    kind = query.get("kind")
    if kind not in _SURFACE_QUERY_KINDS and kind not in _HARDWARE_QUERY_KINDS:
        _schema_error()
    if not isinstance(query.get("a"), str) or not isinstance(query.get("b"), str):
        _schema_error()
    result = query.get("result")
    if not isinstance(result, dict):
        _schema_error()
    required = (
        "status", "lower_bound_m", "witness_clearance_m", "intervals",
        "reason", "contact_status",
    )
    if any(key not in result for key in required):
        _schema_error()
    if result["status"] not in _PAIR_STATUSES:
        _schema_error()
    _optional_finite_number(result["lower_bound_m"])
    _optional_finite_number(result["witness_clearance_m"])
    if not isinstance(result["reason"], str):
        _schema_error()
    if not isinstance(result["contact_status"], str):
        _schema_error()
    intervals = result["intervals"]
    if not isinstance(intervals, list):
        _schema_error()
    for interval in intervals:
        _assert_clearance_interval(interval)
    if kind in _SURFACE_QUERY_KINDS:
        if "node_comparisons" not in result or "feature_tests" not in result:
            _schema_error()
    else:
        if "hardware_queries" not in result:
            _schema_error()


def _assert_clearance_report_schema(report):
    if any(key not in report for key in _REPORT_REQUIRED_KEYS):
        _schema_error()
    if type(report["schema_version"]) is not int:
        _schema_error()
    if not isinstance(report["request"], dict) or not isinstance(report["request_sha256"], str):
        _schema_error()
    if type(report["physical_qualification"]) is not bool:
        _schema_error()
    if report["classification"] not in _CLASSIFICATIONS:
        _schema_error()
    if report["modeled_surface_status"] not in _PAIR_STATUSES:
        _schema_error()
    if type(report["station_span_complete"]) is not bool:
        _schema_error()
    _finite_number(report["root_gap_m"])
    _finite_number(report["tip_gap_m"])
    excluded = report["excluded_regions"]
    if not isinstance(excluded, dict) or any(key not in excluded for key in _EXCLUDED_REGION_REQUIRED_KEYS):
        _schema_error()
    _finite_number(excluded["root_radial_width_m"])
    _finite_number(excluded["hinge_half_width_m"])
    if not isinstance(excluded["source"], str) or not isinstance(excluded["scope"], str):
        _schema_error()
    if excluded["status"] != "not_evaluated":
        _schema_error()
    _schema_nonneg_int(report["original_triangle_count"])
    _schema_nonneg_int(report["retained_triangle_count"])
    if not isinstance(report["queries"], list):
        _schema_error()
    for query in report["queries"]:
        _assert_clearance_query(query)
    if report["hardware_status"] is not None and report["hardware_status"] not in _PAIR_STATUSES:
        _schema_error()
    limitations = report["limitations"]
    if not isinstance(limitations, list) or any(not isinstance(item, str) for item in limitations):
        _schema_error()
    _assert_finite_json(report)


def _assert_clearance_report_request(report, clearance_request, *, hinge_radius_m, end_angle_deg):
    if report.get("request_sha256") != clearance_request.request_sha256:
        raise SearchError("Candidate clearance artifact identity mismatch.")
    request_context = json.loads(clearance_request.context_json)
    if report.get("request") != request_context:
        raise SearchError("Candidate clearance artifact identity mismatch.")
    inputs = request_context.get("inputs") or {}
    if inputs.get("end_angle_deg") != end_angle_deg:
        raise SearchError("Candidate clearance artifact identity mismatch.")
    if request_context.get("draft_sha256") != clearance_request.draft.draft_sha256:
        raise SearchError("Candidate clearance artifact identity mismatch.")
    if request_context.get("draft_toml") != clearance_request.draft.toml:
        raise SearchError("Candidate clearance artifact identity mismatch.")
    model, _, _ = _inputs(clearance_request.draft)
    if abs(model.hinge.radius_m - hinge_radius_m) > 1e-12:
        raise SearchError("Candidate clearance artifact identity mismatch.")
    if inputs.get("max_node_comparisons") != clearance_request.inputs.max_node_comparisons:
        raise SearchError("Candidate clearance artifact identity mismatch.")
    if inputs.get("max_feature_tests") != clearance_request.inputs.max_feature_tests:
        raise SearchError("Candidate clearance artifact identity mismatch.")
    if inputs.get("max_hardware_queries") != clearance_request.inputs.max_hardware_queries:
        raise SearchError("Candidate clearance artifact identity mismatch.")


def _assert_qualification_invariants(report):
    if report.get("full_propeller_clearance") is not None:
        raise SearchError("Candidate clearance report violates qualification invariants.")
    pending = [report]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            if "physical_qualification" in node and node["physical_qualification"] is not False:
                raise SearchError("Candidate clearance report violates qualification invariants.")
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)


def _query_usage(result, key):
    if key not in result:
        return 0
    return _nonneg_int(result[key])


def _assert_candidate_accounting(report, inputs):
    ceilings = {
        "node_comparisons": inputs.max_node_comparisons,
        "feature_tests": inputs.max_feature_tests,
        "hardware_queries": inputs.max_hardware_queries,
    }
    totals = {key: _nonneg_int(report.get(key)) for key in ceilings}
    for key, used in totals.items():
        if used > ceilings[key]:
            raise SearchError("Candidate clearance accounting exceeds configured ceilings.")
    ledger = dict.fromkeys(ceilings, 0)
    for query in report["queries"]:
        kind, result = query["kind"], query["result"]
        if kind in _SURFACE_QUERY_KINDS:
            node, features = _query_usage(result, "node_comparisons"), _query_usage(result, "feature_tests")
            if node > ceilings["node_comparisons"] or features > ceilings["feature_tests"]:
                raise SearchError("Candidate clearance accounting exceeds configured ceilings.")
            if _query_usage(result, "hardware_queries"):
                _accounting_error()
            ledger["node_comparisons"] += node
            ledger["feature_tests"] += features
        else:
            used = _query_usage(result, "hardware_queries")
            if used > ceilings["hardware_queries"]:
                raise SearchError("Candidate clearance accounting exceeds configured ceilings.")
            if _query_usage(result, "node_comparisons") or _query_usage(result, "feature_tests"):
                _accounting_error()
            ledger["hardware_queries"] += used
    if ledger != totals:
        _accounting_error()
    for key, used in ledger.items():
        if used > ceilings[key]:
            raise SearchError("Candidate clearance accounting exceeds configured ceilings.")


def _policy_gate(decision):
    return {
        "value": decision.value,
        "reason": decision.reason,
        "query_index": decision.query_index,
        "interval_index": decision.interval_index,
    }


def _record_negative_policy(policy, details, constraints, evidence, report):
    """Apply v1 only to the evidence state that will remain in the details."""
    if policy is None:
        return
    if evidence is None:
        status = "no_evidence"
        accepted = None
    elif evidence["execution_status"] == "completed":
        status = "completed"
        accepted = report
    elif evidence["execution_status"] == "candidate_validation_failed":
        status = "candidate_validation_failed"
        accepted = None
    elif evidence["execution_status"] == "evidence_attachment_exceeds_search_details_budget":
        status = "evidence_unavailable_oversize"
        accepted = None
    else:
        raise SearchError("Candidate clearance policy rejected the evidence state.")
    try:
        decision = decide_negative_clearance(policy, accepted, evidence_status=status)
    except ClearancePolicyError as exc:
        raise SearchError("Candidate clearance policy rejected the evidence.") from exc
    if (decision.surface_path_clearance.value is True
            or decision.interblade_clearance.value is True):
        raise SearchError("Negative clearance policy cannot promote a gate to true.")
    details["geom04_negative_clearance_policy"] = {
        "policy_id": decision.policy_id,
        "surface_path_clearance": _policy_gate(decision.surface_path_clearance),
        "interblade_clearance": _policy_gate(decision.interblade_clearance),
    }
    constraints["surface_path_clearance"] = decision.surface_path_clearance.value
    constraints["interblade_clearance"] = decision.interblade_clearance.value
    if constraints["surface_path_clearance"] is False:
        details["surface_path_clearance_status"] = _POLICY_SURFACE_FAILURE
    else:
        details["surface_path_clearance_status"] = _GEOM01_UNKNOWN


def _json_contains_bool(value):
    pending = [value]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
        elif isinstance(node, bool):
            return True
    return False


def _attach_positive_readiness(request, details, constraints, blade, hinge_radius_m, end_angle_deg):
    """Diagnose the final evidence state without changing constraints or reports."""
    if request.readiness_question is None:
        return
    saved_constraints = dict(constraints)
    evidence = details.get("geom04_clearance")
    if evidence is None:
        status, report = "no_evidence", None
    else:
        execution = evidence.get("execution_status")
        if execution == "completed":
            status, report = "completed", evidence.get("report")
        elif execution == "candidate_validation_failed":
            status, report = "candidate_validation_failed", None
        elif execution == "evidence_attachment_exceeds_search_details_budget":
            status, report = "evidence_unavailable_oversize", None
        else:
            raise SearchError("Candidate clearance readiness rejected the evidence state.")
    radius = blade.diameter_m / 2.0
    exclusions = request.clearance_inputs
    report_token = None if report is None else _json(report)
    try:
        readiness = assess_positive_clearance_readiness(
            request.readiness_question,
            evidence_status=status,
            report=report,
            candidate=CandidateClearanceFacts(
                blade_count=blade.blade_count,
                end_angle_deg=end_angle_deg,
                hub_radius_m=blade.hub_radius_m,
                hinge_radius_m=hinge_radius_m,
                tip_radius_m=radius,
                first_station_radius_m=blade.stations[0].r_over_R * radius,
                last_station_radius_m=blade.stations[-1].r_over_R * radius,
                root_exclusion_width_m=None if exclusions is None else exclusions.root_attachment_m,
                hinge_exclusion_width_m=None if exclusions is None else exclusions.hinge_attachment_m,
            ),
        )
    except ClearanceReadinessError as exc:
        raise SearchError("Candidate clearance readiness rejected the evidence.") from exc
    except ArithmeticError as exc:
        raise SearchError("Candidate clearance readiness rejected the evidence.") from exc
    if report is not None and _json(report) != report_token:
        raise SearchError("Candidate clearance readiness rejected the evidence.")
    document = readiness_document(readiness)
    if _json_contains_bool(document):
        raise SearchError("Candidate clearance readiness rejected the evidence.")
    details["geom04_positive_clearance_readiness"] = document
    if _details_size(details) > _SEARCH_DETAILS_BUDGET:
        del details["geom04_positive_clearance_readiness"]
    if constraints != saved_constraints:
        raise SearchError("Candidate clearance readiness rejected the evidence.")


def _accept_bound_clearance_report(artifact, clearance_request, inputs, *, hinge_radius_m, end_angle_deg):
    """Identity, digest, schema, qualification and accounting, without mutating the report."""
    if artifact.request_sha256 != clearance_request.request_sha256:
        raise SearchError("Candidate clearance artifact identity mismatch.")
    if hashlib.sha256(artifact.report_json.encode("utf-8")).hexdigest() != artifact.report_sha256:
        raise SearchError("Candidate clearance artifact identity mismatch.")
    try:
        report = json.loads(artifact.report_json, parse_constant=_reject_json_constant)
    except ValueError as exc:
        raise SearchError("Candidate clearance report is not strict finite JSON.") from exc
    if not isinstance(report, dict):
        raise SearchError("Candidate clearance report schema is invalid.")
    _assert_clearance_report_schema(report)
    _assert_clearance_report_request(
        report, clearance_request, hinge_radius_m=hinge_radius_m, end_angle_deg=end_angle_deg)
    _assert_qualification_invariants(report)
    _assert_candidate_accounting(report, inputs)
    return report


def _inputs(draft):
    model, _ = analysis._load_geometry(draft)
    hinge = model.hinge
    if (hinge is None or not math.isclose(hinge.axis_elevation_rad, math.pi / 2, abs_tol=1e-12, rel_tol=0)
            or any(value != 0 for value in (hinge.axial_offset_m, hinge.tangential_offset_m,
                                            hinge.deployed_angle_rad, hinge.stop_angle_rad))
            or not -math.pi <= hinge.stowed_angle_rad < 0):
        raise SearchError("Geometry search requires the zero-offset planar +z hinge with radial open state.")
    if "stowed_envelope_requirement" not in model.metadata:
        raise SearchError("A source-bound stowed envelope requirement is required.")
    target = normalize_quantity(model.metadata["stowed_envelope_requirement"], "length").si_value
    if not math.isfinite(target) or target <= 0:
        raise SearchError("Stowed envelope requirement must be positive and finite.")
    ids = {station.airfoil_id for station in model.blade.stations}
    if len(ids) != 1 or len(model.blade.stations) > 64:
        raise SearchError("Geometry search supports a single profile and at most 64 stations.")
    foil = next(foil for foil in model.airfoils if foil.id in ids)
    if not foil.coordinates or len(foil.coordinates) > 601:
        raise SearchError("Geometry search requires 1–601 explicit source-bound profile coordinates.")
    return model, target, foil


def prepare_geometry_search(
    draft: DesignDraftArtifact, *, hinge_radii_m: tuple[float, ...],
    stowed_angles_deg: tuple[float, ...], max_evaluations: int = 25,
    clearance_inputs=None, hardware_json: bytes | None = None,
    clearance_policy: NegativeClearancePolicy | None = None,
    readiness_question: FuturePositiveQuestionV1 | None = None,
) -> GeometrySearchRequest:
    """Validate budgets and source identity without generating candidate meshes."""
    model, target, foil = _inputs(draft)
    if type(max_evaluations) is not int or not 1 <= max_evaluations <= 25:
        raise SearchError("Geometry evaluation budget must be an integer from 1 to 25.")
    if hardware_json is not None and clearance_inputs is None:
        raise SearchError("Hardware cannot bind without clearance inputs.")
    blade = model.blade
    radius = blade.diameter_m / 2
    plan = GridSearchPlan((
        SearchAxis("hinge_radius_m", hinge_radii_m, blade.hub_radius_m, radius),
        SearchAxis("stowed_angle_deg", stowed_angles_deg, math.degrees(model.hinge.stowed_angle_rad), 0.),
    ), max_evaluations, _CONSTRAINTS)
    hinges = next(axis.values for axis in plan.axes if axis.name == "hinge_radius_m")
    if any(not blade.hub_radius_m < h < radius for h in hinges):
        raise SearchError("Hinge positions must lie strictly between hub and tip.")
    count = math.prod(len(axis.values) for axis in plan.axes)
    vertex_budget = count * (len(blade.stations) + 2) * len(foil.coordinates) * blade.blade_count
    if vertex_budget > 250_000 or blade.blade_count > 8:
        raise SearchError("Aggregate preview budget is 250000 vertices and at most eight blades.")
    binding = None
    if clearance_inputs is not None:
        clearance = _clearance_module()
        if not isinstance(clearance_inputs, clearance.SurfaceClearanceInputs):
            raise SearchError("Expected explicit surface-clearance inputs.")
        clearance.SurfaceClearanceInputs(**asdict(clearance_inputs))
        hardware = _static_hardware_binding(blade, hardware_json)
        binding = {
            "inputs": asdict(clearance_inputs),
            "hardware_raw_sha256": None if hardware is None else hardware.raw_sha256,
            "hardware_canonical_sha256": None if hardware is None else hardware.canonical_sha256,
            "physical_qualification": False,
            "full_propeller_clearance": None,
            "reuse_policy": "rebuild_draft_and_request_per_candidate_never_reuse_foreign_geometry",
            "end_angle_policy": "candidate_stowed_angle_within_declared_travel",
            "selection_effect": (
                "negative_policy_may_set_clearance_constraints_false_never_true"
                if isinstance(clearance_policy, NegativeClearancePolicy) and clearance_policy.enabled
                else "evidence_only_does_not_alter_geom01_constraints"
            ),
            "budget_policy": "per_candidate_configured_limits_not_shared_grid_remainder",
            "per_candidate_max_node_comparisons": clearance_inputs.max_node_comparisons,
            "per_candidate_max_feature_tests": clearance_inputs.max_feature_tests,
            "per_candidate_max_hardware_queries": clearance_inputs.max_hardware_queries,
            "aggregate_node_comparison_ceiling": count * clearance_inputs.max_node_comparisons,
            "aggregate_feature_test_ceiling": count * clearance_inputs.max_feature_tests,
            "aggregate_hardware_query_ceiling": count * clearance_inputs.max_hardware_queries,
        }
    root = Path(__file__).parents[1]
    sources = ("application/geometry_search.py", "application/folding_mechanism.py",
               "application/design_search.py", "application/design_analysis.py",
               "visualization/propeller_25d.py", "core/airfoil.py", "core/models.py", "core/config.py", "core/units.py")
    if binding is not None:
        sources += _CLEARANCE_SOURCES
    if clearance_policy is not None:
        if not isinstance(clearance_policy, NegativeClearancePolicy):
            raise SearchError("Expected an explicit negative-clearance policy.")
        sources += ("application/geometry_clearance_policy.py",)
    if readiness_question is not None:
        if not isinstance(readiness_question, FuturePositiveQuestionV1):
            raise SearchError("Expected an explicit positive-clearance readiness question.")
        sources += ("application/geometry_clearance_readiness.py",)
    context = {
        "schema_version": 1, "classification": "geometry_feasibility_screening_only",
        "base_draft_toml": draft.toml, "base_draft_sha256": draft.draft_sha256,
        "source_sha256": draft.source_sha256, "plan": asdict(plan),
        "stowed_requirement_m": target,
        "topology": "single_rigid_tip_planar_z_hinge",
        "proposed_angle_semantics": "alternative_stowed_endpoint_within_existing_travel_not_current_measured_state",
        "objective": "selected_endpoint_centerline_envelope_m_minimize",
        "full_180_centerline_lower_bound_m": radius + blade.hub_radius_m,
        "full_180_target_necessary_condition_met": target >= radius + blade.hub_radius_m,
        "full_180_bound_scope": "any_hinge_position_with_centerline_hub_nonpenetration_not_surface_clearance",
        "maximum_generated_vertices": vertex_budget,
        "implementation_sha256": {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in sources},
        "python": platform.python_version(),
    }
    if binding is not None:
        context["candidate_clearance"] = binding
    if clearance_policy is not None:
        context["negative_clearance_policy"] = clearance_policy.declaration()
    if readiness_question is not None:
        context["positive_clearance_readiness"] = readiness_question.declaration()
    text = _json(context)
    return GeometrySearchRequest(
        draft, plan, _sha(text), text, clearance_inputs, hardware_json, clearance_policy,
        readiness_question)


def run_geometry_search(request: GeometrySearchRequest) -> analysis.DesignAnalysisArtifact:
    """Compare proposed hinge/stowed endpoints; unknown surface constraints block selection.

    Optional GEOM-04 binding attaches candidate-specific evidence only. An
    explicit negative-clearance policy may then set either surface gate to
    False, or leave it None. This policy never sets either gate to True.
    An optional readiness question is diagnostic only and does not assign
    either gate.
    """
    if not isinstance(request, GeometrySearchRequest) or not isinstance(request.plan, GridSearchPlan):
        raise SearchError("Expected a prepared geometry grid.")
    axes = {axis.name: axis.values for axis in request.plan.axes}
    if set(axes) != {"hinge_radius_m", "stowed_angle_deg"}:
        raise SearchError("Geometry grid axes do not match the prepared contract.")
    fresh = prepare_geometry_search(request.draft, hinge_radii_m=axes["hinge_radius_m"],
        stowed_angles_deg=axes["stowed_angle_deg"], max_evaluations=request.plan.max_evaluations,
        clearance_inputs=request.clearance_inputs, hardware_json=request.hardware_json,
        clearance_policy=request.clearance_policy, readiness_question=request.readiness_question)
    if fresh != request:
        raise SearchError("Geometry request identity changed.")
    model, target, foil = _inputs(request.draft)
    blade = model.blade
    stations = tuple(PreviewBladeStation(s.r_over_R, s.chord_m, math.degrees(s.twist_rad)) for s in blade.stations)
    clearance = None if request.clearance_inputs is None else _clearance_module()

    def evaluate(parameters):
        h, angle = parameters["hinge_radius_m"], parameters["stowed_angle_deg"]
        audit = geometry.build_mechanism_geometry_audit(
            geometry.MechanismGeometryInputs(blade.diameter_m, blade.hub_radius_m, h, angle, target),
            tuple(s.r_over_R for s in blade.stations))
        mesh = None
        mesh_error = None
        try:
            mesh = build_propeller_preview_mesh(PropellerPreviewSpec(
                blade.diameter_m, blade.hub_radius_m, blade.blade_count, h, angle,
                airfoil_id=foil.id, airfoil_definition=foil), stations)
        except (ValueError, ArithmeticError) as exc:
            mesh_error = str(exc)[:1024]
        mesh_diameter = None if mesh is None else 2 * mesh.mesh_envelope_radius_m
        # On 0..-180 degrees every point of the moving radial centreline has
        # nonincreasing distance to the origin. Its path minimum is at the endpoint.
        path_clearance = audit.hub_centerline_clearance_m
        constraints = {
            "centerline_target": audit.current_envelope_requirement_met,
            "centerline_path_clearance": path_clearance > 0.0,
            "station_span_complete": audit.station_span_complete,
            "mesh_envelope_target": None if mesh is None else mesh_diameter <= target,
            "surface_path_clearance": None, "interblade_clearance": None,
        }
        details = {
            "audit": asdict(audit), "proposed_path_minimum_hub_clearance_m": path_clearance,
            "proposed_path_angle_interval_deg": [angle, 0.0],
            "full_180_path_hub_clearance_m": audit.full_stow_path_hub_clearance_m,
            "mesh_envelope_diameter_m": mesh_diameter, "mesh_error": mesh_error,
            "mesh_qualification": None if mesh is None else mesh.qualification,
            "airfoil_coordinate_sha256": None if mesh is None else mesh.airfoil_coordinate_sha256,
            "canonical_design_modified": False,
            "surface_path_clearance_status": _GEOM01_UNKNOWN,
            "full_propeller_clearance": None,
            "physical_qualification": False,
        }
        if clearance is not None:
            candidate_inputs = replace(request.clearance_inputs, end_angle_deg=angle)
            candidate_draft = _draft_with_hinge_radius(request.draft, h)
            clearance_request = artifact = report = None
            try:
                # Narrow candidate-validation boundary: exclusions/hardware vs this hinge.
                clearance_request = clearance.prepare_surface_clearance(
                    candidate_draft, candidate_inputs,
                    hardware_json=request.hardware_json)
            except clearance.SurfaceClearanceValidationError as exc:
                evidence = _geom04_namespace(
                    execution_status="candidate_validation_failed",
                    hinge_radius_m=h, end_angle_deg=angle,
                    reason="unknown_candidate_clearance_unresolved",
                    error=str(exc)[:1024])
            except ArithmeticError as exc:
                raise SearchError("Candidate clearance preparation failed.") from exc
            else:
                try:
                    artifact = clearance.run_surface_clearance(clearance_request)
                except ArithmeticError as exc:
                    raise SearchError("Candidate clearance execution failed.") from exc
                report = _accept_bound_clearance_report(
                    artifact, clearance_request, candidate_inputs,
                    hinge_radius_m=h, end_angle_deg=angle)
                evidence = _geom04_namespace(
                    execution_status="completed",
                    hinge_radius_m=h, end_angle_deg=angle,
                    clearance_request=clearance_request, artifact=artifact, report=report)
            details["geom04_clearance"] = evidence
            _record_negative_policy(request.clearance_policy, details, constraints, evidence, report)
            if _details_size(details) > _SEARCH_DETAILS_BUDGET:
                details["geom04_clearance"] = _geom04_namespace(
                    execution_status="evidence_attachment_exceeds_search_details_budget",
                    hinge_radius_m=h, end_angle_deg=angle,
                    reason="complete_geom04_report_exceeds_existing_256_kib_search_details_snapshot",
                    clearance_request=clearance_request, artifact=artifact)
                _record_negative_policy(
                    request.clearance_policy, details, constraints,
                    details["geom04_clearance"], None)
        elif request.clearance_policy is not None:
            _record_negative_policy(request.clearance_policy, details, constraints, None, None)
        _attach_positive_readiness(request, details, constraints, blade, h, angle)
        return Evaluation(audit.centerline_envelope_diameter_m, constraints, details)

    return run_grid_search(request.plan, evaluate, evaluator_identity={
        "id": "geom01_planar_hinge_stow_v1", "geometry_request_sha256": request.request_sha256,
        "geometry_context": json.loads(request.context_json),
    })
