"""Golden acceptance and cross-provider benchmark behavior."""

from __future__ import annotations

import json
import sys
import textwrap
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

from pyfoldable import NeuralFoilProvider, XfoilProvider
from pyfoldable.core import (
    POLAR_ACCEPTANCE_SCHEMA_VERSION,
    PolarAcceptanceCriteria,
    PolarBenchmarkReport,
    PolarErrorTolerance,
    PolarGenerationResult,
    PolarGoldenFixture,
    PolarPointResult,
    PolarProviderExecutionError,
    ProviderCapabilities,
    ProviderIdentity,
    compare_polar_results,
    load_polar_golden_fixture,
    run_polar_provider_benchmark,
)


FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "polar_acceptance"
    / "naca0012_re200k.json"
)
CAPABILITIES = ProviderCapabilities(
    supports_mach=True,
    supports_n_crit=True,
    supports_forced_transition=True,
    supports_pointwise_confidence=False,
    supports_partial_results=True,
    supports_vectorized_alpha=True,
    supports_iteration_limit=True,
    supports_timeout=True,
)


def _candidate(
    fixture: PolarGoldenFixture,
    identity: ProviderIdentity,
    *,
    cl_offset: float = 0.0,
    cd_offset: float = 0.0,
    cm_offset: float = 0.0,
    failed_index: int | None = None,
) -> PolarGenerationResult:
    points = []
    for index, point in enumerate(fixture.reference.points):
        if index == failed_index:
            points.append(PolarPointResult(point.alpha_rad, "not_converged"))
        else:
            points.append(
                replace(
                    point,
                    cl=float(point.cl) + cl_offset,
                    cd=float(point.cd) + cd_offset,
                    cm=float(point.cm) + cm_offset,
                )
            )
    return PolarGenerationResult(
        fixture.reference.request,
        identity,
        tuple(points),
        0.123,
    )


class FixtureProvider:
    capabilities = CAPABILITIES

    def __init__(
        self,
        fixture: PolarGoldenFixture,
        name: str,
        *,
        cl_offset: float = 0.0,
        error: BaseException | None = None,
    ) -> None:
        self.fixture = fixture
        self.identity = ProviderIdentity(name, "1", f"{name}-backend", "1")
        self.cl_offset = cl_offset
        self.error = error

    def generate(self, request):
        if self.error is not None:
            raise self.error
        assert request == self.fixture.reference.request
        return _candidate(self.fixture, self.identity, cl_offset=self.cl_offset)


def test_golden_fixture_loads_as_a_versioned_provider_result() -> None:
    fixture = load_polar_golden_fixture(FIXTURE_PATH)

    assert POLAR_ACCEPTANCE_SCHEMA_VERSION == 1
    assert fixture.name == "naca0012_re200k_clean"
    assert fixture.reference.provider.name == "golden"
    assert fixture.reference.complete
    assert len(fixture.reference.points) == 9


def test_comparison_reports_coefficient_metrics_and_mapping() -> None:
    fixture = load_polar_golden_fixture(FIXTURE_PATH)
    candidate = _candidate(
        fixture,
        ProviderIdentity("xfoil", "1", "xfoil", "6.99"),
        cl_offset=0.01,
        cd_offset=0.0002,
        cm_offset=0.001,
    )

    report = compare_polar_results(fixture.reference, candidate)

    assert report.passed
    assert report.coverage == 1.0
    assert report.usable_match_count == 9
    assert tuple(metric.coefficient for metric in report.metrics) == ("cl", "cd", "cm")
    assert report.metrics[0].max_absolute_error == pytest.approx(0.01)
    assert report.as_mapping()["schema_version"] == 1
    assert report.as_mapping()["candidate_provider"]["name"] == "xfoil"


@pytest.mark.parametrize(
    ("offsets", "coefficient"),
    [
        ({"cl_offset": 0.2}, "cl"),
        ({"cd_offset": 0.02}, "cd"),
        ({"cm_offset": 0.1}, "cm"),
    ],
)
def test_each_coefficient_can_fail_its_own_tolerance(offsets, coefficient) -> None:
    fixture = load_polar_golden_fixture(FIXTURE_PATH)
    candidate = _candidate(
        fixture,
        ProviderIdentity("candidate", "1", "backend", "1"),
        **offsets,
    )

    report = compare_polar_results(fixture.reference, candidate)

    assert not report.passed
    failed = {metric.coefficient for metric in report.metrics if not metric.passed}
    assert coefficient in failed


