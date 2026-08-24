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


def test_opening_sensitivity_rejects_physical_qualification_promotion(tmp_path):
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    document["physical_qualification"] = True
    changed = tmp_path / "opening.json"
    changed.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(OpeningSensitivityError, match="physical qualification"):
        load_opening_sensitivity(REPO_ROOT, report_path=changed)


def test_opening_sensitivity_rejects_representative_proxy_claim(tmp_path):
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    document["polar_evidence"]["representative"] = True
    changed = tmp_path / "opening.json"
    changed.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(OpeningSensitivityError, match="non-representative analytic proxy"):
        load_opening_sensitivity(REPO_ROOT, report_path=changed)


def test_opening_sensitivity_rejects_non_finite_summary_values(tmp_path):
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    document["angle_summaries"][0]["effective_diameter_m"] = float("nan")
    changed = tmp_path / "opening.json"
    changed.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(OpeningSensitivityError, match="non-finite JSON constant"):
        load_opening_sensitivity(REPO_ROOT, report_path=changed)


def test_opening_sensitivity_rejects_duplicate_or_unordered_states(tmp_path):
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    document["angle_summaries"][1]["state_id"] = document["angle_summaries"][0][
        "state_id"
    ]
    changed = tmp_path / "opening.json"
    changed.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(OpeningSensitivityError, match="unique and ordered"):
        load_opening_sensitivity(REPO_ROOT, report_path=changed)


def test_opening_sensitivity_rejects_missing_case_rows(tmp_path):
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    document["cases"].pop()
    changed = tmp_path / "opening.json"
    changed.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(OpeningSensitivityError, match="case matrix"):
        load_opening_sensitivity(REPO_ROOT, report_path=changed)


def test_opening_sensitivity_rejects_non_string_state_identity(tmp_path):
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    document["angle_summaries"][0]["state_id"] = 7
    changed = tmp_path / "opening.json"
    changed.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(OpeningSensitivityError, match="Invalid angle summary"):
        load_opening_sensitivity(REPO_ROOT, report_path=changed)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("angle_from_deployed_deg", -14.0),
        ("effective_diameter_m", 999.0),
        ("projection_factor", 0.123),
    ],
)
def test_opening_sensitivity_rejects_summary_geometry_drift(
    tmp_path,
    field,
    value,
):
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    document["angle_summaries"][1][field] = value
    changed = tmp_path / "opening.json"
    changed.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(OpeningSensitivityError, match="summar"):
        load_opening_sensitivity(REPO_ROOT, report_path=changed)


def test_opening_sensitivity_rejects_summary_range_drift(tmp_path):
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    document["angle_summaries"][1]["regimes"]["static"][
        "thrust_ratio_minimum"
    ] = -999.0
    changed = tmp_path / "opening.json"
    changed.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(OpeningSensitivityError, match="case matrix"):
        load_opening_sensitivity(REPO_ROOT, report_path=changed)


def test_opening_sensitivity_rejects_deployed_mapping_promotion(tmp_path):
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    document["cases"][0]["fixed_mapping_equal"] = False
    changed = tmp_path / "opening.json"
    changed.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(OpeningSensitivityError, match="Invalid case"):
        load_opening_sensitivity(REPO_ROOT, report_path=changed)
