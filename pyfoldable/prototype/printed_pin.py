"""Printed-pin hinge demonstrator for the F1S short joint: temporary, hand-operated, not the metal configuration.

Selected arrangement (one, not a family):

- **Pin:** PLA, integral head (Ø8 × 1.6 mm, inside the lugs' Ø8.6 spot face), printed upright with the head on the
  bed. The bearing surface is then round, and its layer rings run in the direction of rotation. Three shank
  diameters (3.80 / 3.90 / 4.00 mm, identified by 1 / 2 / 3 notches on the head rim) form the fit experiment. The
  joint hole stays at the metal design clearance, and the pin is chosen to fit the hole, never the reverse.
- **Retention:** a flat PLA C-clip in a groove that lies wholly above the distal lug, outside the bearing span. The
  clip prints flat, so its arms flex within the layers. It is sized for PLA: 1.6 mm thick, 1.3 mm arms, a 0.3 mm snap
  on a Ø3.0 groove root shared by all three pins, and a grip tab for removal. It is not a scaled DIN 6799.
- **No washers:** the head and the clip bear on the lugs' washer-seat faces, which print on the bed.
- **Length:** taken from the regenerated solids. Head underside to the groove's near flank is the lug stack
  q1 − p0 plus an allowance for thicker printed lugs; the far flank adds the clip thickness and the groove slack.
- **End play** (open assembly, proximal on the head): the distal can drop by the inter-lug gap (the metal design's
  running gap, the only travel toward the proximal) and rise by the clip-side allowance (thick-lug allowance + clip
  slack). Total end play = inter-lug gap + clip-side allowance; ``end_play_from_solids`` reproduces it from the
  solids. The extra clip-side room lets the distal rock more than the metal model allows (``rocking``).
- **Joint:** the F1S fit-test section, with the same pivot, lugs, stop, blade sections and hole. It is trimmed for
  printing like the metal kit's fit pair, but has no clamp block or load tab, so nothing but the joint limits the
  hand fold.

Evidence: a trial record (``SCHEMA``) is classified as a printed-pin observation. It is shown, but never applied to
a design. It is not evidence for the metal-pin assembly's play, friction, strength, contact loads or speed. Observed
contact is a geometric observation, not a quantitative clearance acceptance. The demonstrator has no operating
envelope and inherits no RPM limit. Physical qualification: false.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

from . import cad, fit
from .design import PrototypeDesign, to_json

SCHEMA = "pyfoldable.prototype.printed_pin_trial/1"
KIT_SCHEMA = "pyfoldable.prototype.printed_pin_demo/1"
EVIDENCE = "printed_pin_observation"
PIN_DIAMETERS_MM = (3.8, 3.9, 4.0)                  # notches on the head rim: 1, 2, 3


@dataclass(frozen=True)
class PinSpec:
    head_diameter_mm: float = 8.0
    head_height_mm: float = 1.6
    groove_root_mm: float = 3.0                     # one clip for every pin variant (groove depth 0.4–0.5 mm)
    clip_thickness_mm: float = 1.6                  # 8 layers at 0.2 mm
    groove_slack_mm: float = 0.2                    # groove width − clip thickness
    stack_allowance_mm: float = 0.15                # printed lugs may be this much thicker in total
    end_mm: float = 1.2                             # pin beyond the groove
    tip_chamfer_mm: float = 0.4
    notch_depth_mm: float = 0.6
    clip_seat_mm: float = 3.1
    clip_arm_mm: float = 1.3
    clip_mouth_mm: float = 2.7                      # < groove root: the clip snaps over it
    clip_lead_mm: float = 3.6                       # mouth width at the clip's outer edge (lead-in)
    clip_tab_mm: tuple = (3.0, 4.0)                 # grip tab length, width


SPEC = PinSpec()

_P = fit.FIELDS
FIELDS = {
    "schema": ("text", None, True, "kayıt şeması"),
    "kit_design_sha256": ("text", None, True, "basılı pim gösterici paketinin kimliği (predictions.json)"),
    **{k: _P[k] for k in ("print_printer", "print_material_family", "print_filament_product",
                          "print_filament_manufacturer", "print_filament_lot", "print_plate", "print_slicer",
                          "print_project_sha256", "print_nozzle_mm", "print_layer_mm", "print_walls",
                          "print_infill_fraction", "print_changes")},
    "pin_print_orientation": ("text", None, True, "pimlerin gerçek baskı yönü (önerilen: dik, kafa tablada)"),
    "pin_variant_mm": ("pin", None, True, "mafsalda kullanılan pimin CAD çapı [mm] (kafadaki çentik: 1 = 3,80; "
                                          "2 = 3,90; 3 = 4,00)"),
    "pin_diameter_a_mm": ("num", (1.0, 10.0), True, "kullanılan pimin taşıma bölgesinde ölçülen çapı [mm]"),
    "pin_diameter_b_mm": ("num", (1.0, 10.0), False, "aynı kesitte ilk ölçüme dik ölçülen çap [mm] (ovallik)"),
    "other_pins_note": ("text", None, False, "diğer pim çeşitlerinin ölçülen çapı ve deliklerdeki geçmesi"),
    "pin_head_to_groove_near_mm": ("num", (3.0, 40.0), False, "kafa altından kanalın kafaya yakın kenarına (uzak kenarına değil) "
                                                              "ölçülen boy [mm] (kumpas derinlik ucu)"),
    "lug_thickness_proximal_mm": ("num", (0.5, 30.0), False, "proksimal lug ölçülen kalınlığı [mm]"),
    "lug_thickness_distal_mm": ("num", (0.5, 30.0), False, "distal lug ölçülen kalınlığı [mm]"),
    "coupon_fit": ("fits", None, False, "kullanılan pimle kupon deliği başına geçme: " + " / ".join(fit.FITS)),
    "coupon_hole_mm": ("holes", None, False, "kupon deliği başına ölçülen çap [mm] (pim mastarı; bilinmiyorsa null)"),
    "insertion_fit": ("fit", None, True, "pimin iki mafsal deliğine elle takılması: " + " / ".join(fit.FITS)),
    "removal_by_hand": ("bool", None, False, "pim aletsiz çıkarılabildi mi"),
    "clip_installs": ("bool", None, True, "klips kanala elle takıldı mı"),
    "clip_removes": ("bool", None, False, "klips tırnakla/elle çıkarılabildi mi"),
    "clip_retains": ("bool", None, True, "deneme boyunca klips yerinde kaldı mı"),
    "rotation_free": ("bool", None, True, "distal tüm hareket boyunca elle takılmadan dönüyor mu"),
    "end_play_total_mm": ("num", (0.0, 3.0), False, "uçtan uca eksenel boşluk [mm]: distal proksimal lug'a "
                                                     "bastırılmış, klips kanalın uzak kenarına itilmişken distal üst yüzü "
                                                     "ile klips arasındaki sentil ölçüsü (ölçülmediyse null)"),
    "open_stop_seats": ("bool", None, True, "açık konumda burun pede oturuyor mu (ışık testi)"),
    "stop_gap_mm": ("num", (0.0, 5.0), False, "açık stop aralığı [mm] (sentil)"),
    "folded_stop_deg": ("num", (0.0, 180.0), False, "elle ulaşılan katlanma açısı [°] (açıölçer)"),
    "interference_observed": ("text", None, False, "görülen temas/sürtünme yeri ve açısı (yoksa boş)"),
    "cycle_count": ("int", (0, 100000), True, "beyan edilen elle açma–katlama çevrimi sayısı"),
    "wear_observed": ("text", None, False, "çevrimlerden sonra aşınma, beyazlama, toz, parlama"),
    "play_change_observed": ("text", None, False, "çevrimlerden sonra boşluktaki değişim (hissedilen veya ölçülen)"),
    "damage_observed": ("text", None, False, "kırık, çatlak, katman ayrılması, eğilmiş pim"),
    "photos": ("text", None, False, "fotoğraf dosya adları"),
    "measurement_resolution_mm": ("num", (0.001, 0.5), False, "kullanılan ölçü aletinin çözünürlüğü [mm]"),
    "notes": ("text", None, False, "serbest not"),
}


def demo_identity(d: PrototypeDesign, spec: PinSpec = SPEC) -> str:
    """Identity of the demonstrator configuration: the joint design, the printed pin/clip spec and the pin variants."""
    key = {"kind": KIT_SCHEMA, "design": d.identity, "spec": asdict(spec), "pins": list(PIN_DIAMETERS_MM)}
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------------ geometry
def _groove_z(stack, spec=SPEC):
    """(near flank, far flank, top) of the pin in its own frame (head underside at z = head height)."""
    g0 = spec.head_height_mm + stack + spec.stack_allowance_mm
    g1 = g0 + spec.clip_thickness_mm + spec.groove_slack_mm
    return g0, g1, g1 + spec.end_mm


def pin_solid(dia, stack, notches=0, spec=SPEC):
    """Printed pin in its print frame: axis z, head on z = 0, groove outside the lug stack, chamfered tip."""
    b3d = cad._b3d()
    s = spec
    g0, g1, top = _groove_z(stack, s)
    r, rh = dia / 2.0, s.head_diameter_mm / 2.0
    p = cad._zcyl(b3d, 0, 0, 0, s.head_height_mm, rh) + cad._zcyl(b3d, 0, 0, s.head_height_mm, top, r)
    p = p - (cad._zcyl(b3d, 0, 0, g0, g1, r + 0.5) - cad._zcyl(b3d, 0, 0, g0 - 0.1, g1 + 0.1, s.groove_root_mm / 2.0))
    p = b3d.chamfer(p.edges().group_by(b3d.Axis.Z)[-1], s.tip_chamfer_mm)
    for k in range(notches):                       # identification: k notches on the head rim
        cut = cad._box(b3d, rh - s.notch_depth_mm, rh + 1.0, -0.4, 0.4, -1.0, s.head_height_mm + 1.0)
        p = p - cut.rotate(b3d.Axis.Z, 90.0 + 25.0 * k)
    return cad._single(p, f"printed pin Ø{dia:g}")


def clip_solid(spec=SPEC):
    """Flat C-clip in its print frame: seat on the origin, z 0..t, mouth toward +x, grip tab toward −x."""
    b3d = cad._b3d()
    s = spec
    t, rs = s.clip_thickness_mm, s.clip_seat_mm / 2.0
    ro = rs + s.clip_arm_mm
    tab_len, tab_w = s.clip_tab_mm
    body = cad._zcyl(b3d, 0, 0, 0, t, ro) + cad._box(b3d, -(ro + tab_len), -ro + 0.5, -tab_w / 2, tab_w / 2, 0, t)
    m, lead, xl = s.clip_mouth_mm / 2.0, s.clip_lead_mm / 2.0, ro - 0.6
    mouth = b3d.extrude(b3d.Polygon((0, -m), (xl, -m), (ro + 0.01, -lead), (ro + 1, -lead), (ro + 1, lead),
                                    (ro + 0.01, lead), (xl, m), (0, m), align=None), t + 2.0)
    clip = body - cad._zcyl(b3d, 0, 0, -1, t + 1, rs) - mouth.translate(b3d.Vector(0, 0, -1.0))
    return cad._single(clip, "printed clip")


def build(d: PrototypeDesign, spec: PinSpec = SPEC) -> dict:
    """The demonstrator: trimmed joint stubs (as ``cad.Parts`` for the sweep), each pin variant and the clip in their
    print frames, and the largest pin and the clip posed on the joint axis (the open assembly)."""
    b3d = cad._b3d()
    full = cad.build(d)
    prox, dist = cad.print_trimmed_stubs(full)
    (p0, _), (_, q1) = d.lug_bands_mm
    stack = float(dist.bounding_box().max.Z - prox.bounding_box().min.Z)          # from the solids, not a constant
    if abs(stack - (q1 - p0)) > 1e-6:
        raise RuntimeError(f"Trimmed stubs span {stack:.3f} mm, the lug stack is {q1 - p0:.3f} mm.")
    pins = {dia: pin_solid(dia, stack, k + 1, spec) for k, dia in enumerate(PIN_DIAMETERS_MM)}
    clip = clip_solid(spec)
    px, py = full.pin_axis
    z_head = p0 - spec.head_height_mm
    g0, _, _ = _groove_z(stack, spec)
    pin_at = pins[max(PIN_DIAMETERS_MM)].translate(b3d.Vector(px, py, z_head))
    clip_at = clip.translate(b3d.Vector(px, py, z_head + g0))                  # resting on the groove's near flank
    parts = replace(full, proximal=prox, distal=dist, hardware={"pin": pin_at, "clip": clip_at})
    return {"parts": parts, "pins": pins, "clip": clip, "stack_mm": stack, "spec": spec, "z_head_mm": z_head}


def _vol(a, b):
    x = a & b
    return 0.0 if x is None else float(x.volume)


def _free_travel(moving, fixed, sign, hi=2.0, tol=1e-3):
    """Largest z translation (sign ±1) of ``moving`` before it overlaps ``fixed`` (bisection, overlap > 1e-4 mm³)."""
    b3d = cad._b3d()
    if _vol(moving, fixed) > 1e-4:
        raise RuntimeError("Parts overlap at the nominal pose.")
    lo = 0.0
    while hi - lo > tol:
        mid = (lo + hi) / 2.0
        if _vol(moving.translate(b3d.Vector(0, 0, sign * mid)), fixed) > 1e-4:
            hi = mid
        else:
            lo = mid
    return lo


def end_play_from_solids(demo: dict) -> dict:
    """Distal axial travel in the open assembly with the proximal on the head: down onto the proximal lug, and up to
    the clip pushed against the groove's far flank (the clip's own slack measured against the pin)."""
    b3d = cad._b3d()
    parts = demo["parts"]
    hw = parts.hardware
    slack = _free_travel(hw["clip"], hw["pin"], +1)
    clip_far = hw["clip"].translate(b3d.Vector(0, 0, slack))
    down = _free_travel(parts.distal, parts.proximal, -1)
    up = _free_travel(parts.distal, clip_far, +1)
    return {"below_nominal": down, "above_nominal": up, "total": down + up, "clip_slack": slack,
            "method": "katıların z ötelemesiyle ikiye bölme, 0,001 mm"}


def _finite(x):
    return None if x is None or not math.isfinite(x) else float(x)


def fold_travel(sw: dict):
    """(useful hand-fold travel [deg], index of the tightest sampled pose inside it) from a column sweep: the travel
    ends one step before body or nose contact. Contact at the first sampled step is refused (no useful travel)."""
    ang, gap, ngap = (np.array(sw[k], dtype=float) for k in ("angles_deg", "gap_mm", "nose_gap_mm"))
    step = abs(ang[1] - ang[0]) if len(ang) > 1 else 1.0
    hit = np.flatnonzero((gap < 0.0) | (ngap < 0.0))
    travel = float(-ang[hit[0]] - step) if len(hit) else float(-ang[-1])
    if len(hit) and hit[0] == 0:                       # the first sampled pose already touches: nothing sampled is free
        raise RuntimeError(f"Gövdeler ilk taranan açıda ({-ang[0]:g}°) temas ediyor: elle yararlı katlanma yok.")
    within = -ang <= travel + 1e-9
    return travel, int(np.argmin(np.where(within, gap, np.inf)))


def check(demo: dict) -> dict:
    """Retention geometry, interference at open/tightest/folded, pin and clip access paths, and the hand-fold travel
    (column sweep of the stubs: travel ends one step before body or nose contact)."""
    from . import checks
    b3d = cad._b3d()
    parts, s, stack = demo["parts"], demo["spec"], demo["stack_mm"]
    d, hw = parts.design, parts.hardware
    sw = checks.sweep(parts)
    ang, gap = np.array(sw["angles_deg"], dtype=float), np.array(sw["gap_mm"], dtype=float)
    travel, k = fold_travel(sw)
    configs = {"open": 0.0, "tightest": float(ang[k]), "folded": -travel}
    inter = {"pim_proksimal": _vol(hw["pin"], parts.proximal), "klips_proksimal": _vol(hw["clip"], parts.proximal)}
    for name, a in configs.items():
        dist = parts.distal_at(a)
        inter.update({f"pim_distal_{name}": _vol(hw["pin"], dist), f"klips_distal_{name}": _vol(hw["clip"], dist),
                      f"proksimal_distal_{name}": _vol(parts.proximal, dist)})
    # access: the pin goes in from below along its axis; the clip slides in along +x, mouth first, above the distal
    length = _groove_z(stack, s)[2]
    pin_path = sum(_vol(hw["pin"].translate(b3d.Vector(0, 0, -dz)), body)
                   for dz in np.arange(1.0, length + 2.0, 1.0) for body in (parts.proximal, parts.distal))
    clip_path = sum(_vol(hw["clip"].translate(b3d.Vector(-dx, 0, 0)), body)
                    for dx in np.arange(1.0, 16.0, 1.0) for body in (parts.proximal, parts.distal))
    h = d.hardware
    g0, g1, top = _groove_z(stack, s)
    (_, p1), (q0, _) = d.lug_bands_mm
    lug_gap = q0 - p1                                                              # inter-lug running gap
    side = s.stack_allowance_mm + s.groove_slack_mm                                 # clip-side assembly allowance
    tp, td = d.lug_thicknesses_mm
    # tilt about an in-plane axis (radians). faces: total end play over the boss radius, the codebase's metal-model
    # convention (checks.joint_play: lug gap / R_b) and the conservative bound; clip: the distal pivots under the clip
    # (outer radius r_c) and drops at the boss edge, (g + a)/(R_b + r_c). holes: c/t_d + c/t_p with the CAD pin.
    rb = d.connection.boss_radius_mm
    r_clip = s.clip_seat_mm / 2.0 + s.clip_arm_mm
    faces = (lug_gap + side) / rb
    faces_clip = (lug_gap + side) / (rb + r_clip)
    holes = {f"{p:.2f}": (d.hole_diameter_mm - p) / td + (d.hole_diameter_mm - p) / tp for p in PIN_DIAMETERS_MM}
    worst = {k: min(faces, v) for k, v in holes.items()}
    worst_clip = {k: min(faces_clip, v) for k, v in holes.items()}
    geometry = {
        "stack_mm": stack, "pin_length_mm": top,
        "grip_near_flank_mm": g0 - s.head_height_mm, "grip_far_flank_mm": g1 - s.head_height_mm,
        "groove_start_above_stack_mm": g0 - s.head_height_mm - stack, "groove_width_mm": g1 - g0,
        "groove_root_mm": s.groove_root_mm, "groove_depth_mm": {f"{p:.2f}": (p - s.groove_root_mm) / 2 for p in PIN_DIAMETERS_MM},
        "clip_seat_mm": s.clip_seat_mm, "clip_mouth_mm": s.clip_mouth_mm, "clip_thickness_mm": s.clip_thickness_mm,
        "inter_lug_gap_mm": lug_gap, "thick_lug_allowance_mm": s.stack_allowance_mm,
        "clip_groove_slack_mm": s.groove_slack_mm, "clip_side_allowance_mm": side, "end_play_total_mm": lug_gap + side,
        "end_play_from_solids_mm": end_play_from_solids(demo),
        "assembles_up_to_extra_stack_mm": side,
        "rocking": {"faces_deg": math.degrees(faces), "faces_clip_bearing_deg": math.degrees(faces_clip),
                    "holes_deg": {k: math.degrees(v) for k, v in holes.items()},
                    "worst_deg": {k: math.degrees(v) for k, v in worst.items()},
                    "worst_clip_bearing_deg": {k: math.degrees(v) for k, v in worst_clip.items()},
                    "metal_model_faces_deg": math.degrees(lug_gap / rb),
                    "note": "yüz sınırı (ihtiyatlı, metal modelin kuralı) = uçtan uca eksenel boşluk / göbek yarıçapı; "
                            "klips dayanmalı = boşluk / (göbek yarıçapı + klips dış yarıçapı); delik sınırı = "
                            "c/t_d + c/t_p (CAD); en kötüsü = min(yüz, delik)"},
        "head_diameter_mm": s.head_diameter_mm,
        "spot_face_diameter_mm": 2 * (max(h.washer_od_mm, h.clip_od_mm, h.head_diameter_mm) / 2 + cad.SPOT_CLEAR_MM),
        "hole_diameter_mm": d.hole_diameter_mm,
        "diametral_clearance_cad_mm": {f"{p:.2f}": d.hole_diameter_mm - p for p in PIN_DIAMETERS_MM},
    }
    s_k = sw["where"][k][2] if sw["where"][k] else None

    def with_rocking(tilts):
        # distal tip tilted down (worst direction); it drops by the inter-lug gap at the boss edge (radius R_b) and
        # rocks about that edge, so a point at radial distance s from the pin drops g + φ·(s − R_b). An estimate at
        # the nominal tightest column only: a geometric expectation, not a clearance acceptance.
        if s_k is None or not math.isfinite(gap[k]):
            return None
        return {kk: float(gap[k]) - (lug_gap + v * max(0.0, s_k - rb)) for kk, v in tilts.items()}
    fold = {"useful_travel_deg": travel, "tightest_angle_deg": configs["tightest"],
            "min_gap_mm": _finite(float(gap[k])), "folded_stop_deg": sw["folded_stop_deg"],
            "tightest_distance_from_pin_mm": s_k,
            "tightest_gap_with_rocking_mm": with_rocking(worst),
            "tightest_gap_with_rocking_clip_bearing_mm": with_rocking(worst_clip),
            "body_contact_deg": float(-ang[np.flatnonzero(gap < 0.0)[0]]) if (gap < 0.0).any() else None,
            "metal_design_required_travel_deg": sw["required_travel_deg"], "method": sw["method"]}
    return {"geometry": geometry, "fold": fold, "configurations": configs, "interference_mm3": inter,
            "access": {"pin_path_clear": pin_path < 1e-3, "clip_path_clear": clip_path < 1e-3,
                       "pin_path_mm3": pin_path, "clip_path_mm3": clip_path,
                       "note": "klipsin pim kanalına oturması tasarlanmış bir yaylanmadır (ağız < kanal dibi)"},
            "sweep": sw}


def predictions(d: PrototypeDesign, chk: dict, spec: PinSpec = SPEC) -> dict:
    h = d.hardware
    return {
        "schema": KIT_SCHEMA, "kit_design_sha256": demo_identity(d, spec), "kit_design_name": d.name,
        "design_sha256": d.identity, "evidence": EVIDENCE, "physical_qualification": False,
        "operating_envelope": None, "rpm_limit": None,
        "pin_diameters_mm": list(PIN_DIAMETERS_MM), "hole_diameter_mm": d.hole_diameter_mm,
        "hole_clearance_mm": d.connection.hole_clearance_mm, "coupon_steps_mm": list(fit.COUPON_STEPS_MM),
        "lug_thicknesses_mm": list(d.lug_thicknesses_mm), "pin_spec": asdict(spec),
        "geometry": chk["geometry"], "fold": chk["fold"], "configurations": chk["configurations"],
        "interference_mm3": chk["interference_mm3"],
        "access": {k: v for k, v in chk["access"].items()}, "declared_process": fit.process_label(d),
        "metal_reference": {"pin_standard": h.pin_standard, "pin_length_mm": d.pin_length_mm,
                            "note": "metal pim ve kitin kendi paketi ayrıdır; bu gösterici onun yerine geçmez"},
    }


# ------------------------------------------------------------------------------------------------ trial record
def template(pred: dict, prefill: dict | None = None) -> str:
    rec = {k: None for k in FIELDS}
    rec.update(schema=SCHEMA, kit_design_sha256=pred["kit_design_sha256"], notes="")
    rec.update({k: v for k, v in (prefill or {}).items() if k in FIELDS and v is not None})
    return json.dumps(rec, indent=1, ensure_ascii=False)


def parse(text: str, pred: dict) -> dict:
    return fit.parse(text, pred, fields=FIELDS, schema=SCHEMA)


def _cad(pred, key):
    v = (pred.get("geometry") or {}).get(key)
    return "–" if v is None else f"{v:.2f}"


def classify(rec: dict, pred: dict, d: PrototypeDesign) -> dict:
    """A printed-pin observation: shown, never applied to a design and never direct evidence for the metal pin."""
    diffs = fit.process_differences(d, rec)
    reasons = ["basılı PLA pim gözlemi: metal pimli montajın boşluğu, sürtünmesi, dayanımı, temas yükleri ve izin "
               "verilen devri için kanıt değildir",
               "görülen temas geometrik bir gözlemdir; nicel açıklık kabulü değildir",
               "basılı pimin eğilmesi ve yüzey pürüzlülüğü hissedilen/ölçülen boşluğu etkiler"]
    if diffs:
        reasons.append("baskı süreci tasarımın bildirdiğinden farklı: " + "; ".join(diffs))
    w = []
    if rec["insertion_fit"] in ("girmez", "sıkı"):
        w.append("Pim mafsal deliklerine zor giriyor: daha küçük pim çeşidini deneyin. Delik metal pim deliğidir; "
                 "delmeyin, büyütmeyin.")
    if not rec["rotation_free"]:
        w.append("Distal serbest dönmüyor: takılan açıyı ve yeri kaydedin (fotoğraf).")
    if not rec["open_stop_seats"]:
        w.append("Açık stop oturmuyor: burun/ped yüzlerini ve destek kalıntısını kontrol edin.")
    if not rec["clip_installs"]:
        w.append("Klips takılamadı: kanal ve klips ağzını ölçüp kaydedin.")
    if not rec["clip_retains"]:
        w.append("Tutma: klips deneme sırasında yerinde kalmadı; çevrim sayısını ve nasıl çıktığını kaydedin.")
    if (rec.get("interference_observed") or "").strip():
        w.append(f"Görülen temas/sürtünme ({rec['interference_observed'].strip()[:200]}): geometrik gözlemdir, "
                 "nicel açıklık kararı değildir.")
    if (rec.get("damage_observed") or "").strip():
        w.append(f"Hasar bildirildi: {rec['damage_observed'].strip()[:200]}")
    a, b = rec["pin_diameter_a_mm"], rec.get("pin_diameter_b_mm")
    if b is not None and abs(a - b) > 0.1:
        w.append(f"Pim ovalliği {abs(a - b):.2f} mm: boşluk hissi yöne bağlıdır.")
    travel = (pred.get("fold") or {}).get("useful_travel_deg")
    if rec.get("folded_stop_deg") is not None and travel is not None and rec["folded_stop_deg"] < travel - 10.0:
        w.append(f"Elle ulaşılan katlanma ({rec['folded_stop_deg']:.0f}°) modeldeki yararlı hareketin ({travel:.0f}°) "
                 "altında: engelin yerini kaydedin.")
    rows = [("Pim çeşidi (CAD) [mm]", rec["pin_variant_mm"]), ("Pim çapı ölçülen [mm]", rec["pin_diameter_a_mm"]),
            ("Pim çapı dik yön [mm]", b), ("Deliğe takılma", rec["insertion_fit"]),
            ("Kafa altı → kanal yakın kenarı [mm] (CAD)",
             f"{rec.get('pin_head_to_groove_near_mm')} ({_cad(pred, 'grip_near_flank_mm')})"),
            ("Uçtan uca eksenel boşluk [mm] (CAD)", f"{rec.get('end_play_total_mm')} ({_cad(pred, 'end_play_total_mm')})"),
            ("Serbest dönüş", rec["rotation_free"]), ("Açık stop oturuyor", rec["open_stop_seats"]),
            ("Elle katlanma [°]", rec.get("folded_stop_deg")), ("Model yararlı hareket [°]", travel),
            ("Klips takıldı / çıktı / yerinde kaldı",
             f"{rec['clip_installs']} / {rec.get('clip_removes')} / {rec['clip_retains']}"),
            ("Çevrim sayısı", rec["cycle_count"]), ("Aşınma", rec.get("wear_observed")),
            ("Boşluk değişimi", rec.get("play_change_observed")), ("Hasar", rec.get("damage_observed")),
            ("Temas/sürtünme", rec.get("interference_observed")), ("Baskı süreci", fit.record_process_label(rec))]
    return {"evidence": EVIDENCE, "label": "basılı pim gözlemi (metal referans değil)", "direct_for_metal": False,
            "reasons": reasons, "process_differences": diffs, "warnings": w,
            "rows": [{"Gözlem": k, "Değer": "" if v is None else str(v)} for k, v in rows],
            "record_sha256": fit.record_sha256(rec)}


# ------------------------------------------------------------------------------------------------------ package
def _tr(x, n=2):
    return f"{x:.{n}f}".replace(".", ",")


def _write_plate(folder, stem, shapes):
    """One geometry 3MF per plate (named objects, print orientation) and one STL per object."""
    b3d = cad._b3d()
    m = b3d.Mesher()
    dims, files = [], []
    for label, s in shapes:
        m.add_shape(s, linear_deflection=0.01, angular_deflection=0.1)
        bb = s.bounding_box()
        dims.append((label, bb.size.X, bb.size.Y, bb.size.Z))
    path = folder / "3mf" / f"{stem}.3mf"
    m.write(str(path))
    del m
    fit._name_3mf_objects(path, [label for label, _ in shapes])
    files.append(path)
    for label, s in shapes:
        stl = folder / "stl" / f"{label}.stl"
        b3d.export_stl(s, str(stl), tolerance=0.01, angular_tolerance=0.1)
        files.append(stl)
    return dims, files


def _shaded(ax, shape, offset, color):
    import matplotlib.colors as mcolors
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    v, f = cad.tessellate(copy.deepcopy(shape), 0.15, 0.4)
    tri = (v + np.asarray(offset))[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    light = np.array([-0.4, -0.5, 0.77]) / np.linalg.norm([-0.4, -0.5, 0.77])
    fc = np.clip(np.array(mcolors.to_rgb(color))[None, :] * (0.35 + 0.65 * np.abs(n @ light))[:, None], 0, 1)
    ax.add_collection3d(Poly3DCollection(tri, facecolors=fc, edgecolors="none"))
    return tri.reshape(-1, 3)


PROX_C, DIST_C, PIN_C, CLIP_C = "#4C78A8", "#E45756", "#555555", "#54A24B"


def _views(demo, chk, folder):
    """Exploded assembly, section through the pivot (the complete stack) and plan views at open/tightest/folded."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from .export import _section_lines
    parts, s, stack = demo["parts"], demo["spec"], demo["stack_mm"]
    d, hw = parts.design, parts.hardware
    px, py = parts.pin_axis
    (p0, p1), (q0, q1) = d.lug_bands_mm
    g = chk["geometry"]
    out = []

    fig = plt.figure(figsize=(8.5, 9.5))
    ax = fig.add_subplot(projection="3d")
    pts = []
    for shape, dz, col, lab in ((hw["pin"], -24.0, PIN_C, "pim (alttan takılır)"),
                                (parts.proximal, 0.0, PROX_C, "proksimal"),
                                (parts.distal, 16.0, DIST_C, "distal (proksimalin üstünde)"),
                                (hw["clip"], 30.0, CLIP_C, "klips (yandan kanala)")):
        p = _shaded(ax, shape, (0.0, 0.0, dz), col)
        pts.append(p)
        bb = shape.bounding_box()
        ax.text(bb.max.X + 3, py, bb.center().Z + dz, lab, fontsize=9)
    allp = np.vstack(pts)
    ax.plot([px, px], [py, py], [allp[:, 2].min() - 3, allp[:, 2].max() + 3], "k-.", lw=0.8)
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(hi - lo)
    ax.view_init(elev=18, azim=-58)
    ax.set_xlabel("x [mm] (veter)"); ax.set_ylabel("y [mm] (açıklık)"); ax.set_zlabel("z [mm] (pim ∥ mil)")
    ax.set_title(f"{d.name} basılı pim gösterici — patlatılmış montaj (pim Ø{max(PIN_DIAMETERS_MM):.2f})", fontsize=11)
    out.append(("gorseller/patlatilmis_montaj.png", fig))

    fig, ax = plt.subplots(figsize=(8.5, 7.5))
    for shape, col, lab, lw in ((parts.proximal, PROX_C, "proksimal", 1.2), (parts.distal, DIST_C, "distal", 1.2),
                                (hw["pin"], PIN_C, f"pim Ø{max(PIN_DIAMETERS_MM):.2f}", 1.6),
                                (hw["clip"], CLIP_C, "klips", 1.6)):
        for k, line in enumerate(_section_lines(shape, px)):
            ax.plot(line[:, 0], line[:, 1], color=col, lw=lw, label=lab if k == 0 else None)
    zh = demo["z_head_mm"]
    g0, g1, _ = _groove_z(stack, s)
    marks = ((p0, "p0: kafa altı / proksimal pul yüzü", "center"), (p1, "p1", "top"), (q0, "q0", "bottom"),
             (q1, "q1: distal pul yüzü", "top"), (zh + g0, "kanal yakın kenarı", "bottom"),
             (zh + g1, "kanal uzak kenarı", "center"))
    for z, lab, va in marks:                       # paired planes 0.15–0.3 mm apart: labels above/below their line
        ax.axhline(z, color="0.6", lw=0.5, ls=":")
        ax.text(py + 7.5, z, f"{lab} ({_tr(z)})", fontsize=7, va=va)
    ax.set_xlim(py - 12, py + 16); ax.set_ylim(zh - 4.5, zh + g["pin_length_mm"] + 2.0); ax.set_aspect("equal")
    ax.set_xlabel("y [mm] (açıklık)"); ax.set_ylabel("z [mm] (pim ekseni ∥ mil)")
    ax.set_title(f"Pim ekseninden kesit (x = {_tr(px)} mm), açık konum", fontsize=11)
    ax.text(0.02, 0.02, f"lug yığını q1 − p0 = {_tr(stack)} mm · kafa altı → kanal yakın kenarı {_tr(g['grip_near_flank_mm'])}, "
            f"uzak kenarı {_tr(g['grip_far_flank_mm'])} mm · pim boyu {_tr(g['pin_length_mm'])} mm · pul yok\n"
            f"uçtan uca eksenel boşluk {_tr(g['end_play_total_mm'])} mm = lug arası {_tr(g['inter_lug_gap_mm'])} (aşağı) + "
            f"klips tarafı payı {_tr(g['clip_side_allowance_mm'])} (yukarı: kalın lug payı {_tr(s.stack_allowance_mm)} + "
            f"klips boşluğu {_tr(s.groove_slack_mm)})",
            transform=ax.transAxes, fontsize=8, va="bottom", bbox=dict(fc="white", ec="0.7"))
    ax.legend(loc="upper left", fontsize=8)
    out.append(("gorseller/pim_kesiti.png", fig))

    def fill(axx, shape, col, alpha, z=1):
        v, f = cad.tessellate(copy.deepcopy(shape), 0.2, 0.5)
        axx.add_collection(PolyCollection(v[f][:, :, :2], facecolor=col, edgecolor=col, alpha=alpha, linewidths=0,
                                          zorder=z, rasterized=True))
        return v
    cf, fold = chk["configurations"], chk["fold"]
    fig, axs = plt.subplots(1, 3, figsize=(16, 6.5))
    gap = _tr(fold["min_gap_mm"]) if fold["min_gap_mm"] is not None else "–"
    titles = {"open": "Açık (θ = 0°, burun pedde)",
              "tightest": f"En dar ara konum (θ = {cf['tightest']:.0f}°, dikey açıklık {gap} mm)",
              "folded": f"Katlı (θ = {cf['folded']:.0f}°; burun {fold['folded_stop_deg']:.0f}°'de proksimale değer)"}
    for axx, key in zip(axs, ("open", "tightest", "folded")):
        vs = [fill(axx, parts.proximal, PROX_C, 0.55), fill(axx, parts.distal_at(cf[key]), DIST_C, 0.55, z=2)]
        fill(axx, hw["clip"], CLIP_C, 0.9, z=3)
        axx.add_patch(plt.Circle((px, py), s.head_diameter_mm / 2, fill=False, color=PIN_C, lw=1.0, zorder=4))
        v = np.vstack(vs)
        axx.set_xlim(v[:, 0].min() - 3, v[:, 0].max() + 3); axx.set_ylim(v[:, 1].min() - 3, v[:, 1].max() + 3)
        axx.set_aspect("equal"); axx.set_title(titles[key], fontsize=10)
        axx.set_xlabel("x [mm] (hücum kenarı −x)")
    axs[0].set_ylabel("y [mm] (açıklık)")
    fig.suptitle(f"{d.name} basılı pim gösterici — plan (+z, itki tarafından); distal dönüş yönünün tersine, geri "
                 f"katlanır (−θ). Elle yararlı hareket {fold['useful_travel_deg']:.0f}° (sütun yöntemi)", fontsize=11)
    out.append(("gorseller/katlanma_konumlari.png", fig))
    paths = []
    for name, f in out:
        f.tight_layout()
        f.savefig(folder / name, dpi=130)
        plt.close(f)
        paths.append(folder / name)
    return paths


