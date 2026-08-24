import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER = PROJECT_ROOT / "examples" / "run_pr09_fea_contract_evidence.py"
REPORT = PROJECT_ROOT / "reports" / "pr09_fea_contract_evidence.json"


def _module():
    spec = importlib.util.spec_from_file_location("pr09_evidence", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load PR-09 evidence runner.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pr09_report_is_reproducible_and_never_promotes_fixture_physics():
    stored = json.loads(REPORT.read_text(encoding="utf-8"))
    actual = _module().build_report()
    assert stored == actual
    assert stored["software_fixture_decision"]["software_gate_passed"]
    assert not stored["software_fixture_decision"]["physical_qualification"]
    assert len(stored["manifest"]["load_cases"]) == 5
    assert stored["project_readiness"]["state"] == (
        "blocked_waiting_for_real_structural_inputs"
    )
    assert not stored["project_readiness"]["physical_qualification"]
    assert stored["decision"] == (
        "pr09_software_contract_complete_physical_evidence_pending"
    )
