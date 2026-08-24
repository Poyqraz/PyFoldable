import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER = PROJECT_ROOT / "examples" / "review_acar_2025_jointed_tip_evidence.py"
FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "literature"
    / "acar_2025_jointed_tip_bemt_v1.json"
)
REPORT = PROJECT_ROOT / "reports" / "pr06d_acar_2025_jointed_tip_review.json"


def _module():
    spec = importlib.util.spec_from_file_location("acar_2025_review", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load Acar 2025 review runner.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_acar_2025_table_is_audited_without_becoming_qualification():
    stored = json.loads(REPORT.read_text(encoding="utf-8"))
    actual = _module().build_report(FIXTURE)

    assert stored == actual
    assert stored["source"]["pdf_sha256"] == (
        "030d485df45a22a1c67c3e004597218a8a5d87163c135e92ec3d4327ec6ad134"
    )
    assert stored["evidence_class"] == "methodology_only_tip_jointed_system"
    assert not stored["physical_qualification"]
    assert stored["point_count"] == 31
    assert stored["speed_range_m_s"] == [0.0, 30.0]
    assert stored["table_audit"]["maximum_thrust_closure_error_n"] < 0.0011
    assert stored["table_audit"]["maximum_power_closure_error_w"] < 0.011
    assert stored["table_audit"]["maximum_reported_efficiency_formula_error"] < 0.02
    assert stored["table_audit"]["reported_efficiency_rejected_count"] > 0
    assert stored["mode_counts"]["tip"]["powered_drag"] > 0
    assert stored["mode_counts"]["tip"]["energy_extracting_drag"] > 0
    assert "main_thrust_narrative_conflicts_with_table" in stored[
        "internal_consistency_findings"
    ]
    assert "angular_speed_power_equation_has_extra_2pi" in stored[
        "internal_consistency_findings"
    ]
    assert "main_rotor_speed_not_reported" in stored["reproduction_blockers"]
    assert stored["gate_effect"] == {
        "pr06c_physical_gate_changed": False,
        "pr06d_physical_qualification_changed": False,
        "reason": "computational methodology with incomplete reproducibility inputs",
    }
