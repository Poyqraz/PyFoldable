"""CAD/polar-upload-free UI wiring with inert records and an inert BEM seam."""
from pathlib import Path
import json
import sys

import pytest
from streamlit.testing.v1 import AppTest

from pyfoldable.application import provider_design_analysis as service, design_analysis
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS
from pyfoldable.providers import xfoil
from pyfoldable.providers.xfoil import XfoilProvider
# Shared inert helpers are source-checkout test code, not an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "application"))
from test_provider_design_analysis import scenario, install_inert_bem


APP = Path(__file__).resolve().parents[2] / "apps/pyfoldable_dashboard.py"


def widget(items, label):
    return next(item for item in items if item.label == label)


def workspace():
    app = AppTest.from_file(str(APP)).run(timeout=30)
    app.sidebar.radio[0].set_value("Tasarım Geometrisi").run(timeout=30)
    assert not app.exception
    widget(app.checkbox, "Uygulama kayıtlarıyla BEM hazırlığı").check().run(timeout=30)
    return app


def declare_root(app):
    widget(app.text_input, "Kanat kökü r_root [değer birim]").set_value("20 mm")
    widget(app.text_input, "Kökün fiziksel/model anlamı").set_value("exposed root in shaft frame; INERT test assumption")
    widget(app.text_input, "Kök beyanı veya kaynak kimliği").set_value("UI-INERT-root-v1")
    widget(app.number_input, "İç kayıt BEM annulus sayısı").set_value(4).run(timeout=30)
    return app


@pytest.fixture(autouse=True)
def no_implicit_provider_or_bem(monkeypatch):
    def forbidden(*a, **k):
        pytest.fail("UI invoked a provider or a non-inert BEM solver")
    monkeypatch.setattr(XfoilProvider, "generate", forbidden)
    monkeypatch.setattr(xfoil, "_discover_backend_version", forbidden)
    monkeypatch.setattr(design_analysis, "solve_bem_rotor", forbidden)


def test_five_profiles_and_missing_root_or_data_do_not_launch(monkeypatch):
    monkeypatch.setattr(service, "application_provider_repository", lambda: service.ManagedProviderRepository())
    app = workspace()
    assert any("missing_root_declaration" in e.value for e in app.error)
    declare_root(app)
    for profile in PROJECT_AIRFOIL_IDS:
        widget(app.selectbox, "Kesit modeli").set_value(profile).run(timeout=30)
        assert not app.exception
        assert any("missing_applicable_family" in e.value and profile in e.value for e in app.error)
        assert not any(b.label == "İç kayıtlarla BEM çalıştır" for b in app.button)
    assert not any(d.label == "İç kayıt BEM raporunu indir" for d in app.get("download_button"))


def test_no_upload_explicit_inert_run_snapshot_export_and_input_invalidation(monkeypatch):
    _, repository = scenario("NACA2412")
    monkeypatch.setattr(service, "application_provider_repository", lambda: repository)
    app = declare_root(workspace())
    assert all(u.value is None for u in app.file_uploader)
    assert widget(app.button, "İç kayıtlarla BEM çalıştır").disabled
    widget(app.button, "İç kayıt hazırlığını doğrula").click().run(timeout=30)
    assert not widget(app.button, "İç kayıtlarla BEM çalıştır").disabled
    calls = install_inert_bem(monkeypatch)
    widget(app.button, "İç kayıtlarla BEM çalıştır").click().run(timeout=30)
    assert len(calls) == 1
    assert not app.exception
    assert any(d.label == "İç kayıt BEM raporunu indir" for d in app.get("download_button"))
    widget(app.button, "İç kayıt sonucunu karşılaştırmaya ekle").click().run(timeout=30)
    saved = json.dumps(app.session_state["py03_profile_comparison_records"], sort_keys=True)
    assert "inert_fixture" in saved
    app.run(timeout=30)
    assert len(calls) == 1
    widget(app.text_input, "Kök beyanı veya kaynak kimliği").set_value("UI-INERT-root-v2").run(timeout=30)
    assert not any(d.label == "İç kayıt BEM raporunu indir" for d in app.get("download_button"))
    assert widget(app.button, "İç kayıtlarla BEM çalıştır").disabled
    widget(app.selectbox, "Kesit modeli").set_value("NACA0012").run(timeout=30)
    assert json.dumps(app.session_state["py03_profile_comparison_records"], sort_keys=True) == saved
    assert len(calls) == 1


