"""DIAGNOSTIC ONLY (not retained as polar data, never admitted): convergence map of the pinned
local XFOIL 6.99 build over a Re x Mach grid for NACA2412, for two angle sequences.
Used to choose a declarable grid by solver convergence, not by coefficient values."""
import json, math, os, sys
from dataclasses import replace
from pathlib import Path
root = Path.home() / "projects/PyFoldable"
sys.path.insert(0, str(root))
from pyfoldable.core.profile_catalog import load_project_airfoil
from pyfoldable.core.providers import PolarGenerationRequest
from pyfoldable.providers import xfoil

os.environ["OSMAP"] = str(Path.home() / "pyf-work/xfoil/preflight/runtime/osmapDP.dat")
prov = xfoil.XfoilProvider(Path.home() / "pyf-work/xfoil/preflight/bin/xfoil", backend_version="6.99")
foil = load_project_airfoil("NACA2412")
res = [100000.0, 130000.0, 165000.0, 245000.0, 330000.0, 400000.0]
machs = [0.05, 0.07, 0.1, 0.2, 0.31, 0.36]
seqs = {"2deg": list(range(-6, 9, 2)), "1deg": list(range(-6, 9, 1))}
out = []
for sname, alphas in seqs.items():
    for it in (160,):
        for m in machs:
            for re in res:
                q = PolarGenerationRequest(airfoil=foil, alpha_rad=tuple(math.radians(a) for a in alphas), reynolds=re, mach=m,
                    n_crit=9.0, xtr_upper=1.0, xtr_lower=1.0, max_iterations=it, timeout_s=30.0, scenario_id="diagnostic", options={"repanel": True})
                r = prov.generate(q)
                bad = [round(math.degrees(p.alpha_rad)) for p in r.points if not p.usable]
                out.append({"seq": sname, "iter": it, "mach": m, "re": re, "complete": r.complete, "failed_alpha": bad})
                print(sname, it, m, int(re), "OK" if r.complete else f"FAIL {bad}", flush=True)
json.dump(out, open(sys.argv[1], "w"), indent=1)
