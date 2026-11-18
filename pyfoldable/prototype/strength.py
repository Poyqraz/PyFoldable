"""Analytical checks of the single-lug-per-segment joint (one pin, two stacked lugs: single shear, eccentric path).

Not the clevis–tang (double-shear) formulas of ``dynamics/pin_lug.py``. Load path: the distal lug (mid-plane z_d)
hands the in-plane pin force P to the proximal lug (mid-plane z_p) across one shear plane; the lines of action are
a = (t_p + t_d)/2 + g apart, and the joint also carries the in-plane couple M from the equilibrium (offset
centrifugal force, stop force, thrust). Assumptions (stated, conservative, no stress field):

- pin single shear: P / (π d²/4);
- pin bending: each lug clamps the pin over its thickness, inflection at the gap: M_pin = P a / 2, σ = 32 M_pin/(π d³);
- lug edge bearing (each lug passes P plus half the joint couple into the pin across its thickness, as the
  existing tang check): P/(d t) + 6 (M/2)/(d t²);
- lug net section across the hole (w = 2 R_b): P/((w − d_h) t) + 6 (M/2)/((w − d_h) t²); no stress concentration
  (see ``lug_fea`` for the in-plane peak);
- lug shear-out toward the free edge: P / (2 (R_b − d_h/2) t);
- stop seat pressure: F_stop / (nose width × lug-band height); nose root bending: the nose is a cantilever from the
  distal root down to the seat centroid.

Printed allowables are exploratory (``design.MATERIALS``); margins use the safety factor and in-plane (XY) values
because the parts print with the rotor plane on the bed. Every centrifugal stress scales with Ω², so each check
also reports the speed at which it reaches allowable/SF. Preliminary estimates for comparing candidates; they do not
qualify a part.
"""
from __future__ import annotations

import math

from functools import lru_cache

from .design import MATERIALS, MATERIAL_SOURCE, STEEL, STEEL_SOURCE


@lru_cache(maxsize=64)
def _fe_peak_per_newton(boss_radius, hole_radius, thickness, modulus, poisson):
    """In-plane peak principal stress per newton of pin load (plane-stress Q9 FE, ``lug_fea``; linear in the load)."""
    from .lug_fea import lug_stress
    return lug_stress(boss_radius, hole_radius, thickness, 2.0 * boss_radius, 1.0, E=modulus, nu=poisson,
                      level=2)["peak_max_principal_mpa"]


def checks(load: dict, d, meta) -> list[dict]:
    c, pm = d.connection, d.print_model
    mat = MATERIALS[pm.material]
    P = load["pin_force_inplane_n"]
    M = load["pin_couple_inplane_nmm"]
    dp, dh, Rb = c.pin_diameter_mm, d.hole_diameter_mm, c.boss_radius_mm
    tp, td = d.lug_thicknesses_mm
    a = d.lug_midplane_offset_mm
    x0, x1 = meta["stop_x_mm"]
    z0, z1 = meta["stop_z_mm"]
    nose_w, seat_h = x1 - x0, z1 - z0
    nose_lever = meta["nose_z_mm"][1] - 0.5 * (z0 + z1)        # seat centroid to the nose root (distal underside)
    f_stop = load["stop_force_n"]
    rows = [
        ("pin_shear", "Pim tek kesme", P / (math.pi * dp * dp / 4), STEEL["shear_mpa"], STEEL_SOURCE),
        ("pin_bending", "Pim eğilmesi (P·a/2)", 32 * (P * a / 2) / (math.pi * dp ** 3), STEEL["bending_mpa"], STEEL_SOURCE),
    ]
    for name, t in (("proksimal", tp), ("distal", td)):
        rows += [
            (f"bearing_{name}", f"Yatak basıncı ({name} lug)", P / (dh * t) + 6 * (M / 2) / (dh * t * t),
             mat["bearing_mpa"], MATERIAL_SOURCE),
            (f"net_{name}", f"Net kesit çekme+eğilme ({name} lug)",
             P / ((2 * Rb - dh) * t) + 6 * (M / 2) / ((2 * Rb - dh) * t * t), mat["tensile_xy_mpa"], MATERIAL_SOURCE),
            (f"shear_out_{name}", f"Kenar yırtılması ({name} lug)", P / (2 * (Rb - dh / 2) * t), mat["shear_mpa"],
             MATERIAL_SOURCE),
            (f"fe_peak_{name}", f"FE düzlem-içi tepe gerilme, delik kenarı ({name} lug; eğilme hariç)",
             P * _fe_peak_per_newton(Rb, dh / 2, t, mat["modulus_mpa"], mat["poisson"]), mat["tensile_xy_mpa"],
             MATERIAL_SOURCE),
        ]
    rows += [
        ("stop_seat", "Stop yüzeyi basıncı", max(f_stop, 0.0) / (nose_w * seat_h), mat["compressive_mpa"], MATERIAL_SOURCE),
        ("stop_nose_root", "Stop burnu kök eğilmesi", 6 * max(f_stop, 0.0) * nose_lever / (nose_w * c.nose_depth_mm ** 2),
         mat["tensile_xy_mpa"], MATERIAL_SOURCE),
    ]
    sf = d.operating.safety_factor
    out = []
    for key, label, sigma, allow, source in rows:
        limit = None
        if sigma > 0 and not load["aero_included"]:
            limit = load["rpm"] * math.sqrt(allow / (sf * sigma))
        out.append({"key": key, "label": label, "stress_mpa": sigma, "allowable_mpa": allow,
                    "margin": allow / (sf * sigma) - 1.0 if sigma > 0 else None,
                    "rpm_limit": limit, "source": source})
    return out


def governing(rows):
    lim = [r for r in rows if r["rpm_limit"] is not None]
    return min(lim, key=lambda r: r["rpm_limit"]) if lim else None


SCOPE = ("Ön analitik tahmin: tek lug/tek kesme el formülleri, keşif malzeme değerleri ve güvenlik katsayısı; "
         "gerilme yığılması (düzlem içi FE ayrı), temas, sürtünme, yorulma ve baskı anizotropisi yok. "
         "Parça niteliklendirmesi değildir.")