def read_3mf(path):
    """[(object name, vertices (n, 3) in plate mm, triangles (m, 3))] of every build item, transforms applied."""
    import xml.etree.ElementTree as ET
    import zipfile
    core = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read(next(n for n in z.namelist() if n.endswith(".model"))))
    objs = {o.get("id"): o for o in root.iter(core + "object")}

    def tf(s):
        if not s:
            return np.eye(3), np.zeros(3)
        v = [float(x) for x in s.split()]
        return np.array(v[:9]).reshape(3, 3), np.array(v[9:12])

    def walk(oid, R, tr):
        o = objs[oid]
        mesh = o.find(core + "mesh")
        if mesh is not None:
            V = np.array([[float(v.get(a)) for a in "xyz"] for v in mesh.iter(core + "vertex")])
            F = np.array([[int(x.get(a)) for a in ("v1", "v2", "v3")] for x in mesh.iter(core + "triangle")])
            yield V @ R + tr, F
        comps = o.find(core + "components")
        for c in ([] if comps is None else comps.findall(core + "component")):
            Rc, tc = tf(c.get("transform"))
            yield from walk(c.get("objectid"), Rc @ R, tc @ R + tr)
    out = []
    for item in root.iter(core + "item"):
        R, tr = tf(item.get("transform"))
        oid = item.get("objectid")
        out += [(objs[oid].get("name") or oid, V, F) for V, F in walk(oid, R, tr)]
    return out


