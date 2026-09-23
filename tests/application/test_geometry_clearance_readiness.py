"""GEOM-01 positive-clearance readiness v1 is diagnostic only.

`preconditions_satisfied` means the accepted evidence meets this question's
proof prerequisites. It is not a clearance constraint and it is not True.
One-blade interblade applicability is decided before evidence availability.
"""
from dataclasses import asdict, replace
import copy
import hashlib
import inspect
import json
import math
import re

import pytest

from pyfoldable.application.design_analysis import _load_geometry
from pyfoldable.application.design_search import SearchError, _json
from pyfoldable.application.folding_mechanism import (
    MechanismGeometryInputs,
    build_mechanism_geometry_audit,
)
from pyfoldable.application.geometry_clearance_policy import NegativeClearancePolicy
from pyfoldable.application.geometry_clearance_readiness import (
    DIAGNOSTIC_ID,
    DIMENSIONS,
    EFFECT,
    HUB_NOMINAL_CONTAINMENT,
    HUB_NOT_ESTABLISHED,
    MODEL_SCOPE,
    MOTION_DOMAIN,
    CandidateClearanceFacts,
    ClearanceReadinessError,
    FuturePositiveQuestionV1,
    assess_positive_clearance_readiness,
    readiness_document,
)
from pyfoldable.application.geometry_search import prepare_geometry_search, run_geometry_search
from pyfoldable.application.hardware_clearance import MotionShape, query_motion_pair
from pyfoldable.application.surface_clearance import (
    SurfaceClearanceInputs,
    SurfaceClearanceValidationError,
    prepare_surface_clearance,
    run_surface_clearance,
)
from pyfoldable.geometry.hardware import finite_cylinder
from pyfoldable.geometry.surface_clearance import (
    ClearanceControls,
    SurfacePart,
    hub_clearance,
    pair_clearance,
)
from test_geometry_search import _bound_report_artifact, _complete_span_draft
from test_polar_upload import draft


_THRESHOLD = 0.0005
_ANGLE = -10.0
_BANNED = (
    "gate_value", "feasible", "selectable", "certified", "qualified",
    "collision-free", "collision_free",
)


def _question(**changes):
    values = {"required_clearance_m": _THRESHOLD}
    values.update(changes)
    return FuturePositiveQuestionV1(**values)


def _facts(**changes):
    values = dict(
        blade_count=2,
        end_angle_deg=_ANGLE,
        hub_radius_m=0.018,
        hinge_radius_m=0.1,
        tip_radius_m=0.125,
        first_station_radius_m=0.018,
        last_station_radius_m=0.125,
        root_exclusion_width_m=0.0,
        hinge_exclusion_width_m=0.0,
    )
    values.update(changes)
    return CandidateClearanceFacts(**values)


def _path(angle=_ANGLE):
    return math.radians(float(angle)), 0.0


def _interval(status="separated", *, lower=0.02, lo=None, hi=0.0, method="aabb_bound",
              contact=None, **extra):
    if lo is None:
        lo = _path()[0]
    if contact is None:
        contact = "separated" if status == "separated" else "unknown"
    row = {
        "angle_min_rad": lo,
        "angle_max_rad": hi,
        "status": status,
        "lower_bound_m": lower if status == "separated" else None,
        "witness_clearance_m": None,
        "witness_angle_rad": None,
        "method": method,
        "contact_status": contact,
        "point_a": None,
        "point_b": None,
    }
    row.update(extra)
    return row


def _result(status="separated", *, lower=0.02, intervals=None, reason=None, contact=None, **extra):
    if intervals is None:
        intervals = [_interval(status, lower=lower, contact=contact)]
    if contact is None:
        contact = "separated" if status == "separated" else "unknown"
    separated = [row["lower_bound_m"] for row in intervals if row.get("status") == "separated"]
    query_lower = None
    if status == "separated" and separated and all(
            value is not None and not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) for value in separated):
        query_lower = min(separated)
    document = {
        "status": status,
        "lower_bound_m": query_lower,
        "witness_clearance_m": None,
        "intervals": intervals,
        "reason": reason if reason is not None else status,
        "contact_status": contact,
        "node_comparisons": 0,
        "feature_tests": 0,
    }
    document.update(extra)
    return document


def _query(kind, a, b, result):
    return {"kind": kind, "a": a, "b": b, "result": result}


def _surface_name(blade, part):
    return f"blade_{blade}_{part}"


def _own_queries(blade_count, result):
    return [
        _query("own_root_tip", _surface_name(blade, "root"), _surface_name(blade, "tip"), copy.deepcopy(result))
        for blade in range(1, blade_count + 1)
    ]


def _interblade_queries(blade_count, result):
    rows = []
    parts = [(blade, part) for blade in range(1, blade_count + 1) for part in ("root", "tip")]
    for index, left in enumerate(parts):
        for right in parts[index + 1:]:
            if left[0] == right[0]:
                continue
            rows.append(_query(
                "interblade", _surface_name(*left), _surface_name(*right), copy.deepcopy(result)))
    return rows


def _hub_queries(blade_count, result, *, hardware_name=None):
    rows = []
    for blade in range(1, blade_count + 1):
        for part in ("root", "tip"):
            if hardware_name is None:
                rows.append(_query("hub", _surface_name(blade, part), "hub_envelope", copy.deepcopy(result)))
            else:
                rows.append(_query(
                    "hardware_surface", _surface_name(blade, part), hardware_name, copy.deepcopy(result)))
    return rows


def _ledger(blade_count=2, result=None, *, hardware_name=None, extra=()):
    separated = result if result is not None else _result()
    return (
        _hub_queries(blade_count, separated, hardware_name=hardware_name)
        + _own_queries(blade_count, separated)
        + _interblade_queries(blade_count, separated)
        + list(extra)
    )


def _report(queries, facts=None, **changes):
    facts = facts or _facts()
    root_gap = facts.first_station_radius_m - facts.hub_radius_m
    tip_gap = facts.tip_radius_m - facts.last_station_radius_m
    root_ok = abs(root_gap) <= 8 * max(
        math.ulp(facts.first_station_radius_m), math.ulp(facts.hub_radius_m))
    tip_ok = abs(tip_gap) <= 8 * max(
        math.ulp(facts.last_station_radius_m), math.ulp(facts.tip_radius_m))
    hinge_ok = facts.first_station_radius_m < facts.hinge_radius_m < facts.last_station_radius_m
    hardware = changes.pop("hardware", None)
    mode = changes.pop(
        "hub_obstacle",
        "declared_finite_cylinder" if hardware_name_present(hardware) else "infinite_cylinder_conservative_envelope",
    )
    document = {
        "request": {
            "inputs": {
                "required_clearance_m": _THRESHOLD,
                "end_angle_deg": facts.end_angle_deg,
                "max_depth": 8,
                "max_intervals": 255,
            },
            "motion": MOTION_DOMAIN,
            "model_scope": MODEL_SCOPE,
            "hub_obstacle": mode,
            "hardware": hardware,
        },
        "queries": queries,
        "root_gap_m": root_gap,
        "tip_gap_m": tip_gap,
        "station_span_complete": root_ok and tip_ok and hinge_ok,
        "excluded_regions": {
            "root_radial_width_m": 0.0 if facts.root_exclusion_width_m is None else facts.root_exclusion_width_m,
            "hinge_half_width_m": 0.0 if facts.hinge_exclusion_width_m is None else facts.hinge_exclusion_width_m,
            "source": "synthetic readiness fixture",
            "status": "not_evaluated",
            "scope": "declared_reference_radial_bands_move_with_each_rigid_part",
        },
    }
    request_changes = changes.pop("request", None)
    document.update(changes)
    if request_changes:
        document["request"].update(request_changes)
    return document


def hardware_name_present(hardware):
    if not isinstance(hardware, dict):
        return False
    for body in hardware.get("bodies") or []:
        geometry = body.get("geometry") if isinstance(body, dict) else None
        if isinstance(geometry, dict) and geometry.get("kind") == "finite_cylinder" and body.get("binding") == "hub":
            return True
    return False


