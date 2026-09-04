"""Real Streamlit AppTest integration, executed by the UI-enabled CI matrix."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[2] / "apps" / "pyfoldable_dashboard.py"


def payload():
    return json.dumps({
        "mass_distribution": {
            "source": "synthetic test only",
            "classification": "synthetic_test_fixture",
            "samples": [{"distance_from_hinge_m": 0.01, "mass_kg": 0.04, "source": "synthetic"}],
        },
        "mechanical_source": "synthetic",
        "spring_stiffness_nm_rad": 0.02,
        "rest_angle_rad": 0.0,
        "viscous_damping_nm_s_rad": 0.001,
        "initial_angle_rad": -0.5,
        "initial_angular_velocity_rad_s": 0.0,
        "drive": {
            "time_s": [0.0, 0.01], "rpm": [0.0, 10.0],
            "applied_hinge_torque_nm": [0.0, 0.0],
        },
        "dry_friction": {
            "mode": "none", "coulomb_torque_nm": 0.0,
            "transition_velocity_rad_s": 0.0, "source": "explicit_frictionless_model",
        },
    })


def page():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Tasarım Geometrisi").run()
    next(w for w in app.checkbox if w.label == "Aktif taslağa bağlı mekanizma analizini aç").check().run()
    next(w for w in app.text_area if w.label == "Aktif mekanizma girdileri [JSON]").set_value(payload()).run()
    assert not app.exception
    return app


def test_bound_run_and_valid_geometry_change_invalidate_download():
    app = page()
    assert "py05_bound_result" not in app.session_state
    next(w for w in app.button if w.label == "Aktif mekanizmayı çalıştır").click().run()
    assert not app.exception
    artifact = app.session_state["py05_bound_result"]
    document = json.loads(artifact.report_json)
    assert document["physical_qualification"] is False
    assert document["request"]["provenance"]["references"][0]["binding"]["draft_sha256"]
    next(w for w in app.slider if w.label == "Chord ölçeği").set_value(1.1).run()
    assert not app.exception
    assert "py05_bound_result" not in app.session_state
    assert not any(w.label == "Aktif mekanizma sonucunu JSON indir" for w in app.get("download_button"))


def test_bound_failed_rerun_clears_download(monkeypatch):
    app = page()
    next(w for w in app.button if w.label == "Aktif mekanizmayı çalıştır").click().run()
    import pyfoldable.application.mechanism_transient as service

    def fail(*args, **kwargs):
        raise service.MechanismTransientError("injected failure")

    monkeypatch.setattr(service, "run_bound_mechanism_transient", fail)
    next(w for w in app.button if w.label == "Aktif mekanizmayı çalıştır").click().run()
    assert not app.exception
    assert "py05_bound_result" not in app.session_state
    assert not any(w.label == "Aktif mekanizma sonucunu JSON indir" for w in app.get("download_button"))


def test_bound_invalid_json_is_controlled():
    app = page()
    next(w for w in app.text_area if w.label == "Aktif mekanizma girdileri [JSON]").set_value("{}").run()
    assert not app.exception
    assert "py05_bound_result" not in app.session_state
    assert not any(w.label == "Aktif mekanizmayı çalıştır" for w in app.button)
