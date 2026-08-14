"""Filesystem polar-cache persistence, recovery, and provenance behavior."""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from pyfoldable.core import (
    AirfoilDefinition,
    FilesystemPolarCache,
    POLAR_CACHE_SCHEMA_VERSION,
    PolarCacheError,
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarPointResult,
    PolarProviderCapabilityError,
    PolarProviderExecutionError,
    ProviderCapabilities,
    ProviderIdentity,
    generate_polar_cached,
)


AIRFOIL = AirfoilDefinition(
    id="CACHE-TEST",
    source="fixture",
    coordinates=((1.0, 0.0), (0.5, 0.1), (0.0, 0.0), (0.5, -0.1), (1.0, 0.0)),
)
IDENTITY = ProviderIdentity("fake", "1", "fake-backend", "2")
CAPABILITIES = ProviderCapabilities(
    supports_mach=True,
    supports_n_crit=True,
    supports_forced_transition=True,
    supports_pointwise_confidence=True,
    supports_partial_results=True,
    supports_vectorized_alpha=True,
    supports_iteration_limit=True,
    supports_timeout=True,
)


def _request(**changes) -> PolarGenerationRequest:
    request = PolarGenerationRequest(
        airfoil=AIRFOIL,
        alpha_rad=(-0.1, 0.0, 0.1),
        reynolds=150_000.0,
        scenario_id="smooth",
        options={"solver": {"b": 2, "a": 1}},
    )
    return replace(request, **changes)


def _point(alpha: float, *, confidence: float = 0.9) -> PolarPointResult:
    return PolarPointResult(
        alpha_rad=alpha,
        status="converged",
        cl=10.0 * alpha,
        cd=0.01 + alpha * alpha,
        cm=-0.02,
        confidence=confidence,
        iterations=7,
    )


class CountingProvider:
    def __init__(
        self,
        *,
        identity: ProviderIdentity = IDENTITY,
        capabilities: ProviderCapabilities = CAPABILITIES,
        partial: bool = False,
        fail: bool = False,
    ) -> None:
        self.identity = identity
        self.capabilities = capabilities
        self.partial = partial
        self.fail = fail
        self.calls = 0

    def generate(self, request: PolarGenerationRequest) -> PolarGenerationResult:
        self.calls += 1
        if self.fail:
            raise PolarProviderExecutionError("backend failed")
        points = tuple(_point(alpha) for alpha in request.alpha_rad)
        if self.partial:
            points = (
                points[0],
                PolarPointResult(
                    request.alpha_rad[1],
                    "not_converged",
                    iterations=50,
                    message="iteration limit",
                ),
                points[2],
            )
        return PolarGenerationResult(
            request=request,
            provider=self.identity,
            points=points,
            elapsed_s=0.125,
            warnings=("provider warning",),
            metadata={
                "backend_detail": {"rows": len(points)},
                "cache": {"status": "forged"},
            },
        )


def _read_document(cache: FilesystemPolarCache, provider, request) -> dict:
    path = cache.entry_path(provider.identity, request)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_document(cache: FilesystemPolarCache, provider, request, document) -> None:
    path = cache.entry_path(provider.identity, request)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_cache_miss_writes_then_hit_skips_provider(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path / "polars")
    provider = CountingProvider()
    request = _request()

    generated = generate_polar_cached(provider, request, cache)
    loaded = generate_polar_cached(provider, request, cache)

    assert provider.calls == 1
    assert generated.metadata["cache"]["status"] == "miss"
    assert loaded.metadata["cache"]["status"] == "hit"
    assert loaded.points == generated.points
    assert loaded.warnings == generated.warnings
    assert loaded.elapsed_s == generated.elapsed_s
    assert loaded.metadata["backend_detail"] == {"rows": 3}
    expected_entry = f"{generated.cache_key[:2]}/{generated.cache_key}.json"
    assert loaded.metadata["cache"]["entry"] == expected_entry
    assert cache.entry_path(provider.identity, request).is_file()


def test_cache_file_uses_versioned_canonical_document_without_runtime_provenance(
    tmp_path,
) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = CountingProvider()
    request = _request()

    result = generate_polar_cached(provider, request, cache)
    document = _read_document(cache, provider, request)

    assert set(document) == {
        "schema_version",
        "cache_key",
        "provider",
        "request",
        "result",
    }
    assert document["schema_version"] == POLAR_CACHE_SCHEMA_VERSION
    assert document["cache_key"] == result.cache_key
    assert document["provider"] == provider.identity.as_mapping()
    assert "cache" not in document["result"]["metadata"]


