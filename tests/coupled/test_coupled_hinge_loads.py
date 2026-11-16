"""Connection loads of a coupled record from MBDyn's joint reactions, checked against the distal Newton–Euler balance."""
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


def test_an_edited_companion_is_not_accepted(recorded):
    run, row = recorded
    hinge_loads.store(run, hinge_loads.extract(run, row))
    p = hinge_loads.path_for(run)
    c = json.loads(p.read_text())
    c["checks"][0]["passed"] = not c["checks"][0]["passed"]
    p.write_text(json.dumps(c))
    assert hinge_loads.load(run, row) is None
