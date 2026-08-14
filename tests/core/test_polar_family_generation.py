"""Provider-backed PolarFamily generation and fail-fast behavior."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from pyfoldable.core import (
    AirfoilDefinition,
    FilesystemPolarCache,
    POLAR_FAMILY_GENERATION_SCHEMA_VERSION,
    PolarFamilyGenerationError,
    PolarFamilyGenerationPlan,
    PolarFamilyGenerationResult,
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarPointResult,
    PolarProviderChainExhaustedError,
    PolarProviderExecutionError,
    PolarProviderHealthPolicy,
    PolarProviderHealthRegistry,
    PolarProviderTimeoutError,
    PolarRetryPolicy,
    ProviderCapabilities,
    ProviderIdentity,
    generate_polar_family,
)


AIRFOIL = AirfoilDefinition(
    id="FAMILY-TEST",
    source="fixture",
    coordinates=((1.0, 0.0), (0.5, 0.1), (0.0, 0.0), (0.5, -0.1), (1.0, 0.0)),
)
PRIMARY = ProviderIdentity("primary", "1", "primary-backend", "1")
SECONDARY = ProviderIdentity("secondary", "1", "secondary-backend", "1")
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


def _request(**changes) -> PolarGenerationRequest:
    base = PolarGenerationRequest(
        airfoil=AIRFOIL,
        alpha_rad=(-0.1, 0.0, 0.1),
        reynolds=100_000.0,
        mach=0.0,
        scenario_id="clean",
    )
    return replace(base, **changes)


def _plan(**changes) -> PolarFamilyGenerationPlan:
    values = {
        "request_template": _request(),
        "reynolds_grid": (100_000.0, 200_000.0, 400_000.0),
        "mach_grid": (0.0,),
    }
    values.update(changes)
    return PolarFamilyGenerationPlan(**values)


def _result(
    request: PolarGenerationRequest,
    identity: ProviderIdentity,
    *,
    partial: bool = False,
) -> PolarGenerationResult:
    points = []
    for index, alpha in enumerate(request.alpha_rad):
        if partial and index == 1:
            points.append(PolarPointResult(alpha, "not_converged", message="fixture"))
        else:
            scale = request.reynolds / 100_000.0 + request.mach
            points.append(
                PolarPointResult(
                    alpha,
                    "converged",
                    cl=scale * 10.0 * alpha,
                    cd=0.01 + alpha * alpha / scale,
                    cm=-0.02,
                )
            )
    return PolarGenerationResult(
        request=request,
        provider=identity,
        points=tuple(points),
        elapsed_s=0.01,
        metadata={"backend_cell": f"{request.mach:g}:{request.reynolds:g}"},
    )


class GridProvider:
    def __init__(
        self,
        identity: ProviderIdentity,
        *,
        capabilities: ProviderCapabilities = CAPABILITIES,
        failures: dict[tuple[float, float], BaseException] | None = None,
        partial_cells: set[tuple[float, float]] | None = None,
    ) -> None:
        self.identity = identity
        self.capabilities = capabilities
        self.failures = dict(failures or {})
        self.partial_cells = set(partial_cells or ())
        self.calls: list[tuple[float, float]] = []

    def generate(self, request: PolarGenerationRequest) -> PolarGenerationResult:
        key = (request.mach, request.reynolds)
        self.calls.append(key)
        failure = self.failures.get(key)
        if failure is not None:
            raise failure
        return _result(request, self.identity, partial=key in self.partial_cells)


def test_plan_builds_a_rectangular_canonical_request_grid() -> None:
    plan = _plan(
        request_template=_request(reynolds=100_000.0, mach=0.0),
        reynolds_grid=(100_000, 200_000),
        mach_grid=(0, 0.2),
    )

    assert plan.cell_count == 4
    assert tuple((request.mach, request.reynolds) for request in plan.requests) == (
        (0.0, 100_000.0),
        (0.0, 200_000.0),
        (0.2, 100_000.0),
        (0.2, 200_000.0),
    )
    assert plan.reynolds_grid == (100_000.0, 200_000.0)
    assert plan.mach_grid == (0.0, 0.2)
    assert plan.as_mapping()["schema_version"] == 1


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"reynolds_grid": ()}, "must not be empty"),
        ({"reynolds_grid": (100_000.0, 100_000.0)}, "strictly increasing"),
        ({"reynolds_grid": (200_000.0, 100_000.0)}, "strictly increasing"),
        ({"reynolds_grid": (True,)}, "finite number"),
        ({"reynolds_grid": (0.0,)}, "greater than zero"),
        ({"mach_grid": (-0.1,)}, "non-negative"),
        ({"mach_grid": (0.0, float("nan"))}, "finite number"),
        (
            {
                "request_template": _request(reynolds=150_000.0),
                "reynolds_grid": (100_000.0,),
            },
            "first Reynolds",
        ),
        (
            {
                "request_template": _request(mach=0.1),
                "mach_grid": (0.0,),
            },
            "first Mach",
        ),
    ],
)
def test_plan_rejects_ambiguous_or_noncanonical_grids(changes, message) -> None:
    values = {
        "request_template": _request(),
        "reynolds_grid": (100_000.0,),
        "mach_grid": (0.0,),
    }
    values.update(changes)

    with pytest.raises((TypeError, ValueError), match=message):
        PolarFamilyGenerationPlan(**values)


def test_generation_builds_queryable_family_and_preserves_cell_provenance() -> None:
    provider = GridProvider(PRIMARY)

    generated = generate_polar_family((provider,), _plan())

    assert POLAR_FAMILY_GENERATION_SCHEMA_VERSION == 1
    assert provider.calls == [
        (0.0, 100_000.0),
        (0.0, 200_000.0),
        (0.0, 400_000.0),
    ]
    assert generated.family.tables == tuple(cell.table for cell in generated.cells)
    assert tuple(cell.position for cell in generated.cells) == (1, 2, 3)
    assert tuple(cell.reynolds_index for cell in generated.cells) == (0, 1, 2)
    assert generated.selected_providers == (PRIMARY,)
    assert generated.elapsed_s >= 0.0

    middle = generated.cells[1]
    assert middle.table.metadata["backend_cell"] == "0:200000"
    assert middle.table.metadata["provider"] == PRIMARY.as_mapping()
    assert middle.table.metadata["orchestration"]["selected_provider"] == (
        PRIMARY.as_mapping()
    )
    assert middle.as_mapping()["usable_point_count"] == 3
    assert generated.as_mapping()["complete"] is True
    assert generated.as_mapping()["selected_providers"] == (
        PRIMARY.as_mapping(),
    )
    request_mapping = generated.plan.as_mapping()["request_template"]
    assert request_mapping["n_crit"] == 9.0
    assert request_mapping["airfoil"]["coordinates"] == AIRFOIL.coordinates
    json.dumps(generated.as_mapping(), allow_nan=False)

    query = generated.family.query(
        alpha_rad=0.05,
        reynolds=200_000.0,
        mach=0.0,
    )
    assert query.cl == pytest.approx(1.0)


def test_provider_iterable_is_snapshotted_for_every_grid_cell() -> None:
    provider = GridProvider(PRIMARY)
    provider_iterable = (item for item in (provider,))

    generated = generate_polar_family(provider_iterable, _plan())

    assert len(generated.cells) == 3
    assert len(provider.calls) == 3


def test_capability_fallback_is_preserved_per_cell() -> None:
    no_mach = replace(CAPABILITIES, supports_mach=False)
    primary = GridProvider(PRIMARY, capabilities=no_mach)
    secondary = GridProvider(SECONDARY)
    plan = _plan(
        reynolds_grid=(100_000.0, 200_000.0),
        mach_grid=(0.0, 0.2),
    )

    generated = generate_polar_family((primary, secondary), plan)

    assert primary.calls == [(0.0, 100_000.0), (0.0, 200_000.0)]
    assert secondary.calls == [(0.2, 100_000.0), (0.2, 200_000.0)]
    assert generated.selected_providers == (PRIMARY, SECONDARY)
    mach_cell = generated.cells[2]
    attempts = mach_cell.result.metadata["orchestration"]["attempts"]
    assert tuple(attempt["outcome"] for attempt in attempts) == (
        "capability_error",
        "success",
    )


def test_cache_is_forwarded_and_second_family_run_avoids_backend_work(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    first = GridProvider(PRIMARY)
    plan = _plan(reynolds_grid=(100_000.0, 200_000.0))

    generated = generate_polar_family((first,), plan, cache=cache)
    second = GridProvider(PRIMARY)
    loaded = generate_polar_family((second,), plan, cache=cache)

    assert first.calls == [(0.0, 100_000.0), (0.0, 200_000.0)]
    assert second.calls == []
    assert tuple(cell.cache_status for cell in generated.cells) == ("miss", "miss")
    assert tuple(cell.cache_status for cell in loaded.cells) == ("hit", "hit")


def test_health_registry_state_flows_across_family_cells() -> None:
    primary = GridProvider(
        PRIMARY,
        failures={(0.0, 100_000.0): PolarProviderTimeoutError("opens")},
    )
    secondary = GridProvider(SECONDARY)
    health = PolarProviderHealthRegistry(
        PolarProviderHealthPolicy(failure_threshold=1, recovery_timeout_s=60.0)
    )
    retry = PolarRetryPolicy(max_attempts=1)
    plan = _plan(reynolds_grid=(100_000.0, 200_000.0))

    generated = generate_polar_family(
        (primary, secondary),
        plan,
        retry_policy=retry,
        health_registry=health,
    )

    assert primary.calls == [(0.0, 100_000.0)]
    assert secondary.calls == [(0.0, 100_000.0), (0.0, 200_000.0)]
    second_attempt = generated.cells[1].result.metadata["orchestration"]["attempts"][0]
    assert second_attempt["outcome"] == "circuit_open"
    assert health.snapshot(PRIMARY).total_rejections == 1


def test_fail_fast_error_retains_completed_cells_and_failed_request() -> None:
    provider = GridProvider(
        PRIMARY,
        failures={(0.0, 200_000.0): PolarProviderExecutionError("bad cell")},
    )
    plan = _plan()

    with pytest.raises(PolarFamilyGenerationError) as captured:
        generate_polar_family((provider,), plan)

    error = captured.value
    assert tuple(
        cell.request.reynolds for cell in error.completed_cells
    ) == (100_000.0,)
    assert error.failed_request.reynolds == 200_000.0
    assert error.failed_result is None
    assert "cell 2/3" in str(error)
    assert error.as_mapping()["failed_position"] == 2
    assert isinstance(error.__cause__, PolarProviderChainExhaustedError)
    assert provider.calls == [(0.0, 100_000.0), (0.0, 200_000.0)]


def test_partial_result_is_rejected_without_hidden_fallback() -> None:
    primary = GridProvider(PRIMARY, partial_cells={(0.0, 100_000.0)})
    secondary = GridProvider(SECONDARY)

    with pytest.raises(PolarFamilyGenerationError) as captured:
        generate_polar_family((primary, secondary), _plan())

    error = captured.value
    assert error.completed_cells == ()
    assert error.failed_result is not None
    assert not error.failed_result.complete
    assert isinstance(error.__cause__, PolarProviderExecutionError)
    assert primary.calls == [(0.0, 100_000.0)]
    assert secondary.calls == []


def test_unexpected_provider_exception_is_not_masked_without_health_isolation() -> None:
    provider = GridProvider(
        PRIMARY,
        failures={(0.0, 100_000.0): RuntimeError("programming bug")},
    )

    with pytest.raises(RuntimeError, match="programming bug"):
        generate_polar_family((provider,), _plan())


def test_family_generation_never_masks_base_exceptions() -> None:
    provider = GridProvider(
        PRIMARY,
        failures={(0.0, 100_000.0): KeyboardInterrupt()},
    )

    with pytest.raises(KeyboardInterrupt):
        generate_polar_family((provider,), _plan())


def test_family_generation_rejects_invalid_plan_and_provider_inputs() -> None:
    with pytest.raises(TypeError, match="plan"):
        generate_polar_family((), object())
    with pytest.raises(TypeError, match="ordered iterable"):
        generate_polar_family("primary", _plan())
    with pytest.raises(ValueError, match="at least one"):
        generate_polar_family((), _plan())


def test_generation_result_rejects_forged_grid_indices() -> None:
    generated = generate_polar_family((GridProvider(PRIMARY),), _plan())
    forged = (replace(generated.cells[0], reynolds_index=1), *generated.cells[1:])

    with pytest.raises(ValueError, match="indices"):
        PolarFamilyGenerationResult(
            generated.plan,
            generated.family,
            forged,
            generated.elapsed_s,
        )
