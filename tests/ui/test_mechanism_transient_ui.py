from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[2] / "apps" / "pyfoldable_dashboard.py"


def page():
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    app.sidebar.radio[0].set_value("Mekanizma Geçişi").run()
    return app


def test_transient_requires_explicit_run_and_invalidates_changed_input():
    app = page()
    assert not any(x.label == "Geçiş sonucunu JSON indir" for x in app.get("download_button"))
    next(x for x in app.button if x.label == "Mekanizma geçişini çalıştır").click().run()
    assert any(x.label == "Geçiş sonucunu JSON indir" for x in app.get("download_button"))
    widget = next(x for x in app.number_input if x.label == "Geçiş kütlesi [kg]")
    widget.set_value(widget.value * 1.1).run()
    assert "py05_transient_result" not in app.session_state
    assert not any(x.label == "Geçiş sonucunu JSON indir" for x in app.get("download_button"))


def test_invalid_transient_input_has_no_run_or_stale_result():
    app = page()
    next(x for x in app.number_input if x.label == "Geçiş menteşe ataleti [kg m²]").set_value(0.0001).run()
    assert not any(x.label == "Mekanizma geçişini çalıştır" for x in app.button)
    assert "py05_transient_result" not in app.session_state