def _color(name):
    return (PIN_C if "_pim_" in name else CLIP_C if "_klips" in name else PROX_C if "proksimal" in name
            else DIST_C if "distal" in name else "#C9A227")


def _scene(ax, meshes):
    """All triangles of a 3D view in ONE collection, so matplotlib depth-sorts faces across parts (one collection
    per part draws whole parts over each other). ``meshes``: [(vertices, triangles, color)]."""
    import matplotlib.colors as mcolors
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    light = np.array([-0.4, -0.5, 0.77]) / np.linalg.norm([-0.4, -0.5, 0.77])
    tris, colors = [], []
    for V, F, color in meshes:
        tri = V[F]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        tris.append(tri)
        colors.append(np.clip(np.array(mcolors.to_rgb(color))[None, :] * (0.35 + 0.65 * np.abs(n @ light))[:, None], 0, 1))
    ax.add_collection3d(Poly3DCollection(np.vstack(tris), facecolors=np.vstack(colors), edgecolors="none"))
    allv = np.vstack([V for V, _, _ in meshes])
    return allv.min(axis=0), allv.max(axis=0)


def _previews(folder, demo, d):
    """CAD previews (not slicer previews): each first-print plate read back from its 3MF (top and shaded views), and
    the assembled joint at the open stop from above and from below."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    paths = []
    for stem, title in (("01A_kucuk_parcalar", "Plaka 01A — kupon, pimler, klipsler (destek yok, brim yok)"),
                        ("01B_mafsal_cifti", "Plaka 01B — mafsal çifti (ağaç destek yalnız tabladan, 3 mm brim)")):
        objs = read_3mf(folder / "3mf" / f"{stem}.3mf")
        allv = np.vstack([V for _, V, _ in objs])
        lo, hi = allv.min(axis=0), allv.max(axis=0)
        fig = plt.figure(figsize=(15, 6.8))
        ax = fig.add_subplot(1, 2, 1)
        for name, V, F in objs:
            ax.add_collection(PolyCollection(V[F][:, :, :2], facecolor=_color(name), edgecolor=_color(name),
                                             alpha=0.75, linewidths=0, rasterized=True))
            c = V.mean(axis=0)
            ax.text(c[0], V[:, 1].max() + 1.2, name.replace("F1S_", ""), ha="center", fontsize=7)
        ax.set_xlim(lo[0] - 6, hi[0] + 6); ax.set_ylim(lo[1] - 6, hi[1] + 8); ax.set_aspect("equal")
        ax.set_xlabel("tabla X [mm]"); ax.set_ylabel("tabla Y [mm]"); ax.grid(True, lw=0.3)
        ax.set_title(f"Üstten (z = 0 tabla düzlemi); en yüksek nesne {hi[2]:.1f} mm", fontsize=10)
        ax3 = fig.add_subplot(1, 2, 2, projection="3d")
        _scene(ax3, [(V, F, _color(name)) for name, V, F in objs])
        ax3.set_xlim(lo[0], hi[0]); ax3.set_ylim(lo[1], hi[1]); ax3.set_zlim(0, max(hi[2], 1.0))
        ax3.set_box_aspect((hi[0] - lo[0], hi[1] - lo[1], max(hi[2], 1.0)))
        ax3.view_init(elev=32, azim=-62)
        ax3.set_xlabel("X"); ax3.set_ylabel("Y"); ax3.set_zlabel("Z")
        fig.suptitle(f"{title}\nCAD önizleme: `3mf/{stem}.3mf` dosyasından okundu — dilimleyici önizlemesi DEĞİL "
                     "(destek, brim ve takım yolları gösterilmez)", fontsize=11)
        paths.append((f"gorseller/onizleme_{stem}.png", fig))
    parts = demo["parts"]
    meshes = []
    for shape, col in ((parts.proximal, PROX_C), (parts.distal, DIST_C), (parts.hardware["pin"], PIN_C),
                       (parts.hardware["clip"], CLIP_C)):
        v, f = cad.tessellate(copy.deepcopy(shape), 0.1, 0.3)
        meshes.append((v, f, col))
    px, py = parts.pin_axis
    fig = plt.figure(figsize=(15, 7.5))
    for k, (elev, azim, sub) in enumerate(((26, -55, "üstten: klips, pim ucu ve distal pul yüzü"),
                                           (-26, -55, "alttan: pim kafası ve proksimal pul yüzü"))):
        ax = fig.add_subplot(1, 2, k + 1, projection="3d")
        lo, hi = _scene(ax, meshes)
        lo = np.array([max(lo[0], px - 16), max(lo[1], py - 16), lo[2]])     # the joint, not the whole stubs
        hi = np.array([min(hi[0], px + 16), min(hi[1], py + 16), hi[2]])
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
        ax.set_box_aspect(hi - lo)
        ax.view_init(elev=elev, azim=azim)
        ax.set_title(sub, fontsize=10)
        ax.set_xlabel("x [mm]"); ax.set_ylabel("y [mm]"); ax.set_zlabel("z [mm]")
    fig.suptitle(f"{d.name} basılı pim gösterici — montajlı mafsal, açık konum (θ = 0°), pim Ø{max(PIN_DIAMETERS_MM):.2f}"
                 "\nCAD önizleme (montaj katıları) — dilimleyici önizlemesi değil", fontsize=11)
    paths.append(("gorseller/onizleme_montaj_acik.png", fig))
    out = []
    for name, f in paths:
        f.tight_layout()
        f.savefig(folder / name, dpi=130)
        plt.close(f)
        out.append(folder / name)
    return out


def export_package(d: PrototypeDesign, folder: Path, demo=None, chk=None) -> dict:
    """Self-contained Turkish operator package: the two first-print plates (3MF, print orientation), STL per part,
    STEP per part (assembly frame, open), views, guides, trial protocol, the forms and the trial record template."""
    import build123d as b3d
    demo = build(d) if demo is None else demo
    chk = check(demo) if chk is None else chk
    folder = Path(folder)
    for sub in ("3mf", "stl", "step", "gorseller"):
        (folder / sub).mkdir(parents=True, exist_ok=True)
    parts, s = demo["parts"], demo["spec"]
    tag = d.name.replace("13in-", "")
    coupon = fit._oriented(cad.hole_coupon(d, fit.COUPON_STEPS_MM), False)
    small = [(f"{tag}_kupon_D{d.connection.pin_diameter_mm:g}+0.0-0.4", coupon)]
    for i, (dia, pin) in enumerate(demo["pins"].items()):
        small.append((f"{tag}_pim_D{dia:.2f}_{i + 1}centik", pin.translate(b3d.Vector(8.0 + 14.0 * i, 24.0, 0.0))))
    for i in range(3):
        small.append((f"{tag}_klips_{i + 1}", demo["clip"].translate(b3d.Vector(8.0 + 14.0 * i, 37.0, 0.0))))
    prox = fit._oriented(parts.proximal, False)
    dist = fit._oriented(parts.distal, True).translate(b3d.Vector(prox.bounding_box().size.X + 12.0, 0.0, 0.0))
    dims_a, files = _write_plate(folder, "01A_kucuk_parcalar", small)
    dims_b, files_b = _write_plate(folder, "01B_mafsal_cifti", [(f"{tag}_gosterici_proksimal", prox),
                                                                (f"{tag}_gosterici_distal", dist)])
    files += files_b
    z_head = demo["z_head_mm"]
    px, py = parts.pin_axis
    assembly = {f"{tag}_gosterici_proksimal": parts.proximal, f"{tag}_gosterici_distal": parts.distal,
                f"{tag}_klips": parts.hardware["clip"],
                **{f"{tag}_pim_D{dia:.2f}": pin.translate(b3d.Vector(px, py, z_head)) for dia, pin in demo["pins"].items()}}
    for name, shape in assembly.items():
        b3d.export_step(shape, str(folder / "step" / f"{name}.step"))
        files.append(folder / "step" / f"{name}.step")
    files += _views(demo, chk, folder)
    files += _previews(folder, demo, d)
    pred = _jsonable(predictions(d, chk, s))
    docs = {"00_ONCE_BENI_OKU.md": _start_doc(d, pred), "BASKI_REHBERI.md": _guide_doc(d, pred, dims_a, dims_b),
            "MONTAJ.md": _assembly_doc(d, pred), "DENEME_PROTOKOLU.md": _protocol_doc(d, pred),
            "BASKI_VE_DENEME_KAYDI.md": _form_doc(d, pred),
            "deneme_kaydi.json": template(pred, fit.declared_prefill(d)),
            "predictions.json": json.dumps(pred, indent=1, ensure_ascii=False), "design.json": to_json(d)}
    for name, text in docs.items():
        (folder / name).write_text(text, encoding="utf-8")
        files.append(folder / name)
    sums = [(hashlib.sha256(p.read_bytes()).hexdigest(), p.relative_to(folder).as_posix()) for p in sorted(files)]
    (folder / "SHA256SUMS").write_text("".join(f"{h}  {n}\n" for h, n in sums), encoding="utf-8")
    return {"predictions": pred, "files": sums, "dims": dims_a + dims_b}


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, (float, np.floating)):
        return float(x) if math.isfinite(x) else None
    if isinstance(x, np.integer):
        return int(x)
    return x


# ---------------------------------------------------------------------------------------------- Turkish documents
def _not_evidence():
    return ("- Bu bir **basılı PLA pim gözlemidir**: metal pimli montajın boşluğu, sürtünmesi, dayanımı, temas yükleri "
            "ve izin verilen devri için kanıt değildir.\n"
            "- Görülen temas **geometrik bir gözlemdir**; nicel açıklık kabulü değildir. Basılı pimin eğilmesi ve yüzey "
            "pürüzlülüğü hissedilen boşluğu etkiler.\n"
            "- Göstericinin onaylı bir motorlu çalışma zarfı **yoktur**; metal pim veya PLA için hesaplanan devir "
            "sınırları buna aktarılmaz. Motorla döndürmeyin.\n"
            "- Metal pime, başka bir tutma yöntemine veya ASA'ya geçiş ilgili ölçümlerin yeniden yapılmasını gerektirir.\n"
            "- Fiziksel yeterlilik: yok.")


def _start_doc(d, pred):
    s = pred["pin_spec"]
    return f"""# {d.name} basılı pim gösterici — önce beni okuyun

