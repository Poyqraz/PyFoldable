"""Near-wake strength at the hinge radius vs span, continuous_rbf vs split_rigid main runs (flow companions)."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.home() / "projects/PyFoldable"))
from pyfoldable.application import coupled_analysis as s  # noqa: E402
from pyfoldable.coupled import flow  # noqa: E402

root = Path.home() / "projects/PyFoldable"
out = {}
for label, rid in (("continuous_rbf", "20261112T071200_20d4a1092d"), ("split_rigid", "20261112T005547_39a32f06ef")):
    row = s.load_result(root / "outputs/coupled_runs" / rid)
    fc = s.load_flow(root, row)
    g = row["run_definition"]["case"]["geometry"]
    h, R = g["hinge_radius_m"], g["tip_radius_m"]
    by_w = {r["window"]: r for r in row["series"]}
    rows = []
    for w in fc.windows.tolist():
        p, v, _ = fc.particles(w)
        near = p[:, 2] > -0.5 * R
        r = np.hypot(p[near, 0], p[near, 1])
        m = np.linalg.norm(v[near], axis=1)
        band = np.abs(r - h) < 0.015
        inboard = (r > g["first_aero_radius_m"]) & (r < h - 0.015)
        tip = np.abs(r - R) < 0.03
        vel = fc.plane_velocity[fc.index(w)]
        zk = int(np.argmin(np.abs(fc.plane_z + 0.5 * R)))
        rows.append({"window": w, "t": by_w[w]["time_s"], "theta": by_w[w]["theta_deg"][0], "thrust": by_w[w]["thrust_n"],
                     "n_particles": int(len(p)), "hinge_band_sum": float(m[band].sum()), "inboard_sum": float(m[inboard].sum()),
                     "tip_sum": float(m[tip].sum()), "total_near": float(m.sum()),
                     "max_down_w_at_half_R_below": float((-vel[zk, :, 2]).max())})
    out[label] = {"events": flow.events(row), "rows": rows}
    ev = flow.events(row)
    print(f"\n{label} {rid} events {ev}")
    print(" window  t[s]    theta  thrust  particles  hinge-band  inboard   tip      hinge/total  max(-w)@-R/2")
    for x in rows:
        if x["window"] in (144, 279, 288, 289, 309, 312, 338, 360, 432, 504, 576, 648, 720) or x["window"] in ev.values():
            print(f" {x['window']:5d} {x['t']:.4f} {x['theta']:7.2f} {x['thrust']:7.2f} {x['n_particles']:9d} {x['hinge_band_sum']:10.5f} "
                  f"{x['inboard_sum']:9.5f} {x['tip_sum']:8.5f} {x['hinge_band_sum']/max(x['total_near'],1e-12):10.3f} {x['max_down_w_at_half_R_below']:9.2f}")
json.dump(out, open(Path.home() / "pyf-work/runs/wake_compare.json", "w"), indent=1)
