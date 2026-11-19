"""Where the required axial offset comes from, and the deployed alignment and folded envelope of a candidate.

Offset budget (checked against the full-travel CAD sweep, ``docs/prototype_13in.md``): for a backward fold beyond
about 110° with the pin near the quarter chord, the governing contact is the distal trailing-edge root passing over the
proximal leading-edge region about one chord inboard of the pin. The lowest edge of the upper body crosses the highest
edge of the lower body, so the whole vertical extent of the hinge-zone sections must be cleared:

    δ_req ≈ H_j + c_b + r          H_j = vertical extent of the joint section ≈ c_j sin β_j + t_j cos β_j

with the required body clearance c_b and a residual r (the proximal section one chord inboard is taller). Split:

- mechanism floor t_j + c_b (+ joint play): what this topology needs even with a flat blade;
- blade term c_j sin β_j + r: set by the chord and pitch of the sections near the joint (the template's contribution).

The pin's chordwise position barely changes this (the crossing happens for any pin ahead of mid-chord), and moving it
aft removes the centrifugal seating; the study probes in the report record both.

The data functions return plain arrays (mm) so the report (matplotlib PNG) and the app (plotly) draw the same geometry.
"""
from __future__ import annotations

import math

import numpy as np

from . import cad

IN_TO_MM = 25.4


def offset_budget(d, sweep) -> dict:
    rj = d.connection.hinge_radius_mm
    chord, twist = d.section(rj)
    z = cad.section_points(d, rj)[:, 2]
    prof = cad.printable_profile(d, chord)
    n = len(prof) // 2
    thick = float((np.interp(np.linspace(0.02, 0.98, 97), *prof[:n + 1][::-1].T)
                   - np.interp(np.linspace(0.02, 0.98, 97), *prof[n:].T)).max() * chord)
    H = float(np.ptp(z))
    cb = d.connection.body_clearance_mm
    est = required_by_travel(d, sweep, (-d.connection.stowed_angle_deg,))[0]
    req, req_p = est["required_mm"], est["required_with_play_mm"]
    floor = thick * math.cos(math.radians(twist)) + cb
    return {
        "required_mm": req, "required_with_play_mm": req_p, "play_mm": req_p - req,
        "section_height_mm": H, "projected_chord_mm": chord * math.sin(math.radians(twist)),
        "thickness_mm": thick, "clearance_mm": cb, "residual_mm": req - H - cb,
        "mechanism_floor_mm": floor, "mechanism_floor_with_play_mm": floor + req_p - req,
        "blade_term_mm": req - floor, "chord_mm": chord, "twist_deg": twist,
        "pitch_at_joint_in": 2 * math.pi * rj * math.tan(math.radians(twist)) / IN_TO_MM,
        "pitch_075R_in": pitch_in(d, 0.75),
    }


def pitch_in(d, r_over_R):
    r = r_over_R * d.planform.tip_radius_mm
    return 2 * math.pi * r * math.tan(math.radians(d.section(r)[1])) / IN_TO_MM


def required_by_travel(d, sweep, travels=range(10, 181, 10)) -> list[dict]:
    """Offset that would clear each required travel, estimated from the gaps at the current offset (the vertical gap
    moves one-to-one with δ outside the joint ring). Not clipped at δ, so a margin shows as a smaller value. With play:
    both criteria (nominal gap ≥ body clearance, worst-case gap with the design's play ≥ 0)."""
    a = -np.array(sweep["angles_deg"])
    g, gp = np.array(sweep["gap_mm"]), np.array(sweep["gap_play_mm"])
    need, delta = d.connection.body_clearance_mm, d.connection.axial_offset_mm
    out = []
    for T in travels:
        sel = a <= T + 1e-9
        if not sel.any():
            continue
        gmin, gpmin = float(g[sel].min()), float(gp[sel].min())
        if not (math.isfinite(gmin) and math.isfinite(gpmin)):       # no overlap up to this travel: nothing to clear
            out.append({"travel_deg": int(round(T)), "required_mm": None, "required_with_play_mm": None})
            continue
        nominal = delta + need - gmin
        out.append({"travel_deg": int(round(T)), "required_mm": nominal, "required_with_play_mm": max(nominal, delta - gpmin)})
    return out