Bu paket, metal pim alınmadan önce elle montaj ve katlanma denemesi için **tamamen basılabilir, geçici bir mafsal
göstericisidir**. Bambu Studio'da açılıp dilimlenmedi; geometri ve talimat paketidir. Dilimlemeyi operatör kendi
P1S yapılandırmasıyla yapar. Metal pimli ölçüm paketi ayrı bir pakettir: bu gösterici onun yerine geçmez ve onun
ölçümlerini üretmez.

## İlk baskı: yalnız bu iki dosya

1. `3mf/01A_kucuk_parcalar.3mf`: delik kuponu, üç pim (Ø3,80 / Ø3,90 / Ø4,00 mm; kafa kenarında 1 / 2 / 3 çentik)
   ve üç klips. **Destek yok, brim yok.**
2. `3mf/01B_mafsal_cifti.3mf`: kısa F1S mafsal çifti (proksimal dik, distal ters çevrilmiş). **Ağaç destek yalnız
   tabladan, 3 mm brim.**

İki dosya aynı işte, ayrı plakalarda basılabilir. Başka hiçbir dosya basılmaz. Tam boy kanat baskısı bu kompakt
denemenin parçası değildir; ayrı ve sonraki bir iştir.

## Sonra

Parçalar proje sahibine teslim edilir. Pim seçimi ve montaj `MONTAJ.md`, elle deneme `DENEME_PROTOKOLU.md` ile yapılır.
Gözlemler `deneme_kaydi.json` ve `BASKI_VE_DENEME_KAYDI.md` formuna yazılır.

