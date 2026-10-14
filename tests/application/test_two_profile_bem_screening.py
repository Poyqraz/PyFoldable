"""Comparison boundary for one shared-planform, two-profile BEM screening."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from pyfoldable.application.two_profile_bem_screening import (
    ANNULUS_COUNT,
    MAX_BEM_CALLS,
    PROFILE_IDS,
    ScreeningError,
    _CallBudget,
    block_declared_screening,
    build_shared_declaration,
    canonical_json,
    execute_declared_screening,
    profile_bindings,
    publish_screening,
    render_comparison_csv,
    render_report,
    write_study_outputs,
)
from pyfoldable.core.providers import (
    PolarGenerationResult,
    PolarPointResult,
    PolarProviderExecutionError,
    ProviderIdentity,
)
from pyfoldable.providers.xfoil import XfoilProvider


ROOT = Path(__file__).resolve().parents[2]
NACA0012_SHA256 = "ab62d56cc86a591da4f83c1980ea5b07743c4e47bdb0eb63a8e166e190a96d42"
NACA2412_SHA256 = "3f84aba0f9234ed6e9fe4eedebe88ae8701a19ae181d70e21a02b0704916999a"


def _identity(version: str = "6.99") -> ProviderIdentity:
    return ProviderIdentity("xfoil-subprocess", "2", "XFOIL", version)


def _coefficients(alpha: float) -> tuple[float, float, float]:
    return (2.0 * math.pi * math.sin(alpha), 0.02 + 0.1 * alpha * alpha, 0.0)


class _Provider:
    def __init__(self, *, fail: bool = False, version: str = "6.99") -> None:
        self.fail = fail
        self.calls: list[object] = []
        self._identity = _identity(version)

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    @property
    def capabilities(self):
        return XfoilProvider.capabilities

    def generate(self, request):
        self.calls.append(request)
        if self.fail:
            raise PolarProviderExecutionError("forced provider failure")
        points = tuple(
            PolarPointResult(alpha, "converged", *_coefficients(alpha))
            for alpha in request.alpha_rad
        )
        return PolarGenerationResult(request, self.identity, points, elapsed_s=0.0)


def _record(**changes):
    declaration = build_shared_declaration(ROOT)
    record = {
        "airfoil_id": "NACA0012",
        "coordinate_sha256": NACA0012_SHA256,
        "draft_sha256": "a" * 64,
        "geometry_sha256": declaration["geometry_sha256"],
        "operating_condition_sha256": declaration["operating_condition_sha256"],
        "polar_content_sha256": "b" * 64,
        "polar_coordinate_sha256": NACA0012_SHA256,
        "status": "converged",
        "failure": None,
        "repeatable": True,
        "bem_calls": 2,
        "physical_qualification": False,
        "metrics": {
            "thrust_n": 1.0,
            "torque_nm": 0.1,
            "shaft_power_w": 70.0,
            "thrust_coefficient": 0.05,
            "torque_coefficient": 0.01,
            "power_coefficient": 0.02,
            "propulsive_efficiency": None,
        },
        "source_bound_report": None,
    }
    record.update(changes)
    return declaration, record


def test_shared_hashes_ignore_profile_coordinates_and_drafts_do_not() -> None:
    declaration = build_shared_declaration(ROOT)
    bindings = profile_bindings(ROOT)
    text = canonical_json(declaration)

    assert declaration["profiles"] == list(PROFILE_IDS)
    assert declaration["physical_qualification"] is False
    assert declaration["capture_budget"]["annulus_count"] == ANNULUS_COUNT
    assert declaration["capture_budget"]["max_bem_calls"] == MAX_BEM_CALLS
    assert declaration["capture_budget"]["expansion_allowed"] is False
    assert declaration["solver"]["bounds"] == "error"
    assert NACA0012_SHA256 not in text
    assert NACA2412_SHA256 not in text
    assert "NACA" not in canonical_json(declaration["geometry"])
    assert "NACA" not in canonical_json(declaration["operating_condition"])
    assert bindings["NACA0012"]["geometry_sha256"] == bindings["NACA2412"]["geometry_sha256"]
    assert (
        bindings["NACA0012"]["operating_condition_sha256"]
        == bindings["NACA2412"]["operating_condition_sha256"]
    )
    assert bindings["NACA0012"]["geometry_sha256"] == declaration["geometry_sha256"]
    assert bindings["NACA0012"]["coordinate_sha256"] == NACA0012_SHA256
    assert bindings["NACA2412"]["coordinate_sha256"] == NACA2412_SHA256
    assert bindings["NACA0012"]["draft_sha256"] != bindings["NACA2412"]["draft_sha256"]
    reloaded = json.loads(text)
    assert canonical_json(reloaded) == text
    assert reloaded["shared_declaration_sha256"] == declaration["shared_declaration_sha256"]


def test_declared_grid_covers_the_positive_only_search_image() -> None:
    declaration = build_shared_declaration(ROOT)
    envelope = declaration["query_envelope"]

    assert envelope["alpha_rad"][0] <= envelope["alpha_rad_min"]
    assert envelope["alpha_rad"][-1] >= envelope["alpha_rad_max"]
    assert envelope["reynolds_grid"][0] <= envelope["reynolds_min"]
    assert envelope["reynolds_grid"][-1] >= envelope["reynolds_max"]
    assert envelope["mach_grid"][0] <= envelope["mach_min"]
    assert envelope["mach_grid"][-1] >= envelope["mach_max"]
    assert envelope["reynolds_grid"][0] > 0.0
    assert len(envelope["mach_grid"]) == 2
    assert len(envelope["reynolds_grid"]) == 2
    assert declaration["capture_budget"]["cells_per_profile"] == 4
    assert all(
        later > earlier
        for earlier, later in zip(envelope["alpha_rad"], envelope["alpha_rad"][1:])
    )


def test_successful_runs_publish_profile_metrics_without_a_winner(monkeypatch) -> None:
    calls = {"bem": 0}
    screening = __import__(
        "pyfoldable.application.two_profile_bem_screening", fromlist=["run_design_analysis"]
    )
    real_run = screening.run_design_analysis

    def _count(draft, families, **kwargs):
        calls["bem"] += 1
        return real_run(draft, families, **kwargs)

    monkeypatch.setattr(screening, "run_design_analysis", _count)
    declaration = build_shared_declaration(ROOT)
    provider = _Provider()
    result = execute_declared_screening(declaration, provider=provider, repository_root=ROOT)
    published = result["published"]

    assert calls["bem"] == MAX_BEM_CALLS
    assert len(provider.calls) == 8
    assert published["winner"] is None
    assert published["combined_totals"] is None
    assert published["physical_qualification"] is False
    assert published["failure_ledger"] == []
    assert [row["airfoil_id"] for row in published["comparison_rows"]] == list(PROFILE_IDS)
    assert published["comparison_rows"][0]["draft_sha256"] != published["comparison_rows"][1]["draft_sha256"]
    assert {
        row["geometry_sha256"] for row in published["comparison_rows"]
    } == {declaration["geometry_sha256"]}
    assert {
        row["operating_condition_sha256"] for row in published["comparison_rows"]
    } == {declaration["operating_condition_sha256"]}
    for row in published["comparison_rows"]:
        assert row["physical_qualification"] is False
        assert row["repeatable"] is True
        assert row["propulsive_efficiency"] is None
        assert math.isfinite(row["thrust_n"])
        assert math.isfinite(row["torque_nm"])
        assert math.isfinite(row["shaft_power_w"])
        assert math.isfinite(row["thrust_coefficient"])
        assert math.isfinite(row["torque_coefficient"])
        assert math.isfinite(row["power_coefficient"])
        assert row["coordinate_sha256"] == row["polar_coordinate_sha256"]
    reports = [record["source_bound_report"] for record in result["records"]]
    assert [json.loads(report)["artifact_class"] for report in reports] == [
        "active_design_bem_screening",
        "active_design_bem_screening",
    ]
    assert all(json.loads(report)["physical_qualification"] is False for report in reports)


def test_provider_failure_remains_in_the_ledger_and_does_not_call_bem(monkeypatch) -> None:
    def _forbidden(*args, **kwargs):
        raise AssertionError("BEM must not run without a complete polar family")

    monkeypatch.setattr(
        "pyfoldable.application.two_profile_bem_screening.run_design_analysis",
        _forbidden,
    )
    declaration = build_shared_declaration(ROOT)
    provider = _Provider(fail=True)
    result = execute_declared_screening(
        declaration, provider=provider, repository_root=ROOT
    )
    published = result["published"]

    assert published["comparison_rows"] == []
    assert published["combined_totals"] is None
    assert published["winner"] is None
    assert [row["airfoil_id"] for row in published["failure_ledger"]] == list(PROFILE_IDS)
    assert {row["status"] for row in published["failure_ledger"]} == {"polar_generation_failed"}
    assert all("forced provider failure" in row["failure"] for row in published["failure_ledger"])
    assert all("thrust_n" not in row for row in published["failure_ledger"])
    assert published["bem_calls"] == 0
    assert len(provider.calls) == len(PROFILE_IDS)


def test_provider_identity_mismatch_does_not_query_or_solve() -> None:
    declaration = build_shared_declaration(ROOT)
    provider = _Provider(version="synthetic")
    result = execute_declared_screening(declaration, provider=provider, repository_root=ROOT)

    assert provider.calls == []
    assert result["published"]["bem_calls"] == 0
    assert result["published"]["comparison_rows"] == []
    assert {row["status"] for row in result["published"]["failure_ledger"]} == {
        "provider_identity_mismatch"
    }


def test_mutated_envelope_is_rejected_before_provider_execution() -> None:
    declaration = build_shared_declaration(ROOT)
    mutated = copy.deepcopy(declaration)
    mutated["query_envelope"]["alpha_rad"].append(mutated["query_envelope"]["alpha_rad"][-1] + 0.1)
    provider = _Provider()

    with pytest.raises(ScreeningError, match="Declaration"):
        execute_declared_screening(mutated, provider=provider, repository_root=ROOT)
    assert provider.calls == []


def test_bem_budget_rejects_a_fifth_call() -> None:
    budget = _CallBudget(MAX_BEM_CALLS, "BEM")
    for _ in range(MAX_BEM_CALLS):
        budget.charge()
    with pytest.raises(ScreeningError, match="BEM budget"):
        budget.charge()


def test_mismatched_polar_coordinate_has_no_comparison_row_or_total() -> None:
    declaration, first = _record(polar_coordinate_sha256="0" * 64)
    _, second = _record(
        airfoil_id="NACA2412",
        coordinate_sha256=NACA2412_SHA256,
        polar_coordinate_sha256=NACA2412_SHA256,
        draft_sha256="c" * 64,
    )
    published = publish_screening([first, second], declaration)

    assert [row["airfoil_id"] for row in published["comparison_rows"]] == ["NACA2412"]
    assert published["failure_ledger"][0]["airfoil_id"] == "NACA0012"
    assert published["failure_ledger"][0]["status"] == "polar_coordinate_mismatch"
    assert "thrust_n" not in published["failure_ledger"][0]
    assert published["combined_totals"] is None
    assert published["winner"] is None


def test_one_failed_profile_does_not_publish_a_partial_total() -> None:
    declaration, first = _record()
    _, second = _record(
        airfoil_id="NACA2412",
        coordinate_sha256=NACA2412_SHA256,
        polar_coordinate_sha256=NACA2412_SHA256,
        draft_sha256="c" * 64,
        status="bem_failed",
        failure="Annulus 0 failed: outside the declared polar grid.",
        repeatable=None,
        metrics=None,
        bem_calls=1,
    )
    published = publish_screening([first, second], declaration)
    csv_text = render_comparison_csv(published)
    report = render_report(published, runtime={"python": "3.12.3"})

    assert published["combined_totals"] is None
    assert published["winner"] is None
    assert [row["airfoil_id"] for row in published["comparison_rows"]] == ["NACA0012"]
    assert published["failure_ledger"][0]["status"] == "bem_failed"
    assert "outside the declared polar grid" in published["failure_ledger"][0]["failure"]
    assert "winner" not in csv_text.casefold()
    assert "NACA2412" in csv_text
    assert "outside the declared polar grid" in report
    assert "physical_qualification: false" in report
    assert "Qualified winner: none" in report
    assert "Combined totals: none" in report


def test_qualification_claim_is_rejected() -> None:
    declaration, first = _record(physical_qualification=True)
    _, second = _record(
        airfoil_id="NACA2412",
        coordinate_sha256=NACA2412_SHA256,
        polar_coordinate_sha256=NACA2412_SHA256,
    )
    with pytest.raises(ScreeningError, match="physical_qualification"):
        publish_screening([first, second], declaration)


def test_writer_emits_profile_json_csv_and_report(tmp_path: Path) -> None:
    declaration, first = _record()
    _, second = _record(
        airfoil_id="NACA2412",
        coordinate_sha256=NACA2412_SHA256,
        draft_sha256="c" * 64,
        status="polar_generation_failed",
        failure="XFOIL did not converge.",
        repeatable=None,
        metrics=None,
        polar_content_sha256=None,
        polar_coordinate_sha256=None,
        bem_calls=0,
    )
    published = publish_screening([first, second], declaration)
    write_study_outputs(
        tmp_path,
        declaration=declaration,
        records=[first, second],
        published=published,
        runtime={"python": "3.12.3", "provider": "xfoil-subprocess"},
    )

    assert json.loads((tmp_path / "declaration.json").read_text(encoding="utf-8"))[
        "shared_declaration_sha256"
    ] == declaration["shared_declaration_sha256"]
    failed = json.loads((tmp_path / "NACA2412.json").read_text(encoding="utf-8"))
    succeeded = json.loads((tmp_path / "NACA0012.json").read_text(encoding="utf-8"))
    assert failed["physical_qualification"] is False
    assert failed["comparison_published"] is False
    assert "thrust_n" not in failed
    assert succeeded["comparison_published"] is True
    assert succeeded["thrust_n"] == 1.0
    assert "ledger" in (tmp_path / "comparison.csv").read_text(encoding="utf-8")
    assert "screening" in (tmp_path / "report.md").read_text(encoding="utf-8").casefold()


def test_missing_provider_blocks_both_profiles_before_bem() -> None:
    declaration = build_shared_declaration(ROOT)
    result = block_declared_screening(
        declaration,
        repository_root=ROOT,
        status="provider_unavailable",
        failure="XFOIL executable was not found.",
    )
    published = result["published"]

    assert published["comparison_rows"] == []
    assert published["combined_totals"] is None
    assert published["winner"] is None
    assert published["bem_calls"] == 0
    assert [row["status"] for row in published["failure_ledger"]] == [
        "provider_unavailable",
        "provider_unavailable",
    ]
