"""PY-06D1: analytic observations, explicit provenance and leakage guards."""
from dataclasses import asdict, replace
import json
import math

import pytest

from pyfoldable.core.mechanism_observation import (
    ObservationProvenance, MechanismObservationRun, ObservedContact,
    compare_mechanism_observations, partition_mechanism_runs,
)
from pyfoldable.dynamics.mechanism_transient import (
    DriveHistory, MechanismParameters, SolverControls, TransientRequest,
    sample_mechanism_transient, solve_mechanism_transient,
)


def run_fixture(**changes):
    p = MechanismParameters(0.2, 0.1, 0.003, 0.0, 0.3, 0.0, 0.0, -2.0, 2.0)
    request = TransientRequest(p, DriveHistory((0.0, 0.4), (0.0, 0.0), (0.0, 0.0)),
                               0.4, 0.0, SolverControls(max_step_s=0.07))
    t = (0.0, 0.017, 0.101, 0.253, 0.4)
    provenance = ObservationProvenance(
        physical_run_id="fixture/run-1", raw_data_sha256="a" * 64,
        design_sha256="b" * 64, blade_id="blade-1", source="analytic oscillator fixture",
        classification="software_fixture", angle_calibration_sha256="c" * 64,
        synchronization_source="analytic common clock", initial_state_source="analytic initial state",
        initial_state_method="declared_fixture", parameter_source="analytic oscillator parameters",
        torque_source="controlled zero fixture", torque_evidence="controlled_zero",
        clock_basis="synchronized_elapsed_seconds", angle_convention="relative_hinge_rad_ccw_z_zero_radial_unwrapped",
        rpm_processing="unfiltered_piecewise_linear", sampling_policy_source="fixture sampling policy",
        max_drive_gap_s=0.4, max_observation_gap_s=0.2, clock_uncertainty_s=0.0,
    )
    values = dict(request=request, provenance=provenance, time_s=t,
                  angle_rad=tuple(0.4 * math.cos(10 * x) for x in t),
                  standard_uncertainty_rad=(0.001,) * len(t), observed_contact=None)
    values.update(changes)
    return MechanismObservationRun(**values)


def test_dense_observations_match_analytic_without_changing_original_solution():
    run = run_fixture()
    sampled = sample_mechanism_transient(run.request, run.time_s)
    assert sampled.result == solve_mechanism_transient(run.request)
    assert sampled.time_s == run.time_s
    assert sampled.angle_rad == pytest.approx(run.angle_rad, abs=2e-8)
    report = compare_mechanism_observations(run)
    assert report.status == "screening_only"
    assert report.rmse_rad < 2e-8
    assert report.excluded_time_s == ()
    assert report.physical_qualification is False
    assert report.parameter_fitting_performed is False
    assert report.measurement_readiness == "pending_no_measured_evidence"
    assert report.uncertainty_assessment == "indeterminate_model_drive_and_clock_uncertainty_unpropagated"
    assert json.loads(report.request_json)["run"] == json.loads(json.dumps(asdict(run)))


def test_residual_sign_units_and_input_hash_include_observations_and_sources():
    run = run_fixture()
    shifted = replace(run, angle_rad=tuple(x + 0.02 for x in run.angle_rad))
    result = compare_mechanism_observations(shifted)
    assert result.residual_rad == pytest.approx((-0.02,) * 5, abs=2e-8)
    assert result.rmse_rad == pytest.approx(0.02, abs=2e-8)
    assert result.max_absolute_residual_rad == pytest.approx(0.02, abs=2e-8)
    original = compare_mechanism_observations(run)
    assert original.request_sha256 != result.request_sha256
    changed = replace(run, provenance=replace(run.provenance, synchronization_source="new clock audit"))
    assert compare_mechanism_observations(changed).request_sha256 != original.request_sha256
    with pytest.raises(ValueError, match="stale"):
        compare_mechanism_observations(shifted, expected_request_sha256=original.request_sha256)