def _finite_hub_hardware(name="sleeve"):
    return {"bodies": [{"name": name, "binding": "hub", "geometry": {"kind": "finite_cylinder"}}]}


def _convex(name, binding="blade_1_root"):
    return {"name": name, "binding": binding, "geometry": {"kind": "convex_polyhedron"}}


def _assess(report, facts=None, question=None, status="completed"):
    facts = facts or _facts()
    question = question or _question()
    before = None if report is None else copy.deepcopy(report)
    result = assess_positive_clearance_readiness(
        question, evidence_status=status, report=report, candidate=facts)
    if before is not None:
        assert report == before
    document = readiness_document(result)
    _assert_diagnostic_shape(document)
    return result, document


def _codes(gate):
    return [blocker.code for blocker in gate.blockers]


def _assert_diagnostic_shape(document):
    text = json.dumps(document)
    assert ": true" not in text and ": false" not in text
    for banned in _BANNED:
        assert banned not in text
    assert document["diagnostic_id"] == DIAGNOSTIC_ID
    assert document["effect"] == EFFECT
    assert document["effect"] == "diagnostic_only_does_not_alter_geom01_constraints"
    for gate_name in ("surface_path", "interblade"):
        gate = document[gate_name]
        assert gate["assessment"] in {"preconditions_satisfied", "blocked", "not_applicable"}
        rows = gate["dimensions"]
        assert [row["name"] for row in rows] == list(DIMENSIONS)
        states = {row["state"] for row in rows}
        assert states <= {"satisfied", "blocked", "not_assessed", "not_applicable"}
        if gate["assessment"] == "preconditions_satisfied":
            assert states <= {"satisfied", "not_applicable"}
        if gate["assessment"] == "not_applicable":
            assert states == {"not_applicable"}
        if gate["assessment"] == "blocked":
            assert "blocked" in states
        assert "value" not in gate
        assert gate["assessment"] not in {True, False}


def _producer_pair(angle=_ANGLE, clearance=_THRESHOLD):
    start = math.radians(float(angle))
    left = SurfacePart("left", (((0.2, 0.0, 0.0), (0.21, 0.0, 0.0), (0.2, 0.01, 0.0)),), moving=False)
    right = SurfacePart("right", (((0.4, 0.2, 0.0), (0.41, 0.2, 0.0), (0.4, 0.21, 0.0)),), moving=False)
    return asdict(pair_clearance(
        left, right, angle_min_rad=start, angle_max_rad=0.0, clearance_m=clearance,
        controls=ClearanceControls(max_depth=4, max_intervals=16, max_node_comparisons=1000)))


def _producer_hub(angle=_ANGLE, clearance=_THRESHOLD):
    start = math.radians(float(angle))
    part = SurfacePart("blade_1_tip", (((0.2, 0.0, 0.0), (0.22, 0.0, 0.0), (0.2, 0.02, 0.0)),))
    return asdict(hub_clearance(
        part, 0.018, angle_min_rad=start, angle_max_rad=0.0, clearance_m=clearance,
        controls=ClearanceControls(max_depth=4, max_intervals=16, max_node_comparisons=1000)))


def _producer_finite_hub(angle=_ANGLE, clearance=_THRESHOLD):
    start = math.radians(float(angle))
    solid = finite_cylinder(radius_m=0.018, height_m=0.04, segments=8, approximation_tolerance_m=0.002)
    hub = MotionShape("sleeve", solid=solid)
    surface = MotionShape(
        "blade_1_root",
        triangles=(((0.08, 0.0, 0.0), (0.09, 0.0, 0.0), (0.08, 0.01, 0.0)),),
    )
    return query_motion_pair(
        surface, hub, angle_min_rad=start, angle_max_rad=0.0, clearance_m=clearance,
        max_queries=64, max_depth=4, max_intervals=16)


def _complete_span_text():
    base = draft(chord_scale=0.1)
    text, root_count = re.subn(r"r_over_R = 0\.2(?:0*)\b", "r_over_R = 0.144", base.toml)
    text, tip_count = re.subn(r"r_over_R = 0\.98(?:0*)\b", "r_over_R = 1.0", text)
    assert root_count == tip_count == 1
    return replace(base, toml=text, draft_sha256=hashlib.sha256(text.encode()).hexdigest())


def _run_report(draft_obj, **inputs):
    request = prepare_surface_clearance(draft_obj, SurfaceClearanceInputs(**inputs))
    return json.loads(run_surface_clearance(request).report_json)


def _facts_from_draft(draft_obj, angle, inputs):
    model, _ = _load_geometry(draft_obj)
    blade = model.blade
    radius = blade.diameter_m / 2.0
    return CandidateClearanceFacts(
        blade_count=blade.blade_count,
        end_angle_deg=angle,
        hub_radius_m=blade.hub_radius_m,
        hinge_radius_m=model.hinge.radius_m,
        tip_radius_m=radius,
        first_station_radius_m=blade.stations[0].r_over_R * radius,
        last_station_radius_m=blade.stations[-1].r_over_R * radius,
        root_exclusion_width_m=inputs.root_attachment_m,
        hinge_exclusion_width_m=inputs.hinge_attachment_m,
    )


def test_question_identity_is_fixed_and_rejects_invented_scopes():
    question = _question()
    declaration = question.declaration()
    assert declaration["diagnostic_id"] == "geom01_positive_readiness_v1"
    assert declaration["motion_domain"] == "synchronous_planar_rigid_tips_from_zero_to_declared_endpoint"
    assert declaration["model_scope"] == MODEL_SCOPE
    assert declaration["effect"] == "diagnostic_only_does_not_alter_geom01_constraints"
    assert declaration["hub_containment"] == HUB_NOT_ESTABLISHED
    assert set(declaration) == {
        "diagnostic_id", "required_clearance_m", "motion_domain", "model_scope",
        "hub_containment", "effect",
    }
    with pytest.raises(ClearanceReadinessError):
        _question(diagnostic_id="custom")
    with pytest.raises(ClearanceReadinessError):
        _question(motion_domain="other")
    with pytest.raises(ClearanceReadinessError):
        _question(model_scope="solid_cad")
    with pytest.raises(ClearanceReadinessError):
        _question(effect="may_set_true")
    with pytest.raises(ClearanceReadinessError):
        _question(hub_containment="measured_hardware")
    with pytest.raises(ClearanceReadinessError):
        _question(required_clearance_m=True)


def test_no_evidence_blocks_both_gates_for_two_blades():
    result, document = _assess(None, status="no_evidence")
    assert result.surface_path.assessment == "blocked"
    assert result.interblade.assessment == "blocked"
    assert _codes(result.surface_path) == ["evidence_unavailable"]
    assert _codes(result.interblade) == ["evidence_unavailable"]
    assert result.surface_path.blockers[0].evidence_detail == "absent"
    assert document["evidence_status"] == "no_evidence"
    assert "geom04" not in json.dumps(document["surface_path"]["blockers"])


def test_validation_failure_and_oversize_are_evidence_unavailable():
    failed, _ = _assess({"queries": "not-read"}, status="candidate_validation_failed")
    oversize, _ = _assess({"report_sha256": "abc"}, status="evidence_unavailable_oversize")
    assert failed.surface_path.blockers[0].evidence_detail == "candidate_validation_failed"
    assert failed.interblade.blockers[0].evidence_detail == "candidate_validation_failed"
    assert oversize.surface_path.blockers[0].evidence_detail == "oversize"
    assert oversize.interblade.assessment == "blocked"


def test_one_blade_interblade_is_not_applicable_before_evidence():
    facts = _facts(blade_count=1)
    for status in ("no_evidence", "candidate_validation_failed", "evidence_unavailable_oversize"):
        result, _ = _assess(None, facts=facts, status=status)
        assert result.interblade.assessment == "not_applicable"
        assert result.interblade.blockers == ()
        assert result.surface_path.assessment == "blocked"
        assert result.surface_path.blockers[0].code == "evidence_unavailable"


