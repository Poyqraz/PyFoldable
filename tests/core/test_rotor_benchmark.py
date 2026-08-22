import json
from dataclasses import replace
from pathlib import Path

import pytest

from pyfoldable.core import (
    BEMAnnulusSettings,
    BEMRotorSettings,
    RotorBenchmarkError,
    RotorBenchmarkPolicy,
    build_rotor_benchmark_proxy_polar_family,
    evaluate_rotor_benchmark_variant,
    load_rotor_benchmark_fixture,
    radial_convergence_evidence,
    run_rotor_benchmark_cases,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "rotor_benchmark"
    / "uiuc_apcsf_10x4.7_v1.json"
)
REPORT = PROJECT_ROOT / "reports" / "pr06c_fixed_propeller_benchmark.json"


def _selected_variant():
    fixture = load_rotor_benchmark_fixture(FIXTURE)
    family = build_rotor_benchmark_proxy_polar_family()
    annulus = BEMAnnulusSettings(include_tip_loss=True, include_root_loss=False)
    settings = BEMRotorSettings(80, "station_span", annulus)
    convergence = radial_convergence_evidence(
        fixture,
        family,
        point_ids=("static-6528", "forward-6512-j0199"),
        annulus_settings=annulus,
    )
    predictions = run_rotor_benchmark_cases(fixture, family, settings=settings)
    result = evaluate_rotor_benchmark_variant(
        fixture,
        predictions,
        RotorBenchmarkPolicy(),
        variant_id="qprop-tip_proxy-baseline",
        representative_polar_evidence=False,
        radial_terminal_delta=convergence["maximum_terminal_relative_delta"],
        settings=settings,
        polar_contract={
            "evidence_class": "analytic_proxy",
            "representative_polar_evidence": False,
        },
    )
    return fixture, convergence, result


def test_uiuc_fixture_keeps_raw_windmilling_evidence_outside_propulsive_gate():
    fixture = load_rotor_benchmark_fixture(FIXTURE)

    assert len(fixture.points) == 60
    assert len(fixture.eligible_points) == 50
    assert sum(point.regime == "static" for point in fixture.eligible_points) == 16
    assert all(
        point.thrust_coefficient > 0.0 for point in fixture.eligible_points
    )
    assert all(
        point.thrust_coefficient < 0.0
        for point in fixture.points
        if not point.qualification_eligible
    )


def test_fixture_requires_eligible_points_in_both_declared_regimes():
    fixture = load_rotor_benchmark_fixture(FIXTURE)

    with pytest.raises(RotorBenchmarkError, match="eligible static and forward"):
        replace(
            fixture,
            points=tuple(point for point in fixture.points if point.regime == "static"),
        )


def test_selected_pr06c_variant_reproduces_frozen_failure_evidence():
    fixture, convergence, actual = _selected_variant()
    stored = json.loads(REPORT.read_text(encoding="utf-8"))

    assert stored["fixture"]["sha256"] == fixture.source_sha256
    assert {
        key: value
        for key, value in stored["selected_variant"].items()
        if key != "polar_contract"
    } == {key: value for key, value in actual.items() if key != "polar_contract"}
    assert stored["selected_variant"]["polar_contract"]["evidence_class"] == (
        "analytic_proxy"
    )
    assert stored["radial_convergence"] == convergence
    assert len(stored["sensitivity_variants"]) == 4
    assert not any(
        variant["passed"] for variant in stored["sensitivity_variants"]
    )
    assert not actual["passed"]
    assert actual["successful_point_count"] == 23
    assert actual["solution_coverage"] == pytest.approx(0.46)
    assert actual["failure_counts"] == {"BEMConvergenceError": 27}
    assert actual["gates"] == {
        "solution_coverage": False,
        "ct_wmape": True,
        "cp_wmape": True,
        "ct_bias": False,
        "cp_bias": True,
        "radial_convergence": True,
        "representative_polar_evidence": False,
        "regime_solution_coverage": False,
        "regime_ct_wmape": False,
        "regime_cp_wmape": False,
        "regime_ct_bias": False,
        "regime_cp_bias": False,
    }


def test_benchmark_rejects_missing_or_duplicate_prediction_evidence():
    fixture = load_rotor_benchmark_fixture(FIXTURE)
    family = build_rotor_benchmark_proxy_polar_family()
    settings = BEMRotorSettings(2)
    predictions = run_rotor_benchmark_cases(fixture, family, settings=settings)

    with pytest.raises(RotorBenchmarkError, match="exactly once"):
        evaluate_rotor_benchmark_variant(
            fixture,
            (*predictions[:-1], predictions[0]),
            RotorBenchmarkPolicy(),
            variant_id="forged",
            representative_polar_evidence=False,
            radial_terminal_delta=0.0,
            settings=settings,
            polar_contract={},
        )
