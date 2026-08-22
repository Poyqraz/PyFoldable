"""Deterministic fixed-propeller benchmark contracts for rotor-level BEM results."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from .bem import BEMAnnulusSettings
from .bem_rotor import (
    BEMRotorElementError,
    BEMRotorSettings,
    solve_bem_rotor,
)
from .models import BladeGeometry, BladeStation, OperatingCondition
from .polar import PolarFamily, PolarTable


ROTOR_BENCHMARK_SCHEMA_VERSION = 2
_ROTOR_BENCHMARK_FIXTURE_SCHEMA_VERSION = 1
BenchmarkRegime = Literal["static", "forward"]
PredictionStatus = Literal["success", "unsupported", "error"]


class RotorBenchmarkError(ValueError):
    """Raised when benchmark evidence is incomplete or internally inconsistent."""


def _finite(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RotorBenchmarkError(f"{name} must be numeric and not boolean.")
    if not math.isfinite(value):
        raise RotorBenchmarkError(f"{name} must be finite.")


@dataclass(frozen=True)
class RotorBenchmarkPoint:
    """One measured propeller operating point."""

    id: str
    regime: BenchmarkRegime
    rpm: float
    advance_ratio: float
    thrust_coefficient: float
    power_coefficient: float
    source_id: str
    qualification_eligible: bool = True

    def __post_init__(self) -> None:
        if not self.id or not self.source_id:
            raise RotorBenchmarkError("Benchmark point identity and source are required.")
        if self.regime not in {"static", "forward"}:
            raise RotorBenchmarkError("regime must be 'static' or 'forward'.")
        for name in (
            "rpm",
            "advance_ratio",
            "thrust_coefficient",
            "power_coefficient",
        ):
            _finite(name, getattr(self, name))
        if self.rpm <= 0.0:
            raise RotorBenchmarkError("rpm must be greater than zero.")
        if self.advance_ratio < 0.0:
            raise RotorBenchmarkError("advance_ratio cannot be negative.")
        if self.regime == "static" and self.advance_ratio != 0.0:
            raise RotorBenchmarkError("Static points must have zero advance ratio.")
        if not isinstance(self.qualification_eligible, bool):
            raise RotorBenchmarkError("qualification_eligible must be boolean.")

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "id": self.id,
            "regime": self.regime,
            "rpm": self.rpm,
            "advance_ratio": self.advance_ratio,
            "thrust_coefficient": self.thrust_coefficient,
            "power_coefficient": self.power_coefficient,
            "source_id": self.source_id,
            "qualification_eligible": self.qualification_eligible,
        }


@dataclass(frozen=True)
class RotorBenchmarkFixture:
    """Versioned geometry, environment, and measured reference matrix."""

    id: str
    source_sha256: str
    diameter_m: float
    hub_radius_m: float
    blade_count: int
    geometry: tuple[tuple[float, float, float], ...]
    air_density_kg_m3: float
    dynamic_viscosity_pa_s: float
    temperature_k: float
    pressure_pa: float
    points: tuple[RotorBenchmarkPoint, ...]
    sources: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        if not self.id:
            raise RotorBenchmarkError("Fixture id is required.")
        if len(self.source_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.source_sha256
        ):
            raise RotorBenchmarkError("Fixture source_sha256 must be a SHA-256 digest.")
        for name in (
            "diameter_m",
            "hub_radius_m",
            "air_density_kg_m3",
            "dynamic_viscosity_pa_s",
            "temperature_k",
            "pressure_pa",
        ):
            value = getattr(self, name)
            _finite(name, value)
            if value <= 0.0:
                raise RotorBenchmarkError(f"{name} must be greater than zero.")
        if self.hub_radius_m >= 0.5 * self.diameter_m:
            raise RotorBenchmarkError("hub_radius_m must be smaller than blade radius.")
        if not isinstance(self.blade_count, int) or isinstance(self.blade_count, bool):
            raise RotorBenchmarkError("blade_count must be an integer.")
        if self.blade_count < 1:
            raise RotorBenchmarkError("blade_count must be positive.")
        if len(self.geometry) < 2:
            raise RotorBenchmarkError("At least two radial geometry stations are required.")
        ratios = tuple(row[0] for row in self.geometry)
        if any(not 0.0 < ratio <= 1.0 for ratio in ratios):
            raise RotorBenchmarkError("Geometry r/R values must lie in (0, 1].")
        if any(upper <= lower for lower, upper in zip(ratios, ratios[1:])):
            raise RotorBenchmarkError("Geometry r/R values must be strictly increasing.")
        for ratio, chord_ratio, twist_deg in self.geometry:
            for name, value in (
                ("r_over_R", ratio),
                ("chord_over_R", chord_ratio),
                ("twist_deg", twist_deg),
            ):
                _finite(name, value)
            if chord_ratio <= 0.0:
                raise RotorBenchmarkError("Geometry chord/R must be positive.")
        point_ids = tuple(point.id for point in self.points)
        if not point_ids or len(point_ids) != len(set(point_ids)):
            raise RotorBenchmarkError("Benchmark point ids must be non-empty and unique.")
        eligible_regimes = {
            point.regime for point in self.points if point.qualification_eligible
        }
        if eligible_regimes != {"static", "forward"}:
            raise RotorBenchmarkError(
                "Qualification evidence must contain eligible static and forward points."
            )
        source_ids = {str(source.get("id", "")) for source in self.sources}
        if "" in source_ids or any(point.source_id not in source_ids for point in self.points):
            raise RotorBenchmarkError("Every benchmark point must name a declared source.")

    @property
    def eligible_points(self) -> tuple[RotorBenchmarkPoint, ...]:
        return tuple(point for point in self.points if point.qualification_eligible)

    def blade(self, airfoil_id: str) -> BladeGeometry:
        radius = 0.5 * self.diameter_m
        return BladeGeometry(
            diameter_m=self.diameter_m,
            hub_radius_m=self.hub_radius_m,
            blade_count=self.blade_count,
            stations=tuple(
                BladeStation(
                    r_over_R=ratio,
                    chord_m=chord_ratio * radius,
                    twist_rad=math.radians(twist_deg),
                    airfoil_id=airfoil_id,
                )
                for ratio, chord_ratio, twist_deg in self.geometry
            ),
        )

    def condition(self, point: RotorBenchmarkPoint) -> OperatingCondition:
        rotations_per_second = point.rpm / 60.0
        return OperatingCondition(
            id=point.id,
            angular_speed_rad_s=2.0 * math.pi * rotations_per_second,
            forward_speed_m_s=(
                point.advance_ratio * rotations_per_second * self.diameter_m
            ),
            air_density_kg_m3=self.air_density_kg_m3,
            dynamic_viscosity_pa_s=self.dynamic_viscosity_pa_s,
            temperature_k=self.temperature_k,
            pressure_pa=self.pressure_pa,
        )


@dataclass(frozen=True)
class RotorBenchmarkPrediction:
    """One auditable model outcome, including unsupported-domain failures."""

    point_id: str
    status: PredictionStatus
    thrust_coefficient: float | None = None
    power_coefficient: float | None = None
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not self.point_id or self.status not in {"success", "unsupported", "error"}:
            raise RotorBenchmarkError("Prediction identity/status is invalid.")
        if self.status == "success":
            if self.thrust_coefficient is None or self.power_coefficient is None:
                raise RotorBenchmarkError("Successful predictions require CT and CP.")
            _finite("predicted thrust_coefficient", self.thrust_coefficient)
            _finite("predicted power_coefficient", self.power_coefficient)
            if self.error_type is not None or self.error_message is not None:
                raise RotorBenchmarkError("Successful predictions cannot contain errors.")
        elif (
            self.thrust_coefficient is not None
            or self.power_coefficient is not None
            or not self.error_type
            or not self.error_message
        ):
            raise RotorBenchmarkError("Failed predictions require only typed error evidence.")

    def as_mapping(self) -> Mapping[str, Any]:
        payload: dict[str, Any] = {"point_id": self.point_id, "status": self.status}
        if self.status == "success":
            payload.update(
                thrust_coefficient=self.thrust_coefficient,
                power_coefficient=self.power_coefficient,
            )
        else:
            payload.update(error_type=self.error_type, error_message=self.error_message)
        return payload


@dataclass(frozen=True)
class RotorBenchmarkPolicy:
    """Predeclared screening thresholds; timing is deliberately non-gating."""

    minimum_solution_coverage: float = 0.95
    maximum_ct_wmape: float = 0.15
    maximum_cp_wmape: float = 0.20
    maximum_absolute_ct_normalized_bias: float = 0.10
    maximum_absolute_cp_normalized_bias: float = 0.15
    maximum_radial_terminal_delta: float = 0.005
    require_representative_polar_evidence: bool = True

    def __post_init__(self) -> None:
        for name in (
            "minimum_solution_coverage",
            "maximum_ct_wmape",
            "maximum_cp_wmape",
            "maximum_absolute_ct_normalized_bias",
            "maximum_absolute_cp_normalized_bias",
            "maximum_radial_terminal_delta",
        ):
            value = getattr(self, name)
            _finite(name, value)
            if value < 0.0:
                raise RotorBenchmarkError(f"{name} cannot be negative.")
        if self.minimum_solution_coverage > 1.0:
            raise RotorBenchmarkError("minimum_solution_coverage cannot exceed one.")
        if not isinstance(self.require_representative_polar_evidence, bool):
            raise RotorBenchmarkError(
                "require_representative_polar_evidence must be boolean."
            )

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "minimum_solution_coverage": self.minimum_solution_coverage,
            "maximum_ct_wmape": self.maximum_ct_wmape,
            "maximum_cp_wmape": self.maximum_cp_wmape,
            "maximum_absolute_ct_normalized_bias": (
                self.maximum_absolute_ct_normalized_bias
            ),
            "maximum_absolute_cp_normalized_bias": (
                self.maximum_absolute_cp_normalized_bias
            ),
            "maximum_radial_terminal_delta": self.maximum_radial_terminal_delta,
            "require_representative_polar_evidence": (
                self.require_representative_polar_evidence
            ),
        }


def build_rotor_benchmark_proxy_polar_family(
    *,
    zero_lift_deg: float = -4.0,
    lift_limit: float = 1.2,
    drag_offset: float = 0.025,
    drag_quadratic: float = 0.025,
) -> PolarFamily:
    """Build the declared, deliberately non-qualifying APC airfoil proxy.

    APC describes its dominant airfoil basis as similar to NACA 4412 and Clark-Y,
    while also stating that shapes can vary along the span. This analytic family is
    therefore useful for model screening and sensitivity only; it is not an exact
    representation of the tested blade.
    """
    alpha_rad = tuple(math.radians(value) for value in range(-90, 91, 2))
    lift = tuple(
        max(
            -lift_limit,
            min(
                lift_limit,
                2.0 * math.pi * (alpha - math.radians(zero_lift_deg)),
            ),
        )
        for alpha in alpha_rad
    )
    drag = tuple(
        drag_offset + drag_quadratic * coefficient**2 for coefficient in lift
    )
    contract = (
        f"analytic-proxy:a0={zero_lift_deg:g}:clmax={lift_limit:g}:"
        f"cd0={drag_offset:g}:k={drag_quadratic:g}"
    )
    return PolarFamily(
        tuple(
            PolarTable(
                airfoil_id="APC-SF-4412-CLARKY-PROXY",
                scenario_id="pr06c-analytic-proxy-v1",
                reynolds=reynolds,
                mach=mach,
                alpha_rad=alpha_rad,
                cl=lift,
                cd=drag,
                cm=tuple(0.0 for _ in alpha_rad),
                source=contract,
                metadata={
                    "evidence_class": "analytic_proxy",
                    "representative_polar_evidence": False,
                    "basis_url": (
                        "https://www.apcprop.com/technical-information/engineering/"
                    ),
                },
            )
            for mach in (0.0, 0.4)
            for reynolds in (1.0e3, 5.0e5)
        )
    )


def load_rotor_benchmark_fixture(path: str | Path) -> RotorBenchmarkFixture:
    """Load a strict schema-v1 JSON fixture and bind it to its raw file digest."""
    source = Path(path)
    raw = source.read_bytes()
    payload = json.loads(raw)
    if payload.get("schema_version") != _ROTOR_BENCHMARK_FIXTURE_SCHEMA_VERSION or (
        isinstance(payload.get("schema_version"), bool)
    ):
        raise RotorBenchmarkError("Unsupported rotor benchmark fixture schema.")
    geometry = payload["geometry"]
    environment = payload["environment"]
    if not isinstance(geometry.get("blade_count"), int) or isinstance(
        geometry.get("blade_count"), bool
    ):
        raise RotorBenchmarkError("Fixture blade_count must be an integer.")
    if any(
        not isinstance(row.get("qualification_eligible"), bool)
        for row in payload["points"]
    ):
        raise RotorBenchmarkError(
            "Fixture qualification_eligible values must be JSON booleans."
        )
    return RotorBenchmarkFixture(
        id=str(payload["id"]),
        source_sha256=hashlib.sha256(raw).hexdigest(),
        diameter_m=float(geometry["diameter_m"]),
        hub_radius_m=float(geometry["hub_radius_m"]),
        blade_count=geometry["blade_count"],
        geometry=tuple(
            (
                float(row["r_over_R"]),
                float(row["chord_over_R"]),
                float(row["twist_deg"]),
            )
            for row in geometry["stations"]
        ),
        air_density_kg_m3=float(environment["air_density_kg_m3"]),
        dynamic_viscosity_pa_s=float(environment["dynamic_viscosity_pa_s"]),
        temperature_k=float(environment["temperature_k"]),
        pressure_pa=float(environment["pressure_pa"]),
        points=tuple(
            RotorBenchmarkPoint(
                id=str(row["id"]),
                regime=str(row["regime"]),
                rpm=float(row["rpm"]),
                advance_ratio=float(row["advance_ratio"]),
                thrust_coefficient=float(row["thrust_coefficient"]),
                power_coefficient=float(row["power_coefficient"]),
                source_id=str(row["source_id"]),
                qualification_eligible=row["qualification_eligible"],
            )
            for row in payload["points"]
        ),
        sources=tuple(dict(row) for row in payload["sources"]),
    )


def run_rotor_benchmark_cases(
    fixture: RotorBenchmarkFixture,
    polar_family: PolarFamily,
    *,
    settings: BEMRotorSettings | None = None,
) -> tuple[RotorBenchmarkPrediction, ...]:
    """Run every eligible point while preserving unsupported-domain evidence."""
    controls = BEMRotorSettings() if settings is None else settings
    blade = fixture.blade(polar_family.airfoil_id)
    predictions: list[RotorBenchmarkPrediction] = []
    for point in fixture.eligible_points:
        try:
            result = solve_bem_rotor(
                blade,
                fixture.condition(point),
                {polar_family.airfoil_id: polar_family},
                bounds="error",
                settings=controls,
            )
        except BEMRotorElementError as exc:
            predictions.append(
                RotorBenchmarkPrediction(
                    point_id=point.id,
                    status="unsupported",
                    error_type=(
                        type(exc.__cause__).__name__
                        if exc.__cause__
                        else type(exc).__name__
                    ),
                    error_message=str(exc),
                )
            )
        except Exception as exc:  # benchmark evidence must retain ordinary failures
            predictions.append(
                RotorBenchmarkPrediction(
                    point_id=point.id,
                    status="error",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )
        else:
            predictions.append(
                RotorBenchmarkPrediction(
                    point_id=point.id,
                    status="success",
                    thrust_coefficient=result.thrust_coefficient,
                    power_coefficient=result.power_coefficient,
                )
            )
    return tuple(predictions)


def _coefficient_metrics(
    references: Sequence[float], predictions: Sequence[float]
) -> Mapping[str, float]:
    if len(references) != len(predictions) or not references:
        raise RotorBenchmarkError("Metrics require paired, non-empty values.")
    scale = math.fsum(abs(value) for value in references) / len(references)
    if scale <= 0.0:
        raise RotorBenchmarkError("Aggregate reference scale must be positive.")
    errors = tuple(
        predicted - reference
        for reference, predicted in zip(references, predictions)
    )
    mae = math.fsum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(math.fsum(error * error for error in errors) / len(errors))
    bias = math.fsum(errors) / len(errors)
    return {
        "mean_reference": math.fsum(references) / len(references),
        "mean_prediction": math.fsum(predictions) / len(predictions),
        "mae": mae,
        "rmse": rmse,
        "wmape": math.fsum(abs(error) for error in errors)
        / math.fsum(abs(value) for value in references),
        "normalized_rmse": rmse / scale,
        "normalized_bias": bias / scale,
        "maximum_absolute_error": max(abs(error) for error in errors),
    }


def evaluate_rotor_benchmark_variant(
    fixture: RotorBenchmarkFixture,
    predictions: Sequence[RotorBenchmarkPrediction],
    policy: RotorBenchmarkPolicy,
    *,
    variant_id: str,
    representative_polar_evidence: bool,
    radial_terminal_delta: float,
    settings: BEMRotorSettings,
    polar_contract: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Evaluate coverage, coefficient error, convergence, and evidence gates."""
    if not variant_id:
        raise RotorBenchmarkError("variant_id is required.")
    if not isinstance(representative_polar_evidence, bool):
        raise RotorBenchmarkError("representative_polar_evidence must be boolean.")
    if not isinstance(settings, BEMRotorSettings):
        raise RotorBenchmarkError("settings must be a BEMRotorSettings instance.")
    _finite("radial_terminal_delta", radial_terminal_delta)
    if radial_terminal_delta < 0.0:
        raise RotorBenchmarkError("radial_terminal_delta cannot be negative.")
    eligible = fixture.eligible_points
    point_ids = tuple(point.id for point in eligible)
    by_id = {prediction.point_id: prediction for prediction in predictions}
    if len(by_id) != len(predictions) or set(by_id) != set(point_ids):
        raise RotorBenchmarkError("Predictions must cover each eligible point exactly once.")
    successful = tuple(
        by_id[point.id]
        for point in eligible
        if by_id[point.id].status == "success"
    )
    coverage = len(successful) / len(eligible)
    successful_points = tuple(
        point for point in eligible if by_id[point.id].status == "success"
    )
    ct_metrics = (
        _coefficient_metrics(
            tuple(point.thrust_coefficient for point in successful_points),
            tuple(float(prediction.thrust_coefficient) for prediction in successful),
        )
        if successful
        else None
    )
    cp_metrics = (
        _coefficient_metrics(
            tuple(point.power_coefficient for point in successful_points),
            tuple(float(prediction.power_coefficient) for prediction in successful),
        )
        if successful
        else None
    )
    regime_metrics: dict[str, Mapping[str, Any]] = {}
    for regime in ("static", "forward"):
        regime_points = tuple(point for point in eligible if point.regime == regime)
        regime_successes = tuple(
            point for point in regime_points if by_id[point.id].status == "success"
        )
        regime_metrics[regime] = {
            "point_count": len(regime_points),
            "successful_point_count": len(regime_successes),
            "solution_coverage": len(regime_successes) / len(regime_points),
            "ct_metrics": (
                _coefficient_metrics(
                    tuple(point.thrust_coefficient for point in regime_successes),
                    tuple(
                        float(by_id[point.id].thrust_coefficient)
                        for point in regime_successes
                    ),
                )
                if regime_successes
                else None
            ),
            "cp_metrics": (
                _coefficient_metrics(
                    tuple(point.power_coefficient for point in regime_successes),
                    tuple(
                        float(by_id[point.id].power_coefficient)
                        for point in regime_successes
                    ),
                )
                if regime_successes
                else None
            ),
        }
    gates = {
        "solution_coverage": coverage >= policy.minimum_solution_coverage,
        "ct_wmape": bool(ct_metrics and ct_metrics["wmape"] <= policy.maximum_ct_wmape),
        "cp_wmape": bool(cp_metrics and cp_metrics["wmape"] <= policy.maximum_cp_wmape),
        "ct_bias": bool(
            ct_metrics
            and abs(ct_metrics["normalized_bias"])
            <= policy.maximum_absolute_ct_normalized_bias
        ),
        "cp_bias": bool(
            cp_metrics
            and abs(cp_metrics["normalized_bias"])
            <= policy.maximum_absolute_cp_normalized_bias
        ),
        "radial_convergence": (
            radial_terminal_delta <= policy.maximum_radial_terminal_delta
        ),
        "representative_polar_evidence": (
            representative_polar_evidence
            or not policy.require_representative_polar_evidence
        ),
    }
    gates.update(
        {
            "regime_solution_coverage": all(
                metrics["solution_coverage"] >= policy.minimum_solution_coverage
                for metrics in regime_metrics.values()
            ),
            "regime_ct_wmape": all(
                metrics["ct_metrics"]
                and metrics["ct_metrics"]["wmape"] <= policy.maximum_ct_wmape
                for metrics in regime_metrics.values()
            ),
            "regime_cp_wmape": all(
                metrics["cp_metrics"]
                and metrics["cp_metrics"]["wmape"] <= policy.maximum_cp_wmape
                for metrics in regime_metrics.values()
            ),
            "regime_ct_bias": all(
                metrics["ct_metrics"]
                and abs(metrics["ct_metrics"]["normalized_bias"])
                <= policy.maximum_absolute_ct_normalized_bias
                for metrics in regime_metrics.values()
            ),
            "regime_cp_bias": all(
                metrics["cp_metrics"]
                and abs(metrics["cp_metrics"]["normalized_bias"])
                <= policy.maximum_absolute_cp_normalized_bias
                for metrics in regime_metrics.values()
            ),
        }
    )
    failure_counts: dict[str, int] = {}
    for prediction in predictions:
        if prediction.status != "success":
            key = str(prediction.error_type)
            failure_counts[key] = failure_counts.get(key, 0) + 1
    return {
        "variant_id": variant_id,
        "passed": all(gates.values()),
        "gates": gates,
        "point_count": len(eligible),
        "successful_point_count": len(successful),
        "solution_coverage": coverage,
        "failure_counts": dict(sorted(failure_counts.items())),
        "ct_metrics": ct_metrics,
        "cp_metrics": cp_metrics,
        "regime_metrics": regime_metrics,
        "radial_terminal_delta": radial_terminal_delta,
        "representative_polar_evidence": representative_polar_evidence,
        "settings": dict(settings.as_mapping()),
        "polar_contract": dict(polar_contract),
        "predictions": [dict(prediction.as_mapping()) for prediction in predictions],
    }


