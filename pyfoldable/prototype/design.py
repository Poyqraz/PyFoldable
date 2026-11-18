"""Design record of the printable prototype: planform, single-lug connection, hardware, print model and inputs.

Frame (identical to the display mesh and the coupled model, blade 1): x chordwise from the leading to the trailing
edge (the leading edge leads; rotation +Ω about +z), y spanwise outward from the shaft, z along the shaft (positive
twist lifts the leading edge, so the thrust side is +z). This package uses millimetres and degrees; every field
name carries its unit.

Reference planes and offset (owner request, 2026-11-18):

- plane A, z = 0: proximal reference plane through the quarter-chord line of the proximal sections (hub plane);
- plane B, z = δ: distal reference plane through the quarter-chord line of the distal sections;
- axial offset δ = z_B − z_A (``axial_offset_mm``, signed, + toward +z). It is a rigid translation along the pin and
  adds no angular degree of freedom; the deployed blade therefore has a step δ at the joint.
- lug stack along the pin: proximal lug [z_i − g/2 − t_p, z_i − g/2], distal lug [z_i + g/2, z_i + g/2 + t_d] with the
  lug interface plane z_i (default δ/2) and running gap g. Pin diameter, lug thicknesses, gap and total stack
  t_p + g + t_d are separate dimensions; the distance between the lug mid-planes, (t_p + t_d)/2 + g, is derived.

Joint topology (owner sketches): one lug (a boss around the pin) on each segment, one common pin parallel to the
shaft on the joint plane y = r_j at chordwise position ``pin_x_mm`` (from the quarter chord of the hinge section).
The distal segment folds backward (negative fold, toward the trailing edge). The open stop blocks forward rotation:
a stop nose on the distal root, ahead of the pin, reaches down into the proximal band and seats on a stop pad of
the proximal tip. A rigid stop that blocks forward rotation without blocking the backward fold must lie ahead of
the pin on the joint plane (points ahead of the pin move inboard on forward rotation and sweep only the outboard
half-plane when folding back); see ``docs/prototype_13in.md``.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field, replace
from functools import cached_property
from pathlib import Path

TEMPLATE = "configs/designs/TIP_HINGED_250_CANONICAL.toml"
MIN_LUG_MM = 2.0
MEASURED_FIELDS = ("measured_axial_play_mm", "measured_tilt_deg", "play_record_sha256", "measured_play_basis",
                   "measured_axial_play_u_mm", "measured_tilt_u_deg", "print_z_u_mm")
MIN_ZONE_MM = 10.0                            # hinge-zone half-width floor (the loft samples the zone every w/4)
LUG_PROUD_MM = 0.2                            # full-depth lug faces stand proud of the blade's extreme surface point:
#                                               a face tangent to the blade surface made OCC fusions fail silently
IN_TO_MM = 25.4

MATERIALS = {
    # Exploratory values for FFF parts at 100 % infill, printed with the rotor plane on the bed (in-plane loads run
    # along the layers). Typical public data-sheet / literature ranges, not measurements of the owner's printer.
    "PLA": dict(density_g_cm3=1.24, tensile_xy_mpa=40.0, tensile_z_mpa=20.0, shear_mpa=20.0, bearing_mpa=40.0,
                compressive_mpa=55.0, modulus_mpa=3000.0, poisson=0.35, glass_c=60.0),
    "ABS": dict(density_g_cm3=1.04, tensile_xy_mpa=30.0, tensile_z_mpa=15.0, shear_mpa=15.0, bearing_mpa=30.0,
                compressive_mpa=45.0, modulus_mpa=2000.0, poisson=0.35, glass_c=100.0),
}
MATERIAL_SOURCE = ("Keşif varsayımı: FFF %100 doluluk için tipik veri sayfası/literatür aralığının alt tarafı; "
                   "sahibin yazıcısı, filamenti ve baskı süreci için ölçülmedi.")
STEEL = dict(density_g_cm3=7.85, shear_mpa=120.0, bending_mpa=200.0)
STEEL_SOURCE = "Keşif varsayımı: ISO 2341 pim çeliği (ör. 4.6 sınıfı) için düşük taraf; tedarikçi verisiyle değiştirin."


@dataclass(frozen=True)
class Planform:
    """Aerodynamic planform (the analyses' sections). Stations: ((radius_mm, chord_mm, twist_deg), ...)."""
    profile_id: str = "NACA2412"
    diameter_mm: float = 13.0 * IN_TO_MM
    stations: tuple = ()
    template_id: str = "project_250"
    chord_scale: float = 1.0
    twist_scale: float = 1.0
    blade_count: int = 2
    # local hinge-zone shaping (0: none): chord and twist scaled by 1 − (1 − k)·b(r) with a cosine bump b of
    # half-width ``hinge_zone_mm`` centred on the joint plane; a new planform identity, not the template's
    hinge_zone_mm: float = 0.0               # inboard half-width (proximal side)
    hinge_zone_outboard_mm: float | None = None  # outboard half-width (distal side); None: same as inboard
    hinge_zone_center_mm: float = 0.0
    hinge_chord_factor: float = 1.0
    hinge_twist_factor: float = 1.0

    @property
    def tip_radius_mm(self):
        return self.diameter_mm / 2.0


@dataclass(frozen=True)
class Connection:
    hinge_radius_mm: float = 99.0             # joint plane r_j (proximal longer than distal)
    axial_offset_mm: float = 5.5              # δ = z_B − z_A
    lug_interface_z_mm: float | None = None   # z_i; None: δ/2
    pin_x_mm: float = 0.0                     # pin chordwise position from the hinge section's quarter chord
    pin_diameter_mm: float = 3.0
    hole_clearance_mm: float = 0.20           # diametral: printed hole = pin + clearance (calibrate with the coupon)
    lug_thickness_proximal_mm: float | None = None  # None: full depth (blade's far surface over the boss → interface)
    lug_thickness_distal_mm: float | None = None
    lug_gap_mm: float = 0.30                  # running gap between the lug faces
    boss_radius_mm: float = 5.5               # lug disk radius about the pin
    relief_clearance_mm: float = 0.6          # radial clearance of the swept relief beyond the other boss
    face_gap_mm: float = 0.30                 # spanwise gap between the body end faces at the joint plane
    nose_depth_mm: float = 4.0                # stop nose: spanwise extent outboard of the joint plane
    nose_extension_mm: float = 2.0            # stop nose / pad reach ahead of the leading edge
    pad_depth_mm: float = 4.0                 # stop pad: spanwise extent inboard of the joint plane
    stowed_angle_deg: float = -140.0          # required backward travel: owner decision (template declares −180°);
    #                                           the 4 mm stop nose doubles as the folded stop at ≈ 144°
    body_clearance_mm: float = 0.5            # required nominal clearance between the segments outside the joint
    # joint play measured on a printed fit pair (``fit.apply``); None: the worst-case model play is used
    measured_axial_play_mm: float | None = None
    measured_tilt_deg: float | None = None
    play_record_sha256: str | None = None     # SHA-256 of the fit record the measured play came from
    measured_play_basis: str | None = None    # "direct": measured on this design's own kit; "transferred": another
    measured_axial_play_u_mm: float | None = None   # standard uncertainties of the measurement (``fit.uncertainty``)
    measured_tilt_u_deg: float | None = None
    print_z_u_mm: float | None = None         # print variation of one surface (standard uncertainty)


@dataclass(frozen=True)
class Hardware:
    """Nominal pin set: ISO 2341 type A clevis pin Ø3 with head, turned groove for a DIN 6799 retaining washer
    (E-clip, size 2.3) and DIN 433 washers under the head and under the clip. Dimensions are catalogue nominals;
    verify against the supplier's drawing before ordering."""
    pin_standard: str = "ISO 2341-A Ø3 (kafa Ø5×1) + DIN 6799 kanalı (Ø2,3 × 0,64)"
    head_diameter_mm: float = 5.0
    head_height_mm: float = 1.0
    washer_od_mm: float = 6.0
    washer_id_mm: float = 3.2
    washer_thickness_mm: float = 0.5
    clip_od_mm: float = 6.0
    clip_thickness_mm: float = 0.6
    groove_diameter_mm: float = 2.3
    groove_width_mm: float = 0.64
    pin_end_mm: float = 0.8                   # pin length beyond the groove


@dataclass(frozen=True)
class PrintModel:
    material: str = "PLA"
    infill_fraction: float = 1.0              # 1: solid; blades and lugs are recommended solid
    wall_mm: float = 1.2                      # perimeters (3 × 0.4 mm nozzle)
    layer_mm: float = 0.2
    min_te_thickness_mm: float = 0.8          # printable trailing edge (template manufacturing section)
    te_blend_start: float = 0.5               # x/c where the trailing-edge thickening starts
    bed_mm: tuple = (256.0, 256.0, 256.0)     # Bambu Lab X1/P1/A1 class; the owner's printer is not yet specified
    orientation: str = "Rotor düzlemi tablada (z yukarı); pim ekseni yazıcı z ekseninde, lug yükü katmanlar boyunca."


@dataclass(frozen=True)
class Operating:
    """Owner inputs not yet supplied stay None and are reported as missing."""
    max_rpm: float | None = None
    required_thrust_n: float | None = None
    motor: str | None = None
    distal_thrust_n: float | None = None      # aerodynamic force on one distal segment along +z (e.g. from BEM)
    distal_drag_n: float | None = None        # in-plane aerodynamic force on one distal segment toward +x
    distal_aero_radius_mm: float | None = None
    what_if_rpm: tuple = (3000.0, 4000.0, 5000.0, 6000.0, 7000.0, 8000.0)
    safety_factor: float = 2.0


@dataclass(frozen=True)
class PrototypeDesign:
    planform: Planform
    connection: Connection = field(default_factory=Connection)
    hardware: Hardware = field(default_factory=Hardware)
    print_model: PrintModel = field(default_factory=PrintModel)
    operating: Operating = field(default_factory=Operating)
    hub_radius_mm: float = 15.0               # placeholder hub (motor interface not yet supplied)
    hub_height_mm: float = 12.0
    hub_bore_mm: float = 5.0
    fit_section_mm: float = 22.0              # short-section fit test: segment length each side of the joint
    name: str = "13in-v1"

    # ---------------------------------------------------------------- derived dimensions
    @property
    def interface_z_mm(self):
        c = self.connection
        return c.axial_offset_mm / 2.0 if c.lug_interface_z_mm is None else c.lug_interface_z_mm

    def body_band_at_pin_mm(self, segment: str):
        """(z_min, z_max) of the segment's printable section surfaces over the boss disk about the pin."""
        from .cad import section_points
        c = self.connection
        rj, R = c.hinge_radius_mm, c.boss_radius_mm
        if segment == "proximal":
            radii, z_off = (rj - R, rj - R / 2, rj), 0.0
        else:
            radii, z_off = (rj + c.face_gap_mm, rj + R / 2, rj + R), c.axial_offset_mm
        z = [p[2] for r in radii for p in section_points(self, r, z_off) if abs(p[0] - c.pin_x_mm) <= R]
        if not z:
            raise ValueError("Pim konumu menteşe kesitinin dışında (lug kanat kesitine bağlanamaz).")
        return min(z), max(z)

    @cached_property
    def lug_thicknesses_mm(self):
        """(t_p, t_d): explicit values, or full depth from the blade's far surface over the boss disk (plus
        ``LUG_PROUD_MM``) to the interface (each lug then engages its whole blade section; it follows the offset)."""
        c, zi = self.connection, self.interface_z_mm
        tp, td = c.lug_thickness_proximal_mm, c.lug_thickness_distal_mm
        if tp is None:
            tp = zi - c.lug_gap_mm / 2.0 - (self.body_band_at_pin_mm("proximal")[0] - LUG_PROUD_MM)
        if td is None:
            td = self.body_band_at_pin_mm("distal")[1] + LUG_PROUD_MM - zi - c.lug_gap_mm / 2.0
        return float(tp), float(td)

    @property
    def lug_bands_mm(self):
        """((z0, z1) proximal lug, (z0, z1) distal lug)."""
        c, zi = self.connection, self.interface_z_mm
        tp, td = self.lug_thicknesses_mm
        p1, d0 = zi - c.lug_gap_mm / 2.0, zi + c.lug_gap_mm / 2.0
        return (p1 - tp, p1), (d0, d0 + td)

    @property
    def lug_midplane_offset_mm(self):
        tp, td = self.lug_thicknesses_mm
        return (tp + td) / 2.0 + self.connection.lug_gap_mm

    @property
    def stack_thickness_mm(self):
        tp, td = self.lug_thicknesses_mm
        return tp + self.connection.lug_gap_mm + td

    @property
    def hole_diameter_mm(self):
        return self.connection.pin_diameter_mm + self.connection.hole_clearance_mm

    @property
    def relief_radius_mm(self):
        return self.connection.boss_radius_mm + self.connection.relief_clearance_mm

    @property
    def pin_length_mm(self):
        h = self.hardware
        return (self.stack_thickness_mm + 2 * h.washer_thickness_mm + h.groove_width_mm + h.pin_end_mm)

    def section(self, radius_mm):
        """(chord_mm, twist_deg) linear in radius between stations (as the BEM); constant outside."""
        st = self.planform.stations
        r = [s[0] for s in st]
        if radius_mm <= r[0]:
            return st[0][1], st[0][2]
        if radius_mm >= r[-1]:
            return st[-1][1], st[-1][2]
        k = next(i for i in range(len(r) - 1) if r[i] <= radius_mm <= r[i + 1])
        w = (radius_mm - r[k]) / (r[k + 1] - r[k])
        return (st[k][1] + w * (st[k + 1][1] - st[k][1]), st[k][2] + w * (st[k + 1][2] - st[k][2]))

    @property
    def section_identity(self):
        """Printable section = catalog profile with a thickened trailing edge: a new aerodynamic identity."""
        return f"{self.planform.profile_id}-te{self.print_model.min_te_thickness_mm:.2f}mm-x{self.print_model.te_blend_start:.2f}"

    @property
    def identity(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, default=list).encode()).hexdigest()

    def missing_owner_inputs(self):
        o = self.operating
        out = [label for v, label in ((o.max_rpm, "azami devir"), (o.required_thrust_n, "gerekli itki"),
                                      (o.motor, "motor"))
               if v is None]
        return out + ["yazıcı modeli/malzeme sınıfı/süreç (keşif varsayımı kullanılıyor)",
                      "motor bağlantısı (göbek yer tutucu)",
                      f"gerekli katlanma açısı (varsayım {-self.connection.stowed_angle_deg:.0f}°; şablon 180° bildirir)"]


