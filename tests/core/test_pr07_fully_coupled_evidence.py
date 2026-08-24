import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER = PROJECT_ROOT / "examples" / "run_pr07_fully_coupled_evidence.py"
REPORT = PROJECT_ROOT / "reports" / "pr07_fully_coupled_evidence.json"


def _module():
    spec = importlib.util.spec_from_file_location("pr07_evidence", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load PR-07 evidence runner.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pr07_report_is_complete_reproducible_and_fail_closed():
    stored = json.loads(REPORT.read_text(encoding="utf-8"))
    actual = _module().build_report()

    assert stored == actual
    assert stored["numerical_gate"] == "passed"
    assert stored["physical_gate"] == "pending_measured_correlation"
    assert stored["case_count"] == 5
    assert stored["maximum_multistart_spread_rpm"] <= 1.0e-6
    assert stored["maximum_absolute_torque_residual_nm"] <= 1.0e-8
    assert stored["decision"] == (
        "pr07_numerical_gate_passed_physical_correlation_pending"
    )
    assert all(case["aero"]["qualification"].startswith("software_fixture") for case in stored["cases"])
