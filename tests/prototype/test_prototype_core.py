"""Design record, steady deployed loads and single-lug checks of the printable prototype (no CAD kernel needed)."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from pyfoldable.prototype import design as pd
from pyfoldable.prototype import loads, strength
from pyfoldable.prototype.mass import MassProps

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def base():
    return pd.default_design(ROOT)


def test_default_is_13_inch_with_a_longer_proximal_and_the_template_planform(base):
    assert base.planform.diameter_mm == pytest.approx(330.2)
    assert pd.validate(base) == []
    st = base.planform.stations
    assert st[0][0] == pytest.approx(0.20 * 165.1) and st[-1][0] == pytest.approx(0.98 * 165.1)
    assert st[0][1] == pytest.approx(28.0 * 330.2 / 250.0)            # chord scales with the diameter, as research does
    assert base.connection.hinge_radius_mm - base.hub_radius_mm > base.planform.tip_radius_mm - base.connection.hinge_radius_mm


def test_reference_planes_and_stack_keep_offset_lugs_gap_and_pin_separate(base):
    assert base.connection.lug_thickness_proximal_mm is None          # default: full-depth lugs
    d = pd.with_changes(base, **{"connection.axial_offset_mm": 6.0, "connection.lug_gap_mm": 0.2,
                                 "connection.lug_thickness_proximal_mm": 3.0, "connection.lug_thickness_distal_mm": 5.0})
    (p0, p1), (q0, q1) = d.lug_bands_mm
    assert d.interface_z_mm == pytest.approx(3.0)                      # default interface plane δ/2
    assert (p1, q0) == pytest.approx((2.9, 3.1))
    assert (p1 - p0, q1 - q0) == pytest.approx((3.0, 5.0))
    assert d.stack_thickness_mm == pytest.approx(8.2)
    assert d.lug_midplane_offset_mm == pytest.approx(4.2)              # derived, not imposed by δ
    assert d.hole_diameter_mm == pytest.approx(d.connection.pin_diameter_mm + d.connection.hole_clearance_mm)
    e = pd.with_changes(d, **{"connection.lug_interface_z_mm": 1.0})
    assert e.lug_bands_mm[0][1] == pytest.approx(0.9)


@pytest.mark.parametrize("change, fragment", [
    ({"connection.hinge_radius_mm": 70.0}, "Proksimal parça distal"),
    ({"connection.lug_gap_mm": 0.0}, "Lug aralığı"),
    ({"connection.boss_radius_mm": 2.5}, "Lug yarıçapı"),
    ({"connection.stowed_angle_deg": 10.0}, "Katlanma açısı"),
    ({"print_model.material": "PETG"}, "Malzeme"),
    ({"operating.max_rpm": -5.0}, "Azami devir"),
    ({"operating.distal_thrust_n": 3.0, "operating.max_rpm": 6000.0}, "etki yarıçapı"),
    ({"operating.distal_drag_n": 1.0, "operating.distal_aero_radius_mm": 130.0}, "azami devirle"),
    ({"operating.distal_drag_n": 1.0, "operating.distal_aero_radius_mm": 50.0, "operating.max_rpm": 6000.0}, "distal parçanın"),
    ({"connection.axial_offset_mm": -3.0}, "Ofset δ > 0"),
    ({"connection.pin_x_mm": 30.0}, "Pim konumu"),
])
def test_validation_refuses_unbuildable_or_unsupported_inputs(base, change, fragment):
    assert any(fragment in e for e in pd.validate(pd.with_changes(base, **change)))


def test_json_round_trip_keeps_the_identity(base):
    d = pd.with_changes(base, **{"operating.max_rpm": 5200.0})
    assert pd.from_json(pd.to_json(d)).identity == d.identity
    assert pd.with_changes(d, **{"connection.axial_offset_mm": 6.1}).identity != d.identity


def test_missing_owner_inputs_stay_visible(base):
    missing = base.missing_owner_inputs()
    assert {"azami devir", "gerekli itki", "motor"} <= set(missing)
    assert "azami devir" not in pd.with_changes(base, **{"operating.max_rpm": 6000.0}).missing_owner_inputs()


def _point_mass(m_g, xyz):
    return MassProps(m_g, tuple(xyz), ((0.0,) * 3,) * 3, 1.0, "test")


META = {"stop_x_mm": (-9.0, -6.0), "stop_z_mm": (-1.0, 3.0), "nose_z_mm": (-1.0, 7.0)}


def test_centrifugal_force_moment_and_stop_follow_the_rigid_body_formulas(base):
    """Point mass m at (x, y, z): F = mΩ²(x, y, 0); M_z about the pin = mΩ²(y_p x − x_p y); the stop force balances
    M_z on its lever, and the pin carries the rest of the force (both reactions push the distal outward)."""
    d = base
    m, x, y, z = 4.0, 4.0, 120.0, 5.0
    L = loads.deployed(_point_mass(m, (x, y, z)), d, META, 6000.0)
    om2 = (6000 * 2 * math.pi / 60) ** 2
    assert L["centrifugal_force_n"][:2] == pytest.approx([m / 1000 * om2 * x / 1000, m / 1000 * om2 * y / 1000])
    px, py = d.connection.pin_x_mm, d.connection.hinge_radius_mm
    Mz = m / 1000 * om2 * (py * x - px * y) / 1000                     # N·mm
    assert L["deploy_moment_nmm"] == pytest.approx(Mz)
    lever = px - (-7.5)
    assert L["stop_force_n"] == pytest.approx(Mz / lever)
    F = np.array(L["centrifugal_force_n"]) + [0, L["stop_force_n"], 0] + np.array(L["pin_force_n"])
    assert np.allclose(F, 0.0, atol=1e-9)
    assert L["pin_couple_nmm"][2] == 0.0                               # the pin carries no moment about its axis
    # in-plane couple from the offset centrifugal force and stop force about the interface plane
    zi = d.interface_z_mm
    Mx = -(-(z - zi) * L["centrifugal_force_n"][1] - (np.mean(META["stop_z_mm"]) - zi) * L["stop_force_n"])
    assert L["pin_couple_nmm"][0] == pytest.approx(Mx)


def test_a_cg_ahead_of_the_pin_line_leaves_the_stop(base):
    L = loads.deployed(_point_mass(4.0, (-4.0, 120.0, 5.0)), base, META, 6000.0)
    assert not L["seated"] and L["stop_force_n"] == 0.0 and L["deploy_moment_nmm"] < 0


def test_drag_moment_reduces_the_seating_moment_and_needs_its_radius(base):
    pm = _point_mass(4.0, (4.0, 120.0, 5.0))
    dry = loads.deployed(pm, base, META, 6000.0)
    wet = loads.deployed(pm, base, META, 6000.0, thrust_n=3.0, drag_n=2.0, aero_radius_mm=130.0)
    assert wet["deploy_moment_nmm"] == pytest.approx(dry["deploy_moment_nmm"] - (130.0 - base.connection.hinge_radius_mm) * 2.0)
    with pytest.raises(ValueError):
        loads.deployed(pm, base, META, 6000.0, thrust_n=3.0)


def test_single_lug_checks_scale_with_speed_squared_and_report_the_limit(base):
    pm = _point_mass(4.0, (4.0, 120.0, 5.0))
    a, b = (strength.checks(loads.deployed(pm, base, META, r), base, META) for r in (3000.0, 6000.0))
    for ra, rb in zip(a, b):
        assert rb["stress_mpa"] == pytest.approx(4 * ra["stress_mpa"])
        assert rb["rpm_limit"] == pytest.approx(ra["rpm_limit"])
        sf = base.operating.safety_factor
        assert rb["stress_mpa"] * sf * (rb["rpm_limit"] / 6000.0) ** 2 == pytest.approx(rb["allowable_mpa"])
    keys = {r["key"] for r in a}
    assert {"pin_shear", "pin_bending", "bearing_proksimal", "bearing_distal", "shear_out_distal", "stop_seat"} <= keys
    P = loads.deployed(pm, base, META, 6000.0)["pin_force_inplane_n"]
    shear = next(r for r in b if r["key"] == "pin_shear")["stress_mpa"]
    assert shear == pytest.approx(P / (math.pi * base.connection.pin_diameter_mm ** 2 / 4))   # one shear plane
    assert strength.governing(b)["rpm_limit"] == min(r["rpm_limit"] for r in b)


def test_aero_case_has_no_speed_scaling_limit(base):
    pm = _point_mass(4.0, (4.0, 120.0, 5.0))
    rows = strength.checks(loads.deployed(pm, base, META, 6000.0, thrust_n=3.0, drag_n=1.0, aero_radius_mm=130.0), base, META)
    assert all(r["rpm_limit"] is None for r in rows) and strength.governing(rows) is None


@pytest.mark.parametrize("pin", [3.0, 4.0, 5.0])
def test_pin_sets_match_their_pin(base, pin):
    hw = pd.hardware_for_pin(pin)
    assert hw.pin_nominal_mm == pin and hw.washer_id_mm > pin and hw.head_diameter_mm > pin
    assert pin - 1.0 <= hw.groove_diameter_mm < pin and hw.clip_od_mm > pin
    d = pd.with_changes(base, hardware=hw, **{"connection.pin_diameter_mm": pin})
    assert not any("Pim seti" in e for e in pd.validate(d))


def test_a_pin_without_its_pin_set_is_refused(base):
    d = pd.with_changes(base, **{"connection.pin_diameter_mm": 4.0})          # Ø3 washers and clip on a Ø4 pin
    assert any("Pim seti" in e for e in pd.validate(d))
    with pytest.raises(ValueError):
        pd.hardware_for_pin(3.5)
