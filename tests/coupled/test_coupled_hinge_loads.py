"""Connection loads of a coupled record from MBDyn's joint reactions, checked against the distal Newton–Euler balance."""
import copy
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from pyfoldable.coupled import hinge_loads, postprocess

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "coupled"


@pytest.fixture(scope="module")
def recorded(tmp_path_factory):
    run = tmp_path_factory.mktemp("rbf") / "run"
    shutil.copytree(FIXTURES / "release_30w_rbf", run)
    row = postprocess.build_result(run, participant_outcome="finished", participant_message="")
    return run, row


def test_joint_reactions_close_the_distal_balance_and_give_the_pin_moment_of_the_hinge_law(recorded):
    run, row = recorded
    c = hinge_loads.extract(run, row)
    assert c["record_result_sha256"] == row["result_sha256"] and len(c["time_s"]) == row["execution"]["valid_prefix_windows"]
    assert c["checks"] and all(ch["passed"] for ch in c["checks"]), c["checks"]
    s = row["series"][:len(c["time_s"])]
    for b, blade in enumerate(c["blades"]):
        expected = [r["hinge_law_torque_nm"][b] + r["latch_torque_nm"][b] for r in s]
        assert np.allclose(blade["M_pin"], expected, atol=1e-9)        # same MBDyn moments, opposite reporting node


def test_connection_carries_the_centripetal_pull_and_the_thrust(recorded):
    run, row = recorded
    c = hinge_loads.extract(run, row)
    mech = row["request"]["mechanics"]
    k = len(c["time_s"]) // 2
    om = c["rpm"][k] * 2 * np.pi / 60
    hinge = row["request"]["case"]["geometry"]["hinge_radius_m"] if "case" in row["request"] else None
    n = c["blades"][0]["N_tension"][k]
    assert 0.8 * mech["distal_mass_kg"] * om ** 2 * 0.2 < n                 # outward pull of order m Ω² r_G
    assert c["blades"][0]["V_axial"][k] < 0                                   # thrust on the distal part pushes +z
    assert hinge is None or n < mech["distal_mass_kg"] * om ** 2 * (hinge + mech["distal_cg_from_hinge_m"]) * 1.2


def test_companion_is_bound_to_the_record_and_the_raw_joint_file(recorded, tmp_path):
    run, row = recorded
    hinge_loads.store(run, hinge_loads.extract(run, row))
    assert hinge_loads.load(run, row) is not None
    assert hinge_loads.load(run, {**row, "result_sha256": "0" * 64}) is None
    jnt = run / "structure" / "out.jnt"
    saved = jnt.read_bytes()
    jnt.write_bytes(saved + b"\n")
    try:
        assert hinge_loads.load(run, row) is None
    finally:
        jnt.write_bytes(saved)
    json.loads(hinge_loads.path_for(run).read_text())


def test_integrator_start_up_transient_of_the_joint_reactions_is_flagged_not_reported_as_load(recorded):
    run, row = recorded
    c = hinge_loads.extract(run, row)
    k0 = c["startup_transient_windows"]
    assert 3 <= k0 < len(c["time_s"]) // 2
    res = [r for r in c["force_residual_n"][:k0] if r is not None]
    assert res and res[0] > 10 * max(r for r in c["force_residual_n"][k0:] if r is not None)
    assert all(p["window"] > k0 for p in c["peaks"])



def test_start_up_exclusion_is_only_a_leading_contiguous_run():
    mag = {k: 600.0 for k in range(1, 40)}
    lead = {k: (300.0 * 0.7 ** k if k < 8 else 1.0) for k in range(1, 40)}
    assert hinge_loads.startup_windows(lead, mag, 40) == 8
    late = {**{k: 1.0 for k in range(1, 40)}, 12: 400.0}              # a mismatch after balanced windows stays visible
    assert hinge_loads.startup_windows(late, mag, 40) == 0
    gap = {k: v for k, v in lead.items() if k not in (5, 6)}           # the run stops at a window the stencil excluded
    assert hinge_loads.startup_windows(gap, mag, 40) == 5


def test_pin_channel_extends_the_span_only_while_its_residual_keeps_decaying():
    mag = {k: 600.0 for k in range(1, 40)}
    settling = {k: 300.0 * 0.7 ** k for k in range(1, 40)}             # ≈0.7× per window, as MBDyn's transient
    assert hinge_loads.startup_windows(settling, mag, 40, start=4, decay=0.8) == 10     # until below 2 % of 600
    sustained = {k: 300.0 * 0.7 ** k + 20.0 for k in range(1, 40)}     # a real mismatch under the transient
    assert hinge_loads.startup_windows(sustained, mag, 40, start=4, decay=0.8) == 7
    flat = {k: 20.0 for k in range(1, 40)}
    assert hinge_loads.startup_windows(flat, mag, 40, start=4, decay=0.8) == 4


def test_symmetric_blades_report_the_same_moments_about_their_blade_plane(recorded):
    run, row = recorded
    c = hinge_loads.extract(run, row)
    k0 = c["startup_transient_windows"]
    b0, b1 = c["blades"]
    for key in ("M_bending", "M_torsion", "M_pin", "N_tension"):
        p0, p1 = (max(abs(x) for x in b[key][k0:]) for b in (b0, b1))
        # was 9x on blade 2 (moment about the 10 mm label offset); blades still differ by ~4e-5 N·m in the solver output
        assert p1 == pytest.approx(p0, rel=1e-4, abs=1e-3), key