def test_request_and_provider_identity_changes_produce_separate_entries(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    first = CountingProvider()
    changed_request = _request(scenario_id="rough")
    changed_provider = CountingProvider(
        identity=replace(IDENTITY, backend_version="3"),
    )

    initial = generate_polar_cached(first, _request(), cache)
    scenario = generate_polar_cached(first, changed_request, cache)
    backend = generate_polar_cached(changed_provider, _request(), cache)

    assert len({initial.cache_key, scenario.cache_key, backend.cache_key}) == 3
    assert first.calls == 2
    assert changed_provider.calls == 1
    assert len(tuple(tmp_path.glob("*/*.json"))) == 3


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: document.update(schema_version=99),
        lambda document: document.update(cache_key="0" * 64),
        lambda document: document["provider"].update(backend_version="tampered"),
        lambda document: document["request"].update(reynolds=999.0),
        lambda document: document["result"]["points"][0].update(cd=-1.0),
        lambda document: document["result"].update(points=[]),
    ],
    ids=[
        "schema",
        "cache-key",
        "provider",
        "request",
        "invalid-point",
        "missing-points",
    ],
)
def test_invalid_cache_documents_are_quarantined_and_regenerated(
    tmp_path,
    mutate,
) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = CountingProvider()
    request = _request()
    generate_polar_cached(provider, request, cache)
    document = _read_document(cache, provider, request)
    mutate(document)
    _write_document(cache, provider, request, document)

    recovered = generate_polar_cached(provider, request, cache)

    assert provider.calls == 2
    assert recovered.metadata["cache"]["status"] == "recovered"
    quarantined = recovered.metadata["cache"]["quarantined_entry"]
    assert quarantined.startswith("corrupt/")
    assert (cache.root / quarantined).is_file()
    assert _read_document(cache, provider, request)["schema_version"] == 1


