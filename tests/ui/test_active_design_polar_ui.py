"""Explicit UI runs and invalidation; uploaded coefficients are synthetic tests."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from pyfoldable.core.profile_catalog import load_project_airfoil


APP = Path(__file__).resolve().parents[2] / "apps/pyfoldable_dashboard.py"
RESULT_KEY = "py03_polar_result"


def _payload():
    return json.dumps({"schema_version": 1, "artifact_class": "active_design_polar_bundle",
        "physical_qualification": False, "tables": [{
            "airfoil_id": "NACA2412", "scenario_id": "synthetic-ui-test", "source": "synthetic test only",
            "reynolds": re, "mach": ma, "alpha_rad": [-1.57, 1.57],
            "cl": [.8, .8], "cd": [.02, .02], "cm": [0., 0.],
            "metadata": {"airfoil_coordinate_sha256": load_project_airfoil("NACA2412").metadata["airfoil_coordinate_sha256"]},
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


def test_uploaded_source_is_plain_text_not_active_markdown():
    source = "![tracking](https://example.invalid/pixel) <https://example.invalid/>"
    doc = json.loads(_payload())
    for table in doc["tables"]: table["source"] = source
    app = _upload(_app(), json.dumps(doc).encode())
    assert not app.exception
    assert not any(source in item.value for item in app.markdown)
    assert any(source in item.value for item in app.text)
