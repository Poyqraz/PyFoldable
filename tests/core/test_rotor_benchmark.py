import json
from dataclasses import replace
from pathlib import Path

import pytest

from pyfoldable.core import (
    BEMAnnulusSettings,
    BEMRotorSettings,
    PolarFamily,
    PolarTable,
    RotorBenchmarkError,
    RotorBenchmarkPolicy,
    SpanwisePolarAnchor,
    SpanwisePolarSchedule,
    build_rotor_benchmark_proxy_polar_family,
    evaluate_rotor_benchmark_variant,
    load_rotor_benchmark_fixture,
    radial_convergence_evidence,
    run_rotor_benchmark_cases,
    run_rotor_benchmark_cases_with_results,
)
from pyfoldable.core.models import BladeGeometry


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
    annulus = BEMAnnulusSettings(
        include_tip_loss=True,
        include_root_loss=False,
        loading_branch="signed_nonreversed",
    )
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
        variant_id="qprop-signed-tip_proxy-baseline",
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


@pytest.mark.parametrize("field", ("id", "kind", "url", "citation"))
def test_fixture_sources_require_complete_provenance(field):
    fixture = load_rotor_benchmark_fixture(FIXTURE)
    source = dict(fixture.sources[0])
    source[field] = ""

    with pytest.raises(RotorBenchmarkError, match="source provenance"):
        replace(fixture, sources=(source, *fixture.sources[1:]))


def test_selected_pr06c_variant_reproduces_frozen_failure_evidence():
    fixture, convergence, actual = _selected_variant()
    stored = json.loads(REPORT.read_text(encoding="utf-8"))

    assert stored["schema_version"] == 3
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
    assert len(stored["sensitivity_variants"]) == 6
    snel = next(
        variant
        for variant in stored["sensitivity_variants"]
        if "snel-1993" in variant["variant_id"]
    )
    assert not snel["passed"]
    assert snel["settings"]["annulus_settings"]["rotational_augmentation"][
        "model_id"
    ] == "snel-1993-v1"
    assert not any(
        variant["passed"] for variant in stored["sensitivity_variants"]
    )
    assert not actual["passed"]
    assert actual["successful_point_count"] == 50
    assert actual["solution_coverage"] == pytest.approx(1.0)
    assert actual["failure_counts"] == {}
    assert actual["gates"] == {
        "solution_coverage": True,
        "ct_wmape": False,
        "cp_wmape": False,
        "ct_bias": False,
        "cp_bias": False,
        "radial_convergence": True,
        "representative_polar_evidence": False,
        "regime_solution_coverage": True,
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

    with pytest.raises(RotorBenchmarkError, match="typed polar evidence"):
        evaluate_rotor_benchmark_variant(
            fixture,
            predictions,
            RotorBenchmarkPolicy(),
            variant_id="forged-representative-evidence",
            representative_polar_evidence=True,
            radial_terminal_delta=0.0,
            settings=settings,
            polar_contract={},
        )


def test_benchmark_override_rejects_incompatible_blade_identity():
    fixture = load_rotor_benchmark_fixture(FIXTURE)
    family = build_rotor_benchmark_proxy_polar_family()
    blade = fixture.blade(family.airfoil_id)
    wrong_diameter = BladeGeometry(
        diameter_m=blade.diameter_m * 0.99,
        hub_radius_m=blade.hub_radius_m,
        blade_count=blade.blade_count,
        stations=blade.stations,
    )
    wrong_count = BladeGeometry(
        diameter_m=blade.diameter_m,
        hub_radius_m=blade.hub_radius_m,
        blade_count=blade.blade_count + 1,
        stations=blade.stations,
    )

    with pytest.raises(RotorBenchmarkError, match="diameter"):
        run_rotor_benchmark_cases(fixture, family, blade=wrong_diameter)
    with pytest.raises(RotorBenchmarkError, match="blade count"):
        radial_convergence_evidence(
            fixture,
            family,
            point_ids=("static-6528",),
            blade=wrong_count,
        )


def test_benchmark_and_convergence_consume_the_same_spanwise_schedule():
    fixture = load_rotor_benchmark_fixture(FIXTURE)
    base = build_rotor_benchmark_proxy_polar_family()

    def renamed(airfoil_id: str) -> PolarFamily:
        return PolarFamily(
            tuple(
                PolarTable(
                    airfoil_id=airfoil_id,
                    scenario_id=table.scenario_id,
                    reynolds=table.reynolds,
                    mach=table.mach,
                    alpha_rad=table.alpha_rad,
                    cl=table.cl,
                    cd=table.cd,
                    cm=table.cm,
                    source=f"{table.source}:{airfoil_id}",
                    metadata=table.metadata,
                )
                for table in base.tables
            )
        )

    blade = fixture.blade("geometry-only")
    schedule = SpanwisePolarSchedule(
        "E63-to-APC12-screen",
        (
            SpanwisePolarAnchor(blade.stations[0].r_over_R, renamed("E63")),
            SpanwisePolarAnchor(blade.stations[-1].r_over_R, renamed("APC12")),
        ),
    )
    settings = BEMRotorSettings(
        4,
        "station_span",
        BEMAnnulusSettings(loading_branch="signed_nonreversed"),
    )

    predictions, rotor_results = run_rotor_benchmark_cases_with_results(
        fixture, schedule, settings=settings, blade=blade
    )
    convergence = radial_convergence_evidence(
        fixture,
        schedule,
        point_ids=("static-6528", "forward-6512-j0199"),
        annulus_counts=(2, 4),
        annulus_settings=settings.annulus_settings,
        blade=blade,
    )

    assert len(predictions) == 50
    assert len(rotor_results) == 50
    assert sum(result.annulus_count for result in rotor_results) == 200
    assert convergence["maximum_terminal_relative_delta"] >= 0.0
