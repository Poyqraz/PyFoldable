"""GEOM-02 explicit application, one geometry, and stale-result regressions."""
import json

from test_active_design_polar_ui import _app, _widget
from pyfoldable.core.profile_catalog import load_project_airfoil


def payload():
    return json.dumps({
        "schema_version": 1, "units": {"length": "mm", "angle": "deg"},
        "diameter": 250, "hub_radius": 18, "airfoil_id": "NACA2412",
        "airfoil_coordinate_sha256": load_project_airfoil("NACA2412").metadata["airfoil_coordinate_sha256"],
        "provenance": {"kind": "declared_design", "reference": "synthetic UI test",
                       "locator": "explicit stations", "revision": "1"},
        "stations": [{"radius": 18, "chord": 3, "twist": 20},
                     {"radius": 70, "chord": 2, "twist": 10},
                     {"radius": 125, "chord": 1, "twist": 5}],
    }).encode()


def explicit(app):
    _widget(app.radio, "Kanat istasyonu kaynağı").set_value("Açık istasyonlar").run(timeout=20)
    return app


def upload(app, raw=None):
    _widget(app.file_uploader, "Kanat istasyonları JSON").set_value(
        ("stations.json", payload() if raw is None else raw, "application/json")
    ).run(timeout=20)
    return app


def has_download(app, label="Taslak TOML indir"):
    return any(item.label == label for item in app.get("download_button"))


def apply(app):
    _widget(app.button, "İstasyonları uygula").click().run(timeout=20)
    assert not app.exception
    return app


def test_explicit_upload_needs_apply_and_geometry_change_clears_results():
    app = upload(explicit(_app()))
    assert not app.exception
    assert not has_download(app)
    assert _widget(app.slider, "Chord ölçeği").disabled
    apply(app)
    assert has_download(app)
    _widget(app.button, "Geometri fizibilitesini tara").click().run(timeout=20)
    assert has_download(app, "Geometri taramasını JSON indir")
    report = json.loads(app.session_state["geom01_result"].report_json)
    assert report["best_candidate"] is None
    assert all(row["constraints"]["station_span_complete"] for row in report["candidates"])
    _widget(app.number_input, "Açık çap [mm]").set_value(260.).run(timeout=20)
    assert not has_download(app)
    assert "geom01_result" not in app.session_state
    _widget(app.number_input, "Açık çap [mm]").set_value(250.).run(timeout=20)
    assert not has_download(app)  # no resurrection without a new explicit apply


def test_invalid_replacement_clears_applied_geometry_and_analysis():
    app = apply(upload(explicit(_app())))
    for key in ("py03_polar_result", "py04_search_result", "py05_bound_result", "py05_transient_result"):
        app.session_state[key] = "old result"
    upload(app, b"{}")
    assert not app.exception
    assert not has_download(app)
    for key in ("py03_polar_result", "py04_search_result", "py05_bound_result", "py05_transient_result"):
        assert key not in app.session_state


def test_preview_uses_exact_draft_stations_without_second_scaling(monkeypatch):
    from pyfoldable.application import design_draft
    from pyfoldable.visualization import propeller_25d
    built = []
    meshes = []
    original_draft = design_draft.build_design_draft
    original_mesh = propeller_25d.build_propeller_preview_mesh
    def capture_draft(*args, **kwargs):
        result = original_draft(*args, **kwargs)
        built.append(result)
        return result
    def capture_mesh(spec, stations, *args, **kwargs):
        meshes.append((spec, stations))
        return original_mesh(spec, stations, *args, **kwargs)
    monkeypatch.setattr(design_draft, "build_design_draft", capture_draft)
    monkeypatch.setattr(propeller_25d, "build_propeller_preview_mesh", capture_mesh)
    app = _app()
    _widget(app.slider, "Chord ölçeği").set_value(1.5).run(timeout=20)
    apply(upload(explicit(app)))
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib
    document = tomllib.loads(built[-1].toml)
    assert [row["chord"] for row in document["blade"]["stations"]] == ["3.0 mm", "2.0 mm", "1.0 mm"]
    spec, stations = meshes[-1]
    assert spec.chord_scale == spec.twist_scale == 1
    assert [s.chord_m for s in stations] == [.003, .002, .001]
    assert len(stations) == 3


def test_mode_switch_does_not_restore_an_old_explicit_result():
    app = apply(upload(explicit(_app())))
    _widget(app.radio, "Kanat istasyonu kaynağı").set_value("Parametrik taslak").run(timeout=20)
    assert has_download(app)
    explicit(app)
    assert not has_download(app)


def test_table_edit_creates_derived_source_and_requires_reapply(monkeypatch):
    import streamlit as st
    original = st.data_editor
    change = {"chord": None}
    def edit(*args, **kwargs):
        rows = original(*args, **kwargs)  # render the actual editor in AppTest
        if change["chord"] is not None:
            rows[0]["Chord [mm]"] = change["chord"]
        return rows
    monkeypatch.setattr(st, "data_editor", edit)
    app = apply(upload(explicit(_app())))
    original_bundle = app.session_state["geom02_applied_bundle"]
    parent = original_bundle.canonical_sha256
    change["chord"] = 4.
    app.run(timeout=20)
    assert not has_download(app)
    apply(app)
    bundle = app.session_state["geom02_applied_bundle"]
    assert bundle.stations[0].chord_m == .004
    assert bundle.provenance.kind == "derived_geometry"
    assert bundle.provenance.parent_sha256 == parent
    assert bundle.stations[0].radius_m == original_bundle.stations[0].radius_m
    assert bundle.stations[0].twist_rad == original_bundle.stations[0].twist_rad
    assert bundle.stations[1:] == original_bundle.stations[1:]
    change["chord"] = -1.
    app.run(timeout=20)
    assert not app.exception
    assert not has_download(app)
    assert "geom02_applied_bundle" not in app.session_state


def test_rebind_requires_apply_and_never_rescales_physical_stations():
    app = apply(upload(explicit(_app())))
    original = app.session_state["geom02_applied_bundle"]
    _widget(app.number_input, "Açık çap [mm]").set_value(300.).run(timeout=20)
    assert not has_download(app)
    _widget(app.button, "Tabloyu güncel ölçülere yeniden bağla").click().run(timeout=20)
    assert not app.exception
    assert not has_download(app)
    apply(app)
    rebound = app.session_state["geom02_applied_bundle"]
    assert rebound.stations == original.stations
    assert rebound.diameter_m == .3
    assert rebound.provenance.kind == "derived_geometry"
    assert rebound.provenance.parent_sha256 == original.canonical_sha256


def test_uncovered_hinge_cannot_leave_an_applied_download():
    doc = json.loads(payload())
    doc["stations"][-1]["radius"] = 90
    app = upload(explicit(_app()), json.dumps(doc).encode())
    if any(item.label == "İstasyonları uygula" for item in app.button):
        apply(app)
    assert not app.exception
    assert not has_download(app, "Etkin istasyon JSON indir")
    assert "geom02_applied_bundle" not in app.session_state


def test_failed_draft_build_cannot_leave_an_applied_download(monkeypatch):
    from pyfoldable.application import design_draft
    app = apply(upload(explicit(_app())))
    def fail(*args, **kwargs):
        raise ValueError("intentional draft failure")
    monkeypatch.setattr(design_draft, "build_design_draft", fail)
    apply(app)
    assert not has_download(app, "Etkin istasyon JSON indir")
    assert "geom02_applied_bundle" not in app.session_state
