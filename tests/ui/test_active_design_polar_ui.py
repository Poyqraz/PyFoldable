"""Explicit UI runs and invalidation; uploaded coefficients are synthetic tests."""

import hashlib
import json
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from pyfoldable.application import design_analysis, polar_upload
from pyfoldable.application.design_analysis import DesignAnalysisError
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS, load_project_airfoil


APP = Path(__file__).resolve().parents[2] / "apps/pyfoldable_dashboard.py"
RESULT_KEY = "py03_polar_result"


def _payload(airfoil_id="NACA2412"):
    foil = load_project_airfoil(airfoil_id)
    return json.dumps({"schema_version": 1, "artifact_class": "active_design_polar_bundle",
        "physical_qualification": False, "tables": [{
            "airfoil_id": foil.id, "scenario_id": "synthetic-ui-test",
            "source": "inert fixture; synthetic test only; not a real-provider polar",
            "reynolds": re, "mach": ma, "alpha_rad": [-1.57, 1.57],
            "cl": [.8, .8], "cd": [.02, .02], "cm": [0., 0.],
            "metadata": {"airfoil_coordinate_sha256": foil.metadata["airfoil_coordinate_sha256"]},
        } for re in (100., 1e7) for ma in (0., 1.)]}).encode()


def _widget(items, label):
    return next(item for item in items if item.label == label)


def _app():
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.sidebar.radio[0].set_value("Tasarım Geometrisi").run(timeout=20)
    return app


def _upload(app, raw=None):
    _widget(app.file_uploader, "Polar JSON dosyası").set_value(("polars.json", _payload() if raw is None else raw, "application/json")).run(timeout=20)
    return app


def _run(app):
    _widget(app.number_input, "Aktif BEM annulus sayısı").set_value(4).run(timeout=20)
    _widget(app.button, "Aktif taslağı BEM ile çalıştır").click().run(timeout=20)
    assert not app.exception
    assert _has_download(app)
    return app


def _has_download(app):
    return any(item.label == "Aktif BEM sonucunu JSON indir" for item in app.get("download_button"))


def test_upload_and_widget_edits_never_run_bem_implicitly(monkeypatch):
    import pyfoldable.application.design_analysis as analysis
    monkeypatch.setattr(analysis, "solve_bem_rotor", lambda *a, **k: pytest.fail("implicit BEM"))
    app = _app()
    assert app.get("file_uploader")
    assert not any(item.label == "Aktif taslağı BEM ile çalıştır" for item in app.button)
    _upload(app)
    _widget(app.number_input, "Açık çap [mm]").set_value(300.).run(timeout=20)
    assert not app.exception
    assert not _has_download(app)


def test_explicit_run_uses_active_draft_and_rerender_keeps_result_without_rerun(monkeypatch):
    app = _run(_upload(_app()))
    artifact = app.session_state[RESULT_KEY]
    report = json.loads(artifact.report_json)
    assert report["physical_qualification"] is False
    assert report["preparation"]["diameter_m"] == .25
    assert report["request"]["polar_upload"]["source_json"] == _payload().decode()
    assert any(item.label == "Aktif itki [N]" for item in app.metric)
    import pyfoldable.application.design_analysis as analysis
    monkeypatch.setattr(analysis, "solve_bem_rotor", lambda *a, **k: pytest.fail("rerun"))
    app.run(timeout=20)
    assert not app.exception
    assert _has_download(app)
    assert app.session_state[RESULT_KEY] == artifact


@pytest.mark.parametrize("kind,label,value", [
    ("number_input", "Açık çap [mm]", 300.),
    ("number_input", "RPM", 6800.),
    ("number_input", "RPM", 0.),
    ("number_input", "Göbek yarıçapı [mm]", 200.),
    ("number_input", "Aktif BEM annulus sayısı", 8),
    ("selectbox", "Kesit modeli", "NACA0012"),
    ("slider", "Katlanma açısı [deg]", -90),
])
def test_changed_or_invalid_inputs_clear_result_and_download(kind, label, value):
    app = _run(_upload(_app()))
    _widget(getattr(app, kind), label).set_value(value).run(timeout=20)
    assert not app.exception
    assert not _has_download(app)
    assert RESULT_KEY not in app.session_state


