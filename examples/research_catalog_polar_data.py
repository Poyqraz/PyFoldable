"""Operator-only: freeze, capture and install one declared catalog-profile polar family.

Reuses the tested deploy-v3 operator (examples/research_deploy_polar_data.py: frozen plan, cold process per
cell, stop at the first failure, retained evidence, install only a complete family) with the profile, scenario
and version taken from the declaration (configs/polars/RESEARCH_AXIAL_800_CATALOG_*_V1.json).
Usage: research_catalog_polar_data.py --protocol <declaration> {freeze|capture|install} --evidence <dir> ...
"""
import importlib.util
import json
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location("research_deploy_operator", Path(__file__).with_name("research_deploy_polar_data.py"))
dep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dep)


def configure(protocol: Path):
    d = json.loads(Path(protocol).read_bytes())
    if not d["scenario_id"].startswith("research_axial_800_catalog_xfoil_v") or len(d["profiles_in_order"]) != 1:
        raise ValueError("Not a catalog-profile declaration")
    dep.PROTOCOL = Path(protocol).resolve()
    dep.PROFILES = tuple(d["profiles_in_order"])
    dep.VERSION = d["install_version"]
    dep.INSTALL_SCENARIO = d["scenario_id"]
    return dep


if __name__ == "__main__":
    i = sys.argv.index("--protocol")
    configure(Path(sys.argv[i + 1]))
    raise SystemExit(dep.main())
