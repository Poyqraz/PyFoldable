"""Lofted 3-D blade from catalog profile coordinates and the design's stations (no CAD input)."""
import math
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from pyfoldable.application import research_design as research
from pyfoldable.visualization import blade_surface as bs

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def design():
    active = research.build_research_design(ROOT, replace(research.defaults(ROOT), profile="NACA2412"))
    foil = next(f for f in active.design.airfoils if f.id == "NACA2412")
    return active, foil


@pytest.fixture(scope="module")
def spec(design):
    return bs.spec_from_design(*design)


def test_spec_carries_the_design_identity_and_dimensions(design, spec):
    active, foil = design
    d = active.design
    assert spec.profile_id == "NACA2412" and spec.blade_count == d.blade.blade_count == 2
    assert spec.tip_radius_m == pytest.approx(d.blade.radius_m)
    assert spec.hub_radius_m == pytest.approx(d.blade.hub_radius_m)
    assert spec.hinge_radius_m == pytest.approx(d.hinge.radius_m)
    assert spec.root_radius_m == pytest.approx(0.100)          # declared physical root of the study layout
    assert [s[0] for s in spec.stations] == pytest.approx([s.r_over_R * d.blade.radius_m for s in d.blade.stations])
    assert spec.profile == tuple(foil.coordinates)


def test_resampled_profile_keeps_leading_and_trailing_edges_and_thickness(design):
    foil = design[1]
    raw = np.asarray(foil.coordinates)
    prof = bs.resample_profile(foil.coordinates, n_side=64)
    assert prof.shape == (127, 2)
    assert prof[0] == pytest.approx(raw[0]) and prof[-1] == pytest.approx(raw[-1])   # open trailing edge preserved
    le = raw[np.argmin(raw[:, 0])]
    assert prof[63] == pytest.approx(le)
    upper, lower = prof[:64], prof[63:]
    assert np.all(np.diff(upper[:, 0]) < 0) and np.all(np.diff(lower[:, 0]) > 0)
    # thickness at mid-chord matches the catalog coordinates (NACA2412: ~10.3 % at x/c = 0.3)
    def t_at(x, pts_u, pts_l):
        return np.interp(x, pts_u[::-1, 0], pts_u[::-1, 1]) - np.interp(x, pts_l[:, 0], pts_l[:, 1])
    nu = int(np.argmin(raw[:, 0]))
    ref = t_at(0.3, raw[:nu + 1], raw[nu:])
    assert t_at(0.3, upper, lower) == pytest.approx(ref, rel=2e-3)


def test_sections_follow_the_bem_linear_chord_and_twist(spec):
    (r0, c0, t0), (r1, c1, t1) = spec.stations[0], spec.stations[1]
    assert bs.section_at(spec, r0) == pytest.approx((c0, t0))
    mid = bs.section_at(spec, 0.5 * (r0 + r1))
    assert mid == pytest.approx((0.5 * (c0 + c1), 0.5 * (t0 + t1)))


def test_loft_section_has_chord_quarter_chord_axis_and_twist(spec):
    mesh = bs.loft(spec, n_side=48, dr=0.004)
    r, chord, twist = spec.stations[2]
    ring = mesh.vertices[mesh.section_index(r)]
    assert ring[:, 1] == pytest.approx(np.full(len(ring), r))
    le, te = ring[47], 0.5 * (ring[0] + ring[-1])
    assert float(np.linalg.norm(te - le)) == pytest.approx(chord, rel=1e-6)
    qc = le + 0.25 * (te - le)
    # stacking point is x/c = 0.25, z = 0; the LE-to-mid-TE line differs by the TE asymmetry (1e-5 c): < 1 um
    assert qc[0] == pytest.approx(0.0, abs=1e-6) and qc[2] == pytest.approx(0.0, abs=1e-6)
    # body frame of the coupled model: x LE->TE, z lift normal; positive twist lifts the leading edge (+z)
    assert math.atan2(le[2] - te[2], te[0] - le[0]) == pytest.approx(twist, abs=1e-4)  # same TE asymmetry


