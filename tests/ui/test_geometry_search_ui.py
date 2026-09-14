"""The geometry grid is explicit and old reports disappear when inputs change."""
from test_active_design_polar_ui import _app, _widget


def download(app):
    return any(item.label == "Geometri taramasını JSON indir" for item in app.get("download_button"))


def test_geometry_search_runs_without_polars_and_invalidates_on_draft_change():
    app = _app()
    assert not download(app)
    _widget(app.button, "Geometri fizibilitesini tara").click().run(timeout=20)
    assert not app.exception
    assert download(app)
    _widget(app.number_input, "Açık çap [mm]").set_value(260.).run(timeout=20)
    assert not app.exception
    assert not download(app)


def test_empty_grid_clears_report_and_disables_run():
    app = _app()
    _widget(app.button, "Geometri fizibilitesini tara").click().run(timeout=20)
    assert download(app)
    _widget(app.multiselect, "Geometri taraması · katlı açı [deg]").set_value([]).run(timeout=20)
    assert not app.exception
    assert not download(app)
    assert not any(b.label == "Geometri fizibilitesini tara" for b in app.button)


def test_failed_rerun_removes_old_report(monkeypatch):
    from pyfoldable.application import geometry_search
    app = _app()
    _widget(app.button, "Geometri fizibilitesini tara").click().run(timeout=20)
    assert download(app)
    def fail(*args, **kwargs):
        raise geometry_search.SearchError("intentional failure")
    monkeypatch.setattr(geometry_search, "run_geometry_search", fail)
    _widget(app.button, "Geometri fizibilitesini tara").click().run(timeout=20)
    assert not app.exception
    assert not download(app)


def test_invalid_preview_clears_geometry_report_before_restoring_same_draft():
    app = _app()
    _widget(app.button, "Geometri fizibilitesini tara").click().run(timeout=20)
    assert download(app)
    _widget(app.number_input, "Göbek yarıçapı [mm]").set_value(120.).run(timeout=20)
    assert not app.exception
    assert "geom01_result" not in app.session_state
    _widget(app.number_input, "Göbek yarıçapı [mm]").set_value(18.).run(timeout=20)
    assert not download(app)
