"""Search button is explicit; stale results must not survive input changes."""

import pytest

from test_active_design_polar_ui import _app, _upload, _widget, _payload


def _configured():
    app = _upload(_app())
    _widget(app.number_input, "Aktif BEM annulus sayısı").set_value(4).run(timeout=20)
    _widget(app.multiselect, "Tarama chord çarpanları").set_value([1.]).run(timeout=20)
    _widget(app.multiselect, "Tarama twist çarpanları").set_value([1.]).run(timeout=20)
    return app


def _run(app):
    _widget(app.button, "Aktif taslak ızgarasını tara").click().run(timeout=20)
    assert not app.exception
    assert _download(app)
    return app


def _download(app):
    return any(item.label == "Tasarım taramasını JSON indir" for item in app.get("download_button"))


def test_grid_widgets_never_solve_automatically(monkeypatch):
    import pyfoldable.application.design_analysis as analysis
    monkeypatch.setattr(analysis, "solve_bem_rotor", lambda *a, **k: pytest.fail("automatic solve"))
    app = _configured()
    assert not app.exception
    assert not _download(app)


def test_explicit_grid_run_and_rerender_preserve_only_screening_result(monkeypatch):
    app = _run(_configured())
    assert any("uygun aday önerilmiyor" in item.value for item in app.warning)
    import pyfoldable.application.design_analysis as analysis
    monkeypatch.setattr(analysis, "solve_bem_rotor", lambda *a, **k: pytest.fail("rerun"))
    app.run(timeout=20)
    assert not app.exception
    assert _download(app)


@pytest.mark.parametrize("kind,label,value", [
    ("number_input", "Tarama minimum itki [N]", 2.),
    ("number_input", "Açık çap [mm]", 300.),
    ("number_input", "RPM", 0.),
    ("number_input", "Göbek yarıçapı [mm]", 200.),
    ("number_input", "Aktif BEM annulus sayısı", 8),
    ("selectbox", "Kesit modeli", "NACA0012"),
    ("slider", "Katlanma açısı [deg]", -90),
    ("multiselect", "Tarama chord çarpanları", [1., 1.1]),
    ("multiselect", "Tarama twist çarpanları", []),
])
def test_input_change_or_failure_clears_search_result(kind, label, value):
    app = _run(_configured())
    _widget(getattr(app, kind), label).set_value(value).run(timeout=20)
    assert not app.exception
    assert not _download(app)
    assert "py04_search_result" not in app.session_state


@pytest.mark.parametrize("raw", [b"{}", None, _payload() + b" "])
def test_changed_or_removed_polar_clears_search(raw):
    app = _run(_configured())
    if raw is None:
        _widget(app.file_uploader, "Polar JSON dosyası").set_value(None).run(timeout=20)
    else: _upload(app, raw)
    assert not app.exception
    assert not _download(app)
    assert "py04_search_result" not in app.session_state


def test_aggregate_budget_prevents_run_button():
    app = _configured()
    _widget(app.number_input, "Aktif BEM annulus sayısı").set_value(40).run(timeout=20)
    for label in ("Tarama chord çarpanları", "Tarama twist çarpanları"):
        _widget(app.multiselect, label).set_value([.8,.9,1.,1.1,1.2]).run(timeout=20)
    assert not app.exception
    assert not any(item.label == "Aktif taslak ızgarasını tara" for item in app.button)


def test_failed_search_rerun_clears_previous_success(monkeypatch):
    import pyfoldable.application.active_design_search as search
    app = _run(_configured())

    def fail(*args, **kwargs):
        raise search.SearchError("test search rejection")

    monkeypatch.setattr(search, "run_active_search", fail)
    _widget(app.button, "Aktif taslak ızgarasını tara").click().run(timeout=20)
    assert not app.exception
    assert not _download(app)
    assert "py04_search_result" not in app.session_state


def test_individual_bem_run_preserves_current_search_result():
    app = _run(_configured())
    previous = app.session_state["py04_search_result"]
    _widget(app.button, "Aktif taslağı BEM ile çalıştır").click().run(timeout=20)
    assert not app.exception
    assert _download(app)
    assert app.session_state["py04_search_result"] == previous
