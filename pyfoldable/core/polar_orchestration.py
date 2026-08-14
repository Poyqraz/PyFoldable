"""Ordered provider fallback and bounded retry orchestration."""

from __future__ import annotations

import inspect
import math
import time
from dataclasses import dataclass, replace
from typing import Literal, Mapping, Sequence

from .polar_cache import FilesystemPolarCache, generate_polar_cached
from .polar_health import (
    PolarProviderCircuitOpenError,
    PolarProviderHealthRegistry,
    PolarProviderHealthSnapshot,
    PolarProviderHealthState,
    PolarProviderUnexpectedError,
    _ProviderCallPermit,
    _safe_error_message,
)
from .providers import (
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarProvider,
    PolarProviderCapabilityError,
    PolarProviderError,
    PolarProviderExecutionError,
    PolarProviderTimeoutError,
    PolarProviderUnavailableError,
    ProviderCapabilities,
    ProviderIdentity,
    generate_polar,
)


POLAR_ORCHESTRATION_SCHEMA_VERSION = 2

PolarProviderAttemptOutcome = Literal[
    "success",
    "capability_error",
    "unavailable",
    "timeout",
    "execution_error",
    "provider_error",
    "unexpected_error",
    "circuit_open",
]
_POLAR_PROVIDER_ATTEMPT_OUTCOMES = {
    "success",
    "capability_error",
    "unavailable",
    "timeout",
    "execution_error",
    "provider_error",
    "unexpected_error",
    "circuit_open",
}
_MISSING_PROVIDER_MEMBER = object()


