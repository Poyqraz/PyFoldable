"""Geometry/timing check: preprocessed geometry equality, and coupled per-step global rr vs the
standalone reference geometry rotated by psi (best-fit psi reported against Omega*t)."""
import glob
import sys

import h5py
import numpy as np

sa, cp = sys.argv[1], sys.argv[2]
omega = float(sys.argv[3]) if len(sys.argv) > 3 else 251.32741228718345


def geo(d):
    out = {}
    with h5py.File(f"{d}/geo_input.h5", "r") as g:
        def visit(name, obj):
            if isinstance(obj, h5py.Dataset):
                out[name] = np.array(obj)
        g.visititems(visit)
    return out


A, B = geo(sa), geo(cp)
common = sorted(set(A) & set(B))
print("geo_input datasets only in standalone:", sorted(set(A) - set(B)))
print("geo_input datasets only in coupled:   ", sorted(set(B) - set(A)))
for k in common:
    a, b = A[k], B[k]
    if a.dtype.kind in "fi" and a.shape == b.shape:
        d = np.abs(a.astype(float) - b.astype(float)).max() if a.size else 0.0
        if d > 0:
            print(f"  DIFF {k}: max {d:.3e}")
    elif a.shape != b.shape:
        print(f"  SHAPE {k}: {a.shape} vs {b.shape}")
    elif a.tobytes() != b.tobytes():
        print(f"  BYTES {k}: {a!r} vs {b!r}")
print("preprocessed geometry compared:", len(common), "datasets")

rr0 = A["Components/Comp001/Geometry/rr"]  # blade-1 reference frame == rotor frame at psi=0
files = sorted(glob.glob(f"{cp}/Output/run_res_*.h5"))


def rot(psi):
    c, s = np.cos(psi), np.sin(psi)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


for fn in files[:4] + files[20:21]:
    with h5py.File(fn, "r") as f:
        t = float(np.array(f["time"]))
        rr = np.array(f["Components/Comp001/Geometry/rr"])
    # best-fit psi from the tip LE point
    i = len(rr0) - 2
    psi = np.arctan2(rr[i, 1], rr[i, 0]) - np.arctan2(rr0[i, 1], rr0[i, 0])
    psi = (psi + np.pi) % (2 * np.pi) - np.pi
    resid = np.abs(rr - rr0 @ rot(psi).T).max()
    print(f"{fn.split('/')[-1]} t={t:.6f} psi_fit={np.degrees(psi):+.4f} deg  Omega*t={np.degrees(omega * t):.4f} deg  "
          f"(psi-Omega t)={np.degrees(psi - omega * t):+.4f} deg  rigid-fit residual {resid:.3e} m")
