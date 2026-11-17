"""Full opening–closing cycle: kinematics, Newton–Euler connection loads, events, contacts, energy, records."""
import math
from dataclasses import replace

import numpy as np
import pytest

from pyfoldable.dynamics import fold_cycle as fc

STATIONS = ((0.144, 0.060, math.radians(20.0)), (0.27, 0.050, math.radians(14.0)), (0.388, 0.035, math.radians(11.0)))
FAST = fc.ShaftSchedule(operating_rpm=2400, rest_s=0.05, spinup_s=0.15, hold_s=0.5, spindown_s=0.4, end_rest_s=0.15)
SPRING = fc.FoldMechanism()
PASSIVE = replace(SPRING, spring_nm_per_rad=0.0, spring_preload_nm=0.0)
OFF = fc.AeroModel(model="off")


def case(mech=SPRING, aero=OFF, schedule=FAST, **kw):
    return fc.CycleCase(0.27, 2, schedule, mech, aero, **kw)


@pytest.fixture(scope="module")
def spring_run():
    return fc.run_cycle(case(), sensitivity=True)


@pytest.fixture(scope="module")
def passive_run():
    return fc.run_cycle(case(PASSIVE), sensitivity=False)


def test_schedule_angle_is_the_integral_of_speed_and_the_rate_its_derivative():
    t = np.linspace(0.0, FAST.knots[-1], 20001)
    om, od, psi = FAST.state(t)
    assert np.allclose(np.gradient(psi, t), om, atol=5e-2)
    assert np.allclose(np.gradient(om, t), od, atol=1.0)          # one-sided differences at the ramp knots
    assert om[0] == 0 and om[np.searchsorted(t, FAST.knots[2] + 0.1)] == pytest.approx(2400 * fc.RPM)


def test_rotating_frame_terms_follow_from_the_body_kinematics_as_in_the_coupled_model():
    mech = replace(PASSIVE, damping_nm_s_per_rad=0.0)
    model = fc._Model(case(mech))
    th, thd = np.array([-0.4, -0.4]), np.zeros(2)
    for t in (0.1, 0.2, 0.4):                                 # spin-up (Ω and dΩ/dt) and operation
        om, od, _ = FAST.state(np.array([t]))
        expected = -(mech.mass_kg * mech.cg_from_hinge_m * 0.27 * (om ** 2 * math.sin(-0.4) + od * math.cos(-0.4))
                     ) / mech.hinge_inertia_kg_m2 - od
        assert model.accel(t, th, thd, np.zeros(2, bool)) == pytest.approx(np.full(2, expected[0]), rel=1e-12)


def test_steady_open_connection_load_is_the_centripetal_pull_and_nothing_out_of_plane(passive_run):
    s = passive_run["series"]
    t = np.array(s["time_s"])
    i = int(np.argmin(np.abs(t - (FAST.knots[2] + 0.2))))
    th = math.radians(s["theta_deg"][i][0])
    m, om = PASSIVE, 2400 * fc.RPM
    xg = math.hypot(-m.cg_from_hinge_m * math.sin(th), 0.27 + m.cg_from_hinge_m * math.cos(th))
    assert s["load_N_tension"][i][0] == pytest.approx(m.mass_kg * om ** 2 * xg, rel=2e-3)
    for k in ("V_axial", "M_bending", "M_torsion"):
        assert abs(s[f"load_{k}"][i][0]) < 1e-9
    assert s["contrib_shaft_centripetal_N_tension"][i] == pytest.approx(s["load_N_tension"][i][0], rel=1e-3)


def test_moment_transport_to_the_tang_mid_plane_turns_an_offset_pull_into_bending():
    F, M = np.array([[0.0, -600.0, 0.0]]), np.zeros((1, 3))
    c0 = fc.local_components(F, M, np.zeros(1))
    c1 = fc.local_components(F, M, np.zeros(1), axial_offset_m=0.01)
    assert c0["N_tension"][0] == pytest.approx(600.0) and c0["M_bending"][0] == 0.0
    assert c1["M_bending"][0] == pytest.approx(6.0) and c1["M_pin"][0] == 0.0 and c1["N_tension"][0] == pytest.approx(600.0)


