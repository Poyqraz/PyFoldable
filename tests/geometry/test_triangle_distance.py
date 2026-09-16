"""Analytic and metamorphic checks for certified triangle distances."""
from fractions import Fraction
import itertools
import math

import pytest

from pyfoldable.geometry.triangle_distance import (
    point_triangle_distance, segment_segment_distance,
    segment_triangle_intersection, triangle_distance,
)

A = ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.))


def encloses(result, squared):
    q = Fraction(squared)
    assert Fraction(result.lower_m) ** 2 <= q <= Fraction(result.upper_m) ** 2
    assert result.upper_m - result.lower_m <= 4 * math.ulp(result.upper_m)


def test_parallel_faces_exact_distance():
    b = tuple((x, y, z + 2) for x, y, z in A)
    r = triangle_distance(A, b)
    encloses(r, 4)
    assert r.contact_status == 'separated'
    assert r.point_a is not None and r.point_b is not None


def test_skew_edges_irrational_distance_bounds():
    r = segment_segment_distance((0, 0, 0), (1, 0, 0), (0, 1, 1), (1, 1, 1))
    encloses(r, 2)


def test_point_projects_to_face_interior():
    r = point_triangle_distance((.25, .25, 3), A)
    encloses(r, 9)
    assert r.point_b == (.25, .25, 0)


def test_point_outside_face_uses_edge():
    encloses(point_triangle_distance((1, 1, 0), A), Fraction(1, 2))


def test_crossing_edge_through_face_interiors():
    b = ((.25, .25, -1), (.25, .25, 1), (2, 2, 1))
    r = triangle_distance(A, b)
    assert r.lower_m == r.upper_m == 0
    assert r.contact_status == 'intersecting'


def test_segment_crosses_face():
    r = segment_triangle_intersection((.25, .25, -1), (.25, .25, 1), A)
    assert r.contact_status == 'intersecting'
    assert r.point_a == r.point_b == (.25, .25, 0)


@pytest.mark.parametrize('b', [
    ((.1, .1, 0), (.2, .1, 0), (.1, .2, 0)),
    ((1, 0, 0), (2, 0, 0), (1, 1, 0)),
    ((0, 0, 0), (1, 0, 0), (0, -1, 0)),
])
def test_coplanar_containment_shared_corner_and_shared_edge(b):
    r = triangle_distance(A, b)
    assert r.contact_status == 'intersecting'
    assert r.upper_m == 0


def test_degenerate_points_and_segments():
    a = ((0, 0, 0),) * 3
    b = ((1, 1, 0), (2, 1, 0), (3, 1, 0))
    encloses(triangle_distance(a, b), 2)
    encloses(segment_segment_distance((0, 0, 0), (0, 0, 0), (1, 0, 0), (1, 0, 0)), 1)


def test_skinny_nonzero_area_keeps_face():
    a = ((0, 0, 0), (1, 0, 0), (1, 2**-45, 0))
    r = point_triangle_distance((.75, 2**-47, 1), a)
    encloses(r, 1)
    assert r.point_b == (.75, 2**-47, 0)


def test_symmetry_vertex_permutations_and_rigid_transform():
    b = ((1, 1, 2), (2, 1, 2), (1, 2, 2))
    baseline = triangle_distance(A, b)
    for aa in itertools.permutations(A):
        assert triangle_distance(aa, b).lower_m == baseline.lower_m
        assert triangle_distance(b, aa).upper_m == baseline.upper_m
    transform = lambda t: tuple((-y + 1, x - 2, z + 1) for x, y, z in t)
    assert triangle_distance(transform(A), transform(b)).lower_m == baseline.lower_m


@pytest.mark.parametrize('scale', [2**-20, .5, 4])
def test_exact_power_of_two_scale(scale):
    b = tuple((x, y, z + 1) for x, y, z in A)
    scaled = lambda t: tuple(tuple(v * scale for v in p) for p in t)
    encloses(triangle_distance(scaled(A), scaled(b)), Fraction(scale)**2)