@dataclass(frozen=True)
class PolarRetryPolicy:
    """Bounded per-provider retry policy for explicitly retryable failures."""

    max_attempts: int = 2
    initial_backoff_s: float = 0.05
    max_backoff_s: float = 0.5
    backoff_factor: float = 2.0
    retry_timeouts: bool = True
    retry_execution_errors: bool = False

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_attempts, bool)
            or not isinstance(self.max_attempts, int)
            or self.max_attempts < 1
        ):
            raise ValueError("max_attempts must be a positive integer.")
        for name in (
            "initial_backoff_s",
            "max_backoff_s",
            "backoff_factor",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite number.")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be a finite number.")
        if self.initial_backoff_s < 0.0:
            raise ValueError("initial_backoff_s must be non-negative.")
        if self.max_backoff_s < self.initial_backoff_s:
            raise ValueError("max_backoff_s must be at least initial_backoff_s.")
        if self.backoff_factor < 1.0:
            raise ValueError("backoff_factor must be at least one.")
        for name in ("retry_timeouts", "retry_execution_errors"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be bool.")

    def allows_retry(self, error: PolarProviderError, attempt_number: int) -> bool:
        """Return whether one failed attempt may be repeated on the same provider."""
        _validate_attempt_number(attempt_number)
        if not isinstance(error, PolarProviderError):
            raise TypeError("error must be a PolarProviderError.")
        if attempt_number >= self.max_attempts:
            return False
        if isinstance(error, PolarProviderTimeoutError):
            return self.retry_timeouts
        if isinstance(error, PolarProviderExecutionError):
            return self.retry_execution_errors
        return False

    def backoff_after(self, attempt_number: int) -> float:
        """Return bounded delay after a retryable failed attempt."""
        _validate_attempt_number(attempt_number)
        if self.initial_backoff_s == 0.0:
            return 0.0
        try:
            scaled = self.initial_backoff_s * (
                self.backoff_factor ** (attempt_number - 1)
            )
        except OverflowError:
            return float(self.max_backoff_s)
        return min(float(self.max_backoff_s), float(scaled))


@dataclass(frozen=True)
class PolarProviderAttempt:
    """Auditable outcome of one provider invocation or capability check."""

    provider: ProviderIdentity
    provider_position: int
    attempt_number: int
    outcome: PolarProviderAttemptOutcome
    elapsed_s: float
    will_retry: bool = False
    backoff_s: float = 0.0
    cache_status: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    circuit_state_before: PolarProviderHealthState | None = None
    circuit_state_after: PolarProviderHealthState | None = None
    circuit_probe: bool = False
    health_counted: bool = False
    health_consecutive_failures: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.provider, ProviderIdentity):
            raise TypeError("provider must be a ProviderIdentity.")
        for name in ("provider_position", "attempt_number"):
            _validate_attempt_number(getattr(self, name), name=name)
        if (
            not isinstance(self.outcome, str)
            or self.outcome not in _POLAR_PROVIDER_ATTEMPT_OUTCOMES
        ):
            raise ValueError(f"Unsupported provider attempt outcome {self.outcome!r}.")
        for name in ("elapsed_s", "backoff_s"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or value < 0.0
            ):
                raise ValueError(f"{name} must be a non-negative finite number.")
        if not isinstance(self.will_retry, bool):
            raise ValueError("will_retry must be bool.")
        for name in ("cache_status", "error_type", "error_message"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} must be a string or None.")
        for name in ("circuit_state_before", "circuit_state_after"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, str)
                or value not in {"closed", "open", "half_open"}
            ):
                raise ValueError(f"{name} must be a circuit state or None.")
        for name in ("circuit_probe", "health_counted"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be bool.")
        if self.health_consecutive_failures is not None and (
            isinstance(self.health_consecutive_failures, bool)
            or not isinstance(self.health_consecutive_failures, int)
            or self.health_consecutive_failures < 0
        ):
            raise ValueError(
                "health_consecutive_failures must be a non-negative integer or None."
            )

    def as_mapping(self) -> dict[str, object]:
        """Return canonical JSON-like provenance for result metadata."""
        return {
            "provider": self.provider.as_mapping(),
            "provider_position": self.provider_position,
            "attempt_number": self.attempt_number,
            "outcome": self.outcome,
            "elapsed_s": self.elapsed_s,
            "will_retry": self.will_retry,
            "backoff_s": self.backoff_s,
            "cache_status": self.cache_status,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "circuit_state_before": self.circuit_state_before,
            "circuit_state_after": self.circuit_state_after,
            "circuit_probe": self.circuit_probe,
            "health_counted": self.health_counted,
            "health_consecutive_failures": self.health_consecutive_failures,
        }


@dataclass(frozen=True)
class _ProviderEntry:
    provider: PolarProvider
    identity: ProviderIdentity


@dataclass(frozen=True)
class _ProviderContract:
    identity: ProviderIdentity
    capabilities: ProviderCapabilities
    delegate: PolarProvider

    def generate(self, request: PolarGenerationRequest) -> PolarGenerationResult:
        return self.delegate.generate(request)


class PolarProviderChainExhaustedError(PolarProviderError):
    """Raised after every configured provider has failed or been rejected."""

    def __init__(self, attempts: Sequence[PolarProviderAttempt]) -> None:
        self.attempts = tuple(attempts)
        summary = ", ".join(
            f"{attempt.provider.name}#{attempt.attempt_number}:{attempt.outcome}"
            for attempt in self.attempts
        )
        super().__init__(f"Polar provider chain exhausted ({summary}).")


def generate_polar_orchestrated(
    providers: Sequence[PolarProvider],
    request: PolarGenerationRequest,
    *,
    retry_policy: PolarRetryPolicy | None = None,
    cache: FilesystemPolarCache | None = None,
    health_registry: PolarProviderHealthRegistry | None = None,
) -> PolarGenerationResult:
    """Generate through an ordered provider chain with bounded per-provider retry."""
    chain = _validate_provider_chain(providers)
    policy = retry_policy or PolarRetryPolicy()
    if not isinstance(policy, PolarRetryPolicy):
        raise TypeError("retry_policy must be a PolarRetryPolicy or None.")
    if cache is not None and not isinstance(cache, FilesystemPolarCache):
        raise TypeError("cache must be a FilesystemPolarCache or None.")
    if health_registry is not None and not isinstance(
        health_registry,
        PolarProviderHealthRegistry,
    ):
        raise TypeError(
            "health_registry must be a PolarProviderHealthRegistry or None."
        )

    attempts: list[PolarProviderAttempt] = []
    last_error: PolarProviderError | None = None
    for provider_position, entry in enumerate(chain, start=1):
        provider = entry.provider
        identity = entry.identity
        capability_started = time.monotonic()
        try:
            capabilities = provider.capabilities
            request.validate_capabilities(capabilities)
        except PolarProviderCapabilityError as error:
            snapshot = _optional_health_snapshot(health_registry, identity)
            attempts.append(
                _failure_attempt(
                    provider=identity,
                    provider_position=provider_position,
                    attempt_number=1,
                    error=error,
                    elapsed_s=time.monotonic() - capability_started,
                    before=snapshot,
                    after=snapshot,
                )
            )
            last_error = error
            continue
        except Exception as error:
            if (
                health_registry is None
                or not health_registry.policy.isolate_unexpected_errors
            ):
                raise
            wrapped = PolarProviderUnexpectedError(identity, error)
            wrapped.__cause__ = error
            permit, before = health_registry._acquire(identity)
            after, counted = _record_health_failure(
                health_registry,
                permit,
                wrapped,
            )
            attempts.append(
                _failure_attempt(
                    provider=identity,
                    provider_position=provider_position,
                    attempt_number=1,
                    error=wrapped,
                    elapsed_s=time.monotonic() - capability_started,
                    before=before,
                    after=after if after is not None else before,
                    permit=permit,
                    health_counted=counted,
                )
            )
            last_error = wrapped
            continue

        contract = _ProviderContract(identity, capabilities, provider)

        attempt_number = 1
        while True:
            started = time.monotonic()
            cached = _cache_first_read(
                contract,
                request,
                cache,
                health_registry,
            )
            if cached is not None:
                snapshot = _optional_health_snapshot(
                    health_registry,
                    identity,
                )
                attempts.append(
                    _success_attempt(
                        provider=identity,
                        provider_position=provider_position,
                        attempt_number=attempt_number,
                        result=cached,
                        elapsed_s=time.monotonic() - started,
                        before=snapshot,
                        after=snapshot,
                    )
                )
                return _with_orchestration_provenance(
                    cached,
                    provider_position=provider_position,
                    attempts=attempts,
                    chain=chain,
                    health_registry=health_registry,
                )

            permit: _ProviderCallPermit | None = None
            before: PolarProviderHealthSnapshot | None = None
            if health_registry is not None:
                permit, before = health_registry._acquire(identity)
                if permit is None:
                    error = PolarProviderCircuitOpenError(before)
                    attempts.append(
                        _failure_attempt(
                            provider=identity,
                            provider_position=provider_position,
                            attempt_number=attempt_number,
                            error=error,
                            elapsed_s=time.monotonic() - started,
                            before=before,
                            after=before,
                        )
                    )
                    last_error = error
                    break

            try:
                result = _generate_with_optional_cache(contract, request, cache)
            except PolarProviderError as error:
                elapsed_s = time.monotonic() - started
                after, counted = _record_health_failure(
                    health_registry,
                    permit,
                    error,
                )
                will_retry = policy.allows_retry(error, attempt_number) and (
                    after is None or after.state == "closed"
                )
                backoff_s = (
                    policy.backoff_after(attempt_number) if will_retry else 0.0
                )
                attempts.append(
                    _failure_attempt(
                        provider=identity,
                        provider_position=provider_position,
                        attempt_number=attempt_number,
                        error=error,
                        elapsed_s=elapsed_s,
                        will_retry=will_retry,
                        backoff_s=backoff_s,
                        before=before,
                        after=after,
                        permit=permit,
                        health_counted=counted,
                    )
                )
                last_error = error
                if not will_retry:
                    break
                if backoff_s > 0.0:
                    time.sleep(backoff_s)
                attempt_number += 1
                continue
            except Exception as error:
                if (
                    health_registry is None
                    or not health_registry.policy.isolate_unexpected_errors
                ):
                    if health_registry is not None and permit is not None:
                        health_registry._record_neutral(permit)
                    raise
                wrapped = PolarProviderUnexpectedError(identity, error)
                wrapped.__cause__ = error
                after, counted = _record_health_failure(
                    health_registry,
                    permit,
                    wrapped,
                )
                attempts.append(
                    _failure_attempt(
                        provider=identity,
                        provider_position=provider_position,
                        attempt_number=attempt_number,
                        error=wrapped,
                        elapsed_s=time.monotonic() - started,
                        before=before,
                        after=after,
                        permit=permit,
                        health_counted=counted,
                    )
                )
                last_error = wrapped
                break
            except BaseException:
                if health_registry is not None and permit is not None:
                    health_registry._record_neutral(permit)
                raise

            after = _record_health_success(
                health_registry,
                permit,
                result,
            )
            attempts.append(
                _success_attempt(
                    provider=identity,
                    provider_position=provider_position,
                    attempt_number=attempt_number,
                    result=result,
                    elapsed_s=time.monotonic() - started,
                    before=before,
                    after=after,
                    permit=permit,
                )
            )
            return _with_orchestration_provenance(
                result,
                provider_position=provider_position,
                attempts=attempts,
                chain=chain,
                health_registry=health_registry,
            )

    exhausted = PolarProviderChainExhaustedError(attempts)
    if last_error is not None:
        raise exhausted from last_error
    raise exhausted


def _validate_provider_chain(
    providers: Sequence[PolarProvider],
) -> tuple[_ProviderEntry, ...]:
    if isinstance(providers, (str, bytes)):
        raise TypeError("providers must be an ordered sequence of PolarProvider objects.")
    try:
        chain = tuple(providers)
    except TypeError as error:
        raise TypeError(
            "providers must be an ordered sequence of PolarProvider objects."
        ) from error
    if not chain:
        raise ValueError("providers must contain at least one provider.")
    entries: list[_ProviderEntry] = []
    for provider in chain:
        if not all(
            inspect.getattr_static(
                provider,
                name,
                _MISSING_PROVIDER_MEMBER,
            )
            is not _MISSING_PROVIDER_MEMBER
            for name in ("identity", "capabilities", "generate")
        ):
            raise TypeError("providers must contain only PolarProvider objects.")
        identity = provider.identity
        if not isinstance(identity, ProviderIdentity):
            raise TypeError("provider identity must be a ProviderIdentity.")
        entries.append(_ProviderEntry(provider, identity))
    identities = tuple(entry.identity for entry in entries)
    if len(set(identities)) != len(identities):
        raise ValueError("providers must not contain duplicate identities.")
    return tuple(entries)


def _validate_attempt_number(value: int, *, name: str = "attempt_number") -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer.")


def _generate_with_optional_cache(
    provider: PolarProvider,
    request: PolarGenerationRequest,
    cache: FilesystemPolarCache | None,
) -> PolarGenerationResult:
    if cache is None:
        return generate_polar(provider, request)
    return generate_polar_cached(provider, request, cache)


def _failure_outcome(error: PolarProviderError) -> PolarProviderAttemptOutcome:
    if isinstance(error, PolarProviderCapabilityError):
        return "capability_error"
    if isinstance(error, PolarProviderUnavailableError):
        return "unavailable"
    if isinstance(error, PolarProviderTimeoutError):
        return "timeout"
    if isinstance(error, PolarProviderExecutionError):
        return "execution_error"
    if isinstance(error, PolarProviderUnexpectedError):
        return "unexpected_error"
    if isinstance(error, PolarProviderCircuitOpenError):
        return "circuit_open"
    return "provider_error"


def _cache_status(metadata: Mapping[str, object]) -> str | None:
    cache_metadata = metadata.get("cache")
    if not isinstance(cache_metadata, Mapping):
        return None
    status = cache_metadata.get("status")
    return status if isinstance(status, str) else None


def _with_orchestration_provenance(
    result: PolarGenerationResult,
    *,
    provider_position: int,
    attempts: Sequence[PolarProviderAttempt],
    chain: Sequence[_ProviderEntry],
    health_registry: PolarProviderHealthRegistry | None,
) -> PolarGenerationResult:
    metadata = dict(result.metadata)
    metadata["orchestration"] = {
        "schema_version": POLAR_ORCHESTRATION_SCHEMA_VERSION,
        "selected_provider": result.provider.as_mapping(),
        "selected_provider_position": provider_position,
        "attempt_count": len(attempts),
        "retry_count": sum(attempt.attempt_number > 1 for attempt in attempts),
        "fallback_used": provider_position > 1,
        "health_enabled": health_registry is not None,
        "circuit_rejection_count": sum(
            attempt.outcome == "circuit_open" for attempt in attempts
        ),
        "unexpected_error_count": sum(
            attempt.outcome == "unexpected_error" for attempt in attempts
        ),
        "attempts": tuple(attempt.as_mapping() for attempt in attempts),
    }
    if health_registry is not None:
        metadata["orchestration"]["provider_health"] = tuple(
            health_registry.snapshot(entry.identity).as_mapping()
            for entry in chain
        )
    return replace(result, metadata=metadata)


def _cache_first_read(
    provider: PolarProvider,
    request: PolarGenerationRequest,
    cache: FilesystemPolarCache | None,
    health_registry: PolarProviderHealthRegistry | None,
) -> PolarGenerationResult | None:
    if cache is None or health_registry is None:
        return None
    return cache._get_after_capability_validation(provider, request)


def _optional_health_snapshot(
    health_registry: PolarProviderHealthRegistry | None,
    provider: ProviderIdentity,
) -> PolarProviderHealthSnapshot | None:
    if health_registry is None:
        return None
    return health_registry.snapshot(provider)


def _record_health_failure(
    health_registry: PolarProviderHealthRegistry | None,
    permit: _ProviderCallPermit | None,
    error: PolarProviderError,
) -> tuple[PolarProviderHealthSnapshot | None, bool]:
    if health_registry is None or permit is None:
        return None, False
    return health_registry._record_failure(permit, error)


def _record_health_success(
    health_registry: PolarProviderHealthRegistry | None,
    permit: _ProviderCallPermit | None,
    result: PolarGenerationResult,
) -> PolarProviderHealthSnapshot | None:
    if health_registry is None or permit is None:
        return None
    if _cache_status(result.metadata) == "hit":
        return health_registry._record_neutral(permit)
    return health_registry._record_success(permit)


def _failure_attempt(
    *,
    provider: ProviderIdentity,
    provider_position: int,
    attempt_number: int,
    error: PolarProviderError,
    elapsed_s: float,
    before: PolarProviderHealthSnapshot | None,
    after: PolarProviderHealthSnapshot | None,
    will_retry: bool = False,
    backoff_s: float = 0.0,
    permit: _ProviderCallPermit | None = None,
    health_counted: bool = False,
) -> PolarProviderAttempt:
    return PolarProviderAttempt(
        provider=provider,
        provider_position=provider_position,
        attempt_number=attempt_number,
        outcome=_failure_outcome(error),
        elapsed_s=elapsed_s,
        will_retry=will_retry,
        backoff_s=backoff_s,
        error_type=type(error).__name__,
        error_message=_safe_error_message(error),
        circuit_state_before=before.state if before is not None else None,
        circuit_state_after=after.state if after is not None else None,
        circuit_probe=permit.probe if permit is not None else False,
        health_counted=health_counted,
        health_consecutive_failures=(
            after.consecutive_failures if after is not None else None
        ),
    )


def _success_attempt(
    *,
    provider: ProviderIdentity,
    provider_position: int,
    attempt_number: int,
    result: PolarGenerationResult,
    elapsed_s: float,
    before: PolarProviderHealthSnapshot | None,
    after: PolarProviderHealthSnapshot | None,
    permit: _ProviderCallPermit | None = None,
) -> PolarProviderAttempt:
    return PolarProviderAttempt(
        provider=provider,
        provider_position=provider_position,
        attempt_number=attempt_number,
        outcome="success",
        elapsed_s=elapsed_s,
        cache_status=_cache_status(result.metadata),
        circuit_state_before=before.state if before is not None else None,
        circuit_state_after=after.state if after is not None else None,
        circuit_probe=permit.probe if permit is not None else False,
        health_consecutive_failures=(
            after.consecutive_failures if after is not None else None
        ),
    )
