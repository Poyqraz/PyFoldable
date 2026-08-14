"""Versioned, atomic filesystem cache for provider-generated polar results."""

from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal, Mapping

from .polar_cache_errors import PolarCacheError
from .polar_cache_lifecycle import (
    PolarCacheEntry,
    PolarCacheMaintenanceResult,
    PolarCacheStats,
    _cache_stats,
    _list_cache_entries,
    _maintain_cache,
)
from .polar_cache_lock import (
    PolarCacheLockPolicy,
    _ProcessKeyLock,
    _cache_key_lock_path,
)
from .providers import (
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarPointResult,
    PolarProvider,
    PolarProviderExecutionError,
    ProviderIdentity,
    _validate_polar_result,
    generate_polar,
)


POLAR_CACHE_SCHEMA_VERSION = 1
CacheStatus = Literal["hit", "miss", "recovered"]


@dataclass(frozen=True)
class _CacheRead:
    result: PolarGenerationResult | None
    status: CacheStatus
    entry: Path
    quarantined_entry: str | None = None


class FilesystemPolarCache:
    """Store validated polar results as versioned JSON with atomic replacement."""

    def __init__(
        self,
        root: str | Path,
        *,
        lock_policy: PolarCacheLockPolicy | None = None,
    ) -> None:
        self._root = Path(root)
        self._lock = threading.RLock()
        self._lock_policy = lock_policy or PolarCacheLockPolicy()
        if not isinstance(self._lock_policy, PolarCacheLockPolicy):
            raise TypeError("lock_policy must be a PolarCacheLockPolicy or None.")

    @property
    def root(self) -> Path:
        return self._root

    def entry_path(
        self,
        provider: ProviderIdentity,
        request: PolarGenerationRequest,
    ) -> Path:
        """Return the deterministic, sharded path for one request/provider key."""
        cache_key = request.cache_key(provider)
        return self._root / cache_key[:2] / f"{cache_key}.json"

    def lock_path(
        self,
        provider: ProviderIdentity,
        request: PolarGenerationRequest,
    ) -> Path:
        """Return the persistent process-coordination path for one cache key."""
        return _cache_key_lock_path(self._root, request.cache_key(provider))

    def get(
        self,
        provider: PolarProvider,
        request: PolarGenerationRequest,
    ) -> PolarGenerationResult | None:
        """Return a validated cache hit, or ``None`` for a clean/recovered miss."""
        request.validate_capabilities(provider.capabilities)
        return self._get_after_capability_validation(provider, request)

    def _get_after_capability_validation(
        self,
        provider: PolarProvider,
        request: PolarGenerationRequest,
    ) -> PolarGenerationResult | None:
        read = self._read(provider, request)
        if read.result is None:
            return None
        return _with_cache_provenance(
            read.result,
            "hit",
            read.entry,
            self._root,
            coalesced=False,
            lock_wait_s=0.0,
        )

    def list_entries(self) -> tuple[PolarCacheEntry, ...]:
        """Return active cache entries sorted by relative path."""
        try:
            with self._lock:
                return _list_cache_entries(self._root)
        except OSError as error:
            raise PolarCacheError(
                f"Could not inspect polar cache root {self._root}."
            ) from error

    def stats(self) -> PolarCacheStats:
        """Return active, corrupt, and temporary artifact storage totals."""
        try:
            with self._lock:
                return _cache_stats(self._root)
        except OSError as error:
            raise PolarCacheError(
                f"Could not inspect polar cache root {self._root}."
            ) from error

    def maintain(
        self,
        *,
        max_bytes: int | None = None,
        max_age_s: float | None = None,
        corrupt_max_age_s: float | None = None,
        temporary_max_age_s: float | None = None,
    ) -> PolarCacheMaintenanceResult:
        """Apply deterministic eviction and optional artifact cleanup policies."""
        try:
            with self._lock:
                return _maintain_cache(
                    self._root,
                    max_bytes=max_bytes,
                    max_age_s=max_age_s,
                    corrupt_max_age_s=corrupt_max_age_s,
                    temporary_max_age_s=temporary_max_age_s,
                )
        except OSError as error:
            raise PolarCacheError(
                f"Could not maintain polar cache root {self._root}."
            ) from error

    def put(self, result: PolarGenerationResult) -> Path:
        """Atomically publish one structurally validated provider result."""
        with self._lock:
            return self._put(result)

    def _put(self, result: PolarGenerationResult) -> Path:
        entry = self.entry_path(result.provider, result.request)
        try:
            document = _encode_document(result)
            entry.parent.mkdir(parents=True, exist_ok=True)
            serialized = json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ) + "\n"
        except (OSError, TypeError, ValueError) as error:
            raise PolarCacheError(f"Could not prepare polar cache entry {entry}.") from error

        descriptor: int | None = None
        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                dir=entry.parent,
                prefix=f".{result.cache_key}.",
                suffix=".tmp",
                text=True,
            )
            temporary_path = Path(temporary_name)
            stream = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
            descriptor = None
            with stream:
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, entry)
        except OSError as error:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise PolarCacheError(f"Could not write polar cache entry {entry}.") from error
        return entry

    def _read(
        self,
        provider: PolarProvider,
        request: PolarGenerationRequest,
    ) -> _CacheRead:
        with self._lock:
            return self._read_unlocked(provider, request)

    def _read_unlocked(
        self,
        provider: PolarProvider,
        request: PolarGenerationRequest,
    ) -> _CacheRead:
        entry = self.entry_path(provider.identity, request)
        try:
            serialized = entry.read_text(encoding="utf-8")
        except FileNotFoundError:
            return _CacheRead(None, "miss", entry)
        except UnicodeError:
            quarantined = self._quarantine(
                entry,
                result_key=request.cache_key(provider.identity),
            )
            return _CacheRead(None, "recovered", entry, quarantined)
        except OSError as error:
            raise PolarCacheError(f"Could not read polar cache entry {entry}.") from error

        try:
            document = json.loads(serialized)
            result = _decode_document(document, provider.identity, request)
            _validate_polar_result(provider, request, result)
        except (
            json.JSONDecodeError,
            UnicodeError,
            KeyError,
            TypeError,
            ValueError,
            PolarProviderExecutionError,
        ):
            quarantined = self._quarantine(
                entry,
                result_key=request.cache_key(provider.identity),
            )
            return _CacheRead(None, "recovered", entry, quarantined)
        return _CacheRead(result, "hit", entry)

    def _quarantine(self, entry: Path, *, result_key: str) -> str | None:
        quarantine = self._root / "corrupt" / (
            f"{result_key}.{uuid.uuid4().hex}.json"
        )
        try:
            quarantine.parent.mkdir(parents=True, exist_ok=True)
            os.replace(entry, quarantine)
        except OSError:
            return None
        return _relative_entry(self._root, quarantine)

    def _process_key_lock(self, cache_key: str) -> _ProcessKeyLock:
        return _ProcessKeyLock(self._root, cache_key, self._lock_policy)


