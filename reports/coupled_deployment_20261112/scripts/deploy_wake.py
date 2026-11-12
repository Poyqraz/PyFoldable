"""Wake through deployment (flow companions): near-wake strength by band and slipstream speed at event frames."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.home() / "projects/PyFoldable"))
from pyfoldable.application import coupled_analysis as s  # noqa: E402
from pyfoldable.coupled import flow  # noqa: E402

root = Path.home() / "projects/PyFoldable"
runs = {"main_-5_const": "20261112T071200_20d4a1092d", "m20_ramp_2200_2400": "20261112T203049_d66ad5cd8d",
        "m15_ramp_2200_2400": "20261112T203052_6971a5d10d", "m20_const_2400_partial": "20261112T191618_02b58b9c61"}
out = {}
for label, rid in runs.items():
    row = s.load_result(root / "outputs/coupled_runs" / rid)
    d = s.local_run_dir(root, row)
    try:
        fc = flow.load(d, row)
    except flow.FlowCompanionError:
        fc = s.build_flow(root, row)
    g = row["run_definition"]["case"]["geometry"]
    h, R = g["hinge_radius_m"], g["tip_radius_m"]
    ev = flow.events(row)
    by = {r["window"]: r for r in row["series"]}
    rows = []
    for w in fc.windows.tolist():
        p, v, _ = fc.particles(w)
        near = p[:, 2] > -0.5 * R
        r = np.hypot(p[near, 0], p[near, 1]); m = np.linalg.norm(v[near], axis=1)
        vel = fc.plane_velocity[fc.index(w)]
        zk = int(np.argmin(np.abs(fc.plane_z + 0.5 * R)))
        rows.append({"window": w, "t": by[w]["time_s"], "rpm": by[w]["rpm"], "theta": by[w]["theta_deg"][0],
                     "theta_rate": by[w]["theta_rate_rad_s"][0], "thrust": by[w]["thrust_n"],
                     "particles": int(len(p)), "hinge_band": float(m[np.abs(r - h) < 0.015].sum()),
                     "tip_band": float(m[np.abs(r - R) < 0.03].sum()), "near_total": float(m.sum()),
                     "max_down_w_half_R": float((-vel[zk, :, 2]).max())})
    out[label] = {"run_id": rid, "events": ev, "frames": len(rows), "rows": rows}
    print(f"\n{label} ({len(rows)} frames) events {ev}")
    print("  window  t[s]   rpm    theta  thdot   thrust  parts  hinge   tip    hinge%  -w@-R/2")
    keys = {ev.get(k) for k in ev} | {ev.get("release", 0) - 1}
    for x in rows:
        if x["window"] in keys or x["window"] in (144, 360, 432, 576):
            print(f"  {x['window']:5d} {x['t']:.4f} {x['rpm']:6.1f} {x['theta']:7.2f} {x['theta_rate']:6.1f} {x['thrust']:7.2f} {x['particles']:6d} "
                  f"{x['hinge_band']:6.3f} {x['tip_band']:6.3f} {100 * x['hinge_band'] / max(x['near_total'], 1e-12):6.2f} {x['max_down_w_half_R']:7.2f}")
json.dump(out, open(sys.argv[1], "w"), indent=1)
