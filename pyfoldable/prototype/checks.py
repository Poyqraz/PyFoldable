"""Assembly checks of the actual solids: full folding travel, joint play, printability and deployed alignment.

Full-travel clearance (column method): both solids are tessellated (0.05 mm chord tolerance) and rasterised on a
0.25 mm plan grid into the proximal's top surface (max z per column, dilated by one cell: conservative) and the
distal's bottom surface (min z per column, in its own deployed frame; for δ < 0 the roles flip). For every fold angle
the distal columns are turned about the pin and the vertical gap distal-bottom − proximal-top is evaluated where
both exist. Because the segments pass above/below each other, this vertical gap is the relevant clearance and its
deficit is directly the extra offset needed. The method is checked against exact OpenCASCADE distances
(``exact_distance``) at the open stop, just off it and at the governing angles.

Designed contacts are reported, not flagged: the lug running faces (gap g) inside the relief radius, the stop seat
at fold 0 (excluded below 2°; the nose moves outboard off the pad on backward rotation), and the washers on their
lug faces. Joint play: radial play (hole clearance) and axial play (lug gap) let the distal rock about an in-plane
axis by φ = min(c_h/t_d + c_h/t_p, g/R_b); the worst-case gap outside the joint is gap − g − φ·s at distance s from
the pin.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

GRID_MM = 0.25
OFF_STOP_DEG = 2.0
NOSE_FREE_DEG = 10.0


def _samples(v, f, h):
    tri = v[f]
    edge = np.linalg.norm(tri[:, [1, 2, 0]] - tri, axis=2).max(axis=1)
    k = np.maximum(1, np.ceil(edge / (0.5 * h)).astype(int))
    out = []
    for n in np.unique(k):
        t = tri[k == n]
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
        keep = (i + j) <= n
        w = np.stack([i[keep], j[keep], n - i[keep] - j[keep]], 1) / n
        out.append(np.einsum("wk,tkd->twd", w, t).reshape(-1, 3))
    return np.vstack(out)


@dataclass
class HeightMap:
    x0: float
    y0: float
    h: float
    top: np.ndarray        # max z per cell (−inf: empty)
    bottom: np.ndarray     # min z per cell (+inf: empty)

    def cells(self, which):
        a = self.top if which == "top" else self.bottom
        iy, ix = np.nonzero(np.isfinite(a))
        return self.x0 + (ix + 0.5) * self.h, self.y0 + (iy + 0.5) * self.h, a[iy, ix]

    def lookup(self, x, y, which):
        a = self.top if which == "top" else self.bottom
        ix = np.floor((x - self.x0) / self.h).astype(int)
        iy = np.floor((y - self.y0) / self.h).astype(int)
        ok = (ix >= 0) & (iy >= 0) & (ix < a.shape[1]) & (iy < a.shape[0])
        out = np.full(len(x), -np.inf if which == "top" else np.inf)
        out[ok] = a[iy[ok], ix[ok]]
        return out


def heightmap(shape, bounds, h=GRID_MM, dilate=False) -> HeightMap:
    from scipy.ndimage import maximum_filter, minimum_filter
    from .cad import tessellate
    v, f = tessellate(shape)
    p = _samples(v, f, h)
    x0, x1, y0, y1 = bounds
    nx, ny = int(math.ceil((x1 - x0) / h)), int(math.ceil((y1 - y0) / h))
    ix = np.floor((p[:, 0] - x0) / h).astype(int)
    iy = np.floor((p[:, 1] - y0) / h).astype(int)
    ok = (ix >= 0) & (iy >= 0) & (ix < nx) & (iy < ny)
    top = np.full((ny, nx), -np.inf)
    bottom = np.full((ny, nx), np.inf)
    np.maximum.at(top, (iy[ok], ix[ok]), p[ok, 2])
    np.minimum.at(bottom, (iy[ok], ix[ok]), p[ok, 2])
    if dilate:
        top = maximum_filter(top, size=3, mode="constant", cval=-np.inf)
        bottom = minimum_filter(bottom, size=3, mode="constant", cval=np.inf)
    return HeightMap(x0, y0, h, top, bottom)


def joint_play(d) -> dict:
    """Worst-case model play, or the play measured on a printed fit pair when the design carries it."""
    c = d.connection
    tp, td = d.lug_thicknesses_mm
    phi_holes = c.hole_clearance_mm / td + c.hole_clearance_mm / tp
    phi_faces = c.lug_gap_mm / c.boss_radius_mm
    model = min(phi_holes, phi_faces)
    measured = None not in (c.play_record_sha256, c.measured_axial_play_mm, c.measured_tilt_deg)
    phi = math.radians(c.measured_tilt_deg) if measured else model
    axial = c.measured_axial_play_mm if measured else c.lug_gap_mm
    return {"radial_play_mm": c.hole_clearance_mm, "axial_play_mm": axial,
            "tilt_rad": phi, "tilt_deg": math.degrees(phi), "model_tilt_rad": model,
            "source": f"ölçüm (kayıt {c.play_record_sha256[:12]})" if measured else "model (en kötü durum)",
            "tilt_limited_by": "ölçüm" if measured else ("delik boşluğu" if phi_holes <= phi_faces else "lug yüz aralığı"),
            "tip_droop_mm": axial + phi * (d.planform.tip_radius_mm - c.hinge_radius_mm)}


def sweep(parts, step_deg=1.0) -> dict:
    """Vertical clearance between the segments over the travel, nominal and with worst-case joint play.
    Sign convention: ``angles_deg`` and ``*_angle_deg`` are signed fold angles (negative: folded back); ``*_travel_deg``,
    ``body_clear_to_deg`` and ``folded_stop_deg`` are travel magnitudes from the open stop."""
    d = parts.design
    c = d.connection
    px, py = parts.pin_axis
    R = d.planform.tip_radius_mm
    L = R - c.hinge_radius_mm + 5.0
    span = max(s[1] for s in d.planform.stations) + 10.0
    bounds = (-span - L, span + L, c.hinge_radius_mm - L - span, R + 5.0)
    prox = heightmap(parts.proximal, bounds, dilate=True)
    dist = heightmap(parts.distal, bounds)
    u, v, zd = dist.cells("bottom")          # δ > 0 (validated): the distal passes above
    s = np.hypot(u - px, v - py)
    x0, x1 = parts.meta["stop_x_mm"]
    nose = (u >= x0 - GRID_MM) & (u <= x1 + GRID_MM) & (v >= py - GRID_MM) & (v <= py + c.nose_depth_mm + GRID_MM)
    # inside the relief ring the joint is rotation-invariant (bosses, reliefs): its radial clearance is a design
    # dimension verified exactly, not by the dilated grid
    outside = s > d.relief_radius_mm + 2 * GRID_MM
    body = outside & ~nose
    play = joint_play(d)
    angles = -np.arange(OFF_STOP_DEG, 180.0 + 1e-9, step_deg)
    gap, gap_play, nose_gap, where = [], [], [], []
    for a in angles:
        t = math.radians(a)
        ct, st = math.cos(t), math.sin(t)
        x = px + (u - px) * ct - (v - py) * st
        y = py + (u - px) * st + (v - py) * ct
        zp = prox.lookup(x, y, "top")
        g = zd - zp
        fin = np.isfinite(g)
        sel = fin & body
        ns = fin & nose & outside
        nose_gap.append(float(g[ns].min()) if (ns.any() and -a >= NOSE_FREE_DEG) else np.inf)
        if not sel.any():
            gap.append(np.inf); gap_play.append(np.inf); where.append(None)
            continue
        k = np.flatnonzero(sel)[np.argmin(g[sel])]
        gap.append(float(g[k]))
        gp = g[sel] - play["axial_play_mm"] - play["tilt_rad"] * s[sel]
        gap_play.append(float(gp.min()))
        where.append((float(x[k]), float(y[k]), float(s[k])))
    gap, gap_play, nose_gap = np.array(gap), np.array(gap_play), np.array(nose_gap)
    need = c.body_clearance_mm
    required = -c.stowed_angle_deg
    hit = np.flatnonzero(nose_gap < 0.0)
    folded_stop = float(-angles[hit[0]]) if len(hit) else None      # the nose meets the proximal: folded stop
    in_req = -angles <= required + 1e-9
    bad = np.flatnonzero((gap < need) & in_req)
    body_clear_to = max(0.0, float(-angles[bad[0]] - step_deg)) if len(bad) else required
    clear_travel = min(body_clear_to, folded_stop - step_deg if folded_stop is not None else required)
    gr, gpr = np.where(in_req, gap, np.inf), np.where(in_req, gap_play, np.inf)
    i_min, i_min_p = int(np.argmin(gr)), int(np.argmin(gpr))
    stop_ok = folded_stop is None or folded_stop >= required
    return {
        "angles_deg": angles.tolist(), "gap_mm": gap.tolist(), "gap_play_mm": gap_play.tolist(),
        "nose_gap_mm": nose_gap.tolist(), "where": where,
        "min_gap_mm": float(gr[i_min]), "min_gap_angle_deg": float(angles[i_min]),
        "min_gap_play_mm": float(gpr[i_min_p]), "min_gap_play_angle_deg": float(angles[i_min_p]),
        "required_travel_deg": required, "body_clear_to_deg": body_clear_to, "folded_stop_deg": folded_stop,
        "clear_travel_deg": clear_travel,
        "full_travel_clear": bool(len(bad) == 0 and stop_ok),
        "body_clear": bool(len(bad) == 0),
        "full_travel_clear_with_play": bool(gpr.min() >= 0.0 and stop_ok),
        "required_offset_mm": c.axial_offset_mm + max(0.0, need - gr[i_min]),
        # both criteria: nominal gap ≥ body clearance and worst-case gap with play ≥ 0 (the pass rule above)
        "required_offset_with_play_mm": max(c.axial_offset_mm + max(0.0, need - gr[i_min]),
                                            c.axial_offset_mm + max(0.0, -gpr[i_min_p])),
        "joint_running_gap_mm": c.lug_gap_mm, "play": play, "body_clearance_mm": need,
        "method": f"sütun yöntemi {GRID_MM} mm ızgara, {step_deg}° adım; tesselasyon 0,05 mm",
    }


def exact_distance(parts, fold_deg, with_hardware=False):
    """Exact minimum distance [mm] between the proximal (and the pin set) and the distal posed at the fold angle."""
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    dist = parts.distal_at(fold_deg)
    out = {"proximal": BRepExtrema_DistShapeShape(parts.proximal.wrapped, dist.wrapped).Value()}
    if with_hardware:
        for k, hw in parts.hardware.items():
            out[k] = BRepExtrema_DistShapeShape(hw.wrapped, dist.wrapped).Value()
            out[k + "_proximal"] = BRepExtrema_DistShapeShape(hw.wrapped, parts.proximal.wrapped).Value()
    return out


def bed_fit(shape, bed):
    """Smallest footprint over plan rotations; fits if some rotation lies inside the bed (x, y) and z ≤ bed z."""
    from .cad import tessellate
    v, _ = tessellate(shape, 0.2)
    zspan = float(v[:, 2].max() - v[:, 2].min())
    best = None
    for a in np.radians(np.arange(0.0, 90.0, 2.5)):
        x = v[:, 0] * math.cos(a) - v[:, 1] * math.sin(a)
        y = v[:, 0] * math.sin(a) + v[:, 1] * math.cos(a)
        w, h = float(np.ptp(x)), float(np.ptp(y))
        ok = (w <= bed[0] and h <= bed[1]) or (h <= bed[0] and w <= bed[1])
        if best is None or (ok and not best[2]) or (ok == best[2] and w * h < best[0] * best[1]):
            best = (w, h, ok, math.degrees(a))
    return {"footprint_mm": (round(best[0], 1), round(best[1], 1)), "height_mm": round(zspan, 1),
            "fits": bool(best[2] and zspan <= bed[2]), "rotation_deg": best[3]}


def lug_engagement(d) -> dict:
    """Fraction of each blade's section height over the boss disk that its lug band covers (a lug that only grazes
    its blade is a thin, eccentric neck). The reference is the blade part that can exist beside the pin: the relief
    removes the proximal above its lug band and the distal below its lug band."""
    (p0, p1), (q0, q1) = d.lug_bands_mm
    out = {}
    for name, (z0, z1) in (("proksimal", (p0, p1)), ("distal", (q0, q1))):
        b0, b1 = d.body_band_at_pin_mm("proximal" if name == "proksimal" else "distal")
        b0, b1 = (b0, min(b1, p1)) if name == "proksimal" else (max(b0, q0), b1)
        out[name] = max(0.0, min(z1, b1) - max(z0, b0)) / (b1 - b0) if b1 > b0 else 0.0
    return out


def printability(d, printable: dict) -> list[dict]:
    from .cad import printable_profile
    c, pm = d.connection, d.print_model
    wall = c.boss_radius_mm - d.hole_diameter_mm / 2.0
    tip_chord = d.planform.stations[-1][1]
    te = (lambda p: (p[0, 1] - p[-1, 1]) * tip_chord)(printable_profile(d, tip_chord))
    rows = [
        {"check": "Delik çevresi et kalınlığı", "value": f"{wall:.2f} mm", "ok": wall >= 2 * pm.wall_mm,
         "note": f"≥ 2 çevre duvarı ({2 * pm.wall_mm:.1f} mm)"},
        {"check": "Lug kalınlığı (katman)", "value": f"{min(d.lug_thicknesses_mm) / pm.layer_mm:.0f}",
         "ok": min(d.lug_thicknesses_mm) >= 10 * pm.layer_mm, "note": "≥ 10 katman"},
        *({"check": f"Lug–kanat bağlantısı ({name})", "value": f"{frac:.0%} kesit kalınlığı",
           "ok": frac >= 0.6, "note": "lug bandı, pim çevresinde kendi kanat kesitinin ≥ %60'ını kavramalı"}
          for name, frac in lug_engagement(d).items()),
        {"check": "Firar kenarı kalınlığı (uç)", "value": f"{te:.2f} mm", "ok": te >= pm.min_te_thickness_mm - 1e-6,
         "note": f"≥ {pm.min_te_thickness_mm} mm (kesit {d.section_identity})"},
        {"check": "Lug aralığı (katman)", "value": f"{c.lug_gap_mm / pm.layer_mm:.1f}", "ok": c.lug_gap_mm >= pm.layer_mm,
         "note": "ayrı parçalar; aralık montajda donanımla kurulur"},
        {"check": "Burulmuş yüzeyler", "value": f"azami {max(s[2] for s in d.planform.stations):.0f}°", "ok": True,
         "note": "rotor düzlemi tablada: alt yüzey destek ister (destek arayüzü alt yüzeyde)"},
    ]
    for name, shape in printable.items():
        fit = bed_fit(shape, pm.bed_mm)
        rows.append({"check": f"Tabla sığması: {name}", "value": f"{fit['footprint_mm'][0]}×{fit['footprint_mm'][1]}×{fit['height_mm']} mm",
                     "ok": fit["fits"], "note": f"tabla {pm.bed_mm[0]:.0f}×{pm.bed_mm[1]:.0f}×{pm.bed_mm[2]:.0f}, döndürme {fit['rotation_deg']:.1f}°"})
    return rows


def alignment(d, parts) -> dict:
    """Deployed geometry at the joint: step, gaps and local protrusions of the connection."""
    from .cad import section_points
    c, hw = d.connection, d.hardware
    (p0, p1), (q0, q1) = d.lug_bands_mm

    def surfaces(radius, z_off):
        p = section_points(d, radius, z_off)
        n = len(p) // 2
        up, lo = p[:n + 1], p[n:]
        zu = np.interp(c.pin_x_mm, *up[np.argsort(up[:, 0])][:, [0, 2]].T)
        zl = np.interp(c.pin_x_mm, *lo[np.argsort(lo[:, 0])][:, [0, 2]].T)
        return zu, zl
    pu, pl = surfaces(c.hinge_radius_mm, 0.0)
    du, dl = surfaces(c.hinge_radius_mm + c.face_gap_mm, c.axial_offset_mm)
    head_low = p0 - hw.washer_thickness_mm - hw.head_height_mm
    clip_high = q1 + hw.washer_thickness_mm + hw.clip_thickness_mm + hw.pin_end_mm
    return {
        "step_mm": c.axial_offset_mm,
        "face_gap_mm": c.face_gap_mm,
        "nose_ahead_of_le_mm": c.nose_extension_mm,
        "proximal_boss_below_surface_mm": max(0.0, pl - p0),
        "distal_boss_above_surface_mm": max(0.0, q1 - du),
        "head_below_proximal_surface_mm": max(0.0, pl - head_low),
        "clip_above_distal_surface_mm": max(0.0, clip_high - du),
        "lug_midplane_offset_mm": d.lug_midplane_offset_mm,
        "stack_thickness_mm": d.stack_thickness_mm,
        "proximal_surfaces_at_pin_mm": (float(pl), float(pu)),
        "distal_surfaces_at_pin_mm": (float(dl), float(du)),
        "relief_radius_mm": d.relief_radius_mm,
        "hardware_inside_relief": max(hw.washer_od_mm, hw.clip_od_mm, hw.head_diameter_mm) / 2 < d.relief_radius_mm,
    }
