"""Manufacturing outputs of one candidate: STEP/STL/3MF parts (millimetres), assembly STEP, drawing, hardware list,
assembly instructions, calculation and assumption summary, and SHA-256 sums. Nothing here changes the design."""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import math
from dataclasses import asdict
from pathlib import Path

import numpy as np

from . import cad, checks, loads, mass, strength
from .design import MATERIAL_SOURCE, STEEL_SOURCE, to_json

PRINTABLE = ("rotor_hub_proximal", "distal", "fit_proximal", "fit_distal", "hole_coupon")


def _b3d():
    import build123d as b3d
    return b3d


def build_outputs(parts) -> dict:
    """Named solids for export (deployed assembly coordinates; the rotor includes every proximal segment)."""
    fp, fd = cad.fit_test(parts)
    return {"rotor_hub_proximal": cad.rotor(parts), "distal": parts.distal, "fit_proximal": fp, "fit_distal": fd,
            "hole_coupon": cad.hole_coupon(parts.design), **{f"hw_{k}": v for k, v in parts.hardware.items()}}


def _write_mesh(b3d, shape, stl_path, mf_path):
    b3d.export_stl(shape, str(stl_path), tolerance=0.01, angular_tolerance=0.1)
    m = b3d.Mesher()
    m.add_shape(shape, linear_deflection=0.01, angular_deflection=0.1)
    m.write(str(mf_path))


