"""Bounded continuous clearance certificates for synchronous planar mesh motion.

For an angular interval of width w <= pi, any vertex at planar pivot radius r
moves at most 2*r*sin(w/4) from its midpoint pose. Expanding a midpoint BVH box
by that amount in x and y therefore encloses every triangle interior throughout
the interval (triangles are convex combinations of their vertices). Disjoint
expanded boxes provide a conservative Euclidean separation lower bound.

Overlapping boxes are UNKNOWN, never collision evidence. A violation requires
an actual pair of surface sample points closer than the requested clearance.
Hub queries use an infinite cylinder: an intrusion is into that conservative
obstacle, not a claim about the physical finite hub. No CAD solid, connectivity,
strength, or physical qualification is established by these checks.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import sys

from .triangle_distance import triangle_distance, point_triangle_distance

Vec3 = tuple[float, float, float]
Triangle = tuple[Vec3, Vec3, Vec3]
MAX_TRIANGLES = 12000
# Coordinates/pivots are bounded to 10 m; rotated coordinates stay below 40 m.
# Use a 64 m arithmetic scale, including rotated bounding-box corners. This
# deliberately generous absolute pad covers double arithmetic and trigonometry
# roundoff for this bounded domain. It is a numerical guard, not mesh accuracy.
NUMERICAL_PAD_M = 4096 * sys.float_info.epsilon * 64


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f'{name} must be a real number, not bool')
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f'{name} must be representable as a finite float') from exc
    if not math.isfinite(number):
        raise ValueError(f'{name} must be finite')
    return number


def _vector(value, name):
    if not isinstance(value, tuple) or len(value) != 3:
        raise TypeError(f'{name} must be an immutable xyz tuple')
    for coordinate in value:
        if abs(_number(coordinate, name)) > 10:
            raise ValueError(f'{name} coordinates must be within +/-10 m')


@dataclass(frozen=True)
class SurfacePart:
    name: str
    triangles: tuple[Triangle, ...]
    pivot: Vec3 = (0., 0., 0.)
    moving: bool = False

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError('part name must be nonempty')
        if type(self.moving) is not bool:
            raise TypeError('moving must be bool')
        _vector(self.pivot, 'pivot')
        if not isinstance(self.triangles, tuple) or not 1 <= len(self.triangles) <= MAX_TRIANGLES:
            raise ValueError('triangles must be an immutable nonempty tuple of at most 12000 triangles')
        for triangle in self.triangles:
            if not isinstance(triangle, tuple) or len(triangle) != 3:
                raise ValueError('each triangle must contain three immutable xyz tuples')
            for point in triangle:
                _vector(point, 'vertex')


@dataclass(frozen=True)
class ClearanceControls:
    max_depth: int = 8
    max_intervals: int = 255
    max_node_comparisons: int = 50000
    max_feature_tests: int = 2048

    def __post_init__(self):
        for name, minimum, maximum in (('max_depth', 0, 8), ('max_intervals', 1, 255), ('max_node_comparisons', 1, 200000), ('max_feature_tests', 0, 200000)):
            value = getattr(self, name)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f'{name} must be an integer in [{minimum}, {maximum}]')


@dataclass(frozen=True)
class ClearanceInterval:
    angle_min_rad: float
    angle_max_rad: float
    status: str
    lower_bound_m: float | None = None
    witness_clearance_m: float | None = None
    witness_angle_rad: float | None = None
    method: str = 'aabb_bound'
    contact_status: str = 'unknown'
    point_a: Vec3 | None = None
    point_b: Vec3 | None = None


@dataclass(frozen=True)
class ClearanceReport:
    status: str
    lower_bound_m: float | None
    witness_clearance_m: float | None
    node_comparisons: int
    intervals: tuple[ClearanceInterval, ...]
    reason: str
    feature_tests: int = 0
    contact_status: str = 'unknown'


@dataclass(frozen=True)
class _Check:
    status: str
    lower: float | None = None
    witness: float | None = None
    method: str = 'aabb_bound'
    contact: str = 'unknown'
    point_a: Vec3 | None = None
    point_b: Vec3 | None = None


@dataclass(frozen=True)
class _Node:
    low: Vec3
    high: Vec3
    radius: float
    triangles: tuple[Triangle, ...]
    children: tuple[_Node, ...]


def _tree(triangles, pivot):
    points = tuple(p for triangle in triangles for p in triangle)
    low = tuple(min(p[i] for p in points) for i in range(3))
    high = tuple(max(p[i] for p in points) for i in range(3))
    radius = max(math.hypot(p[0]-pivot[0], p[1]-pivot[1]) for p in points)
    if len(triangles) <= 4:
        return _Node(low, high, radius, triangles, ())
    axis = max(range(3), key=lambda i: high[i]-low[i])
    ordered = sorted(triangles, key=lambda t: sum(p[axis] for p in t))
    middle = len(ordered)//2
    return _Node(low, high, radius, (), (_tree(tuple(ordered[:middle]), pivot), _tree(tuple(ordered[middle:]), pivot)))


def _rotate(point, part, angle):
    if not part.moving or angle == 0:
        return point
    x, y = point[0]-part.pivot[0], point[1]-part.pivot[1]
    c, s = math.cos(angle), math.sin(angle)
    return (part.pivot[0]+x*c-y*s, part.pivot[1]+x*s+y*c, point[2])


def _box(node, part, middle, width):
    corners = tuple(_rotate((x,y,z), part, middle) for x in (node.low[0],node.high[0]) for y in (node.low[1],node.high[1]) for z in (node.low[2],node.high[2]))
    expansion = 2*node.radius*math.sin(width/4) if part.moving else 0.
    low = tuple(min(p[i] for p in corners)-NUMERICAL_PAD_M-(expansion if i < 2 else 0.) for i in range(3))
    high = tuple(max(p[i] for p in corners)+NUMERICAL_PAD_M+(expansion if i < 2 else 0.) for i in range(3))
    return low, high


def _gap(box_a, box_b):
    return max(0., math.sqrt(sum(max(0.,box_a[0][i]-box_b[1][i],box_b[0][i]-box_a[1][i])**2 for i in range(3)))-NUMERICAL_PAD_M)


def _samples(node, part, angle):
    for triangle in node.triangles:
        for point in triangle:
            yield _rotate(point, part, angle)
        yield _rotate(tuple(sum(p[i] for p in triangle)/3 for i in range(3)), part, angle)


class _Budget:
    def __init__(self, controls):
        self.controls = controls
        self.used = 0
        self.features = 0

    def take(self):
        if self.used >= self.controls.max_node_comparisons:
            return False
        self.used += 1
        return True

    @property
    def remaining_features(self):
        return self.controls.max_feature_tests - self.features


def _motion(node, part, width):
    return 2 * node.radius * math.sin(width / 4) if part.moving else 0.


def _narrow_pair(na, nb, a, b, middle, width, clearance, budget):
    minimum = math.inf
    unresolved = False
    movement = _motion(na, a, width) + _motion(nb, b, width) + 4 * NUMERICAL_PAD_M
    for ta in na.triangles:
        posed_a = tuple(_rotate(p, a, middle) for p in ta)
        for tb in nb.triangles:
            if budget.remaining_features <= 0:
                return _Check('unknown', method='feature_budget_exhausted')
            result = triangle_distance(posed_a, tuple(_rotate(p, b, middle) for p in tb),
                                       max_feature_tests=min(64, budget.remaining_features))
            budget.features += result.feature_tests
            if result.upper_m + 4 * NUMERICAL_PAD_M < clearance:
                return _Check('violation', witness=result.upper_m + 4 * NUMERICAL_PAD_M,
                              method='triangle_distance', contact=result.contact_status,
                              point_a=result.point_a, point_b=result.point_b)
            if result.contact_status == 'intersecting' and clearance == 0:
                contact = 'rounded_pose_contact' if middle != 0 and (a.moving or b.moving) else 'intersecting'
                return _Check('unknown', method='triangle_distance', contact=contact,
                              point_a=result.point_a, point_b=result.point_b)
            lower = max(0., result.lower_m - movement)
            if lower > clearance + NUMERICAL_PAD_M:
                minimum = min(minimum, lower)
            else:
                unresolved = True
    return _Check('unknown', method='triangle_distance') if unresolved else _Check(
        'separated', minimum, method='triangle_distance', contact='separated')


def _pair_interval(a, b, tree_a, tree_b, lo, hi, clearance, budget):
    middle, width = (lo+hi)/2, hi-lo
    stack = [(tree_a,tree_b)]
    minimum = math.inf
    unresolved = False
    method = 'aabb_bound'
    while stack:
        if not budget.take():
            return _Check('unknown', method='node_budget_exhausted')
        na, nb = stack.pop()
        lower = _gap(_box(na,a,middle,width), _box(nb,b,middle,width))
        if lower > clearance+NUMERICAL_PAD_M:
            minimum = min(minimum,lower)
            continue
        if not na.children and not nb.children:
            samples_b = tuple(_samples(nb,b,middle))
            witness = min(math.dist(p,q) for p in _samples(na,a,middle) for q in samples_b)
            if witness < clearance-NUMERICAL_PAD_M:
                return _Check('violation', witness=witness, method='surface_sample')
            refined = _narrow_pair(na, nb, a, b, middle, width, clearance, budget)
            method = refined.method
            if refined.status == 'violation' or refined.contact in ('intersecting', 'rounded_pose_contact'):
                return refined
            if refined.status == 'separated':
                minimum = min(minimum, refined.lower)
            else:
                unresolved = True
        elif na.children and (not nb.children or na.radius >= nb.radius):
            stack.extend((child,nb) for child in na.children)
        else:
            stack.extend((na,child) for child in nb.children)
    return _Check('unknown', method=method) if unresolved else _Check('separated', minimum, method=method, contact='separated')


def _hub_interval(part, tree, radius, lo, hi, clearance, budget):
    middle, width = (lo+hi)/2, hi-lo
    stack = [tree]
    minimum = math.inf
    unresolved = False
    method = 'aabb_bound'
    while stack:
        if not budget.take():
            return _Check('unknown', method='node_budget_exhausted')
        node = stack.pop()
        low,high = _box(node,part,middle,width)
        lower = math.hypot(*(max(0.,low[i],-high[i]) for i in range(2)))-radius-NUMERICAL_PAD_M
        if lower > clearance+NUMERICAL_PAD_M:
            minimum = min(minimum,lower)
        elif node.children:
            stack.extend(node.children)
        else:
            witness = min(math.hypot(p[0],p[1])-radius for p in _samples(node,part,middle))
            if witness < clearance-NUMERICAL_PAD_M:
                return _Check('violation', witness=witness, method='surface_sample')
            for triangle in node.triangles:
                if budget.remaining_features <= 0:
                    unresolved = True
                    method = 'feature_budget_exhausted'
                    break
                posed = tuple(_rotate(p, part, middle) for p in triangle)
                projected = tuple((p[0], p[1], 0.) for p in posed)
                result = point_triangle_distance((0., 0., 0.), projected,
                    max_feature_tests=min(64, budget.remaining_features))
                budget.features += result.feature_tests
                method = 'projected_triangle_distance'
                upper = result.upper_m - radius + 4 * NUMERICAL_PAD_M
                if upper < clearance - NUMERICAL_PAD_M:
                    # Witness lies on the XY projection, not necessarily at z=0
                    # on the source surface; keep coordinates out of the 3D plot.
                    return _Check('violation', witness=upper, method=method)
                lower = result.lower_m - radius - _motion(node, part, width) - 4 * NUMERICAL_PAD_M
                if lower > clearance + NUMERICAL_PAD_M:
                    minimum = min(minimum, lower)
                else:
                    unresolved = True
    return _Check('unknown', method=method) if unresolved else _Check('separated', minimum, method=method, contact='separated')


def _query(interval_check, lo, hi, clearance, controls, obstacle):
    lo,hi = _number(lo,'angle_min_rad'),_number(hi,'angle_max_rad')
    clearance = _number(clearance,'clearance_m')
    if lo > hi or hi-lo > math.pi or max(abs(lo),abs(hi)) > 2*math.pi:
        raise ValueError('angles must be ordered, within +/-2pi, with interval width <= pi')
    if not 0 <= clearance <= 10:
        raise ValueError('clearance_m must be between 0 and 10 m')
    controls = controls if controls is not None else ClearanceControls()
    if not isinstance(controls,ClearanceControls):
        raise TypeError('controls must be ClearanceControls')
    budget = _Budget(controls)
    pending = [(lo,hi,0)]
    rows = []
    attempted = 0
    while pending:
        left,right,depth = pending.pop()
        if attempted >= controls.max_intervals or budget.used >= controls.max_node_comparisons:
            rows.append(ClearanceInterval(left,right,'unknown'))
            continue
        attempted += 1
        result = interval_check(left,right,clearance,budget)
        status, lower, witness = result.status, result.lower, result.witness
        if status == 'violation' or result.contact in ('intersecting', 'rounded_pose_contact'):
            rows.append(ClearanceInterval(left,right,status,lower,witness,(left+right)/2,
                result.method, result.contact, result.point_a, result.point_b))
            # A witness settles this query, not the rest of the motion path.
            # Keep unvisited intervals visible instead of dropping them.
            rows.extend(ClearanceInterval(a,b,'unknown') for a,b,_ in pending)
            reason = 'witnessed clearance violation' if status == 'violation' else 'surface contact in reported pose; zero-clearance query remains unresolved'
            return ClearanceReport(status,None,witness,budget.used,tuple(rows),f'{reason} against {obstacle}; no physical qualification', budget.features, result.contact)
        if status == 'unknown' and depth < controls.max_depth and right > left and attempted < controls.max_intervals and budget.used < controls.max_node_comparisons:
            middle = (left+right)/2
            pending.extend(((middle,right,depth+1),(left,middle,depth+1)))
        else:
            rows.append(ClearanceInterval(left,right,status,lower,witness,method=result.method,
                contact_status=result.contact, point_a=result.point_a, point_b=result.point_b))
    separated = all(row.status == 'separated' for row in rows)
    lower = min(row.lower_bound_m for row in rows) if separated else None
    return ClearanceReport('separated' if separated else 'unknown',lower,None,budget.used,tuple(rows),f'continuous conservative mesh bounds against {obstacle}' if separated else 'unresolved boxes or subdivision/comparison budget; no collision conclusion',budget.features,'separated' if separated else 'unknown')


def pair_clearance(a: SurfacePart, b: SurfacePart, *, angle_min_rad=0., angle_max_rad=0., clearance_m=0., controls: ClearanceControls | None = None) -> ClearanceReport:
    """Certify separation for all triangle interiors over a common angle path."""
    if not isinstance(a,SurfacePart) or not isinstance(b,SurfacePart):
        raise TypeError('both parts must be SurfacePart')
    if len(a.triangles)+len(b.triangles) > MAX_TRIANGLES:
        raise ValueError('pair queries support at most 12000 total triangles')
    ta,tb = _tree(a.triangles,a.pivot),_tree(b.triangles,b.pivot)
    return _query(lambda lo,hi,c,budget: _pair_interval(a,b,ta,tb,lo,hi,c,budget),angle_min_rad,angle_max_rad,clearance_m,controls,'mesh surface')


def hub_clearance(part: SurfacePart, hub_radius_m: float, *, angle_min_rad=0., angle_max_rad=0., clearance_m=0., controls: ClearanceControls | None = None) -> ClearanceReport:
    """Check against an infinite cylinder centered on the global z axis."""
    if not isinstance(part,SurfacePart):
        raise TypeError('part must be SurfacePart')
    radius = _number(hub_radius_m,'hub_radius_m')
    if not 0 < radius <= 10:
        raise ValueError('hub_radius_m must be positive and <= 10 m')
    tree = _tree(part.triangles,part.pivot)
    return _query(lambda lo,hi,c,budget: _hub_interval(part,tree,radius,lo,hi,c,budget),angle_min_rad,angle_max_rad,clearance_m,controls,'infinite hub cylinder')
