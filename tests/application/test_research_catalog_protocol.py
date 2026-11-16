"""Catalog-profile polar declarations: prelaunch checks only (no XFOIL constructor or solver)."""
import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("research_catalog_operator_test", ROOT / "examples/research_catalog_polar_data.py")
cat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cat)
DECLS = sorted((ROOT / "configs/polars").glob("RESEARCH_AXIAL_800_CATALOG_*_V*.json"))
PRESCREEN = [*json.loads((ROOT / "reports/catalog_polars_20261116/convergence_prescreen.json").read_text()),
             *json.loads((ROOT / "reports/catalog_polars_20261116/convergence_prescreen_naca0012.json").read_text())]
SHIFTED = json.loads((ROOT / "reports/catalog_polars_20261116/convergence_prescreen_high_camber_shifted.json").read_text())


def test_every_catalog_profile_without_a_wide_grid_has_a_declaration():
    profiles = {json.loads(p.read_text())["profiles_in_order"][0] for p in DECLS}
    assert profiles == {"NACA0012", "NACA23012", "NACA4415", "NACA63-412", "NACA4412"}
    assert {p.stem for p in DECLS if p.stem.endswith("_V2")} == {"RESEARCH_AXIAL_800_CATALOG_NACA4412_V2",
                                                                 "RESEARCH_AXIAL_800_CATALOG_NACA4415_V2"}


@pytest.mark.parametrize("path", DECLS, ids=lambda p: p.stem)
def test_declaration_freezes_with_deploy_settings_and_avoids_prescreen_failures(path):
    d = json.loads(path.read_text())
    base = json.loads((ROOT / "configs/polars/RESEARCH_AXIAL_800_DEPLOY_V3.json").read_text())
    shifted = d["alpha_deg_in_order"] != base["alpha_deg_in_order"]
    if shifted:   # V2 of the 4 %-camber profiles: -8..6 deg with the lift-sign rule declared at -8/-6 and 2/4/6
        assert d["alpha_deg_in_order"] == [-8, -6, -4, -2, 0, 2, 4, 6] and len(d["alpha_deg_in_order"]) == 8
        assert d["lift_sign_check"] == {"negative_deg": [-8, -6], "positive_deg": [2, 4, 6]}
        assert d["supersedes"]["failed_declarations"]
    for key in ("n_crit", "xtr_upper", "xtr_lower", "max_iterations", "timeout_s", "options",
                "provider", "executable_sha256", "osmap_sha256", "preflight_archive_sha256", "build_record_sha256"):
        assert d[key] == base[key], key
    assert d["physical_qualification"] is False
    dep = cat.configure(path)
    plan, files = dep.make_plan()                 # also checks that the grid covers the conditional BEM scan
    cells = len(d["reynolds"]) * len(d["mach"])
    assert cells == d["budget"]["max_provider_calls"] == len(files) // 2
    profile = d["profiles_in_order"][0]
    failed = {(r["mach"], r["re"]) for r in (SHIFTED if shifted else PRESCREEN) if r["profile"] == profile and not r["complete"]}
    assert not failed & {(m, re) for m in d["mach"] for re in d["reynolds"]}
    assert dep.VERSION == d["install_version"] and dep.INSTALL_SCENARIO == d["scenario_id"]


def test_launcher_refuses_a_non_catalog_declaration():
    with pytest.raises(ValueError, match="catalog"):
        cat.configure(ROOT / "configs/polars/RESEARCH_AXIAL_800_DEPLOY_V3.json")


def test_lift_sign_rule_is_declared_per_profile_and_defaults_to_the_retained_rule():
    import math
    base = cat.dep.base
    cambered = {math.radians(a): cl for a, cl in ((-8, -0.25), (-6, -0.05), (-4, 0.02), (2, 0.6), (4, 0.8), (6, 1.0))}
    assert not base.lift_signs_ok(cambered, (-6.0, -4.0), (2.0, 4.0, 6.0))       # retained rule: CL(-4) < 0
    assert base.lift_signs_ok(cambered, (-8.0, -6.0), (2.0, 4.0, 6.0))
    d = json.loads((ROOT / "configs/polars/RESEARCH_AXIAL_800_DEPLOY_V3.json").read_text())
    assert cat.dep.lift_policy(d) == ((-6.0, -4.0), (4.0, 6.0, 8.0))           # absent key: the retained rule


def test_scan_guard_bound_follows_the_declared_negative_lift_angle():
    from pyfoldable.core import BEMRotorSettings, load_design_config
    base = cat.dep.base
    design = load_design_config(ROOT / "configs/designs/RESEARCH_AXIAL_800_V1.toml")
    deep = base.scan_guard(design, BEMRotorSettings(annulus_count=40), negative_guard_deg=-6.0)
    default = base.scan_guard(design, BEMRotorSettings(annulus_count=40))
    assert all(a["alpha_rad"][0] < b["alpha_rad"][0] for a, b in zip(deep, default))
    assert all(r["alpha_rad"][0] <= math.radians(-6.0) for r in deep)


EVIDENCE = sorted((ROOT / "reports/catalog_polars_20261116").glob("evidence_*"))


@pytest.mark.parametrize("folder", EVIDENCE, ids=lambda p: p.name)
def test_retained_catalog_evidence_reverifies_against_its_declaration(folder):
    name = folder.name.removeprefix("evidence_")
    dep = cat.configure(ROOT / f"configs/polars/RESEARCH_AXIAL_800_CATALOG_{name}.json")
    dep.require_plan(folder)
    profile = dep.PROFILES[0]
    cells = folder / profile
    assert dep.base.load(cells / "checksums.json") == dep.base.phase_files(cells)
    outcome = dep.base.load(cells / "outcome.json")
    # the two V1 captures of the 4 %-camber profiles are retained failures; every other one is complete
    assert outcome["complete"] is (name not in ("NACA4412_V1", "NACA4415_V1"))
