"""Ordered polar provider fallback, retry, provenance, and cache behavior."""

from __future__ import annotations

from dataclasses import replace

import pytest

import pyfoldable.core.polar_orchestration as orchestration
from pyfoldable.core import (
    AirfoilDefinition,
    FilesystemPolarCache,
    POLAR_ORCHESTRATION_SCHEMA_VERSION,
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarPointResult,
    PolarProviderCapabilityError,
    PolarProviderAttempt,
    PolarProviderChainExhaustedError,
    PolarProviderExecutionError,
    PolarProviderTimeoutError,
    PolarProviderUnavailableError,
    PolarRetryPolicy,
    ProviderCapabilities,
    ProviderIdentity,
    generate_polar_orchestrated,
)


AIRFOIL = AirfoilDefinition(
    id="ORCHESTRATION-TEST",
    source="fixture",
    coordinates=((1.0, 0.0), (0.5, 0.1), (0.0, 0.0), (0.5, -0.1), (1.0, 0.0)),
)
PRIMARY = ProviderIdentity("primary", "1", "primary-backend", "2")
SECONDARY = ProviderIdentity("secondary", "1", "secondary-backend", "3")
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
    request = PolarGenerationRequest(
        airfoil=AIRFOIL,
        alpha_rad=(-0.1, 0.0, 0.1),
        reynolds=250_000.0,
        scenario_id="orchestration",
    )
    return replace(request, **changes)


def _result(
    request: PolarGenerationRequest,
    identity: ProviderIdentity,
    *,
    metadata=None,
) -> PolarGenerationResult:
    return PolarGenerationResult(
        request=request,
        provider=identity,
        points=tuple(
            PolarPointResult(
                alpha,
                "converged",
                cl=10.0 * alpha,
                cd=0.01 + alpha * alpha,
                cm=-0.02,
            )
            for alpha in request.alpha_rad
        ),
        elapsed_s=0.1,
        metadata=metadata or {},
    )


class ScriptedProvider:
    capabilities = CAPABILITIES

    def __init__(
        self,
        identity: ProviderIdentity,
        outcomes,
        *,
        capabilities: ProviderCapabilities = CAPABILITIES,
    ) -> None:
        self.identity = identity
        self.capabilities = capabilities
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate(self, request: PolarGenerationRequest) -> PolarGenerationResult:
        self.calls += 1
        if not self.outcomes:
            raise AssertionError("Provider was called more times than scripted.")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        metadata = outcome if isinstance(outcome, dict) else {}
        return _result(request, self.identity, metadata=metadata)


def test_primary_success_records_selected_provider_and_preserves_metadata() -> None:
    primary = ScriptedProvider(PRIMARY, [{"backend_detail": "kept"}])
    secondary = ScriptedProvider(SECONDARY, ["success"])

    result = generate_polar_orchestrated((primary, secondary), _request())

    provenance = result.metadata["orchestration"]
    assert result.provider == PRIMARY
    assert result.metadata["backend_detail"] == "kept"
    assert provenance["schema_version"] == POLAR_ORCHESTRATION_SCHEMA_VERSION
    assert provenance["selected_provider"] == PRIMARY.as_mapping()
    assert provenance["selected_provider_position"] == 1
    assert provenance["attempt_count"] == 1
    assert provenance["retry_count"] == 0
    assert provenance["fallback_used"] is False
    assert provenance["attempts"][0]["outcome"] == "success"
    assert secondary.calls == 0


def test_timeout_is_retried_with_bounded_backoff(monkeypatch) -> None:
    primary = ScriptedProvider(
        PRIMARY,
        [PolarProviderTimeoutError("slow"), "success"],
    )
    sleeps = []
    monkeypatch.setattr(orchestration.time, "sleep", sleeps.append)
    policy = PolarRetryPolicy(
        max_attempts=3,
        initial_backoff_s=0.1,
        max_backoff_s=0.2,
        backoff_factor=2.0,
    )

    result = generate_polar_orchestrated(
        (primary,),
        _request(),
        retry_policy=policy,
    )

    attempts = result.metadata["orchestration"]["attempts"]
    assert primary.calls == 2
    assert sleeps == [0.1]
    assert tuple(attempt["outcome"] for attempt in attempts) == (
        "timeout",
        "success",
    )
    assert attempts[0]["will_retry"] is True
    assert attempts[0]["backoff_s"] == 0.1
    assert result.metadata["orchestration"]["retry_count"] == 1


