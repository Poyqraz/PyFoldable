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
    with pytest.raises(ValueError, match="veri"):
        research.match_operating_point(ROOT, r["b_v1"], repo, "thrust", 20 * r["a"]["aerodynamics"]["thrust_n"])


@pytest.fixture(scope="module")
def catalog():
    mp = pytest.MonkeyPatch()
    mp.setenv("PYFOLDABLE_PROVIDER_STORE", str(ROOT / "data/research_reference/axial_800_store"))
    repo = managed.application_provider_repository()
    fam = {f.family_id: f for f in repo.families}

    def run(profile, family_id, **inputs):
        active = research.build_research_design(ROOT, replace(research.defaults(ROOT), profile=profile, **inputs))
        return research.run_research(active, fam[family_id], repo, None)
    out = {"0012": run("NACA0012", "research_axial_800_catalog_xfoil_v1_naca0012:NACA0012"),
           "63412": run("NACA63-412", "research_axial_800_catalog_xfoil_v1_naca63412:NACA63-412"),
           "4412": run("NACA4412", "research_axial_800_catalog_xfoil_v2_naca4412:NACA4412")}
    yield out, repo
    mp.undo()


def test_catalog_profiles_with_the_same_build_grid_and_settings_are_matched(catalog):
    r, repo = catalog
    pair = [r["0012"], r["63412"]]
    assert research.compare_results(pair)["matched_numerical_comparison"] is True
    assert research.matching_action(pair, repo) is None
    # the per-profile scenario label stays visible as information
    assert "Polar senaryosu" in _fields(research.comparison_differences(pair))


def test_catalog_profiles_with_really_different_grids_stay_unmatched(catalog):
    r, repo = catalog
    pair = [r["4412"], r["0012"]]
    result = research.compare_results(pair)
    assert result["matched_numerical_comparison"] is False and result["comparison_class"] == "unmatched"
    assert research.matching_action(pair, repo) == {"available": False}


def test_trim_reaches_a_target_inside_the_data_after_overshooting_the_mach_edge(catalog):
    r, repo = catalog
    out = research.match_operating_point(ROOT, r["0012"], repo, "thrust", 40.0)
    assert 2500.0 < out["rpm"] < 2550.0
    assert out["row"]["aerodynamics"]["thrust_n"] == pytest.approx(40.0, rel=1e-3)
    assert out["row"]["operating_point_match"] == {"quantity": "thrust", "target": 40.0, "rel_tol": 1e-3,
                                                   "runs": out["runs"]}
    assert research.read_saved_result(research.saved_result_json(out["row"]).encode()) == out["row"]


def test_trim_far_outside_the_data_fails_closed_in_turkish(catalog):
    r, repo = catalog
    with pytest.raises(ValueError, match="ulaşılamıyor") as info:
        research.match_operating_point(ROOT, r["0012"], repo, "thrust", 20 * r["0012"]["aerodynamics"]["thrust_n"])
    assert "RPM" in str(info.value)


def test_equal_thrust_pair_is_classified_and_exported_with_the_trim(runs):
    import csv
    import io
    import json
    r, repo = runs
    target = r["a"]["aerodynamics"]["thrust_n"]
    trimmed = research.match_operating_point(ROOT, r["b_v1"], repo, "thrust", target)["row"]
    result = research.compare_results([r["a"], trimmed])
    assert result["comparison_class"] == "equal_thrust"
    assert result["matched_numerical_comparison"] is False          # the operating conditions really differ
    assert research.compare_results([trimmed, r["a"]])["comparison_class"] == "equal_thrust"
    assert research.compare_results([r["a"], r["b_v1"]])["comparison_class"] == "matched"
    assert research.compare_results([r["a"], r["b_rpm"]])["comparison_class"] == "unmatched"
    document, table = research.comparison_exports([r["a"], trimmed], result)
    assert json.loads(document)["assessment"]["comparison_class"] == "equal_thrust"
    assert json.loads(document)["results"][1]["operating_point_match"]["target"] == target
    rows = list(csv.DictReader(io.StringIO(table)))
    assert {row["comparison_class"] for row in rows} == {"equal_thrust"}
    assert rows[1]["trim_quantity"] == "thrust" and float(rows[1]["trim_target"]) == target


def test_a_saved_trim_that_contradicts_its_result_is_rejected(runs):
    r, repo = runs
    row = research.match_operating_point(ROOT, r["b_v1"], repo, "thrust", r["a"]["aerodynamics"]["thrust_n"])["row"]
    body = {k: v for k, v in row.items() if k != "result_sha256"}
    body["operating_point_match"] = {**body["operating_point_match"], "target": 2 * body["operating_point_match"]["target"]}
    forged = {**body, "result_sha256": research._digest(body)}
    with pytest.raises(ValueError):
        research.read_saved_result(research.saved_result_json(forged).encode())


def test_legacy_comparison_status_is_derived_from_the_records(runs):
    from pyfoldable.application.profile_bem_comparison import comparison_document
    r, _ = runs
    matched = comparison_document([r["a"]["aerodynamics"], r["b_v1"]["aerodynamics"]], evidence_class="caller_supplied_unqualified")
    assert matched["genuine_comparison_status"] == "MATCHED_RETAINED_PROVIDER_CONTRACT"
    other = comparison_document([r["a"]["aerodynamics"], r["b_v3"]["aerodynamics"]], evidence_class="caller_supplied_unqualified")
    assert other["genuine_comparison_status"] == "BLOCKED_no_shared_retained_provider_contract"
    assert "does not contain" not in other["genuine_comparison_note"]


def test_readiness_margins_measure_the_distance_to_the_grid_edges(catalog):
    import math
    _, repo = catalog
    family = next(f for f in repo.families if f.family_id == "research_axial_800_deploy_xfoil_v3:NACA2412")
    active = research.build_research_design(ROOT, replace(research.defaults(ROOT), rpm=1500.0))
    initial = research.initial_query_ranges(active)
    assert research.declared_grid_covers_initial(family, initial)
    (alpha_low, _), _, _ = research.grid_margins(family, initial)
    assert 0 < math.degrees(alpha_low) < 1                                # 1500 RPM sits 0.6° above the α floor


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
    with pytest.raises(ValueError, match="tam veri sürümü"):
        research.match_operating_point(ROOT, row, repo, "thrust", 30.0)