def test_explicit_failure_keeps_request_and_null_totals_across_rerender(monkeypatch):
    _, repository = scenario("NACA2412")
    monkeypatch.setattr(service, "application_provider_repository", lambda: repository)
    app = declare_root(workspace())
    widget(app.button, "İç kayıt hazırlığını doğrula").click().run(timeout=30)
    calls = []
    def fail(*a, **k):
        calls.append(1)
        raise design_analysis.DesignAnalysisError("INERT retained failure")
    monkeypatch.setattr(design_analysis, "solve_bem_rotor", fail)
    widget(app.button, "İç kayıtlarla BEM çalıştır").click().run(timeout=30)
    assert not app.exception
    outcome = app.session_state[service.ACTIVE_OUTCOME]
    assert outcome.artifact is None
    assert outcome.record["thrust_n"] is None
    assert outcome.record["ui_request_sha256"]
    assert outcome.record["provider_design_admission"]["evidence_class"] == "inert_fixture"
    app.run(timeout=30)
    assert calls == [1]
    assert any("INERT retained failure" in e.value for e in app.error)


def test_distinct_root_rejections_survive_no_upload_saved_history(monkeypatch):
    _, repository = scenario("NACA2412")
    monkeypatch.setattr(service, "application_provider_repository", lambda: repository)
    app = declare_root(workspace())
    for root in ("80 mm", "81 mm"):
        widget(app.text_input, "Kanat kökü r_root [değer birim]").set_value(root).run(timeout=30)
        assert not app.exception
        assert any("longer_proximal_required" in e.value for e in app.error)
        widget(app.button, "İç kayıt ret kaydını karşılaştırmaya ekle").click().run(timeout=30)
    records = app.session_state["py03_profile_comparison_records"]
    assert len(records) == 2
    assert [r["attempted_selection"]["root"]["value"] for r in records] == [80., 81.]
    assert len({r["attempt_sha256"] for r in records}) == 2
    assert all(r["analysis_request_sha256"] is r["report_sha256"] is r["thrust_n"] is None for r in records)
    saved = json.dumps(records, sort_keys=True)
    widget(app.selectbox, "Kesit modeli").set_value("NACA0012").run(timeout=30)
    assert json.dumps(app.session_state["py03_profile_comparison_records"], sort_keys=True) == saved
    assert all(u.value is None for u in app.file_uploader)