@pytest.mark.parametrize("times", [(0.0, 0.0), (-0.1, 0.4), (0.0, 0.5), (0.0, float("nan")), [0.0, 0.4], (False, 0.4)])
def test_sampler_rejects_invalid_times(times):
    with pytest.raises(ValueError):
        sample_mechanism_transient(run_fixture().request, times)


@pytest.mark.parametrize("changes", [
    {"clock_basis": "camera_unsynchronized"}, {"angle_convention": "degrees"},
    {"rpm_processing": "filtered_without_trace"}, {"torque_evidence": "missing"},
    {"initial_state_method": "fit_from_full_holdout"}, {"raw_data_sha256": "bad"},
    {"physical_run_id": " "}, {"clock_uncertainty_s": -1.0},
    {"max_drive_gap_s": True}, {"classification": "literature_as_measurement"},
])
def test_provenance_rejects_unsupported_semantics(changes):
    with pytest.raises(ValueError):
        replace(run_fixture().provenance, **changes)


def test_gaps_window_coverage_uncertainty_and_unknown_torque_fail_closed():
    run = run_fixture()
    for changed in (
        dict(provenance=replace(run.provenance, max_drive_gap_s=0.3)),
        dict(provenance=replace(run.provenance, max_observation_gap_s=0.1)),
        dict(time_s=(0.001,) + run.time_s[1:]),
        dict(standard_uncertainty_rad=(-1.0,) * 5),
        dict(angle_rad=run.angle_rad[:-1]),
        dict(request=replace(run.request, drive=replace(run.request.drive, applied_hinge_torque_nm=(0.0, 1.0)))),
    ):
        with pytest.raises(ValueError):
            replace(run, **changed)
    with pytest.raises(ValueError, match="independent"):
        replace(run.provenance, classification="measured")


def test_terminal_contact_retains_excluded_observations_instead_of_truncating_success():
    run = run_fixture()
    p = replace(run.request.parameters, spring_stiffness_nm_rad=0.0, upper_stop_rad=0.6)
    request = replace(run.request, parameters=p, initial_angular_velocity_rad_s=1.0)
    result = compare_mechanism_observations(replace(run, request=request))
    assert result.status == "blocked_incomplete_prediction"
    assert result.compared_time_s == (0.0, 0.017, 0.101)
    assert result.excluded_time_s == (0.253, 0.4)
    assert result.predicted_contact.time_s == pytest.approx(0.2)
    assert result.contact_assessment == "predicted_contact_not_observed"
    assert result.rmse_rad is None  # no full-window aggregate hiding loss of coverage


def test_observed_event_is_not_ignored_when_solver_does_not_contact():
    run = replace(run_fixture(), observed_contact=ObservedContact("upper", 0.4))
    result = compare_mechanism_observations(run)
    assert result.status == "screening_event_mismatch"
    assert result.contact_assessment == "observed_contact_not_predicted"
    with pytest.raises(ValueError):
        replace(run, observed_contact=ObservedContact("upper", 0.3))


def test_partition_rejects_run_aliases_raw_aliases_and_different_designs():
    train = run_fixture()
    other = replace(train, provenance=replace(train.provenance, physical_run_id="fixture/run-2", raw_data_sha256="d" * 64))
    split = partition_mechanism_runs((train,), (other,))
    assert split.training_run_ids == ("fixture/run-1",)
    assert split.holdout_run_ids == ("fixture/run-2",)
    assert split.all_runs_declared_measured is False
    for invalid in (train,
                    replace(other, provenance=replace(other.provenance, raw_data_sha256=train.provenance.raw_data_sha256)),
                    replace(other, provenance=replace(other.provenance, design_sha256="e" * 64))):
        with pytest.raises(ValueError):
            partition_mechanism_runs((train,), (invalid,))
    with pytest.raises(ValueError):
        partition_mechanism_runs((), (other,))