def validate(d: PrototypeDesign) -> list[str]:
    """Hard input errors (the design cannot be built). Feasibility problems are reported by the checks instead."""
    errs = []
    p, c, h, pm = d.planform, d.connection, d.hardware, d.print_model
    r = [s[0] for s in p.stations]
    if len(r) < 2 or any(b <= a for a, b in zip(r, r[1:])):
        errs.append("İstasyonlar en az iki ve artan yarıçapta olmalı.")
    if any(not (s[1] > 0) for s in p.stations):
        errs.append("Kordlar pozitif olmalı.")
    if r and not (d.hub_radius_mm < r[0] and r[-1] <= p.tip_radius_mm + 1e-9):
        errs.append("İstasyonlar göbek ile uç yarıçapı arasında olmalı.")
    if r and not (r[0] + 10 < c.hinge_radius_mm < r[-1] - 10):
        errs.append("Menteşe istasyon aralığının içinde olmalı (≥ 10 mm pay).")
    if c.hinge_radius_mm - d.hub_radius_mm <= p.tip_radius_mm - c.hinge_radius_mm:
        errs.append("Proksimal parça distal parçadan uzun olmalı (sahip tasarım amacı).")
    positive = dict(pin_diameter_mm=c.pin_diameter_mm, boss_radius_mm=c.boss_radius_mm,
                    nose_depth_mm=c.nose_depth_mm, pad_depth_mm=c.pad_depth_mm, wall_mm=pm.wall_mm,
                    layer_mm=pm.layer_mm, hub_height_mm=d.hub_height_mm)
    positive.update({k: v for k, v in (("lug_thickness_proximal_mm", c.lug_thickness_proximal_mm),
                                       ("lug_thickness_distal_mm", c.lug_thickness_distal_mm)) if v is not None})
    errs += [f"{k} pozitif olmalı." for k, v in positive.items() if not (math.isfinite(v) and v > 0)]
    if p.hinge_zone_mm:
        if not (math.isfinite(p.hinge_zone_mm) and p.hinge_zone_mm >= MIN_ZONE_MM):
            errs.append(f"Menteşe bölgesi yarı genişliği ≥ {MIN_ZONE_MM:.0f} mm olmalı.")
        elif abs(p.hinge_zone_center_mm - c.hinge_radius_mm) > 1e-6:
            errs.append("Menteşe bölgesi biçimlendirmesi menteşe düzlemine ortalanmalı (yarıçapı r_j ile aynı).")
        elif p.hinge_zone_outboard_mm is not None and not (math.isfinite(p.hinge_zone_outboard_mm)
                                                            and p.hinge_zone_outboard_mm >= MIN_ZONE_MM):
            errs.append(f"Menteşe bölgesi dış yarı genişliği ≥ {MIN_ZONE_MM:.0f} mm olmalı.")
        elif r and not (r[0] <= c.hinge_radius_mm - p.hinge_zone_mm
                        and c.hinge_radius_mm + (p.hinge_zone_outboard_mm or p.hinge_zone_mm) <= r[-1]):
            errs.append("Menteşe bölgesi istasyon aralığının içinde kalmalı.")
        for k, v in (("hinge_chord_factor", p.hinge_chord_factor), ("hinge_twist_factor", p.hinge_twist_factor)):
            if not (math.isfinite(v) and 0.2 <= v <= 1.5):
                errs.append(f"{k} 0,2 ile 1,5 arasında olmalı.")
    if c.axial_offset_mm <= 0:
        errs.append("Ofset δ > 0 olmalı: v1 distal parçayı proksimalin üstüne (itki tarafına) yerleştirir.")
    if not errs and r and r[0] + 10 < c.hinge_radius_mm < r[-1] - 10:
        try:
            tp, td = d.lug_thicknesses_mm
        except ValueError as exc:
            return errs + [str(exc)]
        if min(tp, td) < MIN_LUG_MM:
            errs.append(f"Lug kalınlığı {min(tp, td):.2f} mm < {MIN_LUG_MM} mm: ofset/arayüz düzlemi lugları "
                        "sığdırmıyor (ofseti artırın veya arayüz düzlemini kaydırın).")
    nonneg = dict(hole_clearance_mm=c.hole_clearance_mm, lug_gap_mm=c.lug_gap_mm, face_gap_mm=c.face_gap_mm,
                  relief_clearance_mm=c.relief_clearance_mm, nose_extension_mm=c.nose_extension_mm)
    errs += [f"{k} negatif olamaz." for k, v in nonneg.items() if not (math.isfinite(v) and v >= 0)]
    measured = tuple(getattr(c, k) for k in MEASURED_FIELDS)
    numbers = (c.measured_axial_play_mm, c.measured_tilt_deg, c.measured_axial_play_u_mm, c.measured_tilt_u_deg,
               c.print_z_u_mm)
    if any(v is not None for v in measured):
        if any(v is None for v in measured):
            errs.append("Ölçülen boşluk; eksenel boşluk, eğilme, belirsizlikler, dayanak ve kayıt özetiyle birlikte "
                        "girilmeli.")
        elif c.measured_play_basis not in ("direct", "transferred"):
            errs.append("Ölçülen boşluğun dayanağı 'direct' veya 'transferred' olmalı.")
        elif (not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0
                      for v in numbers)
              or not (isinstance(c.play_record_sha256, str) and len(c.play_record_sha256) == 64
                      and all(ch in "0123456789abcdef" for ch in c.play_record_sha256))):
            errs.append("Ölçülen boşluk değerleri sonlu ve negatif olmayan sayılar, kayıt özeti 64 karakterlik onaltılık "
                        "SHA-256 olmalı.")
    if c.lug_gap_mm <= 0:
        errs.append("Lug aralığı sıfırdan büyük olmalı (dönen yüzeyler).")
    if c.boss_radius_mm <= d.hole_diameter_mm / 2 + pm.wall_mm:
        errs.append("Lug yarıçapı delik yarıçapı + bir çevre duvarından büyük olmalı.")
    if not -180.0 <= c.stowed_angle_deg < 0:
        errs.append("Katlanma açısı −180° ile 0° arasında olmalı (geri katlanma).")
    if not 0 < pm.infill_fraction <= 1:
        errs.append("Doluluk oranı (0, 1] aralığında olmalı.")
    if pm.material not in MATERIALS:
        errs.append("Malzeme PLA veya ABS olmalı.")
    if h.groove_diameter_mm >= c.pin_diameter_mm or h.head_diameter_mm <= c.pin_diameter_mm:
        errs.append("Pim kanalı pimden küçük, kafa pimden büyük olmalı.")
    if not 0 < d.hub_bore_mm < 2 * d.hub_radius_mm - 4:
        errs.append("Göbek deliği göbekten en az 2 mm et bırakmalı.")
    o = d.operating
    if o.max_rpm is not None and not (math.isfinite(o.max_rpm) and o.max_rpm > 0):
        errs.append("Azami devir pozitif olmalı.")
    if o.distal_thrust_n is not None or o.distal_drag_n is not None:
        if o.distal_aero_radius_mm is None or o.max_rpm is None:
            errs.append("Distal aerodinamik kuvvetler etki yarıçapı ve azami devirle birlikte girilmeli.")
        elif not c.hinge_radius_mm < o.distal_aero_radius_mm <= p.tip_radius_mm:
            errs.append("Aerodinamik etki yarıçapı distal parçanın üzerinde olmalı.")
    if not o.safety_factor >= 1:
        errs.append("Güvenlik katsayısı ≥ 1 olmalı.")
    return errs


