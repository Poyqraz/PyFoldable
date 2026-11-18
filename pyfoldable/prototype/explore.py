"""Bounded design exploration around the connection and blade parameters.

Stage 1 (geometry, every candidate): build the solids, full-travel clearance (nominal and with worst-case joint play),
printability and deployed alignment, mass. Candidates that cannot be built, do not clear the required travel or fail
a printability check are kept with their reasons. Stage 2 (eligible only): steady deployed loads at the reference
speed and the single-lug strength checks (speed limit at the safety factor). The result is a table of alternatives
with their trade-offs, not one optimum. Grid size is capped (``MAX_CANDIDATES``); planform axes rebuild the stations
from the research template exactly as the research workflow does.
"""
from __future__ import annotations

import itertools
import math
import time
from dataclasses import replace

from . import cad, checks, loads, mass, strength
from .design import PIN_SETS, hardware_for_pin, planform_from_template, validate, with_changes, without_measurement

MAX_CANDIDATES = 24
PLANFORM_AXES = ("planform.twist_scale", "planform.chord_scale", "planform.profile_id", "planform.hinge_zone_mm",
                 "planform.hinge_zone_outboard_mm", "planform.hinge_chord_factor", "planform.hinge_twist_factor")
REFERENCE_RPM = 6000.0


def candidate_design(base, root, params: dict):
    plan = {k.split(".", 1)[1]: v for k, v in params.items() if k in PLANFORM_AXES}
    rest = {k: v for k, v in params.items() if k not in PLANFORM_AXES}
    d = with_changes(base, **rest) if rest else base
    p = base.planform
    if plan or (p.hinge_zone_mm > 0 and d.connection.hinge_radius_mm != base.connection.hinge_radius_mm):
        kw = dict(diameter_mm=p.diameter_mm, chord_scale=p.chord_scale, twist_scale=p.twist_scale,
                  profile_id=p.profile_id, template_id=p.template_id, hinge_zone_mm=p.hinge_zone_mm,
                  hinge_chord_factor=p.hinge_chord_factor, hinge_twist_factor=p.hinge_twist_factor,
                  hinge_zone_outboard_mm=p.hinge_zone_outboard_mm)
        kw.update(plan)
        kw["hinge_zone_center_mm"] = d.connection.hinge_radius_mm         # the zone follows the joint
        d = replace(d, planform=planform_from_template(root, **kw))
    pin = d.connection.pin_diameter_mm
    if pin != d.hardware.pin_nominal_mm and any(abs(pin - k) < 1e-9 for k in PIN_SETS):
        d = replace(d, hardware=hardware_for_pin(pin))                    # the pin set follows the pin
    if params and d.connection.play_record_sha256 is not None:            # play was measured on the base geometry only
        d = without_measurement(d)
    return d


def evaluate(d, rpm=None) -> dict:
    """All checks of one candidate (raises nothing: failures become reasons)."""
    t0 = time.time()
    out = {"design": d, "reasons": [], "eligible": False}
    errs = validate(d)
    if errs:
        out["reasons"] += errs
        return out
    try:
        parts = cad.build(d)
    except Exception as exc:                                  # a geometric conflict is a result, not a crash
        out["reasons"].append(f"Geometri kurulamadı: {exc}")
        return out
    out["parts"] = parts
    try:
        _checks(out, d, parts, rpm)
    except Exception as exc:                                  # any later failure is a reason, never a success
        out["eligible"] = False
        out["reasons"].append(f"Kontrol tamamlanamadı: {type(exc).__name__}: {exc}")
    out["seconds"] = round(time.time() - t0, 1)
    return out


