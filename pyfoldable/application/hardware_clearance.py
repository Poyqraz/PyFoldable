"""Bounded synchronous motion queries against explicitly supplied hardware.

Hardware tolerance is a declared geometric uncertainty: it reduces separation
bounds and increases witness upper bounds. Open blade surfaces stay surfaces.
"""
from dataclasses import dataclass, field
import math

from pyfoldable.geometry.hardware import (
    ConvexSolid, CylinderEnvelope, transformed_solid, surface_solid_distance,
    solid_solid_distance, interior_margin,
)
from pyfoldable.geometry.surface_clearance import NUMERICAL_PAD_M, SurfacePart

PAD = 8 * NUMERICAL_PAD_M
IDENTITY = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))


def rotation_z(angle):
    if angle == 0:
        return IDENTITY
    c, s = math.cos(angle), math.sin(angle)
    return ((c, -s, 0.), (s, c, 0.), (0., 0., 1.))


def _rotate(point, pivot, angle):
    if angle == 0:
        return point
    x, y = point[0] - pivot[0], point[1] - pivot[1]
    c, s = math.cos(angle), math.sin(angle)
    return (pivot[0] + c*x - s*y, pivot[1] + s*x + c*y, point[2])


@dataclass(frozen=True)
class MotionShape:
    name: str
    triangles: tuple | None = None
    solid: object | None = None
    pivot: tuple = (0., 0., 0.)
    moving: bool = False
    tolerance_m: float = 0.
    low: tuple = field(init=False)
    high: tuple = field(init=False)
    radius: float = field(init=False)

    def __post_init__(self):
        if (self.triangles is None) == (self.solid is None):
            raise ValueError('Motion shape requires exactly one surface or solid.')
        if type(self.moving) is not bool or not isinstance(self.name, str) or not self.name:
            raise ValueError('Invalid motion shape identity.')
        if isinstance(self.tolerance_m, bool) or not isinstance(self.tolerance_m, (int, float)) or not 0 <= self.tolerance_m <= .1:
            raise ValueError('Hardware tolerance must be finite in [0, 0.1] m.')
        if len(self.pivot) != 3 or any(not math.isfinite(v) or abs(v)>10 for v in self.pivot):
            raise ValueError('Invalid motion pivot.')
        if self.triangles is not None:
            SurfacePart(self.name, self.triangles, self.pivot, self.moving)
            vertices = tuple(p for tri in self.triangles for p in tri)
        else:
            if not isinstance(self.solid, (ConvexSolid, CylinderEnvelope)):
                raise ValueError('Unsupported hardware solid.')
            outer = self.solid.outer if isinstance(self.solid, CylinderEnvelope) else self.solid
            vertices = outer.vertices
        object.__setattr__(self, 'low', tuple(min(p[i] for p in vertices) for i in range(3)))
        object.__setattr__(self, 'high', tuple(max(p[i] for p in vertices) for i in range(3)))
        object.__setattr__(self, 'radius', max(math.hypot(p[0]-self.pivot[0], p[1]-self.pivot[1]) for p in vertices) + PAD)

    @classmethod
    def from_part(cls, part):
        return cls(part.name, triangles=part.triangles, pivot=part.pivot, moving=part.moving)

    def displacement(self, width):
        return 2 * self.radius * math.sin(width/4) if self.moving else 0.

    def bounds(self, angle, width):
        corners = tuple((x, y, z) for x in (self.low[0], self.high[0])
                        for y in (self.low[1], self.high[1]) for z in (self.low[2], self.high[2]))
        if self.moving:
            corners = tuple(_rotate(p, self.pivot, angle) for p in corners)
        pad = self.displacement(width) + self.tolerance_m + PAD
        return (tuple(min(p[i] for p in corners)-pad for i in range(3)),
                tuple(max(p[i] for p in corners)+pad for i in range(3)))

    def posed(self, angle):
        angle = angle if self.moving else 0.
        if self.triangles is not None:
            return tuple(tuple(_rotate(p, self.pivot, angle) for p in tri) for tri in self.triangles)
        if angle == 0:
            return self.solid
        r = rotation_z(angle)
        t = tuple(self.pivot[i] - sum(r[i][j]*self.pivot[j] for j in range(3)) for i in range(3))
        return transformed_solid(self.solid, r, t)


def _row(left, right, status='unknown', **kwargs):
    return dict(angle_min_rad=left, angle_max_rad=right, status=status,
                lower_bound_m=None, witness_clearance_m=None, witness_angle_rad=None,
                method='hardware_budget_exhausted', contact_status='unknown', point_a=None, point_b=None) | kwargs


