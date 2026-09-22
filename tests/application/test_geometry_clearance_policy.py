"""GEOM-01 negative clearance policy v1: False or None, never True."""
import json
import math

import pytest

from pyfoldable.application.geometry_clearance_policy import (
    MOTION_DOMAIN,
    POLICY_ID,
    ClearancePolicyError,
    NegativeClearancePolicy,
    decide_negative_clearance,
)

_PATH_MIN = math.radians(-10.0)


def _policy(**changes):
    values = {"required_clearance_m": 0.001}
    values.update(changes)
    return NegativeClearancePolicy(**values)


def _interval(status="violation", *, witness_clearance_m=0.0, witness_angle_rad=-0.05, **extra):
    row = {
        "angle_min_rad": _PATH_MIN,
        "angle_max_rad": 0.0,
        "status": status,
        "lower_bound_m": None,
        "witness_clearance_m": witness_clearance_m if status == "violation" else None,
        "witness_angle_rad": witness_angle_rad if status == "violation" else None,
        "method": "triangle_distance",
        "contact_status": "unknown",
        "point_a": None,
        "point_b": None,
    }
    row.update(extra)
    return row


def _query(kind, a, b, status="separated", **result_fields):
    intervals = result_fields.pop("intervals", None)
    if intervals is None:
        intervals = [_interval(status)]
    result = {
        "status": status,
        "lower_bound_m": None,
        "witness_clearance_m": 0.0 if status == "violation" else None,
        "intervals": intervals,
        "reason": status,
        "contact_status": result_fields.pop("contact_status", "unknown"),
        "node_comparisons": 0,
        "feature_tests": 0,
    }
    result.update(result_fields)
    return {"kind": kind, "a": a, "b": b, "result": result}


def _hardware(*bodies):
    return {"bodies": list(bodies)}


def _finite_hub(name="sleeve"):
    return {"name": name, "binding": "hub", "geometry": {"kind": "finite_cylinder"}}


def _convex(name, binding):
    return {"name": name, "binding": binding, "geometry": {"kind": "convex_polyhedron"}}


def _report(queries, **changes):
    document = {
        "request": {
            "inputs": {
                "required_clearance_m": 0.001,
                "end_angle_deg": -10.0,
            },
            "motion": MOTION_DOMAIN,
            "hardware": None,
        },
        "queries": queries,
        "station_span_complete": False,
        "excluded_regions": {"root_radial_width_m": 0.02, "hinge_half_width_m": 0.01},
        "modeled_surface_status": "violation",
        "hardware_status": "violation",
        "classification": "failed",
    }
    request_changes = changes.pop("request", None)
    document.update(changes)
    if request_changes:
        document["request"].update(request_changes)
    return document


def _values(policy, report, **kwargs):
    decision = decide_negative_clearance(policy, report, **kwargs)
    assert decision.policy_id == POLICY_ID
    assert decision.surface_path_clearance.value is not True
    assert decision.interblade_clearance.value is not True
    return decision


def test_policy_identity_is_fixed_negative_only_v1():
    policy = _policy()
    assert policy.policy_id == "geom01_negative_clearance_v1"
    assert policy.motion_domain == "synchronous_planar_rigid_tips_from_zero_to_declared_endpoint"
    assert policy.enabled is True
    declaration = policy.declaration()
    assert declaration["semantics"] == "negative_only"
    assert set(declaration) == {
        "policy_id", "enabled", "required_clearance_m", "motion_domain", "semantics",
    }


@pytest.mark.parametrize("value", [-0.01, 0.11, True, float("nan"), float("inf")])
def test_policy_threshold_matches_geom04_clearance_bounds(value):
    with pytest.raises(ClearancePolicyError):
        _policy(required_clearance_m=value)


def test_disabled_policy_returns_none_without_reading_a_violation():
    report = _report([_query("own_root_tip", "blade_1_root", "blade_1_tip", "violation")])
    before = json.dumps(report)
    decision = _values(_policy(enabled=False), report)
    assert decision.surface_path_clearance.value is None
    assert decision.interblade_clearance.value is None
    assert decision.surface_path_clearance.reason == "policy_not_enabled"
    assert decision.interblade_clearance.reason == "policy_not_enabled"
    assert json.dumps(report) == before


def test_no_evidence_returns_none():
    decision = _values(_policy(), None, evidence_status="no_evidence")
    assert decision.surface_path_clearance.value is None
    assert decision.interblade_clearance.value is None
    assert decision.surface_path_clearance.reason == "no_evidence"


def test_candidate_validation_failure_returns_none():
    decision = _values(_policy(), None, evidence_status="candidate_validation_failed")
    assert decision.surface_path_clearance.reason == "candidate_validation_failed"
    assert decision.interblade_clearance.value is None