def outline(d, segment: str, n=40) -> np.ndarray:
    """Plan outline (x, y) of a segment's aerodynamic body: leading edge out, trailing edge back."""
    c = d.connection
    r0, r1 = ((d.hub_radius_mm, c.hinge_radius_mm) if segment == "proximal"
              else (c.hinge_radius_mm + c.face_gap_mm, d.planform.tip_radius_mm))
    le, te = [], []
    for r in np.linspace(r0, r1, n):
        x = cad.section_points(d, float(r), n_side=24)[:, 0]
        le.append((x.min(), r))
        te.append((x.max(), r))
    return np.array(le + te[::-1] + le[:1])


def rotate(points, pivot, deg):
    t = math.radians(deg)
    p = np.asarray(points, float) - pivot
    return np.column_stack([p[:, 0] * math.cos(t) - p[:, 1] * math.sin(t),
                            p[:, 0] * math.sin(t) + p[:, 1] * math.cos(t)]) + pivot


def envelope(d, sweep) -> dict:
    """Deployed and folded plan outlines, folded radius and the governing contact point."""
    c = d.connection
    pivot = np.array([c.pin_x_mm, c.hinge_radius_mm])
    prox, dist = outline(d, "proximal"), outline(d, "distal")
    fold = -min(sweep["clear_travel_deg"], -c.stowed_angle_deg)
    folded = rotate(dist, pivot, fold)
    a = np.array(sweep["angles_deg"])
    k = int(np.argmin(np.abs(a - sweep["min_gap_angle_deg"])))
    radius = float(max(np.hypot(*prox.T).max(), np.hypot(*folded.T).max()))
    return {"proximal": prox, "distal": dist, "folded": folded, "fold_deg": fold, "pivot": pivot,
            "folded_radius_mm": radius, "deployed_radius_mm": d.planform.tip_radius_mm,
            "critical": sweep["where"][k], "critical_angle_deg": float(a[k])}


def folded_dimensions(d, sweep, angles=(0, 60, 90, 110, 140, 160, 180)) -> list[dict]:
    """Folded rotor size per fold angle (all blades, aerodynamic outlines; the stop nose adds about 2 mm ahead of the
    leading edge at the joint): envelope diameter about the shaft, length along the blade axis and width across it,
    with the offset each fold needs (from ``required_by_travel``) and whether the folded stop allows it. Length is
    along blade 1's axis, which is the blade axis for two blades."""
    c = d.connection
    pivot = np.array([c.pin_x_mm, c.hinge_radius_mm])
    prox, dist = outline(d, "proximal"), outline(d, "distal")
    n = d.planform.blade_count
    stop = sweep.get("folded_stop_deg")
    out = []
    for a in angles:
        blade = np.vstack([prox, rotate(dist, pivot, -a)])
        pts = np.vstack([rotate(blade, np.zeros(2), 360.0 * k / n) for k in range(n)])
        need = required_by_travel(d, sweep, (max(a, 2),))[0] if a > 0 else None
        out.append({"fold_deg": int(a), "reachable": bool(stop is None or a < stop),   # the nose touches at the stop
                    "envelope_diameter_mm": float(2.0 * np.hypot(*pts.T).max()),
                    "length_mm": float(np.ptp(pts[:, 1])), "width_mm": float(np.ptp(pts[:, 0])),
                    "required_offset_mm": None if need is None else need["required_mm"],
                    "required_offset_with_play_mm": None if need is None else need["required_with_play_mm"]})
    return out


def alignment_sections(d) -> dict:
    """Deployed joint seen from the tip: proximal end section (z = 0) and distal root section (z = δ), lug bands,
    pin set, all in (x, z) mm."""
    c, h = d.connection, d.hardware
    (p0, p1), (q0, q1) = d.lug_bands_mm
    px = c.pin_x_mm
    zw0 = p0 - h.washer_thickness_mm
    zt = q1 + h.washer_thickness_mm + h.clip_thickness_mm
    return {"proximal": cad.section_points(d, c.hinge_radius_mm)[:, [0, 2]],
            "distal": cad.section_points(d, c.hinge_radius_mm + c.face_gap_mm, c.axial_offset_mm)[:, [0, 2]],
            "lug_proximal": (px - c.boss_radius_mm, px + c.boss_radius_mm, p0, p1),
            "lug_distal": (px - c.boss_radius_mm, px + c.boss_radius_mm, q0, q1),
            "pin": (px, zw0 - h.head_height_mm, zt + h.pin_end_mm), "delta_mm": c.axial_offset_mm}


