"""GEOM04B: narrow phase resolves boxes without promoting unresolved motion."""
import math
import pytest
from pyfoldable.geometry.surface_clearance import SurfacePart, ClearanceControls, pair_clearance, hub_clearance

A = ((0., 0., 0.), (2., 0., 0.), (0., 2., 0.))
B = ((2., 2., 0.), (2., .5, 0.), (.5, 2., 0.))


def test_overlapping_boxes_resolve_with_triangle_bounds():
    a, b = SurfacePart('a', (A,)), SurfacePart('b', (B,))
    coarse = pair_clearance(a, b, clearance_m=.1, controls=ClearanceControls(max_feature_tests=0))
    fine = pair_clearance(a, b, clearance_m=.1)
    assert coarse.status == 'unknown'
    assert fine.status == 'separated'
    assert .1 < fine.lower_bound_m <= .5 / math.sqrt(2)
    assert 0 < fine.feature_tests <= 2048


def test_unsampled_edge_face_intersection_has_actual_witness():
    a = SurfacePart('a', (((-1.,0.,0.),(1.,0.,0.),(0.,1.,0.)),))
    b = SurfacePart('b', (((0.,.2,-1.),(0.,.2,1.),(.5,.2,0.)),))
    result = pair_clearance(a, b, clearance_m=.001)
    assert result.status == 'violation'
    row = next(r for r in result.intervals if r.status == 'violation')
    assert row.point_a is not None and row.point_b is not None
    assert row.witness_angle_rad == 0
    assert row.method == 'triangle_distance'


def test_zero_clearance_contact_does_not_change_clearance_semantics():
    result = pair_clearance(SurfacePart('a', (A,)), SurfacePart('b', (A,)))
    assert result.status == 'unknown'
    assert result.contact_status == 'intersecting'
    assert result.witness_clearance_m is None


def test_triangle_feature_budget_is_separate_and_bounded():
    result = pair_clearance(SurfacePart('a', (A,)), SurfacePart('b', (B,)),
        clearance_m=.1, controls=ClearanceControls(max_feature_tests=1))
    assert result.status == 'unknown'
    assert result.feature_tests <= 1
    assert result.lower_bound_m is None


def test_hub_projection_finds_an_unsampled_interior_intrusion():
    tri = ((-.3,0.,0.),(.7,0.,0.),(.8,1.,0.))
    result = hub_clearance(SurfacePart('a', (tri,)), .1)
    assert result.status == 'violation'
    assert result.witness_clearance_m < -.09
    assert result.feature_tests > 0
    assert result.intervals[0].method == 'projected_triangle_distance'


@pytest.mark.parametrize('value', [-1, True, 200001])
def test_feature_budget_is_strict(value):
    with pytest.raises(ValueError):
        ClearanceControls(max_feature_tests=value)


def test_motion_bound_does_not_reuse_midpoint_distance_as_path_distance():
    a = SurfacePart('moving', (((1.,0.,0.),(1.01,0.,0.),(1.,.01,0.)),), moving=True)
    b = SurfacePart('fixed', (((0.,1.,0.),(.01,1.,0.),(0.,1.01,0.)),))
    report = pair_clearance(a, b, angle_min_rad=0., angle_max_rad=math.pi, clearance_m=.03)
    assert report.status == 'violation'
    assert report.intervals[0].witness_angle_rad == pytest.approx(math.pi/2)


def test_identity_pose_does_not_round_small_gap_to_contact():
    a = SurfacePart('a', (((1e-20, 0., 0.),) * 3,), pivot=(1.,0.,0.), moving=True)
    b = SurfacePart('b', (((0.,0.,0.),) * 3,))
    result = pair_clearance(a, b)
    assert result.contact_status != 'intersecting'


def test_nontrivial_rotated_pose_contact_is_only_a_rounded_pose_observation():
    a = SurfacePart('a', (((1.,0.,0.),) * 3,), moving=True)
    p = (math.cos(.1), math.sin(.1), 0.)
    b = SurfacePart('b', ((p,) * 3,))
    result = pair_clearance(a, b, angle_min_rad=.1, angle_max_rad=.1)
    assert result.status == 'unknown'
    assert result.contact_status == 'rounded_pose_contact'
