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
    PolarProviderHealthPolicy,
    PolarProviderHealthRegistry,
    PolarProviderResultRejectedError,
    PolarResultQualificationPolicy,
    PolarProviderTimeoutError,
    PolarProviderUnavailableError,
    PolarProviderUnexpectedError,
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


class ResultProvider:
    def __init__(self, identity: ProviderIdentity, statuses: tuple[str, ...]) -> None:
        self.identity = identity
        self.statuses = statuses
        self.calls = 0
        self.capabilities = replace(
            CAPABILITIES,
            supports_pointwise_confidence="low_confidence" in statuses,
        )

    def generate(self, request: PolarGenerationRequest) -> PolarGenerationResult:
        self.calls += 1
        points = []
        for alpha, status in zip(request.alpha_rad, self.statuses):
            if status == "not_converged":
                points.append(PolarPointResult(alpha, status, message="fixture"))
            else:
                points.append(
                    PolarPointResult(
                        alpha,
                        status,
                        cl=10.0 * alpha,
                        cd=0.01 + alpha * alpha,
                        cm=-0.02,
                        confidence=0.4 if status == "low_confidence" else None,
                    )
                )
        return PolarGenerationResult(
            request=request,
            provider=self.identity,
            points=tuple(points),
            elapsed_s=0.1,
        )


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


def test_health_threshold_opens_circuit_and_suppresses_planned_retry() -> None:
    primary = ScriptedProvider(PRIMARY, [PolarProviderTimeoutError("slow")])
    secondary = ScriptedProvider(SECONDARY, ["success"])
    registry = PolarProviderHealthRegistry(
        PolarProviderHealthPolicy(failure_threshold=1, recovery_timeout_s=60.0)
    )
    retry = PolarRetryPolicy(max_attempts=3, initial_backoff_s=0.0)

    result = generate_polar_orchestrated(
        (primary, secondary),
        _request(),
        retry_policy=retry,
        health_registry=registry,
    )

    first = result.metadata["orchestration"]["attempts"][0]
    assert primary.calls == 1
    assert secondary.calls == 1
    assert first["outcome"] == "timeout"
    assert first["will_retry"] is False
    assert first["health_counted"] is True
    assert first["circuit_state_before"] == "closed"
    assert first["circuit_state_after"] == "open"
    assert registry.snapshot(PRIMARY).state == "open"


def test_open_circuit_is_audited_and_falls_back_without_backend_call() -> None:
    primary = ScriptedProvider(PRIMARY, [PolarProviderTimeoutError("opens")])
    secondary = ScriptedProvider(SECONDARY, ["success", "success"])
    registry = PolarProviderHealthRegistry(
        PolarProviderHealthPolicy(failure_threshold=1, recovery_timeout_s=60.0)
    )
    retry = PolarRetryPolicy(max_attempts=1)
    generate_polar_orchestrated(
        (primary, secondary),
        _request(),
        retry_policy=retry,
        health_registry=registry,
    )

    result = generate_polar_orchestrated(
        (primary, secondary),
        _request(scenario_id="second"),
        retry_policy=retry,
        health_registry=registry,
    )

    provenance = result.metadata["orchestration"]
    assert primary.calls == 1
    assert secondary.calls == 2
    assert provenance["attempts"][0]["outcome"] == "circuit_open"
    assert provenance["circuit_rejection_count"] == 1
    assert registry.snapshot(PRIMARY).total_rejections == 1


def test_unexpected_exception_is_isolated_counted_and_fallen_back() -> None:
    primary = ScriptedProvider(PRIMARY, [RuntimeError("backend bug")])
    secondary = ScriptedProvider(SECONDARY, ["success"])
    registry = PolarProviderHealthRegistry(
        PolarProviderHealthPolicy(failure_threshold=1)
    )

    result = generate_polar_orchestrated(
        (primary, secondary),
        _request(),
        health_registry=registry,
    )

    provenance = result.metadata["orchestration"]
    first = provenance["attempts"][0]
    assert result.provider == SECONDARY
    assert first["outcome"] == "unexpected_error"
    assert first["error_type"] == PolarProviderUnexpectedError.__name__
    assert "RuntimeError" in first["error_message"]
    assert first["health_counted"] is True
    assert provenance["unexpected_error_count"] == 1
    assert registry.snapshot(PRIMARY).state == "open"