def test_threshold_mismatch_either_direction_blocks_without_abort():
    report = _report(_ledger())
    low, _ = _assess(report, question=_question(required_clearance_m=0.02))
    # 0.03 is strictly above the producer threshold 0.02. Equality is not a mismatch.
    high_report = _report(_ledger(result=_result("separated", lower=0.03)))
    high_report["request"]["inputs"]["required_clearance_m"] = 0.02
    high, _ = _assess(high_report, question=_question(required_clearance_m=_THRESHOLD))
    for result in (low, high):
        assert "threshold_mismatch" in _codes(result.surface_path)
        assert "threshold_mismatch" in _codes(result.interblade)
        assert result.surface_path.assessment == "blocked"
        assert result.interblade.assessment == "blocked"


def test_motion_mismatch_blocks_without_abort():
    report = _report(_ledger(), request={"motion": "asynchronous_tips"})
    result, _ = _assess(report)
    assert "motion_scope_mismatch" in _codes(result.surface_path)
    assert "motion_scope_mismatch" in _codes(result.interblade)


def test_candidate_endpoint_contradiction_aborts():
    report = _report(_ledger())
    with pytest.raises(ClearanceReadinessError):
        _assess(report, facts=_facts(end_angle_deg=-20.0))


def test_span_metadata_contradiction_aborts():
    report = _report(_ledger())
    report["root_gap_m"] = 1.0
    with pytest.raises(ClearanceReadinessError):
        _assess(report)


def test_station_gaps_are_separate_blockers_and_match_the_audit():
    radius = 0.125
    canonical = (0.20, 0.98)
    audit = build_mechanism_geometry_audit(
        MechanismGeometryInputs(0.25, 0.018, 0.1, _ANGLE, 0.14), canonical)
    facts = _facts(
        first_station_radius_m=canonical[0] * radius,
        last_station_radius_m=canonical[1] * radius,
    )
    report = _report(_ledger(), facts)
    assert report["root_gap_m"] == audit.root_surface_gap_m
    assert report["tip_gap_m"] == audit.tip_surface_gap_m
    assert report["station_span_complete"] is audit.station_span_complete
    result, _ = _assess(report, facts)
    assert "root_span_missing" in _codes(result.surface_path)
    assert "tip_span_missing" in _codes(result.surface_path)
    assert "root_span_missing" in _codes(result.interblade)
    assert "tip_span_missing" in _codes(result.interblade)
    assert result.interblade.assessment == "blocked"

    root_only = _facts(first_station_radius_m=canonical[0] * radius, last_station_radius_m=radius)
    root_result, _ = _assess(_report(_ledger(), root_only), root_only)
    assert "root_span_missing" in _codes(root_result.surface_path)
    assert "tip_span_missing" not in _codes(root_result.surface_path)

    tip_only = _facts(first_station_radius_m=0.018, last_station_radius_m=canonical[1] * radius)
    tip_result, _ = _assess(_report(_ledger(), tip_only), tip_only)
    assert "tip_span_missing" in _codes(tip_result.interblade)
    assert "root_span_missing" not in _codes(tip_result.interblade)


def test_eight_ulp_endpoint_coincidence_is_accepted():
    hub = 0.02
    step = math.ulp(hub)
    first = hub
    while abs((candidate := first + step) - hub) <= 8 * max(math.ulp(candidate), math.ulp(hub)):
        first = candidate
    facts = _facts(hub_radius_m=hub, first_station_radius_m=first)
    result, _ = _assess(_report(_ledger(), facts), facts)
    assert "root_span_missing" not in _codes(result.surface_path)
    beyond = first + step
    assert abs(beyond - hub) > 8 * max(math.ulp(beyond), math.ulp(hub))
    missing = _facts(hub_radius_m=hub, first_station_radius_m=beyond)
    blocked, _ = _assess(_report(_ledger(), missing), missing)
    assert "root_span_missing" in _codes(blocked.surface_path)


@pytest.mark.parametrize("field", ["root_exclusion_width_m", "hinge_exclusion_width_m"])
def test_positive_exclusion_blocks_both_gates(field):
    facts = _facts(**{field: 0.002})
    report = _report(_ledger(), facts)
    report["excluded_regions"]["source"] = "this text does not permit contact"
    result, _ = _assess(report, facts)
    regions = {blocker.region for blocker in result.surface_path.blockers if blocker.code == "excluded_region"}
    assert ("root" if "root" in field else "hinge") in regions
    assert "excluded_region" in _codes(result.interblade)
    assert result.surface_path.assessment == "blocked"
    assert result.interblade.assessment == "blocked"
    assert "shared_hinge_contact_domain_unresolved" in _codes(result.surface_path)
    assert "shared_hinge_contact_domain_unresolved" not in _codes(result.interblade)


def test_zero_width_not_evaluated_exclusion_does_not_block():
    result, _ = _assess(_report(_ledger()))
    assert "excluded_region" not in _codes(result.interblade)
    assert result.interblade.assessment == "preconditions_satisfied"


def test_missing_relevant_pairs_block_only_the_affected_gate():
    separated = _result()
    no_own = _hub_queries(2, separated) + _interblade_queries(2, separated)
    missing_own, _ = _assess(_report(no_own))
    assert "relevant_pair_missing" in _codes(missing_own.surface_path)
    assert missing_own.interblade.assessment == "preconditions_satisfied"
    no_inter = _hub_queries(2, separated) + _own_queries(2, separated)
    missing_inter, _ = _assess(_report(no_inter))
    assert "relevant_pair_missing" in _codes(missing_inter.interblade)
    assert missing_inter.interblade.assessment == "blocked"


def test_duplicate_relevant_pair_aborts():
    queries = _ledger()
    queries.append(copy.deepcopy(queries[0]))
    with pytest.raises(ClearanceReadinessError):
        _assess(_report(queries))


def test_unexpected_hub_row_and_out_of_range_blade_abort():
    hardware = _finite_hub_hardware()
    queries = _ledger(hardware_name="sleeve")
    queries.append(_query("hub", "blade_1_root", "hub_envelope", _result()))
    with pytest.raises(ClearanceReadinessError):
        _assess(_report(queries, hardware=hardware))
    out_of_range = _ledger()
    out_of_range.append(_query("interblade", "blade_1_root", "blade_3_tip", _result()))
    with pytest.raises(ClearanceReadinessError):
        _assess(_report(out_of_range))


def test_blade_shaped_hardware_names_keep_the_producer_role():
    hardware = {"bodies": [
        _convex("blade_1_root", "blade_1_root"),
        _convex("blade_1_tip", "blade_2_tip"),
    ]}
    extra = [
        _query("hardware_surface", "blade_1_root", "blade_1_root", _result(
            "unknown", intervals=[], reason="global_budget_exhausted")),
        _query("hardware_pair", "blade_1_root", "blade_1_tip", _result("violation")),
    ]
    result, _ = _assess(_report(_ledger(extra=extra), hardware=hardware))
    assert result.interblade.assessment == "preconditions_satisfied"
    assert "relevant_pair_missing" not in _codes(result.interblade)


def test_relevant_unknown_budget_precision_and_contact_block_only_that_gate():
    def with_interblade(status_result):
        queries = _hub_queries(2, _result()) + _own_queries(2, _result())
        queries.extend(_interblade_queries(2, _result())[:-1])
        queries.append(_query("interblade", "blade_1_tip", "blade_2_tip", status_result))
        return _assess(_report(queries))

    unknown, _ = with_interblade(_result("unknown", intervals=[_interval("unknown", lower=None)]))
    assert "relevant_query_unresolved" in _codes(unknown.interblade)
    assert unknown.interblade.blockers[-1].cause == "unspecified" or any(
        blocker.cause == "unspecified" for blocker in unknown.interblade.blockers)
    assert "relevant_query_unresolved" not in _codes(unknown.surface_path)

    budget, _ = with_interblade(_result(
        "unknown", intervals=[_interval("unknown", lower=None, method="node_budget_exhausted")],
        reason="node_budget_exhausted"))
    assert any(blocker.cause == "budget" for blocker in budget.interblade.blockers)

    precision, _ = with_interblade(_result(
        "unknown", intervals=[_interval("unknown", lower=None, method="precision_exhausted")],
        reason="precision_exhausted"))
    assert any(blocker.cause == "precision" for blocker in precision.interblade.blockers)

    contact, _ = with_interblade(_result(
        "unknown", intervals=[_interval("unknown", lower=None, contact="intersecting")],
        contact="intersecting"))
    assert any(blocker.cause == "contact" for blocker in contact.interblade.blockers)


