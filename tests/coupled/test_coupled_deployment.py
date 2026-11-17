"""Deployment extensions of the coupled route: prescribed shaft-speed ramp, fold geometry envelope and
trajectory applicability (no solver is executed)."""
import math
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from pyfoldable.application import coupled_analysis as svc
from pyfoldable.coupled import c81 as c81mod, deck as deckmod, envelope, postprocess
from pyfoldable.coupled.model import CoupledCaseError, CoupledControls, CoupledMechanics, build_case, shaft_speed

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_coupled_core import _tables, active  # noqa: E402,F401  (module fixture)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "coupled"


def _mech(**kw):
    base = dict(distal_mass_kg=0.03, distal_cg_from_hinge_m=0.055, distal_inertia_cg_kg_m2=3e-5,
                initial_fold_rad=math.radians(-5), release_time_s=0.01,
                source="unit-test demonstration assumption", declaration_kind="demonstration_assumption")
    base.update(kw)
    return CoupledMechanics(**base)


def test_constant_speed_decks_are_byte_identical_to_the_reviewed_generator(active):
    text = c81mod.build_c81(_tables()).text
    expected = {"continuous_rbf": "d5502374b5795d0a075c4be07cd0ed69e0d2263a059beed1bde0586242c90d23",
                "split_rigid": "61fe4ce3e64b2859665f6dc7d2a967891daa3745feb89bcf752892629203ee45"}
    for topo, sha in expected.items():
        case = build_case(active, _mech(), CoupledControls(duration_s=0.02, aero_topology=topo))
        assert deckmod.deck_manifest(deckmod.generate_deck(case, text))["deck_sha256"] == sha, topo


def test_ramp_profile_is_smooth_and_prescribed_exactly(active):
    c = CoupledControls(duration_s=0.1, drive_profile="ramp", ramp_start_rpm=2200.0, ramp_start_s=0.02, ramp_duration_s=0.05)
    case = build_case(active, _mech(), c)
    w1, w0 = case.omega_rad_s, 2200.0 * math.pi / 30
    assert shaft_speed(case, 0.0) == (pytest.approx(w0), 0.0)
    assert shaft_speed(case, 0.02)[0] == pytest.approx(w0)
    mid, mid_dot = shaft_speed(case, 0.045)
    assert mid == pytest.approx(0.5 * (w0 + w1)) and mid_dot == pytest.approx((w1 - w0) * math.pi / (2 * 0.05))
    assert shaft_speed(case, 0.07) == (pytest.approx(w1), pytest.approx(0.0, abs=1e-9))
    assert shaft_speed(case, 0.09) == (pytest.approx(w1), 0.0)
    assert case.dt_s == pytest.approx(math.radians(5.0) / w1)  # step defined at the final speed
    mbd = deckmod.generate_deck(case, c81mod.build_c81(_tables()).text)["structure/rotor.mbd"]
    assert f"axial rotation, 1, null, 2, null, cosine, 0.02, {math.pi / 0.05!r}, {(w1 - w0) / 2!r}, half, {w0!r};" in mbd
    assert f"structural: 2, dynamic, null, eye, null, 0., 0., {w0!r};" in mbd  # hub starts at the ramp start speed


@pytest.mark.parametrize("kw", [dict(ramp_start_rpm=2400.0), dict(ramp_start_rpm=0.0), dict(ramp_duration_s=0.0),
                                dict(ramp_start_s=-0.01), dict(ramp_start_s=0.08), dict(drive_profile="torque")])
def test_invalid_ramps_are_refused(active, kw):
    base = dict(duration_s=0.1, drive_profile="ramp", ramp_start_rpm=2200.0, ramp_start_s=0.02, ramp_duration_s=0.05)
    base.update(kw)
    with pytest.raises(CoupledCaseError):
        build_case(active, _mech(), CoupledControls(**base))


