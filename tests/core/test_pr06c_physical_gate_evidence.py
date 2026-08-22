import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER = PROJECT_ROOT / "examples" / "run_pr06c_physical_gate.py"
REPORT = PROJECT_ROOT / "reports" / "pr06c_physical_gate.json"


def _build_report():
    spec = importlib.util.spec_from_file_location("run_pr06c_physical_gate", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the PR-06C gate runner.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_report()


def test_pr06c_physical_gate_report_is_reproducible_and_fail_closed():
    stored = json.loads(REPORT.read_text(encoding="utf-8"))
    actual = _build_report()

    assert stored == actual
    assert not stored["passed"]
    assert stored["decision"] == "pr06c_blocked"
    assert stored["gates"]["fixture_identity"]
    assert stored["gates"]["frozen_policy"]
    assert not stored["gates"]["benchmark_accuracy"]
    assert not stored["gates"]["representative_polar_evidence"]
    assert not stored["gates"]["independent_model_form_review"]
    assert stored["evidence_inventory"]["apc12_coordinate_identity"]["status"] == "required_not_captured"
    screen = stored["reviewed_manufacturer_geometry_screen"]
    assert screen["point_count"] == 50
    assert screen["solution_coverage"] == 1.0
    assert screen["overall"]["ct_wmape"] > 0.15
    assert screen["forward"]["ct_wmape"] > 0.15
    assert screen["forward"]["cp_wmape"] > 0.20
