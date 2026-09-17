"""Analytical software fixtures, never measured propeller geometry."""
import math
import pytest
from pyfoldable.geometry.hardware import (
    ConvexSolid, finite_cylinder, surface_solid_distance, solid_solid_distance,
    transform_solid,
)

VERTICES = ((-1.,-1.,-1.),(1.,-1.,-1.),(1.,1.,-1.),(-1.,1.,-1.),
            (-1.,-1.,1.),(1.,-1.,1.),(1.,1.,1.),(-1.,1.,1.))
FACES = ((0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),
         (1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7))
I = ((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))


def box(scale=1.):
    return ConvexSolid(tuple(tuple(scale*x for x in p) for p in VERTICES), FACES)


def test_cube_accepts_and_rejects_topology_and_orientation():
    assert len(box().triangles) == 12
    for faces in (FACES[:-1], FACES + (FACES[0],), tuple(tuple(reversed(f)) for f in FACES)):
        with pytest.raises(ValueError):
            ConvexSolid(VERTICES, faces)


def test_nonconvex_and_degenerate_and_invalid_indices_rejected():
    v=list(VERTICES);v[6]=(0.,0.,0.)
    for vertices,faces in ((v,FACES),(VERTICES, ((0,0,1),)+FACES[1:]),(VERTICES, ((True,2,1),)+FACES[1:])):
        with pytest.raises(ValueError):
            ConvexSolid(vertices, faces)


def test_surface_entirely_inside_is_penetration_even_zero_clearance():
    result=surface_solid_distance((((0.,0.,0.),(.2,0.,0.),(0.,.2,0.)),),box(),max_triangle_queries=200)
    assert result.penetration is True
    assert result.lower_m == result.upper_m == 0.


def test_surface_outside_analytic_distance():
    t=(((2.,0.,0.),(2.,.2,0.),(2.,0.,.2)),)
    result=surface_solid_distance(t,box(),max_triangle_queries=200)
    assert result.lower_m <= 1. <= result.upper_m
    assert result.lower_m > .99999
    assert result.penetration is False


def test_crossing_triangle_without_internal_vertices_is_penetration():
    t=(((-2.,0.,0.),(2.,0.,0.),(0.,2.,0.)),)
    result=surface_solid_distance(t,box(),max_triangle_queries=200)
    assert result.penetration is True
    assert result.upper_m == 0.


def test_tangent_is_contact_not_penetration():
    t=(((1.,0.,0.),(1.,.2,0.),(1.,0.,.2)),)
    result=surface_solid_distance(t,box(),max_triangle_queries=200)
    assert result.penetration is False
    assert result.contact_status == 'confirmed'


def test_solid_containment_and_budget_exhaustion():
    assert solid_solid_distance(box(.1),box(),max_triangle_queries=200).penetration is True
    far=transform_solid(box(), I, (5.,0.,0.))
    r=solid_solid_distance(box(),far,max_triangle_queries=0)
    assert r.lower_m == 0 and r.reason == 'triangle_budget_exhausted'


def test_cylinder_cap_side_and_containment():
    c=finite_cylinder(radius_m=1.,height_m=2.,segments=16,approximation_tolerance_m=.03)
    assert 0 < c.approximation_error_m < .03
    assert surface_solid_distance((((0.,0.,0.),(.1,0.,0.),(0.,.1,0.)),),c,max_triangle_queries=200).penetration
    for tri in ((((0.,0.,2.),(.1,0.,2.),(0.,.1,2.)),), (((2.,0.,0.),(2.,.1,0.),(2.,0.,.1)),)):
        r=surface_solid_distance(tri,c,max_triangle_queries=500)
        assert r.lower_m <= 1 <= r.upper_m
        assert r.lower_m > .97


def test_cylinder_insufficient_approximation_and_nonrigid_transform_rejected():
    with pytest.raises(ValueError):
        finite_cylinder(radius_m=1.,height_m=2.,segments=8,approximation_tolerance_m=.0001)
    with pytest.raises(ValueError):
        transform_solid(box(), ((2.,0.,0.),(0.,1.,0.),(0.,0.,1.)),(0.,0.,0.))


