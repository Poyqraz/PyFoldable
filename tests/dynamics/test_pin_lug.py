"""Preliminary clevis–tang checks: load sharing between the plates and the classical hand formulas."""
import math

import numpy as np
import pytest

from pyfoldable.dynamics import pin_lug as pl

GEOM = pl.PinLugGeometry(pin_diameter_m=0.004, tang_thickness_m=0.006, plate_thickness_m=0.003, gap_m=0.0005,
                         tang_width_m=0.012, tang_edge_m=0.008)


def loads(N=600.0, Vt=0.0, Va=0.0, Ms=0.0, Mt=0.0):
    return {k: np.array([v]) for k, v in (("N_tension", N), ("V_inplane", Vt), ("V_axial", Va), ("M_torsion", Ms),
                                            ("M_bending", Mt))}


def test_pure_pull_is_shared_equally_and_matches_the_hand_formulas():
    c = pl.connection_checks(loads(), GEOM, pl.Allowables(pin_shear_pa=200e6, source="test datasheet"))
    r = {x["key"]: x for x in c["rows"]}
    assert c["plate_force_n"][0] == pytest.approx(300.0)
    assert r["pin_shear"]["peak_pa"] == pytest.approx(300.0 / (math.pi * 0.004 ** 2 / 4))
    assert r["pin_bending"]["peak_pa"] == pytest.approx(32 * 300.0 * (0.0015 + 0.0005 + 0.0015) / (math.pi * 0.004 ** 3))
    assert r["tang_bearing"]["peak_pa"] == pytest.approx(600.0 / (0.004 * 0.006))   # moment-free: uniform bearing
    assert r["tang_tension"]["peak_pa"] == pytest.approx(600.0 / (0.008 * 0.006))
    assert r["tang_shear_out"]["peak_pa"] == pytest.approx(600.0 / (2 * 0.006 * 0.006))
    assert r["pin_shear"]["status"] == "yeterli" and r["pin_bending"]["status"] == "girdi gerekli"
    assert c["allowable_source"] == "test datasheet"


def test_tang_bearing_adds_the_edge_term_of_the_moment_it_passes_into_the_pin():
    g = pl.PinLugGeometry(pin_diameter_m=0.004, tang_thickness_m=0.004, plate_thickness_m=0.003)
    peak = lambda **m: {x["key"]: x for x in pl.connection_checks(loads(**m), g, pl.Allowables())["rows"]}[
        "tang_bearing"]["peak_pa"]
    assert peak(Mt=0.0) == pytest.approx(37.5e6)
    assert peak(Mt=0.5) == pytest.approx(84.375e6)          # 37.5 + 6*0.5/(d t^2)
    assert peak(Mt=2.0) == pytest.approx(225e6)
    assert peak(Ms=0.3, Mt=0.4) == pytest.approx(peak(Mt=0.5))   # normal moment magnitude hypot(M_s, M_t)


def test_tang_net_section_adds_bending_from_the_thrust_moment():
    c = pl.connection_checks(loads(N=600.0, Mt=0.5), GEOM, pl.Allowables())
    r = {x["key"]: x for x in c["rows"]}
    assert r["tang_tension"]["peak_pa"] == pytest.approx(600.0 / (0.008 * 0.006) + 6 * 0.5 / (0.008 * 0.006 ** 2))


def test_unsourced_allowables_give_no_verdict():
    every = dict(pin_shear_pa=1e12, pin_bending_pa=1e12, tang_bearing_pa=1e12, plate_bearing_pa=1e12,
                 tang_tension_pa=1e12, tang_shear_pa=1e12)
    for src in ("", "   "):
        c = pl.connection_checks(loads(), GEOM, pl.Allowables(**every, source=src))
        assert all(x["status"] == "girdi gerekli (kaynak)" and x["margin"] is None for x in c["rows"])
        assert c["allowable_source"] == ""
    c = pl.connection_checks(loads(), GEOM, pl.Allowables(**every, source="EN 10088 tablo"))
    assert all(x["status"] == "yeterli" and x["margin"] > 0 for x in c["rows"])


def test_bending_from_thrust_becomes_a_couple_between_the_plates():
    s = GEOM.plate_spacing_m
    c = pl.connection_checks(loads(N=600.0, Mt=1.0), GEOM, pl.Allowables())
    assert c["plate_force_n"][0] == pytest.approx(300.0 + 1.0 / s)          # couple along the span adds to one plate
    c2 = pl.connection_checks(loads(N=0.0, Ms=0.5), GEOM, pl.Allowables())
    assert c2["plate_force_n"][0] == pytest.approx(0.5 / s)                  # torsion: opposite in-plane plate forces


def test_missing_dimensions_leave_checks_unavailable_and_invalid_geometry_is_refused():
    c = pl.connection_checks(loads(), pl.PinLugGeometry(0.004, 0.006, 0.003), pl.Allowables())
    assert set(c["unavailable_checks"]) == {"tang_width_m", "tang_edge_m"}
    assert {x["key"] for x in c["rows"]} == {"pin_shear", "pin_bending", "tang_bearing", "plate_bearing"}
    with pytest.raises(ValueError):
        pl.PinLugGeometry(0.004, 0.006, 0.003, tang_width_m=0.003)
