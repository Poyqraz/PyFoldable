"""Fold contacts of the lofted blade surfaces (synchronous fold of all blades, rigid parts, no solver).

For each pair of parts the fold angle is scanned from open (0) toward the declared lower limit; the first
angle at which surface points of one part lie inside the other part's solid is refined by bisection and
reported with the contact points. Solids are exact for the loft: a point is inside a part when its
spanwise position is in the part's range and its section coordinates (inverse twist, chord scaling) lie
inside the catalog profile. Parts: proximal and distal of every blade (split at the hinge radius, or with
the circular joint relief of ``blade_surface``), the placeholders where no surface data exist (contacts
with them are only *possible*), and the hub as an infinite cylinder of the declared hub radius (only the
radius is defined; contacts with it are *possible*, since its axial extent is unknown). The step is
chosen so that the distal tip moves at most half the thinnest section thickness per step; detection tests
surface sample points against exact solids, so thin-edge crossings smaller than the sampling can still be
missed — display screening, not GEOM-03/04 qualification evidence. The shown pose is clamped to the last
clear angle of the first certain contact (no interlocked defined surfaces are drawn).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from pyfoldable.visualization import blade_surface as bs


@dataclass
class Contact:
    a: str
    b: str
    status: str                          # contact | clear | in_contact_open | possible_undefined_geometry |
    #                                      possible_hub_radius_only
    first_contact_deg: float | None = None
    last_clear_deg: float | None = None  # bisection bracket: clear at this angle, contact at first_contact_deg
    point_a: tuple | None = None         # world point on/inside part a at the first contact [m]
    point_b: tuple | None = None         # nearest surface point of part b [m]
    note: str = ""


@dataclass
class ContactReport:
    joint: str
    fold_min_deg: float
    step_deg: float
    tolerance_deg: float
    contacts: list = field(default_factory=list)
    interference_free_deg: float = 0.0   # last clear angle before the first certain contact

    def pair(self, a: str, b: str) -> Contact:
        return next(c for c in self.contacts if c.a == a and c.b == b)

    def clamp(self, fold_deg: float) -> float:
        """Shown pose: never beyond the first certain contact (no interlocked surfaces are drawn)."""
        return max(fold_deg, self.interference_free_deg)


class _Model:
    def __init__(self, spec: bs.BladeSpec, joint: str, n_side: int, dr: float):
        self.spec, self.joint = spec, joint
        self.mesh = bs.loft(spec, n_side=n_side, dr=dr, joint=joint)
        prof = bs.resample_profile(spec.profile, n_side)
        if float(np.linalg.norm(prof[0] - prof[-1])) < 1e-9:
            prof = prof[:-1]
        self.prof = prof
        self.rho = self.mesh.joint_radius_m
        self.r = [s[0] for s in spec.stations]
        self.root = spec.root_radius_m if spec.root_radius_m is not None else spec.hub_radius_m
        self.extent = 1.05 * max(max(abs(p[0] - 0.25), abs(p[1])) for p in prof) * max(s[1] for s in spec.stations)
        cen = self.mesh.face_centroids()
        pts, part = [], []
        for name, region in (("proximal", ("aero",)), ("distal", ("aero", "joint"))):
            fsel = (self.mesh.face_part == name) & np.isin(self.mesh.region, region)
            vsel = np.unique(self.mesh.faces[fsel])
            pts.append(np.vstack([self.mesh.vertices[vsel], cen[fsel]])); part.append(name)
        self.samples = dict(zip(part, pts))
        if joint == "relief":                           # keep each part's samples inside its own exact region
            h = spec.hinge_radius_m
            for name, p in list(self.samples.items()):
                zone = bs.in_joint_zone(p[:, 0], p[:, 1], spec, self.rho)
                keep = ~zone if name == "proximal" else (zone | (p[:, 1] >= h - 1e-12))
                self.samples[name] = p[keep]
        for name, region_part in (("undefined_root", "proximal"), ("undefined_tip", "distal")):
            fsel = (self.mesh.region == "undefined") & (self.mesh.face_part == region_part)
            vsel = np.unique(self.mesh.faces[fsel])
            self.samples[name] = np.vstack([self.mesh.vertices[vsel], cen[fsel]]) if len(vsel) else np.zeros((0, 3))

    @staticmethod
    def moving(part):
        return part in ("distal", "undefined_tip")

    def _section_inside(self, p, ysec=None):
        y = p[:, 1] if ysec is None else np.full(len(p), ysec)
        chord = np.interp(y, self.r, [s[1] for s in self.spec.stations])
        tw = np.interp(y, self.r, [s[2] for s in self.spec.stations])
        c, s = np.cos(tw), np.sin(tw)
        X, Z = p[:, 0] * c - p[:, 2] * s, p[:, 0] * s + p[:, 2] * c
        xc, zc = X / chord + 0.25, Z / chord
        poly = self.prof
        inside = np.zeros(len(p), dtype=bool)
        x0, z0 = poly[:, 0], poly[:, 1]
        x1, z1 = np.roll(x0, -1), np.roll(z0, -1)
        for k in range(len(poly)):                      # ray casting in +x/c (closed by the TE segment)
            cond = (z0[k] > zc) != (z1[k] > zc)
            xint = x0[k] + (zc - z0[k]) * (x1[k] - x0[k]) / np.where(z1[k] == z0[k], 1e-300, z1[k] - z0[k])
            inside ^= cond & (xc < xint)
        return inside

    def inside(self, part, p):
        """p in the part's unfolded frame (blade body frame)."""
        h, r0, r1 = self.spec.hinge_radius_m, self.r[0], self.r[-1]
        out = np.zeros(len(p), dtype=bool)
        near = (np.abs(p[:, 0]) <= self.extent) & (np.abs(p[:, 2]) <= self.extent)
        if part == "undefined_root":
            cand = near & (p[:, 1] >= self.root) & (p[:, 1] <= r0)
            ysec = r0
        elif part == "undefined_tip":
            cand = near & (p[:, 1] >= r1) & (p[:, 1] <= self.spec.tip_radius_m)
            ysec = r1
        else:
            joint = bs.in_joint_zone(p[:, 0], p[:, 1], self.spec, self.rho) if self.joint == "relief" else np.zeros(len(p), bool)
            eps = 1e-9                                  # the shared hinge plane belongs to neither part's interior
            if part == "proximal":
                cand = near & (p[:, 1] >= r0) & (p[:, 1] < h - eps) & ~joint
            else:
                cand = near & (((p[:, 1] > h + eps) & (p[:, 1] <= r1)) | (joint & (p[:, 1] >= r0)))
            ysec = None
        if cand.any():
            out[cand] = self._section_inside(p[cand], ysec)
        return out

    def to_world(self, part, p, blade, fold):
        az = 2.0 * math.pi * blade / self.spec.blade_count
        return bs.pose_points(p, np.full(len(p), self.moving(part)), self.spec.hinge_radius_m, fold, az)

    def to_body(self, part, w, blade, fold):
        az = 2.0 * math.pi * blade / self.spec.blade_count
        ca, sa = math.cos(-az), math.sin(-az)
        p = np.array(w, dtype=float, copy=True)
        p[:, 0], p[:, 1] = w[:, 0] * ca - w[:, 1] * sa, w[:, 0] * sa + w[:, 1] * ca
        if self.moving(part):
            p = bs.pose_points(p, np.ones(len(p), bool), self.spec.hinge_radius_m, -fold)
        return p

    def hits(self, a, b, fold):
        """Points of part a (blade 0) inside part b, and points of b inside a, in world coordinates."""
        name_a, blade_a = a
        wa = self.to_world(name_a, self.samples[name_a], blade_a, fold)
        if b[0] == "hub":
            return wa[np.hypot(wa[:, 0], wa[:, 1]) < self.spec.hub_radius_m], None
        name_b, blade_b = b
        ina = wa[self.inside(name_b, self.to_body(name_b, wa, blade_b, fold))]
        wb = self.to_world(name_b, self.samples[name_b], blade_b, fold)
        inb = wb[self.inside(name_a, self.to_body(name_a, wb, blade_a, fold))]
        return ina, inb


