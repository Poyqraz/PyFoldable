"""Comparison of two BEM records: name the exact differing fields and the action that gives a matched pair."""
from dataclasses import replace
from pathlib import Path

import pytest

from pyfoldable.application import provider_design_analysis as managed
from pyfoldable.application import research_design as research

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def runs():
    mp = pytest.MonkeyPatch()
    mp.setenv("PYFOLDABLE_PROVIDER_STORE", str(ROOT / "data/research_reference/axial_800_store"))
    repo = managed.application_provider_repository()
    fam = {f.family_id: f for f in repo.families}

    def run(profile, family_id, **inputs):
        active = research.build_research_design(ROOT, replace(research.defaults(ROOT), profile=profile, **inputs))
        return research.run_research(active, fam[family_id], repo, None)
    out = {"a": run("NACA0012", "research_axial_800_attached_xfoil_v1:NACA0012"),
           "b_v1": run("NACA2412", "research_axial_800_attached_xfoil_v1:NACA2412"),
           "b_v3": run("NACA2412", "research_axial_800_deploy_xfoil_v3:NACA2412"),
           "b_rpm": run("NACA2412", "research_axial_800_attached_xfoil_v1:NACA2412", rpm=2300.0)}
    yield out, repo
    mp.undo()


def _fields(diff):
    return {d["field"] for d in diff if not d["expected"]}


def test_matched_pair_differs_only_in_the_profile(runs):
    r, _ = runs
    diff = research.comparison_differences([r["a"], r["b_v1"]])
    assert _fields(diff) == set()
    assert {d["field"] for d in diff if d["expected"]} == {"Profil", "Profil koordinatları"}


def test_a_different_polar_family_is_named_with_its_build_and_grid(runs):
    r, _ = runs
    diff = research.comparison_differences([r["a"], r["b_v3"]])
    assert {"Polar veri sürümü", "XFOIL derlemesi", "Polar ızgarası (Re)", "Polar ızgarası (Mach)"} <= _fields(diff)
    row = next(d for d in diff if d["field"] == "Polar veri sürümü")
    assert row["first"] == "2026-11-11-v1" and row["second"] == "2026-11-12-deploy-v3"


def test_operating_point_differences_are_named(runs):
    r, _ = runs
    assert "Devir [RPM]" in _fields(research.comparison_differences([r["a"], r["b_rpm"]]))


def test_matching_action_points_at_the_profile_version_that_shares_the_contract(runs):
    r, repo = runs
    action = research.matching_action([r["a"], r["b_v3"]], repo)
    assert action["profile"] == "NACA2412" and action["version_label"] == "2026-11-11-v1"
    assert action["content_sha256"] == next(f.stored_version.content_sha256 for f in repo.families
                                            if f.family_id == "research_axial_800_attached_xfoil_v1:NACA2412")
    assert research.matching_action([r["a"], r["b_v1"]], repo) is None          # already matched
    assert research.matching_action([r["a"], r["b_rpm"]], repo) is None         # same data, only the operating point differs


@pytest.mark.parametrize("quantity,key", [("thrust", "thrust_n"), ("power", "shaft_power_w")])
def test_second_record_is_moved_to_the_first_records_thrust_or_power_by_shaft_speed(runs, quantity, key):
    r, repo = runs
    out = research.match_operating_point(ROOT, r["b_v1"], repo, quantity, r["a"]["aerodynamics"][key])
    target = r["a"]["aerodynamics"][key]
    assert out["row"]["aerodynamics"]["status"] == "success"
    assert out["row"]["aerodynamics"][key] == pytest.approx(target, rel=2e-3)
    assert out["row"]["inputs"]["rpm"] == out["rpm"] < 2400.0               # NACA2412 makes more thrust at 2400
    assert out["row"]["inputs"]["inflow_m_s"] == r["b_v1"]["inputs"]["inflow_m_s"]
    assert len(out["runs"]) <= 8 and all(run["rpm"] > 0 for run in out["runs"])
    assert research.comparison_differences([r["a"], out["row"]])          # rpm differs and is named
    assert "Devir [RPM]" in _fields(research.comparison_differences([r["a"], out["row"]]))


def test_a_target_outside_the_admitted_data_fails_closed(runs):
    r, repo = runs
    with pytest.raises(ValueError, match="left the admitted data"):
        research.match_operating_point(ROOT, r["b_v1"], repo, "thrust", 20 * r["a"]["aerodynamics"]["thrust_n"])


def test_a_record_already_at_the_target_needs_no_second_run(runs):
    r, repo = runs
    out = research.match_operating_point(ROOT, r["b_v1"], repo, "thrust", r["b_v1"]["aerodynamics"]["thrust_n"])
    assert out["rpm"] == 2400.0 and len(out["runs"]) == 1


def test_the_exact_data_version_is_required_not_only_the_family(runs):
    import copy
    import json
    r, repo = runs
    row = copy.deepcopy(r["b_v1"])
    report = json.loads(row["aerodynamics"]["report_text"])
    report["request"]["provider_design_admission"]["stored_version"]["content_sha256"] = "0" * 64
    row["aerodynamics"]["report_text"] = json.dumps(report)
    with pytest.raises(ValueError, match="exact data version"):
        research.match_operating_point(ROOT, row, repo, "thrust", 30.0)
