"""PR-09 test-first structural/FEA evidence contract."""

from __future__ import annotations

import pytest

from pyfoldable.core.fea_contract import (
    CADRevisionIdentity,
    FEAAcceptancePolicy,
    FEALoadCase,
    FEAMaterialIdentity,
    FEAMeshLevel,
    FEAProjectManifest,
    FEAResultCase,
    assess_fea_result_bundle,
)


SHA = "a" * 64


def _cad() -> CADRevisionIdentity:
    return CADRevisionIdentity(
        design_id="TIP_HINGED_250_CANONICAL",
        revision="A",
        filename="tip_hinged_250_rev_a.step",
        file_format="STEP AP242",
        sha256=SHA,
        length_unit="m",
        coordinate_frame="shaft_z_right_handed",
    )


def _material() -> FEAMaterialIdentity:
    return FEAMaterialIdentity(
        id="PA_CF_COUPON_V1",
        model="orthotropic",
        source="project_coupon_test_plan_v1",
        property_names=(
            "density_kg_m3",
            "elastic_modulus_x_pa",
            "elastic_modulus_y_pa",
            "elastic_modulus_z_pa",
            "poisson_xy",
            "shear_modulus_xy_pa",
            "allowable_x_pa",
            "allowable_y_pa",
        ),
        qualification="software_fixture_not_material_evidence",
    )


def _case(case_id: str = "steady_max_rpm") -> FEALoadCase:
    return FEALoadCase(
        id=case_id,
        analysis_type="static_structural",
        load_source_id="pr07-operating-envelope-v1",
        required_metric_units={
            "maximum_von_mises_stress": "Pa",
            "maximum_total_deformation": "m",
            "minimum_safety_factor": "1",
        },
    )


def _manifest() -> FEAProjectManifest:
    return FEAProjectManifest(
        id="pr09-test-v1",
        cad=_cad(),
        materials=(_material(),),
        load_cases=(_case(),),
        policy=FEAAcceptancePolicy(
            maximum_mesh_change_percent=5.0,
            maximum_force_balance_error_percent=1.0,
            metric_limits={"minimum_safety_factor": (1.5, None)},
        ),
    )


def _result(**changes) -> FEAResultCase:
    values = dict(
        case_id="steady_max_rpm",
        cad_sha256=SHA,
        material_ids=("PA_CF_COUPON_V1",),
        solver_name="ANSYS Mechanical",
        solver_version="2026 R1",
        converged=True,
        mesh_convergence_metric="maximum_von_mises_stress",
        mesh_levels=(
            FEAMeshLevel("coarse", 100_000, 2.0e8),
            FEAMeshLevel("medium", 200_000, 2.08e8),
            FEAMeshLevel("fine", 400_000, 2.10e8),
        ),
        force_balance_error_percent=0.2,
        metrics={
            "maximum_von_mises_stress": (2.10e8, "Pa"),
            "maximum_total_deformation": (0.0012, "m"),
            "minimum_safety_factor": (1.7, "1"),
        },
        warnings=(),
    )
    values.update(changes)
    return FEAResultCase(**values)


def test_complete_bundle_passes_software_acceptance() -> None:
    decision = assess_fea_result_bundle(_manifest(), (_result(),))
    assert decision.software_gate_passed
    assert not decision.physical_qualification
    assert decision.state == "software_pass_physical_evidence_pending"
    assert decision.cases[0].mesh_change_percent < 5.0


def test_hash_units_metrics_and_mesh_fail_closed() -> None:
    wrong_hash = assess_fea_result_bundle(
        _manifest(), (_result(cad_sha256="b" * 64),)
    )
    assert not wrong_hash.software_gate_passed
    assert "cad_sha256_mismatch" in wrong_hash.cases[0].failures

    wrong_units = assess_fea_result_bundle(
        _manifest(),
        (_result(metrics={"maximum_von_mises_stress": (210.0, "MPa")}),),
    )
    assert not wrong_units.software_gate_passed
    assert any("missing_metric" in item for item in wrong_units.cases[0].failures)

    short_mesh = assess_fea_result_bundle(
        _manifest(), (_result(mesh_levels=(FEAMeshLevel("fine", 1, 2.1e8),)),)
    )
    assert not short_mesh.software_gate_passed
    assert "mesh_levels_below_three" in short_mesh.cases[0].failures

    wrong_mesh_metric = assess_fea_result_bundle(
        _manifest(), (_result(mesh_convergence_metric="unrelated_metric"),)
    )
    assert "mesh_convergence_metric_not_declared" in (
        wrong_mesh_metric.cases[0].failures
    )


def test_missing_duplicate_or_unknown_cases_are_rejected() -> None:
    missing = assess_fea_result_bundle(_manifest(), ())
    assert not missing.software_gate_passed
    assert missing.missing_case_ids == ("steady_max_rpm",)

    with pytest.raises(ValueError, match="unique"):
        assess_fea_result_bundle(_manifest(), (_result(), _result()))

    with pytest.raises(ValueError, match="Unknown"):
        assess_fea_result_bundle(
            _manifest(), (_result(case_id="not_declared"),)
        )


def test_policy_limits_are_explicit_and_not_invented() -> None:
    with pytest.raises(ValueError, match="declared metric"):
        FEAProjectManifest(
            id="invalid-policy",
            cad=_cad(),
            materials=(_material(),),
            load_cases=(_case(),),
            policy=FEAAcceptancePolicy(
                metric_limits={"fatigue_life_cycles": (1_000_000.0, None)}
            ),
        )

    below_limit = assess_fea_result_bundle(
        _manifest(),
        (_result(metrics={
            "maximum_von_mises_stress": (2.10e8, "Pa"),
            "maximum_total_deformation": (0.0012, "m"),
            "minimum_safety_factor": (1.2, "1"),
        }),),
    )
    assert "metric_below_limit:minimum_safety_factor" in below_limit.cases[0].failures


def test_pa_cf_orthotropic_card_requires_directional_properties() -> None:
    with pytest.raises(ValueError, match="orthotropic"):
        FEAMaterialIdentity(
            id="PA_CF_INCOMPLETE",
            model="orthotropic",
            source="unknown",
            property_names=("density_kg_m3", "elastic_modulus_pa"),
            qualification="unverified",
        )