def test_oversize_evidence_returns_none():
    decision = _values(_policy(), {"queries": []}, evidence_status="evidence_unavailable_oversize")
    assert decision.surface_path_clearance.value is None
    assert decision.interblade_clearance.value is None
    assert decision.surface_path_clearance.reason == "evidence_unavailable_oversize"
    assert decision.surface_path_clearance.query_index is None


def test_own_root_tip_violation_sets_only_surface_gate_false():
    report = _report([_query("own_root_tip", "blade_1_root", "blade_1_tip", "violation")])
    before = json.dumps(report)
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is False
    assert decision.surface_path_clearance.reason == "relevant_violation_witness"
    assert decision.surface_path_clearance.query_index == 0
    assert decision.surface_path_clearance.interval_index == 0
    assert decision.interblade_clearance.value is None
    assert decision.interblade_clearance.reason == "no_relevant_violation"
    assert json.dumps(report) == before


def test_interblade_violation_sets_only_interblade_gate_false():
    report = _report([_query("interblade", "blade_1_root", "blade_2_tip", "violation")])
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is None
    assert decision.interblade_clearance.value is False
    assert decision.interblade_clearance.query_index == 0
    assert decision.interblade_clearance.interval_index == 0


def test_both_families_can_be_false_together():
    report = _report([
        _query("own_root_tip", "blade_1_tip", "blade_1_root", "violation"),
        _query("interblade", "blade_2_root", "blade_1_root", "violation"),
    ])
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is False
    assert decision.interblade_clearance.value is False


def test_finite_cylinder_hub_violation_sets_surface_false():
    report = _report(
        [_query("hardware_surface", "blade_1_tip", "sleeve", "violation")],
        request={"hardware": _hardware(_finite_hub("sleeve"))},
    )
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is False
    assert decision.interblade_clearance.value is None


def test_name_containing_hub_without_finite_cylinder_is_not_surface_proof():
    report = _report(
        [_query("hardware_surface", "hub", "blade_1_root", "violation")],
        request={"hardware": _hardware(_convex("hub", "hub"))},
    )
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is None
    assert decision.interblade_clearance.value is None


def test_finite_hub_penetration_at_zero_clearance_sets_surface_false():
    report = _report(
        [_query(
            "hardware_surface", "sleeve", "blade_2_root", "violation",
            intervals=[_interval(witness_clearance_m=-0.002, witness_angle_rad=0.0)],
        )],
        request={
            "hardware": _hardware(_finite_hub("sleeve")),
            "inputs": {"required_clearance_m": 0.0, "end_angle_deg": -10.0},
        },
    )
    decision = _values(_policy(required_clearance_m=0.0), report)
    assert decision.surface_path_clearance.value is False
    assert decision.interblade_clearance.value is None


def test_infinite_cylinder_violation_does_not_set_surface_false():
    report = _report([_query("hub", "blade_1_root", "hub_envelope", "violation")])
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is None
    assert decision.interblade_clearance.value is None
    assert decision.surface_path_clearance.reason == "infinite_hub_violation_not_finite_hub_proof"


def test_general_hardware_surface_violation_does_not_change_gates():
    report = _report(
        [_query("hardware_surface", "blade_1_tip", "pod", "violation")],
        request={"hardware": _hardware(_convex("pod", "blade_1_root"))},
    )
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is None
    assert decision.interblade_clearance.value is None


def test_hardware_pair_violation_does_not_change_gates():
    report = _report(
        [_query("hardware_pair", "pod", "sleeve", "violation")],
        request={"hardware": _hardware(_convex("pod", "blade_1_tip"), _finite_hub("sleeve"))},
    )
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is None
    assert decision.interblade_clearance.value is None


def test_interblade_violation_does_not_require_a_hardware_declaration():
    report = _report([_query("interblade", "blade_1_tip", "blade_2_tip", "violation")])
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is None
    assert decision.interblade_clearance.value is False


def test_relevant_violation_survives_incomplete_span_and_exclusions():
    report = _report(
        [_query("own_root_tip", "blade_1_root", "blade_1_tip", "violation")],
        station_span_complete=False,
        excluded_regions={"root_radial_width_m": 0.03},
    )
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is False


def test_relevant_violation_survives_other_query_budget_exhaustion():
    report = _report([
        _query("own_root_tip", "blade_1_root", "blade_1_tip", "violation"),
        _query("own_root_tip", "blade_2_root", "blade_2_tip", "unknown", intervals=[], reason="global_budget_exhausted"),
    ])
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is False
    assert decision.surface_path_clearance.query_index == 0


def test_budget_exhaustion_without_violation_stays_none():
    report = _report([
        _query("own_root_tip", "blade_1_root", "blade_1_tip", "unknown", intervals=[], reason="global_budget_exhausted"),
        _query("interblade", "blade_1_root", "blade_2_root", "unknown", intervals=[]),
    ])
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is None
    assert decision.interblade_clearance.value is None
    assert decision.surface_path_clearance.reason == "relevant_numerics_unresolved"