def test_invalid_utf8_is_quarantined_and_regenerated(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = CountingProvider()
    request = _request()
    generate_polar_cached(provider, request, cache)
    cache.entry_path(provider.identity, request).write_bytes(b"\xff\xfe")

    recovered = generate_polar_cached(provider, request, cache)

    assert recovered.metadata["cache"]["status"] == "recovered"
    assert provider.calls == 2


def test_cached_result_that_contradicts_capabilities_is_recovered(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = CountingProvider()
    request = _request()
    generate_polar_cached(provider, request, cache)
    limited = CountingProvider(
        capabilities=replace(CAPABILITIES, supports_pointwise_confidence=False),
    )

    assert cache.get(limited, request) is None
    assert len(tuple((tmp_path / "corrupt").glob("*.json"))) == 1


def test_capabilities_are_validated_before_cache_lookup_or_provider_call(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = CountingProvider(
        capabilities=replace(CAPABILITIES, supports_mach=False),
    )
    request = _request(mach=0.2)

    with pytest.raises(PolarProviderCapabilityError, match="mach"):
        generate_polar_cached(provider, request, cache)

    assert provider.calls == 0
    assert not cache.entry_path(provider.identity, request).exists()


def test_partial_results_round_trip_without_fabricating_failed_points(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = CountingProvider(partial=True)
    request = _request()

    generated = generate_polar_cached(provider, request, cache)
    loaded = generate_polar_cached(provider, request, cache)

    assert not generated.complete
    assert loaded.points == generated.points
    assert loaded.points[1].status == "not_converged"
    assert loaded.points[1].cl is None
    assert loaded.metadata["cache"]["status"] == "hit"


def test_low_confidence_points_round_trip_as_usable_results(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = CountingProvider()
    request = _request()
    result = provider.generate(request)
    low = PolarPointResult(
        request.alpha_rad[1],
        "low_confidence",
        cl=0.0,
        cd=0.01,
        cm=-0.02,
        confidence=0.2,
        message="outside training envelope",
    )
    result = replace(result, points=(result.points[0], low, result.points[2]))
    cache.put(result)

    loaded = cache.get(provider, request)

    assert loaded is not None
    assert loaded.complete
    assert loaded.points[1] == low
    assert loaded.usable_mask == (True, True, True)


def test_provider_failures_are_not_cached(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = CountingProvider(fail=True)
    request = _request()

    with pytest.raises(PolarProviderExecutionError, match="backend failed"):
        generate_polar_cached(provider, request, cache)

    assert not cache.entry_path(provider.identity, request).exists()


def test_cache_write_errors_use_typed_exception(tmp_path) -> None:
    root = tmp_path / "not-a-directory"
    root.write_text("occupied", encoding="utf-8")
    cache = FilesystemPolarCache(root)
    provider = CountingProvider()
    result = provider.generate(_request())

    with pytest.raises(PolarCacheError, match="prepare polar cache entry"):
        cache.put(result)


def test_concurrent_writers_publish_one_valid_entry_without_temp_files(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = CountingProvider()
    request = _request()
    result = provider.generate(request)

    with ThreadPoolExecutor(max_workers=8) as executor:
        paths = tuple(executor.map(lambda _: cache.put(result), range(32)))

    assert len(set(paths)) == 1
    assert cache.get(provider, request) is not None
    entry = cache.entry_path(provider.identity, request)
    assert not any(path.suffix == ".tmp" for path in entry.parent.iterdir())
    assert json.loads(entry.read_text(encoding="utf-8"))["cache_key"] == result.cache_key


def _set_age(path, age_s: float) -> None:
    modified_ns = time.time_ns() - int(age_s * 1_000_000_000)
    os.utime(path, ns=(modified_ns, modified_ns))


def _write_lifecycle_artifacts(cache: FilesystemPolarCache) -> tuple:
    corrupt = cache.root / "corrupt" / f"{'a' * 64}.{'b' * 32}.json"
    temporary = cache.root / "aa" / f".{'c' * 64}.writer.tmp"
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    temporary.parent.mkdir(parents=True, exist_ok=True)
    corrupt.write_text("corrupt", encoding="utf-8")
    temporary.write_text("temporary", encoding="utf-8")
    return corrupt, temporary


def test_lifecycle_inventory_and_stats_are_deterministic(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = CountingProvider()
    for scenario in ("charlie", "alpha", "bravo"):
        generate_polar_cached(
            provider,
            _request(scenario_id=scenario),
            cache,
        )
    corrupt, temporary = _write_lifecycle_artifacts(cache)
    (cache.root / "notes.txt").write_text("ignored", encoding="utf-8")

    entries = cache.list_entries()
    stats = cache.stats()

    assert tuple(entry.relative_path for entry in entries) == tuple(
        sorted(entry.relative_path for entry in entries)
    )
    assert stats.entry_count == 3
    assert stats.total_bytes == sum(entry.size_bytes for entry in entries)
    assert stats.oldest_modified_time_ns == min(
        entry.modified_time_ns for entry in entries
    )
    assert stats.newest_modified_time_ns == max(
        entry.modified_time_ns for entry in entries
    )
    assert stats.corrupt_count == 1
    assert stats.corrupt_bytes == corrupt.stat().st_size
    assert stats.temporary_count == 1
    assert stats.temporary_bytes == temporary.stat().st_size
    assert stats.total_storage_bytes == (
        stats.total_bytes + stats.corrupt_bytes + stats.temporary_bytes
    )


def test_empty_cache_stats_do_not_create_the_root(tmp_path) -> None:
    root = tmp_path / "missing"
    cache = FilesystemPolarCache(root)

    assert cache.list_entries() == ()
    assert cache.stats().entry_count == 0
    assert cache.stats().total_storage_bytes == 0
    assert not root.exists()


def test_age_policy_evicts_only_expired_entries_and_removes_empty_shard(
    tmp_path,
) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = CountingProvider()
    old_request = _request(scenario_id="old")
    fresh_request = _request(scenario_id="fresh")
    generate_polar_cached(provider, old_request, cache)
    generate_polar_cached(provider, fresh_request, cache)
    old_path = cache.entry_path(provider.identity, old_request)
    fresh_path = cache.entry_path(provider.identity, fresh_request)
    _set_age(old_path, 120.0)
    _set_age(fresh_path, 1.0)
    old_relative = old_path.relative_to(cache.root).as_posix()
    old_size = old_path.stat().st_size

    result = cache.maintain(max_age_s=60.0)

    assert result.evicted_entries == (old_relative,)
    assert result.reclaimed_bytes == old_size
    assert not old_path.exists()
    assert fresh_path.is_file()
    assert result.before.entry_count == 2
    assert result.after.entry_count == 1
    if old_path.parent != fresh_path.parent:
        assert not old_path.parent.exists()


def test_size_policy_evicts_oldest_then_relative_path_for_ties(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = CountingProvider()
    for scenario in ("one", "two", "three"):
        generate_polar_cached(provider, _request(scenario_id=scenario), cache)
    entries = cache.list_entries()
    same_time_ns = time.time_ns() - 100_000_000_000
    for entry in entries:
        path = cache.root / entry.relative_path
        os.utime(path, ns=(same_time_ns, same_time_ns))
    entries = cache.list_entries()
    first = entries[0]
    total = sum(entry.size_bytes for entry in entries)

    result = cache.maintain(max_bytes=total - first.size_bytes)

    assert result.evicted_entries == (first.relative_path,)
    assert result.after.total_bytes <= total - first.size_bytes
    assert not (cache.root / first.relative_path).exists()


def test_age_eviction_precedes_size_eviction_in_one_maintenance_pass(
    tmp_path,
) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = CountingProvider()
    requests = tuple(
        _request(scenario_id=scenario)
        for scenario in ("expired", "oldest-remaining", "fresh")
    )
    for request in requests:
        generate_polar_cached(provider, request, cache)
    paths = tuple(cache.entry_path(provider.identity, request) for request in requests)
    for path, age_s in zip(paths, (180.0, 30.0, 1.0)):
        _set_age(path, age_s)
    remaining_limit = paths[2].stat().st_size

    result = cache.maintain(max_age_s=60.0, max_bytes=remaining_limit)

    expected = tuple(path.relative_to(cache.root).as_posix() for path in paths[:2])
    assert result.evicted_entries == expected
    assert not paths[0].exists()
    assert not paths[1].exists()
    assert paths[2].is_file()
    assert result.after.total_bytes <= remaining_limit


def test_zero_byte_policy_evicts_every_active_entry_and_allows_regeneration(
    tmp_path,
) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = CountingProvider()
    request = _request()
    generate_polar_cached(provider, request, cache)

    maintenance = cache.maintain(max_bytes=0)
    regenerated = generate_polar_cached(provider, request, cache)

    assert maintenance.after.entry_count == 0
    assert regenerated.metadata["cache"]["status"] == "miss"
    assert provider.calls == 2


def test_artifact_cleanup_is_opt_in_and_age_bounded(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    old_corrupt, old_temporary = _write_lifecycle_artifacts(cache)
    fresh_corrupt = cache.root / "corrupt" / f"{'d' * 64}.{'e' * 32}.json"
    fresh_temporary = cache.root / "dd" / f".{'f' * 64}.writer.tmp"
    fresh_corrupt.write_text("fresh", encoding="utf-8")
    fresh_temporary.parent.mkdir(parents=True, exist_ok=True)
    fresh_temporary.write_text("fresh", encoding="utf-8")
    _set_age(old_corrupt, 120.0)
    _set_age(old_temporary, 120.0)
    _set_age(fresh_corrupt, 1.0)
    _set_age(fresh_temporary, 1.0)

    noop = cache.maintain()
    cleaned = cache.maintain(
        corrupt_max_age_s=60.0,
        temporary_max_age_s=60.0,
    )

    assert noop.before == noop.after
    assert noop.reclaimed_bytes == 0
    assert cleaned.removed_corrupt_entries == (
        old_corrupt.relative_to(cache.root).as_posix(),
    )
    assert cleaned.removed_temporary_entries == (
        old_temporary.relative_to(cache.root).as_posix(),
    )
    assert fresh_corrupt.is_file()
    assert fresh_temporary.is_file()
    assert cleaned.after.corrupt_count == 1
    assert cleaned.after.temporary_count == 1


@pytest.mark.parametrize(
    ("keyword", "value", "message"),
    [
        ("max_bytes", True, "max_bytes"),
        ("max_bytes", 1.5, "max_bytes"),
        ("max_bytes", -1, "max_bytes"),
        ("max_age_s", float("nan"), "max_age_s"),
        ("corrupt_max_age_s", -1.0, "corrupt_max_age_s"),
        ("temporary_max_age_s", True, "temporary_max_age_s"),
    ],
)
def test_lifecycle_policy_values_are_strictly_validated(
    tmp_path,
    keyword,
    value,
    message,
) -> None:
    cache = FilesystemPolarCache(tmp_path)

    with pytest.raises(ValueError, match=message):
        cache.maintain(**{keyword: value})


def test_lifecycle_io_errors_use_typed_exception(tmp_path) -> None:
    root = tmp_path / "not-a-directory"
    root.write_text("occupied", encoding="utf-8")
    cache = FilesystemPolarCache(root)

    with pytest.raises(PolarCacheError, match="inspect polar cache root"):
        cache.stats()
    with pytest.raises(PolarCacheError, match="maintain polar cache root"):
        cache.maintain(max_bytes=0)


def test_readers_writers_and_maintenance_share_one_safe_lock(tmp_path) -> None:
    cache = FilesystemPolarCache(tmp_path)
    provider = CountingProvider()
    request = _request()
    result = provider.generate(request)
    cache.put(result)

    operations = []
    with ThreadPoolExecutor(max_workers=12) as executor:
        for index in range(120):
            if index % 3 == 0:
                operations.append(executor.submit(cache.put, result))
            elif index % 3 == 1:
                operations.append(executor.submit(cache.get, provider, request))
            else:
                operations.append(
                    executor.submit(
                        cache.maintain,
                        max_bytes=10_000_000,
                        temporary_max_age_s=0.0,
                    )
                )
        outcomes = tuple(operation.result() for operation in operations)

    cache.put(result)
    loaded = cache.get(provider, request)
    entry = cache.entry_path(provider.identity, request)
    assert outcomes
    assert loaded is not None
    assert loaded.points == result.points
    assert entry.is_file()
    assert not any(path.suffix == ".tmp" for path in entry.parent.iterdir())
