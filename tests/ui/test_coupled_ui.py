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
    for tab in ("Menteşe", "Yükler", "Güç", "Kapsam ve yakınsama", "Radyal", "3B oynatma", "Mühendislik değerlendirmesi"):
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


def test_xz_coupled_record_is_recognised_for_import(tmp_path):
    from pyfoldable.application import research_ui
    row = _record(tmp_path, FIXTURE_RBF)
    assert research_ui._artifact_class(svc.record_xz_bytes(row)) == "pyfoldable_coupled_result"
    assert research_ui._artifact_class(svc.XZ_MAGIC + b"not-an-xz-stream") is None


def test_restore_upload_limit_is_the_server_wide_limit(monkeypatch):
    # Streamlit's upload endpoint caps every request at server.maxUploadSize (a per-widget
    # max_upload_size only changes the browser-side check), so the bound in force is the server's.
    import streamlit as st
    from pyfoldable.application import research_ui
    real = st.get_option
    monkeypatch.setattr(st, "get_option", lambda k: 7 if k == "server.maxUploadSize" else real(k))
    assert research_ui.restore_upload_limit_bytes() == 7 * 1024 * 1024


def test_archive_fit_is_conservative_at_both_bounds(monkeypatch):
    import streamlit as st
    from pyfoldable.application import research_ui
    real = st.get_option
    monkeypatch.setattr(st, "get_option", lambda k: 5 if k == "server.maxUploadSize" else real(k))
    limit = 5 * 1024 * 1024
    assert research_ui.restore_archive_fits(4_603_084)            # the main record's .json.xz
    assert not research_ui.restore_archive_fits(5_641_917)        # the main record's .json.gz
    assert not research_ui.restore_archive_fits(limit)            # multipart framing counts on older servers
    assert research_ui.restore_archive_fits(limit - research_ui.MULTIPART_MARGIN_BYTES)
    monkeypatch.setattr(st, "get_option", lambda k: 64 if k == "server.maxUploadSize" else real(k))
    assert not research_ui.restore_archive_fits(svc.MAX_COUPLED_ARCHIVE_BYTES + 1)  # archive bound still applies


def test_restore_uploader_never_claims_more_than_the_server_accepts(tmp_path, monkeypatch):
    import streamlit as st
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    bem(monkeypatch)
    _no_toolchain(monkeypatch, tmp_path)
    seen = []
    real = st.file_uploader

    def spy(*a, **k):
        if k.get("key") == "research_restore":
            seen.append(k)
        return real(*a, **k)
    monkeypatch.setattr(st, "file_uploader", spy)
    at = go(app(), "Karşılaştırma / kayıtlar")
    assert not at.exception and seen
    assert all("max_upload_size" not in k for k in seen)
    assert set(seen[-1]["type"]) == {"json", "gz", "xz"}
    assert any("MB" in c.value and ".json.xz" in c.value for c in at.caption)