def test_gravity_with_a_vertical_shaft_is_carried_as_shear_along_the_pin():
    r = fc.run_cycle(case(schedule=replace(FAST, hold_s=0.0, spindown_s=0.01, end_rest_s=0.0), gravity="shaft_vertical"),
                     sensitivity=False)
    s = r["series"]
    i = int(np.argmin(np.abs(np.array(s["time_s"]) - 0.02)))           # at rest, resting on the stowed stop
    assert s["load_V_axial"][i][0] == pytest.approx(SPRING.mass_kg * fc.G0, abs=1e-4)
    # the weight acts at the CG, 55 mm out along the span: bending about e_t at the pin
    assert s["load_M_bending"][i][0] == pytest.approx(-SPRING.mass_kg * fc.G0 * SPRING.cg_from_hinge_m, abs=1e-5)
    assert s["rpm"][i] == 0.0


def test_spring_return_opens_and_folds_back_passive_stays_open(spring_run, passive_run):
    assert spring_run["outcome"]["open_reached"] and spring_run["outcome"]["returned_to_stowed"]
    assert passive_run["outcome"]["open_reached"] and not passive_run["outcome"]["returned_to_stowed"]
    keys = [e["key"] for e in spring_run["events"]]
    order = [k for k in ("release", "motion_start", "first_open_contact", "settled", "spindown_start", "retraction_start",
                         "closed_arrival") if k in keys]
    assert order == ["release", "motion_start", "first_open_contact", "settled", "spindown_start", "retraction_start",
                     "closed_arrival"]
    times = {e["key"]: e["time_s"] for e in spring_run["events"]}
    assert all(times[a] <= times[b] for a, b in zip(order, order[1:]))
    # the spring still pulls at the open stop: the operating angle is the centrifugal/spring equilibrium, not 0
    m, om = SPRING, 2400 * fc.RPM
    expected = -math.degrees((m.spring_preload_nm - m.spring_nm_per_rad * m.stowed_stop_rad)
                             / (m.mass_kg * m.cg_from_hinge_m * 0.27 * om ** 2))
    assert spring_run["outcome"]["operating_theta_deg"] == pytest.approx(expected, rel=0.05)


def test_balances_hold(spring_run, passive_run):
    for r in (spring_run, passive_run):
        assert all(c["passed"] in (True, None) for c in r["checks"]), r["checks"]


def test_contacts_report_impact_metrics_and_peak_depends_on_stiffness_more_than_impulse(spring_run):
    first = next(c for c in spring_run["contacts"] if c["stop"] == "open" and c["blade"] == 0)
    assert first["peak_torque_nm"] < 0 and first["impulse_nm_s"] < 0 and 0.5e-3 < first["duration_s"] < 5e-3
    assert 0.35 < first["effective_restitution"] < 0.85
    sens = spring_run["sensitivity"]
    rows = {r["variant"]: r for r in sens["rows"]}
    soft, stiff = rows["Stop rijitliği ×0,5"], rows["Stop rijitliği ×2"]
    assert abs(stiff["peak_torque_nm"]) > abs(first["peak_torque_nm"]) > abs(soft["peak_torque_nm"])
    assert sens["impulse_spread"] < sens["peak_spread"]
    assert sens["numerical_peak_change"] < 0.02


def test_open_latch_carries_the_pin_moment_until_the_commanded_release():
    mech = replace(PASSIVE, open_latch=True, latch_release_s=FAST.knots[3] + 0.05, actuator_nm=-0.3,
                   actuator_start_s=FAST.knots[3] + 0.05, actuator_end_s=FAST.knots[-1])
    r = fc.run_cycle(case(mech), sensitivity=False)
    assert any(e["kind"] == "latch_engaged" for e in r["latch_events"])
    s = r["series"]
    t, lat, latch = np.array(s["time_s"]), np.array(s["latched"])[:, 0], np.array(s["hinge_latch_nm"])[:, 0]
    assert lat.any() and not lat[t > mech.latch_release_s + 1e-6].any()
    assert np.all(latch[t > mech.latch_release_s + 1e-6] == 0.0)
    held = lat.astype(bool)
    pin = np.array(s["load_M_pin"])[:, 0]
    elements = sum(np.array(s[f"hinge_{k}_nm"])[:, 0] for k in fc.ELEMENTS)
    assert np.allclose(pin, elements, atol=5e-5)                       # stored with 5 decimals
    assert np.abs(latch[held]).max() > 1.0                             # the latch carries the pin moment while held
    assert r["outcome"]["returned_to_stowed"]                         # actuator closes once the speed has dropped
    assert "latch_release" in [e["key"] for e in r["events"]]