def _section_lines(shape, x_mm):
    """Polylines of the planar section x = x_mm (y, z) of a solid (exact OCC section, discretised)."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
    b3d = _b3d()
    sec = BRepAlgoAPI_Section(shape.wrapped, gp_Pln(gp_Pnt(x_mm, 0, 0), gp_Dir(1, 0, 0)))
    sec.Build()
    out = []
    for e in b3d.Compound(sec.Shape()).edges():
        p = [e.position_at(t) for t in np.linspace(0, 1, 24)]
        out.append(np.array([[q.Y, q.Z] for q in p]))
    return out


def drawing(parts, report, path_pdf, path_svg_prefix):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.collections import PolyCollection
    d = parts.design
    c = d.connection
    px, py = parts.pin_axis
    (p0, p1), (q0, q1) = d.lug_bands_mm
    sw = report["sweep"]
    fold_show = -min(sw["clear_travel_deg"], -c.stowed_angle_deg)
    figs = []

    def tri_fill(ax, shape, color, alpha, z=1, lw=0.0, ls="-"):
        # fills are rasterised (dimensions, lines and text stay vector); a fresh copy meshes coarser than the sweep
        v, f = cad.tessellate(copy.deepcopy(shape), 0.2, 0.5)
        ax.add_collection(PolyCollection(v[f][:, :, :2], facecolor=color, edgecolor=color, alpha=alpha,
                                         linewidths=lw, linestyle=ls, zorder=z, rasterized=True))

    # sheet 1: plan view of the joint and the whole blade
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(16.5, 11.7), gridspec_kw={"width_ratios": [1.35, 1]})
    tri_fill(ax, parts.meta["proximal_blade"], "#4C78A8", 0.55)
    tri_fill(ax, parts.distal, "#E45756", 0.55, z=2)
    tri_fill(ax, parts.distal_at(fold_show), "#E45756", 0.12, z=0)
    for r, ls, lab in ((c.boss_radius_mm, "-", "lug Ø%.1f" % (2 * c.boss_radius_mm)),
                       (d.relief_radius_mm, "--", "boşaltma R%.1f" % d.relief_radius_mm)):
        ax.add_patch(plt.Circle((px, py), r, fill=False, ls=ls, lw=0.9, color="k", zorder=5))
    ax.add_patch(plt.Circle((px, py), d.hole_diameter_mm / 2, fill=False, lw=0.9, color="k", zorder=5))
    ax.plot([px - 9, px + 9], [py, py], "k-.", lw=0.6); ax.plot([px, px], [py - 9, py + 9], "k-.", lw=0.6)
    x0, x1 = parts.meta["stop_x_mm"]
    ax.plot([x0, x1], [py, py], color="#F58518", lw=3.5, zorder=6, label="açık stop oturma yüzeyi (y = r_j)")
    ax.axhline(py, color="0.4", lw=0.5, ls=":")
    ax.annotate("", xy=(px + 18, py + 10), xytext=(px + 4, py + 26),
                arrowprops=dict(arrowstyle="->", lw=1.2, connectionstyle="arc3,rad=-0.3"))
    ax.text(px + 12, py + 27, "geri katlanma (−θ)", fontsize=9)
    ax.set_xlim(-32, 40); ax.set_ylim(py - 40, py + 30); ax.set_aspect("equal")
    ax.set_xlabel("x [mm] (veter, hücum kenarı −x)"); ax.set_ylabel("y [mm] (açıklık)")
    ax.set_title(f"Plan (z+ yönünden) — pim ekseni z ∥ mil @ (x {px:.1f}, y {py:.1f}) mm; soluk: θ = {fold_show:.0f}°")
    ax.legend(loc="lower left", fontsize=8)
    tri_fill(ax2, parts.proximal, "#4C78A8", 0.55)
    tri_fill(ax2, parts.distal, "#E45756", 0.55, z=2)
    tri_fill(ax2, parts.distal_at(fold_show), "#E45756", 0.15, z=0)
    ax2.axhline(py, color="0.3", lw=0.6, ls=":"); ax2.set_aspect("equal")
    ax2.set_xlim(-60, 60); ax2.set_ylim(-20, d.planform.tip_radius_mm + 5)
    ax2.set_title(f"Tam kanat: Ø{d.planform.diameter_mm:.1f} mm, r_j {py:.1f} mm; "
                  f"açık katlanma {sw['clear_travel_deg']:.0f}° / gerekli {-c.stowed_angle_deg:.0f}°")
    rows = [("Eksenel ofset δ (A→B)", f"{c.axial_offset_mm:.2f} mm"), ("Pim Ø / delik Ø", f"{c.pin_diameter_mm:.2f} / {d.hole_diameter_mm:.2f} mm"),
            ("Lug kalınlığı prok./dist.", "%.2f / %.2f mm" % d.lug_thicknesses_mm),
            ("Lug aralığı g", f"{c.lug_gap_mm:.2f} mm"), ("Toplam lug yığını", f"{d.stack_thickness_mm:.2f} mm"),
            ("Lug orta düzlem aralığı", f"{d.lug_midplane_offset_mm:.2f} mm"), ("Lug yarıçapı / boşaltma", f"{c.boss_radius_mm:.2f} / {d.relief_radius_mm:.2f} mm"),
            ("Pim x (çeyrek veterden)", f"{c.pin_x_mm:.2f} mm"), ("Uç yüz aralığı", f"{c.face_gap_mm:.2f} mm"),
            ("Stop burnu x aralığı", f"{x0:.1f} … {x1:.1f} mm"), ("Açık stop", "θ = 0 (burun–ped teması)")]
    fig.subplots_adjust(bottom=0.27)
    tax = fig.add_axes([0.56, 0.02, 0.4, 0.2])
    tax.axis("off")
    tab = tax.table(cellText=rows, colLabels=["Kritik ölçü", "Değer"], loc="center", colWidths=[0.55, 0.45])
    tab.auto_set_font_size(False)
    tab.set_fontsize(9)
    fig.suptitle(f"PyFoldable {d.name} — montaj resmi 1/2 (mm) — kimlik {d.identity[:12]} — fiziksel yeterlilik yok",
                 fontsize=11)
    figs.append(fig)

    # sheet 2: section x = pin through the actual solids (y–z), z stack and reference planes
    fig, ax = plt.subplots(figsize=(16.5, 11.7))
    for shape, color in ((parts.meta["proximal_blade"], "#4C78A8"), (parts.distal, "#E45756"),
                         *((h, "0.25") for h in parts.hardware.values())):
        for pl in _section_lines(shape, px + 1e-3):
            ax.plot(pl[:, 0], pl[:, 1], color=color, lw=1.0)
    for z, lab in ((0.0, "Düzlem A (z = 0): proksimal çeyrek veter"), (c.axial_offset_mm, f"Düzlem B (z = δ = {c.axial_offset_mm:.2f})"),
                   (p0, f"proksimal lug {p0:.2f}"), (p1, f"{p1:.2f}"), (q0, f"distal lug {q0:.2f}"), (q1, f"{q1:.2f}")):
        ax.axhline(z, color="0.6", lw=0.5, ls="--")
        ax.text(py + 13, z + 0.05, lab, fontsize=8, color="0.25")
    ax.axvline(py, color="0.3", lw=0.6, ls="-.")
    ax.text(py + 0.3, 0.97, "pim ekseni", fontsize=8, va="top", transform=ax.get_xaxis_transform())   # inside the axes
    ax.set_xlim(py - 16, py + 26); ax.set_aspect("equal")
    ax.set_xlabel("y [mm] (açıklık)"); ax.set_ylabel("z [mm] (mil ekseni, itki tarafı +z)")
    hw = d.hardware
    ax.set_title(f"Kesit A–A: x = {px:.1f} mm (pim ekseninden), firar kenarı tarafından bakış — yığın: pul {hw.washer_thickness_mm} + "
                 f"lug {d.lug_thicknesses_mm[0]:.2f} + g {c.lug_gap_mm} + lug {d.lug_thicknesses_mm[1]:.2f} + pul {hw.washer_thickness_mm} + "
                 f"segman {hw.clip_thickness_mm} mm; pim {d.pin_length_mm:.2f} mm kafa altından")
    fig.suptitle(f"PyFoldable {d.name} — montaj resmi 2/2 (mm) — gerçek katı kesiti", fontsize=11)
    figs.append(fig)
    with PdfPages(path_pdf) as pdf:
        for k, f in enumerate(figs, 1):
            pdf.savefig(f)
            f.savefig(f"{path_svg_prefix}_{k}.svg")
            plt.close(f)


def bom(d, n_blades=None) -> list[dict]:
    n = n_blades or d.planform.blade_count
    h, c = d.hardware, d.connection
    groove_at = 2 * h.washer_thickness_mm + d.stack_thickness_mm
    return [
        {"item": "Pin", "qty": n, "spec": f"{h.pin_standard}; shank length under head {d.pin_length_mm:.2f} mm, "
         f"groove start {groove_at:.2f} mm under the head", "material": "steel (4.6 or better)"},
        {"item": "Washer", "qty": 2 * n, "spec": f"DIN 433 {h.washer_id_mm}×{h.washer_od_mm}×{h.washer_thickness_mm} mm",
         "material": "steel"},
        {"item": "Retaining washer (E-clip)", "qty": n, "spec": f"DIN 6799 size {h.groove_diameter_mm} (OD ≈ {h.clip_od_mm} mm, "
         f"t {h.clip_thickness_mm} mm)", "material": "spring steel"},
        {"item": "Rotor hub with proximal segments", "qty": 1, "spec": "rotor_hub_proximal.stl/.3mf (print)",
         "material": d.print_model.material},
        {"item": "Distal segment", "qty": n, "spec": "distal.stl/.3mf (print)", "material": d.print_model.material},
        {"item": "Fit-test sections", "qty": 1, "spec": "fit_proximal + fit_distal (print first)", "material": d.print_model.material},
        {"item": "Hole coupon", "qty": 1, "spec": f"hole_coupon (holes Ø{c.pin_diameter_mm:.1f} + 0.0…0.4 mm)",
         "material": d.print_model.material},
    ]


def instructions(d) -> str:
    c, h = d.connection, d.hardware
    return f"""# Assembly instructions — {d.name}