def test_irrelevant_exhaustion_does_not_block_a_complete_interblade_gate():
    hardware = {"bodies": [_convex("mount", "blade_1_root"), _convex("fairing", "blade_2_root")]}
    extra = [_query(
        "hardware_surface", "blade_1_root", "mount",
        _result("unknown", intervals=[], reason="global_budget_exhausted")),
        _query("hardware_pair", "mount", "fairing", _result("violation"))]
    result, _ = _assess(_report(_ledger(extra=extra), hardware=hardware))
    assert result.interblade.assessment == "preconditions_satisfied"
    assert "relevant_query_unresolved" not in _codes(result.interblade)


def test_empty_global_budget_ledger_is_not_success():
    empty = _result("unknown", intervals=[], reason="global_budget_exhausted")
    result, _ = _assess(_report(_ledger(result=empty)))
    assert result.interblade.assessment == "blocked"
    assert "relevant_query_unresolved" in _codes(result.interblade)
    assert "angular_coverage_incomplete" in _codes(result.interblade)
    assert any(blocker.cause == "budget" for blocker in result.interblade.blockers)
    assert result.interblade.assessment != "preconditions_satisfied"


def test_angular_gap_blocks_unknown_and_aborts_separated_claim():
    start, _ = _path()
    mid = (start + 0.0) / 2.0
    gap = math.nextafter(mid, 0.0)
    unknown_rows = [
        _interval("unknown", lower=None, lo=start, hi=mid),
        _interval("unknown", lower=None, lo=gap, hi=0.0),
    ]
    unknown, _ = _assess(_report(_ledger(result=_result(
        "unknown", intervals=unknown_rows, contact="unknown"))))
    assert "angular_coverage_incomplete" in _codes(unknown.interblade)
    separated_rows = [
        _interval("separated", lo=start, hi=mid),
        _interval("separated", lo=gap, hi=0.0),
    ]
    with pytest.raises(ClearanceReadinessError):
        _assess(_report(_ledger(result=_result("separated", intervals=separated_rows))))


def test_positive_overlap_and_duplicate_positive_width_abort():
    start, _ = _path()
    mid = (start + 0.0) / 2.0
    overlap = [
        _interval("unknown", lower=None, lo=start, hi=0.0),
        _interval("unknown", lower=None, lo=mid, hi=0.0),
    ]
    with pytest.raises(ClearanceReadinessError):
        _assess(_report(_ledger(result=_result("unknown", intervals=overlap, contact="unknown"))))
    duplicate = [
        _interval("separated", lo=start, hi=0.0),
        _interval("separated", lo=start, hi=0.0),
    ]
    with pytest.raises(ClearanceReadinessError):
        _assess(_report(_ledger(result=_result("separated", intervals=duplicate))))


def test_reordered_valid_intervals_match_and_do_not_mutate_the_report():
    start, _ = _path()
    mid = (start + 0.0) / 2.0
    left = _interval("separated", lo=start, hi=mid)
    right = _interval("separated", lo=mid, hi=0.0)
    forward = _report(_ledger(result=_result("separated", intervals=[left, right])))
    backward = _report(_ledger(result=_result("separated", intervals=[copy.deepcopy(right), copy.deepcopy(left)])))
    order = [row["angle_min_rad"] for row in backward["queries"][0]["result"]["intervals"]]
    forward_result, forward_document = _assess(forward)
    backward_result, backward_document = _assess(backward)
    assert [row["angle_min_rad"] for row in backward["queries"][0]["result"]["intervals"]] == order
    assert forward_document == backward_document
    assert forward_result.interblade.assessment == "preconditions_satisfied"
    assert "angular_coverage_incomplete" not in _codes(forward_result.interblade)


def test_exact_adjacent_intervals_satisfy_coverage():
    start, _ = _path()
    mid = (start + 0.0) / 2.0
    rows = [_interval("separated", lo=start, hi=mid), _interval("separated", lo=mid, hi=0.0)]
    result, _ = _assess(_report(_ledger(result=_result("separated", intervals=rows))))
    assert "angular_coverage_incomplete" not in _codes(result.interblade)
    assert result.interblade.assessment == "preconditions_satisfied"


def test_midpoint_collapse_singletons_do_not_cover_or_abort():
    start, _ = _path()
    mid = (start + 0.0) / 2.0
    gap = math.nextafter(mid, 0.0)
    rows = [
        _interval("unknown", lower=None, lo=start, hi=mid),
        _interval("unknown", lower=None, lo=mid, hi=mid),
        _interval("unknown", lower=None, lo=mid, hi=mid),
        _interval("unknown", lower=None, lo=gap, hi=0.0),
    ]
    result, _ = _assess(_report(_ledger(result=_result("unknown", intervals=rows, contact="unknown"))))
    assert result.interblade.assessment == "blocked"
    assert "angular_coverage_incomplete" in _codes(result.interblade)
    off_tree = [_interval("separated", lo=math.nextafter(start, 0.0), hi=math.nextafter(start, 0.0))]
    with pytest.raises(ClearanceReadinessError):
        _assess(_report(_ledger(result=_result("separated", intervals=off_tree))))


def test_separated_bound_contradictions_abort():
    equal = _result("separated", intervals=[_interval("separated", lower=_THRESHOLD)])
    with pytest.raises(ClearanceReadinessError):
        _assess(_report(_ledger(result=equal)))
    below = _result("separated", intervals=[_interval("separated", lower=_THRESHOLD / 2)])
    with pytest.raises(ClearanceReadinessError):
        _assess(_report(_ledger(result=below)))
    missing = _result("separated", intervals=[_interval("separated", lower=None)])
    with pytest.raises(ClearanceReadinessError):
        _assess(_report(_ledger(result=missing)))
    non_finite = _result("separated", intervals=[_interval("separated", lower=float("nan"))])
    with pytest.raises(ClearanceReadinessError):
        _assess(_report(_ledger(result=non_finite)))
    start, _ = _path()
    mid = (start + 0.0) / 2.0
    inconsistent = _result("separated", intervals=[
        _interval("separated", lower=0.02, lo=start, hi=mid),
        _interval("separated", lower=0.03, lo=mid, hi=0.0),
    ])
    inconsistent["lower_bound_m"] = 0.03
    with pytest.raises(ClearanceReadinessError):
        _assess(_report(_ledger(result=inconsistent)))
    contact = _result("separated", contact="contact", intervals=[_interval("separated", contact="contact")])
    with pytest.raises(ClearanceReadinessError):
        _assess(_report(_ledger(result=contact)))


def test_real_producer_separation_can_satisfy_interblade_prerequisites():
    produced = _producer_pair()
    assert produced["status"] == "separated"
    assert produced["lower_bound_m"] > _THRESHOLD
    result, document = _assess(_report(_ledger(result=produced)))
    assert result.interblade.assessment == "preconditions_satisfied"
    assert result.surface_path.assessment == "blocked"
    assert "shared_hinge_contact_domain_unresolved" in _codes(result.surface_path)
    assert document["interblade"]["assessment"] == "preconditions_satisfied"
    assert document["surface_path"]["assessment"] != "preconditions_satisfied"


