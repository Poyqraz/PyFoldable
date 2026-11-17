"""Each catalog profile through the application services with its retained family: one BEM run at the default
800 mm design point, and the coupled preparation (C81 table from the admission, trajectory check) for a
-20 deg release at 2400 RPM. Usage: six_profile_check.py <out.json>"""
import json
import math
import os
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path.home() / "projects/PyFoldable"
os.environ.setdefault("PYFOLDABLE_PROVIDER_STORE", str(ROOT / "data/research_reference/axial_800_store"))
sys.path.insert(0, str(ROOT))
from pyfoldable.application import coupled_analysis as svc  # noqa: E402
from pyfoldable.application import provider_design_analysis as managed  # noqa: E402
from pyfoldable.application import research_design as research  # noqa: E402
from pyfoldable.coupled import c81  # noqa: E402
from pyfoldable.coupled.model import CoupledControls, CoupledMechanics, build_case  # noqa: E402

repo = managed.application_provider_repository()
out = []
for fam in sorted(repo.families, key=lambda f: f.family_id):
    profile = fam.family_id.split(":")[1]
    active = research.build_research_design(ROOT, replace(research.defaults(ROOT), profile=profile))
    row = research.run_research(active, fam, repo, None)
    a = row["aerodynamics"]
    rec = {"family": fam.family_id, "version": fam.stored_version.version_label, "profile": profile, "bem_status": a["status"],
           "thrust_n": a.get("thrust_n"), "torque_nm": a.get("torque_nm"), "power_w": a.get("shaft_power_w"),
           "failure": a.get("failure_reason")}
    prepared = research.prepare_aero(active, fam, repo)
    table = c81.build_c81(c81.admitted_tables(json.loads(prepared.admission_json)))
    mech = CoupledMechanics(distal_mass_kg=0.030, distal_cg_from_hinge_m=0.055, distal_inertia_cg_kg_m2=3.0e-5,
                            stop_stiffness_nm_per_rad=500.0, stop_restitution=0.5, initial_fold_rad=math.radians(-20),
                            release_time_s=0.05, source="check", declaration_kind="demonstration_assumption")
    case = build_case(active, mech, CoupledControls(azimuth_step_deg=2.5, duration_s=0.125))
    appl = svc.trajectory_applicability(case, table.envelope)
    rec.update(table_re=table.envelope["reynolds"], table_mach=table.envelope["mach"], alpha=table.envelope["alpha_deg"],
               coupled_re_ok=appl["reynolds_ok"], coupled_mach_ok=appl["mach_ok"], coupled_alpha_ok=appl["alpha_ok"],
               swing_mach_ok=appl["swing"]["mach_ok"])
    out.append(rec)
    print(json.dumps(rec, default=str))
json.dump(out, open(sys.argv[1], "w"), indent=1, default=str)
