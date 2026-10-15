"""Partial-fold screening keeps the archived stow collision and parent identity."""

from __future__ import annotations

import hashlib
import json
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = runpy.run_path(str(ROOT / "examples" / "prepare_intermediate_fold_screening.py"))
build_intermediate_fold_study = _SCRIPT["build_intermediate_fold_study"]
render_intermediate_fold_report = _SCRIPT["render_intermediate_fold_report"]
ARCHIVED = ROOT / "reports" / "hinge_location_geometry_screening" / "study.json"
STUDY = ROOT / "reports" / "intermediate_fold_50mm_screening" / "study.json"
REPORT = ROOT / "reports" / "intermediate_fold_50mm_screening" / "report.md"
FIGURE = ROOT / "reports" / "intermediate_fold_50mm_screening" / "plan_view.png"
ARCHIVED_SHA256 = "f3c3e927c0ede938e5e770cce2eab405ca8413cec997eb17ab620b5fe22a7124"
PARENT_SHA256 = "1a149afec4cb192703a597e86717e5040d15e3c7fcb1697b4898ea3d26b6eada"


def _without_runtime(study: dict) -> dict:
    copy = json.loads(json.dumps(study))
    copy.pop("runtime", None)
    return copy


def test_partial_fold_interval_does_not_clear_the_canonical_stow() -> None:
    archived_bytes = ARCHIVED.read_bytes()
    recorded = json.loads(STUDY.read_text(encoding="utf-8"))
    rebuilt = build_intermediate_fold_study(ROOT)

    assert hashlib.sha256(archived_bytes).hexdigest() == ARCHIVED_SHA256
    assert _without_runtime(recorded) == _without_runtime(rebuilt)
    assert recorded["parent"]["canonical_sha256"] == PARENT_SHA256
    assert recorded["physical_qualification"] is False
    assert recorded["qualified_winner"] is None
    assert recorded["derived"]["envelope_deg_rounded"] == "-115.47"
    assert recorded["derived"]["contact_deg_rounded"] == "-158.90"
    assert recorded["derived"]["envelope_endpoint"] == "included"
    assert recorded["derived"]["contact_endpoint"] == "excluded"
    envelope = recorded["boundary_audits"]["envelope_entry"]
    contact = recorded["boundary_audits"]["first_contact"]
    assert envelope["inside_partial_fold_interval"] is True
    assert envelope["tolerance_based_envelope_diagnostic"] is True
    assert contact["inside_partial_fold_interval"] is False
    assert contact["instant_hub_clearance_strictly_positive"] is False
    witness = recorded["inert_tolerance_witness"]
    assert witness["role"] == "inert_regression_not_a_proposed_stop"
    assert witness["fold_angle_deg"] == -115.46756004247239
    assert witness["tolerance_based_envelope_diagnostic"] is True
    assert witness["inside_partial_fold_interval"] is False
    assert witness["audit"]["tolerance_based_envelope_diagnostic"] is True
    assert witness["audit"]["inside_partial_fold_interval"] is False
    assert [pose["fold_angle_deg"] for pose in recorded["reported_poses"]] == [-120.0, -135.0, -150.0]
    assert witness["fold_angle_deg"] not in [pose["fold_angle_deg"] for pose in recorded["reported_poses"]]
    proof = recorded["deployment_to_stop_minimum"]["proof"]
    assert recorded["deployment_to_stop_minimum"]["established_by"] == "closed_form_monotonicity"
    assert recorded["deployment_to_stop_minimum"]["sampled_poses_are_proof"] is False
    assert "derivative" in proof
    for pose in recorded["reported_poses"]:
        assert pose["inside_partial_fold_interval"] is True
        assert pose["deployment_to_stop_minimum_hub_clearance_m"] == pose["analytic_hub_clearance_m"]
        assert pose["deployment_to_stop_minimum_hub_clearance_m"] == pose["hub_centerline_clearance_m"]
        assert pose["deployment_to_stop_minimum_hub_clearance_m"] > 0.0
        assert pose["full_stow_path_hub_clearance_m"] < 0.0
        assert pose["deployment_to_stop_minimum_hub_clearance_m"] != pose["full_stow_path_hub_clearance_m"]
        assert "full_stow_path_intersects_hub" in pose["compatibility_reasons"]
        assert "surface_stations_do_not_cover_hub_to_tip" in pose["compatibility_reasons"]
    stow = recorded["canonical_full_stow"]
    assert stow["fold_angle_deg"] == -180.0
    assert stow["inside_partial_fold_interval"] is False
    assert stow["deployment_to_stop_minimum_hub_clearance_m"] == stow["analytic_hub_clearance_m"]
    assert "tip_centerline_intersects_hub" in stow["compatibility_reasons"]
    assert "full_stow_path_intersects_hub" in stow["compatibility_reasons"]
    report = REPORT.read_text(encoding="utf-8")
    assert render_intermediate_fold_report(recorded) == report
    assert "Qualified winner: none" in report
    assert "-115.46756004247239" in report
    assert "Analytic interval membership: false" in report
    assert "Tolerance-based envelope diagnostic: true" in report
    assert "Sampled poses are not the proof." in report
    assert FIGURE.read_bytes().startswith(b"\x89PNG")