def test_real_finite_hub_separation_and_infinite_envelope_containment():
    finite = _producer_finite_hub()
    assert finite["status"] == "separated"
    assert finite["lower_bound_m"] > _THRESHOLD
    pair = _producer_pair()
    hardware = _finite_hub_hardware("sleeve")
    report = _report(_ledger(hardware_name="sleeve"), hardware=hardware)
    for query in report["queries"]:
        if query["kind"] == "hardware_surface":
            query["result"] = copy.deepcopy(finite)
        else:
            query["result"] = copy.deepcopy(pair)
    finite_result, _ = _assess(report)
    assert finite_result.interblade.assessment == "preconditions_satisfied"
    assert "hub_model_not_positive_sufficient" not in _codes(finite_result.surface_path)
    assert "shared_hinge_contact_domain_unresolved" in _codes(finite_result.surface_path)

    hub = _producer_hub()
    assert hub["status"] == "separated"
    infinite = _report(_ledger())
    for query in infinite["queries"]:
        query["result"] = copy.deepcopy(hub if query["kind"] == "hub" else pair)
    denied, _ = _assess(infinite, question=_question(hub_containment=HUB_NOT_ESTABLISHED))
    assert "hub_model_not_positive_sufficient" in _codes(denied.surface_path)
    assert denied.interblade.assessment == "preconditions_satisfied"
    allowed, _ = _assess(infinite, question=_question(hub_containment=HUB_NOMINAL_CONTAINMENT))
    assert "hub_model_not_positive_sufficient" not in _codes(allowed.surface_path)
    assert "shared_hinge_contact_domain_unresolved" in _codes(allowed.surface_path)
    assert allowed.surface_path.assessment == "blocked"


def test_general_hardware_does_not_broaden_gate_scope():
    produced = _producer_pair()
    absent, _ = _assess(_report(_ledger(result=produced)))
    assert absent.interblade.assessment == "preconditions_satisfied"
    hardware = {"bodies": [_convex("mount", "blade_1_root"), _convex("fairing", "blade_2_root")]}
    extra = [
        _query("hardware_surface", "blade_1_tip", "mount", _result("unknown", intervals=[], reason="global_budget_exhausted")),
        _query("hardware_pair", "mount", "fairing", _result("violation")),
    ]
    present, _ = _assess(_report(_ledger(result=produced, extra=extra), hardware=hardware))
    assert present.interblade.assessment == "preconditions_satisfied"
    assert "relevant_query_unresolved" not in _codes(present.interblade)
    assert "relevant_query_violation" not in _codes(present.interblade)


def test_shared_hinge_blocks_surface_for_positive_and_zero_thresholds():
    produced = _producer_pair()
    positive, _ = _assess(_report(_ledger(result=produced)))
    assert positive.surface_path.assessment == "blocked"
    assert "shared_hinge_contact_domain_unresolved" in _codes(positive.surface_path)
    zero_facts = _facts(end_angle_deg=0.0)
    point = _result("separated", intervals=[_interval("separated", lo=0.0, hi=0.0)])
    zero_report = _report(_ledger(result=point), zero_facts)
    zero_report["request"]["inputs"]["required_clearance_m"] = 0.0
    zero_report["request"]["inputs"]["end_angle_deg"] = 0.0
    zero, _ = _assess(zero_report, zero_facts, _question(required_clearance_m=0.0))
    assert zero.surface_path.assessment == "blocked"
    assert "shared_hinge_contact_domain_unresolved" in _codes(zero.surface_path)
    assert zero.interblade.assessment == "preconditions_satisfied"


def test_current_fixtures_keep_astra_readiness_outcomes():
    canonical_inputs = SurfaceClearanceInputs(
        end_angle_deg=-10, required_clearance_m=_THRESHOLD, max_depth=4,
        max_intervals=32, max_node_comparisons=20000)
    canonical = _run_report(draft(), **{
        "end_angle_deg": -10, "required_clearance_m": _THRESHOLD, "max_depth": 4,
        "max_intervals": 32, "max_node_comparisons": 20000})
    canonical_facts = _facts_from_draft(draft(), -10, canonical_inputs)
    canonical_result, _ = _assess(canonical, canonical_facts, _question())
    assert canonical_result.interblade.assessment == "blocked"
    assert "root_span_missing" in _codes(canonical_result.interblade)
    assert "tip_span_missing" in _codes(canonical_result.interblade)

    full = _complete_span_text()
    full_inputs = SurfaceClearanceInputs(
        end_angle_deg=-10, required_clearance_m=_THRESHOLD, max_depth=6,
        max_intervals=64, max_node_comparisons=80000)
    full_report = _run_report(full, end_angle_deg=-10, required_clearance_m=_THRESHOLD,
                              max_depth=6, max_intervals=64, max_node_comparisons=80000)
    full_facts = _facts_from_draft(full, -10, full_inputs)
    full_result, _ = _assess(full_report, full_facts, _question())
    assert full_result.interblade.assessment == "preconditions_satisfied"
    assert full_result.surface_path.assessment == "blocked"
    assert "shared_hinge_contact_domain_unresolved" in _codes(full_result.surface_path)

    excluded_inputs = SurfaceClearanceInputs(
        end_angle_deg=-10, required_clearance_m=_THRESHOLD, root_attachment_m=0.002,
        hinge_attachment_m=0.002, contact_source="synthetic fixture", max_depth=4,
        max_intervals=16, max_node_comparisons=40000)
    excluded = _run_report(
        full, end_angle_deg=-10, required_clearance_m=_THRESHOLD, root_attachment_m=0.002,
        hinge_attachment_m=0.002, contact_source="synthetic fixture", max_depth=4,
        max_intervals=16, max_node_comparisons=40000)
    excluded_facts = _facts_from_draft(full, -10, excluded_inputs)
    excluded_result, _ = _assess(excluded, excluded_facts, _question())
    assert excluded_result.surface_path.assessment == "blocked"
    assert excluded_result.interblade.assessment == "blocked"
    assert "excluded_region" in _codes(excluded_result.surface_path)
    assert "excluded_region" in _codes(excluded_result.interblade)
    assert "shared_hinge_contact_domain_unresolved" in _codes(excluded_result.surface_path)

    contact_inputs = SurfaceClearanceInputs(
        end_angle_deg=0, required_clearance_m=0.0, max_depth=4, max_intervals=8,
        max_node_comparisons=20000)
    contact = _run_report(
        full, end_angle_deg=0, required_clearance_m=0.0, max_depth=4, max_intervals=8,
        max_node_comparisons=20000)
    contact_facts = _facts_from_draft(full, 0, contact_inputs)
    contact_result, contact_document = _assess(
        contact, contact_facts, _question(required_clearance_m=0.0))
    assert contact_result.surface_path.assessment == "blocked"
    assert "shared_hinge_contact_domain_unresolved" in _codes(contact_result.surface_path)
    assert any(blocker.cause == "contact" for blocker in contact_result.surface_path.blockers)
    assert contact_result.interblade.assessment == "preconditions_satisfied"
    assert "nonpenetration" not in json.dumps(contact_document)


def test_one_blade_completed_evidence_keeps_interblade_not_applicable():
    facts = _facts(blade_count=1)
    queries = _hub_queries(1, _result()) + _own_queries(1, _result())
    result, _ = _assess(_report(queries, facts), facts)
    assert result.interblade.assessment == "not_applicable"
    assert result.surface_path.assessment == "blocked"


def test_pure_module_does_not_execute_clearance_or_touch_files():
    source = inspect.getsource(assess_positive_clearance_readiness)
    module = inspect.getsource(__import__(
        "pyfoldable.application.geometry_clearance_readiness", fromlist=["assess_positive_clearance_readiness"]))
    for banned in ("hashlib", "pathlib", "surface_clearance", "hardware_clearance", "open(", "design_search"):
        assert banned not in module
    assert "hashlib" not in source


def test_blockers_are_sorted_and_primary_reason_is_first():
    facts = _facts(first_station_radius_m=0.025, last_station_radius_m=0.1225, root_exclusion_width_m=0.001)
    result, document = _assess(_report(_ledger(), facts), facts)
    codes = _codes(result.surface_path)
    assert codes[0] == result.surface_path.primary_reason
    assert document["surface_path"]["primary_reason"] == codes[0]
    assert codes.index("root_span_missing") < codes.index("excluded_region")
    assert codes.index("excluded_region") < codes.index("shared_hinge_contact_domain_unresolved")