def _label(part, blade):
    return "hub" if part == "hub" else f"{part}_{blade + 1}"


def _pairs(model):
    out = []
    for c in range(1, model.spec.blade_count):          # static parts of different blades: open-position overlap only
        for a in ("proximal", "undefined_root"):
            for b in ("proximal", "undefined_root"):
                if len(model.samples[a]) and len(model.samples[b]):
                    out.append(((a, 0), (b, c)))
    for mover in ("distal", "undefined_tip"):
        if not len(model.samples[mover]):
            continue
        targets = [("proximal", 0), ("undefined_root", 0), ("hub", None)]
        for c in range(1, model.spec.blade_count):
            targets += [("proximal", c), ("distal", c), ("undefined_root", c), ("undefined_tip", c)]
        for t in targets:
            if t[0] != "hub" and not len(model.samples[t[0]]):
                continue
            out.append(((mover, 0), t))
    return out


def fold_contacts(spec: bs.BladeSpec, *, joint: str = "relief", fold_min_deg: float = -180.0, step_deg: float = 2.0,
                  tolerance_deg: float = 0.05, n_side: int = 40, dr: float = 0.003) -> ContactReport:
    if not -180.0 <= fold_min_deg < 0.0:
        raise ValueError("fold_min_deg must be in [-180, 0)")
    model = _Model(spec, joint, n_side, dr)
    prof = model.prof
    lo_side = prof[int(np.argmin(prof[:, 0])):]
    up_side = prof[:int(np.argmin(prof[:, 0])) + 1][::-1]
    t_ratio = max(float(np.interp(x, *up_side.T) - np.interp(x, *lo_side.T)) for x in np.linspace(0.05, 0.6, 23))
    t_min = t_ratio * min(s[1] for s in spec.stations)
    reach = max(spec.tip_radius_m - spec.hinge_radius_m, 1e-6)
    step_deg = min(step_deg, math.degrees(0.5 * t_min / reach))
    rep = ContactReport(joint, fold_min_deg, step_deg, tolerance_deg)
    grid = list(np.arange(0.0, fold_min_deg - 1e-9, -step_deg)) + [fold_min_deg]
    certain = []
    for a, b in _pairs(model):
        undefined = "undefined" in a[0] or "undefined" in b[0]
        hub = b[0] == "hub"
        label_a, label_b = _label(*a), _label(b[0], b[1] if b[1] is not None else 0)
        ia, ib = model.hits(a, b, 0.0)
        static = not (model.moving(a[0]) or (b[0] != "hub" and model.moving(b[0])))
        if len(ia) or (ib is not None and len(ib)):        # already overlapping when open
            pa = (ia if len(ia) else ib).mean(axis=0)
            status = ("possible_undefined_geometry" if undefined else "possible_hub_radius_only" if hub
                      else "in_contact_open")
            rep.contacts.append(Contact(label_a, label_b, status, 0.0, None, tuple(map(float, pa)), None,
                                        "surfaces overlap in the open position"))
            if status == "in_contact_open":
                certain.append(0.0)
            continue
        if static:                                       # unaffected by the fold
            rep.contacts.append(Contact(label_a, label_b, "clear", note="static parts; no overlap when open"))
            continue
        prev, found = 0.0, None
        for deg in grid[1:]:
            ia, ib = model.hits(a, b, math.radians(deg))
            if len(ia) or (ib is not None and len(ib)):
                found = (prev, deg)
                break
            prev = deg
        if found is None:
            rep.contacts.append(Contact(label_a, label_b, "clear",
                                        note=f"no contact down to {fold_min_deg:.1f} deg (step {step_deg} deg)"))
            continue
        lo, hi = found                                  # lo clear, hi contact
        while lo - hi > tolerance_deg:
            mid = 0.5 * (lo + hi)
            ia, ib = model.hits(a, b, math.radians(mid))
            if len(ia) or (ib is not None and len(ib)):
                hi = mid
            else:
                lo = mid
        ia, ib = model.hits(a, b, math.radians(hi))
        pa = ia.mean(axis=0) if len(ia) else ib.mean(axis=0)
        if b[0] == "hub":
            pb = pa * (spec.hub_radius_m / max(math.hypot(pa[0], pa[1]), 1e-12))
            pb[2] = pa[2]
        else:
            wb = model.to_world(b[0], model.samples[b[0]], b[1], math.radians(hi))
            pb = wb[np.argmin(np.linalg.norm(wb - pa, axis=1))]
        status = ("possible_undefined_geometry" if undefined else "possible_hub_radius_only" if hub else "contact")
        note = ("involves a region without surface data (placeholder)" if undefined else
                "hub is defined by its radius only (infinite cylinder; axial extent unknown)" if hub else "")
        rep.contacts.append(Contact(label_a, label_b, status, hi, lo, tuple(map(float, pa)), tuple(map(float, pb)), note))
        if status == "contact":
            certain.append(lo)
    rep.interference_free_deg = max(certain) if certain else fold_min_deg
    return rep


def penetrating_points(spec: bs.BladeSpec, *, joint: str = "relief", fold_deg: float, n_side: int = 40,
                       dr: float = 0.003) -> np.ndarray:
    """All points of certain (surface-defined) pairs that penetrate another part at this fold [m]."""
    model = _Model(spec, joint, n_side, dr)
    found = []
    for a, b in _pairs(model):
        if "undefined" in a[0] or "undefined" in b[0] or b[0] == "hub":
            continue
        ia, ib = model.hits(a, b, math.radians(fold_deg))
        found += [ia] + ([ib] if ib is not None else [])
    return np.vstack(found) if found else np.zeros((0, 3))
