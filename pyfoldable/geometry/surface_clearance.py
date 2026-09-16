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

    def __post_init__(self):
        for name, minimum, maximum in (('max_depth', 0, 8), ('max_intervals', 1, 255), ('max_node_comparisons', 1, 200000)):
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


@dataclass(frozen=True)
class ClearanceReport:
    status: str
    lower_bound_m: float | None
    witness_clearance_m: float | None
    node_comparisons: int
    intervals: tuple[ClearanceInterval, ...]
    reason: str


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
    if not part.moving:
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

    def take(self):
        if self.used >= self.controls.max_node_comparisons:
            return False
        self.used += 1
        return True


def _pair_interval(a, b, tree_a, tree_b, lo, hi, clearance, budget):
    middle, width = (lo+hi)/2, hi-lo
    stack = [(tree_a,tree_b)]
    minimum = math.inf
    unresolved = False
    while stack:
        if not budget.take():
            return 'unknown', None, None
        na, nb = stack.pop()
        lower = _gap(_box(na,a,middle,width), _box(nb,b,middle,width))
        if lower > clearance+NUMERICAL_PAD_M:
            minimum = min(minimum,lower)
            continue
        if not na.children and not nb.children:
            samples_b = tuple(_samples(nb,b,middle))
            witness = min(math.dist(p,q) for p in _samples(na,a,middle) for q in samples_b)
            if witness < clearance-NUMERICAL_PAD_M:
                return 'violation', None, witness
            unresolved = True
        elif na.children and (not nb.children or na.radius >= nb.radius):
            stack.extend((child,nb) for child in na.children)
        else:
            stack.extend((na,child) for child in nb.children)
    return ('unknown',None,None) if unresolved else ('separated',minimum,None)


def _hub_interval(part, tree, radius, lo, hi, clearance, budget):
    middle, width = (lo+hi)/2, hi-lo
    stack = [tree]
    minimum = math.inf
    unresolved = False
    while stack:
        if not budget.take():
            return 'unknown',None,None
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
                return 'violation',None,witness
            unresolved = True
    return ('unknown',None,None) if unresolved else ('separated',minimum,None)


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
        status,lower,witness = interval_check(left,right,clearance,budget)
        if status == 'violation':
            rows.append(ClearanceInterval(left,right,status,lower,witness,(left+right)/2))
            # A witness settles this query, not the rest of the motion path.
            # Keep unvisited intervals visible instead of dropping them.
            rows.extend(ClearanceInterval(a,b,'unknown') for a,b,_ in pending)
            return ClearanceReport(status,None,witness,budget.used,tuple(rows),f'witnessed clearance violation against {obstacle}; no physical qualification')
        if status == 'unknown' and depth < controls.max_depth and right > left and attempted < controls.max_intervals and budget.used < controls.max_node_comparisons:
            middle = (left+right)/2
            pending.extend(((middle,right,depth+1),(left,middle,depth+1)))
        else:
            rows.append(ClearanceInterval(left,right,status,lower,witness))
    separated = all(row.status == 'separated' for row in rows)
    lower = min(row.lower_bound_m for row in rows) if separated else None
    return ClearanceReport('separated' if separated else 'unknown',lower,None,budget.used,tuple(rows),f'continuous conservative mesh bounds against {obstacle}' if separated else 'unresolved boxes or subdivision/comparison budget; no collision conclusion')


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