def test_xz_archive_is_prepared_only_on_request(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    bem(monkeypatch)
    _no_toolchain(monkeypatch, tmp_path)
    _forbid_runs(monkeypatch)
    row = _record(tmp_path, FIXTURE_RBF)
    calls = []
    real = svc.record_xz_bytes
    monkeypatch.setattr(svc, "record_xz_bytes", lambda r: calls.append(r["result_sha256"]) or real(r))
    at = app()
    raw = json.dumps(row, sort_keys=True, separators=(",", ":"))
    at.session_state["research_coupled_results"] = ((raw, False),)
    at.session_state["_coupled_active"] = (None, row["result_sha256"])
    go(at, "Sonuçlar")
    at.radio(key="research_results_kind").set_value("Dinamik bağlaşık").run()
    assert not at.exception and calls == []  # nothing expensive on render
    at.button(key="coupled_prepare_xz").click().run()
    assert not at.exception and calls == [row["result_sha256"]]
    assert any(".json.xz" in c.value and "MB" in c.value for c in at.caption)
    at.radio(key="coupled_tab").set_value("Yükler").run()  # a rerun reuses the prepared archive
    assert not at.exception and calls == [row["result_sha256"]]


FLOW_FIXTURE = FIXTURE.with_name("flow_30w_rbf")
FLOW_RUN_ID = "20261112T074237_2a6ad5bd14"


def _flow_app(tmp_path, monkeypatch, *, with_run_folder=True, with_companion=True):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    bem(monkeypatch)
    _no_toolchain(monkeypatch, tmp_path)
    _forbid_runs(monkeypatch)
    runs = tmp_path / "runs"
    runs.mkdir()
    if with_run_folder:
        shutil.copytree(FLOW_FIXTURE, runs / FLOW_RUN_ID)
        if not with_companion:
            shutil.rmtree(runs / FLOW_RUN_ID / "flow")
    monkeypatch.setenv("PYFOLDABLE_COUPLED_RUNS", str(runs))
    row = svc.read_saved_coupled_result((FLOW_FIXTURE / "result.json").read_bytes())
    at = app()
    at.session_state["research_coupled_results"] = ((json.dumps(row, sort_keys=True, separators=(",", ":")), False),)
    at.session_state["_coupled_active"] = (None, row["result_sha256"])
    go(at, "Sonuçlar")
    at.radio(key="research_results_kind").set_value("Dinamik bağlaşık").run()
    at.radio(key="coupled_tab").set_value("Akış ve tepki").run()
    assert not at.exception
    return at


def test_flow_tab_shows_wake_and_response_of_the_same_window_and_jumps_to_events(tmp_path, monkeypatch):
    at = _flow_app(tmp_path, monkeypatch)
    assert any("Hesaplanan (DUST)" in c.value and "Çözülmeyen" in c.value for c in at.caption)
    assert any("RBF" in c.value for c in at.caption)
    assert at.select_slider(key="coupled_flow_window").value == 13  # opens at the first stop contact
    labels = {m.label: m.value for m in at.metric}
    assert "Girdap parçacığı" in labels and int(labels["Girdap parçacığı"]) > 0
    at.selectbox(key="coupled_flow_event").set_value("second_swing_min").run()
    assert not at.exception and at.select_slider(key="coupled_flow_window").value == 29
    at.select_slider(key="coupled_flow_window").set_value(4).run()
    assert not at.exception
    assert any("kilitli" in c.value or "serbest salınım" in c.value or "stop temasında" in c.value for c in at.caption)


def test_flow_tab_explains_a_missing_run_folder_without_offering_extraction(tmp_path, monkeypatch):
    at = _flow_app(tmp_path, monkeypatch, with_run_folder=False)
    assert any("çalıştırma klasörü" in i.value for i in at.info)
    assert not any(b.key == "coupled_flow_build" for b in at.button)


def test_flow_tab_without_toolchain_explains_how_to_prepare_flow_data(tmp_path, monkeypatch):
    at = _flow_app(tmp_path, monkeypatch, with_companion=False)
    assert any("hazırlanmadı" in i.value for i in at.info)
    assert any("araç zinciri" in c.value for c in at.caption)
    assert not any(b.key == "coupled_flow_build" for b in at.button)



def _ready_app(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    bem(monkeypatch)
    _forbid_runs(monkeypatch)
    fake = toolchain.Readiness("ready", "ok", toolchain.Toolchain(tmp_path / "tc.json", {}),
                               {"versions": {"dust_revision": "3b1d2e61f0b7", "mbdyn_revision": "55c86cc6ec7f",
                                             "precice_version": "2.5.0"}})
    monkeypatch.setattr(toolchain, "readiness", lambda **k: fake)
    at = go(app(), "Analiz")
    at.button(key="coupled_fill_demo").click().run()
    return at


def test_drive_ramp_inputs_and_fold_envelope_refusal(tmp_path, monkeypatch):
    at = _ready_app(tmp_path, monkeypatch)
    at.radio(key="coupled_drive_profile").set_value("ramp").run()
    at.number_input(key="coupled_drive_rpm0").set_value(2200.0).run()
    assert not at.exception
    assert any("Motor yasası" in c.value for c in at.caption)  # the drive torque is an output of the prescribed history
    # the limit belongs to the aerodynamic representation and its tolerances, not to the mechanism's travel
    from pyfoldable.application import coupled_ui
    text = coupled_ui.envelope_caption({"fold_limit_deg": -22.96, "limited_by": "junction_chord"},
                                       {"reynolds_ok": True, "mach_ok": True, "alpha_ok": True})
    assert "Aerodinamik temsil sınırı (katlanma): -23.0°" in text and "mekanizma stroku değildir" in text
    at.radio(key="coupled_drive_profile").set_value("constant").run()
    at.number_input(key="coupled_fold").set_value(-45.0).run()
    assert any("geometri sınırının ötesinde" in w.value and "mekanizma stroku değildir" in w.value for w in at.warning)


def test_engineering_assessment_tab_classifies_outputs(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    bem(monkeypatch)
    _no_toolchain(monkeypatch, tmp_path)
    _forbid_runs(monkeypatch)
    row = _record(tmp_path, FIXTURE_RBF)
    at = app()
    at.session_state["research_coupled_results"] = ((json.dumps(row, sort_keys=True, separators=(",", ":")), False),)
    at.session_state["_coupled_active"] = (None, row["result_sha256"])
    go(at, "Sonuçlar")
    at.radio(key="research_results_kind").set_value("Dinamik bağlaşık").run()
    at.radio(key="coupled_tab").set_value("Mühendislik değerlendirmesi").run()
    assert not at.exception
    table = at.dataframe[0].value
    assert {"Ön karar", "Gösterim", "Sayısal denetim"} <= set(table["Sınıf"])
    assert "Stop çarpma enerjisi ½J_hθ̇²" in set(table["Çıktı"]) and "Tepe tahrik torku" in set(table["Çıktı"])
    text = " ".join(c.value for c in at.caption) + " ".join(m.value for m in at.markdown)
    assert "gösterim varsayımı" in text and "itme dengesi" in text


def test_low_speed_trajectory_refusal_is_explained(tmp_path, monkeypatch):
    at = _ready_app(tmp_path, monkeypatch)

    def refuse(*a, **k):
        raise svc.CoupledPreparationError("outside_admitted_reynolds", "Planlanan yörüngede reynolds 1.08e+05…")
    monkeypatch.setattr(svc, "prepare", refuse)
    at.radio(key="coupled_drive_profile").set_value("ramp").run()
    assert any("Reynolds aralığından çıkıyor" in w.value for w in at.warning)



def test_every_coupled_status_has_an_explanation():
    from pyfoldable.application import coupled_ui
    statuses = {"completed", "failed_aero_coverage", "failed_unconverged_coupling", "failed_geometry_envelope",
                "cancelled", "timeout", "failed_solver", "failed_incomplete"}
    assert statuses <= set(coupled_ui._STATUS_TEXT)