def test_fold_geometry_envelope_bounds_rbf_junction_distortion_and_distal_sweep(active):
    case = build_case(active, _mech(), CoupledControls())
    env = envelope.fold_envelope(case)
    assert env["limited_by"] == "junction_chord" and env["fold_limit_deg"] == pytest.approx(-22.96, abs=0.05)
    assert envelope.junction_chord_bound(math.radians(-20)) == pytest.approx(1 - math.cos(math.radians(10)))
    assert 15.0 < envelope.distal_sweep_deg(case, math.radians(-20)) < 18.0
    with pytest.raises(CoupledCaseError) as err:
        build_case(active, _mech(initial_fold_rad=math.radians(-30)), CoupledControls())
    assert err.value.code == "fold_outside_geometry_envelope"
    build_case(active, _mech(initial_fold_rad=math.radians(-20)), CoupledControls())


def test_windows_beyond_the_fold_envelope_end_the_valid_prefix(tmp_path, monkeypatch):
    run = tmp_path / "run"
    shutil.copytree(FIXTURES / "release_30w_rbf", run)
    monkeypatch.setattr(envelope, "FOLD_LIMIT_CHORD", 1e-5)  # pretend a tiny envelope: the latched -5 deg is outside
    row = postprocess.build_result(run, participant_outcome="finished", exit_codes={}, extraction_ok=True)
    ex = row["execution"]
    assert ex["status"] == "failed_geometry_envelope"
    assert ex["first_outside_fold_envelope_window"] == 1 and ex["valid_prefix_windows"] == 0


def test_trajectory_applicability_separates_admitted_and_unsupported_operation(active):
    env = {"alpha_deg": [-6.0, 8.0], "reynolds": [165000.0, 330000.0], "mach": [0.1, 0.31]}
    steady = build_case(active, _mech(), CoupledControls())  # -5 deg release at the design speed
    a = svc.trajectory_applicability(steady, env)
    assert a["reynolds_ok"] and a["mach_ok"] and a["alpha_ok"]
    # -20 deg at 2400 RPM: the opening swing adds theta_dot * (r - r_h) at the tip and leaves the admitted Mach
    # range (the solved run stopped at Mach 0.3105 seven windows after release): warned, and the run stops
    # fail-closed; the bound is conservative, so it is not a refusal
    big = build_case(active, _mech(initial_fold_rad=math.radians(-20)), CoupledControls())
    assert svc.fold_rate_bound(big) == pytest.approx(167.7, abs=1.0)
    ab = svc.check_trajectory(big, env)
    assert ab["mach_ok"] and not ab["swing"]["mach_ok"] and ab["swing"]["mach"][1] > 0.31
    ramp = build_case(active, _mech(initial_fold_rad=math.radians(-15), release_time_s=0.05),
                      CoupledControls(drive_profile="ramp", ramp_start_rpm=2200.0, ramp_start_s=0.05, ramp_duration_s=0.05))
    svc.check_trajectory(ramp, env)  # the strongest deployment the admitted data supports here
    low = build_case(active, _mech(), CoupledControls(drive_profile="ramp", ramp_start_rpm=1200.0, ramp_start_s=0.0,
                                                      ramp_duration_s=0.05))
    b = svc.trajectory_applicability(low, env)
    assert not b["reynolds_ok"] and not b["alpha_ok"] and b["reynolds"][0] < 165000.0 and b["alpha_deg"][0] < -6.0
    with pytest.raises(svc.CoupledPreparationError) as err:
        svc.check_trajectory(low, env)
    assert err.value.code == "outside_admitted_reynolds"



def test_folded_distal_section_speed_is_the_span_normal_component(active):
    case = build_case(active, _mech(initial_fold_rad=math.radians(-20)), CoupledControls())
    g, w, th = case.geometry, case.omega_rad_s, math.radians(-20)
    rows = svc._trajectory_states(case)
    s = g.distal_sections[-1]
    vt = w * (g.hinge_radius_m * math.cos(th) + (s.radius_m - g.hinge_radius_m))
    speed = math.hypot(case.inflow_m_s, vt)
    expect = (math.degrees(s.twist_rad - math.atan2(case.inflow_m_s, vt)), case.density_kg_m3 * speed * s.chord_m / case.viscosity_pa_s)
    assert any(abs(a - expect[0]) < 1e-9 and abs(re - expect[1]) < 1e-6 for a, re, _ in rows)


