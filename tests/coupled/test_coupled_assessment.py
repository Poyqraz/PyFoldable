"""Engineering reading of coupled deployment records (no solver): contact events, impulse and energy
checks, shaft angular-momentum exchange and the classification of outputs."""
import math
import shutil
from pathlib import Path

import pytest

from pyfoldable.coupled import assessment, postprocess

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "coupled"
MECH = {"distal_mass_kg": 0.03, "distal_cg_from_hinge_m": 0.055, "distal_inertia_cg_kg_m2": 3.0e-5,
        "stop_stiffness_nm_per_rad": 500.0, "stop_restitution": 0.5, "spring_nm_per_rad": 0.0}
JH = 3.0e-5 + 0.03 * 0.055 ** 2
RH, RPM, DT = 0.27, 2400.0, 1.0e-4


def _row(rates, contact, torques, *, theta0=-20.0, drive=None, aero=None):
    """Synthetic one-blade record: window 1-2 latched, then free; torques are the hinge-law torque samples."""
    n = len(rates)
    series = []
    for i in range(n):
        series.append({
            "window": i + 1, "time_s": (i + 1) * DT, "rpm": RPM, "latch_active": i < 2,
            "theta_deg": [theta0 if i < 2 else theta0 + 1.0], "theta_rate_rad_s": [rates[i]],
            "contact_active": [contact[i]], "hinge_aero_torque_nm": [0.0], "hinge_law_torque_nm": [torques[i]],
            "hinge_contact_torque_nm": [torques[i] if contact[i] else 0.0],
            "centrifugal_hinge_moment_derived_nm": [0.0], "frame_acceleration_hinge_moment_derived_nm": [0.0],
            "drive_torque_nm": (drive or [3.0] * n)[i], "aero_shaft_torque_nm": (aero or [3.0] * n)[i],
            "thrust_n": 30.0})
    case = {"dt_s": DT, "rpm": RPM, "omega_rad_s": RPM * math.pi / 30, "mechanics": MECH,
            "geometry": {"hinge_radius_m": RH}, "controls": {"drive_profile": "constant"}}
    return {"series": series, "execution": {"valid_prefix_windows": n, "status": "completed"},
            "run_definition": {"case": case}, "checks": []}


def test_impulse_balance_over_contact_and_impact_energy():
    # free flight at 100 rad/s, contact torque -J_h*150/(3 DT) per sample (trapezoid over 4 intervals) -> -50 rad/s
    q = -JH * 150.0 / (3 * DT)
    rates = [0, 0, 100, 100, 100 + 0.5 * q * DT / JH, 100 + 1.5 * q * DT / JH, 100 + 2.5 * q * DT / JH, -50, -50]
    torques = [0, 0, 0, 0, q, q, q, 0, 0]
    contact = [False, False, False, False, True, True, True, False, False]
    ev = assessment.contact_events(_row(rates, contact, torques))[0]
    assert ev["first_contact_window"] == 5 and ev["contact_windows"] == 3
    assert ev["impact_rate_rad_s"] == pytest.approx(100.0)
    assert ev["impact_energy_j"] == pytest.approx(0.5 * JH * 100.0 ** 2)
    W = RPM * math.pi / 30
    assert ev["centrifugal_energy_bound_j"] == pytest.approx(0.03 * W ** 2 * RH * 0.055 * (1 - math.cos(math.radians(-20))))
    assert ev["apparent_restitution"] == pytest.approx(0.5)
    assert ev["impulse_balance_relative_residual"] == pytest.approx(0.0, abs=1e-9)
    assert ev["peak_stop_torque_nm"] == pytest.approx(abs(q))
    assert ev["penalty_peak_estimate_nm"] == pytest.approx(100.0 * math.sqrt(500.0 * JH))


def test_impulse_balance_detects_a_missing_load():
    q = -JH * 150.0 / (3 * DT)
    rates = [0, 0, 100, 100, 100 + 0.5 * q * DT / JH, 100 + 1.5 * q * DT / JH, 100 + 2.5 * q * DT / JH, -50, -50]
    contact = [False, False, False, False, True, True, True, False, False]
    ev = assessment.contact_events(_row(rates, contact, [0, 0, 0, 0, q, 0.5 * q, q, 0, 0]))[0]
    assert ev["impulse_balance_relative_residual"] > 0.1


def test_shaft_exchange_is_the_net_drive_impulse_across_the_contact():
    rates = [0, 0, 100, 100, 100, 100, 20, -50, -50, -50]
    contact = [False] * 6 + [True, True] + [False] * 2
    drive = [3.0] * 5 + [3.0, 3.0 - 100.0, 3.0 - 80.0, 3.0, 3.0]
    sh = assessment.shaft_exchange(_row(rates, contact, [0.0] * 10, drive=drive))
    assert sh["angular_impulse_n_m_s"] == pytest.approx(-180.0 * DT)
    assert sh["peak_drive_torque_nm"] == pytest.approx(97.0)
    assert sh["equivalent_mean_torque_nm"] == pytest.approx(-180.0 * DT / sh["exchange_duration_s"])


