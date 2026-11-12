"""RBF-discrepancy diagnostic: compare two DUST runs step by step, before integrated loads.

Usage: rbf_diag.py <dust_dir_A> <dust_dir_B> [step ...]
Compares, at equal output index: time, component geometry rr (global), element 'ori',
evaluation-point relative velocity (up_x/y/z), vel_2d, alpha, and the implicit first wake
panel (PanelWake/WakePoints rows 1 and 2). Prints max abs differences and the per-element
spanwise distribution for the first component.
"""
import glob
import sys

import h5py
import numpy as np


def files(d):
    return sorted(glob.glob(f"{d}/Output/run_res_*.h5"))


def load(fn):
    out = {}
    with h5py.File(fn, "r") as f:
        out["t"] = float(np.array(f["time"]))
        comps = sorted(k for k in f["Components"] if k.startswith("Comp"))
        for c in comps:
            g = f["Components"][c]
            s = g["Solution"]
            out[c] = {
                "rr": np.array(g["Geometry/rr"]) if "Geometry" in g else None,
                "ori": np.array(g["Geometry/ori"]) if "Geometry" in g else None,
                "up": np.stack([np.array(s["up_x"]), np.array(s["up_y"]), np.array(s["up_z"])], axis=1),
                "vel_2d": np.array(s["vel_2d"]),
                "alpha": np.array(s["alpha"]),
                "dF": np.array(s["dF"]),
            }
        if "PanelWake" in f:
            out["wake"] = np.array(f["PanelWake/WakePoints"])
            out["wake_start"] = np.array(f["PanelWake/StartPoints"])
    return out


a_dir, b_dir = sys.argv[1], sys.argv[2]
steps = [int(x) for x in sys.argv[3:]] or [1, 2, 10, 100, -1]
fa, fb = files(a_dir), files(b_dir)
print("n files", len(fa), len(fb))
for k in steps:
    A, B = load(fa[k]), load(fb[k])
    print(f"\n=== index {k}: tA={A['t']:.6f} tB={B['t']:.6f} ({fa[k].split('/')[-1]})")
    for c in sorted(x for x in A if x.startswith("Comp")):
        if c not in B:
            continue
        a, b = A[c], B[c]
        drr = np.abs(a["rr"] - b["rr"]).max() if a["rr"] is not None and b["rr"] is not None else float("nan")
        dori = np.abs(a["ori"] - b["ori"]).max() if a["ori"] is not None and b["ori"] is not None else float("nan")
        dup = np.abs(a["up"] - b["up"]).max()
        dal = a["alpha"] - b["alpha"]
        print(f"{c}: |drr|max {drr:.3e} m  |dori|max {dori:.3e}  |dup|max {dup:.3e} m/s  "
              f"dalpha [{dal.min():+.4f},{dal.max():+.4f}] deg  sum dFz {a['dF'][:, 2].sum():.4f} {b['dF'][:, 2].sum():.4f}")
    if "wake" in A and "wake" in B and A["wake"].shape == B["wake"].shape:
        w1 = np.abs(A["wake"][0] - B["wake"][0]).max()
        la = np.linalg.norm(A["wake"][1] - A["wake"][0], axis=1)
        lb = np.linalg.norm(B["wake"][1] - B["wake"][0], axis=1)
        da = A["wake"][1] - A["wake"][0]
        db = B["wake"][1] - B["wake"][0]
        cosang = np.sum(da * db, axis=1) / np.maximum(la * lb, 1e-30)
        print(f"first wake row |d|max {w1:.3e} m; first-panel length A {la.min():.4e}..{la.max():.4e} "
              f"B {lb.min():.4e}..{lb.max():.4e}; max angle {np.degrees(np.arccos(np.clip(cosang, -1, 1))).max():.3f} deg")
    c = "Comp001"
    if c in A and c in B:
        a, b = A[c], B[c]
        line = (a["rr"] if a["rr"] is not None else b["rr"])[0::2]
        r = np.linalg.norm(0.5 * (line[:-1, :2] + line[1:, :2]), axis=1)
        print("  r[m]    alphaA  alphaB   dalpha   |up|A     |up|B    d(up) components")
        for i in range(len(a["alpha"])):
            du = a["up"][i] - b["up"][i]
            print(f"  {r[i]:.4f} {a['alpha'][i]:7.3f} {b['alpha'][i]:7.3f} {a['alpha'][i]-b['alpha'][i]:+8.4f} "
                  f"{np.linalg.norm(a['up'][i]):8.3f} {np.linalg.norm(b['up'][i]):8.3f}  {du[0]:+.3e} {du[1]:+.3e} {du[2]:+.3e}")