## Seçilen düzen (kısaca)

Başlı PLA pim, **dik ve kafası tablada** basılır: taşıma yüzeyi yuvarlak çıkar, katman halkaları dönme yönündedir.
Distal lug'ın üstünde, taşıma bölgesinin dışında kalan bir kanala **düz basılan bir PLA klips** yandan takılır. Klips
PLA için boyutlandırıldı ({_tr(s['clip_thickness_mm'], 1)} mm kalınlık, {_tr(s['clip_arm_mm'], 1)} mm kol); metal segmanın
küçültülmüş kopyası değildir. Pul yoktur. Mafsal deliği metal tasarımdaki çaptadır (Ø{_tr(pred['hole_diameter_mm'])} mm):
pim deliğe göre seçilir, delik pime göre değiştirilmez.

## Bu deneme neyi göstermez

{_not_evidence()}

## Dosyalar

| Dosya | İçerik |
|---|---|
| `BASKI_REHBERI.md` | birim, ölçek, yön, beklenen boyutlar, önerilen ayarlar, dilimleme önizlemesi kontrolleri |
| `BASKI_VE_DENEME_KAYDI.md` | önerilen ve **gerçekten kullanılan** ayarlar, doğrulamalar, deneme gözlem formu |
| `MONTAJ.md` | parça listesi, pim seçimi, montaj ve söküm, klips takma/çıkarma |
| `DENEME_PROTOKOLU.md` | elle deneme adımları, çevrimler, fotoğraflar, bu denemeden ne öğrenilir |
| `deneme_kaydi.json` | deneme kaydı (yazıcı, malzeme, filament önceden dolduruldu; etiketle farklıysa düzeltin) |
| `gorseller/` | patlatılmış montaj, pim ekseninden kesit, açık / en dar / katlı konumlar; iki plakanın ve montajın CAD önizlemesi (`onizleme_*.png`, dilimleyici önizlemesi değil) |
| `3mf/`, `stl/` | baskı yönünde geometri (mm, %100 ölçek); `step/`: montaj konumunda CAD (açık) |
| `predictions.json`, `design.json`, `SHA256SUMS` | model değerleri, tasarım kaydı, dosya özetleri |