def _checks(out, d, parts, rpm):
    from .export import PRINTABLE, build_outputs
    sw = checks.sweep(parts)
    out["sweep"] = sw
    out["alignment"] = checks.alignment(d, parts)
    mp = mass.properties(parts)
    out["mass"] = mp
    out["outputs"] = build_outputs(parts)
    out["printability"] = checks.printability(d, {k: out["outputs"][k] for k in PRINTABLE})
    out["reasons"] += [f"Basılabilirlik: {r['check']} ({r['value']}; {r['note']})" for r in out["printability"] if not r["ok"]]
    need = -d.connection.stowed_angle_deg
    if not sw["body_clear"]:
        g = sw["min_gap_mm"]
        what = (f"en büyük girişim {-g:.1f} mm" if g < 0 else
                f"en küçük boşluk {g:.2f} mm < gerekli {d.connection.body_clearance_mm:.2f} mm")
        out["reasons"].append(
            f"Gövdeler {sw['body_clear_to_deg']:.0f}°'den sonra yeterli boşluk bırakmıyor ({need:.0f}° gerekli); {what} "
            f"@ {sw['min_gap_angle_deg']:.0f}°; gereken ofset ≈ {sw['required_offset_mm']:.1f} mm")
    if sw["folded_stop_deg"] is not None and sw["folded_stop_deg"] < need:
        out["reasons"].append(
            f"Stop burnu {sw['folded_stop_deg']:.0f}°'de proksimale değiyor (katlanmış stop; {need:.0f}° gerekli): "
            "burun derinliğini azaltın/öne alın veya gerekli açıyı düşürün")
    if sw["full_travel_clear"] and not sw["full_travel_clear_with_play"]:
        out["reasons"].append(f"Nominal açık, en kötü boşlukla girişim {-sw['min_gap_play_mm']:.1f} mm "
                              f"@ {sw['min_gap_play_angle_deg']:.0f}° (gereken ofset ≈ {sw['required_offset_with_play_mm']:.1f} mm)")
    ref = rpm or d.operating.max_rpm or REFERENCE_RPM
    out["loads"] = loads.deployed(mp["distal"], d, parts.meta, ref)            # centrifugal only: scales with Ω²
    if not out["loads"]["seated"]:                                            # sign of M_z = Ω² m (r_j x_cg − x_p y_cg)
        out["reasons"].append("Merkezkaç momenti distali açık stopa oturtmuyor (ağırlık merkezi pimden geçen "
                              "radyal çizginin önünde).")
    out["eligible"] = not out["reasons"]
    out["strength"] = strength.checks(out["loads"], d, parts.meta)
    gov = strength.governing(out["strength"])
    out["governing"] = None if gov is None else {"key": gov["key"], "label": gov["label"], "rpm_limit": gov["rpm_limit"]}
    owner = loads.owner_case(mp["distal"], d, parts.meta)                     # with the owner's aero forces, if any
    if owner is not None:
        out["owner_loads"] = owner
        out["owner_strength"] = strength.checks(owner, d, parts.meta)
        if not owner["seated"]:
            out["eligible"] = False
            out["reasons"].append(f"Azami devirde ({owner['rpm']:.0f}) distal açık stoptan ayrılıyor "
                                  "(aerodinamik geri moment merkezkaç momentinden büyük).")


def summary_row(r: dict, params: dict) -> dict:
    d = r["design"]
    row = {**{k.split(".")[-1]: v for k, v in params.items()}, "uygun": r["eligible"],
           "gerekçe": " · ".join(r["reasons"]) or "—"}
    if "sweep" in r:
        sw, mp = r["sweep"], r["mass"]
        row.update({
            "açık katlanma [°]": round(sw["clear_travel_deg"]),
            "en küçük boşluk [mm]": round(sw["min_gap_mm"], 2),
            "boşluk, oynama ile [mm]": round(sw["min_gap_play_mm"], 2),
            "gereken ofset [mm]": round(sw["required_offset_mm"], 1),
            "basamak [mm]": d.connection.axial_offset_mm,
            "distal [g]": round(mp["distal"].mass_g, 2),
            "kanat [g]": round(mp["blade"].mass_g, 1),
            "stop momenti @ref [N·mm]": round(r["loads"]["deploy_moment_nmm"]),
            "pim kuvveti @ref [N]": round(r["loads"]["pin_force_inplane_n"]),
            "dayanım sınırı [RPM]": None if not r.get("governing") else round(r["governing"]["rpm_limit"]),
            "belirleyici": None if not r.get("governing") else r["governing"]["label"],
        })
    return row


