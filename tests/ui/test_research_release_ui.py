"""Normal workspace with an isolated persistent store; all solvers inert."""
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
DESIGN, ANALYSIS, RESULTS, RECORDS = "Tasarım", "Analiz", "Sonuçlar", "Karşılaştırma / kayıtlar"


def app():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    return at


def field(at, label):
    return next(n for n in at.number_input if n.label == label)


def go(at, page):
    at.radio(key="research_page").set_value(page).run()
    assert not at.exception
    return at


def test_all_six_preselect_run_and_preserve_navigation_and_history(tmp_path, monkeypatch):
    _, versions = store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    calls = bem(monkeypatch)
    at = app()
    assert at.selectbox(key="research_profile").options == list(PROJECT_AIRFOIL_IDS)
    assert not calls
    saved = None
    for index, profile in enumerate(PROJECT_AIRFOIL_IDS):
        go(at, DESIGN).selectbox(key="research_profile").set_value(profile).run()
        assert not at.exception
        assert "research_active" not in at.session_state
        go(at, ANALYSIS)
        assert at.selectbox(key=f"research_version_{profile}").value == versions[profile].content_sha256
        assert not at.button(key="research_run").disabled and len(calls) == index
        at.button(key="research_run").click().run()
        assert not at.exception and len(calls) == index + 1
        assert at.radio(key="research_page").value == RESULTS
        row = research.read_saved_result(at.session_state["research_active"][1].encode())
        assert row["aerodynamics"]["airfoil_id"] == profile
        assert row["aerodynamics"]["evidence_class"] == "inert_fixture"
        assert all(u.value is None for u in at.get("file_uploader"))
        if saved is None:
            saved = at.session_state["research_saved_results"][0][0]
    go(at, DESIGN).selectbox(key="research_profile").set_value("NACA2412").run()
    at.selectbox(key="research_profile").set_value("NACA4412").run()
    assert not at.exception and "research_active" not in at.session_state and len(calls) == 6
    assert at.session_state["research_saved_results"][0][0] == saved
    assert research.read_saved_result(saved.encode())["aerodynamics"]["airfoil_id"] == "NACA0012"
    assert len(at.session_state["research_saved_results"]) == 6

    at.number_input(key="research_axial_800_rpm").set_value(2500.).run()
    go(at, ANALYSIS)
    go(at, RECORDS)
    go(at, DESIGN)
    assert at.number_input(key="research_axial_800_rpm").value == 2500.
    assert at.selectbox(key="research_profile").value == "NACA4412"
    assert len(calls) == 6


def test_missing_store_or_profile_disables_bem_without_creating_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("PYFOLDABLE_PROVIDER_STORE", str(tmp_path / "missing"))
    def forbidden(*a, **k):
        pytest.fail("Unexpected genuine solver/provider/banner")
    monkeypatch.setattr(design_analysis, "solve_bem_rotor", forbidden)
    monkeypatch.setattr(xfoil.XfoilProvider, "generate", forbidden)
    monkeypatch.setattr(xfoil, "_discover_backend_version", forbidden)
    at = go(app(), ANALYSIS)
    assert at.button(key="research_run").disabled
    assert any("deposu okunamadı" in w.value for w in at.warning)
    go(at, RESULTS)
    go(at, RECORDS)
    assert "research_saved_results" not in at.session_state

    store(tmp_path, monkeypatch, ("NACA0012",))
    at = go(app(), ANALYSIS)
    assert at.button(key="research_run").disabled
    assert any("Eşleşen veri yok" in w.value for w in at.warning)
    assert "research_active" not in at.session_state


def test_removed_version_is_not_replaced_and_saved_export_stays(tmp_path, monkeypatch):
    from pyfoldable.application.provider_record_store import ProviderRecordStore
    from pyfoldable.application import provider_design_analysis as managed
    root, versions = store(tmp_path, monkeypatch, ("NACA2412",))
    calls = bem(monkeypatch)
    at = go(app(), ANALYSIS)
    at.button(key="research_run").click().run()
    saved = at.session_state["research_saved_results"][0][0]
    family = managed.application_provider_repository().families[0]
    with ProviderRecordStore(root) as disk:
        other = disk.register_family(family, version_label="INERT-v2")
    assert other.content_sha256 != versions["NACA2412"].content_sha256
    (root / "records" / (versions["NACA2412"].registration_key + ".json")).unlink()
    at.run()
    assert not at.exception and "research_active" not in at.session_state and len(calls) == 1
    go(at, ANALYSIS)
    assert at.button(key="research_run").disabled
    assert at.selectbox(key="research_version_NACA2412").value == versions["NACA2412"].content_sha256
    assert at.session_state["research_saved_results"][0][0] == saved
    assert research.read_saved_result(saved.encode())["aerodynamics"]["status"] == "success"


