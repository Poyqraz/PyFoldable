"""Catalog profile comparison uses inert polars and the existing BEM path."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace

import pytest

from pyfoldable.application.design_analysis import DesignAnalysisArtifact, DesignAnalysisError, run_design_analysis
from pyfoldable.application.design_draft import DesignDraftInputs, build_design_draft
from pyfoldable.application.polar_upload import inspect_polar_bundle, prepare_polar_run, run_polar_run
from pyfoldable.application.profile_bem_comparison import (
    ProfileComparisonError,
    add_record,
    comparison_csv,
    comparison_document,
    identities_for_draft,
    snapshot_failure,
    snapshot_success,
)
from pyfoldable.core import BEMAnnulusSettings, BEMRotorSettings, PolarTable
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS, load_project_airfoil


def _draft(airfoil_id: str = "NACA2412", **changes):
    inputs = DesignDraftInputs(
        diameter="250 mm", hub_radius="18 mm", hinge_radius="100 mm", blade_count=2,
        airfoil_id=airfoil_id, chord_scale=1.0, twist_scale=1.0,
        preview_fold_angle="0 deg", angular_speed="7100 rpm", forward_speed="0 m/s",
        air_density="1.225 kg/m^3", dynamic_viscosity="1.81e-5 Pa*s",
        temperature="288.15 K", pressure="101325 Pa",
    )
    return build_design_draft(
        "configs/designs/TIP_HINGED_250_CANONICAL.toml",
        replace(inputs, **changes) if changes else inputs,
        airfoil_definition=load_project_airfoil(airfoil_id),
    )


def _payload(airfoil_id: str) -> bytes:
    foil = load_project_airfoil(airfoil_id)
    document = {
        "schema_version": 1,
        "artifact_class": "active_design_polar_bundle",
        "physical_qualification": False,
        "tables": [asdict(PolarTable(
            airfoil_id=foil.id, reynolds=reynolds, mach=mach, alpha_rad=(-1.57, 1.57),
            cl=(0.8, 0.8), cd=(0.02, 0.02), cm=(0.0, 0.0), scenario_id="inert-fixture",
            source="inert fixture; not a real-provider polar",
            metadata={
                "airfoil_coordinate_sha256": foil.metadata["airfoil_coordinate_sha256"],
                "provider": {"name": "inert-fixture", "version": "0"},
            },
        )) for reynolds in (100.0, 1.0e7) for mach in (0.0, 1.0)],
    }
    return json.dumps(document).encode()


def _success(airfoil_id: str = "NACA2412", **changes):
    draft = _draft(airfoil_id, **changes)
    artifact = run_polar_run(prepare_polar_run(draft, _payload(airfoil_id), annulus_count=4))
    return snapshot_success(artifact, evidence_class="inert_fixture")


def test_five_catalog_profiles_keep_distinct_geometry_and_one_planform() -> None:
    assert PROJECT_AIRFOIL_IDS == ("NACA0012", "NACA2412", "NACA23012", "NACA4415", "NACA63-412")
    identities = [identities_for_draft(_draft(airfoil_id), annulus_count=4) for airfoil_id in PROJECT_AIRFOIL_IDS]
    coordinates = {row["airfoil_coordinate_sha256"] for row in identities}
    drafts = {row["draft_sha256"] for row in identities}
    geometries = {row["geometry_sha256"] for row in identities}
    planforms = {row["planform_sha256"] for row in identities}
    conditions = {row["condition_sha256"] for row in identities}
    assert len(coordinates) == 5
    assert len(drafts) == 5
    assert len(geometries) == 5
    assert planforms == {identities[0]["planform_sha256"]}
    assert conditions == {identities[0]["condition_sha256"]}
    assert all(row["physical_qualification"] is False for row in identities)
    snapshots = [_success(airfoil_id) for airfoil_id in PROJECT_AIRFOIL_IDS]
    assert [row["airfoil_id"] for row in snapshots] == list(PROJECT_AIRFOIL_IDS)
    assert len({row["record_sha256"] for row in snapshots}) == 5
    assert len({row["geometry_sha256"] for row in snapshots}) == 5
    assert {row["planform_sha256"] for row in snapshots} == planforms
    assert all(row["status"] == "success" and row["evidence_class"] == "inert_fixture" for row in snapshots)


def test_saved_record_keeps_its_profile_after_the_selector_changes() -> None:
    first = _success("NACA2412")
    second = _success("NACA0012")
    saved = add_record((), first)
    saved = add_record(saved, second)
    assert saved[0]["airfoil_id"] == "NACA2412"
    assert saved[1]["airfoil_id"] == "NACA0012"
    assert saved[0]["draft_sha256"] != saved[1]["draft_sha256"]
    assert saved[0]["planform_sha256"] == saved[1]["planform_sha256"]
    document = comparison_document(saved, evidence_class="inert_fixture")
    assert document["software_controlled_comparison"] is True
    assert document["performance_comparison"] is False
    assert document["genuine_comparison_status"] == "BLOCKED_no_matching_real_provider_polar_bundle"
    assert document["qualified_winner"] is None
    assert "propulsive_efficiency" not in comparison_csv(document)
    assert "shaft_power_w" in comparison_csv(document)
    assert saved[0]["radial_elements"]


def test_unlike_condition_is_not_a_controlled_comparison() -> None:
    matched = _success("NACA2412")
    changed = _success("NACA2412", angular_speed="6800 rpm")
    document = comparison_document(add_record(add_record((), matched), changed), evidence_class="inert_fixture")
    assert document["settings_compatible"] is False
    assert document["software_controlled_comparison"] is False
    assert any(reason.endswith("condition_sha256") for reason in document["mismatch_reasons"])
    assert document["records"][0]["thrust_n"] == matched["thrust_n"]
    assert document["records"][1]["airfoil_id"] == "NACA2412"


def test_wrong_coordinate_polar_and_solver_failure_have_no_totals(monkeypatch) -> None:
    draft = _draft("NACA0012")
    foreign = _payload("NACA2412")
    with pytest.raises(Exception, match="coordinate|profile|match"):
        prepare_polar_run(draft, foreign)
    import pyfoldable.application.design_analysis as analysis
    monkeypatch.setattr(analysis, "solve_bem_rotor", lambda *args, **kwargs: pytest.fail("rejected polar reached BEM"))
    failure = snapshot_failure(
        draft, reason="Polar coordinate SHA-256 does not match the active draft.",
        annulus_count=4, evidence_class="inert_fixture",
        polar_source_sha256="a" * 64,
    )
    other = snapshot_failure(
        draft, reason="Polar coordinate SHA-256 does not match the active draft.",
        annulus_count=4, evidence_class="inert_fixture",
        polar_source_sha256="b" * 64,
    )
    assert failure["record_sha256"] != other["record_sha256"]
    csv_text = comparison_csv(comparison_document((failure,), evidence_class="inert_fixture"))
    assert "null,null,null" in csv_text
    assert failure["status"] == "failure"
    assert failure["thrust_n"] is None
    assert failure["torque_nm"] is None
    assert failure["shaft_power_w"] is None
    assert failure["radial_elements"] is None

    def explode(*_args, **_kwargs):
        raise DesignAnalysisError("coverage missing; no partial totals")

    monkeypatch.setattr(analysis, "solve_bem_rotor", explode)
    with pytest.raises(DesignAnalysisError):
        run_polar_run(prepare_polar_run(_draft(), _payload("NACA2412"), annulus_count=4))
    failed_run = snapshot_failure(
        _draft(), reason="coverage missing; no partial totals",
        annulus_count=4, evidence_class="inert_fixture",
    )
    text = json.dumps(failed_run)
    assert "thrust_n\": null" in text or '"thrust_n":null' in text.replace(" ", "")
    assert failed_run["thrust_n"] is None


def test_switch_back_does_not_relabel_the_first_snapshot() -> None:
    alpha = _success("NACA4415")
    beta = _success("NACA63-412")
    again = _success("NACA4415")
    saved = add_record(add_record(add_record((), alpha), beta), again)
    assert [row["airfoil_id"] for row in saved] == ["NACA4415", "NACA63-412", "NACA4415"]
    assert saved[0] == alpha
    assert saved[0]["record_sha256"] == saved[2]["record_sha256"]
    assert saved[0]["airfoil_id"] != saved[1]["airfoil_id"]
    with pytest.raises(ProfileComparisonError):
        add_record(saved, {**alpha, "airfoil_id": "NACA0012"})


def _settings(**annulus):
    return BEMRotorSettings(annulus_count=4, annulus_settings=BEMAnnulusSettings(**annulus))


def _analysis(airfoil_id: str, settings: BEMRotorSettings):
    draft = _draft(airfoil_id)
    bundle = inspect_polar_bundle(_payload(airfoil_id))
    return run_design_analysis(draft, {airfoil_id: bundle.to_family()}, settings=settings)


def _document(*records):
    saved = ()
    for record in records:
        saved = add_record(saved, record)
    return comparison_document(saved, evidence_class="inert_fixture")


def _reseal(record, **changes):
    body = {key: value for key, value in record.items() if key != "record_sha256"}
    body.update(changes)
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    body["record_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return json.loads(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def test_tip_loss_and_iteration_policies_are_not_interchangeable() -> None:
    enabled = snapshot_success(_analysis("NACA2412", _settings(include_tip_loss=True)), evidence_class="inert_fixture")
    disabled = snapshot_success(_analysis("NACA2412", _settings(include_tip_loss=False)), evidence_class="inert_fixture")
    iterations = snapshot_success(_analysis("NACA2412", _settings(max_iterations=80)), evidence_class="inert_fixture")
    tip = _document(enabled, disabled)
    steps = _document(enabled, iterations)
    assert tip["settings_compatible"] is False
    assert steps["settings_compatible"] is False
    assert enabled["admitted_policy"]["annulus_settings"]["include_tip_loss"] is True
    assert disabled["admitted_policy"]["annulus_settings"]["include_tip_loss"] is False
    assert enabled["admitted_policy"]["annulus_settings"]["max_iterations"] == 100
    assert iterations["admitted_policy"]["annulus_settings"]["max_iterations"] == 80
    assert enabled["admitted_policy_sha256"] != disabled["admitted_policy_sha256"]
    assert enabled["admitted_policy_sha256"] != iterations["admitted_policy_sha256"]


def test_identical_complete_policies_compare_distinct_profiles() -> None:
    settings = _settings()
    first = snapshot_success(_analysis("NACA23012", settings), evidence_class="inert_fixture")
    second = snapshot_success(_analysis("NACA4415", settings), evidence_class="inert_fixture")
    document = _document(first, second)
    assert first["admitted_policy"] == second["admitted_policy"]
    assert first["airfoil_coordinate_sha256"] != second["airfoil_coordinate_sha256"]
    assert document["settings_compatible"] is True
    assert document["software_controlled_comparison"] is True
    assert document["performance_comparison"] is False
    assert document["genuine_comparison_status"] == "BLOCKED_no_matching_real_provider_polar_bundle"


def test_repeated_runs_and_relabeling_are_not_profile_comparisons() -> None:
    original = _success("NACA2412")
    duplicate = _document(original, original)
    assert duplicate["settings_compatible"] is True
    assert duplicate["software_controlled_comparison"] is False
    again = _success("NACA2412")
    repeated = _document(original, again)
    assert repeated["software_controlled_comparison"] is False
    relabeled = _reseal(original, airfoil_id="NACA0012")
    renamed = _document(original, relabeled)
    assert renamed["records"][1]["airfoil_id"] == "NACA0012"
    assert renamed["records"][0]["airfoil_coordinate_sha256"] == renamed["records"][1]["airfoil_coordinate_sha256"]
    assert renamed["software_controlled_comparison"] is False
    missing = _reseal(original, airfoil_coordinate_sha256=None)
    other = _success("NACA0012")
    incomplete = _document(missing, other)
    assert incomplete["software_controlled_comparison"] is False
    distinct = _document(original, other)
    assert distinct["software_controlled_comparison"] is True


def test_failures_stay_visible_without_becoming_a_successful_comparison() -> None:
    success = _success("NACA2412")
    failure = snapshot_failure(
        _draft("NACA0012"), reason="coverage missing; no partial totals",
        annulus_count=4, evidence_class="inert_fixture", failure_stage="solver_invocation",
    )
    document = _document(success, failure)
    assert [row["status"] for row in document["records"]] == ["success", "failure"]
    assert document["records"][1]["thrust_n"] is None
    assert document["software_controlled_comparison"] is False
    assert document["performance_comparison"] is False


def test_preflight_rejection_keeps_foreign_identity_without_an_executed_request() -> None:
    foreign = _payload("NACA2412")
    draft = _draft("NACA0012")
    with pytest.raises(Exception):
        prepare_polar_run(draft, foreign)
    bundle = inspect_polar_bundle(foreign)
    failure = snapshot_failure(
        draft, reason="Polar profile does not match the active draft.",
        evidence_class="inert_fixture", failure_stage="preflight_rejection",
        polar_source_sha256=hashlib.sha256(foreign).hexdigest(),
        polar_airfoil_id=bundle.airfoil_id,
        polar_coordinate_sha256=bundle.coordinate_sha256,
    )
    assert failure["airfoil_id"] == "NACA0012"
    assert failure["polar_airfoil_id"] == "NACA2412"
    assert failure["polar_coordinate_sha256"] == bundle.coordinate_sha256
    assert failure["analysis_request_sha256"] is None
    assert failure["ui_request_sha256"] is None
    assert failure["executed_policy"] is None
    assert failure["report_sha256"] is None
    assert failure["report_text"] is None
    assert failure["thrust_n"] is None
    assert isinstance(failure["attempt_sha256"], str) and len(failure["attempt_sha256"]) == 64


def test_uninspectable_upload_does_not_invent_polar_identity() -> None:
    failure = snapshot_failure(
        _draft(), reason="Polar JSON is malformed.", evidence_class="inert_fixture",
        failure_stage="preflight_rejection", polar_source_sha256="ab" * 32,
        polar_unavailable_reason="Polar bundle root fields must match the version-1 contract.",
    )
    assert failure["polar_airfoil_id"] is None
    assert failure["polar_coordinate_sha256"] is None
    assert failure["polar_unavailable_reason"] == "Polar bundle root fields must match the version-1 contract."
    assert failure["executed_policy"] is None


def test_export_binds_each_csv_row_to_its_report_and_request() -> None:
    record = _success("NACA63-412")
    document = _document(record)
    assert document["schema_version"] == 2
    assert hashlib.sha256(record["report_text"].encode()).hexdigest() == record["report_sha256"]
    envelope = record["radial_elements"][0]["solution"]["polar_query_envelope"]
    assert envelope["query_count"] > 0
    assert record["polar_query_envelope"]["query_count"] >= envelope["query_count"]
    assert record["analysis_request_sha256"] != record["ui_request_sha256"]
    csv_text = comparison_csv(document)
    assert record["record_sha256"] in csv_text
    assert record["analysis_request_sha256"] in csv_text
    assert record["ui_request_sha256"] in csv_text
    assert record["report_sha256"] in csv_text
    assert "polar_query_envelope" not in csv_text
    assert "differential_thrust_n_m" not in csv_text
    assert "null,null,null" not in csv_text
    failed = snapshot_failure(
        _draft(), reason="coverage missing; no partial totals",
        evidence_class="inert_fixture", failure_stage="preflight_rejection",
    )
    failed_csv = comparison_csv(_document(failed))
    assert "null,null,null" in failed_csv


def _with_report(document: dict) -> DesignAnalysisArtifact:
    text = json.dumps(document)
    return DesignAnalysisArtifact(
        "snapshot", hashlib.sha256(text.encode()).hexdigest(), text, "snapshot.json",
    )


def test_missing_or_contradictory_policy_is_not_replaced_by_defaults() -> None:
    artifact = _analysis("NACA2412", _settings())
    document = json.loads(artifact.report_json)
    document["request"]["policy"]["annulus_settings"].pop("include_tip_loss")
    document["rotor"]["settings"]["annulus_settings"].pop("include_tip_loss")
    with pytest.raises(ProfileComparisonError, match="incomplete|missing|policy"):
        snapshot_success(_with_report(document), evidence_class="inert_fixture")
    conflict = json.loads(artifact.report_json)
    conflict["request"]["policy"]["annulus_settings"]["max_iterations"] = 80
    with pytest.raises(ProfileComparisonError, match="contradict"):
        snapshot_success(_with_report(conflict), evidence_class="inert_fixture")
    element = json.loads(artifact.report_json)
    element["rotor"]["elements"][0]["solution"]["settings"]["max_iterations"] = 80
    with pytest.raises(ProfileComparisonError, match="contradict"):
        snapshot_success(_with_report(element), evidence_class="inert_fixture")
    fresh = _success("NACA2412")
    changed = json.loads(json.dumps(fresh))
    changed["admitted_policy"]["annulus_settings"]["include_tip_loss"] = False
    tampered = _reseal(changed)
    with pytest.raises(ProfileComparisonError, match="policy hash"):
        add_record((), tampered)
