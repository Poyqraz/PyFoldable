"""Cross-process polar cache lock ownership and coalescing behavior."""

from __future__ import annotations

import json
import multiprocessing
import os
import socket
import time
from dataclasses import replace

import pytest

from pyfoldable.core import (
    AirfoilDefinition,
    FilesystemPolarCache,
    POLAR_CACHE_LOCK_SCHEMA_VERSION,
    PolarCacheLockError,
    PolarCacheLockPolicy,
    PolarCacheLockTimeoutError,
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarPointResult,
    PolarProviderExecutionError,
    ProviderCapabilities,
    ProviderIdentity,
    generate_polar_cached,
)
from pyfoldable.core.polar_cache_lock import _is_cache_key_lock_active


AIRFOIL = AirfoilDefinition(
    id="LOCK-TEST",
    source="fixture",
    coordinates=((1.0, 0.0), (0.5, 0.1), (0.0, 0.0), (0.5, -0.1), (1.0, 0.0)),
)
IDENTITY = ProviderIdentity("lock-test", "1", "lock-backend", "2")
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
        reynolds=200_000.0,
        scenario_id="process-lock",
    )
    return replace(request, **changes)


def _result(request: PolarGenerationRequest) -> PolarGenerationResult:
    return PolarGenerationResult(
        request=request,
        provider=IDENTITY,
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
    )


class SimpleProvider:
    identity = IDENTITY
    capabilities = CAPABILITIES

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def generate(self, request: PolarGenerationRequest) -> PolarGenerationResult:
        self.calls += 1
        if self.fail:
            raise PolarProviderExecutionError("intentional failure")
        return _result(request)


class ProcessCountingProvider:
    identity = IDENTITY
    capabilities = CAPABILITIES

    def __init__(self, counter, delay_s: float) -> None:
        self.counter = counter
        self.delay_s = delay_s

    def generate(self, request: PolarGenerationRequest) -> PolarGenerationResult:
        with self.counter.get_lock():
            self.counter.value += 1
        time.sleep(self.delay_s)
        return _result(request)


def _coalescing_process_worker(root, counter, barrier, output) -> None:
    try:
        cache = FilesystemPolarCache(
            root,
            lock_policy=PolarCacheLockPolicy(
                wait_timeout_s=10.0,
                initial_poll_interval_s=0.005,
                max_poll_interval_s=0.05,
                backoff_factor=1.5,
            ),
        )
        provider = ProcessCountingProvider(counter, delay_s=0.5)
        barrier.wait(timeout=10.0)
        result = generate_polar_cached(provider, _request(), cache)
        output.put(
            {
                "status": result.metadata["cache"]["status"],
                "coalesced": result.metadata["cache"]["coalesced"],
                "wait_s": result.metadata["cache"]["lock_wait_s"],
            }
        )
    except BaseException as error:
        output.put({"error": repr(error)})
        raise


def _lock_record(path) -> dict:
    raw = path.read_bytes()
    return json.loads(raw[1:].strip().decode("utf-8"))


