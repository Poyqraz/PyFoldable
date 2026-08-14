"""Provider health telemetry and circuit-breaker state-machine behavior."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from pyfoldable.core import (
    POLAR_PROVIDER_HEALTH_SCHEMA_VERSION,
    PolarProviderCapabilityError,
    PolarProviderCircuitOpenError,
    PolarProviderError,
    PolarProviderExecutionError,
    PolarProviderHealthPolicy,
    PolarProviderHealthRegistry,
    PolarProviderHealthSnapshot,
    PolarProviderTimeoutError,
    PolarProviderUnavailableError,
    PolarProviderUnexpectedError,
    ProviderIdentity,
)


PRIMARY = ProviderIdentity("primary-health", "1", "backend-a", "2")
SECONDARY = ProviderIdentity("secondary-health", "1", "backend-b", "3")


class ManualClock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def _registry(
    clock: ManualClock,
    *,
    failure_threshold: int = 2,
    recovery_timeout_s: float = 10.0,
    **changes,
) -> PolarProviderHealthRegistry:
    return PolarProviderHealthRegistry(
        PolarProviderHealthPolicy(
            failure_threshold=failure_threshold,
            recovery_timeout_s=recovery_timeout_s,
            **changes,
        ),
        clock=clock,
    )


def _record_failure(registry, error, provider=PRIMARY):
    permit, before = registry._acquire(provider)
    assert permit is not None
    after, counted = registry._record_failure(permit, error)
    return before, after, counted


def test_snapshot_of_untracked_provider_is_closed_and_non_mutating() -> None:
    clock = ManualClock()
    registry = _registry(clock)

    snapshot = registry.snapshot(PRIMARY)

    assert snapshot.state == "closed"
    assert snapshot.consecutive_failures == 0
    assert snapshot.total_successes == 0
    assert snapshot.total_failures == 0
    assert snapshot.total_rejections == 0
    assert snapshot.cooldown_remaining_s == 0.0
    assert snapshot.probe_in_flight is False
    assert registry.snapshots() == ()
    assert snapshot.as_mapping()["schema_version"] == (
        POLAR_PROVIDER_HEALTH_SCHEMA_VERSION
    )


def test_counted_failures_open_circuit_at_threshold() -> None:
    clock = ManualClock()
    registry = _registry(clock, failure_threshold=2)

    _, first, first_counted = _record_failure(
        registry,
        PolarProviderTimeoutError("slow-1"),
    )
    _, second, second_counted = _record_failure(
        registry,
        PolarProviderTimeoutError("slow-2"),
    )

    assert first.state == "closed"
    assert first.consecutive_failures == 1
    assert second.state == "open"
    assert second.consecutive_failures == 2
    assert second.cooldown_remaining_s == 10.0
    assert first_counted is True
    assert second_counted is True
    assert second.last_failure_type == "PolarProviderTimeoutError"


def test_success_resets_consecutive_failures_while_closed() -> None:
    clock = ManualClock()
    registry = _registry(clock, failure_threshold=3)
    _record_failure(registry, PolarProviderExecutionError("transient"))
    permit, _ = registry._acquire(PRIMARY)
    assert permit is not None

    snapshot = registry._record_success(permit)

    assert snapshot.state == "closed"
    assert snapshot.consecutive_failures == 0
    assert snapshot.total_successes == 1
    assert snapshot.total_failures == 1
    assert snapshot.last_failure_type is None


def test_open_circuit_rejects_without_granting_call_permit() -> None:
    clock = ManualClock()
    registry = _registry(clock, failure_threshold=1)
    _record_failure(registry, PolarProviderUnavailableError("missing"))

    permit, snapshot = registry._acquire(PRIMARY)

    assert permit is None
    assert snapshot.state == "open"
    assert snapshot.total_rejections == 1
    error = PolarProviderCircuitOpenError(snapshot)
    assert "primary-health" in str(error)
    assert error.snapshot == snapshot


def test_cooldown_allows_exactly_one_half_open_probe() -> None:
    clock = ManualClock()
    registry = _registry(clock, failure_threshold=1, recovery_timeout_s=5.0)
    _record_failure(registry, PolarProviderTimeoutError("slow"))
    clock.advance(5.0)

    first_permit, first = registry._acquire(PRIMARY)
    second_permit, second = registry._acquire(PRIMARY)

    assert first_permit is not None
    assert first_permit.probe is True
    assert first.state == "half_open"
    assert first.probe_in_flight is True
    assert second_permit is None
    assert second.state == "half_open"
    assert second.total_rejections == 1


def test_successful_half_open_probe_closes_circuit() -> None:
    clock = ManualClock()
    registry = _registry(clock, failure_threshold=1, recovery_timeout_s=5.0)
    _record_failure(registry, PolarProviderTimeoutError("slow"))
    clock.advance(5.0)
    permit, _ = registry._acquire(PRIMARY)
    assert permit is not None

    snapshot = registry._record_success(permit)

    assert snapshot.state == "closed"
    assert snapshot.consecutive_failures == 0
    assert snapshot.probe_in_flight is False
    assert snapshot.cooldown_remaining_s == 0.0


def test_failed_half_open_probe_reopens_and_restarts_cooldown() -> None:
    clock = ManualClock()
    registry = _registry(clock, failure_threshold=1, recovery_timeout_s=5.0)
    _record_failure(registry, PolarProviderTimeoutError("slow"))
    clock.advance(5.0)
    permit, _ = registry._acquire(PRIMARY)
    assert permit is not None
    clock.advance(2.0)

    snapshot, counted = registry._record_failure(
        permit,
        PolarProviderExecutionError("probe failed"),
    )

    assert counted is True
    assert snapshot.state == "open"
    assert snapshot.consecutive_failures == 2
    assert snapshot.cooldown_remaining_s == 5.0
    assert snapshot.probe_in_flight is False


def test_neutral_half_open_release_reopens_without_false_success() -> None:
    clock = ManualClock()
    registry = _registry(clock, failure_threshold=1, recovery_timeout_s=5.0)
    _record_failure(registry, PolarProviderTimeoutError("slow"))
    clock.advance(5.0)
    permit, _ = registry._acquire(PRIMARY)
    assert permit is not None

    snapshot = registry._record_neutral(permit)

    assert snapshot.state == "open"
    assert snapshot.cooldown_remaining_s == 5.0
    assert snapshot.total_successes == 0
    assert snapshot.probe_in_flight is False


def test_stale_in_flight_success_cannot_close_newly_opened_circuit() -> None:
    clock = ManualClock()
    registry = _registry(clock, failure_threshold=1)
    failing_permit, _ = registry._acquire(PRIMARY)
    stale_success_permit, _ = registry._acquire(PRIMARY)
    assert failing_permit is not None
    assert stale_success_permit is not None
    registry._record_failure(
        failing_permit,
        PolarProviderTimeoutError("opens circuit"),
    )

    snapshot = registry._record_success(stale_success_permit)

    assert snapshot.state == "open"
    assert snapshot.consecutive_failures == 1
    assert snapshot.total_successes == 0


def test_reset_invalidates_in_flight_permits_without_recreating_state() -> None:
    clock = ManualClock()
    registry = _registry(clock)
    stale_success, _ = registry._acquire(PRIMARY)
    stale_failure, _ = registry._acquire(SECONDARY)
    assert stale_success is not None
    assert stale_failure is not None

    registry.reset()
    registry._record_success(stale_success)
    registry._record_failure(
        stale_failure,
        PolarProviderTimeoutError("late failure"),
    )

    assert registry.snapshots() == ()


def test_concurrent_cooldown_expiry_grants_only_one_probe() -> None:
    clock = ManualClock()
    registry = _registry(clock, failure_threshold=1, recovery_timeout_s=5.0)
    _record_failure(registry, PolarProviderTimeoutError("slow"))
    clock.advance(5.0)

    with ThreadPoolExecutor(max_workers=8) as executor:
        decisions = tuple(executor.map(lambda _: registry._acquire(PRIMARY), range(8)))

    permits = tuple(permit for permit, _ in decisions if permit is not None)
    snapshot = registry.snapshot(PRIMARY)
    assert len(permits) == 1
    assert permits[0].probe is True
    assert snapshot.state == "half_open"
    assert snapshot.probe_in_flight is True
    assert snapshot.total_rejections == 7


def test_snapshots_are_deterministic_and_reset_is_atomic() -> None:
    clock = ManualClock()
    registry = _registry(clock)
    _record_failure(
        registry,
        PolarProviderExecutionError("secondary"),
        provider=SECONDARY,
    )
    _record_failure(
        registry,
        PolarProviderExecutionError("primary"),
        provider=PRIMARY,
    )

    assert tuple(item.provider for item in registry.snapshots()) == (
        PRIMARY,
        SECONDARY,
    )
    registry.reset(PRIMARY)
    assert tuple(item.provider for item in registry.snapshots()) == (SECONDARY,)
    registry.reset()
    assert registry.snapshots() == ()


@pytest.mark.parametrize(
    ("error", "policy_changes", "expected"),
    [
        (PolarProviderCapabilityError("unsupported"), {}, False),
        (PolarProviderUnavailableError("missing"), {}, True),
        (PolarProviderTimeoutError("slow"), {}, True),
        (PolarProviderExecutionError("failed"), {}, True),
        (PolarProviderError("generic"), {}, True),
        (
            PolarProviderUnexpectedError(PRIMARY, RuntimeError("bug")),
            {},
            True,
        ),
        (
            PolarProviderTimeoutError("slow"),
            {"count_timeout_errors": False},
            False,
        ),
        (
            PolarProviderUnexpectedError(PRIMARY, RuntimeError("bug")),
            {"count_unexpected_errors": False},
            False,
        ),
    ],
)
def test_failure_counting_is_explicit(error, policy_changes, expected) -> None:
    policy = PolarProviderHealthPolicy(**policy_changes)
    assert policy.counts_failure(error) is expected


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"failure_threshold": 0}, "failure_threshold"),
        ({"failure_threshold": True}, "failure_threshold"),
        ({"recovery_timeout_s": -1.0}, "recovery_timeout_s"),
        ({"recovery_timeout_s": float("nan")}, "recovery_timeout_s"),
        ({"count_unavailable_errors": 1}, "count_unavailable_errors"),
        ({"count_timeout_errors": "yes"}, "count_timeout_errors"),
        ({"count_execution_errors": None}, "count_execution_errors"),
        ({"count_provider_errors": 1}, "count_provider_errors"),
        ({"isolate_unexpected_errors": 1}, "isolate_unexpected_errors"),
        ({"count_unexpected_errors": 1}, "count_unexpected_errors"),
    ],
)
def test_health_policy_is_strictly_validated(changes, message) -> None:
    with pytest.raises(ValueError, match=message):
        PolarProviderHealthPolicy(**changes)


@pytest.mark.parametrize("clock_value", [True, float("nan"), "now"])
def test_registry_rejects_invalid_clock_values(clock_value) -> None:
    registry = PolarProviderHealthRegistry(clock=lambda: clock_value)
    with pytest.raises(ValueError, match="health clock"):
        registry.snapshot(PRIMARY)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"provider": object()}, "provider"),
        ({"state": []}, "health state"),
        ({"consecutive_failures": True}, "consecutive_failures"),
        ({"total_successes": -1}, "total_successes"),
        ({"total_failures": 1.5}, "total_failures"),
        ({"total_rejections": -1}, "total_rejections"),
        ({"cooldown_remaining_s": float("nan")}, "cooldown_remaining_s"),
        ({"probe_in_flight": 1}, "probe_in_flight"),
        ({"last_failure_type": object()}, "last_failure_type"),
    ],
)
def test_health_snapshot_is_strictly_validated(changes, message) -> None:
    values = {
        "provider": PRIMARY,
        "state": "closed",
        "consecutive_failures": 0,
        "total_successes": 0,
        "total_failures": 0,
        "total_rejections": 0,
        "cooldown_remaining_s": 0.0,
        "probe_in_flight": False,
    }
    values.update(changes)

    with pytest.raises((TypeError, ValueError), match=message):
        PolarProviderHealthSnapshot(**values)


def test_failure_message_is_bounded_in_health_telemetry() -> None:
    clock = ManualClock()
    registry = _registry(clock)

    _, snapshot, _ = _record_failure(
        registry,
        PolarProviderExecutionError("x" * 5000),
    )

    assert snapshot.last_failure_message is not None
    assert len(snapshot.last_failure_message) == 4096
    assert snapshot.last_failure_message.endswith("...")
