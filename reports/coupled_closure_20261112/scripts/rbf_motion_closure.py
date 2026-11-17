"""Rigid-motion reproduction during fold motion: DUST's written lifting-line points (result k) vs the
points PyFoldable reconstructs from the exchanged MBDyn coupling-node states of window k+1 with
DUST's RBF weights (independent re-implementation in postprocess.rbf_weights).
Also: blade-segment rigidity (each node moves with its body: |X_i - (x_body + R_body (l_i - l_body))|).
Usage: rbf_motion_closure.py <run dir> [stride]
"""
import glob
import json
import sys

import h5py
import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path.home() / "projects/PyFoldable"))
run = sys.argv[1]
stride = int(sys.argv[2]) if len(sys.argv) > 2 else 10
r = json.load(open(f"{run}/result.json"))
nodes = r["run_definition"]["coupling_nodes"]
ex = r["window_exchange"]
states = {s["window"]: s["nodes"] for s in r["node_states"]}

# postprocess re-implementation without importing the pyfoldable package (needs scipy)
WN = (1e-3, 1.0, 1e-3)


def rbf_weights(local, p):
    d = [np.sqrt(sum(w * (a - b) ** 2 for w, a, b in zip(WN, p, n))) for n in local]
    idx = sorted(range(len(local)), key=lambda i: (d[i], i))[:2]
    inv = [1.0 / max(d[i], 1e-9) for i in idx]
    s = sum(inv)
    return idx, [v / s for v in inv]


def rotm(p):
    p = np.asarray(p, float); th = np.linalg.norm(p)
    if th < 1e-15:
        return np.eye(3)
    k = p / th; K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K


files = sorted(glob.glob(f"{run}/dust/Output/run_res_*.h5"))
with h5py.File(f"{run}/dust/geo_input.h5", "r") as g:
    comps = sorted(k for k in g["Components"] if k.startswith("Comp"))
    ref = {c: np.array(g[f"Components/{c}/Geometry/rr"]) for c in comps}
names = {}
with h5py.File(files[0], "r") as f:
    for c in comps:
        names[c] = f[f"Components/{c}/CompName"][()].decode().strip()
worst_geo = worst_rig = 0.0
theta_seen = []
for w in range(1, len(ex) + 1, stride):
    X = [np.array(x) for x in ex[w - 1]["position"]]
    R = [rotm(p) for p in ex[w - 1]["rotation"]]
    st = states[w]
    with h5py.File(files[w - 1], "r") as f:
        for c in comps:
            own = [i for i, n in enumerate(nodes) if n["dust_component"] == names[c]]
            local = [nodes[i]["local"] for i in own]
            rr_dust = np.array(f[f"Components/{c}/Geometry/rr"])
            for p_ref, p_dust in zip(ref[c], rr_dust):
                idx, wts = rbf_weights(local, p_ref)
                p = sum(wt * (X[own[j]] + R[own[j]] @ (p_ref - np.array(local[j]))) for j, wt in zip(idx, wts))
                worst_geo = max(worst_geo, np.abs(p - p_dust).max())
    for i, n in enumerate(nodes):
        b = st[str(n["body_label"])]
        bl = next(m for m in r["run_definition"]["bodies"] if m["mbdyn_label"] == n["body_label"])
        pred = np.array(b["x"]) + rotm(b["phi"]) @ (np.array(n["local"]) - np.array(bl["local"]))
        worst_rig = max(worst_rig, np.abs(pred - X[i]).max())
    theta_seen.append(r["series"][w - 1]["theta_deg"][0])
print(f"{run.split('/')[-1]}: windows checked {len(theta_seen)} (theta {min(theta_seen):.2f}..{max(theta_seen):.2f} deg)")
print(f"  DUST written line/TE points vs RBF reconstruction from exchanged node states: max {worst_geo:.3e} m")
print(f"  exchanged coupling-node position vs rigid attachment to MBDyn body node:      max {worst_rig:.3e} m")