def test_hinge_balance_needs_the_frame_acceleration_term():
    """Synthetic ramp history obeying J th'' = M_aero + M_law + M_cf + M_frame: the independent balance
    closes with the frame term and fails without it (no solver)."""
    jh, mrc, dt = 1.2e-4, 4.46e-4, 1e-4
    case = {"rpm": 2400.0, "omega_rad_s": 251.327, "geometry": {"hinge_radius_m": 0.27},
            "mechanics": {"distal_mass_kg": 0.03, "distal_cg_from_hinge_m": 0.055, "spring_nm_per_rad": 0.0,
                          "stop_stiffness_nm_per_rad": 500.0},
            "controls": {"coupling_position_tol_m": 1e-6, "drive_profile": "ramp", "ramp_start_rpm": 2200.0,
                         "ramp_start_s": 0.0, "ramp_duration_s": 0.02}}
    th, rate, series = -0.1, 0.0, []
    for k in range(200):
        t = (k + 1) * dt
        w, wd = shaft_speed(case, t)
        cf, fr, aero = -mrc * w * w * math.sin(th), -(jh + mrc * math.cos(th)) * wd, -0.05
        acc = (aero + cf + fr) / jh
        series.append({"window": k + 1, "time_s": t, "rpm": w * 30 / math.pi, "latch_active": False, "contact_active": [False],
                       "theta_deg": [math.degrees(th)], "theta_rate_rad_s": [rate], "hinge_aero_torque_nm": [aero],
                       "hinge_law_torque_nm": [0.0], "centrifugal_hinge_moment_derived_nm": [cf],
                       "frame_acceleration_hinge_moment_derived_nm": [fr]})
        rate += acc * dt
        th += rate * dt
    closure = {"kinematic_position_m": 0.0, "load_force_n": 0.0, "max_node_force_n": 1.0, "load_moment_nm": 0.0,
               "max_node_moment_nm": 1.0, "interface_power_w": 0.0, "max_interface_power_w": 1.0}
    with_term = {c["name"]: c for c in postprocess._checks(series, case, closure, jh, dt)}
    for r in series:
        r["frame_acceleration_hinge_moment_derived_nm"] = [0.0]
    without = {c["name"]: c for c in postprocess._checks(series, case, closure, jh, dt)}
    assert with_term["hinge_balance_relative_residual"]["value"] < 0.02
    assert without["hinge_balance_relative_residual"]["value"] > 3 * with_term["hinge_balance_relative_residual"]["value"]
    assert with_term["prescribed_speed_deviation_rpm"]["passed"]


def test_sweep_limited_envelope_branch(active, monkeypatch):
    case = build_case(active, _mech(), CoupledControls())
    monkeypatch.setattr(envelope, "FOLD_LIMIT_SWEEP_DEG", 5.0)
    env = envelope.fold_envelope(case)
    assert env["limited_by"] == "distal_sweep" and -8.0 < env["fold_limit_deg"] < -5.0
    assert envelope.distal_sweep_deg(case, math.radians(env["fold_limit_deg"])) <= 5.0 + 1e-6


def test_ramp_records_are_labelled_as_ramps(active):
    case = build_case(active, _mech(), CoupledControls(duration_s=0.1, drive_profile="ramp", ramp_start_rpm=2200.0,
                                                       ramp_start_s=0.02, ramp_duration_s=0.05))
    assert case.drive == "prescribed_speed_ramp"
    assert build_case(active, _mech(), CoupledControls()).drive == "prescribed_constant_speed"
    with pytest.raises(ValueError):
        deckmod.dust_references(case, coupled=False)
    with pytest.raises(CoupledCaseError):
        build_case(active, _mech(), CoupledControls(ramp_start_rpm=float("nan")))
