"""Compare the deploy-v3 capture (local gfortran 11.4 build) with the retained 2026-11-11 NACA2412
family (gfortran 14.2 build) at the shared Re x Mach cells and angles. Evidence, not admission."""
import json, math, sys
from pathlib import Path
root = Path.home() / "projects/PyFoldable"
sys.path.insert(0, str(root))
from pyfoldable.application import provider_design_analysis as managed
from pyfoldable.application.provider_record_store import ProviderRecordStore

ev = Path(sys.argv[1])
new = {}
for p in sorted((ev / "NACA2412").glob("result-*.json")):
    d = json.loads(p.read_bytes())
    r = d["request"]
    new[(r["reynolds"], r["mach"])] = {round(math.degrees(x["alpha_rad"]), 6): x for x in d["points"]}
with ProviderRecordStore(root / "data/research_reference/axial_800_store") as store:
    repo = store.load_repository()
fam = next(f for f in repo.families if f.family_id.endswith(":NACA2412") and f.family_id.startswith("research_axial_800_attached_xfoil_v1"))
rows, worst = [], {"cl": 0.0, "cd_rel": 0.0, "cm": 0.0}
for req, cell in zip(fam.requests, fam.cells):
    res = managed._result(managed._document(cell.result_json))
    key = (req.reynolds, req.mach)
    if key not in new:
        continue
    for pt in res.points:
        a = round(math.degrees(pt.alpha_rad), 6)
        q = new[key][a]
        dcl, dcd, dcm = q["cl"] - pt.cl, q["cd"] - pt.cd, q["cm"] - pt.cm
        rows.append({"reynolds": key[0], "mach": key[1], "alpha_deg": a, "cl_v1": pt.cl, "cl_new": q["cl"],
                     "cd_v1": pt.cd, "cd_new": q["cd"], "cm_v1": pt.cm, "cm_new": q["cm"]})
        worst["cl"] = max(worst["cl"], abs(dcl)); worst["cd_rel"] = max(worst["cd_rel"], abs(dcd) / pt.cd)
        worst["cm"] = max(worst["cm"], abs(dcm))
out = {"retained_family": fam.family_id, "retained_store_version": fam.stored_version.content_sha256,
       "shared_cells": sorted({(r["reynolds"], r["mach"]) for r in rows}), "points": len(rows),
       "max_abs_delta_cl": worst["cl"], "max_rel_delta_cd": worst["cd_rel"], "max_abs_delta_cm": worst["cm"],
       "identical_points": sum(r["cl_v1"] == r["cl_new"] and r["cd_v1"] == r["cd_new"] and r["cm_v1"] == r["cm_new"] for r in rows),
       "rows": rows}
json.dump(out, open(sys.argv[2], "w"), indent=1)
print({k: v for k, v in out.items() if k != "rows"})
