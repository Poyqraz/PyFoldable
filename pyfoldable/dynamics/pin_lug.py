"""Preliminary analytical checks of a clevis–tang (pin-and-lug) folding connection from a connection-load history.

Load path (pin parallel to the shaft): the distal tang sits between two clevis plates of the proximal part whose
mid-planes are s = t_tang + t_plate + 2*gap apart along the pin. The in-plane force P (axial pull and in-plane
shear) is shared by the two plates; the moments normal to the pin (bending from thrust, torsion) are reacted as a
couple of opposite in-plane plate forces f = (M_n × e_z)/s. Per plate: P/2 ± f. Checks (classical hand
formulas, no stress field):

- pin double shear on the most loaded plane: |P/2 ± f|max / (π d²/4);
- pin bending with the clevis–tang arm a = t_plate/2 + gap + t_tang/4: 32 |P/2 ± f|max a / (π d³);
- plate bearing: |P/2 ± f|max / (d t_plate);
- tang edge bearing, since the tang passes M_n into the pin across its thickness:
  |P| / (d t_tang) + 6 hypot(M_s, M_t) / (d t_tang²);
- tang net section (width w given): max(N, 0) / ((w - d) t_tang) + 6 |M_t| / ((w - d) t_tang²);
- tang shear-out (edge e given): max(N, 0) / (2 (e - d/2) t_tang).

The force along the pin is carried by the pin head/collar and plate faces and is reported, not checked; the
moment about the pin is carried by the hinge elements (spring, stops, latch), not by the pin. Allowables without
a source give no margin or verdict (status 'girdi gerekli (kaynak)').

These are preliminary estimates for comparing options. They are not a stress analysis, ignore stress
concentration, fits, fatigue and the printed material's anisotropy, and do not qualify a part.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class PinLugGeometry:
    pin_diameter_m: float
    tang_thickness_m: float
    plate_thickness_m: float
    gap_m: float = 0.0
    tang_width_m: float | None = None          # across the hole, for net-section tension
    tang_edge_m: float | None = None           # pin centre to the tang end loaded by the pull, for shear-out

    def __post_init__(self):
        for k, v in asdict(self).items():
            if v is None:
                continue
            if not (isinstance(v, (int, float)) and math.isfinite(v)) or v < 0 or (v == 0 and k != "gap_m"):
                raise ValueError(f"{k} must be a positive finite length.")
        if self.tang_width_m is not None and self.tang_width_m <= self.pin_diameter_m:
            raise ValueError("The tang must be wider than the pin hole.")
        if self.tang_edge_m is not None and self.tang_edge_m <= self.pin_diameter_m / 2:
            raise ValueError("The edge distance must exceed the hole radius.")

    @property
    def plate_spacing_m(self):
        return self.tang_thickness_m + self.plate_thickness_m + 2.0 * self.gap_m


@dataclass(frozen=True)
class Allowables:
    """Allowable stresses [Pa] entered by the user (material data with its source); None: check unavailable."""
    pin_shear_pa: float | None = None
    pin_bending_pa: float | None = None
    tang_bearing_pa: float | None = None
    plate_bearing_pa: float | None = None
    tang_tension_pa: float | None = None
    tang_shear_pa: float | None = None
    source: str = ""


def plate_forces(loads):
    """Per-plate in-plane force magnitudes [N] (upper, lower) from hinge-local components (arrays)."""
    N, Vt = np.asarray(loads["N_tension"]), np.asarray(loads["V_inplane"])
    Ms, Mt = np.asarray(loads["M_torsion"]), np.asarray(loads["M_bending"])
    return N, Vt, Ms, Mt


def connection_checks(loads: dict, geom: PinLugGeometry, allow: Allowables, time_s=None) -> dict:
    """Stress histories and peak margins. ``loads``: hinge-local components about the tang mid-plane
    (N_tension, V_inplane, V_axial, M_torsion, M_bending) as arrays."""
    N, Vt, Ms, Mt = plate_forces(loads)
    s = geom.plate_spacing_m
    # in (e_s, e_t): force on the distal tang P = (-N, Vt); couple f = (M_n × e_z)/s = (M_t, -M_s)/s
    P = np.stack([-N, Vt], -1)
    f = np.stack([Mt, -Ms], -1) / s
    up, lo = np.linalg.norm(P / 2 + f, axis=-1), np.linalg.norm(P / 2 - f, axis=-1)
    plate = np.maximum(up, lo)
    d, tt, tp = geom.pin_diameter_m, geom.tang_thickness_m, geom.plate_thickness_m
    area = math.pi * d * d / 4.0
    stresses = {
        "pin_shear": (plate / area, allow.pin_shear_pa, "Pim kesmesi (çift kesme, en yüklü düzlem)"),
        "pin_bending": (32.0 * plate * (tp / 2 + geom.gap_m + tt / 4) / (math.pi * d ** 3), allow.pin_bending_pa,
                        "Pim eğilmesi (çatal–dil kolu)"),
        # the tang hands the plate couple into the pin as linearly varying bearing across its thickness
        "tang_bearing": (np.linalg.norm(P, axis=-1) / (d * tt) + 6.0 * np.hypot(Ms, Mt) / (d * tt * tt),
                         allow.tang_bearing_pa, "Dil yatak basıncı (kenar)"),
        "plate_bearing": (plate / (d * tp), allow.plate_bearing_pa, "Çatal plakası yatak basıncı"),
    }
    pull = np.maximum(N, 0.0)
    if geom.tang_width_m is not None:
        wn = geom.tang_width_m - d
        stresses["tang_tension"] = (pull / (wn * tt) + 6.0 * np.abs(Mt) / (wn * tt * tt), allow.tang_tension_pa,
                                    "Dil net kesit çekmesi + eğilme")
    if geom.tang_edge_m is not None:
        stresses["tang_shear_out"] = (pull / (2.0 * (geom.tang_edge_m - d / 2) * tt), allow.tang_shear_pa,
                                      "Dil kenar yırtılması (shear-out)")
    t = None if time_s is None else np.asarray(time_s)
    source = (allow.source or "").strip()
    rows = []
    for key, (sig, allowable, label) in stresses.items():
        j = int(np.argmax(sig))
        verdict = bool(allowable) and bool(source)     # an unsourced allowable gives no margin or verdict
        rows.append({"key": key, "label": label, "peak_pa": float(sig[j]),
                     "time_s": None if t is None else float(t[j]), "allowable_pa": allowable,
                     "margin": float(allowable / max(sig[j], 1e-30) - 1.0) if verdict else None,
                     "status": ("girdi gerekli" if not allowable else "girdi gerekli (kaynak)" if not source
                                else "yeterli" if sig[j] <= allowable else "yetersiz")})
    missing = [k for k, v in (("tang_width_m", geom.tang_width_m), ("tang_edge_m", geom.tang_edge_m)) if v is None]
    return {"rows": rows, "allowable_source": source, "plate_force_n": plate.tolist(), "plate_spacing_m": s,
            "pin_axial_force_n": np.asarray(loads.get("V_axial", np.zeros_like(N))).tolist(),
            "unavailable_checks": missing,
            "scope": ("Ön analitik tahmin: el formülleri, gerilme yığılması, geçme, yorulma ve baskı malzemesinin "
                      "anizotropisi yok. Gerilme alanı çözülmedi; parça niteliklendirmesi değildir.")}
