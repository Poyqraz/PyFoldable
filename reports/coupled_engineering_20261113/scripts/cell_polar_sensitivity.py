"""DIAGNOSTIC ONLY (never admitted, not a polar family): direct XFOIL at the section states of the
1600 RPM run that fall inside the deploy-v3 interpolation cell Re 100k-165k x Mach 0.07-0.10, compared
with DUST's own interpolation of the admitted C81 table, and the resulting bound on the run's loads.

Inputs: the pinned local XFOIL 6.99 preflight (same executable as the deploy-v3 family), the sealed
record 20261112T220255_14fc6eaab8 and its C81 table regenerated from the admission. Same solver
settings and 2-degree cold sequence as the family. Usage: cell_polar_sensitivity.py <out.json>
"""
import hashlib
import json
import math
import os
import sys
from pathlib import Path

root = Path.home() / "projects/PyFoldable"
sys.path.insert(0, str(root))
from pyfoldable.application import coupled_analysis as svc  # noqa: E402
from pyfoldable.core.profile_catalog import load_project_airfoil  # noqa: E402
from pyfoldable.core.providers import PolarGenerationRequest  # noqa: E402
from pyfoldable.coupled import c81  # noqa: E402
from pyfoldable.providers import xfoil  # noqa: E402

pre = Path.home() / "pyf-work/xfoil/preflight"
os.environ["OSMAP"] = str(pre / "runtime/osmapDP.dat")
prov = xfoil.XfoilProvider(pre / "bin/xfoil", backend_version="6.99")
foil = load_project_airfoil("NACA2412")
ALPHAS = list(range(-6, 9, 2))

run_dir = root / "outputs/coupled_runs/20261112T220255_14fc6eaab8"
row = svc.load_result(run_dir)
text = (run_dir / "dust/airfoil/NACA2412.c81").read_text()
if hashlib.sha256(text.encode()).hexdigest() != row["request"]["c81"]["sha256"]:
    raise SystemExit("C81 file in the run folder does not match the sealed record")
table = c81.parse_c81(text)

# section states of the run inside the cell
ix = {c: i for i, c in enumerate(row["radial_columns"])}
case = row["run_definition"]["case"]
rho, a_snd = case["density_kg_m3"], case["speed_of_sound_m_s"]
cell = [r for r in row["radial"] if r[ix["reynolds"]] < 165000.0 and r[ix["mach"]] < 0.10]
series = {s["window"]: s for s in row["series"]}


def run_grid(alphas, label, res_list, ma_list):
    pts = []
    for m in ma_list:
        for re in res_list:
            q = PolarGenerationRequest(airfoil=foil, alpha_rad=tuple(math.radians(x) for x in alphas), reynolds=re, mach=m,
                                       n_crit=9.0, xtr_upper=1.0, xtr_lower=1.0, max_iterations=160, timeout_s=30.0,
                                       scenario_id="diagnostic_cell_sensitivity", options={"repanel": True})
            res = prov.generate(q)
            for p in res.points:
                al = math.degrees(p.alpha_rad)
                tl, td, tm = c81.dust_interpolate(table, al, m, re)
                rec = {"sequence": label, "reynolds": re, "mach": m, "alpha_deg": round(al, 6), "converged": bool(p.usable),
                       "table": {"cl": tl, "cd": td, "cm": tm}}
                if p.usable:
                    rec["xfoil"] = {"cl": p.cl, "cd": p.cd, "cm": p.cm}
                    rec["delta"] = {"cl": p.cl - tl, "cd": p.cd - td, "cm": p.cm - tm}
                pts.append(rec)
            print(label, m, int(re), "complete" if res.complete else "incomplete", flush=True)
    return pts


# (1) the family's own 2-degree cold sequence: tests Re/Mach interpolation at the table's angle nodes
points = run_grid(ALPHAS, "family_2deg", [130000.0, 135000.0, 145000.0, 160000.0], [0.085, 0.095, 0.10])
# (2) the run's own angles (between the -2 and 0 nodes): tests the angle interpolation too
RUN_ALPHAS = [-2.0, -1.8, -1.4, -1.0, -0.8, 0.0]
points_run = run_grid(RUN_ALPHAS, "run_angles", [135000.0, 145000.0, 160000.0], [0.085, 0.095, 0.10])


def worst(pts, lo, hi):
    sel = [p for p in pts if p["converged"] and lo <= p["alpha_deg"] <= hi]
    return {q: max(abs(p["delta"][q]) for p in sel) for q in ("cl", "cd", "cm")}