def test_convergence_mismatch_and_coverage_are_explicit_acceptance_gates() -> None:
    fixture = load_polar_golden_fixture(FIXTURE_PATH)
    candidate = _candidate(
        fixture,
        ProviderIdentity("partial", "1", "backend", "1"),
        failed_index=3,
    )

    strict = compare_polar_results(fixture.reference, candidate)
    relaxed = compare_polar_results(
        fixture.reference,
        candidate,
        criteria=PolarAcceptanceCriteria(
            minimum_coverage=8 / 9,
            require_usable_match=False,
        ),
    )

    assert not strict.passed
    assert strict.coverage == pytest.approx(8 / 9)
    assert not strict.usable_match_passed
    assert relaxed.passed


def test_comparison_rejects_request_drift_and_zero_overlap() -> None:
    fixture = load_polar_golden_fixture(FIXTURE_PATH)
    identity = ProviderIdentity("candidate", "1", "backend", "1")
    candidate = _candidate(fixture, identity)
    different_request = replace(candidate.request, reynolds=300_000.0)

    with pytest.raises(ValueError, match="requests must match"):
        compare_polar_results(
            fixture.reference,
            replace(candidate, request=different_request),
        )

    failed = replace(
        candidate,
        points=tuple(
            PolarPointResult(point.alpha_rad, "not_converged")
            for point in candidate.points
        ),
    )
    with pytest.raises(ValueError, match="no usable points"):
        compare_polar_results(fixture.reference, failed)


def test_cross_provider_benchmark_builds_complete_matrix_and_records_timing() -> None:
    fixture = load_polar_golden_fixture(FIXTURE_PATH)
    matching = FixtureProvider(fixture, "xfoil", cl_offset=0.01)
    drifting = FixtureProvider(fixture, "neuralfoil", cl_offset=0.2)

    report = run_polar_provider_benchmark((matching, drifting), (fixture,))

    assert report.provider_count == 2
    assert report.fixture_count == 1
    assert len(report.entries) == 2
    assert report.entries[0].passed
    assert report.entries[0].provider_elapsed_s == pytest.approx(0.123)
    assert report.entries[0].wall_elapsed_s >= 0.0
    assert not report.entries[1].passed
    assert not report.passed
    assert report.as_mapping()["entries"][1]["acceptance"]["passed"] is False
    assert report.provider_summaries[0].passed_count == 1
    assert report.provider_summaries[1].failed_count == 1