def test_explicit_aero_model_loads_the_distal_segment_and_records_its_angle_range():
    strips = fc.strips_from_stations(STATIONS, 0.27)
    r = fc.run_cycle(case(aero=fc.AeroModel(strips=strips)), sensitivity=False)
    s = r["series"]
    i = int(np.argmin(np.abs(np.array(s["time_s"]) - (FAST.knots[2] + 0.2))))
    assert s["aero_thrust_n"][i][0] > 0 and s["load_V_axial"][i][0] == pytest.approx(-s["aero_thrust_n"][i][0], abs=1e-4)
    assert s["load_M_bending"][i][0] != 0 and s["alpha_min_deg"][i] < s["alpha_max_deg"][i]
    assert r["analysis_mode"] == "mechanical_cycle_explicit_aero"
    assert all(c["passed"] in (True, None) for c in r["checks"])


def test_records_are_sealed_and_tampering_is_detected(passive_run):
    assert fc.verify(passive_run) is passive_run
    bad = dict(passive_run, outcome={**passive_run["outcome"], "returned_to_stowed": True})
    with pytest.raises(ValueError, match="digest"):
        fc.verify(bad)
    assert fc.case_from_dict(passive_run["case"]) == case(PASSIVE)



def test_a_self_consistent_but_malformed_record_is_refused(passive_run):
    bad = {k: v for k, v in passive_run.items() if k != "result_sha256"}
    bad["series"] = {**bad["series"], "rpm": bad["series"]["rpm"][:-1]}
    with pytest.raises(ValueError, match="lengths"):
        fc.verify(fc.seal(bad))


# ------------------------------------------------------------------------------------- phase-1 WP1 regressions
def _check(r, name):
    return next(c for c in r["checks"] if c["name"] == name)


@pytest.mark.parametrize("mech", [replace(SPRING, actuator_nm=-0.3, actuator_start_s=0.6, actuator_end_s=2.4),
                                  replace(SPRING, stop_stiffness_nm_per_rad=1e5),
                                  replace(SPRING, damping_nm_s_per_rad=0.0, stop_restitution=1.0)],
                         ids=["actuator_switch", "stiff_stop", "zero_damping_rattle"])
def test_consistency_checks_do_not_fail_on_switches_or_stiff_stops(mech):
    r = fc.run_cycle(case(mech), sensitivity=False)
    for name in ("pin_moment_fd_outside_contact", "energy_balance_relative"):
        assert _check(r, name)["passed"], _check(r, name)


def test_a_corrupted_rate_still_fails_the_consistency_checks(monkeypatch):
    real = fc._evaluate

    def corrupted(model, segments, t):
        th, thd, lat = real(model, segments, t)
        bump = (t >= 0.60) & (t <= 0.61)
        return th, thd + np.where(bump, np.sin(np.pi * (t - 0.60) / 0.01), 0.0)[:, None], lat
    monkeypatch.setattr(fc, "_evaluate", corrupted)
    r = fc.run_cycle(case(), sensitivity=False)
    assert _check(r, "pin_moment_fd_outside_contact")["passed"] is False


def test_sensitivity_studies_the_governing_contact_and_reads_its_own_spreads(spring_run):
    sens = spring_run["sensitivity"]
    opens = [c for c in spring_run["contacts"] if c["stop"] == "open"]
    worst = max(opens, key=lambda c: abs(c["peak_torque_nm"]))
    assert abs(worst["peak_torque_nm"]) > abs(opens[0]["peak_torque_nm"])          # the first contact is not the governing one
    ref = next(r for r in sens["rows"] if r["variant"] == "Referans")
    assert ref["peak_torque_nm"] == worst["peak_torque_nm"] and sens["target"]["blade"] == worst["blade"]
    for s in (sens, sens["stowed"]):
        assert ("kararlı" in s["reading"]) == (min(s["impulse_spread"], s["peak_spread"]) < 0.1)
    assert sens["stowed"]["target"]["stop"] == "stowed"
    assert spring_run["notes"]["stop_law"] == "kelvin_voigt_tensile_at_separation"
    assert all(c["tensile_peak_torque_nm"] * c["peak_torque_nm"] <= 0 for c in spring_run["contacts"])
    assert any(c["tensile_peak_torque_nm"] != 0 for c in opens)