Paket kimliği `{pred['kit_design_sha256'][:12]}` (tasarım {pred['design_sha256'][:12]}).
"""


def _dims_rows(dims):
    return "\n".join(f"| `{n}` | {_tr(x, 1)} × {_tr(y, 1)} × {_tr(z, 1)} |" for n, x, y, z in dims)


def _guide_doc(d, pred, dims_a, dims_b):
    pm = d.print_model
    return f"""# {d.name} basılı pim gösterici — baskı rehberi

Bu paket **dilimlenmedi**. Aşağıdaki ayarlar **önerilen** ayarlardır. Gerçekten kullanılan ayarları
`BASKI_VE_DENEME_KAYDI.md` formuna yazın.

## Birim, ölçek, yön

- Birim **mm**, ölçek **%100**. Nesneler baskı yönünde ve tablaya (z = 0) oturtulmuş gelir. Döndürmeyin, otomatik
  yönlendirme kullanmayın; yalnız tabla üzerinde yer değiştirebilirsiniz.
- **Pimler dik, kafası tablada.** Yatırmayın: yatık basılan pim yuvarlak çıkmaz ve dönmesi pürüzlü olur.
- **Klipsler düz** (1,6 mm, 8 katman), kupon düz.
- Proksimal lug'ının pul yüzü tablada; distal **ters çevrilmiş** (pul yüzü tablada).

## Plaka 01A: `3mf/01A_kucuk_parcalar.3mf` (destek yok, brim yok)

| Nesne | Boyut X × Y × Z [mm] |
|---|---|
{_dims_rows(dims_a)}