def test_request_identity_includes_the_question_and_changes_with_its_settings():
    base = prepare_geometry_search(draft(), hinge_radii_m=(0.1,), stowed_angles_deg=(-10.,))
    low = prepare_geometry_search(
        draft(), hinge_radii_m=(0.1,), stowed_angles_deg=(-10.,), readiness_question=_question())
    high = prepare_geometry_search(
        draft(), hinge_radii_m=(0.1,), stowed_angles_deg=(-10.,),
        readiness_question=_question(required_clearance_m=0.01))
    contained = prepare_geometry_search(
        draft(), hinge_radii_m=(0.1,), stowed_angles_deg=(-10.,),
        readiness_question=_question(hub_containment=HUB_NOMINAL_CONTAINMENT))
    assert "positive_clearance_readiness" not in json.loads(base.context_json)
    assert low.request_sha256 != high.request_sha256
    assert low.request_sha256 != contained.request_sha256
    declaration = json.loads(low.context_json)["positive_clearance_readiness"]
    assert declaration["effect"] == EFFECT
    assert declaration["required_clearance_m"] == _THRESHOLD
    rerun = prepare_geometry_search(
        draft(), hinge_radii_m=(0.1,), stowed_angles_deg=(-10.,), readiness_question=_question())
    assert rerun == low


def test_no_question_leaves_search_behavior_without_a_readiness_namespace(monkeypatch):
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda request: pytest.fail("readiness must not execute GEOM-04"))
    prepared = prepare_geometry_search(draft(), hinge_radii_m=(0.1,), stowed_angles_deg=(-10.,))
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    assert "geom04_positive_clearance_readiness" not in row["details"]
    assert row["constraints"]["surface_path_clearance"] is None
    assert row["constraints"]["interblade_clearance"] is None
    assert result["best_candidate"] is None
    assert result["physical_qualification"] is False


def test_question_without_evidence_is_blocked_and_does_not_run_geom04(monkeypatch):
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda request: pytest.fail("readiness must not execute GEOM-04"))
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(0.1,), stowed_angles_deg=(-10.,), readiness_question=_question())
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    readiness = row["details"]["geom04_positive_clearance_readiness"]
    assert readiness["surface_path"]["assessment"] == "blocked"
    assert readiness["interblade"]["assessment"] == "blocked"
    assert readiness["surface_path"]["blockers"][0]["evidence_detail"] == "absent"
    assert row["constraints"]["surface_path_clearance"] is None
    assert row["constraints"]["interblade_clearance"] is None
    assert result["best_candidate"] is None


def test_validation_failure_and_oversize_feed_the_final_evidence_state(monkeypatch):
    def reject(draft_obj, inputs, hardware_json=None):
        raise SurfaceClearanceValidationError("candidate hinge exclusion exceeds the span")

    monkeypatch.setattr("pyfoldable.application.surface_clearance.prepare_surface_clearance", reject)
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(0.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10),
        readiness_question=_question())
    result = json.loads(run_geometry_search(prepared).report_json)
    row = result["candidates"][0]
    readiness = row["details"]["geom04_positive_clearance_readiness"]
    assert readiness["evidence_status"] == "candidate_validation_failed"
    assert readiness["surface_path"]["blockers"][0]["evidence_detail"] == "candidate_validation_failed"
    assert row["constraints"]["surface_path_clearance"] is None

    monkeypatch.undo()
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        lambda request: _bound_report_artifact(request, padding="x" * (300 * 1024)))
    oversize_request = prepare_geometry_search(
        _complete_span_draft(), hinge_radii_m=(0.06,), stowed_angles_deg=(-150.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-150.),
        readiness_question=_question())
    oversize = json.loads(run_geometry_search(oversize_request).report_json)
    over_row = oversize["candidates"][0]
    assert over_row["details"]["geom04_clearance"]["execution_status"] == (
        "evidence_attachment_exceeds_search_details_budget")
    assert over_row["details"]["geom04_clearance"]["report"] is None
    recorded = over_row["details"]["geom04_positive_clearance_readiness"]
    assert recorded["evidence_status"] == "evidence_unavailable_oversize"
    assert recorded["surface_path"]["blockers"][0]["evidence_detail"] == "oversize"
    assert over_row["constraints"]["surface_path_clearance"] is None
    assert over_row["constraints"]["interblade_clearance"] is None


def _search_pair(question, policy=None, *, hinge=0.06, angle=-150.0):
    prepared = prepare_geometry_search(
        _complete_span_text(), hinge_radii_m=(hinge,), stowed_angles_deg=(angle,),
        clearance_inputs=SurfaceClearanceInputs(
            end_angle_deg=angle, required_clearance_m=_THRESHOLD, max_depth=6,
            max_intervals=64, max_node_comparisons=80000),
        clearance_policy=policy,
        readiness_question=question,
    )
    document = json.loads(run_geometry_search(prepared).report_json)
    return document, document["candidates"][0]


def test_readiness_does_not_change_constraints_status_or_selection():
    without, without_row = _search_pair(None)
    with_question, row = _search_pair(_question())
    assert row["constraints"] == without_row["constraints"]
    assert row["objective"] == without_row["objective"]
    assert row["status"] == without_row["status"] == "blocked"
    assert with_question["best_candidate"] is None and without["best_candidate"] is None
    assert row["constraints"]["surface_path_clearance"] is None
    assert row["constraints"]["interblade_clearance"] is None
    assert row["constraints"]["surface_path_clearance"] is not True
    assert row["constraints"]["interblade_clearance"] is not True
    readiness = row["details"]["geom04_positive_clearance_readiness"]
    assert readiness["interblade"]["assessment"] == "preconditions_satisfied"
    assert readiness["surface_path"]["assessment"] == "blocked"
    assert any(blocker["code"] == "shared_hinge_contact_domain_unresolved"
               for blocker in readiness["surface_path"]["blockers"])
    assert row["details"]["geom04_clearance"]["report"] == without_row["details"]["geom04_clearance"]["report"]
    assert row["details"]["full_propeller_clearance"] is None
    assert row["details"]["physical_qualification"] is False
    assert "geom04_positive_clearance_readiness" not in row["details"]["geom04_clearance"]["report"]


def test_negative_false_survives_a_readiness_threshold_mismatch():
    policy = NegativeClearancePolicy(required_clearance_m=_THRESHOLD)
    without, without_row = _search_pair(None, policy)
    _, row = _search_pair(_question(required_clearance_m=0.01), policy)
    assert without_row["constraints"]["surface_path_clearance"] is False
    assert row["constraints"] == without_row["constraints"]
    assert row["constraints"]["surface_path_clearance"] is False
    assert row["status"] == without_row["status"]
    assert row["objective"] == without_row["objective"]
    readiness = row["details"]["geom04_positive_clearance_readiness"]
    assert any(blocker["code"] == "threshold_mismatch" for blocker in readiness["surface_path"]["blockers"])
    assert row["details"]["geom04_negative_clearance_policy"] == (
        without_row["details"]["geom04_negative_clearance_policy"])
    assert row["details"]["geom04_clearance"]["report"] == without_row["details"]["geom04_clearance"]["report"]


def test_duplicate_pair_in_a_search_aborts_instead_of_recording_a_failed_row(monkeypatch):
    def duplicate(request):
        model, _ = _load_geometry(request.draft)
        blade = model.blade
        radius = blade.diameter_m / 2.0
        first = blade.stations[0].r_over_R * radius
        last = blade.stations[-1].r_over_R * radius
        queries = _ledger()
        queries.append(copy.deepcopy(queries[0]))
        return _bound_report_artifact(
            request, queries=queries,
            root_gap_m=first - blade.hub_radius_m,
            tip_gap_m=radius - last,
            station_span_complete=False,
            modeled_surface_status="separated")

    monkeypatch.setattr("pyfoldable.application.surface_clearance.run_surface_clearance", duplicate)
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(0.06,), stowed_angles_deg=(-10.,),
        clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10, max_node_comparisons=10),
        readiness_question=_question())
    with pytest.raises(SearchError, match="readiness"):
        run_geometry_search(prepared)