def generate_polar_cached(
    provider: PolarProvider,
    request: PolarGenerationRequest,
    cache: FilesystemPolarCache,
) -> PolarGenerationResult:
    """Load a valid polar result or generate, persist, and annotate a cache miss."""
    request.validate_capabilities(provider.capabilities)
    read = cache._read(provider, request)
    if read.result is not None:
        return _with_cache_provenance(
            read.result,
            "hit",
            read.entry,
            cache.root,
            coalesced=False,
            lock_wait_s=0.0,
        )

    cache_key = request.cache_key(provider.identity)
    with cache._process_key_lock(cache_key) as acquisition:
        checked = cache._read(provider, request)
        if checked.result is not None:
            return _with_cache_provenance(
                checked.result,
                "hit",
                checked.entry,
                cache.root,
                coalesced=True,
                lock_wait_s=acquisition.waited_s,
                lock_entry=acquisition.relative_path,
                stale_lock_recovered=acquisition.recovered_stale_metadata,
            )

        recovery = checked if checked.status == "recovered" else read
        result = generate_polar(provider, request)
        entry = cache.put(result)
        return _with_cache_provenance(
            result,
            recovery.status,
            entry,
            cache.root,
            quarantined_entry=recovery.quarantined_entry,
            coalesced=False,
            lock_wait_s=acquisition.waited_s,
            lock_entry=acquisition.relative_path,
            stale_lock_recovered=acquisition.recovered_stale_metadata,
        )


def _encode_document(result: PolarGenerationResult) -> dict[str, Any]:
    if not all(isinstance(warning, str) for warning in result.warnings):
        raise TypeError("Cache warnings must contain only strings.")
    metadata = {
        key: value for key, value in result.metadata.items() if key != "cache"
    }
    return {
        "schema_version": POLAR_CACHE_SCHEMA_VERSION,
        "cache_key": result.cache_key,
        "provider": result.provider.as_mapping(),
        "request": _json_value(result.request.cache_payload(result.provider)),
        "result": {
            "elapsed_s": result.elapsed_s,
            "warnings": list(result.warnings),
            "metadata": _json_value(metadata),
            "points": [
                {
                    "alpha_rad": point.alpha_rad,
                    "status": point.status,
                    "cl": point.cl,
                    "cd": point.cd,
                    "cm": point.cm,
                    "confidence": point.confidence,
                    "iterations": point.iterations,
                    "message": point.message,
                }
                for point in result.points
            ],
        },
    }


