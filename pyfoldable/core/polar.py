"""Polar table loading and explicit multidimensional interpolation."""

from __future__ import annotations

import csv
import math
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from .models import PolarTable


PolarBoundsPolicy = Literal["error", "clamp"]


class PolarInterpolationError(ValueError):
    """Raised when a polar family cannot answer a requested query safely."""


@dataclass(frozen=True)
class PolarQueryResult:
    """Interpolated coefficients with query and provenance information."""

    airfoil_id: str
    scenario_id: str
    alpha_rad: float
    reynolds: float
    mach: float
    cl: float
    cd: float
    cm: float
    sources: tuple[str, ...]
    interpolated_dimensions: tuple[str, ...] = ()
    clamped_dimensions: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Coefficients:
    cl: float
    cd: float
    cm: float
    sources: tuple[str, ...]
    interpolated: frozenset[str] = frozenset()
    clamped: frozenset[str] = frozenset()


def _validate_query(value: float, dimension: str, *, positive: bool = False) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise PolarInterpolationError(f"{dimension} must be finite.")
    if positive and numeric <= 0.0:
        raise PolarInterpolationError(f"{dimension} must be greater than zero.")
    if dimension == "mach" and numeric < 0.0:
        raise PolarInterpolationError("mach must be non-negative.")
    return numeric


def _bracket(
    value: float,
    grid: Sequence[float],
    *,
    dimension: str,
    policy: PolarBoundsPolicy,
    logarithmic: bool = False,
) -> tuple[float, float, float, bool]:
    if not grid:
        raise PolarInterpolationError(f"No {dimension} values are available.")
    minimum, maximum = grid[0], grid[-1]
    if value < minimum or value > maximum:
        if policy == "error":
            raise PolarInterpolationError(
                f"Requested {dimension} {value:g} is outside [{minimum:g}, {maximum:g}]."
            )
        clamped_value = min(max(value, minimum), maximum)
        return clamped_value, clamped_value, 0.0, True

    index = bisect_right(grid, value)
    if index > 0 and math.isclose(value, grid[index - 1], rel_tol=1.0e-12, abs_tol=1.0e-14):
        exact = grid[index - 1]
        return exact, exact, 0.0, False
    if index == 0 or index >= len(grid):
        exact = minimum if index == 0 else maximum
        return exact, exact, 0.0, False

    lower, upper = grid[index - 1], grid[index]
    if logarithmic:
        weight = (math.log(value) - math.log(lower)) / (math.log(upper) - math.log(lower))
    else:
        weight = (value - lower) / (upper - lower)
    return lower, upper, weight, False


def _blend(
    lower: _Coefficients,
    upper: _Coefficients,
    weight: float,
    dimension: str,
) -> _Coefficients:
    if weight <= 0.0:
        return lower
    if weight >= 1.0:
        return upper
    inverse = 1.0 - weight
    return _Coefficients(
        cl=lower.cl * inverse + upper.cl * weight,
        cd=lower.cd * inverse + upper.cd * weight,
        cm=lower.cm * inverse + upper.cm * weight,
        sources=tuple(dict.fromkeys((*lower.sources, *upper.sources))),
        interpolated=lower.interpolated | upper.interpolated | {dimension},
        clamped=lower.clamped | upper.clamped,
    )


def _table_coefficients(
    table: PolarTable,
    alpha_rad: float,
    policy: PolarBoundsPolicy,
) -> _Coefficients:
    lower_alpha, upper_alpha, weight, clamped = _bracket(
        alpha_rad,
        table.alpha_rad,
        dimension="alpha_rad",
        policy=policy,
    )
    lower_index = table.alpha_rad.index(lower_alpha)
    upper_index = table.alpha_rad.index(upper_alpha)
    lower = _Coefficients(
        table.cl[lower_index],
        table.cd[lower_index],
        table.cm[lower_index],
        (table.source,),
        clamped=frozenset({"alpha_rad"}) if clamped else frozenset(),
    )
    upper = _Coefficients(
        table.cl[upper_index],
        table.cd[upper_index],
        table.cm[upper_index],
        (table.source,),
        clamped=frozenset({"alpha_rad"}) if clamped else frozenset(),
    )
    return _blend(lower, upper, weight, "alpha_rad")


