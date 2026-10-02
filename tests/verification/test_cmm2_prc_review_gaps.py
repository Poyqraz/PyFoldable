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


def _equilibrium_inputs():
    system = prc._system(2)
    q_phi, q_theta = prc._target_loads(system, -.4, 0., 40., 0., 0., .05, .001)
    return dict(duration_s=.02, theta_rad=-.4, theta_dot_rad_s=0., omega_rad_s=40., Qm_nm=.05, Qh_nm=.001,
                Q_phi_nm=q_phi, q_theta_nm=q_theta, actuation_knots_s=[0., .02], actuation_torques_nm=[.001, .001])


@pytest.mark.parametrize('field,value', [('duration_s', .03), ('q_theta_nm', 0.), ('Q_phi_nm', -.04), ('theta_dot_rad_s', .01)])
def test_duration_and_load_drift_are_rejected_before_production(field, value):
    inputs = _equilibrium_inputs()
    system = prc._system(2)
    evidence.freeze_case_before_measurement('C2V-02', system=system, controls=CoupledSolverControls(), executed_inputs=inputs)
    called = []
    with pytest.raises(AssertionError, match=field):
        evidence.freeze_case_before_measurement('C2V-02', system=system, controls=CoupledSolverControls(), executed_inputs={**inputs, field: value}, production_call=lambda: called.append(1))
    assert not called


@pytest.mark.parametrize('kind,field', [('control', 'controls.rtol'), ('mechanism', 'mechanism.spring_nm_rad')])
def test_control_and_mechanism_drift_after_valid_baseline(kind, field):
    inputs = _equilibrium_inputs()
    evidence.freeze_case_before_measurement('C2V-02', system=prc._system(2), controls=CoupledSolverControls(), executed_inputs=inputs)
    called = []
    with pytest.raises(AssertionError, match=field):
        evidence.freeze_case_before_measurement('C2V-02',
            system=prc._system(2, prc._mechanism(spring_stiffness_nm_rad=.02)) if kind == 'mechanism' else prc._system(2),
            controls=CoupledSolverControls(rtol=1.e-5) if kind == 'control' else CoupledSolverControls(), executed_inputs=inputs,
            production_call=lambda: called.append(1))
    assert not called


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
        digests = []
        for case_id in ('C2V-03', 'C2V-05'):
            row = evidence.EVIDENCE[case_id]
            snapshot = row['premeasurement_snapshots'][0]
            assert snapshot['case_id'] == case_id
            assert row['premeasurement_digest'] == snapshot['premeasurement_digest']
            unhashed = {k:v for k,v in snapshot.items() if k != 'premeasurement_digest'}
            assert row['premeasurement_digest'] == evidence.fixture_digest(unhashed)
            digests.append(row['premeasurement_digest'])
        assert len(set(digests)) == 2
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


@pytest.mark.parametrize('case_id,entry', [
    ('C2V-01', 'test_c2v01_represented_algebra'),
    ('C2V-02', 'test_c2v02_exact_equilibrium'),
    ('C2V-04', 'test_c2v04_independent_work'),
    ('C2V-06', 'test_c2v06_zero_hinge_limit'),
    ('C2V-07', 'test_c2v07_manufactured_contact'),
    ('C2V-08', 'test_c2v08_fail_closed_layers'),
])
@pytest.mark.parametrize('fault', ['setup', 'freeze'])
def test_real_entry_early_failure_is_written(case_id, entry, fault, monkeypatch, tmp_path):
    saved = dict(evidence.EVIDENCE)
    evidence.EVIDENCE.clear()
    called = []
    def boom(*args, **kwargs):
        raise RuntimeError(f'injected {fault}')
    def production(*args, **kwargs):
        called.append(True)
        raise AssertionError('production must not run')
    monkeypatch.setattr(prc, '_system' if fault == 'setup' else 'freeze_case_before_measurement', boom)
    monkeypatch.setattr(prc, '_production_acceleration', production)
    monkeypatch.setattr(prc, '_run', production)
    try:
        with pytest.raises(RuntimeError, match=f'injected {fault}'):
            if case_id == 'C2V-07':
                getattr(prc, entry)(monkeypatch)
            else:
                getattr(prc, entry)()
        path = tmp_path / 'early-fail.json'
        evidence.write_evidence(path)
        row = json.loads(path.read_text())['cases'][case_id]
        assert row['classification'] == 'FAIL'
        assert f'injected {fault}' in row['record_reason']
        assert row['pre_result_freeze_status'] != 'frozen_before_measurement'
        assert row['premeasurement_digest'] is None
        assert not called
    finally:
        evidence.EVIDENCE.clear()
        evidence.EVIDENCE.update(saved)


