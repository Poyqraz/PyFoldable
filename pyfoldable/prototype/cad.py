"""B-rep solids of the prototype (build123d / OpenCASCADE; millimetres; frame and planes in ``design``).

Construction, one design:

- aerodynamic bodies: the catalog profile resampled (cosine spacing), the trailing edge thickened to the printable
  minimum (``PrintModel.min_te_thickness_mm``; a new section identity), placed on the quarter-chord line with the
  linear chord/twist of the stations and lofted. Proximal: hub → joint plane y = r_j at z 0. Distal: r_j + face gap
  → tip, translated by δ along z. Outside the analysis span (hub → first station, last station → tip) the section is
  the nearest station's (the root chord tapers to 55 % at the hub): placeholders, not analysed geometry.
- lugs: one boss per segment, a disk of radius R_b about the pin, in that segment's lug band (``lug_bands_mm``),
  with 0.4 mm edge rounds on the free circular edges; fused to its body.
- swept reliefs: the proximal is cleared above its lug band and the distal below its lug band inside the relief
  radius R_b + c_r about the pin, so either boss turns over the other through the whole travel; spot faces clear
  the washers/head/clip.
- open stop: the distal nose (ahead of the pin, outside the relief radius, joint plane y ≥ r_j) reaches down to the
  proximal lug band and seats flat on the proximal pad (y ≤ r_j). Contact normal is spanwise, so the seat is a flat
  face pair; under forward rotation the nose moves inboard onto the pad.
- hole Ø(pin + clearance) through both bosses with 0.4 mm entry chamfers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .design import PrototypeDesign

EDGE_ROUND_MM = 0.4
HOLE_CHAMFER_MM = 0.4
SPOT_CLEAR_MM = 0.3


def _b3d():
    try:
        import build123d as b3d
    except ImportError as exc:                              # pragma: no cover - exercised without the extra
        raise RuntimeError("CAD needs the optional extra: pip install -e '.[cad]'") from exc
    return b3d


def printable_profile(d: PrototypeDesign, chord_mm: float, n_side: int = 48) -> np.ndarray:
    """Normalised (x/c, z/c) Selig-order section with the trailing edge thickened to the printable minimum by a
    smooth ramp from ``te_blend_start`` (symmetric about the camber line)."""
    from pyfoldable.core.profile_catalog import load_project_airfoil
    from pyfoldable.visualization.blade_surface import resample_profile
    prof = resample_profile(load_project_airfoil(d.planform.profile_id).coordinates, n_side).copy()
    up, lo = slice(0, n_side), slice(n_side - 1, 2 * n_side - 1)
    te_now = prof[0, 1] - prof[-1, 1]
    add = max(0.0, d.print_model.min_te_thickness_mm / chord_mm - te_now) / 2.0
    x0 = d.print_model.te_blend_start
    ramp = np.clip((prof[:, 0] - x0) / (1.0 - x0), 0.0, 1.0) ** 2
    prof[up, 1] += add * ramp[up]
    prof[lo, 1] -= add * ramp[lo]
    prof[n_side - 1, 1] = prof[n_side - 1, 1]               # leading edge untouched (ramp 0 there)
    return prof


def section_points(d: PrototypeDesign, radius_mm: float, z_offset_mm: float = 0.0, chord_mm=None,
                   n_side: int = 48) -> np.ndarray:
    chord, twist = d.section(radius_mm)
    chord = chord if chord_mm is None else chord_mm
    prof = printable_profile(d, chord, n_side)
    X, Z = (prof[:, 0] - 0.25) * chord, prof[:, 1] * chord
    b = math.radians(twist)
    c, s = math.cos(b), math.sin(b)
    return np.column_stack([X * c + Z * s, np.full(len(prof), radius_mm), -X * s + Z * c + z_offset_mm])


def _wire(pts):
    b3d = _b3d()
    v = [b3d.Vector(*map(float, p)) for p in pts]
    return b3d.Wire([b3d.Edge.make_spline(v), b3d.Edge.make_line(v[-1], v[0])])


def _loft(d: PrototypeDesign, radii, z_offset, chord_of=None):
    b3d = _b3d()
    wires = [_wire(section_points(d, r, z_offset, None if chord_of is None else chord_of(r))) for r in radii]
    return b3d.Solid.make_loft(wires, ruled=False)


def _radii(d: PrototypeDesign, r0, r1, step=4.0):
    """Evenly spaced loft sections (about ``step`` apart, at least four per hinge-zone half-width). The planform is
    linear between stations, so dense even sampling represents it (a station kink is rounded over one spacing);
    irregular station + grid spacing with steep twist gradients made OCC booleans of the spline loft with the bosses
    fail silently (empty intersection)."""
    p = d.planform
    if p.hinge_zone_mm > 0:
        step = min(step, p.hinge_zone_mm / 4.0, (p.hinge_zone_outboard_mm or p.hinge_zone_mm) / 4.0)
    return [float(r) for r in np.linspace(r0, r1, max(2, int(math.ceil((r1 - r0) / step)) + 1))]


def _single(shape, what):
    solids = shape.solids()
    if len(solids) != 1:
        raise RuntimeError(f"{what}: expected one solid, got {len(solids)}")
    s = solids[0]
    if not s.is_valid():
        raise RuntimeError(f"{what}: invalid solid")
    return s


@dataclass
class Parts:
    design: PrototypeDesign
    proximal: object                 # one proximal segment with hub sector (blade 1)
    distal: object                   # distal segment, deployed (fold 0)
    hardware: dict                   # name -> solid (pin, head included in pin; washers; clip), fixed on the axis
    pin_axis: tuple                  # (x, y) of the pin axis in mm
    meta: dict = field(default_factory=dict)

    def distal_at(self, fold_deg: float):
        b3d = _b3d()
        x, y = self.pin_axis
        return self.distal.rotate(b3d.Axis((x, y, 0.0), (0.0, 0.0, 1.0)), fold_deg)


def _boss(b3d, x, y, z0, z1, r):
    cyl = b3d.Pos(x, y, z0) * b3d.Cylinder(r, z1 - z0, align=(b3d.Align.CENTER, b3d.Align.CENTER, b3d.Align.MIN))
    return b3d.fillet(cyl.edges().filter_by(b3d.GeomType.CIRCLE), EDGE_ROUND_MM)


def _zcyl(b3d, x, y, z0, z1, r):
    return b3d.Pos(x, y, z0) * b3d.Cylinder(r, z1 - z0, align=(b3d.Align.CENTER, b3d.Align.CENTER, b3d.Align.MIN))


def _hole(b3d, x, y, z0, z1, r):
    h = _zcyl(b3d, x, y, z0 - 1.0, z1 + 1.0, r)
    for z, up in ((z0, True), (z1, False)):                 # 45° entry chamfers at both lug faces
        cone = b3d.Solid.make_cone(r + HOLE_CHAMFER_MM, r, HOLE_CHAMFER_MM,
                                   b3d.Plane((x, y, z), z_dir=(0, 0, 1) if up else (0, 0, -1)))
        h = h + cone
    return h


def _box(b3d, x0, x1, y0, y1, z0, z1):
    return b3d.Pos(x0, y0, z0) * b3d.Box(x1 - x0, y1 - y0, z1 - z0, align=(b3d.Align.MIN,) * 3)


def build(d: PrototypeDesign) -> Parts:
    b3d = _b3d()
    c, h = d.connection, d.hardware
    rj, delta = c.hinge_radius_mm, c.axial_offset_mm
    (p0, p1), (q0, q1) = d.lug_bands_mm
    px, py = c.pin_x_mm, rj
    R_rel = d.relief_radius_mm
    r_first = d.planform.stations[0][0]
    c_first = d.planform.stations[0][1]
    hub_r = d.hub_radius_mm

    def root_chord(r):                                       # placeholder root taper (outside the analysis span)
        if r >= r_first:
            return None
        return c_first * (0.55 + 0.45 * (r - (hub_r - 1.5)) / (r_first - (hub_r - 1.5)))

    prox = _loft(d, _radii(d, hub_r - 1.5, rj), 0.0, chord_of=root_chord)
    dist = _loft(d, _radii(d, rj + c.face_gap_mm, d.planform.tip_radius_mm), delta)
    big = 4.0 * max(s[1] for s in d.planform.stations) + 50.0

    # lugs (bosses) fused to their bodies
    prox = prox + _boss(b3d, px, py, p0, p1, c.boss_radius_mm)
    dist = dist + _boss(b3d, px, py, q0, q1, c.boss_radius_mm)
    # swept reliefs: nothing of the proximal above its band, nothing of the distal below its band, near the pin
    prox = prox - _zcyl(b3d, px, py, p1, p1 + big, R_rel)
    dist = dist - _zcyl(b3d, px, py, q0 - big, q0, R_rel)
    # spot faces for washer + head (below the proximal lug) and washer + clip (above the distal lug)
    spot = max(h.washer_od_mm, h.clip_od_mm, h.head_diameter_mm) / 2.0 + SPOT_CLEAR_MM
    prox = prox - _zcyl(b3d, px, py, p0 - big, p0, spot)
    dist = dist - _zcyl(b3d, px, py, q1, q1 + big, spot)
    # open stop: proximal pad and distal nose ahead of the pin (outside the relief radius)
    x_le = section_points(d, rj)[:, 0].min()
    x_front, x_back = x_le - c.nose_extension_mm, px - R_rel
    if not x_back - x_front > 1.0:
        raise RuntimeError("No room for the stop ahead of the pin (move the pin aft or extend the nose).")
    prox = _single(prox + _box(b3d, x_front, x_back, rj - c.pad_depth_mm, rj, p0, p1), "proximal with stop pad")
    # the nose rises into the distal root section (its mid-thickness over the nose width) so it fuses with it
    sec = section_points(d, rj + c.face_gap_mm + c.nose_depth_mm / 2.0, delta)
    inside = sec[(sec[:, 0] >= x_front) & (sec[:, 0] <= x_back)]
    if len(inside) < 2:
        raise RuntimeError("The stop nose lies ahead of the distal section (reduce the nose extension).")
    nose_top = max(q0 + 1.0, float(inside[:, 2].mean()))
    dist = _single(dist + _box(b3d, x_front, x_back, rj, rj + c.nose_depth_mm, p0, nose_top), "distal with stop nose")
    # pin hole through both lugs
    r_hole = d.hole_diameter_mm / 2.0
    prox = prox - _hole(b3d, px, py, p0, p1, r_hole)
    dist = dist - _hole(b3d, px, py, q0, q1, r_hole)
    # hub sector (placeholder interface): cylinder with bore, fused to the proximal root
    hub = _zcyl(b3d, 0.0, 0.0, -d.hub_height_mm / 2.0, d.hub_height_mm / 2.0, hub_r)
    hub = hub - _zcyl(b3d, 0.0, 0.0, -d.hub_height_mm, d.hub_height_mm, d.hub_bore_mm / 2.0)
    prox_blade = _single(prox, "proximal")
    prox = _single(prox + hub, "proximal+hub")
    dist = _single(dist, "distal")

    # hardware on the pin axis: head + shank with groove, washers, clip (E-clip modelled as a full ring)
    zw0 = p0 - h.washer_thickness_mm
    zh0 = zw0 - h.head_height_mm
    zt = q1 + h.washer_thickness_mm
    z_end = zt + h.groove_width_mm + h.pin_end_mm
    pin = _zcyl(b3d, px, py, zh0, zw0, h.head_diameter_mm / 2.0) + _zcyl(b3d, px, py, zw0, z_end, c.pin_diameter_mm / 2.0)
    groove = (_zcyl(b3d, px, py, zt, zt + h.groove_width_mm, c.pin_diameter_mm / 2.0 + 0.1)
              - _zcyl(b3d, px, py, zt - 0.1, zt + h.groove_width_mm + 0.1, h.groove_diameter_mm / 2.0))
    pin = _single(pin - groove, "pin")
    ring = lambda z0, z1, ro, ri: _single(_zcyl(b3d, px, py, z0, z1, ro) - _zcyl(b3d, px, py, z0 - 1, z1 + 1, ri), "ring")  # noqa: E731
    hardware = {
        "pin": pin,
        "washer_head": ring(zw0, p0, h.washer_od_mm / 2, h.washer_id_mm / 2),
        "washer_clip": ring(q1, zt, h.washer_od_mm / 2, h.washer_id_mm / 2),
        "clip": ring(zt, zt + h.clip_thickness_mm, h.clip_od_mm / 2, h.groove_diameter_mm / 2),
    }
    meta = dict(x_le_hinge_mm=float(x_le), stop_x_mm=(float(x_front), float(x_back)),
                stop_z_mm=(float(p0), float(p1)), nose_z_mm=(float(p0), float(nose_top)),
                pin_z_mm=(float(zh0), float(z_end)), pin_length_mm=float(z_end - zw0),
                spot_radius_mm=float(spot), proximal_blade=prox_blade)
    return Parts(d, prox, dist, hardware, (px, py), meta)


def rotor(parts: Parts):
    """Hub with all proximal segments (one print) for the complete-rotor candidate."""
    b3d = _b3d()
    n = parts.design.planform.blade_count
    out = parts.proximal
    for k in range(1, n):
        out = out + parts.proximal.rotate(b3d.Axis.Z, 360.0 * k / n)
    return _single(out, "rotor")


def fit_test(parts: Parts):
    """Short proximal/distal sections around the joint for fit and motion tests (same joint, flat cut ends)."""
    b3d = _b3d()
    d = parts.design
    rj, L = d.connection.hinge_radius_mm, d.fit_section_mm
    big = 400.0
    keep_p = _box(b3d, -big, big, rj - L, rj + 30.0, -big, big)
    keep_d = _box(b3d, -big, big, rj - 30.0, rj + L, -big, big)
    return (_single(parts.meta["proximal_blade"] & keep_p, "fit proximal"),
            _single(parts.distal & keep_d, "fit distal"))


def fit_fixture(parts: Parts, clamp_mm=(20.0, 8.0), tab_mm=(12.0, 14.0, 3.0), lever_mm=30.0):
    """The fit pair as a measurement fixture: the proximal stub gets a flat clamp block on its inboard cut end (vise
    jaws on its z faces keep the rotor plane level) and the distal stub a flat load tab on its outboard cut end with
    a Ø3.2 hole on the span line through the pin at ``lever_mm`` from the pin (force or weight → torque about the pin;
    up/down load → tilt). Returns (proximal, distal, lever_mm)."""
    b3d = _b3d()
    d = parts.design
    c = d.connection
    rj, L, px = c.hinge_radius_mm, d.fit_section_mm, c.pin_x_mm
    fp, fd = fit_test(parts)
    y_in = rj - L
    sec = section_points(d, y_in)
    zc = 0.5 * (sec[:, 2].min() + sec[:, 2].max())
    block = _box(b3d, sec[:, 0].min(), sec[:, 0].max(), y_in - clamp_mm[0], y_in + 1.0,
                 zc - clamp_mm[1] / 2.0, zc + clamp_mm[1] / 2.0)
    prox = _single(fp + block, "fit proximal with clamp block")
    y_out = rj + L
    w, length, t = tab_mm
    if not (lever_mm - L >= 3.0 and L + length - lever_mm >= 3.0):           # hole on the tab, ≥ 3 mm from its ends
        raise RuntimeError("Load-tab hole does not fit on the tab (adjust the lever or the tab length).")
    out = section_points(d, y_out, c.axial_offset_mm)
    zt = float(out[np.abs(out[:, 0] - px) <= 2.0, 2].max())                      # upper surface near the pin x
    tab = _box(b3d, px - w / 2.0, px + w / 2.0, y_out - 1.0, y_out + length, zt - t, zt)
    tab = tab - _zcyl(b3d, px, rj + lever_mm, zt - t - 1.0, zt + 1.0, 1.6)
    dist = _single(fd + tab, "fit distal with load tab")
    return prox, dist, float(lever_mm)


def hole_coupon(d: PrototypeDesign, steps=(0.0, 0.1, 0.2, 0.3, 0.4)):
    """Plate of the proximal lug thickness, printed in the same orientation, with holes Ø(pin + step) and k notches
    beside hole k (k = 1..n) to identify it: pick the step that gives the intended running fit with the real pin."""
    b3d = _b3d()
    t, pitch = d.lug_thicknesses_mm[0], 10.0
    w = pitch * len(steps) + 4.0
    plate = _box(b3d, 0.0, w, 0.0, 16.0, 0.0, t)
    for k, s in enumerate(steps):
        x = 7.0 + pitch * k
        plate = plate - _zcyl(b3d, x, 9.0, -1.0, t + 1.0, (d.connection.pin_diameter_mm + s) / 2.0)
        for j in range(k + 1):
            plate = plate - _box(b3d, x - 3.0 + 1.4 * j, x - 2.4 + 1.4 * j, -0.1, 1.2, -1.0, t + 1.0)
    return _single(plate, "hole coupon")


def tessellate(shape, tol=0.05, angular_tol=0.2):
    v, f = shape.tessellate(tol, angular_tol)
    return np.array([[p.X, p.Y, p.Z] for p in v]), np.array(f, dtype=int)
