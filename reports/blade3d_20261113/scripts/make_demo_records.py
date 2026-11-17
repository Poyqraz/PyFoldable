"""Demo inputs for the lofted 3-D blade (no new solver beyond one BEM call; the coupled record is retained).

1. A genuine saved BEM result: the same service call the application's "BEM'i çalıştır" button makes
   (research_design.run_research with the application's retained provider repository), for the default
   800 mm research design with NACA2412 and the 2026-11-11 retained family; written as the application's
   saved-result JSON, which "Karşılaştırma / kayıtlar → Önceki sonuç JSON'unu aç" opens.
2. The fold-contact report of that design (relief and hinge-plane split) as JSON.
Usage: make_demo_records.py <out_dir>
"""
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path.home() / "projects/PyFoldable"
sys.path.insert(0, str(ROOT))
from pyfoldable.application import provider_design_analysis as managed  # noqa: E402
from pyfoldable.application import research_design as research  # noqa: E402
from pyfoldable.application import blade_geometry as bg  # noqa: E402
from pyfoldable.visualization import fold_interference as fi  # noqa: E402

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
active = research.build_research_design(ROOT, replace(research.defaults(ROOT), profile="NACA2412"))
repo = managed.application_provider_repository()
fam = next(f for f in repo.families if f.family_id == "research_axial_800_attached_xfoil_v1:NACA2412")
row = research.run_research(active, fam, repo, None)
assert row["aerodynamics"]["status"] == "success", row["aerodynamics"].get("failure_reason")
text = research.saved_result_json(row)
(out / "bem_naca2412_axial800_2026-11-11-v1.json").write_text(text if isinstance(text, str) else text.decode())
research.read_saved_result((out / "bem_naca2412_axial800_2026-11-11-v1.json").read_bytes())   # reopens like the UI
foil = next(f for f in active.design.airfoils if f.id == "NACA2412")
spec = bg.spec_from_active(active, foil)
rep = {j: asdict(fi.fold_contacts(spec, joint=j, fold_min_deg=-180.0)) for j in ("relief", "plane")}
(out / "fold_contacts_axial800_naca2412.json").write_text(json.dumps(rep, indent=1, default=float))
print("thrust", row["aerodynamics"]["thrust_n"], "torque", row["aerodynamics"]["torque_nm"],
      "interference-free relief", rep["relief"]["interference_free_deg"], "plane", rep["plane"]["interference_free_deg"])
