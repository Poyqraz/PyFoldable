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
