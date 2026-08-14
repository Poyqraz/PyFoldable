"""Thread-safe provider health telemetry and circuit-breaker state."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Callable, Literal

from .providers import (
    PolarProviderCapabilityError,
    PolarProviderError,
    PolarProviderExecutionError,
    PolarProviderTimeoutError,
    PolarProviderUnavailableError,
    ProviderIdentity,
)


POLAR_PROVIDER_HEALTH_SCHEMA_VERSION = 1

PolarProviderHealthState = Literal["closed", "open", "half_open"]
_MAX_ERROR_MESSAGE_LENGTH = 4096


@dataclass(frozen=True)
class PolarProviderHealthPolicy:
    """Failure threshold, cooldown, and isolation rules for provider circuits."""

    failure_threshold: int = 3
    recovery_timeout_s: float = 30.0
    count_unavailable_errors: bool = True
    count_timeout_errors: bool = True
    count_execution_errors: bool = True
    count_provider_errors: bool = True
    isolate_unexpected_errors: bool = True
    count_unexpected_errors: bool = True

    def __post_init__(self) -> None:
        if (
            isinstance(self.failure_threshold, bool)
            or not isinstance(self.failure_threshold, int)
            or self.failure_threshold < 1
        ):
            raise ValueError("failure_threshold must be a positive integer.")
        if (
            isinstance(self.recovery_timeout_s, bool)
            or not isinstance(self.recovery_timeout_s, (int, float))
            or not math.isfinite(float(self.recovery_timeout_s))
            or self.recovery_timeout_s < 0.0
        ):
            raise ValueError(
                "recovery_timeout_s must be a non-negative finite number."
            )
        for name in (
            "count_unavailable_errors",
            "count_timeout_errors",
            "count_execution_errors",
            "count_provider_errors",
            "isolate_unexpected_errors",
            "count_unexpected_errors",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be bool.")

    def counts_failure(self, error: PolarProviderError) -> bool:
        """Return whether one typed failure contributes to opening a circuit."""
        if not isinstance(error, PolarProviderError):
            raise TypeError("error must be a PolarProviderError.")
        if isinstance(error, PolarProviderCapabilityError):
            return False
        if isinstance(error, PolarProviderCircuitOpenError):
            return False
        if isinstance(error, PolarProviderUnexpectedError):
            return self.count_unexpected_errors
        if isinstance(error, PolarProviderUnavailableError):
            return self.count_unavailable_errors
        if isinstance(error, PolarProviderTimeoutError):
            return self.count_timeout_errors
        if isinstance(error, PolarProviderExecutionError):
            return self.count_execution_errors
        return self.count_provider_errors


@dataclass(frozen=True)
class PolarProviderHealthSnapshot:
    """Immutable health and circuit telemetry for one provider identity."""

    provider: ProviderIdentity
    state: PolarProviderHealthState
    consecutive_failures: int
    total_successes: int
    total_failures: int
    total_rejections: int
    cooldown_remaining_s: float
    probe_in_flight: bool
    last_failure_type: str | None = None
    last_failure_message: str | None = None

    def __post_init__(self) -> None:
        _validate_identity(self.provider)
        if not isinstance(self.state, str) or self.state not in {
            "closed",
            "open",
            "half_open",
        }:
            raise ValueError(f"Unsupported provider health state {self.state!r}.")
        for name in (
            "consecutive_failures",
            "total_successes",
            "total_failures",
            "total_rejections",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer.")
        if (
            isinstance(self.cooldown_remaining_s, bool)
            or not isinstance(self.cooldown_remaining_s, (int, float))
            or not math.isfinite(float(self.cooldown_remaining_s))
            or self.cooldown_remaining_s < 0.0
        ):
            raise ValueError(
                "cooldown_remaining_s must be a non-negative finite number."
            )
        if not isinstance(self.probe_in_flight, bool):
            raise ValueError("probe_in_flight must be bool.")
        for name in ("last_failure_type", "last_failure_message"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} must be a string or None.")

    def as_mapping(self) -> dict[str, object]:
        """Return canonical JSON-like health telemetry for provenance."""
        return {
            "schema_version": POLAR_PROVIDER_HEALTH_SCHEMA_VERSION,
            "provider": self.provider.as_mapping(),
            "state": self.state,
            "consecutive_failures": self.consecutive_failures,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "total_rejections": self.total_rejections,
            "cooldown_remaining_s": self.cooldown_remaining_s,
            "probe_in_flight": self.probe_in_flight,
            "last_failure_type": self.last_failure_type,
            "last_failure_message": self.last_failure_message,
        }


class PolarProviderCircuitOpenError(PolarProviderError):
    """Raised internally when an open circuit rejects a provider invocation."""

    def __init__(self, snapshot: PolarProviderHealthSnapshot) -> None:
        if not isinstance(snapshot, PolarProviderHealthSnapshot):
            raise TypeError("snapshot must be a PolarProviderHealthSnapshot.")
        self.snapshot = snapshot
        super().__init__(
            f"Provider circuit is {snapshot.state} for {snapshot.provider.name}; "
            f"cooldown remaining {snapshot.cooldown_remaining_s:.6g} s."
        )


class PolarProviderUnexpectedError(PolarProviderError):
    """Typed wrapper used when health isolation contains an unexpected exception."""

    def __init__(self, provider: ProviderIdentity, error: Exception) -> None:
        _validate_identity(provider)
        if not isinstance(error, Exception):
            raise TypeError("error must be an Exception.")
        self.provider = provider
        self.original_type = type(error).__name__
        message = _safe_error_message(error)
        super().__init__(
            f"Provider {provider.name} raised unexpected {self.original_type}: {message}"
        )


@dataclass
class _HealthRecord:
    state: PolarProviderHealthState = "closed"
    consecutive_failures: int = 0
    total_successes: int = 0
    total_failures: int = 0
    total_rejections: int = 0
    opened_at_s: float | None = None
    probe_in_flight: bool = False
    last_failure_type: str | None = None
    last_failure_message: str | None = None
    generation: int = 0


@dataclass(frozen=True)
class _ProviderCallPermit:
    provider: ProviderIdentity
    generation: int
    probe: bool


class PolarProviderHealthRegistry:
    """Process-local, thread-safe health registry keyed by provider identity."""

    def __init__(
        self,
        policy: PolarProviderHealthPolicy | None = None,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._policy = policy or PolarProviderHealthPolicy()
        if not isinstance(self._policy, PolarProviderHealthPolicy):
            raise TypeError("policy must be a PolarProviderHealthPolicy or None.")
        self._clock = clock or time.monotonic
        if not callable(self._clock):
            raise TypeError("clock must be callable or None.")
        self._records: dict[ProviderIdentity, _HealthRecord] = {}
        self._lock = threading.RLock()
        self._generation = 0

    @property
    def policy(self) -> PolarProviderHealthPolicy:
        return self._policy

    def snapshot(self, provider: ProviderIdentity) -> PolarProviderHealthSnapshot:
        """Return current health without mutating or advancing circuit state."""
        _validate_identity(provider)
        with self._lock:
            record = self._records.get(provider)
            if record is None:
                record = _HealthRecord()
            return self._snapshot(provider, record, self._now())

    def snapshots(self) -> tuple[PolarProviderHealthSnapshot, ...]:
        """Return tracked providers in deterministic identity order."""
        with self._lock:
            now = self._now()
            identities = sorted(self._records, key=_identity_order)
            return tuple(
                self._snapshot(identity, self._records[identity], now)
                for identity in identities
            )

    def reset(self, provider: ProviderIdentity | None = None) -> None:
        """Reset one provider or clear every tracked provider atomically."""
        if provider is not None:
            _validate_identity(provider)
        with self._lock:
            if provider is None:
                self._records.clear()
            else:
                self._records.pop(provider, None)

    def _acquire(
        self,
        provider: ProviderIdentity,
    ) -> tuple[_ProviderCallPermit | None, PolarProviderHealthSnapshot]:
        _validate_identity(provider)
        with self._lock:
            now = self._now()
            record = self._records.get(provider)
            if record is None:
                record = _HealthRecord(generation=self._next_generation())
                self._records[provider] = record
            if record.state == "open":
                remaining = self._cooldown_remaining(record, now)
                if remaining > 0.0:
                    record.total_rejections += 1
                    return None, self._snapshot(provider, record, now)
                record.state = "half_open"
                record.probe_in_flight = True
                record.generation = self._next_generation()
                permit = _ProviderCallPermit(provider, record.generation, True)
                return permit, self._snapshot(provider, record, now)
            if record.state == "half_open":
                record.total_rejections += 1
                return None, self._snapshot(provider, record, now)
            permit = _ProviderCallPermit(provider, record.generation, False)
            return permit, self._snapshot(provider, record, now)

    def _record_success(
        self,
        permit: _ProviderCallPermit,
    ) -> PolarProviderHealthSnapshot:
        with self._lock:
            now = self._now()
            record = self._records.get(permit.provider)
            if record is None:
                return self._snapshot(permit.provider, _HealthRecord(), now)
            if permit.generation != record.generation:
                return self._snapshot(permit.provider, record, now)
            record.total_successes += 1
            if record.state == "half_open" and permit.probe:
                record.state = "closed"
                record.probe_in_flight = False
                record.opened_at_s = None
                record.generation = self._next_generation()
            if record.state == "closed":
                record.consecutive_failures = 0
                record.last_failure_type = None
                record.last_failure_message = None
            return self._snapshot(permit.provider, record, now)

    def _record_failure(
        self,
        permit: _ProviderCallPermit,
        error: PolarProviderError,
    ) -> tuple[PolarProviderHealthSnapshot, bool]:
        counted = self._policy.counts_failure(error)
        with self._lock:
            now = self._now()
            record = self._records.get(permit.provider)
            if record is None:
                return self._snapshot(permit.provider, _HealthRecord(), now), counted
            if permit.generation != record.generation:
                return self._snapshot(permit.provider, record, now), counted
            record.total_failures += 1
            record.last_failure_type = type(error).__name__
            record.last_failure_message = _safe_error_message(error)
            if not counted:
                self._release_neutral_locked(permit, record, now)
                return self._snapshot(permit.provider, record, now), False
            if record.state == "half_open" and permit.probe:
                record.consecutive_failures += 1
                self._open(record, now)
            elif record.state == "closed":
                record.consecutive_failures += 1
                if record.consecutive_failures >= self._policy.failure_threshold:
                    self._open(record, now)
            return self._snapshot(permit.provider, record, now), True

    def _record_neutral(
        self,
        permit: _ProviderCallPermit,
    ) -> PolarProviderHealthSnapshot:
        with self._lock:
            now = self._now()
            record = self._records.get(permit.provider)
            if record is None:
                return self._snapshot(permit.provider, _HealthRecord(), now)
            if permit.generation != record.generation:
                return self._snapshot(permit.provider, record, now)
            self._release_neutral_locked(permit, record, now)
            return self._snapshot(permit.provider, record, now)

    def _release_neutral_locked(
        self,
        permit: _ProviderCallPermit,
        record: _HealthRecord,
        now: float,
    ) -> None:
        if record.state == "half_open" and permit.probe:
            record.state = "open"
            record.probe_in_flight = False
            record.opened_at_s = now
            record.generation = self._next_generation()

    def _open(self, record: _HealthRecord, now: float) -> None:
        record.state = "open"
        record.probe_in_flight = False
        record.opened_at_s = now
        record.generation = self._next_generation()

    def _next_generation(self) -> int:
        self._generation += 1
        return self._generation

    def _snapshot(
        self,
        provider: ProviderIdentity,
        record: _HealthRecord,
        now: float,
    ) -> PolarProviderHealthSnapshot:
        return PolarProviderHealthSnapshot(
            provider=provider,
            state=record.state,
            consecutive_failures=record.consecutive_failures,
            total_successes=record.total_successes,
            total_failures=record.total_failures,
            total_rejections=record.total_rejections,
            cooldown_remaining_s=self._cooldown_remaining(record, now),
            probe_in_flight=record.probe_in_flight,
            last_failure_type=record.last_failure_type,
            last_failure_message=record.last_failure_message,
        )

    def _cooldown_remaining(self, record: _HealthRecord, now: float) -> float:
        if record.state != "open" or record.opened_at_s is None:
            return 0.0
        elapsed = max(0.0, now - record.opened_at_s)
        return max(0.0, float(self._policy.recovery_timeout_s) - elapsed)

    def _now(self) -> float:
        value = self._clock()
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError("health clock must return a finite number.")
        return float(value)


def _validate_identity(provider: ProviderIdentity) -> None:
    if not isinstance(provider, ProviderIdentity):
        raise TypeError("provider must be a ProviderIdentity.")


def _identity_order(provider: ProviderIdentity) -> tuple[str, str, str, str]:
    return (
        provider.name,
        provider.adapter_version,
        provider.backend_name,
        provider.backend_version,
    )


def _safe_error_message(error: BaseException) -> str:
    try:
        message = str(error)
    except Exception:
        message = f"<{type(error).__name__} message unavailable>"
    if len(message) > _MAX_ERROR_MESSAGE_LENGTH:
        return message[: _MAX_ERROR_MESSAGE_LENGTH - 3] + "..."
    return message