def test_horizontal_gravity_reports_every_blade():
    r = fc.run_cycle(fc.CycleCase(0.27, 3, FAST, PASSIVE, OFF, gravity="shaft_horizontal"), sensitivity=False)
    s = r["series"]
    for p in r["peaks"]:
        x = np.array(s[f"load_{p['key']}"])
        b = int(np.unravel_index(np.argmax(np.abs(x)), x.shape)[1])
        assert p["blade"] == b and p["value"] == pytest.approx(x.flat[np.argmax(np.abs(x))])
    assert len(r["outcome"]["returned_by_blade"]) == 3 and len(r["outcome"]["open_reached_by_blade"]) == 3
    assert r["outcome"]["returned_to_stowed"] == all(r["outcome"]["returned_by_blade"])
    assert "all_returned" not in r["outcome"] and "any_open_reached" not in r["outcome"]
    assert np.array(s["energy_residual_j_by_blade"]).shape == (len(s["time_s"]), 3)
    assert np.array(s["contrib_gravity_M_pin_by_blade"]).shape == (len(s["time_s"]), 3)
    assert len(r["events_by_blade"]) == 3
    # blade 1's events, plus the earliest blade that leaves the stowed stop under gravity before the shaft turns
    assert all(e["blade"] in (None, 0) or e["key"] == "left_stowed_before_spinup" for e in r["events"])
    assert any(e["key"] == "left_stowed_before_spinup" for e in r["events"])
    assert {c["blade"] for c in r["contacts"]} == {0, 1, 2}
    assert fc.verify(r) is r


def test_identical_blades_are_integrated_once_and_replicated():
    r = fc.run_cycle(fc.CycleCase(0.27, 3, FAST, PASSIVE, OFF), sensitivity=False)
    th = np.array(r["series"]["theta_deg"])
    assert np.array_equal(th[:, 0], th[:, 2]) and "energy_residual_j_by_blade" not in r["series"]


def test_rest_inflow_zero_keeps_the_blade_stowed_until_spin_up():
    strips = fc.strips_from_stations(STATIONS, 0.27)
    k1 = FAST.knots[1]
    zero = fc.run_cycle(case(PASSIVE, aero=fc.AeroModel(strips=strips, rest_inflow="zero")), sensitivity=False)
    t, th = np.array(zero["series"]["time_s"]), np.array(zero["series"]["theta_deg"])[:, 0]
    assert th[t < k1].max() < math.degrees(PASSIVE.stowed_stop_rad) + 0.1
    assert "left_stowed_before_spinup" not in [e["key"] for e in zero["events"]]
    design = fc.run_cycle(case(PASSIVE, aero=fc.AeroModel(strips=strips)), sensitivity=False)
    ev = next(e for e in design["events"] if e["key"] == "left_stowed_before_spinup")
    assert ev["time_s"] < k1
    with pytest.raises(ValueError):
        fc.AeroModel(strips=strips, rest_inflow="sometimes")


def test_latch_and_actuator_inputs_are_validated():
    with pytest.raises(ValueError, match="actuator"):
        replace(SPRING, actuator_nm=-0.3, actuator_start_s=2.0, actuator_end_s=1.0)
    with pytest.raises(ValueError, match="latch"):
        replace(SPRING, latch_release_s=-0.1)
    with pytest.raises(ValueError, match="capture"):
        replace(SPRING, latch_capture_rad=-0.01)
    replace(SPRING, actuator_nm=0.0, actuator_start_s=2.0, actuator_end_s=1.0)        # inactive window stays allowed


def test_a_capture_band_lets_the_latch_engage_against_the_aerodynamic_moment():
    mech = replace(PASSIVE, open_latch=True, latch_release_s=FAST.knots[3] + 0.05, actuator_nm=-0.3,
                   actuator_start_s=FAST.knots[3] + 0.05, actuator_end_s=FAST.knots[-1], latch_capture_rad=math.radians(1.0))
    r = fc.run_cycle(case(mech, aero=fc.AeroModel(strips=fc.strips_from_stations(STATIONS, 0.27))), sensitivity=False)
    assert any(e["kind"] == "latch_engaged" for e in r["latch_events"])
    assert all(c["passed"] in (True, None) for c in r["checks"]), r["checks"]      # the snap is not a consistency failure


