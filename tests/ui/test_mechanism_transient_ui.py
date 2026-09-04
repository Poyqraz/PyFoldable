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


def test_failed_repeat_removes_previous_result(monkeypatch):
    app = page()
    next(x for x in app.button if x.label == "Mekanizma geçişini çalıştır").click().run()
    assert "py05_transient_result" in app.session_state
    import pyfoldable.application.mechanism_transient as service

    def fail(*args, **kwargs):
        raise service.MechanismTransientError("injected failure")

    monkeypatch.setattr(service, "run_mechanism_transient", fail)
    next(x for x in app.button if x.label == "Mekanizma geçişini çalıştır").click().run()
    assert not app.exception
    assert "py05_transient_result" not in app.session_state
    assert not any(x.label == "Geçiş sonucunu JSON indir" for x in app.get("download_button"))


def test_signed_custom_history_and_friction_run():
    app = page()
    next(x for x in app.checkbox if x.label == "Parçalı zaman geçmişini JSON ile gir").check().run()
    next(x for x in app.text_area if x.label == "RPM/menteşe torku geçmişi [JSON]").set_value(
        '{"time_s":[0,0.01,0.02],"rpm":[-60,60,-60],"applied_hinge_torque_nm":[0,0,0]}'
    ).run()
    next(x for x in app.checkbox if x.label == "Düzenlileştirilmiş Coulomb sürtünmesi").check().run()
    next(x for x in app.button if x.label == "Mekanizma geçişini çalıştır").click().run()
    assert not app.exception
    assert "py05_transient_result" in app.session_state