def test_unprintable_unexpected_exception_cannot_break_fallback_telemetry() -> None:
    class UnprintableError(Exception):
        def __str__(self) -> str:
            raise RuntimeError("broken exception formatter")

    primary = ScriptedProvider(PRIMARY, [UnprintableError()])
    secondary = ScriptedProvider(SECONDARY, ["success"])
    registry = PolarProviderHealthRegistry(
        PolarProviderHealthPolicy(failure_threshold=1)
    )

    result = generate_polar_orchestrated(
        (primary, secondary),
        _request(),
        health_registry=registry,
    )

    first = result.metadata["orchestration"]["attempts"][0]
    assert result.provider == SECONDARY
    assert first["outcome"] == "unexpected_error"
    assert "message unavailable" in first["error_message"]
    assert "message unavailable" in registry.snapshot(PRIMARY).last_failure_message


def test_exhausted_unexpected_error_preserves_original_exception_chain() -> None:
    primary = ScriptedProvider(PRIMARY, [RuntimeError("root bug")])
    registry = PolarProviderHealthRegistry()

    with pytest.raises(PolarProviderChainExhaustedError) as captured:
        generate_polar_orchestrated(
            (primary,),
            _request(),
            health_registry=registry,
        )

    wrapped = captured.value.__cause__
    assert isinstance(wrapped, PolarProviderUnexpectedError)
    assert isinstance(wrapped.__cause__, RuntimeError)
    assert str(wrapped.__cause__) == "root bug"


def test_unexpected_exception_is_not_isolated_when_policy_disables_it() -> None:
    primary = ScriptedProvider(PRIMARY, [RuntimeError("surface this")])
    secondary = ScriptedProvider(SECONDARY, ["success"])
    registry = PolarProviderHealthRegistry(
        PolarProviderHealthPolicy(isolate_unexpected_errors=False)
    )

    with pytest.raises(RuntimeError, match="surface this"):
        generate_polar_orchestrated(
            (primary, secondary),
            _request(),
            health_registry=registry,
        )

    assert secondary.calls == 0
    assert registry.snapshot(PRIMARY).state == "closed"
    assert registry.snapshot(PRIMARY).total_failures == 0


def test_unexpected_capabilities_failure_is_isolated_and_fallen_back() -> None:
    class BrokenCapabilitiesProvider:
        identity = PRIMARY

        @property
        def capabilities(self):
            raise RuntimeError("capabilities bug")

        def generate(self, request):
            raise AssertionError("generate must not be called")

    secondary = ScriptedProvider(SECONDARY, ["success"])
    registry = PolarProviderHealthRegistry(
        PolarProviderHealthPolicy(failure_threshold=1)
    )

    result = generate_polar_orchestrated(
        (BrokenCapabilitiesProvider(), secondary),
        _request(),
        health_registry=registry,
    )

    first = result.metadata["orchestration"]["attempts"][0]
    assert result.provider == SECONDARY
    assert first["outcome"] == "unexpected_error"
    assert "capabilities bug" in first["error_message"]
    assert registry.snapshot(PRIMARY).state == "open"


def test_capabilities_failure_still_propagates_without_health_isolation() -> None:
    class BrokenCapabilitiesProvider:
        identity = PRIMARY

        @property
        def capabilities(self):
            raise RuntimeError("surface capabilities bug")

        def generate(self, request):
            raise AssertionError("generate must not be called")

    with pytest.raises(RuntimeError, match="surface capabilities bug"):
        generate_polar_orchestrated(
            (BrokenCapabilitiesProvider(),),
            _request(),
        )


def test_health_cache_hit_reads_provider_capabilities_once(tmp_path) -> None:
    class SingleReadCapabilitiesProvider(ScriptedProvider):
        def __init__(self) -> None:
            self.identity = PRIMARY
            self.outcomes = [RuntimeError("must-not-run")]
            self.calls = 0
            self.capability_reads = 0

        @property
        def capabilities(self):
            self.capability_reads += 1
            if self.capability_reads > 1:
                raise RuntimeError("capabilities read twice")
            return CAPABILITIES

    cache = FilesystemPolarCache(tmp_path)
    request = _request()
    cache.put(_result(request, PRIMARY))
    primary = SingleReadCapabilitiesProvider()

    result = generate_polar_orchestrated(
        (primary,),
        request,
        cache=cache,
        health_registry=PolarProviderHealthRegistry(),
    )

    assert result.metadata["cache"]["status"] == "hit"
    assert primary.capability_reads == 1
    assert primary.calls == 0


