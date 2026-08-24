import json
from pathlib import Path

import pytest

from pyfoldable.application.opening_sensitivity import (
    OpeningSensitivityError,
    load_opening_sensitivity,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "reports" / "pr06d_opening_sensitivity.json"


def test_opening_sensitivity_exposes_screening_rows_without_requalifying_them():
    snapshot = load_opening_sensitivity(REPO_ROOT)

    assert snapshot.qualification == "screening_only_until_pr06c_passes"
    assert snapshot.case_count == 250
    assert snapshot.condition_count == 50
    assert len(snapshot.rows) == 5
    assert snapshot.rows[0].angle_from_deployed_deg == 0.0
    assert snapshot.rows[0].static_thrust_ratio_median == 1.0
    assert snapshot.rows[-1].angle_from_deployed_deg == -60.0
    assert snapshot.rows[-1].static_thrust_ratio_median < 1.0
    assert len(snapshot.report_sha256) == 64


def test_opening_sensitivity_rejects_changed_qualification(tmp_path):
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    document["qualification"] = "qualified"
    changed = tmp_path / "opening.json"
    changed.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(OpeningSensitivityError, match="screening-only"):
        load_opening_sensitivity(REPO_ROOT, report_path=changed)


def test_opening_sensitivity_rejects_incomplete_case_matrix(tmp_path):
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    document["case_count"] -= 1
    changed = tmp_path / "opening.json"
    changed.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(OpeningSensitivityError, match="case matrix"):
        load_opening_sensitivity(REPO_ROOT, report_path=changed)
