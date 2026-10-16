"""Catalog profile comparison uses inert polars and the existing BEM path."""

from __future__ import annotations

import json
from dataclasses import asdict, replace

import pytest

from pyfoldable.application.design_analysis import DesignAnalysisError
from pyfoldable.application.design_draft import DesignDraftInputs, build_design_draft
from pyfoldable.application.polar_upload import prepare_polar_run, run_polar_run
from pyfoldable.application.profile_bem_comparison import (
    ProfileComparisonError,
    add_record,
    comparison_csv,
    comparison_document,
    identities_for_draft,
    snapshot_failure,
    snapshot_success,
)
from pyfoldable.core import PolarTable
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
