"""Single-screen UI with an actual isolated store; every solver seam is inert."""
import json
from pathlib import Path
import sys

import pytest
from streamlit.testing.v1 import AppTest

from pyfoldable.application import research_design as research, design_analysis
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS
from pyfoldable.providers import xfoil

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "application"))
from research_inert_support import store, bem

APP = Path(__file__).resolve().parents[2] / "apps/pyfoldable_research.py"


def app():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    return at


def test_all_six_no_upload_run_switch_save_and_restore(tmp_path, monkeypatch):
    _, versions = store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    calls = bem(monkeypatch)
    at = app()
    assert at.selectbox(key="research_profile").options == list(PROJECT_AIRFOIL_IDS)
    assert not calls
    saved = None
    for profile in PROJECT_AIRFOIL_IDS:
        at.selectbox(key="research_profile").set_value(profile).run()
        assert "research_active" not in at.session_state
        assert not at.exception
        at.selectbox(key=f"research_version_{profile}").set_value(versions[profile].content_sha256).run()
        assert len(calls) == list(PROJECT_AIRFOIL_IDS).index(profile)
        at.button(key="research_run").click().run()
        assert not at.exception and len(calls) == list(PROJECT_AIRFOIL_IDS).index(profile) + 1
        row = research.read_saved_result(at.session_state["research_active"][1].encode())
        assert row["aerodynamics"]["airfoil_id"] == profile
        assert row["aerodynamics"]["evidence_class"] == "inert_fixture"
        assert all(u.value is None for u in at.get("file_uploader"))
        if saved is None:
            saved = at.session_state["research_saved_results"][0][0]
    at.selectbox(key="research_profile").set_value("NACA4412").run()
    at.selectbox(key="research_profile").set_value("NACA2412").run()
    at.selectbox(key="research_profile").set_value("NACA4412").run()
    assert not at.exception and "research_active" not in at.session_state and len(calls) == 6
    assert at.session_state["research_saved_results"][0][0] == saved
    restored = research.read_saved_result(saved.encode())
    assert restored["aerodynamics"]["airfoil_id"] == "NACA0012"
    at.number_input(key="research_axial_800_rpm").set_value(2500.).run()
    assert "research_active" not in at.session_state and len(calls) == 6


def test_missing_store_explicit_failure_has_no_totals_or_bem(tmp_path, monkeypatch):
    monkeypatch.setenv("PYFOLDABLE_PROVIDER_STORE", str(tmp_path / "missing"))
    def forbidden(*a, **k):
        pytest.fail("Unexpected genuine solver/provider/banner")
    monkeypatch.setattr(design_analysis, "solve_bem_rotor", forbidden)
    monkeypatch.setattr(xfoil.XfoilProvider, "generate", forbidden)
    monkeypatch.setattr(xfoil, "_discover_backend_version", forbidden)
    at = app()
    at.button(key="research_run").click().run()
    assert not at.exception
    row = research.read_saved_result(at.session_state["research_active"][1].encode())
    assert row["aerodynamics"]["status"] == "failure"
    assert row["aerodynamics"]["thrust_n"] is None
    assert row["geometry"]["status"] == "computed"
    assert row["mechanism"]["status"] == "missing_inputs"


def test_store_corruption_invalidates_active_but_saved_json_stays(tmp_path, monkeypatch):
    root, versions = store(tmp_path, monkeypatch, ("NACA2412",))
    calls = bem(monkeypatch)
    at = app()
    at.selectbox(key="research_version_NACA2412").set_value(versions["NACA2412"].content_sha256).run()
    at.button(key="research_run").click().run()
    saved = at.session_state["research_saved_results"][0][0]
    record = root / "records" / (versions["NACA2412"].registration_key + ".json")
    record.unlink()
    at.run()
    assert not at.exception and "research_active" not in at.session_state and len(calls) == 1
    assert at.session_state["research_saved_results"][0][0] == saved
    assert research.read_saved_result(saved.encode())["aerodynamics"]["status"] == "success"
