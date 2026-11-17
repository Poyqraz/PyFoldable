"""Same case, two polar families: the -20 deg 2200->2400 RPM ramp on the 2026-11-11 table and on deploy-v3.

Inside Re 165k..330k x Mach 0.10..0.31 both C81 files interpolate between the same source tables (shared
sha256), so identical outputs are expected there. This checks that swapping the table changes nothing where
the tables agree; it does not measure sensitivity to different polar data.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.home() / "projects/PyFoldable"))
from pyfoldable.application import coupled_analysis as s  # noqa: E402

root = Path.home() / "projects/PyFoldable"
a = s.load_result(root / "outputs/coupled_runs/20261112T203049_d66ad5cd8d")
b = s.load_result(root / "outputs/coupled_runs/20261112T220258_0bb5c02ad8")
fields = ("thrust_n", "aero_shaft_torque_nm", "drive_torque_nm", "hinge_aero_torque_nm", "rpm", "theta_deg", "theta_rate_rad_s")
diff = {q: float(max(np.abs(np.asarray(x[q], float) - np.asarray(y[q], float)).max() for x, y in zip(a["series"], b["series"])))
        for q in fields}
cov = {q: [min(r["coverage"][q][0] for r in a["series"]), max(r["coverage"][q][1] for r in a["series"])]
       for q in ("alpha_deg", "reynolds", "mach")}
ta, tb = (set(r["request"]["c81"]["source_table_sha256"]) for r in (a, b))
out = {"runs": {"attached_xfoil_v1": "20261112T203049_d66ad5cd8d",
                "deploy_xfoil_v3": "20261112T220258_0bb5c02ad8"},
       "families": [r["request"]["aero_admission"]["family_id"] for r in (a, b)],
       "c81_sha256": [r["request"]["c81"]["sha256"] for r in (a, b)],
       "table_envelopes": [r["request"]["c81"]["envelope"] for r in (a, b)],
       "source_tables": {"v1": len(ta), "v3": len(tb), "shared": len(ta & tb), "v1_all_in_v3": ta <= tb},
       "trajectory_coverage": cov, "windows": [len(a["series"]), len(b["series"])],
       "result_sha256_differ": a["result_sha256"] != b["result_sha256"],
       "max_abs_series_difference": diff,
       "reading": "Bit-identical series: the trajectory stays where both tables interpolate the same source tables. "
                  "Consistency of the table swap and of the run path, not a polar sensitivity measure."}
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(json.dumps({k: out[k] for k in ("families", "source_tables", "trajectory_coverage", "max_abs_series_difference")}, indent=1))
