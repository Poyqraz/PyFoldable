"""DIAGNOSTIC ONLY (not retained as polar data, never admitted): convergence pre-screen of the pinned local
XFOIL 6.99 build for the catalog profiles without retained data, on the deploy-v3 grid levels and the
declared 2-degree cold sequence. Chooses a declarable grid by solver convergence, not by coefficients.
Usage: convergence_prescreen.py <out.json> [profile ...]"""
import json
import math
import os
import sys
from pathlib import Path

root = Path.home() / "projects/PyFoldable"
sys.path.insert(0, str(root))
from pyfoldable.core.profile_catalog import load_project_airfoil  # noqa: E402
from pyfoldable.core.providers import PolarGenerationRequest  # noqa: E402
from pyfoldable.providers import xfoil  # noqa: E402

os.environ["OSMAP"] = str(Path.home() / "pyf-work/xfoil/preflight/runtime/osmapDP.dat")
prov = xfoil.XfoilProvider(Path.home() / "pyf-work/xfoil/preflight/bin/xfoil", backend_version="6.99")
profiles = sys.argv[2:] or ["NACA23012", "NACA4415", "NACA63-412", "NACA4412"]
res = [100000.0, 165000.0, 245000.0, 330000.0, 400000.0]
machs = [0.07, 0.1, 0.31, 0.36]
alphas = [int(a) for a in os.environ.get("PRESCREEN_ALPHAS", "-6,-4,-2,0,2,4,6,8").split(",")]
out = []
for prof in profiles:
    foil = load_project_airfoil(prof)
    for m in machs:
        for re in res:
            q = PolarGenerationRequest(airfoil=foil, alpha_rad=tuple(math.radians(a) for a in alphas), reynolds=re, mach=m,
                                       n_crit=9.0, xtr_upper=1.0, xtr_lower=1.0, max_iterations=160, timeout_s=30.0,
                                       scenario_id="diagnostic", options={"repanel": True})
            r = prov.generate(q)
            bad = [round(math.degrees(p.alpha_rad)) for p in r.points if not p.usable]
            out.append({"profile": prof, "mach": m, "re": re, "complete": r.complete, "failed_alpha": bad})
            print(prof, m, int(re), "OK" if r.complete else f"FAIL {bad}", flush=True)
            json.dump(out, open(sys.argv[1], "w"), indent=1)
