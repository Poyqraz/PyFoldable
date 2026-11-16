"""Write one declared capture protocol per catalog profile from the deploy-v3 declaration (same solver settings,
pinned executable and angle sequence); only the profile, scenario, version and the grid chosen from the
convergence pre-screen differ. Usage: make_declarations.py"""
import json
from pathlib import Path

ROOT = Path.home() / "projects/PyFoldable"
base = json.loads((ROOT / "configs/polars/RESEARCH_AXIAL_800_DEPLOY_V3.json").read_text())
GRIDS = {  # chosen so that no pre-screen failure lies on a declared node (reports/catalog_polars_20261116)
    "NACA0012": ([100000.0, 165000.0, 245000.0, 330000.0, 400000.0], [0.07, 0.1, 0.31]),
    "NACA23012": ([100000.0, 165000.0, 245000.0, 330000.0], [0.07, 0.1, 0.31, 0.36]),
    "NACA4415": ([165000.0, 245000.0, 330000.0], [0.07, 0.1, 0.31, 0.36]),
    "NACA63-412": ([100000.0, 165000.0, 245000.0, 330000.0, 400000.0], [0.07, 0.1, 0.31]),
    "NACA4412": ([100000.0, 245000.0, 400000.0], [0.07, 0.1, 0.31, 0.36]),
}
for profile, (re, mach) in GRIDS.items():
    slug = profile.replace("-", "").lower()
    d = {k: v for k, v in base.items() if k not in ("supersedes", "deployment_targets")}
    d.update(scenario_id=f"research_axial_800_catalog_xfoil_v1_{slug}", profiles_in_order=[profile], reynolds=re, mach=mach,
             install_version=f"2026-11-16-catalog-v1-{slug}",
             budget={**base["budget"], "max_provider_calls": len(re) * len(mach)},
             grid_selection=("Levels chosen from the convergence pre-screen of this executable "
                             "(reports/catalog_polars_20261116/convergence_prescreen.json) so that no non-converging "
                             "state is a declared node; selection by solver convergence, not by coefficient values."),
             relation_to_v1="Separate family per profile; same executable, settings and angle sequence as deploy-v3.",
             scope=f"Attached-flow {profile} section grid for the 800 mm research layout. Unqualified numerical evidence; "
                   "more XFOIL coverage does not establish validity in separated flow.")
    path = ROOT / f"configs/polars/RESEARCH_AXIAL_800_CATALOG_{slug.upper()}_V1.json"
    path.write_text(json.dumps(d, indent=2) + "\n")
    print(path.name, len(re) * len(mach))

# V2 for the 4 %-camber profiles: their zero-lift angle is near -4 deg, so the V1 captures stopped on the
# retained lift-sign rule (CL(-4) < 0). The angle sequence is shifted to -8..6 deg (8 angles; the BEM operating
# point near 5 deg stays inside) and the lift-sign rule is declared at the angles that bound the scan.
SHIFTED = {
    "NACA4415": ([165000.0, 245000.0, 330000.0, 400000.0], [0.07, 0.1, 0.31]),
    "NACA4412": ([100000.0, 165000.0, 245000.0, 400000.0], [0.07, 0.1, 0.36]),
}
for profile, (re, mach) in SHIFTED.items():
    slug = profile.replace("-", "").lower()
    v1 = ROOT / f"configs/polars/RESEARCH_AXIAL_800_CATALOG_{slug.upper()}_V1.json"
    d = json.loads(v1.read_text())
    d.update(scenario_id=f"research_axial_800_catalog_xfoil_v2_{slug}", reynolds=re, mach=mach,
             alpha_deg_in_order=[-8, -6, -4, -2, 0, 2, 4, 6],
             lift_sign_check={"negative_deg": [-8, -6], "positive_deg": [2, 4, 6]},
             install_version=f"2026-11-16-catalog-v2-{slug}",
             budget={**d["budget"], "max_provider_calls": len(re) * len(mach)},
             grid_selection=("Levels chosen from the convergence pre-screen of this executable with the shifted sequence "
                             "(reports/catalog_polars_20261116/convergence_prescreen_high_camber_shifted.json)."),
             supersedes={"failed_declarations": [{"protocol": f"configs/polars/{v1.name}",
                                                  "outcome": "stopped at cell index 1: CL(-4 deg) >= 0 (zero-lift angle near "
                                                             "-4 deg) violates the retained lift-sign rule"}]})
    path = ROOT / f"configs/polars/RESEARCH_AXIAL_800_CATALOG_{slug.upper()}_V2.json"
    path.write_text(json.dumps(d, indent=2) + "\n")
    print(path.name, len(re) * len(mach))
