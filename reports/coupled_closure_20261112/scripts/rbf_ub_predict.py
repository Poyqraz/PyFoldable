"""Hypothesis test: the rbf lifting-line branch evaluates the element body velocity `ub` at the
leading-line midpoint (loc_cen = mean(ver1, ver2)); standalone DUST evaluates it at the control
point ctr_pt = cen + tang_cen*chord/2 (rigid coupling: vertex mean).

The projected relative velocity `up` (in the nor/tang_cen plane) is recovered exactly from the
output: up_x, up_y are written, |up| = vel_2d, and up_z follows from |up| (sign: relative flow
downward). Frames are reconstructed as in calc_geo_data_liftlin and validated (up . bnorm = 0,
atan2 vs reported alpha up to the 2-D circulation correction). The predicted alpha change from
moving the ub evaluation point is compared with the observed coupled-minus-standalone change.

Usage: rbf_ub_predict.py <standalone dust dir> <coupled dust dir> [index] [omega]
(index 0 = first output: no wake history, both blades at the same relative attitude)
"""
import glob
import sys

import h5py
import numpy as np

sa, cp = sys.argv[1], sys.argv[2]
k = int(sys.argv[3]) if len(sys.argv) > 3 else 0
omega = float(sys.argv[4]) if len(sys.argv) > 4 else 251.32741228718345
ez = np.array([0.0, 0.0, 1.0])

with h5py.File(f"{sa}/geo_input.h5", "r") as g:
    rr = np.array(g["Components/Comp001/Geometry/rr"])
    ee = np.array(g["Components/Comp001/Geometry/ee"]) - 1


def frames(rr):
    out = []
    for e in ee:
        v = rr[e]
        cen = 0.5 * (v[0] + v[1])
        nor = np.cross(v[2] - v[0], v[3] - v[1])
        nor /= np.linalg.norm(nor)
        ev = [v[(i + 1) % 4] - v[i] for i in range(4)]
        tang = ev[1] - ev[3]
        tang /= np.linalg.norm(tang)
        bn = np.cross(tang, nor)
        bn /= np.linalg.norm(bn)
        chord = 0.5 * (np.linalg.norm(ev[1]) + np.linalg.norm(ev[3]))
        ctr = cen + tang * chord / 2
        nor = np.cross(bn, tang)
        nor /= np.linalg.norm(nor)
        out.append(dict(cen=cen, ctr=ctr, nor=nor, tang=tang, bn=bn, vmean=v.mean(axis=0), chord=chord))
    return out


def rotz(p):
    c, s = np.cos(p), np.sin(p)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def load(d, with_geom):
    fn = sorted(glob.glob(f"{d}/Output/run_res_*.h5"))[k]
    with h5py.File(fn, "r") as f:
        s = f["Components/Comp001/Solution"]
        out = {n: np.array(s[n]) for n in ("up_x", "up_y", "alpha", "vel_2d", "vel_outplane", "aero_coeff")}
        out["t"] = float(np.array(f["time"]))
        out["rr"] = np.array(f["Components/Comp001/Geometry/rr"]) if with_geom else None
    return out


A, B = load(sa, False), load(cp, True)
frA = frames(rr @ rotz(omega * A["t"]).T)          # standalone: reference geometry at psi = Omega t
frB = frames(B["rr"])                               # coupled: geometry written by DUST at this step


def up_vec(D, i):
    ux, uy, u = D["up_x"][i], D["up_y"][i], D["vel_2d"][i]
    uz = -np.sqrt(max(u * u - ux * ux - uy * uy, 0.0))
    return np.array([ux, uy, uz])


def alpha_of(u, f):
    return np.degrees(np.arctan2(u @ f["nor"], u @ f["tang"]))


print(f"index {k}: t_SA={A['t']:.6f} t_CP={B['t']:.6f}")
print(" i   r      |up.bn|SA  |up.bn|CP   ageo_SA-a_SA ageo_CP-a_CP | da_geo_obs  da_pred(ub@cen)  da_pred(ub@vertex-mean)  dvout_obs dvout_pred")
for i in range(len(ee)):
    fa, fb = frA[i], frB[i]
    ua, ub_ = up_vec(A, i), up_vec(B, i)
    ga, gb = alpha_of(ua, fa), alpha_of(ub_, fb)
    # rbf ub at cen instead of ctr_pt: V_rel = ... - ub  -> dV = -(ub(cen) - ub(ctr))
    dV = -(np.cross(omega * ez, fa["cen"]) - np.cross(omega * ez, fa["ctr"]))
    dVm = -(np.cross(omega * ez, fa["vmean"]) - np.cross(omega * ez, fa["ctr"]))
    pred = alpha_of(ua + dV, fa) - ga
    predm = alpha_of(ua + dVm, fa) - ga
    r = np.hypot(*fa["cen"][:2])
    print(f"{i:2d} {r:.4f}  {abs(ua @ fa['bn']):.2e}  {abs(ub_ @ fb['bn']):.2e}   {ga - A['alpha'][i]:+.4f}      {gb - B['alpha'][i]:+.4f}    |"
          f"  {gb - ga:+.4f}     {pred:+.4f}           {predm:+.6f}            {B['vel_outplane'][i]-A['vel_outplane'][i]:+.3f}   {dV @ fa['bn']:+.3f}")

print("\nin-plane components (blade frame):  n.up SA  n.up CP  d_obs  d_pred | t.up SA  t.up CP  d_obs  d_pred | Gamma SA CP | cl SA CP")
with h5py.File(sorted(glob.glob(f"{sa}/Output/run_res_*.h5"))[k], "r") as f:
    gA = np.array(f["Components/Comp001/Solution/Gamma_old"]) if "Gamma_old" in f["Components/Comp001/Solution"] else None
with h5py.File(sorted(glob.glob(f"{cp}/Output/run_res_*.h5"))[k], "r") as f:
    gB = np.array(f["Components/Comp001/Solution/Gamma_old"])
for i in range(len(ee)):
    fa, fb = frA[i], frB[i]
    ua, ub_ = up_vec(A, i), up_vec(B, i)
    dV = -(np.cross(omega * ez, fa["cen"]) - np.cross(omega * ez, fa["ctr"]))
    print(f"{i:2d}  {ua@fa['nor']:+8.4f} {ub_@fb['nor']:+8.4f} {ub_@fb['nor']-ua@fa['nor']:+.4f} {dV@fa['nor']:+.4f} |"
          f" {ua@fa['tang']:+8.3f} {ub_@fb['tang']:+8.3f} {ub_@fb['tang']-ua@fa['tang']:+.4f} {dV@fa['tang']:+.4f} |"
          f" {gA[i]:+.4f} {gB[i]:+.4f} | {A['aero_coeff'][0][i]:.4f} {B['aero_coeff'][0][i]:.4f}")
