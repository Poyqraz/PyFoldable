"""Rotor thrust/torque from DUST result files (same arithmetic for standalone and coupled runs).

thrust = sum dF_z; torque about +z (drive sense) Q = -sum[(c x dF)_z + dMom_z], c = element
leading-line midpoint (mean of ver1, ver2) at that step (coupled: written geometry; standalone:
reference geometry of each blade rotated by Omega*t). Averages over the last n revolutions.
Usage: dust_loads.py <dust dir> [steps_per_rev=72] [n_revs=1] [omega] [time_offset_steps]
time_offset_steps: 1 for coupled runs (geometry at label t + dt), 0 for standalone.
"""
import glob
import sys

import h5py
import numpy as np

d = sys.argv[1]
spr = int(sys.argv[2]) if len(sys.argv) > 2 else 72
nrev = int(sys.argv[3]) if len(sys.argv) > 3 else 1
omega = float(sys.argv[4]) if len(sys.argv) > 4 else 251.32741228718345
off = int(sys.argv[5]) if len(sys.argv) > 5 else 0

with h5py.File(f"{d}/geo_input.h5", "r") as g:
    comps = sorted(k for k in g["Components"] if k.startswith("Comp"))
    ref = {c: (np.array(g[f"Components/{c}/Geometry/rr"]), np.array(g[f"Components/{c}/Geometry/ee"]) - 1) for c in comps}
blade_angle = {c: np.pi * i for i, c in enumerate(comps)}  # two blades, 180 deg apart (reference files)


def rotz(p):
    c, s = np.cos(p), np.sin(p)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


files = sorted(glob.glob(f"{d}/Output/run_res_*.h5"))
T, Q, tt = [], [], []
for fn in files:
    with h5py.File(fn, "r") as f:
        t = float(np.array(f["time"]))
        tot_t = tot_q = 0.0
        for c in comps:
            s = f[f"Components/{c}/Solution"]
            dF, dM = np.array(s["dF"]), np.array(s["dMom"])
            if f"Components/{c}/Geometry/rr" in f:
                rr = np.array(f[f"Components/{c}/Geometry/rr"])
            else:
                rr = ref[c][0] @ rotz(omega * (t + off * 0) + blade_angle[c]).T
            ee = ref[c][1]
            cen = 0.5 * (rr[ee[:, 0]] + rr[ee[:, 1]])
            tot_t += dF[:, 2].sum()
            tot_q += -(np.cross(cen, dF)[:, 2].sum() + dM[:, 2].sum())
        T.append(tot_t); Q.append(tot_q); tt.append(t)
T, Q = np.array(T), np.array(Q)
n = spr * nrev
print(f"{d}: {len(files)} outputs, t_last={tt[-1]:.5f}")
print(f"  last {nrev} rev ({n} outputs): thrust {T[-n:].mean():.4f} N  torque {Q[-n:].mean():.5f} N m  "
      f"power {Q[-n:].mean() * omega:.2f} W   (thrust min/max {T[-n:].min():.3f}/{T[-n:].max():.3f})")