def test_base_exception_releases_half_open_probe_without_masking() -> None:
    current_time = [0.0]
    registry = PolarProviderHealthRegistry(
        PolarProviderHealthPolicy(failure_threshold=1, recovery_timeout_s=5.0),
        clock=lambda: current_time[0],
    )
    permit, _ = registry._acquire(PRIMARY)
    assert permit is not None
    registry._record_failure(permit, PolarProviderTimeoutError("opens"))
    current_time[0] = 5.0
    primary = ScriptedProvider(PRIMARY, [KeyboardInterrupt()])

    with pytest.raises(KeyboardInterrupt):
        generate_polar_orchestrated(
            (primary,),
            _request(),
            health_registry=registry,
        )

    snapshot = registry.snapshot(PRIMARY)
    assert snapshot.state == "open"
    assert snapshot.probe_in_flight is False
    assert snapshot.cooldown_remaining_s == 5.0


def test_open_circuit_still_serves_primary_cache_hit(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    request = _request()
    cache.put(_result(request, PRIMARY))
    registry = PolarProviderHealthRegistry(
        PolarProviderHealthPolicy(failure_threshold=1, recovery_timeout_s=60.0)
    )
    permit, _ = registry._acquire(PRIMARY)
    assert permit is not None
    registry._record_failure(permit, PolarProviderTimeoutError("opens"))
    primary = ScriptedProvider(PRIMARY, [RuntimeError("must-not-run")])

    result = generate_polar_orchestrated(
        (primary,),
        request,
        cache=cache,
        health_registry=registry,
    )

    attempt = result.metadata["orchestration"]["attempts"][0]
    assert primary.calls == 0
    assert result.metadata["cache"]["status"] == "hit"
    assert result.metadata["cache"]["coalesced"] is False
    assert attempt["cache_status"] == "hit"
    assert attempt["circuit_state_before"] == "open"
    assert attempt["circuit_state_after"] == "open"
    assert registry.snapshot(PRIMARY).state == "open"
    assert registry.snapshot(PRIMARY).total_successes == 0


def test_successful_half_open_provider_probe_closes_circuit() -> None:
    current_time = [0.0]
    registry = PolarProviderHealthRegistry(
        PolarProviderHealthPolicy(failure_threshold=1, recovery_timeout_s=5.0),
        clock=lambda: current_time[0],
    )
    permit, _ = registry._acquire(PRIMARY)
    assert permit is not None
    registry._record_failure(permit, PolarProviderTimeoutError("opens"))
    current_time[0] = 5.0
    primary = ScriptedProvider(PRIMARY, ["success"])

    result = generate_polar_orchestrated(
        (primary,),
        _request(),
        health_registry=registry,
    )

    attempt = result.metadata["orchestration"]["attempts"][0]
    assert attempt["circuit_probe"] is True
    assert attempt["circuit_state_before"] == "half_open"
    assert attempt["circuit_state_after"] == "closed"
    assert registry.snapshot(PRIMARY).state == "closed"


def test_capability_mismatch_does_not_mutate_provider_health() -> None:
    limited = replace(CAPABILITIES, supports_mach=False)
    primary = ScriptedProvider(PRIMARY, ["must-not-run"], capabilities=limited)
    secondary = ScriptedProvider(SECONDARY, ["success"])
    registry = PolarProviderHealthRegistry()

    result = generate_polar_orchestrated(
        (primary, secondary),
        _request(mach=0.2),
        health_registry=registry,
    )

    first = result.metadata["orchestration"]["attempts"][0]
    assert first["outcome"] == "capability_error"
    assert first["health_counted"] is False
    assert registry.snapshot(PRIMARY).total_failures == 0
    assert tuple(snapshot.provider for snapshot in registry.snapshots()) == (SECONDARY,)


def test_health_provenance_contains_chain_snapshots() -> None:
    primary = ScriptedProvider(PRIMARY, [PolarProviderUnavailableError("missing")])
    secondary = ScriptedProvider(SECONDARY, ["success"])
    registry = PolarProviderHealthRegistry()

    result = generate_polar_orchestrated(
        (primary, secondary),
        _request(),
        health_registry=registry,
    )

    provenance = result.metadata["orchestration"]
    health = provenance["provider_health"]
    assert provenance["health_enabled"] is True
    assert tuple(item["provider"] for item in health) == (
        PRIMARY.as_mapping(),
        SECONDARY.as_mapping(),
    )
    assert health[0]["total_failures"] == 1
    assert health[1]["total_successes"] == 1


def test_result_qualification_routes_partial_result_without_health_penalty() -> None:
    primary = ResultProvider(
        PRIMARY, ("converged", "not_converged", "converged")
    )
    secondary = ResultProvider(
        SECONDARY, ("converged", "converged", "converged")
    )
    registry = PolarProviderHealthRegistry()

    result = generate_polar_orchestrated(
        (primary, secondary),
        _request(),
        result_policy=PolarResultQualificationPolicy(),
        health_registry=registry,
    )

    attempts = result.metadata["orchestration"]["attempts"]
    assert result.provider == SECONDARY
    assert tuple(attempt["outcome"] for attempt in attempts) == (
        "result_rejected",
        "success",
    )
    assert attempts[0]["result_point_count"] == 3
    assert attempts[0]["result_accepted_points"] == 2
    assert attempts[0]["result_usable_fraction"] == pytest.approx(2.0 / 3.0)
    assert attempts[0]["result_rejected_indices"] == (1,)
    assert attempts[0]["will_retry"] is False
    assert attempts[0]["health_counted"] is False
    assert result.metadata["orchestration"]["result_rejection_count"] == 1
    primary_health = registry.snapshot(PRIMARY)
    assert primary_health.state == "closed"
    assert primary_health.total_failures == 0
    assert primary_health.total_successes == 0


def test_result_qualification_is_opt_in_for_backward_compatibility() -> None:
    primary = ResultProvider(
        PRIMARY, ("converged", "not_converged", "converged")
    )
    secondary = ResultProvider(
        SECONDARY, ("converged", "converged", "converged")
    )

    result = generate_polar_orchestrated((primary, secondary), _request())

    assert result.provider == PRIMARY
    assert not result.complete
    assert secondary.calls == 0


def test_cached_partial_result_is_rejected_before_circuit_admission(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    request = _request()
    cached_primary = ResultProvider(
        PRIMARY, ("converged", "not_converged", "converged")
    )
    generate_polar_orchestrated((cached_primary,), request, cache=cache)
    primary = ResultProvider(
        PRIMARY, ("converged", "converged", "converged")
    )
    secondary = ResultProvider(
        SECONDARY, ("converged", "converged", "converged")
    )
    registry = PolarProviderHealthRegistry()

    result = generate_polar_orchestrated(
        (primary, secondary),
        request,
        cache=cache,
        health_registry=registry,
        result_policy=PolarResultQualificationPolicy(),
    )

    first = result.metadata["orchestration"]["attempts"][0]
    assert result.provider == SECONDARY
    assert primary.calls == 0
    assert first["outcome"] == "result_rejected"
    assert first["cache_status"] == "hit"
    assert first["circuit_state_before"] == "closed"
    assert first["health_counted"] is False
    assert registry.snapshot(PRIMARY).total_failures == 0


def test_low_confidence_can_be_accepted_or_rejected_explicitly() -> None:
    primary = ResultProvider(
        PRIMARY, ("converged", "low_confidence", "converged")
    )
    secondary = ResultProvider(
        SECONDARY, ("converged", "converged", "converged")
    )

    accepted = generate_polar_orchestrated(
        (primary, secondary),
        _request(),
        result_policy=PolarResultQualificationPolicy(),
    )
    rejected = generate_polar_orchestrated(
        (primary, secondary),
        _request(reynolds=300_000.0),
        result_policy=PolarResultQualificationPolicy(allow_low_confidence=False),
    )

    assert accepted.provider == PRIMARY
    assert rejected.provider == SECONDARY
    assert rejected.metadata["orchestration"]["attempts"][0]["outcome"] == (
        "result_rejected"
    )


def test_all_rejected_results_are_retained_as_chain_cause() -> None:
    providers = (
        ResultProvider(PRIMARY, ("converged", "not_converged", "converged")),
        ResultProvider(SECONDARY, ("converged", "not_converged", "converged")),
    )

    with pytest.raises(PolarProviderChainExhaustedError) as captured:
        generate_polar_orchestrated(
            providers,
            _request(),
            result_policy=PolarResultQualificationPolicy(),
        )

    assert tuple(attempt.outcome for attempt in captured.value.attempts) == (
        "result_rejected",
        "result_rejected",
    )
    assert isinstance(captured.value.__cause__, PolarProviderResultRejectedError)
    assert captured.value.__cause__.qualification.rejected_indices == (1,)


def test_result_policy_and_attempt_qualification_invariants_are_strict() -> None:
    with pytest.raises(TypeError, match="result_policy"):
        generate_polar_orchestrated((ScriptedProvider(PRIMARY, ["ok"]),), _request(), result_policy=object())
    with pytest.raises(ValueError, match="at least two"):
        PolarProviderAttempt(
            provider=PRIMARY,
            provider_position=1,
            attempt_number=1,
            outcome="result_rejected",
            elapsed_s=0.0,
            result_point_count=0,
            result_accepted_points=0,
            result_usable_fraction=0.0,
        )
