"""Chord-surface screening keeps the parent pin and does not promote clearance."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

from pyfoldable.application.surface_clearance import SurfaceClearanceInputs


ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = runpy.run_path(str(ROOT / "examples" / "prepare_chord_surface_50mm_screening.py"))
build_chord_surface_study = _SCRIPT["build_chord_surface_study"]
render_chord_surface_report = _SCRIPT["render_chord_surface_report"]
STUDY = ROOT / "reports" / "chord_surface_50mm_screening" / "study.json"
REPORT = ROOT / "reports" / "chord_surface_50mm_screening" / "report.md"
PLAN = ROOT / "reports" / "chord_surface_50mm_screening" / "plan_view.png"
SURFACE = ROOT / "reports" / "chord_surface_50mm_screening" / "surface_view.png"
PARENT_SHA256 = "1a149afec4cb192703a597e86717e5040d15e3c7fcb1697b4898ea3d26b6eada"
HINGE_STUDY_SHA256 = "f3c3e927c0ede938e5e770cce2eab405ca8413cec997eb17ab620b5fe22a7124"
FOLD_HEAD = "3ed68e9b8a2f1c9424204f1fb39404e000f539cf"


def _without_interpreter(study: dict) -> dict:
    copy = json.loads(json.dumps(study))
    copy.pop("runtime", None)
    for stop in copy["stops"]:
        report = stop["geom_report"]
        report.pop("request_sha256", None)
        report["request"].pop("python", None)
    return copy


def test_three_default_budget_reports_stay_blocked() -> None:
    recorded = json.loads(STUDY.read_text(encoding="utf-8"))
    rebuilt = build_chord_surface_study(ROOT)
    assert _without_interpreter(recorded) == _without_interpreter(rebuilt)
    assert recorded["parent_identity"]["canonical_sha256"] == PARENT_SHA256
    assert recorded["pins"]["hinge_location_study"]["sha256"] == HINGE_STUDY_SHA256
    assert recorded["pins"]["intermediate_fold_study"]["head"] == FOLD_HEAD
    assert recorded["physical_qualification"] is False
    assert recorded["qualified_winner"] is None
    assert recorded["full_propeller_clearance"] is None
    assert recorded["study_draft"]["distinct_from_parent"] is True
    assert recorded["study_draft"]["sha256"] != PARENT_SHA256
    assert recorded["deployment_preview"]["geom_report"] is None
    assert [stop["end_angle_deg"] for stop in recorded["stops"]] == [-120.0, -135.0, -150.0]
    defaults = SurfaceClearanceInputs()
    deployment_mesh = recorded["deployment_preview"]["preview_mesh"]
    assert deployment_mesh["mesh_envelope_radius_m"] < deployment_mesh["centerline_envelope_radius_m"]
    axial = (deployment_mesh["axial_min_m"], deployment_mesh["axial_max_m"])
    for stop in recorded["stops"]:
        report = stop["geom_report"]
        assert report["modeled_surface_status"] == "unknown"
        assert report["classification"] == "blocked"
        assert report["full_propeller_clearance"] is None
        assert report["physical_qualification"] is False
        assert report["station_span_complete"] is False
        assert report["request"]["inputs"]["required_clearance_m"] == 0.0
        assert report["request"]["inputs"]["root_attachment_m"] == 0.0
        assert report["request"]["inputs"]["hinge_attachment_m"] == 0.0
        assert report["request"]["inputs"]["max_node_comparisons"] == defaults.max_node_comparisons
        assert report["request"]["inputs"]["max_feature_tests"] == defaults.max_feature_tests
        assert report["request"]["hub_obstacle"] == "infinite_cylinder_conservative_envelope"
        assert report["hardware_status"] is None
        assert report["node_comparisons"] == defaults.max_node_comparisons
        assert report["feature_tests"] == defaults.max_feature_tests
        kinds = {row["kind"] for row in report["queries"]}
        assert kinds == {"hub", "own_root_tip", "interblade"}
        assert any(row["result"]["reason"] == "global_budget_exhausted" for row in report["queries"])
        own = [row for row in report["queries"] if row["kind"] == "own_root_tip"]
        assert len(own) == 2
        assert any(row["result"]["status"] == "unknown" for row in own)
        mesh = stop["preview_mesh"]
        assert mesh["mesh_envelope_radius_m"] != mesh["centerline_envelope_radius_m"]
        assert mesh["mesh_envelope_radius_m"] > mesh["centerline_envelope_radius_m"]
        assert (mesh["axial_min_m"], mesh["axial_max_m"]) == axial
        assert abs(mesh["centerline_envelope_radius_m"] - mesh["pinned_centerline_diameter_m"] / 2.0) <= 1.0e-12
    report_text = REPORT.read_text(encoding="utf-8")
    assert render_chord_surface_report(recorded) == report_text
    assert "Qualified winner: none" in report_text
    assert "manufacturing acceptance margin" in report_text
    assert PLAN.read_bytes().startswith(b"\x89PNG")
    assert SURFACE.read_bytes().startswith(b"\x89PNG")


def test_surface_screening_makes_three_clearance_calls(monkeypatch) -> None:
    calls = []
    module_globals = build_chord_surface_study.__globals__
    real = module_globals["run_surface_clearance"]

    def _wrapped(request):
        calls.append(request)
        return real(request)

    monkeypatch.setitem(module_globals, "run_surface_clearance", _wrapped)
    study = build_chord_surface_study(ROOT)
    assert [request.inputs.end_angle_deg for request in calls] == [-120.0, -135.0, -150.0]
    assert [stop["end_angle_deg"] for stop in study["stops"]] == [-120.0, -135.0, -150.0]
    defaults = SurfaceClearanceInputs()
    for request in calls:
        assert request.hardware_json is None
        assert request.inputs.required_clearance_m == 0.0
        assert request.inputs.root_attachment_m == defaults.root_attachment_m
        assert request.inputs.hinge_attachment_m == defaults.hinge_attachment_m
        assert request.inputs.max_node_comparisons == defaults.max_node_comparisons
        assert request.inputs.max_intervals == defaults.max_intervals
        assert request.inputs.max_depth == defaults.max_depth
        assert request.inputs.max_feature_tests == defaults.max_feature_tests
        assert request.inputs.max_hardware_queries == defaults.max_hardware_queries
