"""Deterministic inventory and maintenance policies for polar cache files."""

from __future__ import annotations

import errno
import math
import re
import stat
import time
from dataclasses import dataclass
from pathlib import Path


_CACHE_ENTRY_PATTERN = re.compile(r"^(?P<key>[0-9a-f]{64})\.json$")
_CORRUPT_ENTRY_PATTERN = re.compile(
    r"^[0-9a-f]{64}\.[0-9a-f]{32}\.json$"
)
_TEMPORARY_ENTRY_PATTERN = re.compile(
    r"^\.[0-9a-f]{64}\..+\.tmp$"
)
_SHARD_PATTERN = re.compile(r"^[0-9a-f]{2}$")


@dataclass(frozen=True)
class PolarCacheEntry:
    """One active cache entry exposed through deterministic inventory APIs."""

    cache_key: str
    relative_path: str
    size_bytes: int
    modified_time_ns: int


@dataclass(frozen=True)
class PolarCacheStats:
    """Storage totals for active, quarantined, and temporary cache artifacts."""

    entry_count: int
    total_bytes: int
    oldest_modified_time_ns: int | None
    newest_modified_time_ns: int | None
    corrupt_count: int
    corrupt_bytes: int
    temporary_count: int
    temporary_bytes: int

    @property
    def total_storage_bytes(self) -> int:
        return self.total_bytes + self.corrupt_bytes + self.temporary_bytes


@dataclass(frozen=True)
class PolarCacheMaintenanceResult:
    """Auditable record of one cache lifecycle maintenance pass."""

    before: PolarCacheStats
    after: PolarCacheStats
    evicted_entries: tuple[str, ...]
    removed_corrupt_entries: tuple[str, ...]
    removed_temporary_entries: tuple[str, ...]
    reclaimed_bytes: int


@dataclass(frozen=True)
class _Artifact:
    path: Path
    relative_path: str
    size_bytes: int
    modified_time_ns: int


@dataclass(frozen=True)
class _Inventory:
    entries: tuple[PolarCacheEntry, ...]
    entry_artifacts: tuple[_Artifact, ...]
    corrupt: tuple[_Artifact, ...]
    temporary: tuple[_Artifact, ...]


def _list_cache_entries(root: Path) -> tuple[PolarCacheEntry, ...]:
    return _scan_cache(root).entries


def _cache_stats(root: Path) -> PolarCacheStats:
    return _stats_from_inventory(_scan_cache(root))


def _maintain_cache(
    root: Path,
    *,
    max_bytes: int | None,
    max_age_s: float | None,
    corrupt_max_age_s: float | None,
    temporary_max_age_s: float | None,
) -> PolarCacheMaintenanceResult:
    _validate_max_bytes(max_bytes)
    _validate_seconds("max_age_s", max_age_s)
    _validate_seconds("corrupt_max_age_s", corrupt_max_age_s)
    _validate_seconds("temporary_max_age_s", temporary_max_age_s)

    inventory = _scan_cache(root)
    before = _stats_from_inventory(inventory)
    now_ns = time.time_ns()
    active = {
        artifact.relative_path: artifact
        for artifact in inventory.entry_artifacts
    }
    evicted: list[str] = []
    removed_corrupt: list[str] = []
    removed_temporary: list[str] = []
    reclaimed_bytes = 0

    if max_age_s is not None:
        max_age_ns = _seconds_to_ns(max_age_s)
        expired = sorted(
            (
                artifact
                for artifact in active.values()
                if now_ns - artifact.modified_time_ns > max_age_ns
            ),
            key=_oldest_first,
        )
        for artifact in expired:
            if _unlink(artifact.path):
                evicted.append(artifact.relative_path)
                reclaimed_bytes += artifact.size_bytes
            active.pop(artifact.relative_path, None)

    if max_bytes is not None:
        active_bytes = sum(artifact.size_bytes for artifact in active.values())
        for artifact in sorted(active.values(), key=_oldest_first):
            if active_bytes <= max_bytes:
                break
            if _unlink(artifact.path):
                evicted.append(artifact.relative_path)
                reclaimed_bytes += artifact.size_bytes
            active_bytes -= artifact.size_bytes
            active.pop(artifact.relative_path, None)

    if corrupt_max_age_s is not None:
        corrupt_age_ns = _seconds_to_ns(corrupt_max_age_s)
        for artifact in sorted(inventory.corrupt, key=_oldest_first):
            if now_ns - artifact.modified_time_ns <= corrupt_age_ns:
                continue
            if _unlink(artifact.path):
                removed_corrupt.append(artifact.relative_path)
                reclaimed_bytes += artifact.size_bytes

    if temporary_max_age_s is not None:
        temporary_age_ns = _seconds_to_ns(temporary_max_age_s)
        for artifact in sorted(inventory.temporary, key=_oldest_first):
            if now_ns - artifact.modified_time_ns <= temporary_age_ns:
                continue
            if _unlink(artifact.path):
                removed_temporary.append(artifact.relative_path)
                reclaimed_bytes += artifact.size_bytes

    _remove_empty_shards(root)
    after = _stats_from_inventory(_scan_cache(root))
    return PolarCacheMaintenanceResult(
        before=before,
        after=after,
        evicted_entries=tuple(evicted),
        removed_corrupt_entries=tuple(removed_corrupt),
        removed_temporary_entries=tuple(removed_temporary),
        reclaimed_bytes=reclaimed_bytes,
    )


