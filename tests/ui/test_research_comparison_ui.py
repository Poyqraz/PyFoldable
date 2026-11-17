"""Records page: an unmatched comparison names its differing fields and offers the matching action."""
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from pyfoldable.application import provider_design_analysis as managed
from pyfoldable.application import research_design as research

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_research_release_ui import RECORDS, app, go  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def pair(monkeypatch):
    monkeypatch.setenv("PYFOLDABLE_PROVIDER_STORE", str(ROOT / "data/research_reference/axial_800_store"))
    repo = managed.application_provider_repository()
    fam = {f.family_id: f for f in repo.families}

    def run(profile, family_id):
        active = research.build_research_design(ROOT, replace(research.defaults(ROOT), profile=profile))
        return research.run_research(active, fam[family_id], repo, None)
    return (run("NACA0012", "research_axial_800_attached_xfoil_v1:NACA0012"),
            run("NACA2412", "research_axial_800_deploy_xfoil_v3:NACA2412"))


def test_unmatched_comparison_lists_differences_and_offers_the_matched_rerun(pair):
    at = app()
    at.session_state["research_saved_results"] = tuple((research.saved_result_json(r), True) for r in pair)
    go(at, RECORDS)
    at.selectbox(key="research_compare_first").select_index(1).run()      # index works on Streamlit 1.40 and later
    at.selectbox(key="research_compare_second").select_index(1).run()
    assert not at.exception
    table = next(d.value for d in at.dataframe if "Alan" in d.value.columns)
    assert {"Polar veri sürümü", "XFOIL derlemesi"} <= set(table["Alan"])
    button = at.button(key="research_compare_match")
    assert "NACA2412" in button.label and "2026-11-11-v1" in button.label
    button.click().run()
    assert not at.exception
    assert at.radio(key="research_page").value == "Analiz"
    assert at.selectbox(key="research_version_NACA2412").value == next(
        f.stored_version.content_sha256 for f in managed.application_provider_repository().families
        if f.family_id == "research_axial_800_attached_xfoil_v1:NACA2412")
    go(at, "Tasarım")
    assert at.selectbox(key="research_profile").value == "NACA2412"


def test_second_record_can_be_moved_to_equal_thrust_and_is_saved_as_a_new_record(pair):
    at = app()
    at.session_state["research_saved_results"] = tuple((research.saved_result_json(r), True) for r in pair)
    go(at, RECORDS)
    at.selectbox(key="research_compare_first").select_index(1).run()      # index works on Streamlit 1.40 and later
    at.selectbox(key="research_compare_second").select_index(1).run()
    at.radio(key="research_compare_trim_quantity").set_value("thrust").run()
    at.button(key="research_compare_trim").click().run()
    assert not at.exception
    assert len(at.session_state["research_saved_results"]) == 3            # originals kept, new record added
    new = json.loads(at.session_state["research_saved_results"][-1][0])
    target = pair[0]["aerodynamics"]["thrust_n"]
    assert new["aerodynamics"]["thrust_n"] == pytest.approx(target, rel=2e-3)
    assert new["inputs"]["rpm"] < 2400 and new["inputs"]["profile"] == "NACA2412"
    assert any("eşit itki" in m.value.lower() for m in at.success)