## Plaka 01B: `3mf/01B_mafsal_cifti.3mf` (ağaç destek yalnız tabladan, 3 mm brim)

| Nesne | Boyut X × Y × Z [mm] |
|---|---|
{_dims_rows(dims_b)}

Dilimleyicideki boyutlar bu tablolardan farklıysa ölçek veya birim yanlış içe aktarılmıştır.

## Önerilen ayarlar (P1S, 0,4 mm nozul)

| Ayar | Önerilen | Not |
|---|---|---|
| Nozul | 0,4 mm | takılı nozulu doğrulayın (0,2–0,8 mm mevcut) |
| Tabla | PEI (düz veya dokulu: doğrulayın) | hangisi kullanıldıysa yazın |
| Filament | {pm.filament or "?"} | etiketi doğrulayın; profil adını yazın |
| Katman | {_tr(pm.layer_mm, 2)} mm | |
| Duvar | {pm.wall_loops} döngü | Ø4 pimde neredeyse tamamı duvardır |
| Doluluk | %{pm.infill_fraction * 100:.0f} | |
| X-Y delik / kontur telafisi | 0 / 0 | telafi kullanırsanız değeri yazın |
| Destek | 01A: kapalı. 01B: ağaç, yalnız tabladan | 01B'de ters distalin stop burnunun altına destek beklenir; deliklere, lug yüzlerine ve stop temas yüzlerine destek gelmemeli |
| Brim | 01A: yok. 01B: 3 mm dış brim | |
| Katman soğutması için yavaşlama | açık (varsayılan) | küçük pim katmanlarının soğuması için; üç pim aynı plakada |
| Ütüleme | kapalı | |

## Dilimleme önizlemesinde kontrol (basmadan önce)

1. Boyutlar tablolarla aynı.
2. Pimler dik; pim kanalının üst kenarı (0,4–0,5 mm çıkıntı) **desteksiz** basılıyor; pimlerde destek yok.
3. Klips ağzı açık (köprülenmemiş, dolmamış); klips 8 katman.
4. Kupon ve mafsal deliklerinin çevresinde tam duvar var.
5. 01B'de destek yalnız ters distalin stop burnunun altında; deliklerde ve lug yüzlerinde destek yok.

Önizlemenin ekran görüntüsünü alın ve formda belirtin. Delikleri delmeyin, raybalamayın, zımparalamayın; pimleri
zımparalamayın: parçalar basıldığı gibi denenir.
"""


def _assembly_doc(d, pred):
    g, s = pred["geometry"], pred["pin_spec"]
    tp, td = pred["lug_thicknesses_mm"]
    cl = g["diametral_clearance_cad_mm"]
    return f"""# {d.name} basılı pim gösterici — montaj

## Parçalar

| Parça | Adet | Not |
|---|---|---|
| Proksimal kısa parça | 1 | lug {_tr(tp)} mm, mengene bloğu yok |
| Distal kısa parça | 1 | lug {_tr(td)} mm, yük dili yok; ters basıldı, montajda çevrilir |
| Pim Ø3,80 / Ø3,90 / Ø4,00 | 1 / 1 / 1 | kafa kenarında 1 / 2 / 3 çentik; boy {_tr(g['pin_length_mm'])} mm |
| Klips | 3 | biri kullanılır, ikisi yedek |
| Delik kuponu | 1 | delikler Ø4,0–4,4 mm; pim/delik hatasını ayırmak için |

Mafsal deliği CAD'de Ø{_tr(g['hole_diameter_mm'])} mm (metal tasarımın deliği). CAD çap boşluğu: Ø3,80 →
{_tr(cl['3.80'])}, Ø3,90 → {_tr(cl['3.90'])}, Ø4,00 → {_tr(cl['4.00'])} mm. Basılı deliğin ve pimin gerçek çapı bundan
farklı olabilir.

## Pim seçimi (delik değişmez)

1. Üç pimin taşıma bölgesindeki çapını kumpasla iki dik yönde ölçün.
2. Her pimi kupon deliklerine ve iki mafsal deliğine elle itin: `girmez` / `sıkı` / `akıcı` / `boşluklu`.
3. **İki mafsal deliğinde de `akıcı` olan en büyük pimi kullanın.** Hiçbiri akıcı değilse (hepsi sıkı/girmez)
   delikleri delmeyin veya büyütmeyin: sonucu kaydedin; en küçük pimle `sıkı` olarak deneyin ya da durun. Hepsi
   boşluklu ise Ø4,00'ü kullanın ve kaydedin.

Bu seçim yalnız gösterici içindir; metal pimin delik boşluğu bu sonuca göre seçilmez.

## Montaj (alttan üste)

1. Destek ve brim kalıntısını temizleyin; deliklere, lug yüzlerine, stop burnu ve pedine zımpara yok.
2. Distal parçayı çevirin: pul yüzü yukarı. Proksimalin lug'ı altta, distalinki üstte; delikleri hizalayın.
3. Pimi **alttan**, kafası proksimalin pul yüzüne dayanacak şekilde itin. Kanal distal lug'ın üstünde açıkta kalır.
4. Klipsi ağzı önde, tutma dili size dönük olarak pimin kanalına **yandan** itin; hafif bir tıkla oturur.
5. Distal'i elle açık stopa (burun pede) getirin ve geri katlayın (dönüş yönünün tersine). Yararlı hareket modelde
   ≈ {pred['fold']['useful_travel_deg']:.0f}°'dir; burun ≈ {pred['fold']['folded_stop_deg']:.0f}°'de proksimale değer.

Açı işareti: açık konum θ = 0°. Distal dönüş yönünün tersine geri katlanır; bu yön **negatif θ** ile gösterilir (θ = −103° = 103° katlanma). Kayıtta katlanma açısını pozitif yazın (ör. 140).

## Söküm

Klipsi tutma dilinden tırnakla yandan itip çıkarın; pimi yukarıdan bastırıp alttan çekin. Zorlamayın; kırılan
parçayı kaydedin.

## Yığın (CAD)

Lug yığını q1 − p0 = {_tr(g['stack_mm'])} mm (iki lug + aralarındaki {_tr(g['inter_lug_gap_mm'])} mm). Kanal bu yığının
{_tr(g['groove_start_above_stack_mm'])} mm üstünde başlar (taşıma bölgesinin dışında), genişliği {_tr(g['groove_width_mm'])} mm,
kanal dibi Ø{_tr(g['groove_root_mm'], 1)} mm; klips {_tr(s['clip_thickness_mm'], 1)} mm.

Boy referansları (kafa altından ölçülür):

- **kanalın yakın kenarı: {_tr(g['grip_near_flank_mm'])} mm** — kayıtta ölçülen değer (`pin_head_to_groove_near_mm`);
- kanalın uzak kenarı: {_tr(g['grip_far_flank_mm'])} mm (yakın kenar + klips + klips boşluğu).

Eksenel hareket (açık montaj, proksimal kafaya oturmuş):

- **uçtan uca eksenel boşluk: {_tr(g['end_play_total_mm'])} mm** (CAD katılarından da aynı bulundu);
- bunun **{_tr(g['inter_lug_gap_mm'])} mm**'si nominal lug arası aralıktır: distal proksimale doğru yalnız bu kadar iner
  (metal tasarımın çalışma aralığı);
- **{_tr(g['clip_side_allowance_mm'])} mm**'si tek taraflı, klips tarafı montaj payıdır: distal nominal konumundan bu kadar
  yükselebilir ({_tr(g['thick_lug_allowance_mm'])} mm kalın basılan lug payı + {_tr(g['clip_groove_slack_mm'])} mm klipsin
  kanal içindeki boşluğu).

Basılı lug'lar toplamda {_tr(g['assembles_up_to_extra_stack_mm'])} mm'ye kadar kalın çıksa da klips takılır (bu durumda
uçtan uca boşluk o kadar azalır). Klips tarafındaki pay nedeniyle distal, metal modelden fazla sallanabilir: yüz sınırı
≈ {_tr(g['rocking']['faces_deg'], 1)}° (metal model {_tr(g['rocking']['metal_model_faces_deg'], 1)}°). Metal referans (pim
{d.hardware.pin_standard}, iki pul ve segman) ayrı bir yığındır; bu pim onun boyunu kopyalamaz.

## Kontrol listesi