def test_transformed_surface_inside_and_cap_outside():
    angle=.31
    rot=((math.cos(angle),-math.sin(angle),0.),(math.sin(angle),math.cos(angle),0.),(0.,0.,1.))
    posed=transform_solid(box(),rot,(2.,1.,0.))
    assert surface_solid_distance((((2.,1.,0.),(2.01,1.,0.),(2.,1.01,0.)),),posed,max_triangle_queries=20).penetration
    result=surface_solid_distance((((2.,1.,2.),(2.01,1.,2.),(2.,1.01,2.)),),posed,max_triangle_queries=200)
    assert result.lower_m <= 1 <= result.upper_m
    assert result.lower_m > .999999


def test_thin_triangle_clipping_and_large_triangle_enclosing_cross_section():
    for tri in (((-3.,-3.,0.),(3.,-3.,0.),(0.,3.,0.)),((-2.,0.,0.),(2.,0.,0.),(0.,1e-100,0.))):
        assert surface_solid_distance((tri,),box(),max_triangle_queries=200).penetration


def test_hardware_query_budget_and_input_fail_closed():
    for budget in (-1,True,200001):
        with pytest.raises(ValueError):
            solid_solid_distance(box(),box(.1),max_triangle_queries=budget)
    r=surface_solid_distance((((2.,0.,0.),(2.,.1,0.),(2.,0.,.1)),),box(),max_triangle_queries=1)
    assert r.queries == 1 and r.lower_m == 0 and r.penetration is None
    assert r.reason=='triangle_budget_exhausted'
    with pytest.raises(ValueError):
        ConvexSolid(((float('nan'),0,0),)+VERTICES[1:],FACES)


def test_disjoint_solids_and_reverse_containment():
    assert solid_solid_distance(box(),box(.1),max_triangle_queries=300).penetration
    result=solid_solid_distance(box(),transform_solid(box(),I,(3.,0.,0.)),max_triangle_queries=500)
    assert result.lower_m <= 1 <= result.upper_m
    assert result.lower_m > .999999
    assert result.penetration is False


def test_cylinder_zero_budget_and_tight_segment_refinement():
    a=finite_cylinder(radius_m=.1,height_m=.2,segments=8,approximation_tolerance_m=.01)
    b=finite_cylinder(radius_m=.1,height_m=.2,segments=32,approximation_tolerance_m=.01)
    assert b.approximation_error_m < a.approximation_error_m
    r=surface_solid_distance((((.3,0.,0.),(.3,.1,0.),(.3,0.,.1)),),a,max_triangle_queries=0)
    assert r.queries==0 and r.lower_m==0 and r.penetration is None


def test_identical_solids_have_shared_strict_interior_witness():
    from pyfoldable.geometry.hardware import interior_margin
    result = solid_solid_distance(box(), box(), max_triangle_queries=500)
    assert result.penetration is True
    assert interior_margin(box(), result.point_a) > 0
    assert result.point_a == result.point_b


def test_tangent_solids_do_not_have_interior_overlap():
    result = solid_solid_distance(box(), transform_solid(box(), I, (2., 0., 0.)), max_triangle_queries=500)
    assert result.penetration is False
    assert result.contact_status == 'confirmed'


def test_disjoint_solid_status_and_partial_budget_are_sound():
    far = transform_solid(box(), I, (3., 0., 0.))
    result = solid_solid_distance(box(), far, max_triangle_queries=500)
    assert result.contact_status == 'separated'
    assert result.point_a is not None and result.point_b is not None
    for budget in (0, 1, 20):
        result = solid_solid_distance(box(), far, max_triangle_queries=budget)
        assert result.queries <= budget
        assert result.penetration is None
        assert result.lower_m == 0
        assert result.contact_status == 'unknown'


def test_intersection_witness_has_margin_in_both_solids():
    from pyfoldable.geometry.hardware import interior_margin
    a, b = box(), transform_solid(box(), I, (1.5, .3, 0.))
    result = solid_solid_distance(a, b, max_triangle_queries=500)
    assert result.penetration is True
    assert interior_margin(a, result.point_a) > 0
    assert interior_margin(b, result.point_a) > 0


def test_interior_margin_uses_exact_planes_and_inner_cylinder():
    from pyfoldable.geometry.hardware import interior_margin
    assert interior_margin(box(), (0., 0., 0.)) == 1.
    assert interior_margin(box(), (.75, 0., 0.)) == .25
    assert interior_margin(box(), (1., 0., 0.)) == 0.
    assert interior_margin(box(), (2., 0., 0.)) == 0.
    cylinder = finite_cylinder(radius_m=1., height_m=2., segments=8, approximation_tolerance_m=.1)
    assert .92 < interior_margin(cylinder, (0., 0., 0.)) < 1.
    posed = transform_solid(box(), I, (9.5, 0., 0.))
    assert interior_margin(posed, (9.5, 0., 0.)) == 1.
    assert surface_solid_distance((((11.,0.,0.),(11.,.1,0.),(11.,0.,.1)),), posed, max_triangle_queries=200).lower_m > .49