def figure(d, sweep, title=""):
    """Report figure (matplotlib): deployed alignment, folded envelope, gap over the travel, offset vs travel."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    env, al, curve = envelope(d, sweep), alignment_sections(d), required_by_travel(d, sweep)
    budget = offset_budget(d, sweep)
    fig, ax = plt.subplots(2, 2, figsize=(13, 9.5))
    a0, a1, a2, a3 = ax.ravel()
    for key, col in (("proximal", "#4C78A8"), ("distal", "#E45756")):
        a0.fill(*al[key].T, color=col, alpha=0.35, label=key)
        a0.plot(*al[key].T, color=col, lw=1)
    for key, col in (("lug_proximal", "#4C78A8"), ("lug_distal", "#E45756")):
        x0, x1, z0, z1 = al[key]
        a0.add_patch(plt.Rectangle((x0, z0), x1 - x0, z1 - z0, fill=False, ec=col, ls="--", lw=1))
    px, zb, zt = al["pin"]
    a0.plot([px, px], [zb, zt], color="0.3", lw=3, label="pim seti")
    for z, lab in ((0.0, "düzlem A"), (al["delta_mm"], "düzlem B")):
        a0.axhline(z, color="0.5", lw=0.7, ls=":")
        a0.text(a0.get_xlim()[0] if False else al["proximal"][:, 0].max() + 1, z, lab, va="center", fontsize=8)
    a0.set(aspect="equal", xlabel="x, veter [mm] (hücum kenarı solda)", ylabel="z, şaft [mm]",
           title=f"Açık hizalama, uçtan bakış: basamak δ = {al['delta_mm']:.1f} mm, kesit yüksekliği "
                 f"{budget['section_height_mm']:.1f} mm")
    a0.legend(fontsize=8, loc="lower right")
    a1.fill(*env["proximal"].T, color="#4C78A8", alpha=0.35)
    a1.plot(*env["distal"].T, color="#E45756", lw=0.8, ls="--", label="distal açık")
    a1.fill(*env["folded"].T, color="#E45756", alpha=0.35, label=f"distal {abs(env['fold_deg']):.0f}° katlı")
    t = np.linspace(0, 2 * np.pi, 200)
    for r, ls, lab in ((env["deployed_radius_mm"], ":", "açık uç dairesi"),
                       (env["folded_radius_mm"], "-", f"katlı zarf R = {env['folded_radius_mm']:.0f} mm")):
        a1.plot(r * np.cos(t), r * np.sin(t), color="0.4", ls=ls, lw=0.8, label=lab)
    if env["critical"]:
        a1.plot(*env["critical"][:2], "k*", ms=11, label=f"belirleyici temas ({abs(env['critical_angle_deg']):.0f}°)")
    a1.plot(*env["pivot"], "ko", ms=4)
    a1.set(aspect="equal", xlim=(-90, 90), ylim=(-10, 175), xlabel="x [mm]", ylabel="y, açıklık [mm]",
           title="Katlanmış zarf (plan)")
    a1.legend(fontsize=8, loc="lower left")
    ang = -np.array(sweep["angles_deg"])
    a2.plot(ang, sweep["gap_mm"], label="nominal")
    a2.plot(ang, sweep["gap_play_mm"], label=f"boşlukla ({sweep['play']['source']})")
    a2.axhline(d.connection.body_clearance_mm, color="0.4", ls="--", lw=0.8, label="gerekli boşluk")
    a2.axvline(-d.connection.stowed_angle_deg, color="0.4", ls=":", lw=0.8, label="gerekli katlanma")
    if sweep["folded_stop_deg"]:
        a2.axvline(sweep["folded_stop_deg"], color="k", lw=0.8, label=f"katlı stop {sweep['folded_stop_deg']:.0f}°")
    a2.set(xlabel="katlanma [°]", ylabel="düşey boşluk [mm]", title="Gövde boşluğu, tam hareket",
           ylim=(min(-2.0, np.nanmin(np.where(np.isfinite(sweep["gap_play_mm"]), sweep["gap_play_mm"], np.nan)) - 0.5), 8))
    a2.legend(fontsize=8)
    a3.plot([c["travel_deg"] for c in curve], [c["required_mm"] for c in curve], "o-", ms=3, label="nominal")
    a3.plot([c["travel_deg"] for c in curve], [c["required_with_play_mm"] for c in curve], "s-", ms=3, label="boşlukla")
    a3.axhspan(5.0, 6.0, color="#14B8A6", alpha=0.15, label="sahip hedefi 5–6 mm")
    a3.axhline(budget["mechanism_floor_mm"], color="0.3", ls="--", lw=0.8,
               label=f"mekanizma tabanı t + c_b = {budget['mechanism_floor_mm']:.1f} mm (tam geçişte, ≳ 110°)")
    a3.set(xlabel="gerekli katlanma [°]", ylabel="gereken ofset [mm]",
           title=f"Gereken ofset: mekanizma {budget['mechanism_floor_mm']:.1f} + kanat {budget['blade_term_mm']:.1f} mm")
    a3.legend(fontsize=8)
    fig.suptitle(title or d.name, fontsize=11)
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------------------------------------- report
REPORT_OFFSET_MM = 6.0
VARIANTS = (   # (label, exploration parameters at δ = REPORT_OFFSET_MM, travel 140°)
    ("düz kanat (burulma 0): mekanizma tabanı", {"planform.twist_scale": 0.0}),
    ("şablon (r_j 99)", {}),
    ("şablon, r_j 110", {"connection.hinge_radius_mm": 110.0}),
    ("B planformu (burulma ×0,6)", {"planform.twist_scale": 0.6}),
    ("B planformu, pim +3 mm", {"planform.twist_scale": 0.6, "connection.pin_x_mm": 3.0}),
    ("B planformu, pim +6 mm", {"planform.twist_scale": 0.6, "connection.pin_x_mm": 6.0}),
    ("13×5,5 sınıfı (burulma ×0,86)", {"planform.twist_scale": 0.86}),
    ("13×5,5 + menteşe bölgesi ±30, burulma ×0,5",
     {"planform.twist_scale": 0.86, "planform.hinge_zone_mm": 30.0, "planform.hinge_twist_factor": 0.5}),
    ("13×5,5 + bölge 45/20 (asimetrik), burulma ×0,4",
     {"planform.twist_scale": 0.86, "planform.hinge_zone_mm": 45.0, "planform.hinge_zone_outboard_mm": 20.0,
      "planform.hinge_twist_factor": 0.4}),
    ("E: 13×5,5 + bölge ±45, kord ×0,85, burulma ×0,45", None),
)
E_PARAMS = {"planform.twist_scale": 0.86, "planform.hinge_zone_mm": 45.0, "planform.hinge_chord_factor": 0.85,
            "planform.hinge_twist_factor": 0.45}
B_PARAMS = {"planform.twist_scale": 0.6, "connection.axial_offset_mm": 9.5}


F1_PARAMS = {"planform.twist_scale": 0.86, "planform.hinge_zone_mm": 45.0, "planform.hinge_chord_factor": 0.85,
             "planform.hinge_twist_factor": 0.6, "connection.axial_offset_mm": 6.5}
F1S_PARAMS = {**F1_PARAMS, "connection.pin_diameter_mm": 4.0, "connection.nose_depth_mm": 4.0,
              "connection.nose_extension_mm": 4.0,   # the strengthened F1 chosen from joint_sizing.csv
              # declared process of the first measurement print (owner, 2026-11-19); nozzle 0.4 is provisional
              "print_model.printer": "Bambu Lab P1S", "print_model.filament": "Eco Smart Standard PLA"}
SIZING_AXES = {"connection.pin_diameter_mm": (3.0, 4.0, 5.0), "connection.nose_depth_mm": (4.0, 5.0, 6.0),
               "connection.nose_extension_mm": (2.0, 3.0, 4.0)}
SIZING_EXTRA = ({"connection.pin_diameter_mm": 4.0, "connection.boss_radius_mm": 6.5, "connection.nose_depth_mm": 5.0,
                 "connection.nose_extension_mm": 3.0},
                {"connection.pin_diameter_mm": 5.0, "connection.boss_radius_mm": 6.5, "connection.nose_depth_mm": 5.0,
                 "connection.nose_extension_mm": 3.0})
SIZING_RPM = 6000.0                                       # reference speed for the stresses (limits scale with Ω²)


def sizing_row(d) -> dict:
    """One joint variant in the actual assembly: solids, full-travel clearance and folded stop, mass, centrifugal
    seating and stop force, every single-lug check with its speed limit at the safety factor, printability."""
    from . import checks, loads, mass, strength
    from .design import validate
    c = d.connection
    row = {"pin_mm": c.pin_diameter_mm, "boss_radius_mm": c.boss_radius_mm, "nose_depth_mm": c.nose_depth_mm,
           "nose_extension_mm": c.nose_extension_mm, "offset_mm": c.axial_offset_mm, "identity": d.identity[:12]}
    errs = validate(d)
    if errs:
        return {**row, "reason": " · ".join(errs)}
    try:
        parts = cad.build(d)
        sw = checks.sweep(parts)
        mp = mass.properties(parts)
        ld = loads.deployed(mp["distal"], d, parts.meta, SIZING_RPM)
        rows = strength.checks(ld, d, parts.meta)
        est = required_by_travel(d, sw, (-c.stowed_angle_deg,))[0]
        gov = strength.governing(rows)
        failed = [r["check"] for r in checks.printability(d, {}) if not r["ok"]]
    except Exception as exc:                                  # a geometric conflict or failed check is a result
        return {**row, "reason": f"{type(exc).__name__}: {exc}"}
    x0, x1 = parts.meta["stop_x_mm"]
    return {**row, "governing": gov["key"] if gov else None, "rpm_limit_sf2": gov["rpm_limit"] if gov else None,
            **{f"limit_{r['key']}": r["rpm_limit"] for r in rows},
            "folded_stop_deg": sw["folded_stop_deg"], "required_mm": est["required_mm"],
            "required_with_play_mm": est["required_with_play_mm"], "seated": bool(ld["seated"]),
            "stop_force_6000_n": ld["stop_force_n"], "stop_lever_mm": ld["stop_lever_mm"], "nose_width_mm": x1 - x0,
            "lugs_mm": [round(t, 2) for t in d.lug_thicknesses_mm], "pin_length_mm": d.pin_length_mm,
            "distal_g": mp["distal"].mass_g, "blade_g": mp["blade"].mass_g, "pin_set_g": mp["pin_set"].mass_g,
            "printability_failed": " · ".join(failed), "reason": ""}


def joint_sizing(root, folder) -> list[dict]:
    """Bounded joint-sizing grid on the F1 aerodynamic baseline (δ 6.5 mm, 140° travel); writes joint_sizing.csv."""
    import csv
    import itertools
    from pathlib import Path

    from . import explore
    from .design import default_design
    root, folder = Path(root), Path(folder)
    base = explore.candidate_design(default_design(root), root, F1_PARAMS)
    keys = list(SIZING_AXES)
    grid = [dict(zip(keys, v)) for v in itertools.product(*SIZING_AXES.values())] + list(SIZING_EXTRA)
    rows = [sizing_row(explore.candidate_design(base, root, p)) for p in grid]
    cols = sorted({k for r in rows for k in r}, key=lambda k: (k.startswith("limit_"), k))
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "joint_sizing.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return rows


def run_candidate(root, folder, name, params, compare=None) -> dict:
    """One candidate end to end: evaluation, the alignment/envelope figure, folded size and the operating envelope
    with the distal's BEM loads (``aero.operating_envelope``; ``compare`` adds the envelope rows of other parameter
    sets for reference), then the manufacturing export (solids, assembly views, drawing, hardware list, calculation
    summary, SHA-256 over everything in the folder) and its own measurement kit."""
    import csv
    import json
    from pathlib import Path

    from . import aero, cad, explore, export, fit, mass
    from .design import default_design, with_changes
    root, folder = Path(root), Path(folder)
    build = lambda n, p: with_changes(explore.candidate_design(default_design(root), root, p), name=f"13in-{n}")  # noqa: E731
    d = build(name, params)
    r = explore.evaluate(d)
    if "parts" not in r or "sweep" not in r:
        raise RuntimeError(f"{name} could not be evaluated: {r['reasons']}")
    out_dir = folder / f"{name}_candidate"
    out_dir.mkdir(parents=True, exist_ok=True)
    figure(d, r["sweep"], f"{name}: δ {d.connection.axial_offset_mm:.1f} mm, pim Ø{d.connection.pin_diameter_mm:g}, "
           f"gerekli katlanma {-d.connection.stowed_angle_deg:.0f}°").savefig(out_dir / "alignment_envelope.png", dpi=110)
    record = json.loads((folder / "aero" / "polars_printable_section.json").read_text(encoding="utf-8"))
    aero.check_record(root, record)
    env = [{"candidate": name, **e} for e in aero.operating_envelope(
        d, aero.schedule(d, aero.families_from_record(d, record)), r["parts"], r["mass"]["distal"])]
    for other, p in (compare or {}).items():
        try:                                                  # a comparison that cannot be built is a row, not a stop
            od = build(other, p)
            op = cad.build(od)
            env += [{"candidate": other, **e} for e in aero.operating_envelope(
                od, aero.schedule(od, aero.families_from_record(od, record)), op, mass.properties(op)["distal"])]
        except Exception as exc:                              # noqa: BLE001
            env.append({"candidate": other, "reason": f"{type(exc).__name__}: {exc}"})
    dims = folded_dimensions(d, r["sweep"])
    for fname, rows in (("operating_envelope.csv", env), ("folded_dimensions.csv", dims)):
        cols = list(dict.fromkeys(k for row in rows for k in row))
        with open(out_dir / fname, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    export.export_candidate(r["parts"], out_dir, r)
    fit.export_kit(d, folder / f"fit_kit_{name}")
    return {"design": d, "evaluation": r, "envelope": env, "folded": dims, "budget": offset_budget(d, r["sweep"])}


def study_row(label, d):
    """Build, sweep and seat one variant; any failure is a row with its reason."""
    from . import loads, mass
    from .design import validate
    row = {"variant": label, "identity": d.identity[:12], "pitch_075R_in": round(pitch_in(d, 0.75), 2)}
    errs = validate(d)
    if errs:
        return {**row, "reason": " · ".join(errs)}
    try:
        parts = cad.build(d)
        from .checks import sweep as run_sweep
        sw = run_sweep(parts)
        b = offset_budget(d, sw)
        curve = {c["travel_deg"]: c for c in required_by_travel(d, sw, (90, 110, 140, 180))}
        mp = mass.properties(parts)
        ld = loads.deployed(mp["distal"], d, parts.meta, 6000.0)
    except Exception as exc:                                  # a geometric conflict is a result
        return {**row, "reason": f"{type(exc).__name__}: {exc}"}
    return {**row, "pitch_joint_in": round(b["pitch_at_joint_in"], 2), "section_height_mm": round(b["section_height_mm"], 2),
            "mechanism_floor_mm": round(b["mechanism_floor_mm"], 2), "blade_term_mm": round(b["blade_term_mm"], 2),
            **{f"req_{t}_mm": round(curve[t]["required_mm"], 2) for t in curve},
            **{f"req_{t}_play_mm": round(curve[t]["required_with_play_mm"], 2) for t in curve},
            "governing_angle_deg": sw["min_gap_angle_deg"], "folded_stop_deg": sw["folded_stop_deg"],
            "seated": bool(ld["seated"]), "stop_moment_6000_nmm": round(ld["deploy_moment_nmm"]), "reason": ""}


def run_report(root, folder) -> dict:
    """Regenerate the study: variant table, figures for B and E, candidate E's outputs and B's measurement kit."""
    import csv
    import json
    from pathlib import Path

    from . import explore, export, fit
    from .design import default_design, with_changes
    root, folder = Path(root), Path(folder)
    (folder / "study").mkdir(parents=True, exist_ok=True)
    base = with_changes(default_design(root), **{"connection.axial_offset_mm": REPORT_OFFSET_MM})
    rows = [study_row(label, explore.candidate_design(base, root, E_PARAMS if p is None else p)) for label, p in VARIANTS]
    keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[1]).index(k) if k in rows[1] else 99)
    with open(folder / "study" / "offset_study.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    out = {"rows": rows}
    for name, params in (("B", B_PARAMS), ("E", {**E_PARAMS, "connection.axial_offset_mm": REPORT_OFFSET_MM})):
        d = with_changes(explore.candidate_design(base, root, params), name=f"13in-{name}")
        r = explore.evaluate(d)
        if "sweep" in r:
            figure(d, r["sweep"], f"{name}: δ {d.connection.axial_offset_mm:.1f} mm, gerekli katlanma "
                   f"{-d.connection.stowed_angle_deg:.0f}°").savefig(folder / "study" / f"alignment_envelope_{name}.png", dpi=110)
            out[name] = {"eligible": r["eligible"], "reasons": r["reasons"], "budget": offset_budget(d, r["sweep"])}
        if name == "E" and "parts" in r:
            export.export_candidate(r["parts"], folder / "E_offset6_ts0p86_zone45_travel140", r)
        fit.export_kit(d, folder / f"fit_kit_{name}")             # B: reference kit; E: the next compact candidate
    (folder / "study" / "study.json").write_text(json.dumps(export._jsonable(out), indent=1, ensure_ascii=False),
                                                 encoding="utf-8")
    return out


if __name__ == "__main__":                                    # python -m pyfoldable.prototype.study <report folder>
    import sys
    from pathlib import Path
    run_report(Path.cwd(), Path(sys.argv[1]))