def test_aerodynamic_surface_is_closed_and_spans_only_the_declared_stations(spec):
    mesh = bs.loft(spec, n_side=40, dr=0.004)
    aero = mesh.faces[mesh.region == "aero"]
    edges = Counter(tuple(sorted(e)) for f in aero for e in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])))
    assert set(edges.values()) == {2}                       # watertight: TE face and both end caps present
    ys = mesh.vertices[np.unique(aero)][:, 1]
    assert ys.min() == pytest.approx(spec.stations[0][0]) and ys.max() == pytest.approx(spec.stations[-1][0])
    assert {"te_face", "end_cap", "upper", "lower"} <= set(mesh.surface[mesh.region == "aero"])
    # outside the stations nothing is invented: root and tip gaps are separate "undefined" placeholders
    und = mesh.vertices[np.unique(mesh.faces[mesh.region == "undefined"])][:, 1]
    assert und.min() == pytest.approx(spec.root_radius_m) and und.max() == pytest.approx(spec.tip_radius_m)
    assert not np.any((und > spec.stations[0][0] + 1e-9) & (und < spec.stations[-1][0] - 1e-9))


def test_fold_rotates_the_distal_back_toward_the_trailing_side_about_the_quarter_chord_pivot(spec):
    mesh = bs.loft(spec, n_side=40, dr=0.004)
    open_ = mesh.posed(0.0)
    folded = mesh.posed(math.radians(-30.0))
    prox, dist = mesh.vertex_part == "proximal", mesh.vertex_part == "distal"
    assert folded[prox] == pytest.approx(open_[prox])
    tip = np.argmax(np.where(dist, open_[:, 1], -np.inf))
    assert folded[tip, 0] > open_[tip, 0] + 0.05             # trailing side is +x (rotation +Omega about +Z)
    pivot = np.array([0.0, spec.hinge_radius_m])
    d0 = np.linalg.norm(open_[dist][:, :2] - pivot, axis=1)
    d1 = np.linalg.norm(folded[dist][:, :2] - pivot, axis=1)
    assert d1 == pytest.approx(d0) and folded[dist][:, 2] == pytest.approx(open_[dist][:, 2])


def test_a_hinge_axis_other_than_the_shaft_parallel_quarter_chord_axis_is_refused(design):
    from types import SimpleNamespace
    active, foil = design
    d = active.design
    tilted = SimpleNamespace(design=replace(d, hinge=replace(d.hinge, axial_offset_m=0.005)), root=active.root)
    with pytest.raises(ValueError, match="hinge axis"):
        bs.spec_from_design(tilted, foil)


def test_hinge_radius_from_arithmetic_does_not_break_the_hinge_ring(spec):
    odd = replace(spec, hinge_radius_m=0.1 + 0.17)           # 0.27000000000000002
    mesh = bs.loft(odd, n_side=24, dr=0.004, joint="plane")
    assert len(mesh.section_index(odd.hinge_radius_m)) > 0


def test_profile_in_the_wrong_point_order_is_refused(spec):
    with pytest.raises(ValueError, match="Selig"):
        bs.resample_profile(tuple(reversed(spec.profile)), 32)


def test_legacy_preview_and_lofted_blade_are_the_same_physical_blade_when_folded(design):
    """Convention alignment (2026-11-13): the 2.5-D preview used by Plan/GEOM-01/03 and the lofted blade agree
    once the frames are mapped (x_p = y_c, y_p = -x_c, z_p = z_c), including the fold side."""
    from pyfoldable.application import research_views
    active, foil = design
    folded = replace(active, inputs=replace(active.inputs, fold_deg=-40.0))
    preview = research_views._mesh(folded, foil)
    n = preview.section_vertex_count
    tip_ring = preview.vertices[(preview.station_count - 1) * n:preview.station_count * n]
    p = [(v[0], v[1], v[2]) for v in tip_ring]
    mesh = bs.loft(bs.spec_from_design(active, foil), n_side=64, dr=0.004)
    r_tip = active.design.blade.stations[-1].r_over_R * active.design.blade.radius_m
    ring = mesh.posed(math.radians(-40.0))[mesh.section_index(r_tip, "distal")]
    mapped = [(y, -x, z) for x, y, z in ring]
    for pick in (lambda q: q[1], lambda q: -q[1]):            # leading edge (max y_p) and trailing edge (min y_p)
        a, b = max(p, key=pick), max(mapped, key=pick)
        assert math.dist(a, b) < 5e-4