def _scan_cache(root: Path) -> _Inventory:
    try:
        root_mode = root.lstat().st_mode
    except FileNotFoundError:
        return _Inventory((), (), (), ())
    if not stat.S_ISDIR(root_mode):
        raise NotADirectoryError(f"Polar cache root is not a directory: {root}")

    entries: list[PolarCacheEntry] = []
    entry_artifacts: list[_Artifact] = []
    corrupt: list[_Artifact] = []
    temporary: list[_Artifact] = []
    for child in sorted(root.iterdir(), key=lambda path: path.name):
        try:
            child_mode = child.lstat().st_mode
        except FileNotFoundError:
            continue
        if child.name == "corrupt" and stat.S_ISDIR(child_mode):
            corrupt.extend(_scan_corrupt(root, child))
            continue
        if not _SHARD_PATTERN.fullmatch(child.name) or not stat.S_ISDIR(child_mode):
            continue
        try:
            shard_paths = sorted(child.iterdir(), key=lambda item: item.name)
        except FileNotFoundError:
            continue
        for path in shard_paths:
            artifact = _regular_artifact(root, path)
            if artifact is None:
                continue
            entry_match = _CACHE_ENTRY_PATTERN.fullmatch(path.name)
            if entry_match and entry_match.group("key").startswith(child.name):
                cache_key = entry_match.group("key")
                entries.append(
                    PolarCacheEntry(
                        cache_key=cache_key,
                        relative_path=artifact.relative_path,
                        size_bytes=artifact.size_bytes,
                        modified_time_ns=artifact.modified_time_ns,
                    )
                )
                entry_artifacts.append(artifact)
            elif _TEMPORARY_ENTRY_PATTERN.fullmatch(path.name):
                temporary.append(artifact)

    entries.sort(key=lambda entry: entry.relative_path)
    entry_artifacts.sort(key=lambda artifact: artifact.relative_path)
    corrupt.sort(key=lambda artifact: artifact.relative_path)
    temporary.sort(key=lambda artifact: artifact.relative_path)
    return _Inventory(
        entries=tuple(entries),
        entry_artifacts=tuple(entry_artifacts),
        corrupt=tuple(corrupt),
        temporary=tuple(temporary),
    )


def _scan_corrupt(root: Path, directory: Path) -> list[_Artifact]:
    artifacts: list[_Artifact] = []
    try:
        paths = sorted(directory.iterdir(), key=lambda item: item.name)
    except FileNotFoundError:
        return artifacts
    for path in paths:
        if not _CORRUPT_ENTRY_PATTERN.fullmatch(path.name):
            continue
        artifact = _regular_artifact(root, path)
        if artifact is not None:
            artifacts.append(artifact)
    return artifacts


def _regular_artifact(root: Path, path: Path) -> _Artifact | None:
    try:
        information = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(information.st_mode):
        return None
    return _Artifact(
        path=path,
        relative_path=path.relative_to(root).as_posix(),
        size_bytes=information.st_size,
        modified_time_ns=information.st_mtime_ns,
    )


def _stats_from_inventory(inventory: _Inventory) -> PolarCacheStats:
    modified_times = tuple(entry.modified_time_ns for entry in inventory.entries)
    return PolarCacheStats(
        entry_count=len(inventory.entries),
        total_bytes=sum(entry.size_bytes for entry in inventory.entries),
        oldest_modified_time_ns=min(modified_times) if modified_times else None,
        newest_modified_time_ns=max(modified_times) if modified_times else None,
        corrupt_count=len(inventory.corrupt),
        corrupt_bytes=sum(artifact.size_bytes for artifact in inventory.corrupt),
        temporary_count=len(inventory.temporary),
        temporary_bytes=sum(
            artifact.size_bytes for artifact in inventory.temporary
        ),
    )


def _oldest_first(artifact: _Artifact) -> tuple[int, str]:
    return artifact.modified_time_ns, artifact.relative_path


def _unlink(path: Path) -> bool:
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def _remove_empty_shards(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if not _SHARD_PATTERN.fullmatch(path.name):
            continue
        try:
            path.rmdir()
        except OSError as error:
            if error.errno not in {errno.ENOENT, errno.ENOTEMPTY, errno.EEXIST}:
                raise


def _validate_max_bytes(value: int | None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("max_bytes must be a non-negative integer or None.")


def _validate_seconds(name: str, value: float | None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a non-negative finite number or None.")
    if not math.isfinite(float(value)) or value < 0.0:
        raise ValueError(f"{name} must be a non-negative finite number or None.")


def _seconds_to_ns(value: float) -> int:
    return int(float(value) * 1_000_000_000)