@pytest.mark.parametrize("replacement", [None, b"{}", b" "])
def test_removed_invalid_or_byte_changed_upload_clears_result(replacement):
    app = _run(_upload(_app()))
    if replacement is None:
        _widget(app.file_uploader, "Polar JSON dosyası").set_value(None).run(timeout=20)
    else:
        _upload(app, _payload() + replacement if replacement == b" " else replacement)
    assert not app.exception
    assert not _has_download(app)
    assert RESULT_KEY not in app.session_state


def test_solver_failure_removes_previous_success(monkeypatch):
    from pyfoldable.application.design_analysis import DesignAnalysisError
    import pyfoldable.application.polar_upload as upload
    app = _run(_upload(_app()))

    def fail(*a, **k):
        raise DesignAnalysisError("test solver rejected without partial totals")

    monkeypatch.setattr(upload, "run_polar_run", fail)
    _widget(app.button, "Aktif taslağı BEM ile çalıştır").click().run(timeout=20)
    assert not app.exception
    assert any("without partial totals" in item.value for item in app.error)
    assert not _has_download(app)
    assert RESULT_KEY not in app.session_state


def test_polar_upload_size_is_checked_before_reading_bytes():
    source = APP.read_text(encoding="utf-8")
    function = source.split("def _render_active_polar_run(", 1)[1].split("\ndef ", 1)[0]
    assert function.index("uploaded.size") < function.index("uploaded.getvalue()")


def test_unicode_failure_is_controlled_and_clears_previous_result():
    app = _run(_upload(_app()))
    doc = json.loads(_payload()); doc["tables"][0]["source"] = "bad\ud800source"
    _upload(app, json.dumps(doc).encode())
    assert not app.exception
    assert any("reddedildi" in item.value for item in app.error)
    assert not _has_download(app)
    assert RESULT_KEY not in app.session_state