def run(base, root, axes: dict, rpm=None, progress=None) -> dict:
    """Cartesian grid over ``axes`` ({'connection.axial_offset_mm': [5, 5.5, 6], ...}), capped at MAX_CANDIDATES."""
    keys = list(axes)
    grid = [dict(zip(keys, v)) for v in itertools.product(*(axes[k] for k in keys))]
    if len(grid) > MAX_CANDIDATES:
        raise ValueError(f"{len(grid)} aday > üst sınır {MAX_CANDIDATES}; eksenleri daraltın.")
    rows, results = [], []
    for i, params in enumerate(grid):
        if progress:
            progress(i, len(grid), params)
        r = evaluate(candidate_design(base, root, params), rpm)
        results.append((params, r))
        rows.append(summary_row(r, params))
    return {"axes": axes, "rows": rows, "results": results, "alternatives": alternatives(results),
            "reference_rpm": rpm or base.operating.max_rpm or REFERENCE_RPM}


def alternatives(results):
    """A small set of distinct useful candidates among the eligible ones (not a single optimum)."""
    ok = [(p, r) for p, r in results if r["eligible"] and r.get("governing")]
    if not ok:
        return []
    picks = {
        "En küçük basamak (hizalama)": min(ok, key=lambda pr: (abs(pr[1]["design"].connection.axial_offset_mm),
                                                              -pr[1]["governing"]["rpm_limit"])),
        "En yüksek dayanım sınırı": max(ok, key=lambda pr: pr[1]["governing"]["rpm_limit"]),
        "En hafif kanat": min(ok, key=lambda pr: pr[1]["mass"]["blade"].mass_g),
    }
    out, seen = [], set()
    for label, (p, r) in picks.items():
        key = r["design"].identity
        out.append({"label": label, "params": p, "identity": key[:12], "duplicate": key in seen})
        seen.add(key)
    return out


def default_axes(base):
    """The owner's 5–6 mm target, the template twist and two flatter planforms (lower pitch)."""
    return {"connection.axial_offset_mm": [5.0, 5.5, 6.0], "planform.twist_scale": [1.0, 0.6, 0.35]}


def required_offset_table(base, root, twist_scales=(1.0, 0.8, 0.6, 0.45, 0.35, 0.25)):
    """For each planform: offset needed to clear the full travel (re-checked at that offset)."""
    out = []
    for ts in twist_scales:
        d = candidate_design(base, root, {"planform.twist_scale": ts})
        r1 = evaluate(d)
        if "sweep" not in r1:
            out.append({"twist_scale": ts, "error": r1["reasons"]})
            continue
        need = math.ceil(r1["sweep"]["required_offset_mm"] * 2) / 2      # round up to 0.5 mm
        r2 = evaluate(with_changes(d, **{"connection.axial_offset_mm": need}))
        out.append({"twist_scale": ts, "offset_tried_mm": d.connection.axial_offset_mm,
                    "clear_travel_at_tried_deg": r1["sweep"]["clear_travel_deg"],
                    "required_offset_mm": r1["sweep"]["required_offset_mm"], "offset_rechecked_mm": need,
                    "body_clear_at_recheck": r2.get("sweep", {}).get("body_clear"),
                    "folded_stop_deg": r2.get("sweep", {}).get("folded_stop_deg"),
                    "min_gap_at_recheck_mm": r2.get("sweep", {}).get("min_gap_mm"),
                    "required_with_play_mm": r2.get("sweep", {}).get("required_offset_with_play_mm")})
    return out
