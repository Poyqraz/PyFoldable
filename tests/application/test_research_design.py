from dataclasses import replace
from pathlib import Path

import pytest

from pyfoldable.application import research_design as release
from pyfoldable.application import provider_design_analysis as managed
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS

ROOT = Path(__file__).resolve().parents[2]


def test_six_profiles_share_parent_and_retain_coordinates():
    designs = [release.build_research_design(ROOT, replace(release.defaults(ROOT), profile=p))
               for p in PROJECT_AIRFOIL_IDS]
    assert len({d.coordinate_sha256 for d in designs}) == 6
    assert len({tuple((s.r_over_R, s.chord_m, s.twist_rad) for s in d.design.blade.stations)
                for d in designs}) == 1
    assert all(d.design.blade.hub_radius_m != d.inputs.root_mm / 1000 for d in designs)


def test_named_project_requirement_and_either_order_are_distinct():
    baseline = release.defaults(ROOT, "project_250")
    assert baseline.root_mm is None
    historic = release.build_research_design(ROOT, replace(
        baseline, root_mm=20, root_meaning="physical blade start", root_source="declared test root", hinge_mm=65))
    exploratory = release.build_research_design(ROOT, replace(release.defaults(ROOT), hinge_mm=205))
    assert exploratory.exposed_lengths_m[0] < exploratory.exposed_lengths_m[1]
    assert historic.exposed_lengths_m[0] < historic.exposed_lengths_m[1]
    assert managed._geometry(release.selection_for(exploratory, None))["length_order_policy"] == "either_order"
    with pytest.raises(managed.ProviderDesignPreparationError, match="longer_proximal_required"):
        managed._geometry(release.selection_for(historic, None))


def test_no_data_and_missing_mechanism_leave_geometry_and_null_totals(monkeypatch):
    d = release.build_research_design(ROOT, release.defaults(ROOT))
    monkeypatch.setattr(managed, "run_provider_design_analysis",
                        lambda *a, **k: pytest.fail("BEM reached without admission"))
    row = release.run_research(d, None, managed.ManagedProviderRepository(), None)
    assert row["geometry"]["status"] == "computed"
    assert row["aerodynamics"]["status"] == "failure"
    assert row["aerodynamics"]["thrust_n"] is None
    assert row["aerodynamics"]["report_text"] is None
    assert row["mechanism"]["status"] == "missing_inputs"
    assert release.read_saved_result(release.saved_result_json(row).encode()) == row
    row["geometry"]["status"] = "changed"
    with pytest.raises(ValueError, match="checksum"):
        release.read_saved_result(release.saved_result_json(row).encode())


def test_inert_restart_execute_export_load_and_immutable_history(tmp_path, monkeypatch):
    from research_inert_support import store, bem
    store(tmp_path, monkeypatch, ("NACA0012", "NACA2412"))
    calls = bem(monkeypatch)
    a = release.build_research_design(ROOT, replace(release.defaults(ROOT), profile="NACA0012"))
    repo = managed.application_provider_repository()
    family = next(f for f in repo.families if f.requests[0].airfoil.id == "NACA0012")
    first = release.run_research(a, family, repo, None)
    raw = release.saved_result_json(first).encode()
    assert first["aerodynamics"]["status"] == "success" and len(calls) == 1
    assert release.read_saved_result(raw) == first
    b = release.build_research_design(ROOT, replace(a.inputs, profile="NACA2412"))
    repo = managed.application_provider_repository()
    second = release.run_research(b, next(f for f in repo.families if f.requests[0].airfoil.id == "NACA2412"), repo, None)
    assert first == release.read_saved_result(raw) and len(calls) == 2
    comparison = release.compare_results([first, second])
    assert comparison["software_controlled_comparison"]
    assert not comparison["matched_numerical_comparison"]  # inert remains inert
    assert not release.compare_results([first, first])["software_controlled_comparison"]
    assert len(release.radial_rows(first)) == 40