def planform_from_template(root: Path, *, diameter_mm=13.0 * IN_TO_MM, chord_scale=1.0, twist_scale=1.0,
                           profile_id="NACA2412", template_id="project_250", hinge_zone_mm=0.0,
                           hinge_zone_center_mm=0.0, hinge_chord_factor=1.0, hinge_twist_factor=1.0,
                           hinge_zone_outboard_mm=None) -> Planform:
    """The research template's stations scaled exactly as the research workflow scales them (chord by diameter
    ratio × chord scale, twist × twist scale), so BEM in *Analiz* can run on the same planform; with an optional local
    hinge-zone shaping (stations inserted every quarter half-width, values from the linear template interpolation)."""
    from pyfoldable.core.config import load_design_config
    design = load_design_config(Path(root) / TEMPLATE)
    scale = diameter_mm / 1000.0 / design.blade.diameter_m
    R = diameter_mm / 2.0
    stations = tuple((round(s.r_over_R * R, 6), round(s.chord_m * 1000 * scale * chord_scale, 6),
                      round(math.degrees(s.twist_rad) * twist_scale, 6)) for s in design.blade.stations)
    if hinge_zone_mm > 0:
        stations = hinge_zone_stations(stations, hinge_zone_center_mm, hinge_zone_mm, hinge_chord_factor,
                                       hinge_twist_factor, hinge_zone_outboard_mm)
    return Planform(profile_id, diameter_mm, stations, template_id, chord_scale, twist_scale, design.blade.blade_count,
                    hinge_zone_mm, hinge_zone_outboard_mm if hinge_zone_mm > 0 else None,
                    hinge_zone_center_mm if hinge_zone_mm > 0 else 0.0, hinge_chord_factor, hinge_twist_factor)


