"""Conservative mesh clearance tests; synthetic geometry is not physical evidence."""
import math
import pytest
from pyfoldable.geometry.surface_clearance import (
    SurfacePart, ClearanceControls, pair_clearance, hub_clearance,
)


def part(name, x=0.0, *, moving=False, pivot=(0.,0.,0.)):
    return SurfacePart(name, (((x,0.,0.),(x,.1,0.),(x,0.,.1)),), pivot, moving)


def test_static_separation_and_witness():
    result = pair_clearance(part('a'),part('b',1),clearance_m=.2)
    assert result.status == 'separated'
    assert result.lower_bound_m <= 1
    result = pair_clearance(part('a'),part('b',.1),clearance_m=.2)
    assert result.status == 'violation'
    assert result.witness_clearance_m < .2


def test_intersecting_boxes_are_unknown_not_collision_proof():
    result = pair_clearance(part('a'),part('b'),clearance_m=0.)
    assert result.status == 'unknown'
    assert result.witness_clearance_m is None


def test_rotational_midpath_approach_is_not_missed_by_endpoints():
    moving = SurfacePart('moving',(((1.,0.,0.),(1.01,0.,0.),(1.,.01,0.)),),(0.,0.,0.),True)
    fixed = SurfacePart('fixed',(((0.,1.,0.),(.01,1.,0.),(0.,1.01,0.)),))
    result = pair_clearance(moving,fixed,angle_min_rad=0,angle_max_rad=math.pi,clearance_m=.03)
    assert result.status == 'violation'
    witness = next(row for row in result.intervals if row.status == 'violation')
    assert witness.witness_angle_rad == pytest.approx(math.pi / 2)


def test_interval_lower_bound_is_below_dense_sample_distances():
    a,b = part('moving',1,moving=True),part('fixed',4)
    result = pair_clearance(a,b,angle_min_rad=-math.pi,angle_max_rad=0.,clearance_m=.1)
    assert result.status == 'separated'
    for i in range(201):
        angle = -math.pi + math.pi*i/200
        for p in a.triangles[0]:
            q=(p[0]*math.cos(angle)-p[1]*math.sin(angle),p[0]*math.sin(angle)+p[1]*math.cos(angle),p[2])
            for r in b.triangles[0]:
                assert result.lower_bound_m <= math.dist(q,r)


def test_budget_exhaustion_is_unknown():
    result = pair_clearance(part('a',1,moving=True),part('b',1.1),angle_min_rad=-math.pi,angle_max_rad=0.,clearance_m=.1,controls=ClearanceControls(max_node_comparisons=1))
    assert result.status == 'unknown'
    assert result.lower_bound_m is None
    assert result.node_comparisons <= 1


def test_hub_cylinder_intrusion_and_clearance():
    assert hub_clearance(part('a',1),hub_radius_m=.2,clearance_m=.1).status == 'separated'
    report = hub_clearance(part('a',.1),hub_radius_m=.2,clearance_m=0.)
    assert report.status == 'violation'
    assert report.witness_clearance_m < 0
    assert 'cylinder' in report.reason


@pytest.mark.parametrize('bad',[float('nan'),float('inf'),True,'1'])
def test_reject_invalid_coordinates(bad):
    with pytest.raises((ValueError,TypeError)):
        SurfacePart('a',(((bad,0,0),(1,0,0),(0,1,0)),))


def test_reject_empty_mutable_or_excessively_large_geometry():
    for triangles in ((),[],(((11.,0.,0.),(1.,0.,0.),(0.,1.,0.)),)):
        with pytest.raises((ValueError,TypeError)):
            SurfacePart('a',triangles)


@pytest.mark.parametrize('kwargs',[{'clearance_m':True},{'angle_min_rad':1,'angle_max_rad':0},{'angle_max_rad':4},{'clearance_m':-1}])
def test_invalid_query(kwargs):
    with pytest.raises((ValueError,TypeError)):
        pair_clearance(part('a'),part('b',1),**kwargs)


def test_controls_are_bounded_strict_integers():
    for kwargs in ({'max_depth':True},{'max_depth':9},{'max_intervals':256},{'max_node_comparisons':200001}):
        with pytest.raises((ValueError,TypeError)):
            ClearanceControls(**kwargs)