def query_motion_pair(a, b, *, angle_min_rad, angle_max_rad, clearance_m,
                      max_queries, max_depth, max_intervals):
    if not isinstance(a, MotionShape) or not isinstance(b, MotionShape) or (a.solid is None and b.solid is None):
        raise ValueError('Hardware motion requires at least one solid.')
    for value, lo, hi in ((max_queries,0,10000),(max_depth,0,8),(max_intervals,1,255)):
        if type(value) is not int or not lo<=value<=hi:
            raise ValueError('Invalid hardware work budget.')
    for v in (angle_min_rad,angle_max_rad,clearance_m):
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
            raise ValueError('Motion query requires finite numeric values.')
    if not -math.pi<=angle_min_rad<=angle_max_rad<=0 or not 0<=clearance_m<=.1:
        raise ValueError('Unsupported hardware motion interval or clearance.')
    pending = [(angle_min_rad, angle_max_rad, 0)]
    rows, used, attempted = [], 0, 0
    status, witness, contact = 'unknown', None, 'unknown'
    while pending:
        left, right, depth = pending.pop()
        if used >= max_queries or attempted >= max_intervals:
            rows.append(_row(left, right))
            continue
        attempted += 1
        used += 1  # Bounding-volume work is also charged to the shared budget.
        mid, width = (left+right)/2, right-left
        box_a, box_b = a.bounds(mid,width), b.bounds(mid,width)
        gap = max(0., math.sqrt(sum(max(0.,box_a[0][i]-box_b[1][i],box_b[0][i]-box_a[1][i])**2 for i in range(3))) - PAD)
        if gap > clearance_m + PAD:
            rows.append(_row(left,right,'separated',lower_bound_m=gap,method='hardware_aabb_bound',contact_status='separated'))
            continue
        detail = None
        if used < max_queries:
            posed_a, posed_b = a.posed(mid), b.posed(mid)
            if a.solid is None:
                detail = surface_solid_distance(posed_a,posed_b,max_triangle_queries=max_queries-used)
            elif b.solid is None:
                detail = surface_solid_distance(posed_b,posed_a,max_triangle_queries=max_queries-used)
            else:
                detail = solid_solid_distance(posed_a,posed_b,max_triangle_queries=max_queries-used)
            used += detail.queries
            uncertainty = a.tolerance_m + b.tolerance_m + PAD
            margin = 0.
            if detail.penetration and detail.point_a is not None:
                margins = [interior_margin(solid,detail.point_a) for shape,solid in ((a,posed_a),(b,posed_b)) if shape.solid is not None]
                margin = min(margins)
            upper = detail.upper_m + uncertainty
            if margin > uncertainty or upper < clearance_m - PAD:
                status, contact = 'violation', 'penetrating' if margin>uncertainty else detail.contact_status
                witness = -(margin-uncertainty) if margin>uncertainty else upper
                pa,pb = detail.point_a,detail.point_b
                if a.solid is not None and b.solid is None:
                    pa,pb=pb,pa
                rows.append(_row(left,right,status,witness_clearance_m=witness,witness_angle_rad=mid,
                    method=detail.reason,contact_status=contact,point_a=pa,point_b=pb))
                rows.extend(_row(lo,hi) for lo,hi,_ in pending)
                break
            lower = max(0.,detail.lower_m-uncertainty-a.displacement(width)-b.displacement(width))
            if lower > clearance_m + PAD:
                rows.append(_row(left,right,'separated',lower_bound_m=lower,method=detail.reason,contact_status='separated'))
                continue
        if depth<max_depth and right>left and attempted<max_intervals and used<max_queries:
            pending.extend(((mid,right,depth+1),(left,mid,depth+1)))
        else:
            rows.append(_row(left,right,method=detail.reason if detail else 'hardware_budget_exhausted',
                contact_status='nominal_pose_contact' if detail and (detail.penetration or detail.contact_status=='confirmed') else 'unknown'))
    if status != 'violation' and all(r['status']=='separated' for r in rows):
        status,contact='separated','separated'
    return dict(status=status,lower_bound_m=min(r['lower_bound_m'] for r in rows) if status=='separated' else None,
        witness_clearance_m=witness,node_comparisons=0,feature_tests=0,hardware_queries=used,
        intervals=rows,contact_status=contact,reason='declared_hardware_motion_screening; no physical qualification')
