import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER = PROJECT_ROOT / "examples" / "run_pr10_experiment_contract_evidence.py"
REPORT = PROJECT_ROOT / "reports" / "pr10_experiment_contract_evidence.json"


def _module():
    spec = importlib.util.spec_from_file_location("pr10_evidence", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load PR-10 evidence runner.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pr10_report_is_reproducible_and_fixture_never_becomes_physics():
    stored = json.loads(REPORT.read_text(encoding="utf-8"))
    actual = _module().build_report()
    assert stored == actual
    fixture = stored["software_fixture_decision"]
    assert fixture["software_gate_passed"]
    assert not fixture["physical_qualification"]
    assert len(fixture["runs"]) == 2
    assert {summary["role"] for summary in fixture["summaries"]} == {
        "fixed_reference", "foldable"
    }
    assert stored["project_readiness"]["state"] == (
        "blocked_waiting_for_calibrated_raw_measurements"
    )
    assert stored["decision"] == (
        "pr10_software_contract_complete_physical_measurements_pending"
    )

    baseline = stored["public_baseline_context"]
    assert baseline["evidence_class"] == "published_external_baseline"
    assert baseline["qualification_scope"] == "model_validation_context_only"
    assert not baseline["physical_qualification"]
    assert baseline["target_geometry"] == "APC Slow Flyer 10x4.7"
    assert baseline["point_count"] == 60
    assert baseline["eligible_point_count"] == 50
    assert baseline["regime_counts"] == {"static": 16, "forward": 44}
    assert baseline["quantities"] == ["CT", "CP", "J", "rpm"]
    assert len(baseline["fixture_sha256"]) == 64
    assert baseline["source_access_policy"] == (
        "url_and_digest_only_no_raw_redistribution"
    )
    assert baseline["published_campaign_uncertainty_percent"]["thrust"] == 0.504
    assert baseline["published_campaign_uncertainty_percent"]["scope"] == (
        "campaign-level apparatus estimate, not per-point error bars"
    )
    assert all(
        source["id"] and source["kind"] and source["url"] and source["citation"]
        for source in baseline["sources"]
    )
    assert "no_raw_sensor_stream" in baseline["limitations"]
    assert "no_calibration_certificates" in baseline["limitations"]
    assert "foldable_prototype_raw_repeated_measurements" in stored[
        "project_readiness"
    ]["missing_inputs"]
    foundation = {item["id"]: item for item in stored["measurement_method_foundation"]}
    independent = foundation["morgado-pascoa-2015-apc-10x4.7sf"]
    assert independent["evidence_class"] == (
        "independent_same_prop_dynamic_reference"
    )
    assert independent["extracted_precedent"]["samples_per_point"] == 400
    assert independent["extracted_precedent"]["window_seconds"] == 50
    assert foundation["astm-e74-e2428-static-boundary"]["limitation"] == (
        "static calibration does not establish dynamic adequacy"
    )
    assert foundation["propdbtools"]["qualification_scope"] == (
        "uiuc_format_ingestion_only"
    )