@pytest.mark.parametrize('subcase,inputs,field,value', [
    ('fold', dict(duration_s=.5, theta_rad=-1.2, theta_dot_rad_s=-1., omega_rad_s=40., Qm_nm=.04, Qh_nm=0., theta_rate_rad_s=-1., theta_ddot_rad_s2=0., omega_dot_rad_s2=0., load_formula='zero_acceleration_target'), 'duration_s', .4),
    ('speed', dict(duration_s=.2, theta_rad=-.3, theta_dot_rad_s=0., omega_rad_s=10., Qm_nm=.04, Qh_nm=0., load_formula='unreachable_counting_callback'), 'omega_rad_s', 11.),
    ('budget', dict(duration_s=.2, theta_rad=-.3, theta_dot_rad_s=.1, omega_rad_s=40., Qm_nm=.04, Qh_nm=0., Q_phi_nm=-.02, q_theta_nm=.004), 'q_theta_nm', .005),
    ('hard', dict(duration_s=.2, theta_rad=-.3, theta_dot_rad_s=.1, omega_rad_s=40., Qm_nm=.04, Qh_nm=0., load_formula='raises_Cmm2TransientFailure', failure_message='hard failure'), 'theta_dot_rad_s', .2),
])
def test_each_c2v08_baseline_then_single_field_drift(subcase, inputs, field, value):
    system = prc._system(2, prc._mechanism(lower_stop_rad=-2., upper_stop_rad=.5)) if subcase == 'fold' else prc._system(2)
    controls = prc._controls(max_rhs_evaluations=1) if subcase == 'budget' else prc._controls()
    inputs = {**inputs, "actuation_knots_s": [0., inputs["duration_s"]], "actuation_torques_nm": [0., 0.]}
    evidence.freeze_case_before_measurement('C2V-08', system=system, controls=controls, executed_inputs=inputs, subcase=subcase)
    mutations = {field: value, 'duration_s': inputs['duration_s'] + .01,
                 'theta_rad': inputs['theta_rad'] + .01, 'Qm_nm': .05,
                 'Qh_nm': .001, 'actuation_knots_s': [0., inputs['duration_s'] + .01]}
    for drift_field, drift_value in mutations.items():
        called = []
        with pytest.raises(AssertionError, match=drift_field):
            evidence.freeze_case_before_measurement('C2V-08', system=system, controls=controls,
                executed_inputs={**inputs, drift_field: drift_value}, subcase=subcase, production_call=lambda: called.append(1))
        assert not called
    called = []
    from dataclasses import replace
    with pytest.raises(AssertionError, match='controls.max_rhs_evaluations'):
        evidence.freeze_case_before_measurement('C2V-08', system=system,
            controls=replace(controls,max_rhs_evaluations=2 if subcase == "budget" else 11999),
            executed_inputs=inputs,subcase=subcase,production_call=lambda:called.append(1))
    assert not called


def test_c2v01_freezes_all_six_rows_before_first_acceleration(monkeypatch):
    saved = dict(evidence.EVIDENCE)
    evidence.EVIDENCE.clear()
    frozen = []
    original = prc.freeze_case_before_measurement
    def capture(*args, **kwargs):
        snapshot = original(*args, **kwargs)
        frozen.append(snapshot)
        return snapshot
    def production(*args, **kwargs):
        assert len(frozen) == 6
        raise RuntimeError('after all row freezes')
    monkeypatch.setattr(prc, 'freeze_case_before_measurement', capture)
    monkeypatch.setattr(prc, '_production_acceleration', production)
    try:
        with pytest.raises(RuntimeError, match='after all row freezes'):
            prc.test_c2v01_represented_algebra()
        row = evidence.EVIDENCE['C2V-01']
        assert len(row['premeasurement_snapshots']) == 6
        assert {(x['mechanism']['blade_count'], tuple(x['executed_inputs']['load_pair_nm'])) for x in row['premeasurement_snapshots']} == {(n,p) for n in (1,2,4) for p in ((-.02,.004),(.015,-.003))}
    finally:
        evidence.EVIDENCE.clear()
        evidence.EVIDENCE.update(saved)


@pytest.mark.parametrize('case_id,inputs,field,value', [
    ('C2V-01', dict(state_rad=[-.4,.2,40.],Qm_nm=.05,Qh_nm=.001,load_pair_nm=[-.02,.004]), 'load_pair_nm', [-.02,.005]),
    ('C2V-06', dict(theta_rad=-.3,theta_dot_rad_s=.1,omega_rad_s=40.,Qa_nm=.02,Q_phi_nm=-.02,q_theta_nm=0.,Qm_nm=.04,Qh_nm=.001), 'Qa_nm', .03),
    ('C2V-07', dict(duration_s=1.,theta_rad=-.2,theta_dot_rad_s=-.4,omega_rad_s=40.,Qm_nm=.04,Qh_nm=0.,theta_rate_rad_s=-.4,theta_ddot_rad_s2=0.,omega_dot_rad_s2=0.,load_formula='zero_acceleration_target',actuation_knots_s=[0.,1.],actuation_torques_nm=[0.,0.]), 'theta_rate_rad_s', -.5),
])
def test_new_case_complete_baseline_then_single_field_drift(case_id, inputs, field, value):
    system = prc._system(2, prc._mechanism(lower_stop_rad=-.5,upper_stop_rad=.2)) if case_id == 'C2V-07' else prc._system(2)
    controls = prc._controls()
    baseline = evidence.freeze_case_before_measurement(case_id, system=system, controls=controls, executed_inputs=inputs)
    assert baseline['executed_inputs'] == inputs
    called = []
    with pytest.raises(AssertionError, match=field):
        evidence.freeze_case_before_measurement(case_id, system=system, controls=controls, executed_inputs={**inputs,field:value}, production_call=lambda:called.append(1))
    assert not called