def test_all_separated_queries_stay_none_even_when_aggregate_status_is_violation():
    report = _report(
        [
            _query("own_root_tip", "blade_1_root", "blade_1_tip", "separated"),
            _query("interblade", "blade_1_tip", "blade_2_root", "separated"),
        ],
        modeled_surface_status="violation",
        hardware_status="violation",
        classification="failed",
    )
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is None
    assert decision.interblade_clearance.value is None
    assert decision.surface_path_clearance.reason == "true_promotion_disabled"
    assert decision.interblade_clearance.reason == "true_promotion_disabled"


def test_complete_span_and_zero_exclusions_still_cannot_promote_true():
    report = _report(
        [
            _query("own_root_tip", "blade_1_root", "blade_1_tip", "separated"),
            _query("interblade", "blade_1_root", "blade_2_tip", "separated"),
            _query("hub", "blade_1_tip", "hub_envelope", "separated"),
        ],
        station_span_complete=True,
        excluded_regions={"root_radial_width_m": 0.0, "hinge_half_width_m": 0.0},
        modeled_surface_status="separated",
    )
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is None
    assert decision.interblade_clearance.value is None


def test_contact_only_unknown_at_zero_clearance_stays_none():
    report = _report(
        [_query(
            "own_root_tip", "blade_1_root", "blade_1_tip", "unknown",
            contact_status="intersecting",
            intervals=[_interval("unknown", contact_status="intersecting")],
        )],
        request={"inputs": {"required_clearance_m": 0.0, "end_angle_deg": -10.0}},
    )
    decision = _values(_policy(required_clearance_m=0.0), report)
    assert decision.surface_path_clearance.value is None
    assert decision.surface_path_clearance.reason == "contact_only_unresolved"


def test_rounded_pose_contact_stays_none():
    report = _report([_query(
        "interblade", "blade_1_root", "blade_2_tip", "unknown",
        contact_status="rounded_pose_contact",
        intervals=[_interval("unknown", contact_status="rounded_pose_contact")],
    )])
    decision = _values(_policy(), report)
    assert decision.interblade_clearance.value is None
    assert decision.interblade_clearance.reason == "contact_only_unresolved"
    assert decision.surface_path_clearance.value is None


@pytest.mark.parametrize("reported", [0.0, 0.002])
def test_threshold_mismatch_either_direction_returns_none(reported):
    report = _report(
        [_query("own_root_tip", "blade_1_root", "blade_1_tip", "violation")],
        request={"inputs": {"required_clearance_m": reported, "end_angle_deg": -10.0}},
    )
    decision = _values(_policy(required_clearance_m=0.001), report)
    assert decision.surface_path_clearance.value is None
    assert decision.interblade_clearance.value is None
    assert decision.surface_path_clearance.reason == "clearance_threshold_mismatch"


def test_motion_mismatch_returns_none():
    report = _report(
        [_query("interblade", "blade_1_root", "blade_2_tip", "violation")],
        request={"motion": "asynchronous_independent_blades"},
    )
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is None
    assert decision.interblade_clearance.value is None
    assert decision.surface_path_clearance.reason == "motion_scope_mismatch"


@pytest.mark.parametrize("query", [
    _query("own_root_tip", "blade_1_root", "blade_2_tip", "separated"),
    _query("interblade", "blade_1_root", "blade_1_tip", "violation"),
    _query("hub", "blade_1_root", "blade_1_tip", "violation"),
])
def test_query_family_pair_contradiction_aborts(query):
    with pytest.raises(ClearancePolicyError):
        decide_negative_clearance(_policy(), _report([query]))


def test_violation_without_usable_witness_aborts():
    report = _report([_query(
        "own_root_tip", "blade_1_root", "blade_1_tip", "violation",
        intervals=[_interval(witness_clearance_m=None, witness_angle_rad=None)],
    )])
    with pytest.raises(ClearancePolicyError):
        decide_negative_clearance(_policy(), report)


def test_witness_outside_candidate_path_aborts():
    report = _report([_query(
        "interblade", "blade_1_root", "blade_2_root", "violation",
        intervals=[_interval(witness_angle_rad=0.2)],
    )])
    with pytest.raises(ClearancePolicyError):
        decide_negative_clearance(_policy(), report)


def test_binding_hub_alone_is_not_finite_hub_proof():
    report = _report(
        [_query("hardware_surface", "blade_1_root", "named_hub", "violation")],
        request={"hardware": _hardware({"name": "named_hub", "binding": "hub", "geometry": {"kind": "convex_polyhedron"}})},
    )
    decision = _values(_policy(), report)
    assert decision.surface_path_clearance.value is None