def test_degenerate_triangle_is_a_valid_conservative_surface_input():
    point = ((1.,0.,0.),)*3
    report = hub_clearance(SurfacePart('point',(point,)),.5)
    assert report.status == 'separated'
    assert 0 < report.lower_bound_m <= .5


def test_unsampled_triangle_intersection_remains_unknown():
    # Crossed triangle interiors: no identical vertices or centroids.
    a = SurfacePart('a',(((-1.,0.,0.),(1.,0.,0.),(0.,1.,0.)),))
    b = SurfacePart('b',(((0.,.2,-1.),(0.,.2,1.),(.5,.2,0.)),))
    assert pair_clearance(a,b).status == 'unknown'


def test_centroid_can_witness_clearance_violation():
    a = SurfacePart('a',(((0.,0.,0.),(3.,0.,0.),(0.,3.,0.)),))
    p = (1.,1.,.01)
    b = SurfacePart('b',((p,p,p),))
    report = pair_clearance(a,b,clearance_m=.02)
    assert report.status == 'violation'
    assert report.witness_clearance_m == pytest.approx(.01)


def test_unresolved_intervals_cover_entire_requested_path_on_exhaustion():
    lo,hi = -math.pi,0.
    result = pair_clearance(part('a',1,moving=True),part('b',1.1),angle_min_rad=lo,angle_max_rad=hi,clearance_m=0.,controls=ClearanceControls(max_node_comparisons=2))
    intervals = sorted(result.intervals,key=lambda row: row.angle_min_rad)
    assert result.status == 'unknown'
    assert intervals[0].angle_min_rad == lo
    assert intervals[-1].angle_max_rad == hi
    assert all(a.angle_max_rad == b.angle_min_rad for a,b in zip(intervals,intervals[1:]))


def test_bvh_certifies_all_leaf_pairs_not_only_first_pair():
    many_a = SurfacePart('a',tuple(part('x',i*.01).triangles[0] for i in range(12)))
    many_b = SurfacePart('b',tuple(part('x',1+i*.01).triangles[0] for i in range(12)))
    report = pair_clearance(many_a,many_b,clearance_m=.1)
    assert report.status == 'separated'
    overlapping_b = SurfacePart('b',many_b.triangles+(many_a.triangles[-1],))
    report = pair_clearance(many_a,overlapping_b,clearance_m=0.)
    assert report.status == 'unknown'


def test_both_rotating_parts_different_pivots_conservative_bound():
    a = part('a',1,moving=True,pivot=(.5,.5,0.))
    b = part('b',4,moving=True,pivot=(4.,.5,0.))
    report = pair_clearance(a,b,angle_min_rad=-math.pi,angle_max_rad=0.,clearance_m=.1)
    assert report.status == 'separated'
    def rotate(p,body,theta):
        x,y=p[0]-body.pivot[0],p[1]-body.pivot[1]
        return (body.pivot[0]+x*math.cos(theta)-y*math.sin(theta),body.pivot[1]+x*math.sin(theta)+y*math.cos(theta),p[2])
    for index in range(101):
        theta=-math.pi+index*math.pi/100
        for p in a.triangles[0]:
            for q in b.triangles[0]:
                assert report.lower_bound_m <= math.dist(rotate(p,a,theta),rotate(q,b,theta))


def test_numerical_guard_does_not_certify_threshold_equality():
    assert pair_clearance(part('a'),part('b',1),clearance_m=1.).status == 'unknown'
    assert pair_clearance(part('a'),part('b',1),clearance_m=1.+1e-13).status == 'unknown'


def test_hub_bound_accounts_for_triangle_interior():
    # All vertices lie outside the cylinder but the triangle crosses its axis.
    triangle = ((1.,0.,0.),(-.5,1.,0.),(-.5,-1.,0.))
    report = hub_clearance(SurfacePart('crossing',(triangle,)),.1)
    assert report.status == 'violation'  # centroid is on the cylinder axis


def test_angular_subdivision_budget_cannot_promote_unresolved_path():
    report = pair_clearance(part('a',1,moving=True),part('b',1.1),angle_min_rad=-math.pi,angle_max_rad=0.,controls=ClearanceControls(max_intervals=1))
    assert report.status == 'unknown'
    assert len(report.intervals) == 1


def test_unrepresentable_integer_is_rejected_as_invalid_input():
    with pytest.raises(ValueError):
        SurfacePart('a',(((10**1000,0.,0.),(1.,0.,0.),(0.,1.,0.)),))
