"""The hinge-location report preserves the accepted parent and names no winner."""

from __future__ import annotations

import json
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = runpy.run_path(
    str(ROOT / "examples" / "prepare_hinge_location_geometry_screening.py")
)
build_hinge_location_study = _SCRIPT["build_hinge_location_study"]
render_hinge_location_report = _SCRIPT["render_hinge_location_report"]
ACCEPTED_PARENT_SHA256 = _SCRIPT["ACCEPTED_PARENT_SHA256"]
STUDY_PATH = ROOT / "reports" / "hinge_location_geometry_screening" / "study.json"
REPORT_PATH = ROOT / "reports" / "hinge_location_geometry_screening" / "comparison.md"
FIGURE_PATH = ROOT / "reports" / "hinge_location_geometry_screening" / "plan_view.png"


def _without_runtime(study: dict) -> dict:
    copy = json.loads(json.dumps(study))
    copy.pop("runtime", None)
    return copy


def test_screening_keeps_the_accepted_parent_and_publishes_no_winner() -> None:
    recorded = json.loads(STUDY_PATH.read_text(encoding="utf-8"))
    rebuilt = build_hinge_location_study(ROOT)

    assert _without_runtime(recorded) == _without_runtime(rebuilt)
    assert recorded["parent"]["canonical_sha256"] == ACCEPTED_PARENT_SHA256
    assert recorded["accepted_parent"]["packet_modified"] is False
    assert recorded["physical_qualification"] is False
    assert recorded["qualified_winner"] is None
    assert [item["declaration"] for item in recorded["hinges"]] == ["100 mm", "50 mm"]
    assert recorded["not_executed"] == [
        "polar provider",
        "BEM",
        "CFD",
        "FEA",
        "transient",
        "qualification",
    ]
    for hinge in recorded["hinges"]:
        assert [pose["fold_angle_deg"] for pose in hinge["poses"]] == [0.0, -90.0, -180.0]
        assert hinge["hinge_station_present"] is True
        assert hinge["necessary_fixed_section_bound_diameter_m"] == 2.0 * hinge["radius_m"]
        for row in hinge["comparison_rows"]:
            assert row["differences"]["radius_m"] == 0.0
            assert row["differences"]["chord_m"] == 0.0
            assert row["differences"]["twist_rad"] == 0.0
        for pose in hinge["poses"]:
            assert pose["physical_qualification"] is False
            assert pose["centerline_envelope_diameter_m"] >= hinge[
                "necessary_fixed_section_bound_diameter_m"
            ]
    report = REPORT_PATH.read_text(encoding="utf-8")
    assert render_hinge_location_report(recorded) == report
    assert "Qualified winner: none" in report
    assert "not clearance" in report.casefold()
    assert FIGURE_PATH.read_bytes().startswith(b"\x89PNG")
