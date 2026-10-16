"""Offline polar-query map. Inert traces are synthetic and publish no totals."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from pyfoldable.application.polar_query_feasibility import (
    MATCHED_PAIR,
    PIN_SHA256,
    build_polar_query_feasibility,
    render_polar_query_feasibility,
)
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS


ROOT = Path(__file__).resolve().parents[2]


def _report():
    return build_polar_query_feasibility(ROOT)


def test_query_map_separates_first_query_potential_domain_and_rectangle() -> None:
    report = _report()
    rows = report["query_map"]["rows"]
    assert len(rows) == 40
    assert report["genuine_query_coverage"] == "unavailable"
    assert report["historical_inputs"]["bem_calls"] == 0
    assert report["physical_qualification"] is False
    assert report["performance_totals_published"] is False
    first = rows[0]["first_no_induction_query"]
    assert first["observed_solver_query"] is False
    assert first["status"] == "conditional_on_reaching_this_annulus"
    assert first["alpha_rad"] == rows[0]["twist_rad"]
    assert math.isclose(first["alpha_rad"], math.radians(30.65875), rel_tol=0.0, abs_tol=1.0e-12)
    terminal = min(row["potential_bracket_domain"]["end"]["alpha_rad"] for row in rows)
    assert terminal < -0.69
    assert all(row["potential_bracket_domain"]["end"]["alpha_rad"] < row["first_no_induction_query"]["alpha_rad"] for row in rows)
    rectangle = report["pr97_rectangle"]
    assert rectangle["observed_solver_queries"] is False
    assert rectangle["mach_grid"] == [0.0, rectangle["mach_max"]]
    assert rectangle["mach_zero_is_outside_the_potential_image"] is True
    assert len(rectangle["alpha_rad"]) == 37
    assert rectangle["alpha_rad"][0] < terminal
    assert rectangle["alpha_rad"][-1] > first["alpha_rad"]
    declaration = json.loads((ROOT / "reports/retained_pins/two_profile_bem_screening/declaration.json").read_text())
    assert rectangle["alpha_rad"] == declaration["query_envelope"]["alpha_rad"]
    assert rectangle["reynolds_grid"] == declaration["query_envelope"]["reynolds_grid"]
    assert report["baseline"]["solver_policy"]["annulus_count"] == 40
    assert report["baseline"]["solver_policy"]["bounds"] == "error"
    assert report["baseline"]["solver_policy"]["annulus_settings"]["include_tip_loss"] is True
    assert report["baseline"]["solver_policy"]["annulus_settings"]["max_iterations"] == 100
    assert report["baseline"]["catalog_profile_ids"] == list(PROJECT_AIRFOIL_IDS)


def test_synthetic_traces_keep_positive_first_query_and_withhold_totals() -> None:
    report = _report()
    wide, gap = report["synthetic_traces"]
    terminal = min(row["potential_bracket_domain"]["end"]["alpha_rad"] for row in report["query_map"]["rows"])
    assert wide["outcome"] == "completed_without_publishing_totals"
    assert wide["evidence_class"] == "synthetic_inert_trace"
    assert wide["performance_totals_published"] is False
    assert wide["query_count"] < 40 * (1 + 128)
    assert wide["min_alpha_rad"] > terminal
    assert math.isclose(wide["first_query"]["alpha_rad"], report["query_map"]["rows"][0]["twist_rad"])
    assert gap["failed_annulus_index"] == 0
    assert gap["query_count"] == 1
    assert gap["first_query"]["alpha_rad"] > math.radians(10.0)
    assert "thrust" not in json.dumps(wide)
    assert "thrust" not in json.dumps(gap)


def test_provider_audit_preserves_failures_and_rejects_neuralfoil_mach() -> None:
    report = _report()
    audit = report["provider_audit"]
    assert audit["retained_real_bundles_in_repository"] == []
    naca0012 = audit["historical_failures"]["NACA0012"]
    naca2412 = audit["historical_failures"]["NACA2412"]
    assert naca0012["bem_calls"] == 0
    assert "not_converged" in naca0012["failure"]
    assert "-40 deg" in naca0012["failure"]
    assert "timeout" in naca2412["failure"]
    assert "per-angle" not in naca2412["failure"]
    assert audit["neuralfoil"]["adapter_supports_mach"] is False
    assert audit["neuralfoil"]["replacement_for_this_baseline"] is False
    assert "mach" in audit["neuralfoil"]["capability_rejection"]
    assert len(audit["hypotheses_not_observed"]) >= 2
    for name, digest in PIN_SHA256.items():
        payload = (ROOT / "reports/retained_pins/two_profile_bem_screening" / name).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == digest


def test_committed_report_matches_the_builder() -> None:
    report = _report()
    stored = json.loads((ROOT / "reports/polar_query_feasibility/report.json").read_text(encoding="utf-8"))
    assert stored == report
    assert (ROOT / "reports/polar_query_feasibility/report.md").read_text(encoding="utf-8") == render_polar_query_feasibility(report)


def test_recommended_experiment_is_one_unexecuted_probe() -> None:
    report = _report()
    experiment = report["recommended_experiment"]
    assert experiment["executed_by_this_diagnostic"] is False
    assert experiment["bem_calls"] == 0
    assert experiment["profiles"] == list(MATCHED_PAIR)
    assert experiment["call_limit"] == 8
    assert experiment["attempt_limit_per_call"] == 1
    assert experiment["retry"] is False
    assert experiment["mach_grid"][0] > 0.0
    assert experiment["alpha_rad_descending"][0] > experiment["alpha_rad_descending"][-1]
    assert experiment["alpha_rad_descending"][0] > report["query_map"]["rows"][0]["first_no_induction_query"]["alpha_rad"]
    assert experiment["provider"]["name"] == "xfoil-subprocess"
    assert "INIT" in experiment["provider"]["initialization"]
    assert experiment["physical_qualification"] is False
    text = render_polar_query_feasibility(report)
    assert "UNESTABLISHED" in text
    assert experiment["experiment_id"] in text
    assert "physical_qualification: false" in text
