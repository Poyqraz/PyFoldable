"""Kinematic study (no solver): DUST's RBF interpolation of the continuous lifting line at fold angles.

Reproduces DUST 3b1d2e61 rbf point motion (2 nearest nodes, anisotropic norm diag(1e-3,1,1e-3),
inverse-distance weights; each node moves rigidly with its segment) for the main case's mesh and
coupling nodes, folding the distal segment in-plane about the hinge axis (parallel to the shaft).
Reports, per fold angle, the worst junction-element distortion: chord-length change, element span
change, and the distal sweep angle (local span direction vs radial direction).
"""
import json
import sys

import h5py
import numpy as np

run = sys.argv[1]
r = json.load(open(f"{run}/result.json"))
nodes = [n for n in r["run_definition"]["coupling_nodes"] if n["blade"] == 0]
g = r["run_definition"]["case"]["geometry"]
h = g["hinge_radius_m"]
rr = np.array(h5py.File(f"{run}/dust/geo_input.h5", "r")["Components/Comp001/Geometry/rr"])  # (2*ns, 3) LE/TE pairs
local = np.array([n["local"] for n in nodes])
seg = [n["segment"] for n in nodes]
W = np.array([1e-3, 1.0, 1e-3])


def weights(p):
    d = np.sqrt(((p - local) ** 2 * W).sum(axis=1))
    idx = np.argsort(d, kind="stable")[:2]
    inv = 1.0 / np.maximum(d[idx], 1e-9)
    return idx, inv / inv.sum()


def rotz(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def moved(theta):
    hinge = np.array([0.0, h, 0.0])
    out = []
    for p in rr:
        idx, w = weights(p)
        acc = np.zeros(3)
        for j, wt in zip(idx, w):
            R = np.eye(3) if seg[j] == "proximal" else rotz(theta)
            x_node = local[j] if seg[j] == "proximal" else hinge + rotz(theta) @ (local[j] - hinge)
            acc += wt * (x_node + R @ (p - local[j]))
        out.append(acc)
    return np.array(out)


le0, te0 = rr[0::2], rr[1::2]
chord0 = np.linalg.norm(te0 - le0, axis=1)
span0 = np.linalg.norm(le0[1:] - le0[:-1], axis=1)
print(f"mesh: {len(le0)} stations, hinge r={h} m, node spacing {abs(local[1,1]-local[0,1]):.4f} m")
print(" fold[deg]  max|dchord|/c  at r[m]   max|dspan|/span  sweep distal[deg]  junction elems")
rows = []
for deg in (0, -5, -10, -15, -20, -30, -45, -60, -90):
    t = np.radians(deg)
    m = moved(t)
    le, te = m[0::2], m[1::2]
    dchord = np.abs(np.linalg.norm(te - le, axis=1) - chord0) / chord0
    dspan = np.abs(np.linalg.norm(le[1:] - le[:-1], axis=1) - span0) / span0
    k = int(np.argmax(dchord))
    # distal span direction vs local radial direction at mid-distal
    i0 = int(np.argmin(np.abs(le0[:, 1] - (h + 0.06))))
    sd = le[i0 + 1] - le[i0]
    radial = le[i0] / np.linalg.norm(le[i0])
    sweep = np.degrees(np.arccos(np.clip(abs(sd @ radial) / np.linalg.norm(sd), -1, 1)))
    junction = int(np.sum(dchord > 1e-9))
    rows.append({"fold_deg": deg, "max_chord_change": float(dchord.max()), "at_r": float(le0[k, 1]),
                 "max_span_change": float(dspan.max()), "distal_sweep_deg": float(sweep), "stations_distorted": junction})
    print(f" {deg:8.1f}   {dchord.max():12.4f}  {le0[k,1]:.4f}   {dspan.max():14.4f}   {sweep:12.1f}       {junction}")
json.dump(rows, open(sys.argv[2], "w"), indent=1)