def test_readiness_namespace_fits_and_is_omitted_in_full_when_it_would_exceed_256_kib(monkeypatch):
    model, _ = _load_geometry(draft())
    blade = model.blade
    radius = blade.diameter_m / 2.0
    facts = _facts(
        hinge_radius_m=0.06,
        hub_radius_m=blade.hub_radius_m,
        tip_radius_m=radius,
        first_station_radius_m=blade.stations[0].r_over_R * radius,
        last_station_radius_m=blade.stations[-1].r_over_R * radius,
    )
    queries = _ledger()
    root_gap = facts.first_station_radius_m - facts.hub_radius_m
    tip_gap = facts.tip_radius_m - facts.last_station_radius_m

    def run(padding, question):
        def artifact(request):
            return _bound_report_artifact(
                request, queries=queries, padding="x" * padding,
                root_gap_m=root_gap, tip_gap_m=tip_gap, station_span_complete=False,
                modeled_surface_status="separated")
        monkeypatch.setattr("pyfoldable.application.surface_clearance.run_surface_clearance", artifact)
        prepared = prepare_geometry_search(
            draft(), hinge_radii_m=(0.06,), stowed_angles_deg=(-10.,),
            clearance_inputs=SurfaceClearanceInputs(end_angle_deg=-10),
            readiness_question=question)
        document = json.loads(run_geometry_search(prepared).report_json)
        return document, document["candidates"][0]

    small_without, small_without_row = run(0, None)
    small_with, small_row = run(0, _question())
    assert "geom04_positive_clearance_readiness" in small_row["details"]
    assert small_row["constraints"] == small_without_row["constraints"]
    assert small_row["status"] == small_without_row["status"]
    assert small_row["objective"] == small_without_row["objective"]
    assert small_with["best_candidate"] == small_without["best_candidate"]
    assert small_row["details"]["geom04_clearance"]["report"]["queries"] == (
        small_without_row["details"]["geom04_clearance"]["report"]["queries"])

    low, high = 0, 260_000
    omitted = None
    while low <= high:
        padding = (low + high) // 2
        document, row = run(padding, _question())
        evidence = row["details"]["geom04_clearance"]
        if evidence["execution_status"] != "completed":
            high = padding - 1
            continue
        if "geom04_positive_clearance_readiness" in row["details"]:
            low = padding + 1
        else:
            omitted = (padding, document, row)
            high = padding - 1
    assert omitted is not None
    padding, _, row = omitted
    _, plain = run(padding, None)
    assert "geom04_positive_clearance_readiness" not in row["details"]
    assert row["constraints"] == plain["constraints"]
    assert row["objective"] == plain["objective"]
    assert row["status"] == plain["status"]
    assert row["details"]["geom04_clearance"] == plain["details"]["geom04_clearance"]
    assert row["details"]["audit"] == plain["details"]["audit"]
    assert len(_json(row["details"]).encode()) <= 256 * 1024


def test_no_readiness_document_assigns_true():
    result, document = _assess(_report(_ledger(result=_producer_pair())))
    assert result.surface_path.assessment != "preconditions_satisfied"
    assert document["interblade"]["assessment"] == "preconditions_satisfied"
    assert True not in document["surface_path"].values()
    assert False not in document["interblade"].values()


_PRODUCER_THRESHOLD = 0.0005
_DIMENSION_STATE_NAMES = (
    "satisfied", "blocked", "not_assessed", "not_applicable",
)


def _dimension_states(gate):
    """Read the ordered per-dimension state map. Names alone are not a state."""
    rows = gate["dimensions"]
    assert isinstance(rows, list) and rows and isinstance(rows[0], dict)
    assert [row["name"] for row in rows] == list(DIMENSIONS)
    states = {row["name"]: row["state"] for row in rows}
    assert set(states.values()) <= set(_DIMENSION_STATE_NAMES)
    return states


def _states(**changes):
    values = {name: "satisfied" for name in DIMENSIONS}
    values.update(changes)
    return values


def _interblade_states(**changes):
    values = _states(
        hub_suitability="not_applicable",
        contact_domain="not_applicable",
    )
    values.update(changes)
    return values


def _surface_states(**changes):
    values = _states(contact_domain="blocked")
    values.update(changes)
    return values


def _unavailable_states():
    return {name: ("blocked" if name == "candidate_binding" else "not_assessed") for name in DIMENSIONS}


def _contained_question(**changes):
    values = {"hub_containment": HUB_NOMINAL_CONTAINMENT}
    values.update(changes)
    return _question(**values)


def _completed(facts=None, result=None, question=None, **report_changes):
    facts = facts or _facts()
    report = _report(_ledger(facts.blade_count, result or _result()), facts, **report_changes)
    return _assess(report, facts, question or _contained_question())


def _rehashed_separated_report(lower, *, query_lower=None, intervals=None):
    """Return a PR #67 identity-bound artifact whose producer threshold stays on the request."""

    def run(clearance_request):
        model, _ = _load_geometry(clearance_request.draft)
        blade = model.blade
        radius = blade.diameter_m / 2.0
        angle = clearance_request.inputs.end_angle_deg
        start = math.radians(float(angle))
        first = blade.stations[0].r_over_R * radius
        last = blade.stations[-1].r_over_R * radius
        hinge = model.hinge.radius_m
        rows = intervals if intervals is not None else [
            _interval("separated", lower=lower, lo=start, hi=0.0)]
        result = _result("separated", intervals=rows)
        if query_lower is not None:
            result["lower_bound_m"] = query_lower
        root_gap = first - blade.hub_radius_m
        tip_gap = radius - last
        root_ok = abs(root_gap) <= 8 * max(math.ulp(first), math.ulp(blade.hub_radius_m))
        tip_ok = abs(tip_gap) <= 8 * max(math.ulp(last), math.ulp(radius))
        hinge_ok = first < hinge < last
        return _bound_report_artifact(
            clearance_request,
            queries=_ledger(blade.blade_count, result),
            root_gap_m=root_gap,
            tip_gap_m=tip_gap,
            station_span_complete=bool(root_ok and tip_ok and hinge_ok),
            modeled_surface_status="separated",
        )

    return run


def _search_rehashed(monkeypatch, lower, question_threshold, **artifact):
    monkeypatch.setattr(
        "pyfoldable.application.surface_clearance.run_surface_clearance",
        _rehashed_separated_report(lower, **artifact),
    )
    return prepare_geometry_search(
        _complete_span_text(),
        hinge_radii_m=(0.1,),
        stowed_angles_deg=(-10.0,),
        clearance_inputs=SurfaceClearanceInputs(
            end_angle_deg=-10.0, required_clearance_m=_PRODUCER_THRESHOLD),
        readiness_question=_question(required_clearance_m=question_threshold),
    )


@pytest.mark.parametrize("question_threshold,lower", [
    (0.001, 0.0001),
    (0.001, _PRODUCER_THRESHOLD),
    (0.0001, 0.0001),
])
def test_producer_threshold_aborts_a_separated_claim_when_the_question_differs(
        monkeypatch, question_threshold, lower):
    prepared = _search_rehashed(monkeypatch, lower, question_threshold)
    with pytest.raises(SearchError, match="readiness"):
        run_geometry_search(prepared)


@pytest.mark.parametrize("question_threshold", [0.001, 0.0001])
def test_valid_producer_separation_with_a_different_question_is_only_a_mismatch(
        monkeypatch, question_threshold):
    prepared = _search_rehashed(monkeypatch, 0.0006, question_threshold)
    document = json.loads(run_geometry_search(prepared).report_json)
    row = document["candidates"][0]
    readiness = row["details"]["geom04_positive_clearance_readiness"]
    assert row["status"] != "failed"
    assert document["best_candidate"] is None
    for gate_name in ("surface_path", "interblade"):
        codes = [blocker["code"] for blocker in readiness[gate_name]["blockers"]]
        assert "threshold_mismatch" in codes
        assert readiness[gate_name]["assessment"] == "blocked"
    assert row["constraints"]["surface_path_clearance"] is None
    assert row["constraints"]["interblade_clearance"] is None


