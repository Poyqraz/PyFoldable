"""Blade geometry for saved records: built from the record itself, identity-checked, never from current inputs."""
import copy
import math
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from pyfoldable.application import blade_geometry as bg
from pyfoldable.application import research_design as research
from pyfoldable.coupled import postprocess
from pyfoldable.visualization import blade_surface as bs

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def row(tmp_path_factory):
    run = tmp_path_factory.mktemp("c") / "run"
    shutil.copytree(ROOT / "tests/fixtures/coupled/release_30w_rbf", run)
    return postprocess.build_result(run, participant_outcome="finished", exit_codes={}, extraction_ok=True)


def test_coupled_spec_reproduces_the_design_stations_and_dimensions(row):
    active = research.build_research_design(ROOT, replace(research.defaults(ROOT), profile="NACA2412"))
    foil = next(f for f in active.design.airfoils if f.id == "NACA2412")
    want = bs.spec_from_design(active, foil)
    got = bg.spec_from_coupled(row)
    assert [v for s in got.stations for v in s] == pytest.approx([v for s in want.stations for v in s])
    assert (got.hub_radius_m, got.root_radius_m, got.hinge_radius_m, got.tip_radius_m, got.blade_count) == \
        pytest.approx((want.hub_radius_m, want.root_radius_m, want.hinge_radius_m, want.tip_radius_m, want.blade_count))
    assert got.profile == want.profile and got.profile_id == "NACA2412"


def test_coupled_spec_refuses_a_record_whose_profile_coordinates_differ(row):
    bad = copy.deepcopy(row)
    bad["request"]["research"]["coordinate_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="coordinate"):
        bg.spec_from_coupled(bad)


def test_node_transforms_pose_the_loft_like_the_mbdyn_bodies(row):
    import numpy as np
    from pyfoldable.coupled import frames
    w = 20
    tr = bg.node_transforms(row, w)
    spec = bg.spec_from_coupled(row)
    nodes = row["node_states"][w]["nodes"]
    # the distal body node's own reference point maps onto its accepted position
    for b, lab in ((0, "200"), (1, "201")):
        local = next(x["local"] for x in row["run_definition"]["bodies"] if x["mbdyn_label"] == int(lab))
        got = tr[b](np.array([local]), np.array([True]))[0]
        assert got == pytest.approx(nodes[lab]["x"], abs=1e-12)
    # fold and azimuth of blade 1 agree with theta and psi of the record
    tip = np.array([[0.0, spec.stations[-1][0], 0.0]])
    ref = bs.pose_points(tip, np.array([True]), spec.hinge_radius_m, math.radians(bg.folds_deg(row, w)[0]),
                         bg.rotor_azimuth(row, w))
    assert tr[0](tip, np.array([True]))[0] == pytest.approx(ref[0], abs=2e-4)


def test_rotor_azimuth_and_folds_come_from_the_accepted_window(row):
    case = row["run_definition"]["case"]
    for w in (1, 10, 30):
        t = row["series"][w - 1]["time_s"]
        expected = math.remainder(case["omega_rad_s"] * t, 2 * math.pi)
        # the accepted MBDyn state, which leads Omega t by the documented ~0.0019 deg (3.3e-5 rad) per step at 5 deg;
        # an off-by-one window would be a whole step (0.087 rad)
        lead = math.remainder(bg.rotor_azimuth(row, w) - expected, 2 * math.pi)
        assert 0.0 <= lead <= 4e-5 * w
        assert bg.folds_deg(row, w) == pytest.approx(row["series"][w - 1]["theta_deg"])


def test_unknown_window_raises_key_error(row):
    with pytest.raises(KeyError):
        bg.rotor_azimuth(row, 10_000)
    with pytest.raises(KeyError):
        bg.folds_deg(row, 10_000)


def test_legacy_split_rigid_records_without_bodies_are_posed_from_their_coupling_nodes(tmp_path):
    import numpy as np
    run = tmp_path / "split"
    shutil.copytree(ROOT / "tests/fixtures/coupled/release_30w", run)
    legacy = postprocess.build_result(run, participant_outcome="finished", exit_codes={}, extraction_ok=True)
    assert "bodies" not in legacy["run_definition"]
    tr = bg.node_transforms(legacy, 20)
    spec = bg.spec_from_coupled(legacy)
    tip = np.array([[0.0, spec.stations[-1][0], 0.0]])
    ref = bs.pose_points(tip, np.array([True]), spec.hinge_radius_m, math.radians(bg.folds_deg(legacy, 20)[0]),
                         bg.rotor_azimuth(legacy, 20))
    assert tr[0](tip, np.array([True]))[0] == pytest.approx(ref[0], abs=2e-4)
