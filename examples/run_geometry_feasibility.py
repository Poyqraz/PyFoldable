"""GEOM-01 offline scan: explicit draft only, no physical input or source mutation."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pyfoldable.application.design_draft import DesignDraftInputs, build_design_draft
from pyfoldable.application.geometry_search import prepare_geometry_search, run_geometry_search
from pyfoldable.core.profile_catalog import load_project_airfoil


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    draft = build_design_draft(root / "configs/designs/TIP_HINGED_250_CANONICAL.toml", DesignDraftInputs(
        diameter="250 mm", hub_radius="18 mm", hinge_radius="100 mm", blade_count=2,
        airfoil_id="NACA2412", chord_scale=1., twist_scale=1., preview_fold_angle="0 deg",
        angular_speed="7100 rpm", forward_speed="0 m/s", air_density="1.225 kg/m^3",
        dynamic_viscosity="1.81e-5 Pa*s", temperature="288.15 K", pressure="101325 Pa"),
        airfoil_definition=load_project_airfoil("NACA2412"))
    request = prepare_geometry_search(draft, hinge_radii_m=(.06, .07, .1), stowed_angles_deg=(-180., -150.))
    print(run_geometry_search(request).report_json, end="")