def test_c2v08_snapshot_covers_all_four_actual_subcases():
    saved = dict(evidence.EVIDENCE)
    evidence.EVIDENCE.clear()
    try:
        prc.test_c2v08_fail_closed_layers()
        row = evidence.EVIDENCE['C2V-08']
        snapshots = row['premeasurement_snapshots']
        assert [x['subcase'] for x in snapshots] == ['fold','speed','budget','hard']
        assert row['premeasurement_digest'] == evidence.fixture_digest({'case_id':'C2V-08','snapshots':snapshots})
        assert row['premeasurement_digest'] != snapshots[0]['premeasurement_digest']
        for snapshot in snapshots:
            unhashed = {k:v for k,v in snapshot.items() if k != 'premeasurement_digest'}
            assert snapshot['premeasurement_digest'] == evidence.fixture_digest(unhashed)
        assert snapshots[2]['controls']['max_rhs_evaluations'] == 1
        assert snapshots[1]['executed_inputs']['omega_rad_s'] == 10.
    finally:
        evidence.EVIDENCE.clear()
        evidence.EVIDENCE.update(saved)


def test_partial_freeze_failure_does_not_claim_complete_freeze(monkeypatch, tmp_path):
    saved = dict(evidence.EVIDENCE)
    evidence.EVIDENCE.clear()
    original = prc.freeze_case_before_measurement
    calls = []
    def failing_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError('second row freeze failed')
        return original(*args, **kwargs)
    monkeypatch.setattr(prc,'freeze_case_before_measurement',failing_second)
    try:
        with pytest.raises(RuntimeError,match='second row freeze failed'):
            prc.test_c2v01_represented_algebra()
        path = tmp_path / 'partial.json'
        evidence.write_evidence(path)
        row = json.loads(path.read_text())['cases']['C2V-01']
        assert row['pre_result_freeze_status'] == 'PARTIALLY_FROZEN'
        assert len(row['premeasurement_snapshots']) == 1
        assert row['metrics']['rows'] == []
    finally:
        evidence.EVIDENCE.clear()
        evidence.EVIDENCE.update(saved)


def test_real_oracle_failure_keeps_production_partial_metrics(monkeypatch, tmp_path):
    saved = dict(evidence.EVIDENCE)
    evidence.EVIDENCE.clear()
    def boom(*args, **kwargs):
        raise RuntimeError('injected algebra oracle')
    monkeypatch.setattr(prc,'_audit_solution',boom)
    try:
        with pytest.raises(RuntimeError,match='injected algebra oracle'):
            prc.test_c2v01_represented_algebra()
        path = tmp_path / 'oracle-fail.json'
        evidence.write_evidence(path)
        row = json.loads(path.read_text())['cases']['C2V-01']
        assert row['classification'] == 'FAIL'
        assert len(row['premeasurement_snapshots']) == 6
        assert row['metrics']['rows'][0]['production_accelerations_rad_s2']
        assert 'injected algebra oracle' in row['record_reason']
    finally:
        evidence.EVIDENCE.clear()
        evidence.EVIDENCE.update(saved)


def test_failed_setup_replaces_previous_case_record(monkeypatch):
    saved = dict(evidence.EVIDENCE)
    try:
        evidence.EVIDENCE['C2V-06'] = {'classification':'PASS','premeasurement_digest':'old-run','metrics':{'stale':1}}
        def boom(*args, **kwargs):
            raise RuntimeError('fresh setup failed')
        monkeypatch.setattr(prc,'_system',boom)
        with pytest.raises(RuntimeError,match='fresh setup failed'):
            prc.test_c2v06_zero_hinge_limit()
        row = evidence.EVIDENCE['C2V-06']
        assert row['classification'] == 'FAIL'
        assert row['premeasurement_digest'] is None
        assert row['pre_result_freeze_status'] == 'NOT_FROZEN'
        assert row['metrics'] is None
    finally:
        evidence.EVIDENCE.clear()
        evidence.EVIDENCE.update(saved)