def hinge_zone_stations(stations, center_mm, half_width_mm, chord_factor, twist_factor, outboard_mm=None):
    """Stations with a cosine-blended local chord/twist scaling about the joint (outside the zone: unchanged); the
    outboard half-width may differ from the inboard one."""
    r = [s[0] for s in stations]
    w_in, w_out = half_width_mm, outboard_mm or half_width_mm
    marks = [center_mm + w_in * k / 4.0 for k in range(-4, 1)] + [center_mm + w_out * k / 4.0 for k in range(1, 5)]
    grid = sorted({*r, *(round(x, 6) for x in marks if r[0] < x < r[-1])})

    def interp(x, i):
        k = next(j for j in range(len(r) - 1) if r[j] <= x <= r[j + 1])
        w = (x - r[k]) / (r[k + 1] - r[k])
        return stations[k][i] + w * (stations[k + 1][i] - stations[k][i])

    def bump(x):
        u = (x - center_mm) / w_out if x > center_mm else (center_mm - x) / w_in
        return 0.5 * (1.0 + math.cos(math.pi * u)) if u < 1.0 else 0.0
    return tuple((x, round(interp(x, 1) * (1 - (1 - chord_factor) * bump(x)), 6),
                  round(interp(x, 2) * (1 - (1 - twist_factor) * bump(x)), 6)) for x in grid)