def test_peaks_cover_every_blade_and_name_the_blade(recorded):
    run, row = recorded
    c = hinge_loads.extract(run, row)
    k0 = c["startup_transient_windows"]
    for p in c["peaks"]:
        best = max(abs(x) for b in c["blades"] for x in b[p["key"]][k0:])
        assert abs(p["value"]) == pytest.approx(best) and p["blade"] in range(len(c["blades"]))
        assert abs(p["value"]) == pytest.approx(max(abs(x) for x in c["blades"][p["blade"]][p["key"]][k0:]))


def test_extract_refuses_a_joint_file_the_sealed_record_did_not_use(recorded):
    run, row = recorded
    jnt = run / "structure" / "out.jnt"
    saved = jnt.read_bytes()
    jnt.write_bytes(saved + b"\n")
    try:
        with pytest.raises(ValueError):
            hinge_loads.extract(run, row)
    finally:
        jnt.write_bytes(saved)


def test_a_companion_from_another_extractor_version_or_manifest_is_not_accepted(recorded):
    run, row = recorded
    c = hinge_loads.extract(run, row)
    assert c["extractor_version"] == hinge_loads.EXTRACTOR_VERSION
    hinge_loads.store(run, {**c, "extractor_version": hinge_loads.EXTRACTOR_VERSION - 1})
    assert hinge_loads.load(run, row) is None
    hinge_loads.store(run, c)
    files = {**row["raw_outputs"]["files"], "structure/out.jnt": {"sha256": "0" * 64}}
    assert hinge_loads.load(run, {**row, "raw_outputs": {**row["raw_outputs"], "files": files}}) is None


def test_coupling_nodes_come_only_from_the_sealed_record_and_a_skipped_check_says_why(recorded):
    run, row = recorded
    c = hinge_loads.extract(run, {**row, "run_definition": {**row["run_definition"], "coupling_nodes": None}})
    assert c["checks"] == [] and c["checks_skipped_reason"]
    assert hinge_loads.extract(run, row)["checks_skipped_reason"] is None


def test_the_window_whose_difference_reaches_the_latch_torque_drop_is_not_checked(recorded):
    run, row = recorded
    s = row["series"]
    drop = next(k for k, r in enumerate(s) if r["latch_torque_nm"][0] == 0.0)
    assert s[drop]["latch_active"]                                      # the recorded flag lags the torque by one window
    c = hinge_loads.extract(run, row)
    assert all(c["force_residual_n"][k] is None for k in range(drop - 2, drop + 3))


def test_release_inside_the_start_up_span_is_listed(recorded):
    run, row = recorded
    c = hinge_loads.extract(run, row)
    k0 = c["startup_transient_windows"]
    rel = next(k for k, r in enumerate(row["series"]) if not r["latch_active"])
    assert rel < k0
    assert {"event": "release", "blade": None, "window": row["series"][rel]["window"],
            "time_s": row["series"][rel]["time_s"]} in c["startup_overlaps"]
    assert all(o["event"] != "first_contact" for o in c["startup_overlaps"])     # first contact at window 13 > k0


def test_a_late_pin_moment_mismatch_is_not_absorbed_into_the_start_up_span(recorded):
    run, row = recorded
    k0 = hinge_loads.extract(run, row)["startup_transient_windows"]
    bad = copy.deepcopy(row)
    k = len(row["series"]) - 4                                          # checked, after contacts and the start-up span
    nodes = row["run_definition"]["coupling_nodes"]
    i = next(i for i, nd in enumerate(nodes) if nd["blade"] == 0 and nd["segment"] == "distal")
    bad["window_exchange"][row["series"][k]["window"] - 1]["moment"][i][2] += 1.0     # 1 N·m about the pin
    c = hinge_loads.extract(run, bad)
    assert c["startup_transient_windows"] == k0
    pin = next(ch for ch in c["checks"] if ch["name"] == "distal_pin_moment_balance_relative")
    assert not pin["passed"], pin


def test_an_edited_companion_is_not_accepted(recorded):
    run, row = recorded
    hinge_loads.store(run, hinge_loads.extract(run, row))
    p = hinge_loads.path_for(run)
    c = json.loads(p.read_text())
    c["checks"][0]["passed"] = not c["checks"][0]["passed"]
    p.write_text(json.dumps(c))
    assert hinge_loads.load(run, row) is None


def test_a_sustained_pin_moment_mismatch_from_the_first_checked_window_is_not_absorbed_into_the_start_up_span(
        recorded, monkeypatch):
    run, row = recorded
    spans = []  # extract calls startup_windows for the force span first, then for the pin-moment extension
    real = hinge_loads.startup_windows
    monkeypatch.setattr(hinge_loads, "startup_windows", lambda *a, **k: spans.append(real(*a, **k)) or spans[-1])
    bad = copy.deepcopy(row)
    nodes = row["run_definition"]["coupling_nodes"]
    i = next(i for i, nd in enumerate(nodes) if nd["blade"] == 0 and nd["segment"] == "distal")
    # 1 N·m about the pin in every window; the 30-window fixture caps the span at 15, so the decay rule itself is
    # pinned by the synthetic test above
    for s in row["series"]:
        bad["window_exchange"][s["window"] - 1]["moment"][i][2] += 1.0
    c = hinge_loads.extract(run, bad)
    force_span = spans[0]
    assert len(spans) == 2 and c["startup_transient_windows"] == force_span
    pin = next(ch for ch in c["checks"] if ch["name"] == "distal_pin_moment_balance_relative")
    assert not pin["passed"], pin
