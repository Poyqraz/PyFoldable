"""Harness regressions for PR-C evidence capture.

These tests do not relax a numerical gate. They fail before the evidence
writer records a critical failure, keeps C2V-05 when C2V-03 fails, and
freezes the manifest to the inputs that will actually be used.
"""

from __future__ import annotations

import json
import math

import pytest

from tests.verification import cmm2_prc_evidence as evidence


def test_manifest_freeze_covers_contract_inputs_before_measurement() -> None:
    manifest = evidence.MANIFEST
    assert manifest["manifest_id"] == "prc_critical_fixture_manifest_v1"
    assert evidence.MANIFEST_SHA == evidence.sha256(evidence.canonical(manifest))
    assert "max_state_e" not in evidence.canonical(manifest)
    for case_id in [f"C2V-{index:02d}" for index in range(1, 11)]:
        assert case_id in manifest["cases"]
    assert [row["id"] for row in manifest["c2v09_candidates"]] == [
        f"C2V09-{index:02d}" for index in range(28)
    ]
    controls = manifest["shared"]["controls"]
    assert controls["rtol"] == 1.0e-6
    assert controls["angle_atol_rad"] == 1.0e-8
    assert controls["hinge_velocity_atol_rad_s"] == 1.0e-8
    assert controls["shaft_speed_atol_rad_s"] == 1.0e-6
    assert controls["max_step_s"] == 0.002
    assert controls["max_duration_s"] == 2.0
    assert controls["max_samples"] == 5000
    assert controls["max_rhs_evaluations"] == 12000
    assert controls["max_input_knots"] == 256
    assert manifest["cases"]["C2V-02"]["duration_s"] == 0.02
    mutated = json.loads(evidence.canonical(manifest))
    mutated["cases"]["C2V-02"]["duration_s"] = 0.03
    assert evidence.sha256(evidence.canonical(mutated)) != evidence.MANIFEST_SHA
    used = evidence.executed_fixture("C2V-02", {"q_theta_nm": -0.03290732868930436})
    changed = evidence.executed_fixture("C2V-02", {"q_theta_nm": 0.0})
    assert evidence.fixture_digest(used) != evidence.fixture_digest(changed)
    assert used["manifest_duration_s"] == 0.02


def _restore_evidence():
    saved = dict(evidence.EVIDENCE)
    evidence.EVIDENCE.clear()
    return saved


def _put_back(saved: dict[str, object]) -> None:
    evidence.EVIDENCE.clear()
    evidence.EVIDENCE.update(saved)


def test_fail_record_remains_after_assertion(tmp_path) -> None:
    saved = _restore_evidence()
    try:
        _fail_record_body(tmp_path)
    finally:
        _put_back(saved)


def _fail_record_body(tmp_path) -> None:
    evidence.commit_case(
        "C2V-02",
        {
            "primary_evidence_class": "INDEPENDENT_NUMERICAL",
            "purpose": "harness fail retention",
            "classification": "FAIL",
            "fixture_identity": "prc_critical_fixture_manifest_v1:C2V-02",
            "fixture_digest": evidence.fixture_digest(
                evidence.executed_fixture("C2V-02", {"q_theta_nm": 0.0})
            ),
            "oracle_method": "harness",
            "independence_limit": "harness",
            "controls": evidence.MANIFEST["shared"]["controls"],
            "metrics": {"max_state_e": 1.25},
            "units": {"max_state_e": "1"},
            "reference_stabilization": None,
            "acceptance_rule": "max e_j <= 1",
            "threshold_basis": "section 7",
            "limitations": "harness",
        },
    )
    with pytest.raises(AssertionError):
        assert evidence.EVIDENCE["C2V-02"]["classification"] == "PASS"
    path = tmp_path / "evidence.json"
    evidence.write_evidence(path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["cases"]["C2V-02"]["classification"] == "FAIL"
    assert math.isfinite(loaded["cases"]["C2V-02"]["metrics"]["max_state_e"])


def test_c2v03_assertion_does_not_drop_c2v05(tmp_path) -> None:
    saved = _restore_evidence()
    try:
        _c2v05_survives(tmp_path)
    finally:
        _put_back(saved)


def _c2v05_survives(tmp_path) -> None:
    common = {
        "primary_evidence_class": "INDEPENDENT_NUMERICAL",
        "fixture_identity": "prc_critical_fixture_manifest_v1:C2V-03",
        "fixture_digest": evidence.fixture_digest(
            evidence.executed_fixture("C2V-03", {})
        ),
        "oracle_method": "DOP853",
        "independence_limit": "harness",
        "controls": evidence.MANIFEST["shared"]["controls"],
        "metrics": {
            "max_abs_A_minus_B_over_S": 0.001,
            "max_abs_A_minus_B_over_0_1_S": 0.01,
            "max_state_e": 2.4,
        },
        "units": {
            "max_abs_A_minus_B_over_S": "1",
            "max_abs_A_minus_B_over_0_1_S": "1",
            "max_state_e": "1",
        },
        "reference_stabilization": {
            "max_abs_A_minus_B_over_S_limit": 0.1,
            "max_abs_A_minus_B_over_0_1_S_limit": 1.0,
            "stabilized": True,
        },
        "acceptance_rule": "section 7 after DOP853 A/B stabilization",
        "threshold_basis": "max e_j <= 1 and abs(A-B) <= 0.1 S_j",
        "limitations": "harness",
        "classification": "FAIL",
    }
    evidence.commit_case("C2V-03", {**common, "purpose": "manufactured trajectory"})
    evidence.commit_case(
        "C2V-05",
        {
            **common,
            "purpose": "DOP853 comparison",
            "fixture_identity": "prc_critical_fixture_manifest_v1:C2V-05",
            "fixture_digest": evidence.fixture_digest(
                evidence.executed_fixture("C2V-05", {})
            ),
        },
    )
    with pytest.raises(AssertionError):
        assert evidence.EVIDENCE["C2V-03"]["classification"] == "PASS"
    assert evidence.EVIDENCE["C2V-05"]["classification"] == "FAIL"
    assert "stabilization_ratio" not in evidence.canonical(evidence.EVIDENCE["C2V-05"])
    path = tmp_path / "evidence.json"
    evidence.write_evidence(path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["cases"]["C2V-05"]["metrics"]["max_abs_A_minus_B_over_S"] == 0.001


def test_nonfinite_metrics_cannot_become_pass() -> None:
    cleaned, reasons = evidence.json_safe({"eta": math.nan, "bound": math.inf, "ok": 1.0})
    assert cleaned["eta"] is None
    assert cleaned["bound"] is None
    assert cleaned["ok"] == 1.0
    assert reasons
    json.dumps(cleaned, allow_nan=False)


def test_unmeasured_cases_are_not_passed() -> None:
    saved = _restore_evidence()
    try:
        coverage = evidence.coverage_record()
        for case_id in ("C2V-09", "C2V-10", "C2V-11", "C2V-12"):
            assert coverage[case_id]["coverage"] == "NOT_MEASURED"
            assert coverage[case_id]["classification"] is None
            assert coverage[case_id]["classification"] != "CHARACTERIZATION ONLY"
    finally:
        _put_back(saved)
