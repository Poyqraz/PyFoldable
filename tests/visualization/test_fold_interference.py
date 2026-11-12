"""Fold contacts of the lofted blade: contact angle and points per pair, and no interlocking in the shown poses."""
import math
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from pyfoldable.application import research_design as research
from pyfoldable.visualization import blade_surface as bs
from pyfoldable.visualization import fold_interference as fi

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def spec():
    active = research.build_research_design(ROOT, replace(research.defaults(ROOT), profile="NACA2412"))
    foil = next(f for f in active.design.airfoils if f.id == "NACA2412")
    return bs.spec_from_design(active, foil)


def test_relief_mesh_keeps_the_aerodynamic_surface_continuous_and_marks_the_joint_zone(spec):
    mesh = bs.loft(spec, n_side=40, dr=0.003, joint="relief")
    aero = mesh.faces[np.isin(mesh.region, ("aero", "joint"))]
    src = mesh.vertex_source[aero]
    edges = Counter(tuple(sorted(e)) for f in src for e in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])))
    assert set(edges.values()) == {2}                     # the parts together are the closed analysis surface
    joint = mesh.face_centroids()[mesh.region == "joint"]
    pivot = np.array([0.0, spec.hinge_radius_m])
    assert len(joint) and np.all(np.linalg.norm(joint[:, :2] - pivot, axis=1) <= mesh.joint_radius_m + 0.004)
    assert np.all(joint[:, 1] <= spec.hinge_radius_m + 1e-9)       # inboard half-disk only
    assert set(mesh.face_part[mesh.region == "joint"]) == {"distal"}
    hinge_ring = mesh.vertices[mesh.section_index(spec.hinge_radius_m)]
    # covers the hinge section and the (wider, tapered) inboard sections it reaches, with a small margin
    assert np.abs(hinge_ring[:, 0]).max() < mesh.joint_radius_m < 1.2 * np.abs(hinge_ring[:, 0]).max()


def test_plane_split_at_the_hinge_interlocks_as_soon_as_the_distal_folds_back(spec):
    rep = fi.fold_contacts(spec, joint="plane", fold_min_deg=-30.0)
    own = rep.pair("distal_1", "proximal_1")
    assert own.status == "contact" and -1.0 < own.first_contact_deg < 0.0
    # the contact is on the trailing side of the hinge, where the distal root swings inboard
    assert own.point_a[0] > 0.0 and abs(own.point_a[1] - spec.hinge_radius_m) < 0.01


def test_relief_moves_the_first_contact_far_beyond_the_plane_split_and_locates_it(spec):
    rep = fi.fold_contacts(spec, joint="relief", fold_min_deg=-180.0)
    own = rep.pair("distal_1", "proximal_1")
    # the joint zone removes the immediate interlock; an in-plane fold about an interior pivot still brings the
    # distal's trailing region onto the proximal's trailing region near the hinge (no axial offset declared)
    assert own.status == "contact" and -120.0 < own.first_contact_deg < -30.0
    for p in (own.point_a, own.point_b):
        assert p is not None and len(p) == 3
        assert abs(p[1] - spec.hinge_radius_m) < 3 * fi.bs.loft(spec, n_side=24, dr=0.01, joint="relief").joint_radius_m
    assert own.point_b[0] > 0.0                                       # trailing side of the proximal
    assert rep.interference_free_deg < -23.0                          # the deployment cases (<= -22.5 deg) are clear
    assert rep.interference_free_deg == pytest.approx(max(c.last_clear_deg for c in rep.contacts
                                                          if c.status == "contact"))
    assert rep.pair("distal_1", "hub").status == "clear"          # hinge 270 mm, distal 130 mm, hub 90 mm
    # no pose shown beyond the first contact: the clamped pose has no penetration
    shown = rep.clamp(-170.0)
    assert shown == pytest.approx(rep.interference_free_deg)
    assert fi.penetrating_points(spec, joint="relief", fold_deg=shown + 0.2).size == 0


def test_hub_contact_is_found_when_the_distal_reaches_the_hub(spec):
    short = replace(spec, stations=tuple((r * 0.6 if i < 2 else r, c, t) for i, (r, c, t) in enumerate(spec.stations)),
                    hub_radius_m=0.08, root_radius_m=0.09, hinge_radius_m=0.20)
    rep = fi.fold_contacts(short, joint="relief", fold_min_deg=-180.0)
    hub = rep.pair("distal_1", "hub")
    # tip trailing-edge corner (0.75 c = 33 mm aft of the pivot line, 188 mm out): |p| < r_hub once its angle
    # from the inward direction is < 23.5 deg, i.e. after 180 - 23.5 - 10 = 146.5 deg of fold
    # only the hub radius is declared (no axial extent): a possible contact, not a certain one
    assert hub.status == "possible_hub_radius_only" and -150.0 < hub.first_contact_deg < -142.0
    assert math.hypot(hub.point_a[0], hub.point_a[1]) == pytest.approx(0.08, abs=0.004)
    certain = [c for c in rep.contacts if c.status == "contact"]
    if certain:
        assert rep.interference_free_deg >= max(c.first_contact_deg for c in certain)


def test_contacts_with_undefined_geometry_are_reported_as_possible_not_certain(spec):
    rep = fi.fold_contacts(spec, joint="relief", fold_min_deg=-180.0)
    kinds = {c.status for c in rep.contacts}
    assert kinds <= {"contact", "clear", "possible_undefined_geometry", "possible_hub_radius_only", "in_contact_open"}
    for c in rep.contacts:
        if "undefined" in c.b:
            assert c.status in ("possible_undefined_geometry", "clear")


def test_the_shown_pose_is_the_last_clear_angle_not_the_first_contact(spec):
    rep = fi.fold_contacts(spec, joint="relief", fold_min_deg=-90.0)
    assert fi.penetrating_points(spec, joint="relief", fold_deg=rep.interference_free_deg).size == 0
    own = rep.pair("distal_1", "proximal_1")
    assert own.first_contact_deg < rep.interference_free_deg <= own.first_contact_deg + rep.tolerance_deg + 1e-9


def test_overlap_already_present_when_open_is_reported_as_such(spec):
    # untwisted sections, 16 blades: 56.5 mm spacing at the 70 mm root chord, so the roots overlap when open
    # (twisted thin sections stack and do not touch even at 32 blades)
    crowded = replace(spec, blade_count=16, stations=tuple((r, c, 0.0) for r, c, _ in spec.stations))
    rep = fi.fold_contacts(crowded, joint="relief", fold_min_deg=-20.0)
    assert any(c.status == "in_contact_open" and c.first_contact_deg == 0.0 for c in rep.contacts)
    assert rep.interference_free_deg == 0.0


def test_scan_step_resolves_the_thinnest_section_swept_by_the_distal_part(spec):
    rep = fi.fold_contacts(spec, joint="relief", fold_min_deg=-30.0)
    t_min = min(s[1] for s in spec.stations) * 0.12               # NACA2412 max thickness at the smallest chord
    reach = spec.tip_radius_m - spec.hinge_radius_m
    assert rep.step_deg <= math.degrees(0.5 * t_min / reach) + 1e-9
