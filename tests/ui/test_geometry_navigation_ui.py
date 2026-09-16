"""Navigation preserves the engineering draft, not discarded widget defaults."""
from test_active_design_polar_ui import _app, _widget
from test_blade_stations_ui import apply, explicit, has_download, upload


def navigate_away_and_back(app):
    app.sidebar.radio[0].set_value("Genel Bakış").run(timeout=20)
    app.sidebar.radio[0].set_value("Tasarım Geometrisi").run(timeout=20)
    assert not app.exception


def test_geometry_controls_and_applied_upload_survive_navigation():
    app = apply(upload(explicit(_app())))
    _widget(app.slider, "Katlanma açısı [deg]").set_value(-60).run(timeout=20)
    _widget(app.multiselect, "Geometri taraması · katlı açı [deg]").set_value([-150.]).run(timeout=20)
    _widget(app.button, "Geometri fizibilitesini tara").click().run(timeout=20)
    bundle = app.session_state["geom02_applied_bundle"]
    draft = app.session_state["geom02_active_draft"]
    report = app.session_state["geom01_result"]
    navigate_away_and_back(app)
    assert _widget(app.radio, "Kanat istasyonu kaynağı").value == "Açık istasyonlar"
    assert _widget(app.slider, "Katlanma açısı [deg]").value == -60
    assert _widget(app.multiselect, "Geometri taraması · katlı açı [deg]").value == [-150.]
    assert app.session_state["geom02_applied_bundle"] == bundle
    assert app.session_state["geom02_active_draft"] == draft
    assert app.session_state["geom01_result"] == report
    assert has_download(app)


def test_pending_table_edit_survives_navigation_without_implicit_apply():
    app = apply(upload(explicit(_app())))
    # AppTest has no data-editor cell helper; supply the same delta the browser
    # sends, then exercise the real editor rather than replacing its return value.
    key = f"geom02_table_{app.session_state['geom02_editor_revision']}"
    app.session_state[key] = {"edited_rows": {0: {"Chord [mm]": 4.}},
                              "added_rows": [], "deleted_rows": []}
    app.run(timeout=20)
    assert not has_download(app)
    navigate_away_and_back(app)
    assert not has_download(app)
    apply(app)
    assert app.session_state["geom02_applied_bundle"].stations[0].chord_m == .004


def test_saved_upload_can_be_cleared_after_navigation_without_resurrection():
    app = apply(upload(explicit(_app())))
    navigate_away_and_back(app)
    _widget(app.button, "İstasyon kaynağını temizle").click().run(timeout=20)
    assert not app.exception
    assert not has_download(app)
    assert "geom02_applied_bundle" not in app.session_state
    navigate_away_and_back(app)
    assert not has_download(app)
    apply(app)
    assert len(app.session_state["geom02_applied_bundle"].stations) == 5


def test_invalid_replacement_after_navigation_cannot_restore_applied_source():
    app = apply(upload(explicit(_app())))
    navigate_away_and_back(app)
    upload(app, b"{}")
    assert not app.exception
    assert not has_download(app)
    navigate_away_and_back(app)
    assert not has_download(app)
    assert "geom02_applied_bundle" not in app.session_state


def test_explicit_upload_removal_does_not_restore_saved_bytes():
    app = apply(upload(explicit(_app())))
    _widget(app.file_uploader, "Kanat istasyonları JSON").set_value(None).run(timeout=20)
    assert not has_download(app)
    navigate_away_and_back(app)
    assert not has_download(app)
    apply(app)
    assert len(app.session_state["geom02_applied_bundle"].stations) == 5


def test_geometry_search_at_zero_rpm_remains_available_while_bem_is_blocked():
    app = _app()
    _widget(app.number_input, "RPM").set_value(0.).run(timeout=20)
    _widget(app.button, "Geometri fizibilitesini tara").click().run(timeout=20)
    assert not app.exception
    assert has_download(app, "Geometri taramasını JSON indir")
    assert not has_download(app, "Analiz hazırlığını JSON indir")
    assert any("Analysis requires positive RPM" in item.value for item in app.warning)


def test_geometry_page_does_not_emit_plotly_width_deprecation(caplog):
    _app()
    assert not any("replace `use_container_width`" in record.message for record in caplog.records)
