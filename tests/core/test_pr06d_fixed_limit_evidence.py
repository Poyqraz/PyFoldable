import importlib.util
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER = PROJECT_ROOT / "examples" / "run_pr06d_fixed_limit_equivalence.py"
FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "rotor_benchmark"
    / "uiuc_apcsf_10x4.7_v1.json"
)
REPORT = PROJECT_ROOT / "reports" / "pr06d_fixed_limit_equivalence.json"


def _build_report():
    spec = importlib.util.spec_from_file_location(
        "run_pr06d_fixed_limit_equivalence", RUNNER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the PR-06D evidence runner.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_report(FIXTURE)


def test_pr06d_fixed_limit_report_is_reproducible_and_exact():
    stored = json.loads(REPORT.read_text(encoding="utf-8"))
    actual = _build_report()

    assert stored == actual
    assert stored["passed"]
    assert stored["decision"] == "pr06d_software_fixed_limit_passed"
    assert stored["point_count"] == 50
    assert stored["fixture"]["qualification_point_count"] == 50
    assert stored["qualification"] == "software_equivalence_not_physical_accuracy"
    assert not stored["polar_evidence"]["representative"]
    assert stored["maximum_absolute_thrust_delta_n"] == 0.0
    assert stored["maximum_absolute_torque_delta_nm"] == 0.0
    assert all(case["passed"] for case in stored["cases"])
    assert all(case["rotor_mapping_equal"] for case in stored["cases"])