def _decode_document(
    document: Any,
    provider: ProviderIdentity,
    request: PolarGenerationRequest,
) -> PolarGenerationResult:
    root = _mapping(document, "cache document")
    if set(root) != {"schema_version", "cache_key", "provider", "request", "result"}:
        raise ValueError("Cache document fields do not match the schema.")
    schema_version = root["schema_version"]
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != POLAR_CACHE_SCHEMA_VERSION
    ):
        raise ValueError("Unsupported polar cache schema version.")
    expected_key = request.cache_key(provider)
    if root["cache_key"] != expected_key:
        raise ValueError("Polar cache key does not match its entry path.")
    if root["provider"] != provider.as_mapping():
        raise ValueError("Polar cache provider identity does not match the request.")
    if root["request"] != _json_value(request.cache_payload(provider)):
        raise ValueError("Polar cache request identity does not match the request.")

    payload = _mapping(root["result"], "cache result")
    if set(payload) != {"elapsed_s", "warnings", "metadata", "points"}:
        raise ValueError("Cache result fields do not match the schema.")
    warnings = payload["warnings"]
    if not isinstance(warnings, list) or not all(
        isinstance(warning, str) for warning in warnings
    ):
        raise TypeError("Cache warnings must be a list of strings.")
    metadata = _mapping(payload["metadata"], "cache metadata")
    raw_points = payload["points"]
    if not isinstance(raw_points, list):
        raise TypeError("Cache points must be a list.")
    points = tuple(_decode_point(point) for point in raw_points)
    return PolarGenerationResult(
        request=request,
        provider=provider,
        points=points,
        elapsed_s=_number(payload["elapsed_s"], "elapsed_s"),
        warnings=tuple(warnings),
        metadata=metadata,
    )


def _decode_point(value: Any) -> PolarPointResult:
    point = _mapping(value, "cache point")
    expected = {
        "alpha_rad",
        "status",
        "cl",
        "cd",
        "cm",
        "confidence",
        "iterations",
        "message",
    }
    if set(point) != expected:
        raise ValueError("Cache point fields do not match the schema.")
    status = point["status"]
    message = point["message"]
    if not isinstance(status, str) or not isinstance(message, str):
        raise TypeError("Cache point status and message must be strings.")
    iterations = point["iterations"]
    if iterations is not None and (
        isinstance(iterations, bool) or not isinstance(iterations, int)
    ):
        raise TypeError("Cache point iterations must be an integer or null.")
    return PolarPointResult(
        alpha_rad=_number(point["alpha_rad"], "alpha_rad"),
        status=status,
        cl=_optional_number(point["cl"], "cl"),
        cd=_optional_number(point["cd"], "cd"),
        cm=_optional_number(point["cm"], "cm"),
        confidence=_optional_number(point["confidence"], "confidence"),
        iterations=iterations,
        message=message,
    )


def _with_cache_provenance(
    result: PolarGenerationResult,
    status: CacheStatus,
    entry: Path,
    root: Path,
    *,
    quarantined_entry: str | None = None,
    coalesced: bool | None = None,
    lock_wait_s: float | None = None,
    lock_entry: str | None = None,
    stale_lock_recovered: bool = False,
) -> PolarGenerationResult:
    metadata = dict(result.metadata)
    cache_metadata: dict[str, Any] = {
        "status": status,
        "schema_version": POLAR_CACHE_SCHEMA_VERSION,
        "entry": _relative_entry(root, entry),
    }
    if quarantined_entry is not None:
        cache_metadata["quarantined_entry"] = quarantined_entry
    if coalesced is not None:
        cache_metadata["coalesced"] = coalesced
        cache_metadata["lock_wait_s"] = float(lock_wait_s or 0.0)
        cache_metadata["stale_lock_recovered"] = stale_lock_recovered
    if lock_entry is not None:
        cache_metadata["lock_entry"] = lock_entry
    metadata["cache"] = cache_metadata
    return replace(result, metadata=metadata)


def _relative_entry(root: Path, entry: Path) -> str:
    try:
        return entry.relative_to(root).as_posix()
    except ValueError:
        return entry.name


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise TypeError(f"{name} must be a string-keyed mapping.")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite.")
    return number


def _optional_number(value: Any, name: str) -> float | None:
    return None if value is None else _number(value, name)


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Cache values must not contain non-finite floats.")
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Cache mapping keys must be strings.")
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    raise TypeError(f"Unsupported cache value type {type(value).__name__}.")
