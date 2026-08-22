import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER = PROJECT_ROOT / "examples" / "run_pr06d_opening_sensitivity.py"
REPORT = PROJECT_ROOT / "reports" / "pr06d_opening_sensitivity.json"


def _module():
    spec = importlib.util.spec_from_file_location("pr06d_opening", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load PR-06D opening runner.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pr06d_opening_report_is_complete_reproducible_and_screening_only():
    stored = json.loads(REPORT.read_text(encoding="utf-8"))
    actual = _module().build_report()

    assert stored == actual
    assert stored["deployed_endpoint_exact"]
    assert stored["state_count"] == 5
    assert stored["condition_count"] == 50
    assert stored["case_count"] == 250
    assert stored["physical_qualification"] is False
    assert stored["qualification"] == "screening_only_until_pr06c_passes"
    assert stored["decision"] == (
        "pr06d_opening_sensitivity_software_complete_screening_only"
    )
    assert stored["angle_summaries"][0]["regimes"]["static"][
        "thrust_ratio_median"
    ] == 1.0