def test_budget_exhaustion_is_conservative_and_counted():
    b = tuple((x, y, z + 1) for x, y, z in A)
    r = triangle_distance(A, b, max_feature_tests=1)
    assert r.lower_m == 0 and r.upper_m == math.inf
    assert r.contact_status == 'unknown' and r.reason == 'feature_budget_exhausted'
    assert r.feature_tests == 1
    assert triangle_distance(A, b).feature_tests <= 21


def test_extreme_precision_falls_back_without_fake_bound():
    tiny = math.nextafter(0., 1.)
    r = triangle_distance(A, ((0, 0, tiny), (1, 0, tiny), (0, 1, tiny)))
    assert r.lower_m == 0 and r.contact_status == 'unknown'
    assert r.reason == 'exact_arithmetic_limit'


@pytest.mark.parametrize('bad', [math.nan, math.inf, 64.1, True])
def test_invalid_coordinates_rejected(bad):
    with pytest.raises(ValueError):
        point_triangle_distance((bad, 0, 0), A)


@pytest.mark.parametrize('budget', [-1, 1.5, True, 1000000])
def test_invalid_budgets_rejected(budget):
    with pytest.raises(ValueError):
        triangle_distance(A, A, max_feature_tests=budget)


def test_oblique_plane_has_rational_squared_distance():
    tri = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    r = point_triangle_distance((0, 0, 0), tri)
    encloses(r, Fraction(1, 3))
    assert r.point_b == (1/3, 1/3, 1/3)


def test_overlapping_boxes_do_not_mean_triangles_intersect():
    b = ((1, 1, 0), (1, .75, 0), (.75, 1, 0))
    r = triangle_distance(A, b)
    encloses(r, Fraction(9, 32))
    assert r.contact_status == 'separated'


def test_coplanar_crossing_without_vertex_containment():
    a = ((-2, -.5, 0), (2, -.5, 0), (0, .5, 0))
    b = ((-.5, -2, 0), (-.5, 2, 0), (.5, 0, 0))
    assert triangle_distance(a, b).contact_status == 'intersecting'


def test_collinear_overlapping_degenerate_triangles():
    a = ((0, 0, 0), (1, 0, 0), (2, 0, 0))
    b = ((.5, 0, 0), (1.5, 0, 0), (3, 0, 0))
    assert triangle_distance(a, b).upper_m == 0


def test_tiny_supported_coordinates_do_not_underflow_distance():
    scale = 2**-200
    a = ((0, 0, 0),) * 3
    b = ((scale, scale, 0),) * 3
    encloses(triangle_distance(a, b), 2 * Fraction(scale)**2)


def test_zero_budget_and_full_rotated_coordinate_domain():
    r = point_triangle_distance((40, 0, 0), A, max_feature_tests=0)
    assert r.lower_m == 0 and r.upper_m == math.inf and r.feature_tests == 0
    encloses(point_triangle_distance((40, 0, 0), A), 39**2)


@pytest.mark.parametrize('triangle', [None, (), A[:2], ((0, 0),)*3, ('abc',)*3])
def test_malformed_triangles_fail_cleanly(triangle):
    with pytest.raises(ValueError):
        triangle_distance(A, triangle)


def test_feature_ids_cover_vertex_edge_and_face():
    face = point_triangle_distance((.25, .25, 1), A)
    assert (face.feature_a, face.feature_b) == ('vertex:0', 'face')
    edge = point_triangle_distance((1, 1, 0), A)
    assert edge.feature_b == 'edge:1'
    vertex = point_triangle_distance((-1, 0, 0), A)
    assert vertex.feature_b == 'vertex:0'
    crossing = segment_triangle_intersection((.25, .25, -1), (.25, .25, 1), A)
    assert (crossing.feature_a, crossing.feature_b) == ('edge:0', 'face')


def test_feature_ids_use_exact_oblique_projection_and_degenerate_precedence():
    oblique = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    assert point_triangle_distance((0, 0, 0), oblique).feature_b == 'face'
    point = ((0, 0, 0),) * 3
    assert triangle_distance(point, A).feature_a == 'vertex:0'
    assert triangle_distance(A, A, max_feature_tests=0).feature_a is None


def test_huge_integer_is_rejected_as_value_error():
    with pytest.raises(ValueError):
        point_triangle_distance((10**10000, 0, 0), A)