def test_contact_unfinished_at_the_end_of_the_valid_prefix_gives_no_event():
    rates = [0, 0, 100, 100, 100, 60]
    row = _row(rates, [False] * 5 + [True], [0.0] * 6)
    assert assessment.contact_events(row) == [] and assessment.shaft_exchange(row) is None


def test_swing_impulse_is_reported_apart_from_the_contact_and_does_not_depend_on_restitution():
    rates = [0, 0, 100, 100, 100, 100, 20, -50, -50, -50]
    contact = [False] * 6 + [True, True] + [False] * 2
    drive = [3.0, 3.0, 3.0 + 40.0, 3.0 + 30.0, 3.0, 3.0, 3.0 - 100.0, 3.0 - 80.0, 3.0, 3.0]
    sh = assessment.shaft_exchange(_row(rates, contact, [0.0] * 10, drive=drive))
    assert sh["swing_impulse_n_m_s"] == pytest.approx(70.0 * DT)  # release (window 3) to the last free window before contact
    assert sh["angular_impulse_n_m_s"] == pytest.approx(-180.0 * DT)


def test_restitution_dependent_totals_are_illustrative_and_incoming_parts_preliminary():
    q = -JH * 150.0 / (3 * DT)
    rates = [0, 0, 100, 100, 100 + 0.5 * q * DT / JH, 100 + 1.5 * q * DT / JH, 100 + 2.5 * q * DT / JH, -50, -50]
    contact = [False, False, False, False, True, True, True, False, False]
    by = {r["key"]: r for r in assessment.output_classes(_row(rates, contact, [0, 0, 0, 0, q, q, q, 0, 0]))}
    assert by["incoming_hinge_momentum_n_m_s"]["class"] == "preliminary"
    assert by["incoming_hinge_momentum_n_m_s"]["value"] == pytest.approx(JH * 100.0)
    assert by["hinge_angular_momentum_change_n_m_s"]["class"] == "illustrative"
    assert by["angular_impulse_n_m_s"]["class"] == "illustrative"
    assert by["swing_impulse_n_m_s"]["class"] == "preliminary"


def test_no_release_or_no_contact_gives_no_event():
    row = _row([0.0] * 6, [False] * 6, [0.0] * 6)
    assert assessment.contact_events(row) == []
    assert assessment.shaft_exchange(row) is None


def test_every_output_is_classified_with_what_governs_it():
    q = -JH * 150.0 / (3 * DT)
    rates = [0, 0, 100, 100, 100 + 0.5 * q * DT / JH, 100 + 1.5 * q * DT / JH, 100 + 2.5 * q * DT / JH, -50, -50]
    contact = [False, False, False, False, True, True, True, False, False]
    rows = assessment.output_classes(_row(rates, contact, [0, 0, 0, 0, q, q, q, 0, 0]))
    assert {r["class"] for r in rows} <= set(assessment.CLASSES)
    assert all(r["governed_by"] and r["label"] for r in rows)
    by = {r["key"]: r for r in rows}
    assert by["impact_energy_j"]["class"] == "preliminary"
    assert by["peak_stop_torque_nm"]["class"] == "illustrative"
    assert by["peak_drive_torque_nm"]["class"] == "illustrative"
    assert by["impulse_balance_relative_residual"]["class"] == "numerical_check"
    # radial load the hinge pin carries at the last window: m W^2 r_cg (the synthetic record ends at -19 deg)
    W, th = RPM * math.pi / 30, math.radians(-19.0)
    r_cg = math.hypot(RH + 0.055 * math.cos(th), 0.055 * math.sin(th))
    assert by["hinge_pin_centrifugal_load_n"]["value"] == pytest.approx(0.03 * W ** 2 * r_cg)
    assert by["hinge_pin_centrifugal_load_n"]["class"] == "preliminary"


def test_recorded_release_run(tmp_path):
    run = tmp_path / "run"
    shutil.copytree(FIXTURES / "release_30w_rbf", run)
    row = postprocess.build_result(run, participant_outcome="finished", exit_codes={}, extraction_ok=True)
    events = assessment.contact_events(row)
    assert len(events) == len(row["series"][0]["theta_deg"])
    for ev in events:
        # the recorded -5 deg release: most of the centrifugal potential reaches the stop
        assert 0.6 < ev["impact_energy_j"] / ev["centrifugal_energy_bound_j"] < 1.05
        assert ev["impulse_balance_relative_residual"] < 0.05
    sh = assessment.shaft_exchange(row)
    assert sh is not None and sh["angular_impulse_n_m_s"] < 0 and sh["speed_change_rpm"] == 0.0
    # constant speed: the drive's net impulse is the distal segments' change of angular momentum about the shaft
    assert sh["momentum_balance_relative_residual"] < 0.02