def test_lock_record_contains_owner_identity_and_clears_on_release(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    request = _request()
    cache_key = request.cache_key(IDENTITY)
    path = cache.lock_path(IDENTITY, request)

    with cache._process_key_lock(cache_key) as acquisition:
        record = _lock_record(path)
        assert acquisition.relative_path == path.relative_to(tmp_path).as_posix()
        assert record["schema_version"] == POLAR_CACHE_LOCK_SCHEMA_VERSION
        assert record["cache_key"] == cache_key
        assert len(record["token"]) == 32
        assert record["pid"] == os.getpid()
        assert record["hostname"] == socket.gethostname()
        assert isinstance(record["acquired_time_ns"], int)
        assert _is_cache_key_lock_active(tmp_path, cache_key)

    assert path.read_bytes() == b"\n"
    assert not _is_cache_key_lock_active(tmp_path, cache_key)


def test_lock_timeout_is_typed_and_does_not_call_provider(tmp_path) -> None:
    request = _request()
    cache_key = request.cache_key(IDENTITY)
    owner = FilesystemPolarCache(tmp_path)
    contender = FilesystemPolarCache(
        tmp_path,
        lock_policy=PolarCacheLockPolicy(
            wait_timeout_s=0.05,
            initial_poll_interval_s=0.005,
            max_poll_interval_s=0.01,
        ),
    )
    provider = SimpleProvider()

    with owner._process_key_lock(cache_key):
        with pytest.raises(PolarCacheLockTimeoutError, match="Timed out"):
            generate_polar_cached(provider, request, contender)

    assert provider.calls == 0


@pytest.mark.parametrize("payload", [b"abandoned", b"{malformed"])
def test_abandoned_or_malformed_owner_metadata_is_safely_recovered(
    tmp_path,
    payload,
) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = SimpleProvider()
    request = _request()
    path = cache.lock_path(IDENTITY, request)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\n" + payload + b"\n")

    result = generate_polar_cached(provider, request, cache)

    assert result.metadata["cache"]["stale_lock_recovered"] is True
    assert result.metadata["cache"]["coalesced"] is False
    assert provider.calls == 1
    assert path.read_bytes() == b"\n"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [("token", "f" * 32), ("cache_key", "0" * 64)],
)
def test_release_refuses_to_clear_another_owner_identity(
    tmp_path,
    field,
    replacement,
) -> None:
    cache = FilesystemPolarCache(tmp_path)
    request = _request()
    cache_key = request.cache_key(IDENTITY)
    process_lock = cache._process_key_lock(cache_key)
    process_lock.__enter__()
    path = cache.lock_path(IDENTITY, request)
    record = _lock_record(path)
    record[field] = replacement
    path.write_bytes(
        b"\n" + json.dumps(record, sort_keys=True).encode("utf-8") + b"\n"
    )

    with pytest.raises(PolarCacheLockError, match="ownership changed"):
        process_lock.__exit__(None, None, None)

    assert _lock_record(path)[field] == replacement
    assert not _is_cache_key_lock_active(tmp_path, cache_key)


def test_provider_failure_releases_lock_for_next_generation(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    request = _request()

    with pytest.raises(PolarProviderExecutionError, match="intentional failure"):
        generate_polar_cached(SimpleProvider(fail=True), request, cache)
    successful = SimpleProvider()
    result = generate_polar_cached(successful, request, cache)

    assert result.metadata["cache"]["status"] == "miss"
    assert successful.calls == 1
    assert cache.lock_path(IDENTITY, request).read_bytes() == b"\n"


def test_maintenance_preserves_entry_while_its_process_lock_is_active(
    tmp_path,
) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = SimpleProvider()
    request = _request()
    cache.put(provider.generate(request))
    entry = cache.entry_path(IDENTITY, request)
    old_ns = time.time_ns() - 120_000_000_000
    os.utime(entry, ns=(old_ns, old_ns))
    cache_key = request.cache_key(IDENTITY)

    with cache._process_key_lock(cache_key):
        protected = FilesystemPolarCache(tmp_path).maintain(
            max_age_s=0.0,
            max_bytes=0,
        )
        assert entry.is_file()
        assert protected.after.entry_count == 1

    evicted = cache.maintain(max_age_s=0.0, max_bytes=0)
    assert not entry.exists()
    assert evicted.after.entry_count == 0


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"wait_timeout_s": -1.0}, "wait_timeout_s"),
        ({"initial_poll_interval_s": 0.0}, "initial_poll_interval_s"),
        (
            {"initial_poll_interval_s": 0.2, "max_poll_interval_s": 0.1},
            "max_poll_interval_s",
        ),
        ({"backoff_factor": 0.5}, "backoff_factor"),
        ({"wait_timeout_s": float("nan")}, "wait_timeout_s"),
    ],
)
def test_lock_policy_is_strictly_validated(changes, message) -> None:
    with pytest.raises(ValueError, match=message):
        PolarCacheLockPolicy(**changes)


def test_four_processes_execute_backend_once_for_one_cache_key(tmp_path) -> None:
    context = multiprocessing.get_context("spawn")
    counter = context.Value("i", 0)
    barrier = context.Barrier(4)
    output = context.Queue()
    processes = tuple(
        context.Process(
            target=_coalescing_process_worker,
            args=(str(tmp_path), counter, barrier, output),
        )
        for _ in range(4)
    )

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20.0)
    results = tuple(output.get(timeout=5.0) for _ in processes)

    assert all(process.exitcode == 0 for process in processes)
    assert not any("error" in result for result in results)
    assert counter.value == 1
    assert sum(result["status"] == "miss" for result in results) == 1
    assert sum(result["status"] == "hit" for result in results) == 3
    assert any(result["coalesced"] for result in results)
    assert max(result["wait_s"] for result in results) > 0.0
