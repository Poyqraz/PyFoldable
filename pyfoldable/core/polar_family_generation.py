"""Provider-backed generation of deterministic polar families."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from .models import PolarTable
from .polar import PolarFamily
from .polar_cache import FilesystemPolarCache
from .polar_health import PolarProviderHealthRegistry
from .polar_orchestration import PolarRetryPolicy, generate_polar_orchestrated
from .providers import (
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarProvider,
    PolarProviderError,
    ProviderIdentity,
)


POLAR_FAMILY_GENERATION_SCHEMA_VERSION = 1


def _plain_value(value: Any) -> Any:
    """Return a recursively JSON-serializable snapshot of contract metadata."""
    if isinstance(value, Mapping):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return tuple(_plain_value(item) for item in value)
    return value


def _increasing_grid(
    name: str,
    values: tuple[float, ...],
    *,
    positive: bool,
) -> tuple[float, ...]:
    try:
        grid = tuple(values)
    except TypeError as error:
        raise TypeError(f"{name} must be an ordered iterable of numbers.") from error
    if not grid:
        raise ValueError(f"{name} must not be empty.")
    normalized: list[float] = []
    for index, value in enumerate(grid):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError(f"{name}[{index}] must be a finite number.")
        numeric = float(value)
        if positive and numeric <= 0.0:
            raise ValueError(f"{name}[{index}] must be greater than zero.")
        if not positive and numeric < 0.0:
            raise ValueError(f"{name}[{index}] must be non-negative.")
        normalized.append(numeric)
    if any(upper <= lower for lower, upper in zip(normalized, normalized[1:])):
        raise ValueError(f"{name} must be strictly increasing and unique.")
    return tuple(normalized)


@dataclass(frozen=True)
class PolarFamilyGenerationPlan:
    """Immutable rectangular Mach/Reynolds grid built from one request template."""

    request_template: PolarGenerationRequest
    reynolds_grid: tuple[float, ...]
    mach_grid: tuple[float, ...] = (0.0,)

    def __post_init__(self) -> None:
        if not isinstance(self.request_template, PolarGenerationRequest):
            raise TypeError("request_template must be a PolarGenerationRequest.")
        reynolds = _increasing_grid(
            "reynolds_grid",
            self.reynolds_grid,
            positive=True,
        )
        mach = _increasing_grid("mach_grid", self.mach_grid, positive=False)
        object.__setattr__(self, "reynolds_grid", reynolds)
        object.__setattr__(self, "mach_grid", mach)
        if self.request_template.reynolds != reynolds[0]:
            raise ValueError(
                "request_template.reynolds must equal the first Reynolds grid value."
            )
        if self.request_template.mach != mach[0]:
            raise ValueError(
                "request_template.mach must equal the first Mach grid value."
            )

    @property
    def cell_count(self) -> int:
        return len(self.mach_grid) * len(self.reynolds_grid)

    @property
    def requests(self) -> tuple[PolarGenerationRequest, ...]:
        """Return the complete grid in Mach-major, Reynolds-minor order."""
        return tuple(
            replace(self.request_template, reynolds=reynolds, mach=mach)
            for mach in self.mach_grid
            for reynolds in self.reynolds_grid
        )

    def as_mapping(self) -> dict[str, object]:
        return {
            "schema_version": POLAR_FAMILY_GENERATION_SCHEMA_VERSION,
            "request_template": {
                "airfoil": {
                    "id": self.request_template.airfoil.id,
                    "source": self.request_template.airfoil.source,
                    "coordinates": self.request_template.airfoil.coordinates,
                },
                "alpha_rad": self.request_template.alpha_rad,
                "reynolds": self.request_template.reynolds,
                "mach": self.request_template.mach,
                "n_crit": self.request_template.n_crit,
                "xtr_upper": self.request_template.xtr_upper,
                "xtr_lower": self.request_template.xtr_lower,
                "max_iterations": self.request_template.max_iterations,
                "timeout_s": self.request_template.timeout_s,
                "scenario_id": self.request_template.scenario_id,
                "options": _plain_value(self.request_template.options),
            },
            "reynolds_grid": self.reynolds_grid,
            "mach_grid": self.mach_grid,
            "cell_count": self.cell_count,
        }


@dataclass(frozen=True)
class PolarFamilyGenerationCell:
    """Successful provider result and table for one rectangular grid cell."""

    position: int
    mach_index: int
    reynolds_index: int
    request: PolarGenerationRequest
    result: PolarGenerationResult
    table: PolarTable

    def __post_init__(self) -> None:
        for name in ("position", "mach_index", "reynolds_index"):
            value = getattr(self, name)
            minimum = 1 if name == "position" else 0
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                qualifier = "positive" if minimum else "non-negative"
                raise ValueError(f"{name} must be a {qualifier} integer.")
        if not isinstance(self.request, PolarGenerationRequest):
            raise TypeError("request must be a PolarGenerationRequest.")
        if not isinstance(self.result, PolarGenerationResult):
            raise TypeError("result must be a PolarGenerationResult.")
        if not isinstance(self.table, PolarTable):
            raise TypeError("table must be a PolarTable.")
        if self.result.request != self.request:
            raise ValueError("Cell result must belong to the cell request.")
        if not self.result.complete:
            raise ValueError("PR-05A family cells require complete provider results.")
        if (
            self.table.airfoil_id != self.request.airfoil.id
            or self.table.scenario_id != self.request.scenario_id
            or self.table.reynolds != self.request.reynolds
            or self.table.mach != self.request.mach
        ):
            raise ValueError("Cell table identity must match the cell request.")
        if self.table != self.result.to_polar_table(require_complete=True):
            raise ValueError("Cell table must be the canonical table for its result.")

    @property
    def cache_status(self) -> str | None:
        cache = self.result.metadata.get("cache")
        if isinstance(cache, Mapping):
            status = cache.get("status")
            return status if isinstance(status, str) else None
        return None

    def as_mapping(self) -> dict[str, object]:
        return {
            "position": self.position,
            "mach_index": self.mach_index,
            "reynolds_index": self.reynolds_index,
            "reynolds": self.request.reynolds,
            "mach": self.request.mach,
            "provider": self.result.provider.as_mapping(),
            "cache_status": self.cache_status,
            "complete": self.result.complete,
            "usable_point_count": sum(self.result.usable_mask),
            "result_elapsed_s": self.result.elapsed_s,
            "orchestration": _plain_value(
                self.result.metadata.get("orchestration")
            ),
        }


@dataclass(frozen=True)
class PolarFamilyGenerationResult:
    """Complete provider-backed family plus ordered cell provenance."""

    plan: PolarFamilyGenerationPlan
    family: PolarFamily
    cells: tuple[PolarFamilyGenerationCell, ...]
    elapsed_s: float

    def __post_init__(self) -> None:
        if not isinstance(self.plan, PolarFamilyGenerationPlan):
            raise TypeError("plan must be a PolarFamilyGenerationPlan.")
        if not isinstance(self.family, PolarFamily):
            raise TypeError("family must be a PolarFamily.")
        if len(self.cells) != self.plan.cell_count:
            raise ValueError("Generation result must contain every planned grid cell.")
        if not all(isinstance(cell, PolarFamilyGenerationCell) for cell in self.cells):
            raise TypeError("cells must contain PolarFamilyGenerationCell values.")
        expected_requests = self.plan.requests
        if tuple(cell.request for cell in self.cells) != expected_requests:
            raise ValueError("Generation cells must preserve canonical plan order.")
        if tuple(cell.position for cell in self.cells) != tuple(
            range(1, self.plan.cell_count + 1)
        ):
            raise ValueError(
                "Generation cell positions must be contiguous and one-based."
            )
        expected_indices = tuple(
            (mach_index, reynolds_index)
            for mach_index in range(len(self.plan.mach_grid))
            for reynolds_index in range(len(self.plan.reynolds_grid))
        )
        if tuple(
            (cell.mach_index, cell.reynolds_index) for cell in self.cells
        ) != expected_indices:
            raise ValueError("Generation cell indices must match canonical grid order.")
        if self.family.tables != tuple(cell.table for cell in self.cells):
            raise ValueError("PolarFamily tables must match generation cells exactly.")
        if (
            isinstance(self.elapsed_s, bool)
            or not isinstance(self.elapsed_s, (int, float))
            or not math.isfinite(float(self.elapsed_s))
            or self.elapsed_s < 0.0
        ):
            raise ValueError("elapsed_s must be a non-negative finite number.")

    @property
    def selected_providers(self) -> tuple[ProviderIdentity, ...]:
        return tuple(dict.fromkeys(cell.result.provider for cell in self.cells))

    def as_mapping(self) -> dict[str, object]:
        return {
            "schema_version": POLAR_FAMILY_GENERATION_SCHEMA_VERSION,
            "plan": self.plan.as_mapping(),
            "elapsed_s": self.elapsed_s,
            "selected_providers": tuple(
                provider.as_mapping() for provider in self.selected_providers
            ),
            "cells": tuple(cell.as_mapping() for cell in self.cells),
            "complete": True,
        }


class PolarFamilyGenerationError(RuntimeError):
    """Fail-fast error retaining completed cells and the failed grid request."""

    def __init__(
        self,
        plan: PolarFamilyGenerationPlan,
        failed_request: PolarGenerationRequest,
        completed_cells: Sequence[PolarFamilyGenerationCell],
        failed_result: PolarGenerationResult | None = None,
    ) -> None:
        if not isinstance(plan, PolarFamilyGenerationPlan):
            raise TypeError("plan must be a PolarFamilyGenerationPlan.")
        if not isinstance(failed_request, PolarGenerationRequest):
            raise TypeError("failed_request must be a PolarGenerationRequest.")
        self.plan = plan
        self.failed_request = failed_request
        self.completed_cells = tuple(completed_cells)
        self.failed_result = failed_result
        if len(self.completed_cells) >= plan.cell_count:
            raise ValueError("completed_cells must leave one failed plan cell.")
        if not all(
            isinstance(cell, PolarFamilyGenerationCell)
            for cell in self.completed_cells
        ):
            raise TypeError("completed_cells must contain generation cells.")
        if failed_result is not None and not isinstance(
            failed_result,
            PolarGenerationResult,
        ):
            raise TypeError("failed_result must be a PolarGenerationResult or None.")
        expected_requests = plan.requests
        if failed_request not in expected_requests:
            raise ValueError("failed_request must belong to the generation plan.")
        if tuple(cell.request for cell in self.completed_cells) != expected_requests[
            : len(self.completed_cells)
        ]:
            raise ValueError("completed_cells must be the canonical successful prefix.")
        if failed_request != expected_requests[len(self.completed_cells)]:
            raise ValueError("failed_request must immediately follow completed_cells.")
        if failed_result is not None and failed_result.request != failed_request:
            raise ValueError("failed_result must belong to failed_request.")
        position = len(self.completed_cells) + 1
        super().__init__(
            "Polar family generation failed at "
            f"cell {position}/{plan.cell_count} "
            f"(Mach={failed_request.mach:g}, Reynolds={failed_request.reynolds:g}); "
            f"{len(self.completed_cells)} cell(s) completed."
        )

    def as_mapping(self) -> dict[str, object]:
        return {
            "schema_version": POLAR_FAMILY_GENERATION_SCHEMA_VERSION,
            "failed_position": len(self.completed_cells) + 1,
            "cell_count": self.plan.cell_count,
            "failed_request": {
                "mach": self.failed_request.mach,
                "reynolds": self.failed_request.reynolds,
            },
            "completed_cells": tuple(
                cell.as_mapping() for cell in self.completed_cells
            ),
            "failed_provider": (
                self.failed_result.provider.as_mapping()
                if self.failed_result is not None
                else None
            ),
        }


def generate_polar_family(
    providers: Sequence[PolarProvider],
    plan: PolarFamilyGenerationPlan,
    *,
    retry_policy: PolarRetryPolicy | None = None,
    cache: FilesystemPolarCache | None = None,
    health_registry: PolarProviderHealthRegistry | None = None,
) -> PolarFamilyGenerationResult:
    """Generate a complete family sequentially through the provider orchestrator."""
    if not isinstance(plan, PolarFamilyGenerationPlan):
        raise TypeError("plan must be a PolarFamilyGenerationPlan.")
    if isinstance(providers, (str, bytes)):
        raise TypeError(
            "providers must be an ordered iterable of PolarProvider objects."
        )
    try:
        provider_chain = tuple(providers)
    except TypeError as error:
        raise TypeError(
            "providers must be an ordered iterable of PolarProvider objects."
        ) from error

    started = time.monotonic()
    cells: list[PolarFamilyGenerationCell] = []
    for position, request in enumerate(plan.requests, start=1):
        result: PolarGenerationResult | None = None
        try:
            result = generate_polar_orchestrated(
                provider_chain,
                request,
                retry_policy=retry_policy,
                cache=cache,
                health_registry=health_registry,
            )
            table = result.to_polar_table(require_complete=True)
        except PolarProviderError as error:
            failure = PolarFamilyGenerationError(
                plan,
                request,
                cells,
                failed_result=result,
            )
            raise failure from error
        mach_index = plan.mach_grid.index(request.mach)
        reynolds_index = plan.reynolds_grid.index(request.reynolds)
        cells.append(
            PolarFamilyGenerationCell(
                position=position,
                mach_index=mach_index,
                reynolds_index=reynolds_index,
                request=request,
                result=result,
                table=table,
            )
        )

    family = PolarFamily(tuple(cell.table for cell in cells))
    return PolarFamilyGenerationResult(
        plan=plan,
        family=family,
        cells=tuple(cells),
        elapsed_s=time.monotonic() - started,
    )