Units: millimetres. Fit and mechanism prototype only; not qualified for powered operation.

1. Print the hole coupon in the same material and orientation as the lugs (rotor plane on the bed). Push the real
   Ø{c.pin_diameter_mm} pin through each hole (k notches mark hole k). Pick the hole that runs freely without
   wobble; set `hole_clearance_mm` to that step and re-export before printing the segments.
2. Print the fit-test pair (`fit_proximal`, `fit_distal`). Support the twisted lower surfaces; keep supports out of
   the lug faces and holes. Remove supports and deburr the hole entries (0.4 mm chamfers are modelled).
3. Stack from below: pin head → washer → proximal lug → distal lug → washer → E-clip. The distal lug sits above
   the proximal lug with the running gap g = {c.lug_gap_mm} mm (the gap is set by the hardware stack; do not
   clamp it closed). Seat the E-clip in the groove with pliers.
4. Rotate the distal through the full travel by hand. Check: it seats flat on the open stop at θ = 0 (nose on the
   proximal pad ahead of the pin), it folds backward (toward the trailing edge) without touching the proximal
   outside the joint, and the pin turns freely. Record any contact location and angle.
5. Measure (see `docs/prototype_13in.md`, measurement plan): masses and CG of each part, hole diameters, lug
   thicknesses, gap, wobble at the distal tip, friction torque, and the stop seat. Only then print the full rotor.
