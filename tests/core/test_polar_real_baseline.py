"""Auditable regression checks for the promoted PR-05E real-solver baseline."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from pyfoldable.core import load_polar_golden_fixture


BASELINE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "polar_real_qualification"
    / "naca0012_re200k_real_v1"
)


def _document(relative: str) -> dict[str, object]:
    return json.loads((BASELINE / relative).read_text(encoding="utf-8"))


def _sha256(relative: str) -> str:
    return hashlib.sha256((BASELINE / relative).read_bytes()).hexdigest()


def test_promotion_record_preserves_verified_capture_provenance() -> None:
    promotion = _document("promotion.json")
    comparison = _document("comparison.json")
    manifest = _document("capture/manifest.json")

    assert promotion["schema_version"] == 1
    assert promotion["kind"] == "polar-real-backend-baseline-promotion"
    assert promotion["review_state"] == "approved"
    assert promotion["promotion_allowed"] is True
    assert manifest["review_state"] == "unreviewed"
    assert manifest["promotion_allowed"] is False

    captures = promotion["captures"]
    assert isinstance(captures, list)
    assert [capture["run_id"] for capture in captures] == [
        31942197266,
        31943335405,
    ]
    assert captures[0]["manifest_sha256"] == _sha256("capture/manifest.json")
    assert captures[1]["manifest_sha256"] == _sha256(
        "second_capture_manifest.json"
    )

    review = promotion["reproducibility_review"]
    assert review["run_id"] == 31945859274
    assert review["report_sha256"] == _sha256("comparison.json")
    assert comparison["reproducible"] is True
    assert comparison["differences"] == []
    assert comparison["first_bundle"]["semantic_sha256"] == review[
        "semantic_sha256"
    ]
    assert comparison["second_bundle"]["semantic_sha256"] == review[
        "semantic_sha256"
    ]

    fixture = promotion["promoted_fixture"]
    assert fixture["sha256"] == _sha256(fixture["path"])


def test_preserved_capture_manifest_covers_every_evidence_file() -> None:
    manifest = _document("capture/manifest.json")

    for entry in manifest["files"]:
        evidence = BASELINE / "capture" / entry["path"]
        payload = evidence.read_bytes()
        assert len(payload) == entry["size_bytes"]
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"]

    golden_document = _document("golden.json")
    raw_xfoil = _document("capture/results/00-xfoil-subprocess.json")
    fixture = load_polar_golden_fixture(BASELINE / "golden.json")
    assert golden_document["reference"]["provider"] == raw_xfoil["provider"]
    assert golden_document["reference"]["points"] == raw_xfoil["points"]
    assert fixture.reference.provider.name == "xfoil-subprocess"
    assert fixture.reference.request.airfoil.coordinates == tuple(
        tuple(point) for point in raw_xfoil["request"]["airfoil"]["coordinates"]
    )


def test_physical_review_metrics_are_recomputed_from_preserved_results() -> None:
    promotion = _document("promotion.json")
    physical = promotion["physical_review"]
    benchmark = _document("capture/benchmark.json")
    xfoil = _document("capture/results/00-xfoil-subprocess.json")
    neuralfoil = _document("capture/results/01-neuralfoil.json")

    assert benchmark["passed"] is True
    assert xfoil["complete"] is True
    assert neuralfoil["complete"] is True
    assert all(point["status"] == "converged" for point in xfoil["points"])
    assert all(point["status"] == "converged" for point in neuralfoil["points"])
    assert xfoil["warnings"] == []
    assert neuralfoil["warnings"] == []
    assert xfoil["metadata"]["returncode"] == physical["xfoil_returncode"] == 0
    assert xfoil["metadata"]["stderr_tail"] == physical["xfoil_nonfatal_stderr"]

    confidences = [point["confidence"] for point in neuralfoil["points"]]
    assert min(confidences) == pytest.approx(
        physical["neuralfoil_minimum_confidence"]
    )
    assert min(confidences) >= physical["neuralfoil_confidence_threshold"]

    neural_metrics = {
        metric["coefficient"]: metric["max_absolute_error"]
        for metric in benchmark["entries"][1]["acceptance"]["metrics"]
    }
    assert neural_metrics == physical["neuralfoil_max_absolute_error"]
    assert benchmark["entries"][1]["acceptance"]["coverage"] == physical["coverage"]

    points = {
        round(math.degrees(point["alpha_rad"])): point for point in xfoil["points"]
    }
    paired_angles = (2, 4, 6)
    residuals = {
        "cl_odd": max(
            abs(points[angle]["cl"] + points[-angle]["cl"])
            for angle in paired_angles
        ),
        "cd_even": max(
            abs(points[angle]["cd"] - points[-angle]["cd"])
            for angle in paired_angles
        ),
        "cm_odd": max(
            abs(points[angle]["cm"] + points[-angle]["cm"])
            for angle in paired_angles
        ),
    }
    assert residuals == pytest.approx(physical["xfoil_symmetry_max_residual"])
    assert {
        coefficient: points[0][coefficient] for coefficient in ("cl", "cd", "cm")
    } == physical["zero_alpha"]
    assert physical["all_points_converged"] is True
    assert physical["decision"] == "accepted"