def test_an_early_latch_release_is_not_reported_as_retraction_during_spin_up():
    r = fc.run_cycle(case(replace(PASSIVE, open_latch=True, latch_release_s=0.15)), sensitivity=False)
    assert all(e["time_s"] >= FAST.knots[2] for e in r["events"] if e["key"] == "retraction_start")


def test_every_contact_peak_of_a_rattle_is_resolved_in_the_stored_series():
    mech = replace(SPRING, damping_nm_s_per_rad=0.0, stop_restitution=1.0, stop_stiffness_nm_per_rad=1e4)
    r = fc.run_cycle(case(mech), sensitivity=False)
    s = r["series"]
    t = np.array(s["time_s"])
    worst = max(r["contacts"], key=lambda c: abs(c["peak_torque_nm"]))
    tau = np.array(s[f"hinge_{worst['stop']}_stop_nm"])[:, worst["blade"]]
    win = (t >= worst["t_in_s"]) & (t <= worst["t_out_s"])
    assert np.abs(tau[win]).max() >= 0.95 * abs(worst["peak_torque_nm"])
    assert len(t) < 20000


def test_contact_refinement_fails_closed_beyond_its_budget(monkeypatch):
    monkeypatch.setattr(fc, "MAX_FINE_SAMPLES", 5)
    contacts = [{"blade": 0, "stop": "open", "t_in_s": 0.3, "t_out_s": 0.302}]
    with pytest.raises(ValueError, match="budget"):
        fc._sample_times(case(), contacts, [])


def test_schedules_longer_than_the_cap_are_rejected():
    with pytest.raises(ValueError, match="cycle duration"):
        replace(FAST, hold_s=fc.MAX_CYCLE_DURATION_S)


def test_declared_product_of_inertia_adds_the_centrifugal_twisting_moment():
    sched = replace(FAST, spindown_s=0.01, end_rest_s=0.0)
    i_tz = 2e-6
    r0 = fc.run_cycle(case(PASSIVE, schedule=sched), sensitivity=False)
    r1 = fc.run_cycle(case(replace(PASSIVE, inertia_tz_kg_m2=i_tz), schedule=sched), sensitivity=False)
    t = np.array(r0["series"]["time_s"])
    i = int(np.argmin(np.abs(t - (sched.knots[2] + 0.4))))
    om = 2400 * fc.RPM + r0["series"]["theta_rate_rad_s"][i][0]
    dm = r1["series"]["load_M_torsion"][i][0] - r0["series"]["load_M_torsion"][i][0]
    assert dm == pytest.approx(-om ** 2 * i_tz, rel=1e-3)
    assert r1["series"]["load_M_pin"][i][0] == pytest.approx(r0["series"]["load_M_pin"][i][0], abs=1e-5)
    j = int(np.argmin(np.abs(t - 0.12)))                                   # spin-up: I_tz·(Ω̇ + θ̈) about e_t
    s0 = r0["series"]
    dmb = r1["series"]["load_M_bending"][j][0] - s0["load_M_bending"][j][0]
    assert dmb == pytest.approx(i_tz * (s0["omega_dot_rad_s2"][j] + s0["theta_acc_rad_s2"][j][0]), rel=2e-3, abs=2e-5)


def test_an_older_schema_record_still_verifies(passive_run):
    assert passive_run["schema_version"] == fc.SCHEMA_VERSION == 2
    old = {k: v for k, v in passive_run.items() if k != "result_sha256"}
    old["schema_version"] = 1
    old["case"] = {**old["case"], "schedule": {**old["case"]["schedule"], "hold_s": 30.0}}   # predates the duration cap
    old = fc.seal(old)
    assert fc.verify(old) is old


