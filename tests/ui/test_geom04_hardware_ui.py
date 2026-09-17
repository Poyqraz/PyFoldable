"""GEOM-04 explicit hardware upload and bounded narrow-phase UI lifecycle."""
import json

from test_active_design_polar_ui import _app, _widget
from test_blade_stations_ui import has_download
from test_geometry_navigation_ui import navigate_away_and_back


UPLOAD = "Göbek ve bağlantı geometrisi JSON"
RUN = "Katlanma boyunca yüzey açıklığını denetle"
DOWNLOAD = "Yüzey açıklığı raporunu JSON indir"


def upload(app, raw):
    _widget(app.file_uploader, UPLOAD).set_value(
        ("hardware.json", raw, "application/json")
    ).run(timeout=30)
    assert not app.exception
    return app


def test_invalid_hardware_blocks_run_and_clears_old_report():
    app = _app()
    app.session_state["geom03_result"] = "previous hardware report"
    upload(app, b"{}")
    assert "geom03_result" not in app.session_state
    assert not has_download(app, DOWNLOAD)
    assert not any(button.label == RUN for button in app.button)
    navigate_away_and_back(app)
    assert app.session_state["geom04_saved_upload"] == b"{}"
    assert not any(button.label == RUN for button in app.button)


def test_hardware_clear_is_explicit_and_does_not_restore_after_navigation():
    app = upload(_app(), b"{}")
    navigate_away_and_back(app)
    _widget(app.button, "Donanım kaynağını temizle").click().run(timeout=30)
    assert not app.exception
    assert any(button.label == RUN for button in app.button)
    navigate_away_and_back(app)
    assert ("geom04_saved_upload" not in app.session_state or app.session_state["geom04_saved_upload"] is None)
    assert not has_download(app, DOWNLOAD)


def test_hardware_upload_removal_does_not_restore_durable_bytes():
    app = upload(_app(), b"{}")
    _widget(app.file_uploader, UPLOAD).set_value(None).run(timeout=30)
    navigate_away_and_back(app)
    assert ("geom04_saved_upload" not in app.session_state or app.session_state["geom04_saved_upload"] is None)
    assert any(button.label == RUN for button in app.button)


def test_new_budgets_survive_navigation_and_invalid_geometry():
    app = _app()
    _widget(app.selectbox, "Dar faz · Özellik sorgusu bütçesi").set_value(512).run(timeout=30)
    _widget(app.selectbox, "Donanım · Sorgu bütçesi").set_value(64).run(timeout=30)
    navigate_away_and_back(app)
    _widget(app.number_input, "Göbek yarıçapı [mm]").set_value(120.).run(timeout=30)
    _widget(app.number_input, "Göbek yarıçapı [mm]").set_value(18.).run(timeout=30)
    assert _widget(app.selectbox, "Dar faz · Özellik sorgusu bütçesi").value == 512
    assert _widget(app.selectbox, "Donanım · Sorgu bütçesi").value == 64


def payload(revision="v1"):
    """Synthetic software fixture, not this propeller's measured hardware."""
    return json.dumps({"schema_version": "pyfoldable.hardware.v1", "units": "mm",
        "provenance": {"kind": "synthetic", "source": "UI lifecycle fixture",
                       "revision": revision, "source_sha256": "a" * 64},
        "bodies": [{"name": "hub", "binding": "hub", "frame": "body_local",
            "transform": {"rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                          "translation": [0, 0, 0]},
            "tolerance": .01,
            "geometry": {"kind": "finite_cylinder", "radius": 18, "height": 20,
                         "segments": 16, "approximation_tolerance": .5}}]}).encode()


def test_valid_hardware_run_retains_source_and_revision_change_invalidates():
    app = upload(_app(), payload())
    _widget(app.selectbox, "Dar faz · Özellik sorgusu bütçesi").set_value(512).run(timeout=30)
    _widget(app.selectbox, "Donanım · Sorgu bütçesi").set_value(64).run(timeout=30)
    _widget(app.button, RUN).click().run(timeout=60)
    assert not app.exception
    assert has_download(app, DOWNLOAD)
    report = json.loads(app.session_state["geom03_result"].report_json)
    assert report["schema_version"] == 2
    assert report["request"]["hardware"] is not None
    assert report["physical_qualification"] is False
    assert report["hardware_queries"] <= 64
    assert report["feature_tests"] <= 512
    artifact = app.session_state["geom03_result"]
    navigate_away_and_back(app)
    assert app.session_state["geom04_saved_upload"] == payload()
    assert app.session_state["geom03_result"] == artifact
    upload(app, payload("v2"))
    assert "geom03_result" not in app.session_state
    assert not has_download(app, DOWNLOAD)


def test_oversized_upload_cannot_fall_back_to_no_hardware():
    from pyfoldable.application.hardware_contract import MAX_HARDWARE_BYTES
    app = upload(_app(), b" " * (MAX_HARDWARE_BYTES + 1))
    assert not any(button.label == RUN for button in app.button)
    assert any("KiB" in item.value for item in app.error)
    navigate_away_and_back(app)
    assert not any(button.label == RUN for button in app.button)
