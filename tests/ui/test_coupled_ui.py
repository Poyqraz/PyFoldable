"""Research workspace with the optional coupled section; no solver is executed."""
import json
import shutil
from pathlib import Path
import sys

import pytest
from streamlit.testing.v1 import AppTest

from pyfoldable.application import coupled_analysis as svc
from pyfoldable.coupled import postprocess, toolchain
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "application"))
from research_inert_support import store, bem  # noqa: E402

APP = Path(__file__).resolve().parents[2] / "apps/pyfoldable_research.py"
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "coupled" / "release_30w"
FIXTURE_RBF = FIXTURE.with_name("release_30w_rbf")


def app():
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    return at


def go(at, page):
    at.radio(key="research_page").set_value(page).run()
    assert not at.exception
    return at


def _no_toolchain(monkeypatch, tmp_path):
    monkeypatch.delenv(toolchain.ENV, raising=False)
    monkeypatch.setattr(toolchain, "DEFAULT", tmp_path / "absent.json")


def _forbid_runs(monkeypatch):
    def forbidden(*a, **k):
        pytest.fail("A coupled run must not start in this test")
    monkeypatch.setattr(svc, "start_run", forbidden)


def test_missing_toolchain_keeps_bem_route(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    calls = bem(monkeypatch)
    _no_toolchain(monkeypatch, tmp_path)
    _forbid_runs(monkeypatch)
    at = go(app(), "Analiz")
    assert any("araç zinciri kurulu değil" in i.value for i in at.info)
    assert not at.button(key="research_run").disabled
    at.button(key="research_run").click().run()
    assert not at.exception and len(calls) == 1


def test_inert_fixture_tables_cannot_feed_a_coupled_run(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    bem(monkeypatch)
    _forbid_runs(monkeypatch)
    fake = toolchain.Readiness("ready", "ok", toolchain.Toolchain(tmp_path / "tc.json", {}),
                               {"versions": {"dust_revision": "3b1d2e61f0b7", "mbdyn_revision": "55c86cc6ec7f",
                                             "precice_version": "2.5.0"}})
    monkeypatch.setattr(toolchain, "readiness", lambda **k: fake)
    at = go(app(), "Analiz")
    at.button(key="coupled_fill_demo").click().run()
    assert not at.exception
    assert any("hazırlanamadı" in w.value and "test kaydıdır" in w.value for w in at.warning)
    assert "_coupled_run" not in at.session_state


def _record(tmp_path, fixture=FIXTURE):
    run = tmp_path / "run"
    shutil.copytree(fixture, run)
    row = postprocess.build_result(run, participant_outcome="finished", exit_codes={}, extraction_ok=True)
    return row


def test_demo_values_persist_after_later_edits(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    bem(monkeypatch)
    _forbid_runs(monkeypatch)
    fake = toolchain.Readiness("ready", "ok", toolchain.Toolchain(tmp_path / "tc.json", {}),
                               {"versions": {"dust_revision": "3b1d2e61f0b7", "mbdyn_revision": "55c86cc6ec7f",
                                             "precice_version": "2.5.0"}})
    monkeypatch.setattr(toolchain, "readiness", lambda **k: fake)
    at = go(app(), "Analiz")
    at.button(key="coupled_fill_demo").click().run()
    at.number_input(key="coupled_release").set_value(0.03).run()
    at.number_input(key="coupled_ctl_duration").set_value(0.06).run()
    assert not at.exception
    assert at.number_input(key="coupled_mass").value == 30.0
    assert at.number_input(key="coupled_cg").value == 55.0
    assert "Gösterim varsayımı" in at.text_input(key="coupled_source").value


def test_local_run_directory_result_can_be_opened_read_only(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    bem(monkeypatch)
    _no_toolchain(monkeypatch, tmp_path)
    _forbid_runs(monkeypatch)
    runs = tmp_path / "runs"
    run = runs / "20261112T000000_fixture"
    shutil.copytree(FIXTURE, run)
    postprocess.build_result(run, participant_outcome="finished", exit_codes={}, extraction_ok=True)
    monkeypatch.setenv("PYFOLDABLE_COUPLED_RUNS", str(runs))
    at = go(app(), "Karşılaştırma / kayıtlar")
    at.button(key="coupled_local_open").click().run()
    assert not at.exception
    assert len(at.session_state["research_coupled_results"]) == 1


@pytest.mark.parametrize("fixture", [FIXTURE, FIXTURE_RBF], ids=["split_rigid", "continuous_rbf"])
def test_recorded_coupled_result_renders_every_view_and_survives_edits(tmp_path, monkeypatch, fixture):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    bem(monkeypatch)
    _no_toolchain(monkeypatch, tmp_path)
    _forbid_runs(monkeypatch)
    row = _record(tmp_path, fixture)
    at = app()
    raw = json.dumps(row, sort_keys=True, separators=(",", ":"))
    at.session_state["research_coupled_results"] = ((raw, False),)
    at.session_state["_coupled_active"] = (None, row["result_sha256"])
    go(at, "Sonuçlar")
    at.radio(key="research_results_kind").set_value("Dinamik bağlaşık").run()
    assert not at.exception
    assert any("Tamamlandı" in s.value for s in at.success)
    # the result is labelled as a short analysis window with its revolution counts
    assert any("devir" in c.value and "uzun süreli" in c.value for c in at.caption)
    # fixtures are shorter than one revolution: headline loads are labelled as last-window values
    labels = [m.label for m in at.metric]
    assert any(lbl.startswith("Son pencere") for lbl in labels) and not any("tam devir" in lbl for lbl in labels)
    for tab in ("Menteşe", "Yükler", "Güç", "Kapsam ve yakınsama", "Radyal", "3B oynatma"):
        at.radio(key="coupled_tab").set_value(tab).run()
        assert not at.exception, tab
    # a design edit never relabels or removes a history record opened from the archive
    go(at, "Tasarım").number_input(key="research_axial_800_rpm").set_value(2500.).run()
    assert not at.exception
    assert len(at.session_state["research_coupled_results"]) == 1
    go(at, "Karşılaştırma / kayıtlar")
    assert any("Dinamik bağlaşık kayıtlar" in m.value for m in at.markdown)


def test_compressed_coupled_record_is_recognised_for_import(tmp_path):
    from pyfoldable.application import research_ui
    row = _record(tmp_path, FIXTURE_RBF)
    archive = svc.record_archive_bytes(row)
    assert research_ui._artifact_class(archive) == "pyfoldable_coupled_result"
    assert research_ui._artifact_class(b"\x1f\x8bnot-a-gzip") is None


def test_import_peek_is_bounded_before_any_full_parse():
    from pyfoldable.application import research_design, research_ui
    big = research_design.MAX_SAVED_RESULT_BYTES + 1
    # a large upload that is not a canonical coupled record is never parsed in full
    other = b'{"artifact_class":"pyfoldable_research_result","x":"' + b"a" * big + b'"}'
    assert research_ui._artifact_class(other) is None
    # a large canonical coupled record is recognised from its leading key (the reader verifies everything)
    coupled = b'{"artifact_class":"pyfoldable_coupled_result",' + b" " * big + b"}"
    assert research_ui._artifact_class(coupled) == "pyfoldable_coupled_result"
    assert research_ui._artifact_class(b"{" * (svc.MAX_COUPLED_RESULT_BYTES + 1)) is None
    # deeply nested small input does not escape as an exception
    assert research_ui._artifact_class(b"[" * 200000) is None