def test_matching_thresholds_keep_normal_readiness_for_a_rehashed_report(monkeypatch):
    prepared = _search_rehashed(monkeypatch, 0.0006, _PRODUCER_THRESHOLD)
    document = json.loads(run_geometry_search(prepared).report_json)
    row = document["candidates"][0]
    readiness = row["details"]["geom04_positive_clearance_readiness"]
    assert "threshold_mismatch" not in [
        blocker["code"] for blocker in readiness["interblade"]["blockers"]]
    assert readiness["interblade"]["assessment"] == "preconditions_satisfied"
    assert readiness["surface_path"]["assessment"] == "blocked"
    assert any(
        blocker["code"] == "shared_hinge_contact_domain_unresolved"
        for blocker in readiness["surface_path"]["blockers"])
    assert row["constraints"]["interblade_clearance"] is None
    assert row["status"] != "failed"
    assert document["best_candidate"] is None


def test_missing_separated_lower_bound_still_aborts_a_rehashed_report(monkeypatch):
    start = math.radians(-10.0)
    prepared = _search_rehashed(
        monkeypatch, None, 0.001,
        intervals=[_interval("separated", lower=None, lo=start, hi=0.0)])
    with pytest.raises(SearchError, match="readiness"):
        run_geometry_search(prepared)


def test_query_lower_bound_mismatch_still_aborts_a_rehashed_report(monkeypatch):
    start = math.radians(-10.0)
    mid = start / 2.0
    prepared = _search_rehashed(
        monkeypatch, 0.02, 0.001,
        intervals=[
            _interval("separated", lower=0.02, lo=start, hi=mid),
            _interval("separated", lower=0.03, lo=mid, hi=0.0),
        ],
        query_lower=0.03,
    )
    with pytest.raises(SearchError, match="readiness"):
        run_geometry_search(prepared)


def test_dimension_states_for_complete_interblade_and_shared_hinge_surface():
    result, document = _completed(result=_producer_pair())
    assert result.interblade.assessment == "preconditions_satisfied"
    assert _dimension_states(document["interblade"]) == _interblade_states()
    assert result.surface_path.assessment == "blocked"
    assert result.surface_path.primary_reason == "shared_hinge_contact_domain_unresolved"
    assert _dimension_states(document["surface_path"]) == _surface_states()


def test_dimension_states_for_root_and_tip_span_gaps():
    root_facts = _facts(first_station_radius_m=0.025)
    _, root = _completed(root_facts)
    assert root["surface_path"]["primary_reason"] == "root_span_missing"
    assert _dimension_states(root["interblade"]) == _interblade_states(radial_coverage="blocked")
    assert _dimension_states(root["surface_path"]) == _surface_states(radial_coverage="blocked")
    tip_facts = _facts(last_station_radius_m=0.12)
    _, tip = _completed(tip_facts)
    assert tip["surface_path"]["primary_reason"] == "tip_span_missing"
    assert _dimension_states(tip["interblade"]) == _interblade_states(radial_coverage="blocked")
    assert _dimension_states(tip["surface_path"]) == _surface_states(radial_coverage="blocked")


def test_dimension_states_for_exclusions_threshold_and_motion():
    excluded = _facts(root_exclusion_width_m=0.001)
    _, exclusion = _completed(excluded)
    assert exclusion["interblade"]["primary_reason"] == "excluded_region"
    assert _dimension_states(exclusion["interblade"]) == _interblade_states(exclusions="blocked")
    assert _dimension_states(exclusion["surface_path"]) == _surface_states(exclusions="blocked")

    _, mismatch = _completed(question=_contained_question(required_clearance_m=0.001))
    assert mismatch["interblade"]["primary_reason"] == "threshold_mismatch"
    assert _dimension_states(mismatch["interblade"]) == _interblade_states(
        question_compatibility="blocked")
    assert _dimension_states(mismatch["surface_path"]) == _surface_states(
        question_compatibility="blocked")

    _, motion = _completed(question=_contained_question(), request={"motion": "asynchronous_tips"})
    assert motion["interblade"]["primary_reason"] == "motion_scope_mismatch"
    assert _dimension_states(motion["interblade"]) == _interblade_states(
        question_compatibility="blocked")
    assert _dimension_states(motion["surface_path"]) == _surface_states(
        question_compatibility="blocked")


def test_dimension_states_for_unknown_and_missing_relevant_pairs():
    queries = _ledger(result=_result())
    replaced = False
    for query in queries:
        if query["kind"] == "interblade":
            query["result"] = _result(
                "unknown", intervals=[_interval("unknown", lower=None)], contact="unknown")
            replaced = True
            break
    assert replaced
    _, unknown = _assess(_report(queries), question=_contained_question())
    assert unknown["interblade"]["primary_reason"] == "relevant_query_unresolved"
    assert _dimension_states(unknown["interblade"]) == _interblade_states(
        numerical_resolution="blocked", separation_support="not_assessed")
    assert _dimension_states(unknown["surface_path"]) == _surface_states()

    retained = [query for query in _ledger(result=_result()) if query["kind"] != "interblade"]
    retained.append(next(query for query in _ledger(result=_result()) if query["kind"] == "interblade"))
    _, gap = _assess(_report(retained), question=_contained_question())
    assert gap["interblade"]["primary_reason"] == "relevant_pair_missing"
    assert _dimension_states(gap["interblade"]) == _interblade_states(
        pair_coverage="blocked",
        angular_coverage="not_assessed",
        numerical_resolution="not_assessed",
        separation_support="not_assessed",
    )
    assert _dimension_states(gap["surface_path"]) == _surface_states()


def test_dimension_states_when_evidence_is_unavailable():
    expected = _unavailable_states()
    for status, detail in (
            ("no_evidence", "absent"),
            ("candidate_validation_failed", "candidate_validation_failed"),
            ("evidence_unavailable_oversize", "oversize"),
    ):
        result, document = _assess(None, status=status)
        assert result.surface_path.primary_reason == "evidence_unavailable"
        assert result.surface_path.blockers[0].evidence_detail == detail
        assert _dimension_states(document["surface_path"]) == expected
        assert _dimension_states(document["interblade"]) == expected
        assert "satisfied" not in _dimension_states(document["surface_path"]).values()


def test_one_blade_interblade_dimensions_are_all_not_applicable():
    """Applicability wins. Every interblade dimension is not_applicable.

    Question and candidate fields stay on the parent result. They are not
    copied into the inapplicable gate.
    """
    facts = _facts(blade_count=1)
    queries = _hub_queries(1, _result()) + _own_queries(1, _result())
    result, document = _assess(
        _report(queries, facts), facts, _contained_question())
    assert result.interblade.assessment == "not_applicable"
    assert result.interblade.primary_reason is None
    assert result.interblade.blockers == ()
    assert _dimension_states(document["interblade"]) == {
        name: "not_applicable" for name in DIMENSIONS}
    assert _dimension_states(document["surface_path"]) == _surface_states()
    absent, absent_document = _assess(None, facts=facts, status="no_evidence")
    assert absent.interblade.assessment == "not_applicable"
    assert _dimension_states(absent_document["interblade"]) == {
        name: "not_applicable" for name in DIMENSIONS}
    assert _dimension_states(absent_document["surface_path"]) == _unavailable_states()


@pytest.mark.parametrize("error", [
    ZeroDivisionError("readiness divide"),
    OverflowError("readiness overflow"),
])
def test_readiness_arithmetic_error_aborts_before_a_failed_row(monkeypatch, error):
    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(
        "pyfoldable.application.geometry_search.assess_positive_clearance_readiness", fail)
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(0.1,), stowed_angles_deg=(-10.0,),
        readiness_question=_question())
    with pytest.raises(SearchError, match="readiness") as caught:
        run_geometry_search(prepared)
    assert caught.value.__cause__ is error


def test_readiness_integrity_error_still_aborts_the_search(monkeypatch):
    def fail(*_args, **_kwargs):
        raise ClearanceReadinessError("injected contradiction")

    monkeypatch.setattr(
        "pyfoldable.application.geometry_search.assess_positive_clearance_readiness", fail)
    prepared = prepare_geometry_search(
        draft(), hinge_radii_m=(0.1,), stowed_angles_deg=(-10.0,),
        readiness_question=_question())
    with pytest.raises(SearchError, match="readiness") as caught:
        run_geometry_search(prepared)
    assert isinstance(caught.value.__cause__, ClearanceReadinessError)
