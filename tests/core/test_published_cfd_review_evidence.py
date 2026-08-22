import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER = PROJECT_ROOT / "examples" / "review_published_cfd_evidence.py"
REPORT = PROJECT_ROOT / "reports" / "pr06c_published_cfd_review.json"


def _module():
    spec = importlib.util.spec_from_file_location("published_cfd_review", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load published CFD review runner.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_published_cfd_review_is_reproducible_and_does_not_pass_gate():
    stored = json.loads(REPORT.read_text(encoding="utf-8"))
    actual = _module().build_report()

    assert stored == actual
    assert stored["decision"] == "literature_context_integrated_pr06c_still_blocked"
    assert stored["source_count"] == 5
    assert stored["numeric_point_count"] == 9
    assert len(stored["static_cp_comparisons"]) == 6
    assert stored["independent_project_review"] is False
    assert stored["gate_effect"]["pr06c_physical_gate_changed"] is False
    assert stored["gate_effect"]["independent_review_gate_passed"] is False
    assert set(stored["inputs"]) == {"cfd_fixture", "uiuc_fixture", "bem_report"}
    assert all(
        len(item["sha256"]) == 64 for item in stored["inputs"].values()
    )
    assert stored["strongest_static_cp_result"][
        "maximum_absolute_recomputed_error_percent"
    ] < 1.3
