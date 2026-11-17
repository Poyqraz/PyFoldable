"""Tests never write into the owner's results folder; the local store keeps only validated, sealed files."""
import json
from pathlib import Path

import pytest

from pyfoldable.application import coupled_analysis
from pyfoldable.application import provider_design_analysis as managed
from pyfoldable.application import research_design as research

ROOT = Path(__file__).resolve().parents[1]


def test_saved_results_go_to_a_temporary_folder_during_tests():
    owner_default = Path(research.__file__).resolve().parents[2] / "outputs" / "research_results"
    assert research.results_root().resolve() != owner_default.resolve()


@pytest.fixture(scope="module")
def row():
    mp = pytest.MonkeyPatch()
    mp.setenv("PYFOLDABLE_PROVIDER_STORE", str(ROOT / "data/research_reference/axial_800_store"))
    repo = managed.application_provider_repository()
    fam = next(f for f in repo.families if f.family_id == "research_axial_800_attached_xfoil_v1:NACA2412")
    yield research.run_research(research.build_research_design(ROOT, research.defaults(ROOT)), fam, repo, None)
    mp.undo()


def test_store_writes_once_under_the_configured_folder_and_skips_tampered_files(row, tmp_path, monkeypatch):
    monkeypatch.setenv("PYFOLDABLE_RESULTS", str(tmp_path / "res"))
    path = research.store_local_result(row)
    assert path.parent == tmp_path / "res" and research.store_local_result(row) == path
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["inputs"]["rpm"] = 9999.0
    (tmp_path / "res" / ("f" * 64 + ".json")).write_text(json.dumps(tampered), encoding="utf-8")
    (tmp_path / "res" / "broken.json").write_text("{", encoding="utf-8")
    listed = research.local_results()
    assert [r["result_sha256"] for r in listed] == [row["result_sha256"]]
    assert not list((tmp_path / "res").glob("*.tmp"))


def test_a_malformed_run_folder_is_skipped(tmp_path, monkeypatch):
    monkeypatch.delenv(coupled_analysis.RUNS_ENV, raising=False)
    base = coupled_analysis.runs_root(tmp_path)
    for name, request in (("20260101T000000_bad", '{"aero_admission": "{not json"}'),
                          ("20260101T000001_list", '[1, 2]'),
                          ("20260101T000002_ok", '{"mechanics": {"initial_fold_rad": -0.349}}')):
        (base / name).mkdir(parents=True)
        (base / name / "status.json").write_text('{"state": "completed"}')
        (base / name / "request.json").write_text(request)
    assert [r["run_id"] for r in coupled_analysis.local_run_summaries(tmp_path)] == ["20260101T000002_ok"]
