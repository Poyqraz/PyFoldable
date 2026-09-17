"""Bounded convex hardware geometry; open blade surfaces remain open surfaces.

Polyhedra are validated with exact rational predicates. A finite cylinder is
bracketed by certified inner/outer prisms: lower distances use the outer solid,
upper distances use the inner solid. Neither approximation is physical evidence.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as F
import math

from .triangle_distance import triangle_distance

MAX_VERTICES = 64
MAX_FACES = 128
MAX_QUERY_TRIANGLES = 12000
MAX_TRIANGLE_QUERIES = 200000
MAX_RATIONAL_BITS = 4096


class _PrecisionLimit(ValueError):
    pass


def _checked(q):
    q = F(q)
    if max(q.numerator.bit_length(), q.denominator.bit_length()) > MAX_RATIONAL_BITS:
        raise _PrecisionLimit("Hardware rational precision limit exceeded.")
    return q


def _number(x, domain=10):
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError('Hardware coordinates must be finite numbers.')
    try:
        x = float(x)
    except (OverflowError, ValueError) as exc:
        raise ValueError('Hardware coordinates must be finite numbers.') from exc
    if not math.isfinite(x) or abs(x) > domain:
        raise ValueError(f"Hardware coordinate domain is +/-{domain} m.")
    if F(x).denominator.bit_length() > 512:
        raise ValueError('Hardware coordinate precision exceeds the bounded domain.')
    return x


def _point(p, domain=10):
    if not isinstance(p, (tuple, list)) or len(p) != 3:
        raise ValueError('Expected an xyz point.')
    return tuple(_number(x, domain) for x in p)


def _q(p): return tuple(_checked(x) for x in p)
def _sub(a,b): return tuple(_checked(x-y) for x,y in zip(a,b))
def _dot(a,b): return _checked(sum(x*y for x,y in zip(a,b)))
def _cross(a,b): return tuple(_checked(q) for q in (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]))


def _sqrt_bounds(q):
    q = _checked(q)
    if q == 0: return 0., 0.
    value = math.sqrt(float(q))
    lower = upper = value
    for _ in range(16):
        if F(lower)*F(lower) <= q: break
        lower = math.nextafter(lower, -math.inf)
    for _ in range(16):
        if F(upper)*F(upper) >= q: break
        upper = math.nextafter(upper, math.inf)
    if not F(lower)*F(lower) <= q <= F(upper)*F(upper):
        raise _PrecisionLimit('Could not bound hardware arithmetic.')
    return lower, upper


def _exact_vertices(solid):
    return getattr(solid, '_query_vertices', tuple(_q(p) for p in solid.vertices))


def _planes(vertices, faces):
    v=tuple(_q(p) for p in vertices)
    return tuple((_cross(_sub(v[b],v[a]),_sub(v[c],v[a])),v[a]) for a,b,c in faces)


@dataclass(frozen=True)
class ConvexSolid:
    vertices: tuple
    faces: tuple

    def __post_init__(self):
        if not isinstance(self.vertices,(list,tuple)) or not 4 <= len(self.vertices) <= MAX_VERTICES:
            raise ValueError('Convex solid requires 4..64 vertices.')
        if not isinstance(self.faces,(list,tuple)) or not 4 <= len(self.faces) <= MAX_FACES:
            raise ValueError('Convex solid requires 4..128 triangular faces.')
        vertices=tuple(_point(p) for p in self.vertices)
        if len(set(vertices)) != len(vertices):
            raise ValueError('Duplicate vertices are not supported.')
        faces=[]
        edges={}
        links=[{} for _ in vertices]
        for face in self.faces:
            if not isinstance(face,(list,tuple)) or len(face)!=3 or any(type(i) is not int or not 0 <= i < len(vertices) for i in face) or len(set(face))!=3:
                raise ValueError('Invalid triangular face indices.')
            a,b,c=face
            faces.append(tuple(face))
            for u,v in ((a,b),(b,c),(c,a)):
                edges.setdefault(tuple(sorted((u,v))),[]).append((u,v))
            for u,v,w in ((a,b,c),(b,c,a),(c,a,b)):
                links[u].setdefault(v,[]).append(w)
                links[u].setdefault(w,[]).append(v)
        if len({tuple(sorted(f)) for f in faces}) != len(faces):
            raise ValueError('Duplicate faces.')
        if any(len(e)!=2 or e[0] != e[1][::-1] for e in edges.values()):
            raise ValueError('Hardware must be closed with consistent face orientation.')
        if len(vertices)-len(edges)+len(faces) != 2:
            raise ValueError('Hardware must have a spherical convex boundary.')
        for link in links:
            if not link or any(len(n)!=2 for n in link.values()):
                raise ValueError('Non-manifold vertex.')
            reached=set();todo=[next(iter(link))]
            while todo:
                u=todo.pop()
                if u not in reached:
                    reached.add(u);todo.extend(link[u])
            if len(reached)!=len(link):
                raise ValueError('Disconnected vertex link.')
        qv=tuple(_q(p) for p in vertices)
        planes=_planes(vertices,faces)
        for n,p in planes:
            if n==(0,0,0) or any(_dot(n,_sub(v,p))>0 for v in qv):
                raise ValueError('Faces must be nondegenerate, outward and convex.')
        volume6=sum(_dot(qv[a],_cross(qv[b],qv[c])) for a,b,c in faces)
        if volume6<=0:
            raise ValueError('Hardware must enclose positive volume.')
        # A closed orientable manifold whose every face supports the convex hull
        # and whose vertex links are single circles is its convex boundary.
        object.__setattr__(self,'vertices',vertices)
        object.__setattr__(self,'faces',tuple(faces))

    @property
    def triangles(self):
        return tuple(tuple(self.vertices[i] for i in face) for face in self.faces)


@dataclass(frozen=True)
class CylinderEnvelope:
    inner: ConvexSolid
    outer: ConvexSolid
    approximation_error_m: float
    radius_m: float
    height_m: float


def _prism(r,height,n):
    xy=tuple((r*math.cos(2*math.pi*i/n),r*math.sin(2*math.pi*i/n)) for i in range(n))
    vertices=tuple((x,y,z) for z in (-height/2,height/2) for x,y in xy)
    faces=[]
    for i in range(1,n-1):
        faces.extend(((0,i+1,i),(n,n+i,n+i+1)))
    for i in range(n):
        j=(i+1)%n
        faces.extend(((i,j,n+j),(i,n+j,n+i)))
    return ConvexSolid(vertices,tuple(faces))


def finite_cylinder(*,radius_m,height_m,segments,approximation_tolerance_m):
    r=_number(radius_m);h=_number(height_m);tol=_number(approximation_tolerance_m)
    if min(r,h,tol)<=0 or type(segments) is not int or not 8 <= segments <= 32:
        raise ValueError('Cylinder requires positive explicit dimensions/tolerance and 8..32 segments.')
    inner=_prism(r*(1-1e-12),h,segments)
    outer=_prism(r/math.cos(math.pi/segments)*(1+1e-12),h,segments)
    rq=F(r)
    # Certify enclosures against the input radius, not approximate trigonometry.
    if any(F(x)**2+F(y)**2 > rq*rq for x,y,z in inner.vertices):
        raise ValueError('Could not certify cylinder inner envelope.')
    for n,p in _planes(outer.vertices,outer.faces):
        if n[2]==0:
            d=_dot(n,p)
            if d<=0 or d*d < rq*rq*(n[0]*n[0]+n[1]*n[1]):
                raise ValueError('Could not certify cylinder outer envelope.')
    # Bound each envelope's Hausdorff error to the actual cylinder with
    # rational squared radii/distances and outward-rounded square roots.
    outer_r=max(_sqrt_bounds(F(x)**2+F(y)**2)[1] for x,y,z in outer.vertices)
    inner_r=min(_sqrt_bounds(_dot(n,p)**2/(n[0]**2+n[1]**2))[0]
                for n,p in _planes(inner.vertices,inner.faces) if n[2]==0)
    error=math.nextafter(max(outer_r-r,r-inner_r),math.inf)
    if error>tol:
        raise ValueError('Explicit cylinder approximation tolerance is too small for the segment count.')
    return CylinderEnvelope(inner,outer,error,r,h)


def validate_transform(rotation,translation):
    if not isinstance(rotation,(tuple,list)) or len(rotation)!=3:
        raise ValueError('Rotation must be 3x3.')
    r=tuple(_point(row) for row in rotation);t=_point(translation, 64)
    if any(abs(_dot(r[i],r[j])-(1 if i==j else 0))>2e-12 for i in range(3) for j in range(3)) or abs(_dot(r[0],_cross(r[1],r[2]))-1)>2e-12:
        raise ValueError('Transform must be a proper rigid rotation.')
    return r,t


def transform_solid(solid,rotation,translation):
    """Transform an already validated solid; no topology repair or inference."""
    r,t=validate_transform(rotation,translation)
    if isinstance(solid,CylinderEnvelope):
        return CylinderEnvelope(transform_solid(solid.inner,r,t),transform_solid(solid.outer,r,t),solid.approximation_error_m,solid.radius_m,solid.height_m)
    if not isinstance(solid,ConvexSolid):
        raise ValueError('Unsupported hardware solid.')
    qr=tuple(_q(row) for row in r);qt=_q(t)
    exact=tuple(tuple(_checked(_dot(row,p)+off) for row,off in zip(qr,qt)) for p in _exact_vertices(solid))
    vertices=tuple(_point(tuple(float(x) for x in p), 64) for p in exact)
    rounding=max(_sqrt_bounds(sum((x-F(y))**2 for x,y in zip(p,v)))[1] for p,v in zip(exact,vertices))
    # Exact affine coordinates preserve the validated topology and containment;
    # triangle distances account for conversion of those coordinates to float.
    result=object.__new__(ConvexSolid)
    object.__setattr__(result,'vertices',vertices)
    object.__setattr__(result,'faces',solid.faces)
    object.__setattr__(result,'_query_vertices',exact)
    object.__setattr__(result,'_rounding_error_m',rounding)
    return result


transformed_solid=transform_solid


@dataclass(frozen=True)
class SolidDistanceResult:
    lower_m: float
    upper_m: float
    penetration: bool | None
    contact_status: str
    triangle_queries: int
    reason: str
    point_a: tuple | None = None
    point_b: tuple | None = None

    @property
    def queries(self): return self.triangle_queries


def _clip_exact(triangle,planes):
    polygon=list(map(_q,triangle))
    for n,p in planes:
        clipped=[]
        for a,b in zip(polygon,polygon[1:]+polygon[:1]):
            da=_dot(n,_sub(a,p));db=_dot(n,_sub(b,p))
            if da<=0:clipped.append(a)
            if (da<0 and db>0) or (da>0 and db<0):
                ratio=_checked(da/(da-db))
                clipped.append(tuple(_checked(x+ratio*(y-x)) for x,y in zip(a,b)))
        polygon=clipped
        if not polygon:break
    if not polygon:return None,False
    witness=tuple(_checked(sum(p[i] for p in polygon)/len(polygon)) for i in range(3))
    strict=all(_dot(n,_sub(witness,p))<0 for n,p in planes)
    return witness,strict


def _clip(triangle, planes):
    witness, strict = _clip_exact(triangle, planes)
    return (None if witness is None else tuple(float(x) for x in witness)), strict


def _query_exact(triangles,solid,budget,source_error=0.):
    if budget==0:return SolidDistanceResult(0.,math.inf,None,'unknown',0,'triangle_budget_exhausted')
    lower=math.inf;upper=math.inf;qa=qb=None;count=0;contact=False
    planes=_planes(_exact_vertices(solid),solid.faces)
    error=math.nextafter(getattr(solid,'_rounding_error_m',0.)+source_error,math.inf) if source_error else getattr(solid,'_rounding_error_m',0.)
    for tri in triangles:
        # One metered primitive per triangle includes bounded <=128 planes.
        if count>=budget:return SolidDistanceResult(0.,upper,None,'unknown',count,'triangle_budget_exhausted',qa,qb)
        count+=1
        witness,strict=_clip(tri,planes)
        if strict:return SolidDistanceResult(0.,0.,True,'penetrating',count,'exact_convex_interior',witness,witness)
        if witness is not None:
            contact=True;lower=0.;upper=0.;qa=qb=witness
        for face in solid.triangles:
            if count>=budget:return SolidDistanceResult(0.,upper,None,'confirmed' if contact else 'unknown',count,'triangle_budget_exhausted',qa,qb)
            count+=1
            result=triangle_distance(tri,face)
            if result.contact_status == 'unknown':
                return SolidDistanceResult(0., upper, None, 'unknown', count,
                    'precision_limit' if result.reason == 'exact_arithmetic_limit' else 'triangle_budget_exhausted', qa, qb)
            safe_lower=max(0.,math.nextafter(result.lower_m-error,-math.inf)) if error else result.lower_m
            safe_upper=math.nextafter(result.upper_m+error,math.inf) if error else result.upper_m
            lower=min(lower,safe_lower)
            if safe_upper<upper:
                upper=safe_upper;qa=result.point_a;qb=result.point_b
    return SolidDistanceResult(lower,upper,False,'confirmed' if contact else ('separated' if lower>0 else 'unknown'),count,'exact_convex_surface_distance',qa,qb)



def _query(triangles, solid, budget, source_error=0.):
    try:
        return _query_exact(triangles, solid, budget, source_error)
    except _PrecisionLimit:
        # A precision failure consumes the remaining allocation: callers may
        # not repeatedly perform unmetered failed exact operations.
        return SolidDistanceResult(0., math.inf, None, 'unknown', budget, 'precision_limit')


def interior_margin(solid, point):
    """Conservative distance to the interior boundary; zero without proof.

    Uses exact halfspaces of a convex solid (the certified *inner* cylinder
    envelope). Floating conversion rounds the squared plane distance downward.
    """
    if isinstance(solid, CylinderEnvelope):
        solid = solid.inner
    if not isinstance(solid, ConvexSolid):
        raise ValueError('Unsupported hardware solid.')
    try:
        q = _q(_point(point, 64))
        margin = math.inf
        for n, p in _planes(_exact_vertices(solid), solid.faces):
            d = _dot(n, _sub(p, q))
            if d <= 0:
                return 0.
            margin = min(margin, _sqrt_bounds(_checked(d*d/_dot(n, n)))[0])
        return margin
    except _PrecisionLimit:
        return 0.


def _shared_interior(a, b, budget):
    """Exact convex intersection witness, including coincident boundaries.

    Every vertex of the intersection belongs to at least one clipped boundary
    face. Averaging the relative-interior points of all nonempty clipped faces
    lies strictly inside both full-dimensional solids iff their intersection
    has interior. Thus this also covers coincident and coplanar-overlap solids,
    which bidirectional boundary penetration alone cannot distinguish.
    """
    count = 0
    witnesses = []
    try:
        ap = _planes(_exact_vertices(a), a.faces)
        bp = _planes(_exact_vertices(b), b.faces)
        for source, planes in ((a, bp), (b, ap)):
            vertices = _exact_vertices(source)
            for face in source.faces:
                if count >= budget:
                    return None, count, 'triangle_budget_exhausted'
                count += 1
                witness, _ = _clip_exact(tuple(vertices[i] for i in face), planes)
                if witness is not None:
                    witnesses.append(witness)
        if not witnesses:
            return None, count, 'complete'
        q = tuple(_checked(sum(p[i] for p in witnesses)/len(witnesses)) for i in range(3))
        if not all(_dot(n, _sub(q, p)) < 0 for n, p in ap + bp):
            return None, count, 'complete'
        rounded = tuple(float(x) for x in q)
        # Returned coordinates, as used by the motion caller, must themselves
        # have strict interior support, not only the unrounded rational point.
        if interior_margin(a, rounded) > 0 and interior_margin(b, rounded) > 0:
            return rounded, count, 'complete'
        return None, count, 'precision_limit'
    except _PrecisionLimit:
        return None, budget, 'precision_limit'


def _inputs(triangles,budget):
    if type(budget) is not int or not 0<=budget<=MAX_TRIANGLE_QUERIES:
        raise ValueError('Invalid hardware triangle query budget.')
    if not isinstance(triangles,(tuple,list)) or not 1<=len(triangles)<=MAX_QUERY_TRIANGLES:
        raise ValueError('Surface requires 1..12000 triangles.')
    result=[]
    for tri in triangles:
        if not isinstance(tri,(tuple,list)) or len(tri)!=3:raise ValueError('Expected triangular surface.')
        result.append(tuple(_point(p, 64) for p in tri))
    return tuple(result)


def surface_solid_distance(triangles,solid,*,max_triangle_queries=5000):
    triangles=_inputs(triangles,max_triangle_queries)
    if isinstance(solid,ConvexSolid):return _query(triangles,solid,max_triangle_queries)
    if not isinstance(solid,CylinderEnvelope):raise ValueError('Unsupported hardware solid.')
    inner=_query(triangles,solid.inner,max_triangle_queries)
    if inner.penetration:
        return SolidDistanceResult(0.,0.,True,'penetrating',inner.queries,'certified_cylinder_inner_penetration',inner.point_a,inner.point_b)
    remaining=max_triangle_queries-inner.queries
    outer=_query(triangles,solid.outer,remaining)
    return SolidDistanceResult(outer.lower_m,inner.upper_m,False if outer.lower_m>0 else None,
        'separated' if outer.lower_m>0 else 'unknown',inner.queries+outer.queries,
        next((r.reason for r in (inner,outer) if r.reason in ('triangle_budget_exhausted','precision_limit')), 'certified_cylinder_envelope'),inner.point_a,inner.point_b)


def solid_solid_distance(a,b,*,max_triangle_queries=5000):
    if not isinstance(a,(ConvexSolid,CylinderEnvelope)) or not isinstance(b,(ConvexSolid,CylinderEnvelope)):
        raise ValueError('Unsupported hardware solid.')
    if type(max_triangle_queries) is not int or not 0 <= max_triangle_queries <= MAX_TRIANGLE_QUERIES:
        raise ValueError('Invalid hardware triangle query budget.')
    # Distance between solid boundaries needs containment checks in both orders.
    ai=a.inner if isinstance(a,CylinderEnvelope) else a
    bi=b.inner if isinstance(b,CylinderEnvelope) else b
    ao=a.outer if isinstance(a,CylinderEnvelope) else a
    bo=b.outer if isinstance(b,CylinderEnvelope) else b
    def query(a,b,budget):
        triangles=tuple(tuple(_exact_vertices(a)[i] for i in f) for f in a.faces)
        return _query(triangles,b,budget,getattr(a,'_rounding_error_m',0.))
    witness, pre_count, pre_reason = _shared_interior(ai, bi, max_triangle_queries)
    if witness is not None:
        return SolidDistanceResult(0., 0., True, "penetrating", pre_count, "exact_shared_solid_interior", witness, witness)
    if pre_reason != "complete":
        return SolidDistanceResult(0., math.inf, None, "unknown", pre_count, pre_reason)
    first=query(ai,bi,max_triangle_queries-pre_count)
    remaining=max_triangle_queries-pre_count-first.queries
    second=query(bi,ai,remaining)
    count=pre_count+first.queries+second.queries
    if a is ai and b is bi:
        lower = min(first.lower_m, second.lower_m)
        best = min((first, second), key=lambda r: r.upper_m)
        incomplete = next((r.reason for r in (first, second)
                           if r.reason in ('triangle_budget_exhausted', 'precision_limit')), None)
        return SolidDistanceResult(lower, best.upper_m,
            False if incomplete is None else None,
            ('unknown' if incomplete else 'separated' if lower > 0 else
             'confirmed' if 'confirmed' in (first.contact_status,second.contact_status) else 'unknown'),
            count, incomplete or 'exact_solid_distance', best.point_a, best.point_b)
    lower=query(ao,bo,max_triangle_queries-count);count+=lower.queries
    reverse=query(bo,ao,max_triangle_queries-count);count+=reverse.queries
    bound = min(lower.lower_m, reverse.lower_m)
    best = min((first, second), key=lambda r: r.upper_m)
    incomplete = next((r.reason for r in (first,second,lower,reverse)
                       if r.reason in ('triangle_budget_exhausted', 'precision_limit')), None)
    return SolidDistanceResult(bound, best.upper_m, False if bound>0 else None,
        'separated' if bound>0 else 'unknown', count,
        incomplete or 'certified_solid_envelopes', best.point_a, best.point_b)
