"""Explicit GEOM-03 execution and stale surface report handling."""
import json

from test_active_design_polar_ui import _app, _widget
from test_blade_stations_ui import has_download
from test_geometry_navigation_ui import navigate_away_and_back


LABEL = "Yüzey açıklığı raporunu JSON indir"


def run(app):
    _widget(app.button, "Katlanma boyunca yüzey açıklığını denetle").click().run(timeout=30)
    assert not app.exception
    assert has_download(app, LABEL)
    return app


def test_surface_run_is_explicit_and_result_tracks_active_geometry(monkeypatch):
    from pyfoldable.application import surface_clearance
    calls = []
    original = surface_clearance.run_surface_clearance
    def capture(request):
        calls.append(request)
        return original(request)
    monkeypatch.setattr(surface_clearance, "run_surface_clearance", capture)
    app = _app()
    assert not calls and not has_download(app, LABEL)
    run(app)
    assert len(calls) == 1
    report = json.loads(app.session_state["geom03_result"].report_json)
    assert report["request"]["draft_sha256"] == app.session_state["geom02_active_draft"]
    assert report["physical_qualification"] is False
    assert report["full_propeller_clearance"] is None
    app.run(timeout=30)
    assert len(calls) == 1
    _widget(app.number_input, "Açık çap [mm]").set_value(260.).run(timeout=30)
    assert not has_download(app, LABEL)


def test_unreferenced_contact_exclusion_clears_old_report():
    app = run(_app())
    _widget(app.number_input, "Menteşe bağlantı yarı genişliği [mm]").set_value(1.).run(timeout=30)
    assert not app.exception
    assert not has_download(app, LABEL)
    assert "geom03_result" not in app.session_state
    assert not any(b.label == "Katlanma boyunca yüzey açıklığını denetle" for b in app.button)


def test_geometry_surface_run_at_zero_rpm_survives_navigation():
    app = _app()
    _widget(app.number_input, "RPM").set_value(0.).run(timeout=30)
    run(app)
    result = app.session_state["geom03_result"]
    navigate_away_and_back(app)
    assert app.session_state["geom03_result"] == result
    assert has_download(app, LABEL)


def test_failed_surface_rerun_clears_previous_result(monkeypatch):
    from pyfoldable.application import surface_clearance
    app = run(_app())
    def fail(*args):
        raise ValueError("synthetic failure")
    monkeypatch.setattr(surface_clearance, "run_surface_clearance", fail)
    _widget(app.button, "Katlanma boyunca yüzey açıklığını denetle").click().run(timeout=30)
    assert not app.exception
    assert not has_download(app, LABEL)


def test_invalid_geometry_does_not_resurrect_surface_report_after_restore():
    app = run(_app())
    _widget(app.number_input, "Göbek yarıçapı [mm]").set_value(120.).run(timeout=30)
    assert "geom03_result" not in app.session_state
    _widget(app.number_input, "Göbek yarıçapı [mm]").set_value(18.).run(timeout=30)
    assert not has_download(app, LABEL)


def test_invalid_geometry_preserves_custom_clearance_and_endpoint():
    app = _app()
    _widget(app.number_input, "İstenen yüzey açıklığı [mm]").set_value(3.).run(timeout=30)
    _widget(app.number_input, "Yüzey denetimi · Hedef açı [deg]").set_value(-90.).run(timeout=30)
    _widget(app.number_input, "Göbek yarıçapı [mm]").set_value(120.).run(timeout=30)
    _widget(app.number_input, "Göbek yarıçapı [mm]").set_value(18.).run(timeout=30)
    assert not app.exception
    assert _widget(app.number_input, "İstenen yüzey açıklığı [mm]").value == 3.
    assert _widget(app.number_input, "Yüzey denetimi · Hedef açı [deg]").value == -90.
    assert not has_download(app, LABEL)
