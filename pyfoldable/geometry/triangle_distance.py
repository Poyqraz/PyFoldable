"""Exact-rational distances between closed triangles, segments and points.

Coordinates are finite binary64 values within +/-64 m (including transformed
SurfacePart coordinates). Fractions represent those supplied values exactly;
this does not certify an upstream trigonometric transform or measured geometry.
Squared minima and geometric predicates are rational. Conversion to distance
uses a square root followed by exact comparisons and outward rounding.

A feature unit is one bounded point/face, edge/edge or edge/face calculation.
At most 21 units solve a triangle pair. Input denominators are limited to 512
bits and intermediate rational numerators/denominators to 4096 bits. Unsupported
precision and incomplete budgets return [0, infinity], never a false separation.
Witness coordinates are rounded display representations of the exact minimizing
points; distance bounds apply to the exact points, not their displayed rounding.
Feature IDs classify the exact rational witnesses: vertex:N takes precedence
over edge:N, then face; ties use the first input index. Triangle edges are
(0,1), (1,2), (2,0). A segment has edge:0; a point has vertex:0.
"""
from dataclasses import dataclass
from fractions import Fraction
import math
from numbers import Real
from typing import Callable


@dataclass(frozen=True)
class DistanceResult:
    lower_m: float
    upper_m: float
    point_a: tuple[float, float, float] | None
    point_b: tuple[float, float, float] | None
    contact_status: str
    reason: str
    feature_tests: int
    feature_a: str | None = None
    feature_b: str | None = None


class _PrecisionLimit(Exception):
    pass


class _BudgetLimit(Exception):
    pass


class _Budget:
    def __init__(self, limit):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 64:
            raise ValueError('max_feature_tests must be an integer in [0, 64]')
        self.limit = limit
        self.used = 0

    def tick(self):
        if self.used >= self.limit:
            raise _BudgetLimit
        self.used += 1


def _check(q):
    if q.numerator.bit_length() > 4096 or q.denominator.bit_length() > 4096:
        raise _PrecisionLimit
    return q


def _point(values):
    try:
        values = tuple(values)
    except TypeError as exc:
        raise ValueError('a point must contain three finite coordinates') from exc
    if len(values) != 3:
        raise ValueError('a point must contain three coordinates')
    if any(isinstance(x, bool) or not isinstance(x, Real) or
           abs(x) > 64 or not math.isfinite(x) for x in values):
        raise ValueError('coordinates must be finite real values within +/-64 m')
    return tuple(Fraction(float(x)) for x in values)


def _triangle(values):
    try:
        values = tuple(values)
    except TypeError as exc:
        raise ValueError('a triangle must contain three points') from exc
    if len(values) != 3:
        raise ValueError('a triangle must contain three points')
    return tuple(_point(p) for p in values)


def _precision(points):
    if any(q.denominator.bit_length() > 512 for p in points for q in p):
        raise _PrecisionLimit


def _sub(a, b):
    return tuple(_check(x-y) for x, y in zip(a, b))


def _add_scaled(a, d, t):
    return tuple(_check(x + t*y) for x, y in zip(a, d))


def _dot(a, b):
    return _check(sum(x*y for x, y in zip(a, b)))


def _cross(a, b):
    return tuple(_check(a[i]*b[j]-a[j]*b[i]) for i, j in ((1, 2), (2, 0), (0, 1)))


def _candidate(a, b):
    delta = _sub(a, b)
    return _dot(delta, delta), a, b


def _edges(t):
    return ((t[0], t[1]), (t[1], t[2]), (t[2], t[0]))


def _on_segment(p, a, b):
    d = _sub(b, a)
    dd = _dot(d, d)
    if not dd:
        return a
    t = _check(_dot(_sub(p, a), d) / dd)
    return _add_scaled(a, d, max(Fraction(0), min(Fraction(1), t)))


def _inside(p, tri, normal):
    return all(_dot(_cross(_sub(b, a), _sub(p, a)), normal) >= 0
               for a, b in _edges(tri))


def _point_face(p, tri):
    candidates = [_candidate(p, _on_segment(p, a, b)) for a, b in _edges(tri)]
    normal = _cross(_sub(tri[1], tri[0]), _sub(tri[2], tri[0]))
    nn = _dot(normal, normal)
    if nn:
        t = _check(_dot(_sub(tri[0], p), normal) / nn)
        projected = _add_scaled(p, normal, t)
        if _inside(projected, tri, normal):
            candidates.append(_candidate(p, projected))
    return min(candidates, key=lambda c: c[0])


def _edge_edge(a0, a1, b0, b1):
    candidates = [_candidate(a, _on_segment(a, b0, b1)) for a in (a0, a1)]
    candidates += [_candidate(_on_segment(b, a0, a1), b) for b in (b0, b1)]
    u, v, w = _sub(a1, a0), _sub(b1, b0), _sub(a0, b0)
    aa, bb, cc = _dot(u, u), _dot(u, v), _dot(v, v)
    dd, ee = _dot(u, w), _dot(v, w)
    determinant = _check(aa*cc-bb*bb)
    if determinant:
        s = _check((bb*ee-cc*dd)/determinant)
        t = _check((aa*ee-bb*dd)/determinant)
        if 0 <= s <= 1 and 0 <= t <= 1:
            candidates.append(_candidate(_add_scaled(a0, u, s), _add_scaled(b0, v, t)))
    return min(candidates, key=lambda c: c[0])


