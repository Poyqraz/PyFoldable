"""CAD/polar-upload-free UI wiring with inert records and an inert BEM seam."""
from pathlib import Path
import json

import pytest
from streamlit.testing.v1 import AppTest

from pyfoldable.application import provider_design_analysis as service, design_analysis
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS
from pyfoldable.providers.xfoil import XfoilProvider
from tests.application.test_provider_design_analysis import scenario, install_inert_bem


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