def test_signed_rpm_ramp_and_knot_sampling_preserve_inertial_angle():
    run = run_fixture()
    # R=0, no applied/spring/damping torque: theta + integral(Omega) is constant.
    request = replace(run.request,
                      parameters=replace(run.request.parameters, spring_stiffness_nm_rad=0.0),
                      drive=DriveHistory((0.0, 0.2, 0.4), (0.0, 30.0, -30.0), (0.0, 0.0, 0.0)))
    times = (0.0, 0.037, 0.2, 0.333, 0.4)
    def theta(t):
        integral = (0.5 * (math.pi / 0.2) * t**2 if t <= 0.2 else
                    0.1 * math.pi + math.pi * (t - 0.2) - 5 * math.pi * (t - 0.2)**2)
        return 0.4 - integral
    result = sample_mechanism_transient(request, times)
    assert result.time_s == times
    assert result.angle_rad == pytest.approx(tuple(theta(t) for t in times), abs=1e-9)
    assert result.result == solve_mechanism_transient(request)
    translated = replace(request, drive=replace(request.drive, time_s=(10.0, 10.2, 10.4)))
    shifted_times = tuple(10 + t for t in times)
    shifted = sample_mechanism_transient(translated, shifted_times)
    assert shifted.time_s == shifted_times
    assert shifted.angle_rad == pytest.approx(result.angle_rad, abs=1e-9)


def test_dense_sampling_never_continues_past_an_internal_out_and_back_contact():
    run = run_fixture()
    p = replace(run.request.parameters, spring_stiffness_nm_rad=0.0, upper_stop_rad=0.6)
    request = replace(run.request, parameters=p, initial_angular_velocity_rad_s=4.0,
                      drive=DriveHistory((0.0, 0.4), (0.0, 0.0), (-0.12, -0.12)),
                      controls=SolverControls(rtol=1e-3, atol=1e-6, max_step_s=0.4))
    result = sample_mechanism_transient(request, (0.0, 0.05, 0.1, 0.2, 0.4))
    assert result.result.contact is not None
    assert result.time_s[-1] <= result.result.contact.time_s
    assert 0.4 not in result.time_s


def test_measured_partition_is_only_declared_readiness_and_freezes_semantics():
    run = run_fixture()
    measured = replace(run, provenance=replace(run.provenance, classification="measured",
                                               initial_state_method="independent_measurement"))
    other = replace(measured, provenance=replace(measured.provenance, physical_run_id="run-2", raw_data_sha256="d" * 64))
    partition = partition_mechanism_runs((measured,), (other,))
    assert partition.all_runs_declared_measured
    result = compare_mechanism_observations(measured)
    assert result.measurement_readiness == "measured_declared_unverified"
    assert result.physical_qualification is False
    changed = replace(other, standard_uncertainty_rad=(0.2,) * 5)
    assert partition_mechanism_runs((measured,), (changed,)).partition_sha256 != partition.partition_sha256
    assert partition_mechanism_runs((other,), (measured,)).partition_sha256 != partition.partition_sha256


def test_contact_roundoff_is_numerically_indeterminate_without_extrapolation():
    run = run_fixture()
    request = replace(run.request,
                      parameters=replace(run.request.parameters, spring_stiffness_nm_rad=0.0,
                                         upper_stop_rad=0.3 + 0.7 * 0.5),
                      initial_angle_rad=0.3, initial_angular_velocity_rad_s=0.7,
                      drive=DriveHistory((0.0, 0.5), (0.0, 0.0), (0.0, 0.0)))
    run = replace(run, request=request, time_s=(0.0, 0.25, 0.5),
                  angle_rad=(0.3, 0.475, 0.65), standard_uncertainty_rad=(0.001,) * 3,
                  provenance=replace(run.provenance, max_drive_gap_s=0.5, max_observation_gap_s=0.25),
                  observed_contact=ObservedContact("upper", 0.5))
    result = compare_mechanism_observations(run)
    assert result.status == "indeterminate_contact_boundary"
    assert result.contact_assessment == "indeterminate_contact_boundary"
    assert result.excluded_time_s == (0.5,)
    assert result.rmse_rad is None
    assert result.compared_time_s[-1] < result.predicted_contact.time_s
