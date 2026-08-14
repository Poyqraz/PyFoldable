"""Ordered provider fallback and bounded retry orchestration."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace
from typing import Literal, Mapping, Sequence

from .polar_cache import FilesystemPolarCache, generate_polar_cached
from .providers import (
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarProvider,
    PolarProviderCapabilityError,
    PolarProviderError,
    PolarProviderExecutionError,
    PolarProviderTimeoutError,
    PolarProviderUnavailableError,
    ProviderIdentity,
    generate_polar,
)


POLAR_ORCHESTRATION_SCHEMA_VERSION = 1

PolarProviderAttemptOutcome = Literal[
    "success",
    "capability_error",
    "unavailable",
    "timeout",
    "execution_error",
    "provider_error",
]
_POLAR_PROVIDER_ATTEMPT_OUTCOMES = {
    "success",
    "capability_error",
    "unavailable",
    "timeout",
    "execution_error",
    "provider_error",
}


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

    def __post_init__(self) -> None:
        if not isinstance(self.provider, ProviderIdentity):
            raise TypeError("provider must be a ProviderIdentity.")
        for name in ("provider_position", "attempt_number"):
            _validate_attempt_number(getattr(self, name), name=name)
        if self.outcome not in _POLAR_PROVIDER_ATTEMPT_OUTCOMES:
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
        }


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
) -> PolarGenerationResult:
    """Generate through an ordered provider chain with bounded per-provider retry."""
    chain = _validate_provider_chain(providers)
    policy = retry_policy or PolarRetryPolicy()
    if not isinstance(policy, PolarRetryPolicy):
        raise TypeError("retry_policy must be a PolarRetryPolicy or None.")
    if cache is not None and not isinstance(cache, FilesystemPolarCache):
        raise TypeError("cache must be a FilesystemPolarCache or None.")

    attempts: list[PolarProviderAttempt] = []
    last_error: PolarProviderError | None = None
    for provider_position, provider in enumerate(chain, start=1):
        attempt_number = 1
        while True:
            started = time.monotonic()
            try:
                result = _generate_with_optional_cache(provider, request, cache)
            except PolarProviderError as error:
                elapsed_s = time.monotonic() - started
                will_retry = policy.allows_retry(error, attempt_number)
                backoff_s = (
                    policy.backoff_after(attempt_number) if will_retry else 0.0
                )
                attempts.append(
                    PolarProviderAttempt(
                        provider=provider.identity,
                        provider_position=provider_position,
                        attempt_number=attempt_number,
                        outcome=_failure_outcome(error),
                        elapsed_s=elapsed_s,
                        will_retry=will_retry,
                        backoff_s=backoff_s,
                        error_type=type(error).__name__,
                        error_message=str(error),
                    )
                )
                last_error = error
                if not will_retry:
                    break
                if backoff_s > 0.0:
                    time.sleep(backoff_s)
                attempt_number += 1
                continue

            attempts.append(
                PolarProviderAttempt(
                    provider=provider.identity,
                    provider_position=provider_position,
                    attempt_number=attempt_number,
                    outcome="success",
                    elapsed_s=time.monotonic() - started,
                    cache_status=_cache_status(result.metadata),
                )
            )
            return _with_orchestration_provenance(
                result,
                provider_position=provider_position,
                attempts=attempts,
            )

    exhausted = PolarProviderChainExhaustedError(attempts)
    if last_error is not None:
        raise exhausted from last_error
    raise exhausted


def _validate_provider_chain(
    providers: Sequence[PolarProvider],
) -> tuple[PolarProvider, ...]:
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
    if not all(isinstance(provider, PolarProvider) for provider in chain):
        raise TypeError("providers must contain only PolarProvider objects.")
    identities = tuple(provider.identity for provider in chain)
    if len(set(identities)) != len(identities):
        raise ValueError("providers must not contain duplicate identities.")
    return chain


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
) -> PolarGenerationResult:
    metadata = dict(result.metadata)
    metadata["orchestration"] = {
        "schema_version": POLAR_ORCHESTRATION_SCHEMA_VERSION,
        "selected_provider": result.provider.as_mapping(),
        "selected_provider_position": provider_position,
        "attempt_count": len(attempts),
        "retry_count": sum(attempt.attempt_number > 1 for attempt in attempts),
        "fallback_used": provider_position > 1,
        "attempts": tuple(attempt.as_mapping() for attempt in attempts),
    }
    return replace(result, metadata=metadata)
