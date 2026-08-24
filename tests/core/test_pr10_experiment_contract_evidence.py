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