def test_configured_persistent_store_no_upload_execution_switching_and_corruption(tmp_path, monkeypatch):
    from pyfoldable.application.provider_record_store import ProviderRecordStore, STORE_ENVIRONMENT_VARIABLE
    from dataclasses import replace
    import hashlib
    root = tmp_path / "isolated-inert-store"
    bindings = {}
    with ProviderRecordStore(root) as store:
        for profile in PROJECT_AIRFOIL_IDS:
            _, repo = scenario(profile)
            bindings[profile] = store.register_family(repo.families[0], version_label="INERT-positive")
        _, repo = scenario("NACA2412")
        store.register_family(replace(repo.families[0], cells=(None,) * 4), version_label="INERT-incomplete")
    monkeypatch.setenv(STORE_ENVIRONMENT_VARIABLE, str(root))
    app = declare_root(workspace())  # actual configured loader, no repository patch
    assert not app.exception
    assert all(u.value is None for u in app.file_uploader)
    assert any("stored_version_required" in e.value for e in app.error)
    assert any("incomplete_family" in d.value for d in app.markdown)
    assert any("Tam hazırlık adayı" in d.value for d in app.markdown)
    widget(app.selectbox, "Uygulama kayıt sürümü").set_value(bindings["NACA2412"].content_sha256).run(timeout=30)
    widget(app.button, "İç kayıt hazırlığını doğrula").click().run(timeout=30)
    calls = install_inert_bem(monkeypatch)
    widget(app.button, "İç kayıtlarla BEM çalıştır").click().run(timeout=30)
    assert not app.exception and len(calls) == 1
    widget(app.button, "İç kayıt sonucunu karşılaştırmaya ekle").click().run(timeout=30)
    saved = json.dumps(app.session_state["py03_profile_comparison_records"], sort_keys=True)
    for profile in PROJECT_AIRFOIL_IDS:
        widget(app.selectbox, "Kesit modeli").set_value(profile).run(timeout=30)
        assert not app.exception
        if profile != "NACA2412":
            assert widget(app.selectbox, "Uygulama kayıt sürümü").value is None
        assert json.dumps(app.session_state["py03_profile_comparison_records"], sort_keys=True) == saved
    widget(app.selectbox, "Kesit modeli").set_value("NACA2412").run(timeout=30)
    widget(app.selectbox, "Uygulama kayıt sürümü").set_value(bindings["NACA2412"].content_sha256).run(timeout=30)
    widget(app.button, "İç kayıt hazırlığını doğrula").click().run(timeout=30)
    _, repo = scenario("NACA2412")
    blob = root / "blobs" / hashlib.sha256(repo.families[0].cells[0].result_json).hexdigest()
    blob.write_bytes(b"INERT corrupted bytes")
    app.run(timeout=30)
    assert not app.exception
    assert any("provider_store_bytes_changed" in e.value for e in app.error)
    assert service.ACTIVE_REQUEST not in app.session_state
    assert service.ACTIVE_OUTCOME not in app.session_state
    assert not any(d.label == "İç kayıt BEM raporunu indir" for d in app.get("download_button"))
    assert len(calls) == 1
    assert json.dumps(app.session_state["py03_profile_comparison_records"], sort_keys=True) == saved


def test_removed_selected_version_does_not_select_another_version(tmp_path, monkeypatch):
    from pyfoldable.application.provider_record_store import ProviderRecordStore, STORE_ENVIRONMENT_VARIABLE
    root = tmp_path / "isolated-inert-store"
    _, repo = scenario("NACA2412")
    with ProviderRecordStore(root) as store:
        first = store.register_family(repo.families[0], version_label="INERT-v1")
        second = store.register_family(repo.families[0], version_label="INERT-v2")
    monkeypatch.setenv(STORE_ENVIRONMENT_VARIABLE, str(root))
    app = declare_root(workspace())
    widget(app.selectbox, "Uygulama kayıt sürümü").set_value(first.content_sha256).run(timeout=30)
    widget(app.button, "İç kayıt hazırlığını doğrula").click().run(timeout=30)
    widget(app.selectbox, "Uygulama kayıt sürümü").set_value(second.content_sha256).run(timeout=30)
    assert service.ACTIVE_REQUEST not in app.session_state
    assert service.ACTIVE_OUTCOME not in app.session_state
    assert widget(app.button, "İç kayıtlarla BEM çalıştır").disabled
    widget(app.selectbox, "Uygulama kayıt sürümü").set_value(first.content_sha256).run(timeout=30)
    widget(app.button, "İç kayıt hazırlığını doğrula").click().run(timeout=30)
    (root / "records" / (first.registration_key + ".json")).unlink()
    app.run(timeout=30)
    assert not app.exception
    assert any("selected_version_unavailable" in e.value for e in app.error)
    assert widget(app.selectbox, "Uygulama kayıt sürümü").value is None
    assert service.ACTIVE_REQUEST not in app.session_state
    assert not any(b.label == "İç kayıtlarla BEM çalıştır" for b in app.button)
