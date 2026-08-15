"""Provider-backed generation of deterministic polar families."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace
from typing import Any, Literal, Mapping, Sequence

from .models import PolarTable
from .polar import PolarFamily
from .polar_cache import FilesystemPolarCache
from .polar_health import PolarProviderHealthRegistry
from .polar_orchestration import (
    PolarProviderAttempt,
    PolarProviderChainExhaustedError,
    PolarRetryPolicy,
    generate_polar_orchestrated,
)
from .polar_qualification import (
    PolarProviderResultRejectedError,
    PolarResultQualification,
    PolarResultQualificationPolicy,
)
from .providers import (
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarProvider,
    PolarProviderError,
    ProviderIdentity,
)


POLAR_FAMILY_GENERATION_SCHEMA_VERSION = 1
POLAR_FAMILY_BATCH_SCHEMA_VERSION = 1

PolarFamilyFailureMode = Literal["fail_fast", "collect_all"]
PolarFamilySubgridPolicy = Literal["none", "complete_axes"]
_FAILURE_MODES = {"fail_fast", "collect_all"}
_SUBGRID_POLICIES = {"none", "complete_axes"}
_COMPLETE_RESULT_POLICY = PolarResultQualificationPolicy()


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
class PolarFamilyBatchPolicy:
    """Failure collection and safe partial-family materialization policy."""

    failure_mode: PolarFamilyFailureMode = "fail_fast"
    subgrid_policy: PolarFamilySubgridPolicy = "none"

    def __post_init__(self) -> None:
        if self.failure_mode not in _FAILURE_MODES:
            raise ValueError(f"Unsupported failure_mode {self.failure_mode!r}.")
        if self.subgrid_policy not in _SUBGRID_POLICIES:
            raise ValueError(f"Unsupported subgrid_policy {self.subgrid_policy!r}.")
        if self.failure_mode == "fail_fast" and self.subgrid_policy != "none":
            raise ValueError(
                "subgrid_policy requires failure_mode='collect_all'."
            )

    def as_mapping(self) -> dict[str, object]:
        return {
            "failure_mode": self.failure_mode,
            "subgrid_policy": self.subgrid_policy,
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
class PolarFamilyGenerationFailure:
    """Serializable diagnostics for one grid cell that exhausted its chain."""

    position: int
    mach_index: int
    reynolds_index: int
    request: PolarGenerationRequest
    error_type: str
    error_message: str
    attempts: tuple[PolarProviderAttempt, ...] = ()
    failed_result: PolarGenerationResult | None = None
    qualification: PolarResultQualification | None = None

    def __post_init__(self) -> None:
        for name in ("position", "mach_index", "reynolds_index"):
            value = getattr(self, name)
            minimum = 1 if name == "position" else 0
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                qualifier = "positive" if minimum else "non-negative"
                raise ValueError(f"{name} must be a {qualifier} integer.")
        if not isinstance(self.request, PolarGenerationRequest):
            raise TypeError("request must be a PolarGenerationRequest.")
        for name in ("error_type", "error_message"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string.")
        if not all(isinstance(attempt, PolarProviderAttempt) for attempt in self.attempts):
            raise TypeError("attempts must contain PolarProviderAttempt values.")
        if self.failed_result is not None:
            if not isinstance(self.failed_result, PolarGenerationResult):
                raise TypeError(
                    "failed_result must be a PolarGenerationResult or None."
                )
            if self.failed_result.request != self.request:
                raise ValueError("failed_result must belong to the failed request.")
        if self.qualification is not None:
            if not isinstance(self.qualification, PolarResultQualification):
                raise TypeError(
                    "qualification must be a PolarResultQualification or None."
                )
            if self.failed_result is None:
                raise ValueError("qualification requires failed_result.")
            if self.qualification.accepted:
                raise ValueError("A failed result qualification cannot be accepted.")
            if self.qualification.point_count != len(self.failed_result.points):
                raise ValueError("qualification must describe failed_result.")

    def as_mapping(self) -> dict[str, object]:
        rejected_result: dict[str, object] | None = None
        if self.failed_result is not None:
            rejected_alpha_rad = tuple(
                self.failed_result.points[index].alpha_rad
                for index in (
                    self.qualification.rejected_indices
                    if self.qualification is not None
                    else ()
                )
            )
            rejected_result = {
                "provider": self.failed_result.provider.as_mapping(),
                "alpha_rad": tuple(
                    point.alpha_rad for point in self.failed_result.points
                ),
                "statuses": tuple(point.status for point in self.failed_result.points),
                "usable_mask": self.failed_result.usable_mask,
                "rejected_alpha_rad": rejected_alpha_rad,
                "rejected_alpha_range_rad": (
                    (min(rejected_alpha_rad), max(rejected_alpha_rad))
                    if rejected_alpha_rad
                    else None
                ),
                "warnings": self.failed_result.warnings,
            }
        return {
            "position": self.position,
            "mach_index": self.mach_index,
            "reynolds_index": self.reynolds_index,
            "reynolds": self.request.reynolds,
            "mach": self.request.mach,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "attempts": tuple(attempt.as_mapping() for attempt in self.attempts),
            "rejected_result": rejected_result,
            "qualification": (
                self.qualification.as_mapping()
                if self.qualification is not None
                else None
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


@dataclass(frozen=True)
class PolarFamilyBatchResult:
    """All ordered cell outcomes plus an optional safe rectangular family."""

    plan: PolarFamilyGenerationPlan
    policy: PolarFamilyBatchPolicy
    cells: tuple[PolarFamilyGenerationCell, ...]
    failures: tuple[PolarFamilyGenerationFailure, ...]
    family: PolarFamily | None
    family_cells: tuple[PolarFamilyGenerationCell, ...]
    family_mach_grid: tuple[float, ...]
    family_reynolds_grid: tuple[float, ...]
    elapsed_s: float

    def __post_init__(self) -> None:
        if not isinstance(self.plan, PolarFamilyGenerationPlan):
            raise TypeError("plan must be a PolarFamilyGenerationPlan.")
        if not isinstance(self.policy, PolarFamilyBatchPolicy):
            raise TypeError("policy must be a PolarFamilyBatchPolicy.")
        if not all(isinstance(cell, PolarFamilyGenerationCell) for cell in self.cells):
            raise TypeError("cells must contain PolarFamilyGenerationCell values.")
        if not all(
            isinstance(failure, PolarFamilyGenerationFailure)
            for failure in self.failures
        ):
            raise TypeError(
                "failures must contain PolarFamilyGenerationFailure values."
            )
        outcomes = tuple(sorted(
            (*self.cells, *self.failures), key=lambda outcome: outcome.position
        ))
        if tuple(outcome.position for outcome in outcomes) != tuple(
            range(1, self.plan.cell_count + 1)
        ):
            raise ValueError("Batch outcomes must cover every planned position once.")
        requests = self.plan.requests
        reynolds_count = len(self.plan.reynolds_grid)
        for outcome in outcomes:
            expected_mach, expected_reynolds = divmod(
                outcome.position - 1, reynolds_count
            )
            if (
                outcome.request != requests[outcome.position - 1]
                or outcome.mach_index != expected_mach
                or outcome.reynolds_index != expected_reynolds
            ):
                raise ValueError("Batch outcome does not match canonical plan order.")
        if self.policy.failure_mode == "fail_fast" and self.failures:
            raise ValueError("fail_fast results cannot contain collected failures.")
        complete = not self.failures
        if complete and len(self.cells) != self.plan.cell_count:
            raise ValueError("A complete batch must contain every successful cell.")
        if not complete and self.policy.failure_mode != "collect_all":
            raise ValueError("Partial batch results require collect_all mode.")
        if self.family is None:
            if self.family_cells or self.family_mach_grid or self.family_reynolds_grid:
                raise ValueError("Family selection must be empty when family is None.")
        else:
            if not isinstance(self.family, PolarFamily):
                raise TypeError("family must be a PolarFamily or None.")
            if not self.family_cells:
                raise ValueError("family requires at least one selected cell.")
            if not all(cell in self.cells for cell in self.family_cells):
                raise ValueError("family_cells must be successful batch cells.")
            if self.family.tables != tuple(cell.table for cell in self.family_cells):
                raise ValueError("family tables must match family_cells exactly.")
            expected_pairs = tuple(
                (mach, reynolds)
                for mach in self.family_mach_grid
                for reynolds in self.family_reynolds_grid
            )
            if tuple(
                (cell.request.mach, cell.request.reynolds)
                for cell in self.family_cells
            ) != expected_pairs:
                raise ValueError("family_cells must form the declared rectangular grid.")
        if complete and (
            self.family is None
            or self.family_cells != self.cells
            or self.family_mach_grid != self.plan.mach_grid
            or self.family_reynolds_grid != self.plan.reynolds_grid
        ):
            raise ValueError("A complete batch must materialize the full plan family.")
        if (
            not complete
            and self.policy.subgrid_policy == "none"
            and self.family is not None
        ):
            raise ValueError("subgrid_policy='none' cannot materialize a partial family.")
        if (
            isinstance(self.elapsed_s, bool)
            or not isinstance(self.elapsed_s, (int, float))
            or not math.isfinite(float(self.elapsed_s))
            or self.elapsed_s < 0.0
        ):
            raise ValueError("elapsed_s must be a non-negative finite number.")

    @property
    def complete(self) -> bool:
        return not self.failures

    @property
    def selected_providers(self) -> tuple[ProviderIdentity, ...]:
        return tuple(dict.fromkeys(cell.result.provider for cell in self.cells))

    def as_mapping(self) -> dict[str, object]:
        return {
            "schema_version": POLAR_FAMILY_BATCH_SCHEMA_VERSION,
            "plan": self.plan.as_mapping(),
            "policy": self.policy.as_mapping(),
            "elapsed_s": self.elapsed_s,
            "complete": self.complete,
            "successful_cell_count": len(self.cells),
            "failed_cell_count": len(self.failures),
            "family_available": self.family is not None,
            "family_mach_grid": self.family_mach_grid,
            "family_reynolds_grid": self.family_reynolds_grid,
            "selected_providers": tuple(
                provider.as_mapping() for provider in self.selected_providers
            ),
            "cells": tuple(cell.as_mapping() for cell in self.cells),
            "failures": tuple(failure.as_mapping() for failure in self.failures),
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
    batch = generate_polar_family_batch(
        providers,
        plan,
        policy=PolarFamilyBatchPolicy(),
        retry_policy=retry_policy,
        cache=cache,
        health_registry=health_registry,
    )
    if batch.family is None:  # pragma: no cover - guarded by batch invariants
        raise RuntimeError("Complete family generation did not produce a family.")
    return PolarFamilyGenerationResult(
        plan=plan,
        family=batch.family,
        cells=batch.cells,
        elapsed_s=batch.elapsed_s,
    )


def generate_polar_family_batch(
    providers: Sequence[PolarProvider],
    plan: PolarFamilyGenerationPlan,
    *,
    policy: PolarFamilyBatchPolicy | None = None,
    retry_policy: PolarRetryPolicy | None = None,
    cache: FilesystemPolarCache | None = None,
    health_registry: PolarProviderHealthRegistry | None = None,
    result_policy: PolarResultQualificationPolicy | None = None,
) -> PolarFamilyBatchResult:
    """Generate all requested cells under explicit failure and sub-grid policy."""
    if not isinstance(plan, PolarFamilyGenerationPlan):
        raise TypeError("plan must be a PolarFamilyGenerationPlan.")
    batch_policy = policy or PolarFamilyBatchPolicy()
    if not isinstance(batch_policy, PolarFamilyBatchPolicy):
        raise TypeError("policy must be a PolarFamilyBatchPolicy or None.")
    qualification_policy = result_policy or _COMPLETE_RESULT_POLICY
    if not isinstance(qualification_policy, PolarResultQualificationPolicy):
        raise TypeError(
            "result_policy must be a PolarResultQualificationPolicy or None."
        )
    if qualification_policy.minimum_usable_fraction != 1.0:
        raise ValueError(
            "Family generation requires minimum_usable_fraction=1.0."
        )
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
    if not provider_chain:
        raise ValueError("providers must contain at least one provider.")

    started = time.monotonic()
    cells: list[PolarFamilyGenerationCell] = []
    failures: list[PolarFamilyGenerationFailure] = []
    reynolds_count = len(plan.reynolds_grid)
    for position, request in enumerate(plan.requests, start=1):
        result: PolarGenerationResult | None = None
        try:
            result = generate_polar_orchestrated(
                provider_chain,
                request,
                retry_policy=retry_policy,
                cache=cache,
                health_registry=health_registry,
                result_policy=qualification_policy,
            )
            table = result.to_polar_table(require_complete=True)
        except PolarProviderError as error:
            mach_index, reynolds_index = divmod(position - 1, reynolds_count)
            diagnostics = _generation_failure(
                position=position,
                mach_index=mach_index,
                reynolds_index=reynolds_index,
                request=request,
                error=error,
                failed_result=result,
            )
            if batch_policy.failure_mode == "fail_fast":
                failure = PolarFamilyGenerationError(
                    plan,
                    request,
                    cells,
                    failed_result=diagnostics.failed_result,
                )
                raise failure from error
            failures.append(diagnostics)
            continue
        mach_index, reynolds_index = divmod(position - 1, reynolds_count)
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

    family, family_cells, family_mach_grid, family_reynolds_grid = (
        _materialize_batch_family(plan, batch_policy, cells, failures)
    )
    return PolarFamilyBatchResult(
        plan=plan,
        policy=batch_policy,
        cells=tuple(cells),
        failures=tuple(failures),
        family=family,
        family_cells=family_cells,
        family_mach_grid=family_mach_grid,
        family_reynolds_grid=family_reynolds_grid,
        elapsed_s=time.monotonic() - started,
    )


def _generation_failure(
    *,
    position: int,
    mach_index: int,
    reynolds_index: int,
    request: PolarGenerationRequest,
    error: PolarProviderError,
    failed_result: PolarGenerationResult | None,
) -> PolarFamilyGenerationFailure:
    attempts = (
        error.attempts
        if isinstance(error, PolarProviderChainExhaustedError)
        else ()
    )
    rejection: PolarProviderResultRejectedError | None = None
    if isinstance(error, PolarProviderResultRejectedError):
        rejection = error
    elif isinstance(error.__cause__, PolarProviderResultRejectedError):
        rejection = error.__cause__
    if rejection is not None:
        failed_result = rejection.result
    message = str(error) or type(error).__name__
    return PolarFamilyGenerationFailure(
        position=position,
        mach_index=mach_index,
        reynolds_index=reynolds_index,
        request=request,
        error_type=type(error).__name__,
        error_message=message[:4096],
        attempts=tuple(attempts),
        failed_result=failed_result,
        qualification=(rejection.qualification if rejection is not None else None),
    )


def _materialize_batch_family(
    plan: PolarFamilyGenerationPlan,
    policy: PolarFamilyBatchPolicy,
    cells: Sequence[PolarFamilyGenerationCell],
    failures: Sequence[PolarFamilyGenerationFailure],
) -> tuple[
    PolarFamily | None,
    tuple[PolarFamilyGenerationCell, ...],
    tuple[float, ...],
    tuple[float, ...],
]:
    ordered_cells = tuple(cells)
    if not failures:
        return (
            PolarFamily(tuple(cell.table for cell in ordered_cells)),
            ordered_cells,
            plan.mach_grid,
            plan.reynolds_grid,
        )
    if policy.subgrid_policy == "none":
        return None, (), (), ()

    successful = {
        (cell.mach_index, cell.reynolds_index): cell for cell in ordered_cells
    }
    mach_count = len(plan.mach_grid)
    reynolds_count = len(plan.reynolds_grid)
    complete_rows = tuple(
        mach_index
        for mach_index in range(mach_count)
        if all(
            (mach_index, reynolds_index) in successful
            for reynolds_index in range(reynolds_count)
        )
    )
    complete_columns = tuple(
        reynolds_index
        for reynolds_index in range(reynolds_count)
        if all(
            (mach_index, reynolds_index) in successful
            for mach_index in range(mach_count)
        )
    )
    candidates: list[
        tuple[
            int,
            tuple[PolarFamilyGenerationCell, ...],
            tuple[float, ...],
            tuple[float, ...],
        ]
    ] = []
    if complete_rows:
        row_cells = tuple(
            successful[(mach_index, reynolds_index)]
            for mach_index in complete_rows
            for reynolds_index in range(reynolds_count)
        )
        candidates.append(
            (
                1,
                row_cells,
                tuple(plan.mach_grid[index] for index in complete_rows),
                plan.reynolds_grid,
            )
        )
    if complete_columns:
        column_cells = tuple(
            successful[(mach_index, reynolds_index)]
            for mach_index in range(mach_count)
            for reynolds_index in complete_columns
        )
        candidates.append(
            (
                0,
                column_cells,
                plan.mach_grid,
                tuple(plan.reynolds_grid[index] for index in complete_columns),
            )
        )
    if not candidates:
        return None, (), (), ()
    _, selected, mach_grid, reynolds_grid = max(
        candidates, key=lambda candidate: (len(candidate[1]), candidate[0])
    )
    return (
        PolarFamily(tuple(cell.table for cell in selected)),
        selected,
        mach_grid,
        reynolds_grid,
    )