def test_profile_switch_keeps_the_saved_comparison_and_does_not_solve(monkeypatch) -> None:
    import pyfoldable.application.design_analysis as analysis
    calls = {"n": 0}
    real = analysis.solve_bem_rotor

    def counted(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(analysis, "solve_bem_rotor", counted)
    app = _run(_upload(_app()))
    assert calls["n"] == 1
    _widget(app.button, "Aktif sonucu karşılaştırmaya ekle").click().run(timeout=30)
    assert calls["n"] == 1
    saved = app.session_state["py03_profile_comparison_records"]
    assert saved[0]["airfoil_id"] == "NACA2412"
    assert saved[0]["thrust_n"] is not None
    monkeypatch.setattr(analysis, "solve_bem_rotor", lambda *args, **kwargs: pytest.fail("selection reran BEM"))
    _widget(app.selectbox, "Kesit modeli").set_value("NACA0012").run(timeout=30)
    assert not app.exception
    assert RESULT_KEY not in app.session_state
    assert any("reddedildi" in item.value for item in app.error)
    assert app.session_state["py03_profile_comparison_records"][0]["airfoil_id"] == "NACA2412"
    assert any(item.label == "Karşılaştırmayı JSON indir" for item in app.download_button)
    assert any(item.label == "Karşılaştırmayı CSV indir" for item in app.download_button)
    assert any("BLOCKED" in item.value for item in app.warning)


def test_bem_failure_stays_active_until_inputs_change_and_can_be_saved(monkeypatch):
    app = _run(_upload(_app()))
    calls = {"n": 0}

    def fail(*_args, **_kwargs):
        calls["n"] += 1
        raise DesignAnalysisError("coverage missing; no partial totals")

    monkeypatch.setattr(polar_upload, "run_polar_run", fail)
    _widget(app.button, "Aktif taslağı BEM ile çalıştır").click().run(timeout=20)
    assert calls["n"] == 1
    assert not app.exception
    assert RESULT_KEY not in app.session_state
    failure = app.session_state["py03_polar_failure"]
    assert failure["status"] == "failure"
    assert failure["airfoil_id"] == "NACA2412"
    assert failure["thrust_n"] is None
    assert failure["torque_nm"] is None
    assert failure["shaft_power_w"] is None
    app.run(timeout=20)
    assert calls["n"] == 1
    assert not app.exception
    assert RESULT_KEY not in app.session_state
    assert app.session_state["py03_polar_failure"] == failure
    assert any("coverage missing" in item.value for item in app.error)
    assert any("tekrarlamaz" in item.value for item in app.caption)
    _widget(app.button, "Başarısız BEM denemesini karşılaştırmaya ekle").click().run(timeout=20)
    assert calls["n"] == 1
    saved = json.loads(json.dumps(app.session_state["py03_profile_comparison_records"]))
    assert saved[0]["status"] == "failure"
    assert saved[0]["airfoil_id"] == "NACA2412"
    assert saved[0]["thrust_n"] is None
    assert saved[0]["record_sha256"] == failure["record_sha256"]
    _widget(app.number_input, "RPM").set_value(6800.).run(timeout=20)
    assert calls["n"] == 1
    assert "py03_polar_failure" not in app.session_state
    assert RESULT_KEY not in app.session_state
    assert app.session_state["py03_profile_comparison_records"][0] == saved[0]
    _widget(app.selectbox, "Kesit modeli").set_value("NACA0012").run(timeout=20)
    assert "py03_polar_failure" not in app.session_state
    assert RESULT_KEY not in app.session_state
    assert app.session_state["py03_profile_comparison_records"][0] == saved[0]


def test_profile_cycle_rejects_wrong_polar_and_exports_the_saved_rows(monkeypatch):
    calls = {"n": 0}
    real = design_analysis.solve_bem_rotor

    def counted(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    exported = []
    original_download = st.download_button

    def spy(label, data=None, **kwargs):
        if label.startswith("Karşılaştırmayı"):
            exported.append((label, data))
        return original_download(label, data=data, **kwargs)

    monkeypatch.setattr(design_analysis, "solve_bem_rotor", counted)
    monkeypatch.setattr(st, "download_button", spy)
    app = _app()
    selectors = [item for item in app.selectbox if item.label == "Kesit modeli"]
    assert len(selectors) == 1
    assert selectors[0].options == list(PROJECT_AIRFOIL_IDS)
    assert calls["n"] == 0
    app = _run(_upload(app, _payload("NACA2412")))
    assert calls["n"] == 1
    _widget(app.button, "Aktif sonucu karşılaştırmaya ekle").click().run(timeout=30)
    assert any("Tek kayıt" in item.value for item in app.caption)
    assert not any("aynı değil" in item.value for item in app.warning)
    alpha = json.loads(json.dumps(app.session_state["py03_profile_comparison_records"][0]))
    assert alpha["status"] == "success"
    assert alpha["airfoil_id"] == "NACA2412"
    wrong = json.loads(_payload("NACA2412"))
    for table in wrong["tables"]:
        table["metadata"]["airfoil_coordinate_sha256"] = "0" * 64
    wrong_bytes = json.dumps(wrong).encode()
    _upload(app, wrong_bytes)
    assert calls["n"] == 1
    assert RESULT_KEY not in app.session_state
    assert any("coordinate SHA-256" in item.value for item in app.error)
    _widget(app.button, "Başarısız polar denemesini karşılaştırmaya ekle").click().run(timeout=30)
    rows = app.session_state["py03_profile_comparison_records"]
    assert rows[0] == alpha
    assert rows[1]["airfoil_id"] == "NACA2412"
    assert rows[1]["status"] == "failure"
    assert rows[1]["thrust_n"] is None
    assert rows[1]["torque_nm"] is None
    assert rows[1]["shaft_power_w"] is None
    assert rows[1]["polar_source_sha256"] == hashlib.sha256(wrong_bytes).hexdigest()
    _widget(app.selectbox, "Kesit modeli").set_value("NACA0012").run(timeout=30)
    assert calls["n"] == 1
    assert RESULT_KEY not in app.session_state
    assert any("does not match" in item.value for item in app.error)
    _widget(app.button, "Başarısız polar denemesini karşılaştırmaya ekle").click().run(timeout=30)
    rows = app.session_state["py03_profile_comparison_records"]
    assert rows[0] == alpha
    assert rows[2]["airfoil_id"] == "NACA0012"
    assert rows[2]["status"] == "failure"
    assert rows[2]["thrust_n"] is None
    _upload(app, _payload("NACA0012"))
    _widget(app.number_input, "Aktif BEM annulus sayısı").set_value(4).run(timeout=20)
    _widget(app.button, "Aktif taslağı BEM ile çalıştır").click().run(timeout=30)
    assert calls["n"] == 2
    _widget(app.button, "Aktif sonucu karşılaştırmaya ekle").click().run(timeout=30)
    rows = app.session_state["py03_profile_comparison_records"]
    assert [row["airfoil_id"] for row in rows] == ["NACA2412", "NACA2412", "NACA0012", "NACA0012"]
    assert rows[0] == alpha
    assert rows[3]["status"] == "success"
    assert rows[0]["geometry_sha256"] != rows[3]["geometry_sha256"]
    assert rows[0]["planform_sha256"] == rows[3]["planform_sha256"]
    _widget(app.selectbox, "Kesit modeli").set_value("NACA2412").run(timeout=30)
    assert calls["n"] == 2
    assert RESULT_KEY not in app.session_state
    assert app.session_state["py03_profile_comparison_records"][3]["airfoil_id"] == "NACA0012"
    _upload(app, _payload("NACA2412"))
    _widget(app.number_input, "Aktif BEM annulus sayısı").set_value(4).run(timeout=20)
    _widget(app.button, "Aktif taslağı BEM ile çalıştır").click().run(timeout=30)
    assert calls["n"] == 3
    assert json.loads(app.session_state[RESULT_KEY].report_json)["rotor"]["airfoil_id"] == "NACA2412"
    _widget(app.number_input, "RPM").set_value(6800.).run(timeout=20)
    assert calls["n"] == 3
    assert RESULT_KEY not in app.session_state
    _widget(app.number_input, "Aktif BEM annulus sayısı").set_value(4).run(timeout=20)
    _widget(app.button, "Aktif taslağı BEM ile çalıştır").click().run(timeout=30)
    assert calls["n"] == 4
    _widget(app.button, "Aktif sonucu karşılaştırmaya ekle").click().run(timeout=30)
    rows = app.session_state["py03_profile_comparison_records"]
    assert rows[0] == alpha
    assert rows[-1]["airfoil_id"] == "NACA2412"
    assert rows[-1]["condition_sha256"] != alpha["condition_sha256"]
    assert any("kontrollü bir karşılaştırma değildir" in item.value for item in app.warning)
    assert any("condition_sha256" in item.value for item in app.warning)
    assert not any("verim" in item.label.lower() for item in app.metric)
    document = json.loads(next(data for label, data in reversed(exported) if label == "Karşılaştırmayı JSON indir"))
    csv_payload = next(data for label, data in reversed(exported) if label == "Karşılaştırmayı CSV indir")
    assert document["performance_comparison"] is False
    assert document["genuine_comparison_status"] == "BLOCKED_no_matching_real_provider_polar_bundle"
    assert document["physical_qualification"] is False
    assert document["qualified_winner"] is None
    assert document["records"][0]["radial_elements"]
    assert document["records"][1]["thrust_n"] is None
    assert document["records"][0]["record_sha256"] == alpha["record_sha256"]
    assert "propulsive_efficiency" not in csv_payload
    assert "shaft_power_w" in csv_payload
    assert "BLOCKED_no_matching_real_provider_polar_bundle" in csv_payload
    assert str(document["records"][0]["thrust_n"]) in csv_payload
    assert calls["n"] == 4


def test_uploaded_source_is_plain_text_not_active_markdown():
    source = "![tracking](https://example.invalid/pixel) <https://example.invalid/>"
    doc = json.loads(_payload())
    for table in doc["tables"]: table["source"] = source
    app = _upload(_app(), json.dumps(doc).encode())
    assert not app.exception
    assert not any(source in item.value for item in app.markdown)
    assert any(source in item.value for item in app.text)