def test_exhausted_timeout_retries_then_falls_back() -> None:
    primary = ScriptedProvider(
        PRIMARY,
        [PolarProviderTimeoutError("first"), PolarProviderTimeoutError("second")],
    )
    secondary = ScriptedProvider(SECONDARY, ["success"])
    policy = PolarRetryPolicy(max_attempts=2, initial_backoff_s=0.0)

    result = generate_polar_orchestrated(
        (primary, secondary),
        _request(),
        retry_policy=policy,
    )

    provenance = result.metadata["orchestration"]
    assert primary.calls == 2
    assert secondary.calls == 1
    assert result.provider == SECONDARY
    assert provenance["fallback_used"] is True
    assert tuple(item["outcome"] for item in provenance["attempts"]) == (
        "timeout",
        "timeout",
        "success",
    )
    assert tuple(item["provider_position"] for item in provenance["attempts"]) == (
        1,
        1,
        2,
    )


def test_execution_error_falls_back_without_retry_by_default() -> None:
    primary = ScriptedProvider(PRIMARY, [PolarProviderExecutionError("invalid output")])
    secondary = ScriptedProvider(SECONDARY, ["success"])

    result = generate_polar_orchestrated((primary, secondary), _request())

    assert primary.calls == 1
    assert secondary.calls == 1
    assert tuple(
        attempt["outcome"]
        for attempt in result.metadata["orchestration"]["attempts"]
    ) == ("execution_error", "success")


def test_execution_error_retry_requires_explicit_opt_in() -> None:
    primary = ScriptedProvider(
        PRIMARY,
        [PolarProviderExecutionError("transient"), "success"],
    )
    policy = PolarRetryPolicy(
        max_attempts=2,
        initial_backoff_s=0.0,
        retry_execution_errors=True,
    )

    result = generate_polar_orchestrated(
        (primary,),
        _request(),
        retry_policy=policy,
    )

    assert primary.calls == 2
    assert result.metadata["orchestration"]["retry_count"] == 1


def test_unavailable_provider_falls_back_without_retry() -> None:
    primary = ScriptedProvider(
        PRIMARY,
        [PolarProviderUnavailableError("not installed")],
    )
    secondary = ScriptedProvider(SECONDARY, ["success"])
    policy = PolarRetryPolicy(max_attempts=5, initial_backoff_s=0.0)

    result = generate_polar_orchestrated(
        (primary, secondary),
        _request(),
        retry_policy=policy,
    )

    assert primary.calls == 1
    assert secondary.calls == 1
    first = result.metadata["orchestration"]["attempts"][0]
    assert first["outcome"] == "unavailable"
    assert first["will_retry"] is False


def test_capability_mismatch_skips_provider_without_invoking_backend() -> None:
    limited = replace(CAPABILITIES, supports_mach=False)
    primary = ScriptedProvider(PRIMARY, ["must-not-run"], capabilities=limited)
    secondary = ScriptedProvider(SECONDARY, ["success"])

    result = generate_polar_orchestrated(
        (primary, secondary),
        _request(mach=0.2),
    )

    first = result.metadata["orchestration"]["attempts"][0]
    assert primary.calls == 0
    assert secondary.calls == 1
    assert first["outcome"] == "capability_error"
    assert first["error_type"] == PolarProviderCapabilityError.__name__


def test_exhausted_chain_exposes_ordered_attempts_and_last_cause() -> None:
    primary = ScriptedProvider(
        PRIMARY,
        [PolarProviderUnavailableError("missing")],
    )
    secondary = ScriptedProvider(
        SECONDARY,
        [PolarProviderExecutionError("failed")],
    )

    with pytest.raises(PolarProviderChainExhaustedError) as captured:
        generate_polar_orchestrated((primary, secondary), _request())

    assert tuple(attempt.outcome for attempt in captured.value.attempts) == (
        "unavailable",
        "execution_error",
    )
    assert "primary#1:unavailable" in str(captured.value)
    assert "secondary#1:execution_error" in str(captured.value)
    assert isinstance(captured.value.__cause__, PolarProviderExecutionError)


def test_unexpected_provider_bug_is_not_masked_or_fallen_back() -> None:
    primary = ScriptedProvider(PRIMARY, [RuntimeError("programming bug")])
    secondary = ScriptedProvider(SECONDARY, ["success"])

    with pytest.raises(RuntimeError, match="programming bug"):
        generate_polar_orchestrated((primary, secondary), _request())

    assert primary.calls == 1
    assert secondary.calls == 0


