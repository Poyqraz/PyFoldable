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
