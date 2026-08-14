"""Golden-fixture acceptance and cross-provider polar benchmarks."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .models import AirfoilDefinition
from .providers import (
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarPointResult,
    PolarProvider,
    PolarProviderError,
    ProviderIdentity,
    generate_polar,
)


POLAR_ACCEPTANCE_SCHEMA_VERSION = 1


def _non_negative_finite(name: str, value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value < 0.0
    ):
        raise ValueError(f"{name} must be a non-negative finite number.")


@dataclass(frozen=True)
class PolarErrorTolerance:
    """Absolute-plus-relative tolerance for one aerodynamic coefficient."""

    absolute: float
    relative: float = 0.0

    def __post_init__(self) -> None:
        _non_negative_finite("absolute", self.absolute)
        _non_negative_finite("relative", self.relative)
        if self.absolute == 0.0 and self.relative == 0.0:
            raise ValueError("At least one error tolerance must be greater than zero.")

    def limit_for(self, reference: float) -> float:
        """Return the allowed absolute error at one reference value."""
        if not math.isfinite(reference):
            raise ValueError("reference must be finite.")
        return float(self.absolute + self.relative * abs(reference))

    def as_mapping(self) -> dict[str, float]:
        return {"absolute": float(self.absolute), "relative": float(self.relative)}


@dataclass(frozen=True)
class PolarAcceptanceCriteria:
    """Acceptance envelope shared by golden and cross-provider comparisons."""

    cl: PolarErrorTolerance = field(
        default_factory=lambda: PolarErrorTolerance(absolute=0.05, relative=0.02)
    )
    cd: PolarErrorTolerance = field(
        default_factory=lambda: PolarErrorTolerance(absolute=0.002, relative=0.10)
    )
    cm: PolarErrorTolerance = field(
        default_factory=lambda: PolarErrorTolerance(absolute=0.01, relative=0.05)
    )
    minimum_coverage: float = 1.0
    require_usable_match: bool = True

    def __post_init__(self) -> None:
        for name in ("cl", "cd", "cm"):
            if not isinstance(getattr(self, name), PolarErrorTolerance):
                raise TypeError(f"{name} must be a PolarErrorTolerance.")
        if (
            isinstance(self.minimum_coverage, bool)
            or not isinstance(self.minimum_coverage, (int, float))
            or not math.isfinite(float(self.minimum_coverage))
            or not 0.0 < self.minimum_coverage <= 1.0
        ):
            raise ValueError("minimum_coverage must be in (0, 1].")
        if not isinstance(self.require_usable_match, bool):
            raise ValueError("require_usable_match must be bool.")

    def as_mapping(self) -> dict[str, object]:
        return {
            "cl": self.cl.as_mapping(),
            "cd": self.cd.as_mapping(),
            "cm": self.cm.as_mapping(),
            "minimum_coverage": float(self.minimum_coverage),
            "require_usable_match": self.require_usable_match,
        }


@dataclass(frozen=True)
class PolarCoefficientMetrics:
    """Error statistics and pointwise tolerance outcome for one coefficient."""

    coefficient: str
    compared_points: int
    max_absolute_error: float
    mean_absolute_error: float
    rms_error: float
    violating_points: tuple[int, ...]
    passed: bool

    def __post_init__(self) -> None:
        if self.coefficient not in {"cl", "cd", "cm"}:
            raise ValueError("coefficient must be 'cl', 'cd', or 'cm'.")
        if (
            isinstance(self.compared_points, bool)
            or not isinstance(self.compared_points, int)
            or self.compared_points < 1
        ):
            raise ValueError("compared_points must be a positive integer.")
        for name in ("max_absolute_error", "mean_absolute_error", "rms_error"):
            _non_negative_finite(name, getattr(self, name))
        if any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            or index >= self.compared_points
            for index in self.violating_points
        ):
            raise ValueError("violating_points must contain valid comparison indices.")
        if tuple(sorted(set(self.violating_points))) != self.violating_points:
            raise ValueError("violating_points must be sorted and unique.")
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be bool.")
        if self.passed != (not self.violating_points):
            raise ValueError("passed must agree with violating_points.")

    def as_mapping(self) -> dict[str, object]:
        return {
            "coefficient": self.coefficient,
            "compared_points": self.compared_points,
            "max_absolute_error": self.max_absolute_error,
            "mean_absolute_error": self.mean_absolute_error,
            "rms_error": self.rms_error,
            "violating_points": self.violating_points,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class PolarAcceptanceReport:
    """Deterministic acceptance result for one candidate polar."""

    reference_provider: ProviderIdentity
    candidate_provider: ProviderIdentity
    point_count: int
    reference_usable_points: int
    compared_points: int
    usable_match_count: int
    coverage: float
    usable_match_passed: bool
    metrics: tuple[PolarCoefficientMetrics, ...]
    criteria: PolarAcceptanceCriteria
    passed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.reference_provider, ProviderIdentity):
            raise TypeError("reference_provider must be a ProviderIdentity.")
        if not isinstance(self.candidate_provider, ProviderIdentity):
            raise TypeError("candidate_provider must be a ProviderIdentity.")
        for name in (
            "point_count",
            "reference_usable_points",
            "compared_points",
            "usable_match_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer.")
        if self.point_count < 1 or self.reference_usable_points < 1:
            raise ValueError("Acceptance requires at least one reference usable point.")
        if self.compared_points > self.reference_usable_points:
            raise ValueError("compared_points cannot exceed reference_usable_points.")
        if self.usable_match_count > self.point_count:
            raise ValueError("usable_match_count cannot exceed point_count.")
        if not 0.0 <= self.coverage <= 1.0 or not math.isfinite(self.coverage):
            raise ValueError("coverage must be finite and in [0, 1].")
        if tuple(metric.coefficient for metric in self.metrics) != ("cl", "cd", "cm"):
            raise ValueError("metrics must contain cl, cd, and cm in canonical order.")
        if any(
            metric.compared_points != self.compared_points for metric in self.metrics
        ):
            raise ValueError("All metrics must cover the compared point count.")
        for name in ("usable_match_passed", "passed"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be bool.")
        if not isinstance(self.criteria, PolarAcceptanceCriteria):
            raise TypeError("criteria must be a PolarAcceptanceCriteria.")
        expected_coverage = self.compared_points / self.reference_usable_points
        if not math.isclose(
            self.coverage,
            expected_coverage,
            rel_tol=0.0,
            abs_tol=1.0e-15,
        ):
            raise ValueError("coverage must match compared/reference usable points.")
        expected_usable_pass = (
            not self.criteria.require_usable_match
            or self.usable_match_count == self.point_count
        )
        if self.usable_match_passed != expected_usable_pass:
            raise ValueError("usable_match_passed is inconsistent with criteria.")
        expected_pass = (
            expected_usable_pass
            and self.coverage >= self.criteria.minimum_coverage
            and all(metric.passed for metric in self.metrics)
        )
        if self.passed != expected_pass:
            raise ValueError("passed is inconsistent with acceptance outcomes.")

    def as_mapping(self) -> dict[str, object]:
        return {
            "schema_version": POLAR_ACCEPTANCE_SCHEMA_VERSION,
            "reference_provider": self.reference_provider.as_mapping(),
            "candidate_provider": self.candidate_provider.as_mapping(),
            "point_count": self.point_count,
            "reference_usable_points": self.reference_usable_points,
            "compared_points": self.compared_points,
            "usable_match_count": self.usable_match_count,
            "coverage": self.coverage,
            "usable_match_passed": self.usable_match_passed,
            "metrics": tuple(metric.as_mapping() for metric in self.metrics),
            "criteria": self.criteria.as_mapping(),
            "passed": self.passed,
        }


@dataclass(frozen=True)
class PolarGoldenFixture:
    """Named, immutable golden result loaded from a versioned JSON fixture."""

    name: str
    reference: PolarGenerationResult

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Golden fixture name must not be empty.")
        if not isinstance(self.reference, PolarGenerationResult):
            raise TypeError("reference must be a PolarGenerationResult.")
        if not any(point.usable for point in self.reference.points):
            raise ValueError("Golden fixture must contain at least one usable point.")


@dataclass(frozen=True)
class PolarBenchmarkEntry:
    """One provider/fixture benchmark outcome, including non-gating timing."""

    fixture_name: str
    provider: ProviderIdentity
    wall_elapsed_s: float
    provider_elapsed_s: float | None
    acceptance: PolarAcceptanceReport | None = None
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not self.fixture_name:
            raise ValueError("fixture_name must not be empty.")
        if not isinstance(self.provider, ProviderIdentity):
            raise TypeError("provider must be a ProviderIdentity.")
        _non_negative_finite("wall_elapsed_s", self.wall_elapsed_s)
        if self.provider_elapsed_s is not None:
            _non_negative_finite("provider_elapsed_s", self.provider_elapsed_s)
        has_acceptance = self.acceptance is not None
        has_error = self.error_type is not None or self.error_message is not None
        if has_acceptance == has_error:
            raise ValueError("Benchmark entry must contain acceptance or an error.")
        if has_acceptance and self.provider_elapsed_s is None:
            raise ValueError("Successful benchmark entries require provider elapsed time.")
        if has_error and self.provider_elapsed_s is not None:
            raise ValueError("Failed benchmark entries cannot report provider elapsed time.")
        error_values = (self.error_type, self.error_message)
        if has_error and not all(
            isinstance(value, str) and value for value in error_values
        ):
            raise ValueError("Benchmark errors require non-empty type and message.")
        if has_acceptance and self.acceptance.candidate_provider != self.provider:
            raise ValueError("Acceptance candidate must match benchmark provider.")

    @property
    def passed(self) -> bool:
        return self.acceptance is not None and self.acceptance.passed

    def as_mapping(self) -> dict[str, object]:
        return {
            "fixture_name": self.fixture_name,
            "provider": self.provider.as_mapping(),
            "wall_elapsed_s": self.wall_elapsed_s,
            "provider_elapsed_s": self.provider_elapsed_s,
            "acceptance": (
                self.acceptance.as_mapping() if self.acceptance is not None else None
            ),
            "error_type": self.error_type,
            "error_message": self.error_message,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class PolarBenchmarkProviderSummary:
    """Aggregate pass/fail and timing telemetry for one provider."""

    provider: ProviderIdentity
    fixture_count: int
    passed_count: int
    failed_count: int
    total_wall_elapsed_s: float
    mean_wall_elapsed_s: float
    max_wall_elapsed_s: float

    def __post_init__(self) -> None:
        if not isinstance(self.provider, ProviderIdentity):
            raise TypeError("provider must be a ProviderIdentity.")
        for name in ("fixture_count", "passed_count", "failed_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer.")
        if self.fixture_count < 1:
            raise ValueError("fixture_count must be positive.")
        if self.passed_count + self.failed_count != self.fixture_count:
            raise ValueError("Provider summary counts must cover every fixture.")
        for name in (
            "total_wall_elapsed_s",
            "mean_wall_elapsed_s",
            "max_wall_elapsed_s",
        ):
            _non_negative_finite(name, getattr(self, name))

    def as_mapping(self) -> dict[str, object]:
        return {
            "provider": self.provider.as_mapping(),
            "fixture_count": self.fixture_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "total_wall_elapsed_s": self.total_wall_elapsed_s,
            "mean_wall_elapsed_s": self.mean_wall_elapsed_s,
            "max_wall_elapsed_s": self.max_wall_elapsed_s,
        }


@dataclass(frozen=True)
class PolarBenchmarkReport:
    """Complete cross-provider benchmark matrix."""

    entries: tuple[PolarBenchmarkEntry, ...]
    criteria: PolarAcceptanceCriteria

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValueError("Benchmark report requires at least one entry.")
        if not isinstance(self.criteria, PolarAcceptanceCriteria):
            raise TypeError("criteria must be a PolarAcceptanceCriteria.")
        keys = tuple((entry.fixture_name, entry.provider) for entry in self.entries)
        if len(set(keys)) != len(keys):
            raise ValueError(
                "Benchmark entries must be unique by fixture and provider."
            )
        providers = {entry.provider for entry in self.entries}
        fixtures = {entry.fixture_name for entry in self.entries}
        if len(self.entries) != len(providers) * len(fixtures):
            raise ValueError(
                "Benchmark entries must form a complete provider/fixture matrix."
            )
        if any(
            entry.acceptance is not None
            and entry.acceptance.criteria != self.criteria
            for entry in self.entries
        ):
            raise ValueError("Benchmark entry criteria must match report criteria.")

    @property
    def passed(self) -> bool:
        return all(entry.passed for entry in self.entries)

    @property
    def provider_count(self) -> int:
        return len({entry.provider for entry in self.entries})

    @property
    def fixture_count(self) -> int:
        return len({entry.fixture_name for entry in self.entries})

    @property
    def provider_summaries(self) -> tuple[PolarBenchmarkProviderSummary, ...]:
        """Return summaries in first-seen provider order."""
        ordered_providers = tuple(
            dict.fromkeys(entry.provider for entry in self.entries)
        )
        summaries: list[PolarBenchmarkProviderSummary] = []
        for provider in ordered_providers:
            entries = tuple(
                entry for entry in self.entries if entry.provider == provider
            )
            elapsed = tuple(entry.wall_elapsed_s for entry in entries)
            passed_count = sum(entry.passed for entry in entries)
            summaries.append(
                PolarBenchmarkProviderSummary(
                    provider=provider,
                    fixture_count=len(entries),
                    passed_count=passed_count,
                    failed_count=len(entries) - passed_count,
                    total_wall_elapsed_s=sum(elapsed),
                    mean_wall_elapsed_s=sum(elapsed) / len(elapsed),
                    max_wall_elapsed_s=max(elapsed),
                )
            )
        return tuple(summaries)

    def as_mapping(self) -> dict[str, object]:
        return {
            "schema_version": POLAR_ACCEPTANCE_SCHEMA_VERSION,
            "provider_count": self.provider_count,
            "fixture_count": self.fixture_count,
            "criteria": self.criteria.as_mapping(),
            "provider_summaries": tuple(
                summary.as_mapping() for summary in self.provider_summaries
            ),
            "entries": tuple(entry.as_mapping() for entry in self.entries),
            "passed": self.passed,
        }


def compare_polar_results(
    reference: PolarGenerationResult,
    candidate: PolarGenerationResult,
    *,
    criteria: PolarAcceptanceCriteria | None = None,
) -> PolarAcceptanceReport:
    """Compare one candidate against a request-identical golden result."""
    if not isinstance(reference, PolarGenerationResult):
        raise TypeError("reference must be a PolarGenerationResult.")
    if not isinstance(candidate, PolarGenerationResult):
        raise TypeError("candidate must be a PolarGenerationResult.")
    if reference.request != candidate.request:
        raise ValueError("Reference and candidate requests must match exactly.")
    policy = criteria or PolarAcceptanceCriteria()
    if not isinstance(policy, PolarAcceptanceCriteria):
        raise TypeError("criteria must be a PolarAcceptanceCriteria or None.")

    reference_usable = sum(point.usable for point in reference.points)
    if reference_usable == 0:
        raise ValueError("Reference result must contain at least one usable point.")
    comparable = tuple(
        (index, expected, actual)
        for index, (expected, actual) in enumerate(
            zip(reference.points, candidate.points)
        )
        if expected.usable and actual.usable
    )
    if not comparable:
        raise ValueError("Candidate has no usable points comparable to the reference.")

    usable_match_count = sum(
        expected.usable == actual.usable
        for expected, actual in zip(reference.points, candidate.points)
    )
    usable_match_passed = (
        not policy.require_usable_match or usable_match_count == len(reference.points)
    )
    coverage = len(comparable) / reference_usable
    coverage_passed = coverage >= policy.minimum_coverage
    metrics = tuple(
        _coefficient_metrics(name, comparable, getattr(policy, name))
        for name in ("cl", "cd", "cm")
    )
    passed = usable_match_passed and coverage_passed and all(
        metric.passed for metric in metrics
    )
    return PolarAcceptanceReport(
        reference_provider=reference.provider,
        candidate_provider=candidate.provider,
        point_count=len(reference.points),
        reference_usable_points=reference_usable,
        compared_points=len(comparable),
        usable_match_count=usable_match_count,
        coverage=coverage,
        usable_match_passed=usable_match_passed,
        metrics=metrics,
        criteria=policy,
        passed=passed,
    )


def run_polar_provider_benchmark(
    providers: Sequence[PolarProvider],
    fixtures: Sequence[PolarGoldenFixture],
    *,
    criteria: PolarAcceptanceCriteria | None = None,
) -> PolarBenchmarkReport:
    """Run every provider against every golden fixture without timing gates."""
    if not providers:
        raise ValueError("providers must not be empty.")
    if not fixtures:
        raise ValueError("fixtures must not be empty.")
    policy = criteria or PolarAcceptanceCriteria()
    if not isinstance(policy, PolarAcceptanceCriteria):
        raise TypeError("criteria must be a PolarAcceptanceCriteria or None.")
    identities: list[ProviderIdentity] = []
    for provider in providers:
        identity = provider.identity
        if not isinstance(identity, ProviderIdentity):
            raise TypeError("Every provider identity must be a ProviderIdentity.")
        identities.append(identity)
    if len(set(identities)) != len(identities):
        raise ValueError("providers must have unique identities.")
    if not all(isinstance(fixture, PolarGoldenFixture) for fixture in fixtures):
        raise TypeError("fixtures must contain PolarGoldenFixture values.")
    names = tuple(fixture.name for fixture in fixtures)
    if len(set(names)) != len(names):
        raise ValueError("fixtures must have unique names.")

    entries: list[PolarBenchmarkEntry] = []
    for fixture in fixtures:
        for provider, identity in zip(providers, identities):
            started = time.perf_counter()
            try:
                result = generate_polar(provider, fixture.reference.request)
                acceptance = compare_polar_results(
                    fixture.reference,
                    result,
                    criteria=policy,
                )
            except PolarProviderError as error:
                entries.append(
                    PolarBenchmarkEntry(
                        fixture.name,
                        identity,
                        time.perf_counter() - started,
                        None,
                        error_type=type(error).__name__,
                        error_message=_safe_error_message(error),
                    )
                )
            except Exception as error:
                entries.append(
                    PolarBenchmarkEntry(
                        fixture.name,
                        identity,
                        time.perf_counter() - started,
                        None,
                        error_type=f"unexpected:{type(error).__name__}",
                        error_message=_safe_error_message(error),
                    )
                )
            else:
                entries.append(
                    PolarBenchmarkEntry(
                        fixture.name,
                        identity,
                        time.perf_counter() - started,
                        result.elapsed_s,
                        acceptance=acceptance,
                    )
                )
    return PolarBenchmarkReport(tuple(entries), policy)


def load_polar_golden_fixture(path: str | Path) -> PolarGoldenFixture:
    """Load and strictly validate a versioned golden-fixture JSON document."""
    fixture_path = Path(path)
    try:
        document = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read polar golden fixture {fixture_path}.") from error
    mapping = _mapping(document, "fixture")
    _require_fields(
        mapping,
        {"schema_version", "name", "request", "reference"},
        "fixture",
    )
    if mapping["schema_version"] != POLAR_ACCEPTANCE_SCHEMA_VERSION:
        raise ValueError("Unsupported polar golden fixture schema version.")
    request = _request_from_mapping(_mapping(mapping["request"], "request"))
    reference_mapping = _mapping(mapping["reference"], "reference")
    _require_fields(reference_mapping, {"provider", "points"}, "reference")
    provider = _provider_from_mapping(
        _mapping(reference_mapping["provider"], "reference.provider")
    )
    points_value = reference_mapping["points"]
    if not isinstance(points_value, list) or not points_value:
        raise ValueError("reference.points must be a non-empty list.")
    points = tuple(
        _point_from_mapping(_mapping(value, f"reference.points[{index}]"))
        for index, value in enumerate(points_value)
    )
    reference = PolarGenerationResult(request, provider, points, 0.0)
    return PolarGoldenFixture(_string(mapping["name"], "name"), reference)


def _coefficient_metrics(
    coefficient: str,
    comparable: Sequence[tuple[int, PolarPointResult, PolarPointResult]],
    tolerance: PolarErrorTolerance,
) -> PolarCoefficientMetrics:
    errors: list[float] = []
    violations: list[int] = []
    for comparison_index, (_, reference, candidate) in enumerate(comparable):
        expected = getattr(reference, coefficient)
        actual = getattr(candidate, coefficient)
        assert expected is not None and actual is not None
        error = abs(actual - expected)
        errors.append(error)
        limit = tolerance.limit_for(expected)
        if error > limit and not math.isclose(
            error,
            limit,
            rel_tol=1.0e-12,
            abs_tol=1.0e-15,
        ):
            violations.append(comparison_index)
    return PolarCoefficientMetrics(
        coefficient=coefficient,
        compared_points=len(errors),
        max_absolute_error=max(errors),
        mean_absolute_error=sum(errors) / len(errors),
        rms_error=math.sqrt(sum(error * error for error in errors) / len(errors)),
        violating_points=tuple(violations),
        passed=not violations,
    )


def _safe_error_message(error: Exception) -> str:
    try:
        message = str(error)
    except Exception:
        message = "error message unavailable"
    normalized = " ".join(message.split()) or "error message unavailable"
    return normalized[:512]


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object with string keys.")
    return MappingProxyType(value)


def _require_fields(value: Mapping[str, Any], expected: set[str], name: str) -> None:
    fields = set(value)
    if fields != expected:
        missing = sorted(expected - fields)
        extra = sorted(fields - expected)
        raise ValueError(f"{name} fields mismatch; missing={missing}, extra={extra}.")


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string.")
    return value


def _provider_from_mapping(value: Mapping[str, Any]) -> ProviderIdentity:
    fields = {"name", "adapter_version", "backend_name", "backend_version"}
    _require_fields(value, fields, "reference.provider")
    return ProviderIdentity(**{name: _string(value[name], name) for name in fields})


def _request_from_mapping(value: Mapping[str, Any]) -> PolarGenerationRequest:
    fields = {
        "airfoil",
        "alpha_rad",
        "reynolds",
        "mach",
        "n_crit",
        "xtr_upper",
        "xtr_lower",
        "max_iterations",
        "timeout_s",
        "scenario_id",
        "options",
    }
    _require_fields(value, fields, "request")
    airfoil_value = _mapping(value["airfoil"], "request.airfoil")
    _require_fields(airfoil_value, {"id", "source", "coordinates"}, "request.airfoil")
    coordinates_value = airfoil_value["coordinates"]
    if not isinstance(coordinates_value, list):
        raise ValueError("request.airfoil.coordinates must be a list.")
    coordinates: list[tuple[float, float]] = []
    for index, point in enumerate(coordinates_value):
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError(f"request.airfoil.coordinates[{index}] must be [x, y].")
        coordinates.append((point[0], point[1]))
    alpha_value = value["alpha_rad"]
    if not isinstance(alpha_value, list):
        raise ValueError("request.alpha_rad must be a list.")
    options = value["options"]
    if not isinstance(options, dict):
        raise ValueError("request.options must be an object.")
    return PolarGenerationRequest(
        airfoil=AirfoilDefinition(
            id=_string(airfoil_value["id"], "request.airfoil.id"),
            source=_string(airfoil_value["source"], "request.airfoil.source"),
            coordinates=tuple(coordinates),
        ),
        alpha_rad=tuple(alpha_value),
        reynolds=value["reynolds"],
        mach=value["mach"],
        n_crit=value["n_crit"],
        xtr_upper=value["xtr_upper"],
        xtr_lower=value["xtr_lower"],
        max_iterations=value["max_iterations"],
        timeout_s=value["timeout_s"],
        scenario_id=_string(value["scenario_id"], "request.scenario_id"),
        options=options,
    )


def _point_from_mapping(value: Mapping[str, Any]) -> PolarPointResult:
    fields = {
        "alpha_rad",
        "status",
        "cl",
        "cd",
        "cm",
        "confidence",
        "iterations",
        "message",
    }
    _require_fields(value, fields, "reference point")
    return PolarPointResult(
        alpha_rad=value["alpha_rad"],
        status=value["status"],
        cl=value["cl"],
        cd=value["cd"],
        cm=value["cm"],
        confidence=value["confidence"],
        iterations=value["iterations"],
        message=value["message"],
    )