def test_fallback_provider_uses_its_own_cache_identity(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    primary = ScriptedProvider(
        PRIMARY,
        [
            PolarProviderUnavailableError("missing"),
            PolarProviderUnavailableError("missing"),
        ],
    )
    secondary = ScriptedProvider(SECONDARY, ["success"])
    request = _request()

    generated = generate_polar_orchestrated(
        (primary, secondary),
        request,
        cache=cache,
    )
    loaded = generate_polar_orchestrated(
        (primary, secondary),
        request,
        cache=cache,
    )

    assert generated.metadata["cache"]["status"] == "miss"
    assert loaded.metadata["cache"]["status"] == "hit"
    assert loaded.metadata["orchestration"]["attempts"][-1]["cache_status"] == "hit"
    assert primary.calls == 2
    assert secondary.calls == 1
    assert cache.entry_path(SECONDARY, request).is_file()
    assert not cache.entry_path(PRIMARY, request).exists()


def test_primary_cache_hit_avoids_backend_invocation(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    request = _request()
    cache.put(_result(request, PRIMARY))
    primary = ScriptedProvider(PRIMARY, [PolarProviderUnavailableError("must-not-run")])

    result = generate_polar_orchestrated((primary,), request, cache=cache)

    assert primary.calls == 0
    assert result.metadata["cache"]["status"] == "hit"
    assert result.metadata["orchestration"]["attempts"][0]["cache_status"] == "hit"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"max_attempts": 0}, "max_attempts"),
        ({"max_attempts": True}, "max_attempts"),
        ({"initial_backoff_s": -1.0}, "initial_backoff_s"),
        (
            {"initial_backoff_s": 0.2, "max_backoff_s": 0.1},
            "max_backoff_s",
        ),
        ({"backoff_factor": 0.5}, "backoff_factor"),
        ({"max_backoff_s": float("nan")}, "max_backoff_s"),
        ({"retry_timeouts": 1}, "retry_timeouts"),
        ({"retry_execution_errors": "yes"}, "retry_execution_errors"),
    ],
)
def test_retry_policy_is_strictly_validated(changes, message) -> None:
    with pytest.raises(ValueError, match=message):
        PolarRetryPolicy(**changes)


def test_backoff_is_exponential_and_capped() -> None:
    policy = PolarRetryPolicy(
        initial_backoff_s=0.1,
        max_backoff_s=0.25,
        backoff_factor=2.0,
    )

    assert tuple(policy.backoff_after(attempt) for attempt in range(1, 5)) == (
        0.1,
        0.2,
        0.25,
        0.25,
    )
    with pytest.raises(ValueError, match="attempt_number"):
        policy.backoff_after(0)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"provider_position": 0}, "provider_position"),
        ({"attempt_number": True}, "attempt_number"),
        ({"outcome": "unknown"}, "outcome"),
        ({"elapsed_s": float("nan")}, "elapsed_s"),
        ({"backoff_s": -1.0}, "backoff_s"),
        ({"will_retry": 1}, "will_retry"),
        ({"cache_status": 1}, "cache_status"),
        ({"error_type": object()}, "error_type"),
    ],
)
def test_provider_attempt_is_strictly_validated(changes, message) -> None:
    values = {
        "provider": PRIMARY,
        "provider_position": 1,
        "attempt_number": 1,
        "outcome": "success",
        "elapsed_s": 0.0,
    }
    values.update(changes)

    with pytest.raises((TypeError, ValueError), match=message):
        PolarProviderAttempt(**values)


def test_timeout_retry_can_be_disabled() -> None:
    primary = ScriptedProvider(PRIMARY, [PolarProviderTimeoutError("slow")])
    secondary = ScriptedProvider(SECONDARY, ["success"])
    policy = PolarRetryPolicy(
        max_attempts=3,
        initial_backoff_s=0.0,
        retry_timeouts=False,
    )

    result = generate_polar_orchestrated(
        (primary, secondary),
        _request(),
        retry_policy=policy,
    )

    assert primary.calls == 1
    assert result.provider == SECONDARY


def test_provider_chain_rejects_empty_duplicate_and_invalid_entries() -> None:
    primary = ScriptedProvider(PRIMARY, ["success"])
    duplicate = ScriptedProvider(PRIMARY, ["success"])

    with pytest.raises(ValueError, match="at least one"):
        generate_polar_orchestrated((), _request())
    with pytest.raises(ValueError, match="duplicate identities"):
        generate_polar_orchestrated((primary, duplicate), _request())
    with pytest.raises(TypeError, match="PolarProvider"):
        generate_polar_orchestrated((object(),), _request())
    with pytest.raises(TypeError, match="ordered sequence"):
        generate_polar_orchestrated("primary", _request())