# ------------------------------------------------------------------------------------- WP1 review regressions
def test_operating_angle_is_a_time_average_not_dominated_by_refined_impacts():
    mech = replace(SPRING, damping_nm_s_per_rad=0.0, stop_restitution=1.0)
    r = fc.run_cycle(case(mech), sensitivity=False)
    s = r["series"]
    t, th = np.array(s["time_s"]), np.array(s["theta_deg"])[:, 0]
    sel = (t >= FAST.knots[2] + 0.5 * FAST.hold_s) & (t <= FAST.knots[3])
    trapz = getattr(np, "trapezoid", None) or np.trapz
    mean = trapz(th[sel], t[sel]) / (t[sel][-1] - t[sel][0])
    assert r["outcome"]["operating_theta_deg"] == pytest.approx(mean, abs=1.0)


def test_an_invalid_older_schema_case_is_still_refused(passive_run):
    old = {k: v for k, v in passive_run.items() if k != "result_sha256"}
    old["schema_version"] = 1
    mech = old["case"]["mechanism"]
    # rules added in schema 2 (actuator window, latch release sign) are tolerated for schema-1 records ...
    old["case"] = {**old["case"], "mechanism": {**mech, "actuator_nm": -0.3, "actuator_start_s": 2.0, "actuator_end_s": 1.0,
                                                "latch_release_s": -1.0}}
    ok = fc.seal(old)
    assert fc.verify(ok) is ok
    # ... every older rule still applies
    old["case"] = {**old["case"], "hinge_radius_m": -1.0, "mechanism": {**mech, "stop_restitution": 5.0}}
    with pytest.raises(ValueError, match="Restitution"):
        fc.verify(fc.seal(old))


def test_check_grid_beyond_its_budget_fails_closed_before_integrating():
    fast_long = fc.ShaftSchedule(operating_rpm=20000, rest_s=0.1, spinup_s=0.3, hold_s=15.0, spindown_s=0.8, end_rest_s=0.6)
    with pytest.raises(ValueError, match="budget"):
        fc.run_cycle(fc.CycleCase(0.27, 8, fast_long, PASSIVE, OFF, gravity="shaft_horizontal"), sensitivity=False)


def test_tight_tolerance_sensitivity_variant_only_integrates_up_to_the_open_target(spring_run, monkeypatch):
    real, ends = fc._integrate, {}

    def spy(cs, t_end=None):
        ends[cs.rtol] = t_end
        return real(cs, t_end)
    monkeypatch.setattr(fc, "_integrate", spy)
    sens = fc.contact_sensitivity(case(), spring_run["contacts"])
    tight = case().rtol / 100
    assert ends[tight] <= sens["target"]["t_in_s"] + sens["rows"][0]["duration_s"] + 0.05 + 1e-9
    assert sens["numerical_peak_change"] is not None
    stowed = {r["variant"]: r for r in sens["stowed"]["rows"]}
    assert not stowed["Daha sıkı tolerans (rtol/100, adım/4)"]["available"]       # not covered: not a different contact
    assert stowed["Stop rijitliği ×2"]["available"]


def test_latch_engaging_within_its_capture_band_adds_no_snap_torque():
    capture = math.radians(1.0)
    mech = replace(PASSIVE, open_latch=True, latch_capture_rad=capture)
    model = fc._Model(case(mech))
    th = np.array([mech.open_stop_rad - capture])
    tau = model.elements(0.0, th, np.zeros(1), np.ones(1, bool))["latch"][0]
    assert tau == pytest.approx(mech.latch_stiffness_nm_per_rad * 1e-3)     # the same 1 mrad preload as at the stop


def test_a_capture_band_does_not_hold_a_blade_off_the_open_stop():
    # the latch only resists folding back: centrifugal moment still seats the blade, so no release impact appears
    base = replace(PASSIVE, open_latch=True, latch_release_s=FAST.knots[3] + 0.05)
    r0 = fc.run_cycle(case(base), sensitivity=False)
    r1 = fc.run_cycle(case(replace(base, latch_capture_rad=math.radians(1.0))), sensitivity=False)
    assert any(e["kind"] == "latch_engaged" for e in r1["latch_events"])
    # within the band-0 latch's own 1 mrad (0.057°) preload past the stop; a held-off blade sat ≈ −0.93°
    assert r1["outcome"]["operating_theta_deg"] == pytest.approx(r0["outcome"]["operating_theta_deg"], abs=0.1)
    assert min(c["t_in_s"] for c in r1["contacts"] if c["stop"] == "open") < base.latch_release_s
    assert all(c["passed"] in (True, None) for c in r1["checks"]), r1["checks"]
