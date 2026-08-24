"""Generate PR-09 software-contract evidence and real-project readiness state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from pyfoldable.core import (
    CADRevisionIdentity,
    FEAAcceptancePolicy,
    FEALoadCase,
    FEAMaterialIdentity,
    FEAMeshLevel,
    FEAProjectManifest,
    FEAResultCase,
    assess_fea_result_bundle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = PROJECT_ROOT / "reports" / "pr09_fea_contract_evidence.json"
DEFAULT_MARKDOWN = PROJECT_ROOT / "reports" / "pr09_fea_contract_evidence.md"
FIXTURE_SHA = "a" * 64


def _load_cases() -> tuple[FEALoadCase, ...]:
    return (
        FEALoadCase("steady_max_rpm", "static_structural", "declared_load_envelope", {
            "maximum_von_mises_stress": "Pa", "maximum_total_deformation": "m",
            "minimum_safety_factor": "1",
        }),
        FEALoadCase("opening_stop_peak", "transient_structural_contact", "declared_opening_transient", {
            "maximum_contact_pressure": "Pa", "hinge_pin_shear_stress": "Pa",
            "minimum_safety_factor": "1",
        }),
        FEALoadCase("imbalance_max_rpm", "static_structural", "declared_imbalance_envelope", {
            "maximum_von_mises_stress": "Pa", "maximum_total_deformation": "m",
            "bearing_reaction_force": "N",
        }),
        FEALoadCase("modal_operating_margin", "modal", "declared_speed_envelope", {
            "first_natural_frequency": "Hz", "minimum_frequency_separation_percent": "%",
        }),
        FEALoadCase("fatigue_duty_cycle", "fatigue", "declared_duty_cycle", {
            "fatigue_life": "cycle", "fatigue_damage": "1",
        }),
    )


def _manifest() -> FEAProjectManifest:
    material = FEAMaterialIdentity(
        id="SYNTHETIC_ORTHOTROPIC_FIXTURE",
        model="orthotropic",
        source="first_party_software_fixture",
        property_names=(
            "density_kg_m3", "elastic_modulus_x_pa", "elastic_modulus_y_pa",
            "elastic_modulus_z_pa", "poisson_xy", "shear_modulus_xy_pa",
            "allowable_x_pa", "allowable_y_pa",
        ),
        qualification="software_fixture_not_material_evidence",
    )
    return FEAProjectManifest(
        id="pr09-fea-contract-software-fixture-v1",
        cad=CADRevisionIdentity(
            "TIP_HINGED_250_SYNTHETIC", "fixture-a", "synthetic.step",
            "STEP AP242", FIXTURE_SHA, "m", "shaft_z_right_handed",
        ),
        materials=(material,),
        load_cases=_load_cases(),
        policy=FEAAcceptancePolicy(
            maximum_mesh_change_percent=5.0,
            maximum_force_balance_error_percent=1.0,
            metric_limits={
                "minimum_safety_factor": (1.5, None),
                "minimum_frequency_separation_percent": (15.0, None),
                "fatigue_life": (1_000_000.0, None),
                "fatigue_damage": (None, 1.0),
            },
        ),
    )


def _result(case: FEALoadCase, metrics: Mapping[str, tuple[float, str]]) -> FEAResultCase:
    primary = float(next(iter(metrics.values()))[0])
    return FEAResultCase(
        case_id=case.id,
        cad_sha256=FIXTURE_SHA,
        material_ids=("SYNTHETIC_ORTHOTROPIC_FIXTURE",),
        solver_name="synthetic-fea-contract-runner",
        solver_version="1",
        converged=True,
        mesh_convergence_metric=next(iter(metrics)),
        mesh_levels=(
            FEAMeshLevel("coarse", 100_000, primary * 0.94),
            FEAMeshLevel("medium", 200_000, primary * 0.98),
            FEAMeshLevel("fine", 400_000, primary),
        ),
        force_balance_error_percent=0.2,
        metrics=metrics,
    )


def build_report() -> Mapping[str, Any]:
    manifest = _manifest()
    metrics = {
        "steady_max_rpm": {
            "maximum_von_mises_stress": (2.0e8, "Pa"),
            "maximum_total_deformation": (0.001, "m"),
            "minimum_safety_factor": (1.7, "1"),
        },
        "opening_stop_peak": {
            "maximum_contact_pressure": (1.5e8, "Pa"),
            "hinge_pin_shear_stress": (1.1e8, "Pa"),
            "minimum_safety_factor": (1.6, "1"),
        },
        "imbalance_max_rpm": {
            "maximum_von_mises_stress": (1.8e8, "Pa"),
            "maximum_total_deformation": (0.0011, "m"),
            "bearing_reaction_force": (75.0, "N"),
        },
        "modal_operating_margin": {
            "first_natural_frequency": (420.0, "Hz"),
            "minimum_frequency_separation_percent": (20.0, "%"),
        },
        "fatigue_duty_cycle": {
            "fatigue_life": (1_500_000.0, "cycle"),
            "fatigue_damage": (0.6, "1"),
        },
    }
    results = tuple(
        _result(case, metrics[case.id]) for case in manifest.load_cases
    )
    decision = assess_fea_result_bundle(manifest, results)
    return {
        "manifest": dict(manifest.as_mapping()),
        "software_fixture_decision": dict(decision.as_mapping()),
        "project_readiness": {
            "state": "blocked_waiting_for_real_structural_inputs",
            "missing_inputs": [
                "revision_controlled_solidworks_or_step_file_and_sha256",
                "pa_cf_directional_coupon_material_card",
                "pin_lock_stop_material_cards",
                "approved_structural_acceptance_limits",
                "declared_max_rpm_opening_stop_imbalance_and_duty_cycle_loads",
                "ansys_mechanical_result_bundle",
            ],
            "physical_qualification": False,
        },
        "decision": "pr09_software_contract_complete_physical_evidence_pending",
        "scope": (
            "All numerical values in this report are first-party software fixtures. "
            "They must not be used as structural design predictions or limits."
        ),
    }


def _markdown(report: Mapping[str, Any]) -> str:
    fixture = report["software_fixture_decision"]
    lines = [
        "# PR-09 structural/FEA contract evidence", "",
        f"- Software fixture gate: **{fixture['state']}**",
        "- Physical qualification: **pending**",
        f"- Required cases: {len(report['manifest']['load_cases'])}",
        "- Real-project readiness: **blocked_waiting_for_real_structural_inputs**",
        "", "## Missing real inputs", "",
    ]
    lines.extend(
        f"- `{item}`" for item in report["project_readiness"]["missing_inputs"]
    )
    lines.extend(("", str(report["scope"]), ""))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = build_report()
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.markdown.write_text(_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
