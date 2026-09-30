"""Negative regressions for the four PR-C harness review gaps.

These tests use the real case helpers and inputs. They do not add xfail or
skip, and they do not weaken a numerical threshold.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from pyfoldable.dynamics.coupled_transient import CoupledSolverControls
from pyfoldable.dynamics.cmm2_coupled_transient import Cmm2TransientFailure
from tests.verification import cmm2_prc_evidence as evidence
import tests.verification.test_cmm2_numerical_verification as prc


def test_pr_sha_is_not_the_checkout(monkeypatch, tmp_path) -> None:
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"pull_request": {"head": {"sha": "a" * 40}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    record = evidence.provenance_record()
    assert record["pr_source_head"] == "a" * 40
    assert record["git_rev_parse_head"] != "a" * 40
    assert record["evidence_checkout_head"] == record["git_rev_parse_head"]
    assert record["evidence_checkout_head"] != record["pr_source_head"]
    assert "python_version" in record
    assert "numpy_version" in record
    assert "scipy_version" in record
    assert "worktree_dirty" in record


def test_dirty_checkout_is_separate_from_head() -> None:
    record = evidence.provenance_record()
    assert record["evidence_checkout_head"] == record["git_rev_parse_head"]
    assert isinstance(record["worktree_dirty"], bool)
    assert "dirty_paths" in record
    if record["worktree_dirty"]:
        assert record["dirty_paths"]
        assert record["evidence_checkout_head"]


def test_nan_sample_cannot_collapse_to_a_passing_ratio() -> None:
    controls = CoupledSolverControls()

    class Sample:
        def __init__(self, time_s, theta, rate, omega):
            self.time_s = time_s
            self.theta_rad = theta
            self.theta_dot_rad_s = rate
            self.omega_rad_s = omega

    finite = Sample(0.0, -0.4, 0.0, 40.0)
    poisoned = Sample(0.01, float("nan"), 0.0, 40.0)
    worst = prc._worst_sample(
        controls,
        [finite, poisoned],
        lambda _time: (-0.4, 0.0, 40.0),
    )
    assert worst["valid"] is False
    assert "nonfinite" in worst["reason"]
    assert worst["e"] is None


def test_nan_reference_component_cannot_pass_stabilization(monkeypatch) -> None:
    class _Solution:
        def __init__(self, values):
            self._values = values

        def sol(self, _time):
            return self._values

    def fake_dop853(_rhs, _y0, _t1, _controls, level):
        if level == "A":
            return _Solution([float("nan"), 0.0, 40.0]), None
        return _Solution([-0.4, 0.0, 40.0]), None

    monkeypatch.setattr(prc, "_dop853", fake_dop853)
    metrics = prc._stabilization_metrics(
        lambda _time, _state: (0.0, 0.0, 0.0),
        (-0.4, 0.0, 40.0),
        [0.0],
        CoupledSolverControls(),
    )
    assert metrics["stabilized"] is False
    assert "nonfinite" in metrics["reason"]
    assert metrics["max_abs_A_minus_B_over_S"] is None
    json.dumps(
        {"reason": metrics["reason"], "ratio": metrics["max_abs_A_minus_B_over_S"]},
        allow_nan=False,
    )


def test_quadrature_reported_error_a_blocks_pass() -> None:
    reliable, reason = prc._quadrature_is_reliable(1.0, float("nan"), 1.0, 0.0)
    assert reliable is False
    assert reason == "QUADRATURE REFERENCE NOT RELIABLE"
    cleaned, reasons = evidence.json_safe({"error_a": float("inf"), "reason": reason})
    assert cleaned["error_a"] is None
    assert reasons
    assert cleaned["reason"] == "QUADRATURE REFERENCE NOT RELIABLE"


def test_duration_drift_is_rejected_before_the_production_call() -> None:
    system = prc._system(2)
    called = {"production": False}

    def production():
        called["production"] = True

    with pytest.raises(AssertionError, match="before measurement"):
        evidence.freeze_case_before_measurement(
            "C2V-02",
            system=system,
            controls=CoupledSolverControls(),
            executed_inputs={"duration_s": 0.03, "theta_rad": -0.4},
            production_call=production,
        )
    assert called["production"] is False


def test_control_drift_is_rejected_before_measurement() -> None:
    system = prc._system(2)
    with pytest.raises(AssertionError, match="before measurement"):
        evidence.freeze_case_before_measurement(
            "C2V-02",
            system=system,
            controls=CoupledSolverControls(rtol=1.0e-5),
            executed_inputs={"duration_s": 0.02, "theta_rad": -0.4},
            production_call=lambda: None,
        )


def test_mechanism_drift_is_rejected_before_measurement() -> None:
    system = prc._system(2, prc._mechanism(spring_stiffness_nm_rad=0.02))
    with pytest.raises(AssertionError, match="before measurement"):
        evidence.freeze_case_before_measurement(
            "C2V-02",
            system=system,
            controls=CoupledSolverControls(),
            executed_inputs={"duration_s": 0.02, "theta_rad": -0.4},
            production_call=lambda: None,
        )


def test_c2v08_unexpected_callback_records_and_reraises() -> None:
    saved = dict(evidence.EVIDENCE)
    evidence.EVIDENCE.clear()
    try:
        with pytest.raises(Cmm2TransientFailure, match="aero evaluator failed"):
            prc.run_c2v08_with_callback_fault(RuntimeError("injected callback"))
        recorded = evidence.EVIDENCE["C2V-08"]
        assert recorded["classification"] == "FAIL"
        assert "injected callback" in recorded["record_reason"]
        assert recorded["metrics"]["failure_layers"]
    finally:
        evidence.EVIDENCE.clear()
        evidence.EVIDENCE.update(saved)


def test_shared_manufactured_failure_records_c2v03_and_c2v05(monkeypatch) -> None:
    saved = dict(evidence.EVIDENCE)
    evidence.EVIDENCE.clear()
    prc._manufactured_measurement.value = None
    prc._manufactured_measurement.error = None

    def boom(*_args, **_kwargs):
        raise Cmm2TransientFailure("injected manufactured failure")

    monkeypatch.setattr(prc, "_run", boom)
    try:
        with pytest.raises(Cmm2TransientFailure, match="injected manufactured failure"):
            prc.test_c2v03_manufactured_trajectory()
        with pytest.raises(Cmm2TransientFailure, match="injected manufactured failure"):
            prc.test_c2v05_dop853_reference()
        assert evidence.EVIDENCE["C2V-03"]["classification"] == "FAIL"
        assert evidence.EVIDENCE["C2V-05"]["classification"] == "FAIL"
        assert "injected manufactured failure" in evidence.EVIDENCE["C2V-03"]["record_reason"]
        assert "injected manufactured failure" in evidence.EVIDENCE["C2V-05"]["record_reason"]
    finally:
        prc._manufactured_measurement.value = None
        prc._manufactured_measurement.error = None
        evidence.EVIDENCE.clear()
        evidence.EVIDENCE.update(saved)


def test_late_assertion_does_not_leave_a_pass_record() -> None:
    saved = dict(evidence.EVIDENCE)
    evidence.EVIDENCE.clear()
    system = prc._system(2)
    theta, rate, omega = -0.3, 0.1, 40.0

    def measure(partial):
        produced = prc._production_acceleration(
            system, theta, rate, omega, 0.04, 0.001, -0.02, 0.0
        )
        partial["metrics"] = {"omega_dot_rad_s2": produced[0]}
        partial["premeasurement_digest"] = "frozen-before-call"
        return {
            "primary_evidence_class": "CROSS_MODEL",
            "purpose": "late assertion regression",
            "classification": "PASS",
            "oracle_method": "real C2V-06 state",
            "independence_limit": "regression",
            "fixture_digest": "frozen-before-call",
            "premeasurement_digest": "frozen-before-call",
            "controls": evidence.CONTRACT_CONTROLS,
            "metrics": partial["metrics"],
            "units": {"omega_dot_rad_s2": "rad/s^2"},
            "reference_stabilization": None,
            "acceptance_rule": "late gate",
            "threshold_basis": "regression",
            "limitations": "regression",
            "executed_inputs": {
                "theta_rad": theta,
                "theta_dot_rad_s": rate,
                "omega_rad_s": omega,
            },
        }

    try:
        with pytest.raises(AssertionError, match="late real gate"):
            evidence.execute_measured_case(
                "C2V-06",
                measure,
                checks=[lambda _payload: (_ for _ in ()).throw(AssertionError("late real gate"))],
            )
        assert evidence.EVIDENCE["C2V-06"]["classification"] == "FAIL"
        assert "late real gate" in evidence.EVIDENCE["C2V-06"]["record_reason"]
        assert "omega_dot_rad_s2" in evidence.EVIDENCE["C2V-06"]["metrics"]
        json.dumps(evidence.EVIDENCE["C2V-06"], allow_nan=False)
    finally:
        evidence.EVIDENCE.clear()
        evidence.EVIDENCE.update(saved)