def _edge_face_hit(a0, a1, tri):
    normal = _cross(_sub(tri[1], tri[0]), _sub(tri[2], tri[0]))
    d = _sub(a1, a0)
    denominator = _dot(normal, d)
    if not denominator:
        # Coplanar intersections are covered by point/face and edge/edge tests.
        return None
    t = _check(_dot(normal, _sub(tri[0], a0)) / denominator)
    if 0 <= t <= 1:
        p = _add_scaled(a0, d, t)
        if _inside(p, tri, normal):
            return Fraction(0), p, p
    return None


def _sqrt_bounds(q):
    if not q:
        return 0., 0.
    # Scale by an even power of two before float conversion to avoid underflow.
    exponent = q.numerator.bit_length() - q.denominator.bit_length()
    shift = exponent // 2
    scaled = q / (Fraction(2) ** (2*shift))
    estimate = math.ldexp(math.sqrt(float(scaled)), shift)
    lower = upper = estimate
    # The scaled float conversion + sqrt is within a few ulps. Exact comparisons
    # establish the actual enclosure, not an assumed floating-point epsilon.
    for _ in range(8):
        if Fraction(lower)**2 <= q:
            break
        lower = math.nextafter(lower, 0.)
    else:
        raise _PrecisionLimit
    for _ in range(8):
        if Fraction(upper)**2 >= q:
            break
        upper = math.nextafter(upper, math.inf)
    else:
        raise _PrecisionLimit
    return lower, upper


def _feature(point, shape):
    for index, vertex in enumerate(shape):
        if point == vertex:
            return f'vertex:{index}'
    edges = ((shape[0], shape[1]),) if len(shape) == 2 else _edges(shape)
    for index, (a, b) in enumerate(edges):
        if point == _on_segment(point, a, b):
            return f'edge:{index}'
    return 'face'


def _run(points, budget, calculate: Callable, shape_a, shape_b):
    try:
        _precision(points)
        q, a, b = calculate()
        lower, upper = _sqrt_bounds(q)
        return DistanceResult(lower, upper, tuple(map(float, a)), tuple(map(float, b)),
                              'intersecting' if q == 0 else 'separated',
                              'exact_rational_distance', budget.used,
                              _feature(a, shape_a), _feature(b, shape_b))
    except (_PrecisionLimit, _BudgetLimit) as exc:
        return DistanceResult(0., math.inf, None, None, 'unknown',
                              'feature_budget_exhausted' if isinstance(exc, _BudgetLimit)
                              else 'exact_arithmetic_limit', budget.used)


def point_triangle_distance(point, triangle, *, max_feature_tests=64):
    """Distance to the closed triangular set (including degenerate sets)."""
    budget = _Budget(max_feature_tests)
    p, tri = _point(point), _triangle(triangle)
    def calculate():
        budget.tick()
        return _point_face(p, tri)
    return _run((p, *tri), budget, calculate, (p,), tri)


def segment_segment_distance(a0, a1, b0, b1, *, max_feature_tests=64):
    """Distance between closed segments; zero-length segments are valid."""
    budget = _Budget(max_feature_tests)
    points = tuple(_point(p) for p in (a0, a1, b0, b1))
    def calculate():
        budget.tick()
        return _edge_edge(*points)
    return _run(points, budget, calculate, points[:2], points[2:])


def segment_triangle_intersection(a0, a1, triangle, *, max_feature_tests=64):
    """Return segment/triangle distance with an exact contact classification.

    A nonintersecting pair reports its distance, not merely a boolean predicate.
    """
    budget = _Budget(max_feature_tests)
    a0, a1, tri = _point(a0), _point(a1), _triangle(triangle)
    def calculate():
        budget.tick()
        hit = _edge_face_hit(a0, a1, tri)
        if hit is not None:
            return hit
        candidates = []
        for p in (a0, a1):
            budget.tick()
            candidates.append(_point_face(p, tri))
        for b0, b1 in _edges(tri):
            budget.tick()
            candidates.append(_edge_edge(a0, a1, b0, b1))
        return min(candidates, key=lambda c: c[0])
    return _run((a0, a1, *tri), budget, calculate, (a0, a1), tri)


def triangle_distance(a, b, *, max_feature_tests=64):
    """Outward-rounded distance interval for two closed triangles.

    Edge/face intersections are tested explicitly before closest-feature pairs;
    vertex/face and edge/edge minima alone miss transverse interior crossings.
    """
    budget = _Budget(max_feature_tests)
    a, b = _triangle(a), _triangle(b)
    def calculate():
        for source, target in ((a, b), (b, a)):
            for p0, p1 in _edges(source):
                budget.tick()
                hit = _edge_face_hit(p0, p1, target)
                if hit is not None:
                    return hit
        candidates = []
        for p in a:
            budget.tick()
            candidates.append(_point_face(p, b))
        for p in b:
            budget.tick()
            q, pb, pa = _point_face(p, a)
            candidates.append((q, pa, pb))
        for a0, a1 in _edges(a):
            for b0, b1 in _edges(b):
                budget.tick()
                candidates.append(_edge_edge(a0, a1, b0, b1))
        return min(candidates, key=lambda c: c[0])
    return _run((*a, *b), budget, calculate, a, b)
