"""Results survive the session: BEM results are written locally and listed again; local dynamic runs are
listed in readable form and open with one click (no run IDs, no recalculation)."""
import json
import shutil
import sys
from pathlib import Path

from pyfoldable.application import research_design as research
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "application"))
from research_inert_support import bem, store  # noqa: E402
from test_coupled_ui import FIXTURE_RBF, _forbid_runs, _no_toolchain  # noqa: E402
from test_research_release_ui import ANALYSIS, RECORDS, RESULTS, app, go  # noqa: E402

from pyfoldable.coupled import postprocess  # noqa: E402


def test_local_result_store_writes_once_and_lists_valid_files(tmp_path, monkeypatch):
    monkeypatch.setenv("PYFOLDABLE_RESULTS", str(tmp_path / "results"))
    row = json.loads((Path(__file__).resolve().parents[2] / "reports/blade3d_20261113/bem_naca2412_axial800_2026-11-11-v1.json").read_text())
    path = research.store_local_result(row)
    assert path.name == row["result_sha256"] + ".json" and research.store_local_result(row) == path
    (tmp_path / "results" / "broken.json").write_text("{")
    listed = research.local_results()
    assert [r["result_sha256"] for r in listed] == [row["result_sha256"]]          # tampered/broken files are skipped
    assert listed[0]["profile"] == "NACA2412" and abs(listed[0]["thrust_n"] - 43.647) < 1e-3


def test_bem_run_is_kept_and_reopened_in_a_new_session(tmp_path, monkeypatch):
    monkeypatch.setenv("PYFOLDABLE_RESULTS", str(tmp_path / "results"))
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    calls = bem(monkeypatch)
    at = go(app(), ANALYSIS)
    at.button(key="research_run").click().run()
    assert len(list((tmp_path / "results").glob("*.json"))) == 1
    fresh = go(app(), RECORDS)                                   # a new session: nothing in its history yet
    assert "bilgisayarda saklanan" in " ".join(m.value for m in fresh.markdown).lower()
    fresh.button(key="research_local_open").click().run()
    assert not fresh.exception and len(calls) == 1               # reopened, not recalculated
    assert len(fresh.session_state["research_saved_results"]) == 1


def test_local_dynamic_runs_are_listed_readably_and_open_with_one_click(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    bem(monkeypatch)
    _no_toolchain(monkeypatch, tmp_path)
    _forbid_runs(monkeypatch)
    runs = tmp_path / "runs"
    run = runs / "20261112T000000_fixture"
    shutil.copytree(FIXTURE_RBF, run)
    postprocess.build_result(run, participant_outcome="finished", exit_codes={}, extraction_ok=True)
    monkeypatch.setenv("PYFOLDABLE_COUPLED_RUNS", str(runs))
    at = go(app(), RECORDS)
    table = next(d.value for d in at.dataframe if "Profil" in d.value.columns and "Katlanma [°]" in d.value.columns)
    assert list(table["Profil"]) == ["NACA2412"] and list(table["Durum"]) == ["Tamamlandı"]
    at.button(key="coupled_local_open").click().run()
    assert not at.exception
    assert at.radio(key="research_page").value == RESULTS
    assert at.radio(key="research_results_kind").value == "Dinamik bağlaşık"


def test_analysis_page_states_what_each_method_needs_for_this_case(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    bem(monkeypatch)
    _no_toolchain(monkeypatch, tmp_path)
    at = go(app(), ANALYSIS)
    table = next(d.value for d in at.dataframe if "Yöntem" in d.value.columns)
    rows = {r["Yöntem"]: r for r in table.to_dict("records")}
    steady = next(v for k, v in rows.items() if k.startswith("Kararlı BEM"))
    dynamic = next(v for k, v in rows.items() if k.startswith("Zamana bağlı"))
    assert steady["Durum"] == "Hazır"
    assert dynamic["Durum"] == "Araç zinciri gerekli" and "DUST" in dynamic["Sonraki adım"]