def test_partially_coincident_solids_and_cylinders_have_interior_overlap():
    from pyfoldable.geometry.hardware import interior_margin
    a, b = box(), transform_solid(box(), I, (1., 0., 0.))
    r = solid_solid_distance(a, b, max_triangle_queries=500)
    assert r.penetration is True
    assert min(interior_margin(a, r.point_a), interior_margin(b, r.point_a)) > 0
    c = finite_cylinder(radius_m=.1, height_m=.2, segments=8, approximation_tolerance_m=.01)
    assert solid_solid_distance(c, c, max_triangle_queries=200).penetration is True
    far = transform_solid(c, I, (.5, 0., 0.))
    r = solid_solid_distance(c, far, max_triangle_queries=5000)
    assert r.contact_status == 'separated' and r.penetration is False
    assert .28 < r.lower_m <= .3 <= r.upper_m


def test_coincident_interior_work_is_metered_and_exhaustion_is_unknown():
    for budget in (0, 1, 12, 23):
        r = solid_solid_distance(box(), box(), max_triangle_queries=budget)
        assert r.queries <= budget
        assert r.penetration is None and r.contact_status == 'unknown'
        assert r.reason == 'triangle_budget_exhausted'
    assert solid_solid_distance(box(), box(), max_triangle_queries=24).penetration


def test_source_and_posed_coordinate_domains_are_separate():
    with pytest.raises(ValueError, match='10 m'):
        box(11.)
    posed = transform_solid(box(), I, (60., 0., 0.))
    assert surface_solid_distance((((63., 0., 0.),)*3,), posed, max_triangle_queries=200).lower_m > 1.99
    with pytest.raises(ValueError, match='64 m'):
        transform_solid(box(), I, (64., 0., 0.))


def test_repeated_exact_transforms_cannot_grow_unbounded():
    from pyfoldable.geometry.hardware import interior_margin
    rotation = ((math.cos(.31), -math.sin(.31), 0.), (math.sin(.31), math.cos(.31), 0.), (0., 0., 1.))
    posed = box()
    for _ in range(200):
        try:
            posed = transform_solid(posed, rotation, (0., 0., 0.))
        except ValueError as exc:
            assert 'precision' in str(exc).lower()
            break
    else:
        pytest.fail('Exact transforms did not enforce the rational bit budget')
    # Last valid coordinates still permit sound bounded queries; no forced
    # failure is required merely because the next composition was rejected.
    r = surface_solid_distance((((3., 0., 0.),)*3,), posed, max_triangle_queries=200)
    assert 0 <= r.lower_m <= r.upper_m
    assert interior_margin(posed, (0., 0., 0.)) >= 0


def test_precision_failure_is_unknown_in_public_queries(monkeypatch):
    import pyfoldable.geometry.hardware as hw
    solid = box(.1)
    monkeypatch.setattr(hw, 'MAX_RATIONAL_BITS', 64)
    r = surface_solid_distance((((3., 0., 0.),)*3,), solid, max_triangle_queries=200)
    assert r.lower_m == 0 and r.penetration is None
    assert r.reason == 'precision_limit' and r.queries <= 200
    assert hw.interior_margin(solid, (0., 0., 0.)) == 0
    r = solid_solid_distance(solid, box(), max_triangle_queries=200)
    assert r.lower_m == 0 and r.penetration is None
    assert r.reason == 'precision_limit'


def test_triangle_kernel_precision_failure_propagates_unknown(monkeypatch):
    import pyfoldable.geometry.hardware as hw
    from pyfoldable.geometry.triangle_distance import DistanceResult
    monkeypatch.setattr(hw, 'triangle_distance', lambda *args: DistanceResult(
        0., math.inf, None, None, 'unknown', 'exact_arithmetic_limit', 1))
    r = surface_solid_distance((((3., 0., 0.),)*3,), box(), max_triangle_queries=200)
    assert r.penetration is None and r.contact_status == 'unknown'
    assert r.reason == 'precision_limit'
