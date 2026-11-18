"""Verification of the 2-D plane-stress FE route for the printed pin lug (pyfoldable.prototype.lug_fea)."""
from __future__ import annotations

import numpy as np
import pytest

from pyfoldable.prototype.lug_fea import (
    edge_forces, lug_stress, pin_bearing_forces, plate_with_hole_kt, rectangle_mesh, solve_plane_stress,
    structured_lug_mesh,
)

R, A, T, NECK, F = 5.5, 1.6, 4.0, 11.0, 100.0  # typical lug: boss radius, hole radius, thickness (mm); pin pull (N)


@pytest.fixture(scope="module")
def lug_levels():
    return {level: lug_stress(R, A, T, NECK, F, level=level) for level in (3, 4)}


def test_distorted_bar_patch_reproduces_uniform_stress_and_extension():
    length, width, t, force, e_mod = 20.0, 4.0, 2.0, 100.0, 3000.0
    nodes, elements = rectangle_mesh(length, width, 6, 2)
    x, y = nodes.T
    interior = (x > 1e-9) & (x < length - 1e-9) & (y > 1e-9) & (y < width - 1e-9)
    nodes[interior] += np.random.default_rng(0).uniform(-0.2, 0.2, (interior.sum(), 2))  # isoparametric patch test
    fixed = np.zeros(nodes.shape, bool)
    fixed[np.isclose(x, 0.0), 0] = True
    fixed[np.isclose(x, 0.0) & np.isclose(y, 0.0), 1] = True
    tip = np.flatnonzero(np.isclose(x, length))
    tip = tip[np.argsort(y[tip])]
    sigma = force / (width * t)
    f = edge_forces(nodes, tip, (sigma, 0.0), t)
    np.testing.assert_allclose(f.sum(axis=0), (force, 0.0), atol=1e-9)

    r = solve_plane_stress(nodes, elements, e_mod, 0.35, t, fixed, f)

    np.testing.assert_allclose(r["stress"][:, 0], sigma, rtol=0.01)
    assert np.abs(r["stress"][:, 1:]).max() < 0.01 * sigma
    np.testing.assert_allclose(r["displacement"][tip, 0], force * length / (e_mod * width * t), rtol=0.01)


def test_plate_with_hole_matches_heywood_finite_width_kt():
    """Finite-width plate, central hole, uniaxial tension (W/d = 10, quarter model, plate length 2W).

    Heywood: Kt_net = 2 + (1 - d/W)^3 on the net-section stress, so relative to the gross far-field stress
    Kt_gross = Kt_net / (1 - d/W) = (2 + 0.9^3) / 0.9 = 3.032 for d/W = 0.1.
    Source: R. B. Heywood, Designing by Photoelasticity, Chapman & Hall (1952), as quoted in W. D. Pilkey and
    D. F. Pilkey, Peterson's Stress Concentration Factors, 3rd ed., Wiley (2008), Ch. 4 (finite-width plate with a
    central circular hole).
    """
    a = 1.0
    d_over_w = 0.1
    kt_heywood = (2.0 + (1.0 - d_over_w) ** 3) / (1.0 - d_over_w)

    kt = plate_with_hole_kt(a, width=2 * a / d_over_w, height=4 * a / d_over_w, n_r=16, n_theta=24)

    assert abs(kt / kt_heywood - 1.0) < 0.05


def test_lug_peak_stress_converges_between_finest_levels(lug_levels):
    coarse, fine = lug_levels[3], lug_levels[4]
    assert fine["elements"] > coarse["elements"]
    assert abs(fine["peak_von_mises_mpa"] / coarse["peak_von_mises_mpa"] - 1.0) < 0.05
    assert abs(fine["peak_max_principal_mpa"] / coarse["peak_max_principal_mpa"] - 1.0) < 0.05


def test_clamp_reactions_balance_pin_force():
    nodes, elements, boundary = structured_lug_mesh(R, A, NECK, n_r=8, n_theta=24)
    f = pin_bearing_forces(nodes, boundary["hole"], boundary["hole_angle"], F)
    np.testing.assert_allclose(f.sum(axis=0), (0.0, F), atol=1e-9 * F)
    x, y = nodes.T
    assert abs(np.sum(x * f[:, 1] - y * f[:, 0])) < 1e-9 * F * A  # frictionless: no torque about the pin
    assert np.abs(f[y < -1e-9]).max() < 1e-12 * F                   # only the +y half of the hole is loaded

    r = solve_plane_stress(nodes, elements, 3000.0, 0.35, T, boundary["clamp"], f)

    reaction = r["reaction"][boundary["clamp"]].sum(axis=0)
    assert abs(reaction[1] + F) < 1e-3 * F
    assert abs(reaction[0]) < 1e-3 * F


def test_lug_peak_sits_at_hole_edge_on_net_section(lug_levels):
    r = lug_levels[4]
    x, y = r["peak_xy_mm"]
    assert abs(abs(x) - A) < 0.15 * A
    assert abs(y) < 0.5 * A
    assert r["nominal_net_mpa"] == pytest.approx(F / ((2 * R - 2 * A) * T))
    assert 1.0 < r["kt_net"] < 6.0
    assert r["scope"].startswith("Düzlem gerilme FE")
