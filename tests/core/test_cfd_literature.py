import json
from pathlib import Path

import pytest

from pyfoldable.core import CFDReferenceError, load_cfd_reference_fixture


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "cfd_reference"
    / "apcsf_10x4.7_published_v1.json"
)


def test_published_cfd_fixture_is_exactly_scoped_and_fail_closed():
    reference = load_cfd_reference_fixture(FIXTURE)

    assert reference.id == "apcsf-10x4.7-published-cfd-v1"
    assert reference.target_geometry_id == "APC Slow Flyer 10x4.7"
    assert reference.independent_project_review is False
    assert reference.qualification == "model_form_context_only"
    assert len(reference.sources) == 5
    assert len(reference.points) == 9
    assert {point.source_id for point in reference.points} <= {
        source.id for source in reference.sources
    }
    assert all(not point.qualification_eligible for point in reference.points)

    icps = [
        point
        for point in reference.points
        if point.source_id == "wan-tsai-icas2020"
        and point.turbulence_model == "SST k-omega"
    ]
    assert [(point.rpm, point.value) for point in icps] == [
        (4319.0, 0.0480),
        (6528.0, 0.0528),
    ]


def test_cfd_fixture_rejects_unknown_source_and_review_promotion(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["points"][0]["source_id"] = "missing"
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CFDReferenceError, match="declared source"):
        load_cfd_reference_fixture(invalid)

    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["independent_project_review"] = True
    invalid.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CFDReferenceError, match="cannot satisfy"):
        load_cfd_reference_fixture(invalid)


def test_figure_only_sources_cannot_contain_digitized_numeric_points(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["points"].append(
        {
            "id": "forbidden-digitization",
            "source_id": "fevralskikh-flowvision-2024",
            "quantity": "thrust_n",
            "value": 1.0,
            "rpm": 5000,
            "evidence_form": "tabulated",
            "qualification_eligible": False,
        }
    )
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CFDReferenceError, match="figure-only"):
        load_cfd_reference_fixture(invalid)