def test_multiple_versions_require_choice_then_empty_selection_stays_empty(tmp_path, monkeypatch):
    from pyfoldable.application.provider_record_store import ProviderRecordStore
    from pyfoldable.application import provider_design_analysis as managed
    root, _ = store(tmp_path, monkeypatch, ("NACA2412",))
    calls = bem(monkeypatch)
    with ProviderRecordStore(root) as disk:
        second = disk.register_family(managed.application_provider_repository().families[0], version_label="INERT-v2")
    at = go(app(), ANALYSIS)
    assert at.selectbox(key="research_version_NACA2412").value is None
    assert at.button(key="research_run").disabled
    at.selectbox(key="research_version_NACA2412").set_value(second.content_sha256).run()
    assert not at.button(key="research_run").disabled
    at.selectbox(key="research_version_NACA2412").set_value(None).run()
    go(at, DESIGN)
    go(at, ANALYSIS)
    assert at.selectbox(key="research_version_NACA2412").value is None
    assert at.button(key="research_run").disabled and not calls


def test_outside_initial_domain_and_solver_failure_are_distinct(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, ("NACA2412",))
    calls = bem(monkeypatch, fail=True)
    at = app()
    at.number_input(key="research_axial_800_rpm").set_value(7100.).run()
    go(at, ANALYSIS)
    assert at.button(key="research_run").disabled
    assert any("kapsamı dışında" in w.value for w in at.warning)
    assert not calls and "research_active" not in at.session_state

    go(at, DESIGN).number_input(key="research_axial_800_rpm").set_value(2400.).run()
    go(at, ANALYSIS)
    at.button(key="research_run").click().run()
    assert not at.exception and len(calls) == 1
    row = research.read_saved_result(at.session_state["research_active"][1].encode())
    assert row["aerodynamics"]["failure_stage"] == "solver_invocation"
    assert row["aerodynamics"]["thrust_n"] is None
    go(at, RECORDS)
    assert not any(box.label == "Birinci BEM kaydı" for box in at.selectbox)
    assert len(at.session_state["research_saved_results"]) == 1


def test_segment_mode_derives_hinge_and_diameter_and_keeps_root_distinct(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, ("NACA2412",))
    calls = bem(monkeypatch)
    at = app()
    at.radio(key="research_geometry_mode_axial_800").set_value("segments").run()
    field(at, "İç parça — proksimal [mm]").set_value(110.).run()
    field(at, "Dış parça — distal [mm]").set_value(190.).run()
    assert not at.exception and not calls
    assert not any(n.label in ("Açık çap [mm]", "Menteşe konumu [mm]") for n in at.number_input)
    go(at, ANALYSIS)
    assert not calls
    go(at, DESIGN)
    at.radio(key="research_geometry_mode_axial_800").set_value("radii").run()
    assert field(at, "Menteşe konumu [mm]").value == 210.
    assert field(at, "Açık çap [mm]").value == 800.
    assert field(at, "Kök konumu [mm]").value == 100.
    assert field(at, "Göbek yarıçapı [mm]").value == 90.