d_nodes = worst(points, -2.0, 0.0)
d_run = worst(points_run, -1.9, -0.8)
dcl, dcd = max(d_nodes["cl"], d_run["cl"]), max(d_nodes["cd"], d_run["cd"])

# per-element strip width: the larger gap to the neighbouring element centre of the same blade and window
by_wb = {}
for r in row["radial"]:
    by_wb.setdefault((r[ix["window"]], r[ix["blade"]]), []).append(r[ix["span_y_m"]])
width = {}
for key, ys in by_wb.items():
    ys = sorted(ys)
    for k, y in enumerate(ys):
        gaps = [abs(y - ys[k - 1])] if k > 0 else []
        gaps += [abs(ys[k + 1] - y)] if k + 1 < len(ys) else []
        width[(key, round(y, 12))] = max(gaps) if gaps else 0.0
per_w, share = {}, {}
for r in cell:
    w = r[ix["window"]]
    q = 0.5 * rho * (r[ix["mach"]] * a_snd) ** 2
    ds = width[((w, r[ix["blade"]]), round(r[ix["span_y_m"]], 12))]
    per_w[w] = per_w.get(w, 0.0) + q * r[ix["chord_m"]] * ds
fz = {}
for r in row["radial"]:
    if r[ix["window"]] in per_w:
        tot, inc = fz.get(r[ix["window"]], (0.0, 0.0))
        inside = r[ix["reynolds"]] < 165000.0 and r[ix["mach"]] < 0.10
        fz[r[ix["window"]]] = (tot + abs(r[ix["dFz_n"]]), inc + (abs(r[ix["dFz_n"]]) if inside else 0.0))
worst_window = max(per_w, key=per_w.get)
dT = per_w[worst_window] * math.hypot(dcl, dcd)
widths_cell = [width[((r[ix["window"]], r[ix["blade"]]), round(r[ix["span_y_m"]], 12))] for r in cell]
out = {"diagnostic": True, "record": "20261112T220255_14fc6eaab8", "executable": "pinned deploy-v3 preflight",
       "cell": {"reynolds": [100000.0, 165000.0], "mach": [0.07, 0.10]},
       "run_states_in_cell": {"elements": len(cell), "windows": len(per_w), "windows_in_record": len(series),
                              "rpm_range_of_cell_windows": [min(series[w]["rpm"] for w in per_w), max(series[w]["rpm"] for w in per_w)],
                              "alpha_deg": [min(r[ix["alpha_deg"]] for r in cell), max(r[ix["alpha_deg"]] for r in cell)],
                              "reynolds": [min(r[ix["reynolds"]] for r in cell), max(r[ix["reynolds"]] for r in cell)],
                              "mach": [min(r[ix["mach"]] for r in cell), max(r[ix["mach"]] for r in cell)],
                              "segments": sorted({r[ix["segment"]] for r in cell}),
                              "share_of_element_abs_dFz_in_cell_windows": sum(v[1] for v in fz.values()) / sum(v[0] for v in fz.values()),
                              "strip_width_m": [min(widths_cell), max(widths_cell)]},
       "xfoil_points": points, "xfoil_points_run_angles": points_run,
       "max_abs_delta_family_nodes_alpha_-2_to_0": d_nodes, "max_abs_delta_run_angles": d_run,
       "max_abs_delta_all_converged": {q: max(abs(p["delta"][q]) for p in points if p["converged"]) for q in ("cl", "cd", "cm")},
       "max_abs_delta_by_alpha": {str(al): {q: max(abs(p["delta"][q]) for p in points if p["converged"] and p["alpha_deg"] == al)
                                            for q in ("cl", "cd")} for al in ALPHAS},
       "nonconverged": [{k: p[k] for k in ("sequence", "reynolds", "mach", "alpha_deg")} for p in points + points_run
                        if not p["converged"]],
       "thrust_estimate": {"window": worst_window, "time_s": series[worst_window]["time_s"], "rpm": series[worst_window]["rpm"],
                           "thrust_n": series[worst_window]["thrust_n"], "first_order_abs_change_n": dT,
                           "method": "sum over the window's cell elements of q c ds * hypot(max|dcl|, max|dcd|), ds the larger gap "
                                     "to the neighbouring element centres; first-order estimate with induction and wake frozen"},
       "hinge": "cell elements are proximal only; the distal (hinge) loads change only through induction, not included here"}
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(json.dumps({k: out[k] for k in ("run_states_in_cell", "max_abs_delta_family_nodes_alpha_-2_to_0", "max_abs_delta_run_angles",
                                      "nonconverged", "thrust_estimate")}, indent=1))