def radial_convergence_evidence(
    fixture: RotorBenchmarkFixture,
    polar_family: PolarFamily,
    *,
    point_ids: Sequence[str],
    annulus_counts: Sequence[int] = (20, 40, 80, 160),
    annulus_settings: BEMAnnulusSettings | None = None,
) -> Mapping[str, Any]:
    """Measure terminal 80→160 annulus sensitivity on declared cases."""
    if len(annulus_counts) < 2 or any(
        not isinstance(count, int) or isinstance(count, bool) or count < 2
        for count in annulus_counts
    ):
        raise RotorBenchmarkError("annulus_counts require at least two valid integers.")
    if any(upper <= lower for lower, upper in zip(annulus_counts, annulus_counts[1:])):
        raise RotorBenchmarkError("annulus_counts must be strictly increasing.")
    by_id = {point.id: point for point in fixture.eligible_points}
    if not point_ids or any(point_id not in by_id for point_id in point_ids):
        raise RotorBenchmarkError("Convergence point ids must be eligible benchmark points.")
    local = BEMAnnulusSettings() if annulus_settings is None else annulus_settings
    blade = fixture.blade(polar_family.airfoil_id)
    cases: list[Mapping[str, Any]] = []
    terminal_deltas: list[float] = []
    for point_id in point_ids:
        point = by_id[point_id]
        results: list[Mapping[str, Any]] = []
        for count in annulus_counts:
            result = solve_bem_rotor(
                blade,
                fixture.condition(point),
                {polar_family.airfoil_id: polar_family},
                bounds="error",
                settings=BEMRotorSettings(count, "station_span", local),
            )
            results.append(
                {
                    "annulus_count": count,
                    "thrust_coefficient": result.thrust_coefficient,
                    "power_coefficient": result.power_coefficient,
                }
            )
        lower, upper = results[-2], results[-1]
        ct_delta = abs(upper["thrust_coefficient"] - lower["thrust_coefficient"]) / max(
            abs(upper["thrust_coefficient"]), 1.0e-30
        )
        cp_delta = abs(upper["power_coefficient"] - lower["power_coefficient"]) / max(
            abs(upper["power_coefficient"]), 1.0e-30
        )
        terminal_deltas.extend((ct_delta, cp_delta))
        cases.append(
            {
                "point_id": point_id,
                "results": results,
                "terminal_relative_delta": {
                    "thrust_coefficient": ct_delta,
                    "power_coefficient": cp_delta,
                },
            }
        )
    return {
        "annulus_counts": list(annulus_counts),
        "cases": cases,
        "maximum_terminal_relative_delta": max(terminal_deltas),
    }