def test_cosmetic_navigation_does_not_readmit_all_profiles(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    calls = bem(monkeypatch)
    original = research.prepare_aero
    inspected = []

    def observe(active, family, repo):
        inspected.append(active.inputs.profile)
        return original(active, family, repo)

    monkeypatch.setattr(research, "prepare_aero", observe)
    at = app()
    assert inspected == []
    go(at, ANALYSIS)
    assert inspected == ["NACA2412"]
    go(at, RESULTS)
    go(at, ANALYSIS)
    at.run()
    assert inspected == ["NACA2412"] and not calls
    at.button(key="research_run").click().run()
    assert not at.exception and inspected == ["NACA2412", "NACA2412"] and len(calls) == 1


def test_stale_store_at_explicit_action_retains_attempt_without_bem(tmp_path, monkeypatch):
    from pyfoldable.application import provider_design_analysis as managed
    root, versions = store(tmp_path, monkeypatch, ("NACA2412",))
    calls = bem(monkeypatch)
    at = go(app(), ANALYSIS)
    original = managed.application_provider_repository
    reads = []

    def remove_on_fresh_read():
        reads.append(True)
        if len(reads) == 2:
            (root / "records" / (versions["NACA2412"].registration_key + ".json")).unlink()
        return original()

    monkeypatch.setattr(managed, "application_provider_repository", remove_on_fresh_read)
    at.button(key="research_run").click().run()
    assert not at.exception and not calls and "research_active" not in at.session_state
    raw, imported = at.session_state["research_saved_results"][0]
    row = research.read_saved_result(raw.encode())
    aero = row["aerodynamics"]
    assert not imported and aero["failure_stage"] == "preflight_rejection"
    assert aero["attempted_selection"]["stored_version_sha256"] == versions["NACA2412"].content_sha256
    assert aero["thrust_n"] is None
    assert any("Hazırlık reddedildi" in w.value for w in at.warning)


def test_mechanics_action_is_independent_of_missing_aerodynamic_data(tmp_path, monkeypatch):
    from dataclasses import asdict
    store(tmp_path, monkeypatch, ("NACA0012",))
    bem_calls = bem(monkeypatch)
    runs = []

    def inert_mechanics(active, options):
        runs.append((active.inputs.fold_deg, options))
        return {"status": "blocked_or_failed", "scope": research._MECHANISM_SCOPE,
                "inputs": asdict(options), "reason": "INERT test mechanism outcome"}

    monkeypatch.setattr(research, "mechanism_result", inert_mechanics)
    at = go(app(), ANALYSIS)
    assert at.button(key="research_run").disabled
    at.checkbox(key="research_mechanics_on").check().run()
    assert at.button(key="research_run_mechanism").disabled
    at.number_input(key="research_mech_mass").set_value(10.)
    at.number_input(key="research_mech_cg").set_value(40.)
    at.number_input(key="research_mech_inertia").set_value(.000001)
    at.text_input(key="research_mech_source").set_value("INERT declared mechanical inputs")
    at.run()
    assert not at.exception and not runs and not bem_calls
    assert not at.button(key="research_run_mechanism").disabled
    at.button(key="research_run_mechanism").click().run()
    assert not at.exception and len(runs) == 1 and not bem_calls
    row = research.read_saved_result(at.session_state["research_active"][1].encode())
    assert row["aerodynamics"] is None and row["mechanism"]["status"] == "blocked_or_failed"
    # Inspect the saved record in a fresh test session. AppTest 1.40 can
    # serialize stale number widgets from the run interrupted by st.rerun.
    records = app()
    records.session_state["research_saved_results"] = ((research.saved_result_json(row), True),)
    go(records, RECORDS)
    assert not any(box.label == "Birinci BEM kaydı" for box in records.selectbox)
    assert any("bağımsız mekanizma kaydı" in c.value for c in records.caption)


def test_source_summary_names_the_retained_research_families():
    from types import SimpleNamespace
    from pyfoldable.application import research_ui
    family = lambda fid, src="operator-captured numerical records; plan_sha256:x": SimpleNamespace(  # noqa: E731
        family_id=fid, source_identity=src)
    assert research_ui._source_summary(family("research_axial_800_attached_xfoil_v1:NACA2412")) == \
        "800 mm eksenel referansın saklanan sağlayıcı çıktıları"
    deploy = research_ui._source_summary(family("research_axial_800_deploy_xfoil_v3:NACA2412"))
    assert "açılma" in deploy and "Re 100k–400k" in deploy and "Mach 0,07–0,36" in deploy and "ekli akış" in deploy
    assert research_ui._source_summary(family("other:X", "caller source; detail")) == "caller source"


def test_deploy_family_shows_the_convergence_prescreen_caveat():
    from types import SimpleNamespace
    from pyfoldable.application import research_ui
    deploy = research_ui._source_note(SimpleNamespace(family_id="research_axial_800_deploy_xfoil_v3:NACA2412"))
    assert "ön tarama" in deploy and "130k" in deploy and "ara değer" in deploy and "ayrılmış akış" in deploy
    assert research_ui._source_note(SimpleNamespace(family_id="research_axial_800_attached_xfoil_v1:NACA2412")) is None