def test_import_rejects_resealed_foreign_failure_and_malformed_provider(tmp_path, monkeypatch):
    import json
    from research_inert_support import store, bem
    a = release.build_research_design(ROOT, release.defaults(ROOT))
    failure = release.run_research(a, None, managed.ManagedProviderRepository(), None)
    foreign = release.build_research_design(ROOT, replace(a.inputs, profile="NACA0012"))
    # A valid different enclosing design, with an intact original failure snapshot.
    failure.update(inputs=release.asdict(foreign.inputs), draft_sha256=foreign.draft.draft_sha256,
                   draft_toml=foreign.draft.toml)
    failure["result_sha256"] = release._digest({k:v for k,v in failure.items() if k!="result_sha256"})
    with pytest.raises(ValueError, match="snapshot does not belong"):
        release.read_saved_result(release.saved_result_json(failure).encode())
    store(tmp_path, monkeypatch, ("NACA2412",))
    bem(monkeypatch)
    repo = managed.application_provider_repository()
    success = release.run_research(a, repo.families[0], repo, None)
    doc = json.loads(success["aerodynamics"]["report_text"])
    doc["request"]["provider_design_admission"] = []
    # Recompute every hash/outer snapshot consistently. Nested admission is still malformed.
    doc["request_sha256"] = release.design_analysis._sha(release.design_analysis._json(doc["request"]))
    text = release.design_analysis._json(doc) + "\n"
    artifact = release.design_analysis.DesignAnalysisArtifact(
        doc["request_sha256"], release.hashlib.sha256(text.encode()).hexdigest(), text, "INERT.json")
    success["aerodynamics"] = managed.snapshot_success(artifact, evidence_class="caller_supplied_unqualified")
    success["result_sha256"] = release._digest({k:v for k,v in success.items() if k!="result_sha256"})
    with pytest.raises(ValueError, match="Malformed"):
        release.read_saved_result(release.saved_result_json(success).encode())


def test_fold_and_hinge_do_not_change_open_kernel_inputs(tmp_path, monkeypatch):
    from research_inert_support import store, bem
    store(tmp_path, monkeypatch, ("NACA2412",))
    calls = bem(monkeypatch)
    a = release.build_research_design(ROOT, release.defaults(ROOT))
    b = release.build_research_design(ROOT, replace(a.inputs, hinge_mm=210, fold_deg=-20, stow_limit_deg=-30))
    repo = managed.application_provider_repository()
    for d in (a,b):
        result = release.run_research(d, repo.families[0], repo, None)
        assert result["aerodynamics"]["status"] == "success"
    assert calls[0] == calls[1]  # actual unchanged kernel signature inputs
    geometry = release.geometry_result(b)
    assert geometry["declared_stow_limit_centerline_envelope_m"] > .7
    assert "-180" in geometry["legacy_audit_full_stow_fields_scope"]


def test_invalid_optional_mechanics_does_not_erase_aero_or_geometry(tmp_path, monkeypatch):
    from research_inert_support import store, bem
    store(tmp_path, monkeypatch, ("NACA2412",))
    calls = bem(monkeypatch)
    active = release.build_research_design(ROOT, release.defaults(ROOT))
    inputs = release.MechanismInputs(10, 999, 0, "INERT assumed mass", 0, .5, 0, 0, 0, 0, 0, "none", 0, 0)
    repo = managed.application_provider_repository()
    row = release.run_research(active, repo.families[0], repo, inputs)
    assert row["geometry"]["status"] == "computed" and row["aerodynamics"]["status"] == "success"
    assert row["mechanism"]["status"] == "blocked_or_failed" and len(calls) == 1


def test_partial_mechanical_selection_is_retained_and_root_is_never_inferred(tmp_path, monkeypatch):
    from research_inert_support import store, bem
    store(tmp_path, monkeypatch, ("NACA2412",))
    calls = bem(monkeypatch)
    active = release.build_research_design(ROOT, replace(release.defaults(ROOT), root_mm=None))
    partial = release.MechanismInputs(12, None, None, "", 0, .5, 0, 0, 0, 0, 0, "none", 0, 0)
    repo = managed.application_provider_repository()
    row = release.run_research(active, repo.families[0], repo, partial)
    assert row["geometry"]["status"] == "computed"
    assert row["geometry"]["proximal_m"] is None
    assert row["aerodynamics"]["status"] == "failure" and not calls
    assert "missing_root_declaration" in row["aerodynamics"]["failure_reason"]
    assert row["mechanism"]["status"] == "missing_inputs"
    assert row["mechanism"]["inputs"]["mass_g"] == 12 and row["mechanism"]["inputs"]["cg_from_hinge_mm"] is None
    assert release.read_saved_result(release.saved_result_json(row).encode()) == row