def test_real_adapter_boundaries_pass_the_same_golden_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_polar_golden_fixture(FIXTURE_PATH)
    executable = tmp_path / "fixture_xfoil"
    executable.write_text(
        textwrap.dedent(
            r"""
            #!/usr/bin/env python3
            import pathlib
            import sys

            commands = sys.stdin.read()
            alphas = [
                float(line.split()[1])
                for line in commands.splitlines()
                if line.upper().startswith("ALFA ")
            ]
            lines = [
                " alpha      CL        CD       CDp       CM     Top_Xtr  Bot_Xtr",
                " ------  --------  --------  --------  --------  --------  --------",
            ]
            for alpha in alphas:
                lines.append(
                    f"{alpha:8.4f} {0.1 * alpha:9.5f} "
                    f"{0.01 + 0.0001 * alpha * alpha:9.6f} 0.005 -0.020 1.0 1.0"
                )
            pathlib.Path("polar.txt").write_text("\n".join(lines), encoding="utf-8")
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)

    backend = ModuleType("neuralfoil")
    backend.__version__ = "0.3.3-fixture"

    def get_aero_from_coordinates(**kwargs):
        alpha = np.asarray(kwargs["alpha"], dtype=float).reshape(-1)
        count = alpha.size
        return {
            "analysis_confidence": np.ones(count),
            "CL": 0.1 * alpha,
            "CD": 0.01 + 0.0001 * alpha**2,
            "CM": np.full(count, -0.02),
            "Top_Xtr": np.ones(count),
            "Bot_Xtr": np.ones(count),
        }

    backend.get_aero_from_coordinates = get_aero_from_coordinates
    monkeypatch.setitem(sys.modules, "neuralfoil", backend)

    report = run_polar_provider_benchmark(
        (
            XfoilProvider(executable, backend_version="6.99-fixture"),
            NeuralFoilProvider(),
        ),
        (fixture,),
    )

    assert tuple(entry.provider.name for entry in report.entries) == (
        "xfoil-subprocess",
        "neuralfoil",
    )
    assert report.passed


@pytest.mark.parametrize(
    "error",
    [
        PolarProviderExecutionError("malformed output"),
        RuntimeError("unexpected\nbackend failure"),
    ],
)
def test_benchmark_isolates_provider_errors_without_losing_audit_data(error) -> None:
    fixture = load_polar_golden_fixture(FIXTURE_PATH)
    failing = FixtureProvider(fixture, "failing", error=error)
    healthy = FixtureProvider(fixture, "healthy")

    report = run_polar_provider_benchmark((failing, healthy), (fixture,))

    assert report.entries[0].error_type
    assert "backend failure" in report.entries[0].error_message or (
        report.entries[0].error_message == "malformed output"
    )
    assert "\n" not in report.entries[0].error_message
    assert report.entries[1].passed


def test_benchmark_never_masks_base_exceptions() -> None:
    fixture = load_polar_golden_fixture(FIXTURE_PATH)
    provider = FixtureProvider(fixture, "interrupt", error=KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        run_polar_provider_benchmark((provider,), (fixture,))


def test_benchmark_rejects_duplicate_provider_identity_and_fixture_name() -> None:
    fixture = load_polar_golden_fixture(FIXTURE_PATH)
    first = FixtureProvider(fixture, "same")
    second = FixtureProvider(fixture, "same")

    with pytest.raises(ValueError, match="unique identities"):
        run_polar_provider_benchmark((first, second), (fixture,))
    with pytest.raises(ValueError, match="unique names"):
        run_polar_provider_benchmark(
            (first,),
            (fixture, PolarGoldenFixture(fixture.name, fixture.reference)),
        )


def test_tolerance_and_criteria_validation_reject_ambiguous_values() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        PolarErrorTolerance(0.0, 0.0)
    with pytest.raises(ValueError, match=r"in \(0, 1\]"):
        PolarAcceptanceCriteria(minimum_coverage=0.0)
    with pytest.raises(ValueError, match="bool"):
        PolarAcceptanceCriteria(require_usable_match=1)


def test_error_exactly_on_absolute_plus_relative_limit_passes() -> None:
    fixture = load_polar_golden_fixture(FIXTURE_PATH)
    tolerance = PolarErrorTolerance(absolute=0.01, relative=0.10)
    candidate = PolarGenerationResult(
        fixture.reference.request,
        ProviderIdentity("boundary", "1", "backend", "1"),
        tuple(
            replace(
                point,
                cl=float(point.cl) + tolerance.limit_for(float(point.cl)),
            )
            for point in fixture.reference.points
        ),
        0.0,
    )
    criteria = PolarAcceptanceCriteria(cl=tolerance)

    assert compare_polar_results(
        fixture.reference,
        candidate,
        criteria=criteria,
    ).passed


def test_report_rejects_an_incomplete_provider_fixture_matrix() -> None:
    fixture = load_polar_golden_fixture(FIXTURE_PATH)
    first = FixtureProvider(fixture, "first")
    second = FixtureProvider(fixture, "second")
    complete = run_polar_provider_benchmark((first, second), (fixture,))
    renamed = replace(
        complete.entries[1],
        fixture_name="another-fixture",
    )

    with pytest.raises(ValueError, match="complete provider/fixture matrix"):
        PolarBenchmarkReport((complete.entries[0], renamed), complete.criteria)


def test_fixture_loader_rejects_schema_and_unknown_fields(tmp_path: Path) -> None:
    document = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    document["schema_version"] = 99
    invalid_schema = tmp_path / "schema.json"
    invalid_schema.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported"):
        load_polar_golden_fixture(invalid_schema)

    document["schema_version"] = 1
    document["unexpected"] = True
    unknown = tmp_path / "unknown.json"
    unknown.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="fields mismatch"):
        load_polar_golden_fixture(unknown)