def default_design(root: Path, **planform_kwargs) -> PrototypeDesign:
    return PrototypeDesign(planform_from_template(root, **planform_kwargs))


def with_changes(d: PrototypeDesign, **changes) -> PrototypeDesign:
    """Replace fields by dotted path, e.g. with_changes(d, **{"connection.axial_offset_mm": 6.0})."""
    groups = {}
    for key, value in changes.items():
        head, _, tail = key.partition(".")
        if tail:
            groups.setdefault(head, {})[tail] = value
        else:
            groups[head] = value
    out = {}
    for head, value in groups.items():
        out[head] = replace(getattr(d, head), **value) if isinstance(value, dict) else value
    return replace(d, **out)


def without_measurement(d: PrototypeDesign) -> PrototypeDesign:
    """The design with no measured play (a geometry change makes a measurement on the old geometry inapplicable)."""
    return with_changes(d, **{f"connection.{k}": None for k in MEASURED_FIELDS})


def to_json(d: PrototypeDesign) -> str:
    return json.dumps(asdict(d), indent=2, ensure_ascii=False, default=list)


def from_json(text: str) -> PrototypeDesign:
    raw = json.loads(text)
    parts = {"planform": Planform, "connection": Connection, "hardware": Hardware, "print_model": PrintModel,
             "operating": Operating}
    kw = {k: (parts[k](**{f: (tuple(map(tuple, v)) if f == "stations" else tuple(v) if isinstance(v, list) else v)
                          for f, v in raw[k].items()}) if k in parts else raw[k]) for k in raw}
    return PrototypeDesign(**kw)