@dataclass(frozen=True)
class PolarFamily:
    """A set of compatible tables queryable across angle, Reynolds, and Mach."""

    tables: tuple[PolarTable, ...]

    def __post_init__(self) -> None:
        if not self.tables:
            raise ValueError("PolarFamily requires at least one table.")
        airfoil_ids = {table.airfoil_id for table in self.tables}
        scenarios = {table.scenario_id for table in self.tables}
        if len(airfoil_ids) != 1:
            raise ValueError("PolarFamily tables must use the same airfoil_id.")
        if len(scenarios) != 1:
            raise ValueError("PolarFamily tables must use the same scenario_id.")
        operating_points = [(table.mach, table.reynolds) for table in self.tables]
        if len(set(operating_points)) != len(operating_points):
            raise ValueError("PolarFamily cannot contain duplicate Mach/Reynolds tables.")

    @property
    def airfoil_id(self) -> str:
        return self.tables[0].airfoil_id

    @property
    def scenario_id(self) -> str:
        return self.tables[0].scenario_id

    def _at_mach(
        self,
        mach: float,
        alpha_rad: float,
        reynolds: float,
        policy: PolarBoundsPolicy,
    ) -> _Coefficients:
        tables = sorted(
            (table for table in self.tables if table.mach == mach),
            key=lambda table: table.reynolds,
        )
        grid = [table.reynolds for table in tables]
        lower_re, upper_re, weight, clamped = _bracket(
            reynolds,
            grid,
            dimension="reynolds",
            policy=policy,
            logarithmic=True,
        )
        by_reynolds = {table.reynolds: table for table in tables}
        lower = _table_coefficients(by_reynolds[lower_re], alpha_rad, policy)
        upper = _table_coefficients(by_reynolds[upper_re], alpha_rad, policy)
        result = _blend(lower, upper, weight, "reynolds")
        if clamped:
            result = _Coefficients(
                result.cl,
                result.cd,
                result.cm,
                result.sources,
                result.interpolated,
                result.clamped | {"reynolds"},
            )
        return result

    def query(
        self,
        *,
        alpha_rad: float,
        reynolds: float,
        mach: float,
        bounds: PolarBoundsPolicy = "error",
    ) -> PolarQueryResult:
        """Interpolate coefficients with explicit boundary behavior.

        Angle of attack and Mach use linear interpolation. Reynolds number uses
        log-linear interpolation. Extrapolation is deliberately unsupported.
        """
        if bounds not in {"error", "clamp"}:
            raise PolarInterpolationError(f"Unsupported bounds policy {bounds!r}.")
        alpha = _validate_query(alpha_rad, "alpha_rad")
        re_value = _validate_query(reynolds, "reynolds", positive=True)
        mach_value = _validate_query(mach, "mach")

        mach_grid = sorted({table.mach for table in self.tables})
        lower_mach, upper_mach, weight, clamped = _bracket(
            mach_value,
            mach_grid,
            dimension="mach",
            policy=bounds,
        )
        lower = self._at_mach(lower_mach, alpha, re_value, bounds)
        upper = self._at_mach(upper_mach, alpha, re_value, bounds)
        result = _blend(lower, upper, weight, "mach")
        if clamped:
            result = _Coefficients(
                result.cl,
                result.cd,
                result.cm,
                result.sources,
                result.interpolated,
                result.clamped | {"mach"},
            )
        return PolarQueryResult(
            airfoil_id=self.airfoil_id,
            scenario_id=self.scenario_id,
            alpha_rad=alpha,
            reynolds=re_value,
            mach=mach_value,
            cl=result.cl,
            cd=result.cd,
            cm=result.cm,
            sources=result.sources,
            interpolated_dimensions=tuple(sorted(result.interpolated)),
            clamped_dimensions=tuple(sorted(result.clamped)),
        )


def load_polar_csv(
    path: str | Path,
    *,
    airfoil_id: str,
    reynolds: float,
    mach: float = 0.0,
    source: str | None = None,
    scenario_id: str = "default",
    metadata: Mapping[str, Any] | None = None,
) -> PolarTable:
    """Load one polar table from CSV with alpha_deg or alpha_rad and cl/cd/cm."""
    polar_path = Path(path)
    try:
        stream = polar_path.open("r", encoding="utf-8-sig", newline="")
    except (OSError, UnicodeError) as exc:
        raise PolarInterpolationError(f"Could not read polar CSV {polar_path}.") from exc
    with stream:
        reader = csv.DictReader(
            line for line in stream if not line.lstrip().startswith("#")
        )
        headers = {
            header.strip().casefold(): header for header in (reader.fieldnames or ())
        }
        angle_key = "alpha_rad" if "alpha_rad" in headers else "alpha_deg"
        required = {angle_key, "cl", "cd", "cm"}
        if not required.issubset(headers):
            raise PolarInterpolationError(
                "Polar CSV requires alpha_deg or alpha_rad plus cl, cd, and cm columns."
            )
        rows: list[tuple[float, float, float, float]] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                alpha = float(row[headers[angle_key]])
                if angle_key == "alpha_deg":
                    alpha = math.radians(alpha)
                values = (
                    alpha,
                    float(row[headers["cl"]]),
                    float(row[headers["cd"]]),
                    float(row[headers["cm"]]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise PolarInterpolationError(
                    f"Polar CSV row {row_number} contains missing or non-numeric data."
                ) from exc
            if not all(math.isfinite(value) for value in values):
                raise PolarInterpolationError(
                    f"Polar CSV row {row_number} contains non-finite data."
                )
            rows.append(values)
    rows.sort(key=lambda row: row[0])
    if not rows:
        raise PolarInterpolationError("Polar CSV contains no data rows.")
    return PolarTable(
        airfoil_id=airfoil_id,
        reynolds=reynolds,
        mach=mach,
        alpha_rad=tuple(row[0] for row in rows),
        cl=tuple(row[1] for row in rows),
        cd=tuple(row[2] for row in rows),
        cm=tuple(row[3] for row in rows),
        source=source or str(polar_path),
        scenario_id=scenario_id,
        metadata=dict(metadata or {}),
    )