6. Full rotor: assemble each blade as in 3. Do not spin it under power: maximum speed, motor and thrust are not
   yet specified and the strength estimates use exploratory material data.
"""


def summary(d, report) -> str:
    sw, al, mp = report["sweep"], report["alignment"], report["mass"]
    lines = [f"# Calculation and assumption summary — {d.name}", "",
             f"Design identity `{d.identity}`. Section identity `{d.section_identity}` (catalog "
             f"{d.planform.profile_id} with the trailing edge thickened to {d.print_model.min_te_thickness_mm} mm: a new "
             "aerodynamic section; retained polars of the catalog profile apply only approximately and an XFOIL family "
             "for this section is required before aerodynamic conclusions).", "",
             "Physical qualification: **false**. Exploratory material values: " + MATERIAL_SOURCE, "",
             "## Geometry", "",
             f"- Diameter {d.planform.diameter_mm:.1f} mm, blades {d.planform.blade_count}, hinge (joint plane) r_j = {d.connection.hinge_radius_mm} mm "
             f"(proximal {d.connection.hinge_radius_mm - d.hub_radius_mm:.1f} mm > distal {d.planform.tip_radius_mm - d.connection.hinge_radius_mm:.1f} mm).",
             f"- Planform from `{d.planform.template_id}` scaled to the diameter, chord ×{d.planform.chord_scale}, twist ×{d.planform.twist_scale}: "
             + "; ".join(f"r {r:.1f}: c {ch:.1f}, β {tw:.1f}°" for r, ch, tw in d.planform.stations),
             f"- Axial offset δ = {d.connection.axial_offset_mm} mm (plane A z = 0 proximal quarter-chord plane → plane B distal); "
             f"deployed step at the joint {al['step_mm']} mm, face gap {al['face_gap_mm']} mm, stop nose {al['nose_ahead_of_le_mm']} mm ahead of the leading edge.",
             f"- Lug stack {d.stack_thickness_mm:.2f} mm (proximal {d.lug_thicknesses_mm[0]:.2f}, gap {d.connection.lug_gap_mm}, "
             f"distal {d.lug_thicknesses_mm[1]:.2f}; "
             + ("full-depth lugs: each spans its blade section over the boss" if d.connection.lug_thickness_proximal_mm is None
                and d.connection.lug_thickness_distal_mm is None else "explicit lug thicknesses")
             + f"); lug mid-planes {d.lug_midplane_offset_mm:.2f} mm apart; pin Ø{d.connection.pin_diameter_mm}, hole Ø{d.hole_diameter_mm:.2f}.",
             "", "## Full-travel clearance (actual solids)", "",
             f"- Required travel {-d.connection.stowed_angle_deg:.0f}° (owner decision; template declares 180°); clear to "
             f"{sw['clear_travel_deg']:.0f}°. Folded stop (stop nose meets the proximal): "
             + (f"{sw['folded_stop_deg']:.0f}°." if sw["folded_stop_deg"] is not None else "none within 180°.")
             + f" Smallest vertical body clearance {sw['min_gap_mm']:.2f} mm at {sw['min_gap_angle_deg']:.0f}° "
             "(negative = interference depth).",
             f"- With worst-case joint play (tilt {sw['play']['tilt_deg']:.2f}°, limited by {sw['play']['tilt_limited_by']}; tip droop "
             f"{sw['play']['tip_droop_mm']:.2f} mm): {sw['min_gap_play_mm']:.2f} mm at {sw['min_gap_play_angle_deg']:.0f}°.",
             f"- Offset that clears the full travel: ≈ {sw['required_offset_mm']:.1f} mm nominal, ≈ {sw['required_offset_with_play_mm']:.1f} mm with play "
             "(estimated from the deficit; confirm by re-running at that offset).",
             f"- Method: {sw['method']}. Exact OpenCASCADE distance proximal–distal: "
             + ", ".join(f"{float(a):g}° → {v['proximal']:.3f} mm" for a, v in report["exact"].items())
             + " (0 at the open stop is the designed seat; the column gap is a vertical clearance ≥ the exact distance).",
             "- Open-stop seat: zero nominal clearance between separately printed faces; the as-printed open angle varies "
             "by about ±0.1 mm / lever (≈ ±0.7° at 8 mm). Measure it on the fit test.",
             "", "## Mass properties (estimate until weighed)", "",
             *[f"- {k}: {mp[k].mass_g:.2f} g, CG ({', '.join(f'{v:.2f}' for v in mp[k].cg_mm)}) mm — {mp[k].method}"
               for k in ("proximal", "distal", "pin_set", "blade")],
             f"- Distal inertia about its CG [g·mm²]: " + np.array2string(np.round(mp["distal"].I, 1), separator=", ").replace("\n", " "),
             f"- Distal CG {mp['fold']['chordwise_cg_offset_mm']:.2f} mm aft of the pin; centrifugal moment about the pin "
             + ("seats the segment on the open stop." if report["load_table"][0]["seated"]
                else "does **not** seat the segment on the open stop."),
             "", "## Deployed loads and single-lug checks (" + ("what-if speeds; no owner maximum speed" if d.operating.max_rpm is None
                 else f"what-if speeds and the owner maximum {d.operating.max_rpm:.0f} RPM") + ")", "",
             "| RPM | case | seated | centrifugal [N] | stop [N] | pin [N] | couple [N·mm] | governing check | "
             "limit RPM (SF %.1f) | min margin |" % d.operating.safety_factor,
             "|---|---|---|---|---|---|---|---|---|---|"]
    for row in report["load_table"]:
        case = ("owner max" + (" + aero" if row["aero"] else ", centrifugal only")) if row["owner"] else "what-if, centrifugal only"
        lim = "—" if row["limit_rpm"] is None else f"{row['limit_rpm']:.0f}"
        lines.append(f"| {row['rpm']:.0f} | {case} | {'yes' if row['seated'] else '**no**'} | {row['centrifugal_n']:.0f} | "
                     f"{row['stop_n']:.0f} | {row['pin_n']:.0f} | {row['couple_nmm']:.0f} | {row['governing']} | {lim} | "
                     + ("— |" if row["min_margin"] is None else f"{row['min_margin']:+.2f} |"))
    lines += ["", strength.SCOPE, "", "Pin steel: " + STEEL_SOURCE, "",
              "## Owner inputs still missing", "", *[f"- {m}" for m in d.missing_owner_inputs()], "",
              "## Printability", "", *[f"- {'OK' if r['ok'] else 'FAIL'} {r['check']}: {r['value']} ({r['note']})"
                                       for r in report["printability"]]]
    return "\n".join(lines) + "\n"


def evaluate_for_export(parts, outputs, evaluation=None) -> dict:
    """Checks for the summary; reuses an ``explore.evaluate`` result of the same parts when given."""
    d = parts.design
    ev = evaluation if evaluation is not None and evaluation.get("parts") is parts else {}
    mp = ev.get("mass") or mass.properties(parts)
    rep = {"sweep": ev.get("sweep") or checks.sweep(parts), "alignment": ev.get("alignment") or checks.alignment(d, parts),
           "mass": mp, "printability": ev.get("printability") or checks.printability(d, {k: outputs[k] for k in PRINTABLE})}
    table = []
    speeds = sorted(set(d.operating.what_if_rpm) | ({d.operating.max_rpm} if d.operating.max_rpm else set()))
    for rpm in speeds:
        owner = rpm == d.operating.max_rpm
        L = loads.owner_case(mp["distal"], d, parts.meta) if owner else loads.deployed(mp["distal"], d, parts.meta, rpm)
        rows = strength.checks(L, d, parts.meta)
        gov = strength.governing(rows) or max(rows, key=lambda r: r["stress_mpa"] / r["allowable_mpa"])
        table.append({"rpm": rpm, "owner": owner, "aero": L["aero_included"], "seated": L["seated"],
                      "centrifugal_n": L["centrifugal_force_n"][1], "stop_n": L["stop_force_n"],
                      "pin_n": L["pin_force_inplane_n"], "couple_nmm": L["pin_couple_inplane_nmm"],
                      "governing": gov["label"], "limit_rpm": gov["rpm_limit"], "min_margin": min(
                          (r["margin"] for r in rows if r["margin"] is not None), default=None)})
    rep["load_table"] = table
    rep["exact"] = {f"{a:g}": checks.exact_distance(parts, a) for a in (0.0, -2.0, rep["sweep"]["min_gap_angle_deg"])}
    return rep


def export_candidate(parts, folder: Path, evaluation=None) -> dict:
    """Write every output into ``folder``; returns the report and the file list with SHA-256. ``evaluation``: an
    ``explore.evaluate`` result for these parts (its checks and printable solids are reused)."""
    b3d = _b3d()
    folder = Path(folder)
    for sub in ("step", "stl", "3mf"):
        (folder / sub).mkdir(parents=True, exist_ok=True)
    d = parts.design
    reuse = evaluation is not None and evaluation.get("parts") is parts
    outputs = evaluation["outputs"] if reuse and evaluation.get("outputs") else build_outputs(parts)
    for name, shape in outputs.items():
        b3d.export_step(shape, str(folder / "step" / f"{name}.step"))
        if name in PRINTABLE:
            _write_mesh(b3d, shape, folder / "stl" / f"{name}.stl", folder / "3mf" / f"{name}.3mf")
    asm = b3d.Compound([parts.proximal, parts.distal, *parts.hardware.values()])
    b3d.export_step(asm, str(folder / "step" / "assembly_deployed.step"))
    report = evaluate_for_export(parts, outputs, evaluation)
    fold = -min(report["sweep"]["clear_travel_deg"], -d.connection.stowed_angle_deg)
    b3d.export_step(b3d.Compound([parts.proximal, parts.distal_at(fold), *parts.hardware.values()]),
                    str(folder / "step" / f"assembly_folded_{abs(fold):.0f}deg.step"))
    drawing(parts, report, folder / "assembly_drawing.pdf", folder / "assembly_drawing")
    (folder / "design.json").write_text(to_json(d), encoding="utf-8")
    (folder / "summary.md").write_text(summary(d, report), encoding="utf-8")
    (folder / "assembly_instructions.md").write_text(instructions(d), encoding="utf-8")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["item", "qty", "spec", "material"], lineterminator="\n")
    w.writeheader()
    w.writerows(bom(d))
    (folder / "hardware_list.csv").write_text(buf.getvalue(), encoding="utf-8")
    (folder / "report.json").write_text(json.dumps(_jsonable(report), indent=1, ensure_ascii=False), encoding="utf-8")
    (folder / "README.md").write_text(
        f"# {d.name} manufacturing outputs\n\nAll lengths in millimetres (STEP declares mm; STL/3MF are in mm). Frame: x chord "
        "(leading edge −x), y span, z shaft (thrust side +z). Assembly STEP files are in the deployed blade-1 frame. "
        "Printable parts: " + ", ".join(PRINTABLE) + ". Hardware solids (hw_*) are for fit checks, not printing.\n"
        "Fit and mechanism prototype; physical qualification false. See summary.md, assembly_instructions.md, "
        "hardware_list.csv and assembly_drawing.pdf.\n", encoding="utf-8")
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    sums = [(hashlib.sha256(p.read_bytes()).hexdigest(), p.relative_to(folder).as_posix()) for p in files]
    (folder / "SHA256SUMS").write_text("".join(f"{h}  {n}\n" for h, n in sums), encoding="utf-8")
    return {"report": report, "files": sums}


def _jsonable(x):
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, (np.floating, np.integer, np.bool_)):
        return x.item()
    if isinstance(x, mass.MassProps):
        return asdict(x)
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x
