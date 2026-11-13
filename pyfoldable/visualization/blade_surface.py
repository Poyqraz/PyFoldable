"""Lofted 3-D blade surfaces from the catalog profile coordinates and the design stations (no CAD).

Frame and conventions (identical to the coupled model, ``pyfoldable/coupled/frames.py``): blade body
frame of blade 1 with x along the chord from leading to trailing edge, y along the span (outward from
the shaft) and z the lift normal; shaft +Z, rotation +Omega about +Z, so the leading edge (-x) leads.
Sections are stacked on the quarter-chord line (x = 0, z = 0) and twisted about it; positive twist
lifts the leading edge (+z). Chord and twist vary linearly in radius between declared stations, as in
the BEM (``linear_chord_twist``). The hinge axis is parallel to the shaft through the quarter-chord
point of the hinge section; a negative fold rotates the distal part back toward the trailing side.

Regions: ``aero`` is the surface the analyses use (first to last declared station, split at the hinge
into proximal and distal parts, each closed: upper and lower surfaces, the catalog's open trailing-edge
face, end caps at the first/last station and a cut face at the hinge, which marks where the
aerodynamic geometry is split, not a joint design). ``undefined`` marks the radial ranges with no
surface data (physical root to the first station, last station to the tip): placeholders extruded from
the nearest declared section, never coloured with results. Reconstructed geometry, not CAD.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class BladeSpec:
    profile_id: str
    profile: tuple                       # Selig order (x/c, z/c): upper TE -> LE -> lower TE
    stations: tuple                      # ((radius_m, chord_m, twist_rad), ...) ascending radius
    hub_radius_m: float
    root_radius_m: float | None          # declared physical blade start, if any
    hinge_radius_m: float
    tip_radius_m: float
    blade_count: int

    def __post_init__(self):
        r = [s[0] for s in self.stations]
        if len(r) < 2 or any(b <= a for a, b in zip(r, r[1:])):
            raise ValueError("Stations must be at least two, ascending in radius.")
        if not r[0] < self.hinge_radius_m < r[-1]:
            raise ValueError("The hinge must lie strictly inside the station span.")
        if r[-1] > self.tip_radius_m + 1e-12 or self.hub_radius_m > r[0] + 1e-12:
            raise ValueError("Stations must lie between the hub and the tip radius.")


def require_default_hinge(hinge) -> None:
    """The loft assumes the hinge axis is parallel to the shaft through the quarter-chord line (as every
    consumer in the repository does); any other declared axis is refused instead of drawn wrongly."""
    if (abs(hinge.axial_offset_m) > 1e-12 or abs(hinge.tangential_offset_m) > 1e-12
            or abs(hinge.axis_azimuth_rad) > 1e-12 or abs(hinge.axis_elevation_rad - math.pi / 2) > 1e-9):
        raise ValueError("Only a hinge axis parallel to the shaft through the quarter-chord line without offsets "
                         "is supported by the lofted view (declared hinge axis differs).")


def spec_from_design(active, foil) -> BladeSpec:
    """Exact geometry of the active research design (no rescaling, no filled-in values)."""
    d = active.design
    require_default_hinge(d.hinge)
    R = d.blade.radius_m
    root = getattr(active, "root", None)
    root_m = None if root is None else root.value / 1000.0
    return BladeSpec(foil.id, tuple(tuple(map(float, p)) for p in foil.coordinates),
                     tuple((s.r_over_R * R, s.chord_m, s.twist_rad) for s in d.blade.stations),
                     d.blade.hub_radius_m, root_m, d.hinge.radius_m, R, d.blade.blade_count)


def section_at(spec: BladeSpec, radius: float) -> tuple[float, float]:
    r = [s[0] for s in spec.stations]
    return (float(np.interp(radius, r, [s[1] for s in spec.stations])),
            float(np.interp(radius, r, [s[2] for s in spec.stations])))


def resample_profile(coords, n_side: int = 64) -> np.ndarray:
    """Cosine-spaced resampling per side; keeps the exact leading-edge point and both trailing-edge points."""
    raw = np.asarray(coords, dtype=float)
    le = int(np.argmin(raw[:, 0]))
    upper = raw[:le + 1][::-1]           # LE -> upper TE
    lower = raw[le:]                     # LE -> lower TE
    xm = 0.5 * (raw[le, 0] + max(raw[0, 0], raw[-1, 0]))
    zu = np.interp(xm, *upper[np.argsort(upper[:, 0], kind="stable")].T)
    zl = np.interp(xm, *lower[np.argsort(lower[:, 0], kind="stable")].T)
    if not (0 < le < len(raw) - 1 and zu > zl):
        raise ValueError("Profile coordinates must be in Selig order (upper TE -> LE -> lower TE).")
    k = np.arange(n_side)

    def side(pts):
        xs = pts[0, 0] + (pts[-1, 0] - pts[0, 0]) * 0.5 * (1.0 - np.cos(math.pi * k / (n_side - 1)))
        order = np.argsort(pts[:, 0], kind="stable")
        z = np.interp(xs, pts[order, 0], pts[order, 1])
        z[0], z[-1] = pts[0, 1], pts[-1, 1]
        return np.column_stack([xs, z])
    u, lo = side(upper), side(lower)
    return np.vstack([u[::-1], lo[1:]])


def _ring(prof, chord, twist, y):
    X, Z = (prof[:, 0] - 0.25) * chord, prof[:, 1] * chord
    c, s = math.cos(twist), math.sin(twist)
    return np.column_stack([X * c + Z * s, np.full(len(prof), y), -X * s + Z * c])


@dataclass
class BladeMesh:
    spec: BladeSpec
    joint: str                           # "plane" (split at the hinge radius) | "relief" (circular joint zone)
    vertices: np.ndarray                 # (N, 3) unfolded body frame of blade 1 [m]
    faces: np.ndarray                    # (M, 3)
    region: np.ndarray                   # per face: "aero" | "joint" | "undefined"
    surface: np.ndarray                  # per face: upper | lower | te_face | end_cap | joint_cut | placeholder
    face_part: np.ndarray                # per face: proximal | distal
    face_radius: np.ndarray              # per face: spanwise centroid position [m] (unfolded)
    vertex_part: np.ndarray              # per vertex: proximal | distal
    vertex_source: np.ndarray            # per vertex: index in the continuous analysis surface (-1: placeholder)
    joint_radius_m: float                # radius of the joint zone about the pivot (relief) or 0
    rings: list = field(default_factory=list)   # (radius, source index array)

    def section_index(self, radius: float, part: str | None = None) -> np.ndarray:
        for r, src in self.rings:
            if abs(r - radius) < 1e-12:
                sel = np.isin(self.vertex_source, src)
                if part is not None:
                    sel &= self.vertex_part == part
                idx = np.flatnonzero(sel)
                _, first = np.unique(self.vertex_source[idx], return_index=True)
                order = np.argsort(np.searchsorted(src, self.vertex_source[idx][first]))
                return idx[first][order]
        raise KeyError(radius)

    def face_centroids(self) -> np.ndarray:
        return self.vertices[self.faces].mean(axis=1)

    def posed(self, fold_rad: float = 0.0, azimuth_rad: float = 0.0) -> np.ndarray:
        """World coordinates: distal rotated by the fold about the hinge axis, then the blade about +Z."""
        return pose_points(self.vertices, self.vertex_part == "distal", self.spec.hinge_radius_m, fold_rad, azimuth_rad)


def pose_points(v, distal_mask, hinge_radius, fold_rad, azimuth_rad=0.0):
    v = np.array(v, dtype=float, copy=True)
    c, s = math.cos(fold_rad), math.sin(fold_rad)
    x, yh = v[distal_mask, 0], v[distal_mask, 1] - hinge_radius
    v[distal_mask, 0], v[distal_mask, 1] = x * c - yh * s, hinge_radius + x * s + yh * c
    if azimuth_rad:
        ca, sa = math.cos(azimuth_rad), math.sin(azimuth_rad)
        v[:, 0], v[:, 1] = v[:, 0] * ca - v[:, 1] * sa, v[:, 0] * sa + v[:, 1] * ca
    return v


def joint_radius(spec: BladeSpec, prof: np.ndarray) -> float:
    """Radius of the joint zone about the pivot: the in-plane extent of the sections it covers (the blade
    tapers, so the inboard section at r_h - rho is wider than the hinge section), plus a 2 % margin."""
    h = spec.hinge_radius_m
    rho = float(np.abs(_ring(prof, *section_at(spec, h), h)[:, 0]).max())
    for _ in range(3):
        y = max(spec.stations[0][0], h - rho)
        rho = 1.02 * max(rho, float(np.abs(_ring(prof, *section_at(spec, y), y)[:, 0]).max()))
    return rho


def in_joint_zone(x, y, spec: BladeSpec, rho: float):
    """Inboard half-disk about the pivot (x = 0, y = r_h): moves with the distal part (relief mode)."""
    return (np.hypot(x, y - spec.hinge_radius_m) <= rho) & (y <= spec.hinge_radius_m)


def loft(spec: BladeSpec, *, n_side: int = 64, dr: float = 0.002, joint: str = "plane") -> BladeMesh:
    if joint not in ("plane", "relief"):
        raise ValueError("joint must be 'plane' or 'relief'")
    prof = resample_profile(spec.profile, n_side)
    closed = float(np.linalg.norm(prof[0] - prof[-1])) < 1e-9
    if closed:
        prof = prof[:-1]
    P = len(prof)
    r_st = [s[0] for s in spec.stations]
    h = round(spec.hinge_radius_m, 12)   # the grid is rounded to 12 decimals; look the hinge ring up the same way
    grid = sorted(set(np.round(np.concatenate([np.arange(r_st[0], r_st[-1], dr), r_st, [h]]), 12)))
    grid = [float(y) for y in grid if r_st[0] - 1e-12 <= y <= r_st[-1] + 1e-12]
    # continuous analysis surface (one ring per grid radius)
    src_v = np.vstack([_ring(prof, *section_at(spec, y), y) for y in grid])
    rings = [(y, np.arange(k * P, (k + 1) * P)) for k, y in enumerate(grid)]
    tris, surf = [], []
    for k in range(len(grid) - 1):
        a, b = rings[k][1], rings[k + 1][1]
        for j in range(P if closed else P - 1):
            j2 = (j + 1) % P
            name = "upper" if j < n_side - 1 else "lower"
            tris += [(a[j], b[j], b[j2]), (a[j], b[j2], a[j2])]
            surf += [name, name]
        if not closed:                                     # catalog's finite trailing-edge thickness
            tris += [(a[P - 1], b[P - 1], b[0]), (a[P - 1], b[0], a[0])]
            surf += ["te_face", "te_face"]
    centres = []
    for ring, flip in ((rings[0][1], False), (rings[-1][1], True)):
        pts = src_v[ring]
        cxz = pts[:, [0, 2]].mean(axis=0)
        centres.append([cxz[0], pts[0, 1], cxz[1]])
        c = len(src_v) + len(centres) - 1
        for j in range(P):
            a, b = ring[j], ring[(j + 1) % P]
            tris.append((c, b, a) if flip else (c, a, b))
            surf.append("end_cap")
    src_v = np.vstack([src_v, centres])
    tris = np.asarray(tris, dtype=int)
    cen = src_v[tris].mean(axis=1)
    rho = joint_radius(spec, prof) if joint == "relief" else 0.0
    is_joint = in_joint_zone(cen[:, 0], cen[:, 1], spec, rho) if joint == "relief" else np.zeros(len(tris), bool)
    part = np.where(is_joint | (cen[:, 1] > h), "distal", "proximal")
    region = np.where(is_joint, "joint", "aero")

    verts, vpart, vsrc, faces, regions, surfaces, fparts, frads = [], [], [], [], [], [], [], []
    base = 0
    for name in ("proximal", "distal"):
        sel = part == name
        used = np.unique(tris[sel])
        remap = {int(s): base + i for i, s in enumerate(used)}
        verts.append(src_v[used]); vpart += [name] * len(used); vsrc += list(map(int, used))
        faces += [[remap[int(i)] for i in f] for f in tris[sel]]
        regions += list(region[sel]); surfaces += list(np.asarray(surf)[sel]); fparts += [name] * int(sel.sum())
        frads += list(cen[sel, 1])
        base += len(used)
        if joint == "plane":                               # cut face where the analysis geometry is split
            hinge_src = rings[grid.index(h)][1]
            ring = [remap[int(s)] for s in hinge_src]
            pts = src_v[hinge_src]
            cxz = pts[:, [0, 2]].mean(axis=0)
            verts.append(np.array([[cxz[0], h, cxz[1]]])); vpart.append(name); vsrc.append(-1)
            c = base
            base += 1
            for j in range(P):
                a, b = ring[j], ring[(j + 1) % P]
                faces.append([c, b, a] if name == "proximal" else [c, a, b])
                regions.append("aero"); surfaces.append("joint_cut"); fparts.append(name); frads.append(h)
    # placeholders where the design holds no surface data (never coloured with results)
    root = spec.root_radius_m if spec.root_radius_m is not None else spec.hub_radius_m
    for name, y0, y1, ysec in (("proximal", root, r_st[0], r_st[0]), ("distal", r_st[-1], spec.tip_radius_m, r_st[-1])):
        if y1 - y0 <= 1e-9:
            continue
        chord, twist = section_at(spec, ysec)
        ra = np.arange(base, base + P); rb = ra + P
        verts += [_ring(prof, chord, twist, y0), _ring(prof, chord, twist, y1)]
        vpart += [name] * 2 * P; vsrc += [-1] * 2 * P
        base += 2 * P
        for j in range(P):
            j2 = (j + 1) % P
            faces += [[ra[j], rb[j], rb[j2]], [ra[j], rb[j2], ra[j2]]]
        for ring, y, flip in ((ra, y0, False), (rb, y1, True)):
            pts = np.vstack(verts)[ring]
            cxz = pts[:, [0, 2]].mean(axis=0)
            verts.append(np.array([[cxz[0], y, cxz[1]]])); vpart.append(name); vsrc.append(-1)
            c = base
            base += 1
            for j in range(P):
                a, b = ring[j], ring[(j + 1) % P]
                faces.append([c, b, a] if flip else [c, a, b])
        nf = 2 * P + 2 * P
        regions += ["undefined"] * nf; surfaces += ["placeholder"] * nf; fparts += [name] * nf
        frads += [0.5 * (y0 + y1)] * nf
    return BladeMesh(spec, joint, np.vstack(verts), np.asarray(faces, dtype=int), np.asarray(regions),
                     np.asarray(surfaces), np.asarray(fparts), np.asarray(frads, dtype=float), np.asarray(vpart),
                     np.asarray(vsrc, dtype=int), rho, rings)