- [ ] Pim çapları ölçüldü, seçilen pim kayda yazıldı
- [ ] Pim alttan takıldı, klips kanala oturdu
- [ ] Distal açık stopta oturuyor, geri katlanma serbest
- [ ] Görseller (`gorseller/`) ile montaj karşılaştırıldı
"""


def _range(values):
    v = list(values.values())
    return f"{_tr(min(v))} ile {_tr(max(v))}"


def _tightest_text(f, g):
    """The tightest pose: nominal gap and the rocking expectation (both rocking bounds), or only what is known."""
    if f.get("min_gap_mm") is None or f.get("tightest_distance_from_pin_mm") is None:
        return " (bu konumda iki parça üst üste gelmiyor; nominal açıklık tanımsız)."
    text = (f" (nominal dikey açıklık {_tr(f['min_gap_mm'])} mm, pimden {_tr(f['tightest_distance_from_pin_mm'], 0)} mm "
            "uzakta).")
    r, a, b = g["rocking"], f.get("tightest_gap_with_rocking_mm"), f.get("tightest_gap_with_rocking_clip_bearing_mm")
    if a and b:
        text += (f" Distal tam sallandığında model bu konumda temas bekler: ihtiyatlı sınırla (yüz sınırı, "
                 f"{_tr(min(r['worst_deg'].values()), 1)}–{_tr(max(r['worst_deg'].values()), 1)}°) tahmini açıklık "
                 f"{_range(a)} mm; klipste dayanma varsayımıyla ({_tr(min(r['worst_clip_bearing_deg'].values()), 1)}–"
                 f"{_tr(max(r['worst_clip_bearing_deg'].values()), 1)}°) {_range(b)} mm.")
    return text


def _protocol_doc(d, pred):
    f, g = pred["fold"], pred["geometry"]
    return f"""# {d.name} basılı pim gösterici — elle deneme protokolü

Açı işareti: açık konum θ = 0°. Distal dönüş yönünün tersine geri katlanır; bu yön **negatif θ** ile gösterilir (θ = −103° = 103° katlanma). Kayıtta katlanma açısını pozitif yazın (ör. 140).

Motorsuz, elle montaj ve katlanma denemesi. Kuvvet ölçümü bu denemenin parçası **değildir**. Metal kitin yük, eğilme
ve sürtünme protokolü burada kullanılmaz. Ölçülmeyen alanları boş (`null`) bırakın; tahminle doldurmayın.

## Gerekenler

Kumpas (0,01–0,02 mm), sentil takımı (isteğe bağlı), açıölçer, telefon kamerası, kalem.

## Adımlar

1. **Ölçüler.** Üç pimin çapını iki dik yönde ölçün; isterseniz lug kalınlıklarını ve kanal–kafa altı boyunu da
   ölçün. Kullanılan pimi kaydedin (`pin_variant_mm`, `pin_diameter_a_mm`, `pin_diameter_b_mm`). Kafa altından
   kanalın kafaya **yakın** kenarına boyu kumpasın derinlik ucuyla ölçün (`pin_head_to_groove_near_mm`; CAD
   {_tr(g['grip_near_flank_mm'])} mm; uzak kenar CAD {_tr(g['grip_far_flank_mm'])} mm).
2. **Geçme.** Kullanılan pimle kupon deliklerini (`coupon_fit`) ve mafsal deliklerini (`insertion_fit`) değerlendirin.
   Pimin elle çıkıp çıkmadığını yazın (`removal_by_hand`).
3. **Klips.** Takma (`clip_installs`) ve tırnakla çıkarma (`clip_removes`). Deneme boyunca yerinde kalıp kalmadığı
   (`clip_retains`).
4. **Serbest dönüş.** Distal açık stoptan katlı konuma kadar takılmadan dönüyor mu (`rotation_free`)? Takıldığı açıyı
   ve yeri yazın.
5. **Açık stop.** Burun pede oturuyor mu (ışık testi, `open_stop_seats`); sentil varsa aralık (`stop_gap_mm`).
   **Uçtan uca eksenel boşluk** (sentil varsa): distal'i proksimal lug'a bastırın, klipsi kanalın uzak kenarına itin
   ve distal üst yüzü ile klips arasındaki aralığı ölçün (`end_play_total_mm`). CAD: uçtan uca
   {_tr(g['end_play_total_mm'])} mm = nominal lug arası {_tr(g['inter_lug_gap_mm'])} mm + tek taraflı klips tarafı payı
   {_tr(g['clip_side_allowance_mm'])} mm. Bu, metal kitin eksenel boşluk ölçümü değildir.
6. **Katlanma.** Elle ulaşılan katlanma açısı (`folded_stop_deg`). Model: yararlı hareket ≈ {f['useful_travel_deg']:.0f}°,
   en dar ara konum θ ≈ {f['tightest_angle_deg']:.0f}°{_tightest_text(f, g)} Önce distal'i bastırmadan, kendi
   ağırlığıyla katlayın; sonra distal ucunu hafifçe proksimale doğru bastırarak tekrarlayın. Görülen temas veya
   sürtünmeyi, bastırarak mı bastırmadan mı olduğunu belirterek yeriyle yazın (`interference_observed`) ve
   fotoğraflayın. Bu geometrik bir gözlemdir.
7. **Çevrimler.** Açık → katlı → açık bir çevrimdir. Beyan edilen sayıda çevrim yapın (öneri: 10, sonra toplam 50,
   sonra toplam 200) ve her aşamada şunları kontrol edin:
   - aşınma, beyazlama ve toz (`wear_observed`);
   - boşluk değişimi (`play_change_observed`);
   - hasar (`damage_observed`).

   Son toplamı yazın (`cycle_count`).
8. **Fotoğraflar.** Montaj, açık, katlı, temas yerleri ve deneme sonrası pim ile klips; dosya adlarını `photos`
   alanına yazın.

## Bu denemeden ne öğrenilir

- Basılı parçaların bu baskı süreciyle elle takılıp sökülebildiği ve pim seçiminin delik ile pim hatasına göre
  nereye düştüğü.
- Mafsalın elle tam katlanma hareketi (model ≈ {f['useful_travel_deg']:.0f}°), açık stop oturması ve görülen temas
  yerleri (geometrik gözlem).
- Klips tutmasının ve PLA yüzeylerinin beyan edilen çevrim sayısından sonra nasıl değiştiği.

## Bu denemeden ne öğrenilmez

{_not_evidence()}
"""


def _form_doc(d, pred):
    pm = d.print_model
    rows = [("Yazıcı", pm.printer or "(bildirilmedi)"),
            ("Nozul çapı (takılı nozul kontrol edildi mi? evet/hayır)", f"{_tr(pm.nozzle_mm, 1)} mm"),
            ("Tabla: düz / dokulu PEI (kontrol edildi mi? evet/hayır)", "PEI (tipi doğrulanacak)"),
            ("Filament ürünü (etiketle karşılaştırıldı mı? evet/hayır)", pm.filament or "(bildirilmedi)"),
            ("Filament üreticisi / renk / parti (etiket fotoğrafı dosya adı)", "(etiketten yazın)"),
            ("Filament profili (dilimleyicide seçilen)", "(profil adını yazın)"),
            ("Dilimleyici ve sürüm", "(sürümü yazın)"), ("Proje dosyası adı", "(yazın)"),
            ("Katman", f"{_tr(pm.layer_mm, 2)} mm"), ("Duvar döngüsü", str(pm.wall_loops)),
            ("Doluluk", f"%{pm.infill_fraction * 100:.0f}"), ("X-Y delik / kontur telafisi", "0 / 0"),
            ("Destek 01A / 01B", "kapalı / ağaç, yalnız tabladan"), ("Brim 01A / 01B", "yok / 3 mm"),
            ("Pim baskı yönü", "dik, kafa tablada"),
            ("Dilimleme önizlemesi incelendi mi? (ekran görüntüsü dosya adı)", "evet")]
    table = "\n".join(f"| {k} | {v} | |" for k, v in rows)
    obs = ["Kullanılan pim (çentik sayısı / CAD çapı)", "Pim çapı, iki dik yön [mm]", "Diğer pimlerin çapı ve geçmesi",
           "Mafsal deliğine takılma (girmez / sıkı / akıcı / boşluklu)", "Pim elle çıkıyor mu",
           "Kafa altı → kanalın yakın kenarı [mm]", "Uçtan uca eksenel boşluk [mm] (sentil)",
           "Klips takıldı / çıkarıldı / yerinde kaldı", "Serbest dönüş", "Açık stop oturuyor mu; aralık [mm]",
           "Elle katlanma açısı [°]", "Görülen temas/sürtünme (yer, açı)", "Toplam çevrim sayısı",
           "Aşınma / boşluk değişimi / hasar", "Fotoğraf dosya adları"]
    obs_table = "\n".join(f"| {k} | |" for k in obs)
    return f"""# Baskı ve deneme kaydı — {d.name} basılı pim gösterici (paket {pred['kit_design_sha256'][:12]})

## Baskı ayarları

“Önerilen” sütunu yalnız öneridir. “Kullanılan” sütununa gerçekte kullandığınız değeri yazın, aynıysa yine yazın.

| Ayar | Önerilen | Kullanılan |
|---|---|---|
{table}

Önerilenden farklar ve baskı gözlemleri (destek izi, dikiş, çarpılma, yapışma, ağzı dolmuş klips):

-

## Deneme gözlemleri (proje sahibi)

| Gözlem | Değer |
|---|---|
{obs_table}

Değerler `deneme_kaydi.json` dosyasına girilir. Yazıcı, malzeme ailesi ve filament ürünü, proje sahibinin bildirdiği
değerlerle önceden dolduruldu; etikette farklıysa düzeltin. Diğer alanlar boştur; ölçülmeyenler boş kalır. Bu kayıt
**basılı pim gözlemi** olarak saklanır ve metal pimli tasarıma uygulanmaz.
"""
