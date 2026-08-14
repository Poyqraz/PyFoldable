"""Cross-process, key-scoped advisory locks for polar cache generation."""

from __future__ import annotations

import errno
import json
import math
import os
import socket
import stat
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .polar_cache_errors import PolarCacheLockError, PolarCacheLockTimeoutError


POLAR_CACHE_LOCK_SCHEMA_VERSION = 1


if os.name == "nt":  # pragma: no cover - exercised on Windows CI/users.
    import msvcrt
else:  # pragma: no cover - branch selection is platform-specific.
    import fcntl


@dataclass(frozen=True)
class PolarCacheLockPolicy:
    """Bounded wait and backoff policy for one cache-key process lock."""

    wait_timeout_s: float = 60.0
    initial_poll_interval_s: float = 0.01
    max_poll_interval_s: float = 0.25
    backoff_factor: float = 1.5

    def __post_init__(self) -> None:
        for name in (
            "wait_timeout_s",
            "initial_poll_interval_s",
            "max_poll_interval_s",
            "backoff_factor",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite number.")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be a finite number.")
        if self.wait_timeout_s < 0.0:
            raise ValueError("wait_timeout_s must be non-negative.")
        if self.initial_poll_interval_s <= 0.0:
            raise ValueError("initial_poll_interval_s must be greater than zero.")
        if self.max_poll_interval_s < self.initial_poll_interval_s:
            raise ValueError(
                "max_poll_interval_s must be at least initial_poll_interval_s."
            )
        if self.backoff_factor < 1.0:
            raise ValueError("backoff_factor must be at least one.")


@dataclass(frozen=True)
class _LockAcquisition:
    relative_path: str
    waited_s: float
    recovered_stale_metadata: bool


class _ProcessKeyLock:
    def __init__(
        self,
        root: Path,
        cache_key: str,
        policy: PolarCacheLockPolicy,
    ) -> None:
        self._root = root
        self._cache_key = cache_key
        self._policy = policy
        self._path = _cache_key_lock_path(root, cache_key)
        self._descriptor: int | None = None
        self._token: str | None = None

    def __enter__(self) -> _LockAcquisition:
        started = time.monotonic()
        deadline = started + float(self._policy.wait_timeout_s)
        interval = float(self._policy.initial_poll_interval_s)
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise PolarCacheLockError(
                f"Could not prepare polar cache lock {self._path}."
            ) from error

        while True:
            descriptor: int | None = None
            try:
                descriptor = os.open(
                    self._path,
                    _lock_open_flags(),
                    0o600,
                )
                if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise OSError(errno.EINVAL, "Cache lock is not a regular file")
                if _try_os_lock(descriptor):
                    waited_s = time.monotonic() - started
                    recovered = _lock_file_has_owner_metadata(descriptor)
                    token = uuid.uuid4().hex
                    _write_owner_record(
                        descriptor,
                        cache_key=self._cache_key,
                        token=token,
                    )
                    self._descriptor = descriptor
                    self._token = token
                    return _LockAcquisition(
                        relative_path=self._path.relative_to(self._root).as_posix(),
                        waited_s=waited_s,
                        recovered_stale_metadata=recovered,
                    )
            except OSError as error:
                if descriptor is not None:
                    os.close(descriptor)
                raise PolarCacheLockError(
                    f"Could not acquire polar cache lock {self._path}."
                ) from error

            if descriptor is not None:
                os.close(descriptor)
            now = time.monotonic()
            remaining = deadline - now
            if remaining <= 0.0:
                raise PolarCacheLockTimeoutError(
                    f"Timed out waiting for polar cache lock {self._path}."
                )
            time.sleep(min(interval, remaining))
            interval = min(
                float(self._policy.max_poll_interval_s),
                interval * float(self._policy.backoff_factor),
            )

    def __exit__(self, exception_type, exception, traceback) -> bool:
        try:
            self._release()
        except PolarCacheLockError:
            if exception_type is None:
                raise
        return False

    def _release(self) -> None:
        descriptor = self._descriptor
        token = self._token
        self._descriptor = None
        self._token = None
        if descriptor is None or token is None:
            return

        ownership_error: PolarCacheLockError | None = None
        try:
            record = _read_owner_record(descriptor)
            if (
                record is None
                or record.get("token") != token
                or record.get("cache_key") != self._cache_key
            ):
                ownership_error = PolarCacheLockError(
                    f"Polar cache lock ownership changed for {self._path}."
                )
            else:
                _clear_owner_record(descriptor)
        except (OSError, TypeError, ValueError) as error:
            ownership_error = PolarCacheLockError(
                f"Could not release polar cache lock {self._path}."
            )
            ownership_error.__cause__ = error
        finally:
            try:
                _unlock_os_lock(descriptor)
            finally:
                os.close(descriptor)
        if ownership_error is not None:
            raise ownership_error


def _cache_key_lock_path(root: Path, cache_key: str) -> Path:
    if not _is_lower_hex(cache_key, length=64):
        raise ValueError("cache_key must be a 64-character lowercase hex digest.")
    return root / "locks" / cache_key[:2] / f"{cache_key}.lock"


def _lock_open_flags() -> int:
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _is_cache_key_lock_active(root: Path, cache_key: str) -> bool:
    path = _cache_key_lock_path(root, cache_key)
    try:
        descriptor = os.open(path, _existing_lock_open_flags())
    except FileNotFoundError:
        return False
    except OSError:
        # Maintenance must fail closed rather than evict an entry whose lock
        # cannot be inspected safely (for example, a substituted symlink).
        return True
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return True
        if not _try_os_lock(descriptor):
            return True
        _unlock_os_lock(descriptor)
        return False
    finally:
        os.close(descriptor)


def _existing_lock_open_flags() -> int:
    flags = os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _try_os_lock(descriptor: int) -> bool:
    if os.name == "nt":  # pragma: no cover - exercised on Windows CI/users.
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        except OSError as error:
            if error.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                return False
            raise
        return True
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        if error.errno in {errno.EACCES, errno.EAGAIN}:
            return False
        raise
    return True


def _unlock_os_lock(descriptor: int) -> None:
    if os.name == "nt":  # pragma: no cover - exercised on Windows CI/users.
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(descriptor, fcntl.LOCK_UN)


def _write_owner_record(descriptor: int, *, cache_key: str, token: str) -> None:
    record = {
        "schema_version": POLAR_CACHE_LOCK_SCHEMA_VERSION,
        "cache_key": cache_key,
        "token": token,
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "acquired_time_ns": time.time_ns(),
    }
    serialized = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    os.lseek(descriptor, 0, os.SEEK_SET)
    os.ftruncate(descriptor, 0)
    _write_all(descriptor, b"\n" + serialized + b"\n")
    os.fsync(descriptor)


def _clear_owner_record(descriptor: int) -> None:
    os.lseek(descriptor, 0, os.SEEK_SET)
    os.ftruncate(descriptor, 0)
    _write_all(descriptor, b"\n")
    os.fsync(descriptor)


def _lock_file_has_owner_metadata(descriptor: int) -> bool:
    raw = _read_lock_bytes(descriptor)
    return bool(raw[1:].strip()) if raw.startswith(b"\n") else bool(raw.strip())


def _read_owner_record(descriptor: int) -> dict[str, Any] | None:
    raw = _read_lock_bytes(descriptor)
    payload = raw[1:].strip() if raw.startswith(b"\n") else raw.strip()
    if not payload:
        return None
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise TypeError("Polar cache lock metadata must be a mapping.")
    required = {
        "schema_version",
        "cache_key",
        "token",
        "pid",
        "hostname",
        "acquired_time_ns",
    }
    if set(value) != required:
        raise ValueError("Polar cache lock metadata fields are invalid.")
    if value["schema_version"] != POLAR_CACHE_LOCK_SCHEMA_VERSION:
        raise ValueError("Polar cache lock schema version is unsupported.")
    if not _is_lower_hex(value["cache_key"], length=64):
        raise ValueError("Polar cache lock cache key is invalid.")
    if not _is_lower_hex(value["token"], length=32):
        raise ValueError("Polar cache lock owner token is invalid.")
    if (
        isinstance(value["pid"], bool)
        or not isinstance(value["pid"], int)
        or value["pid"] <= 0
    ):
        raise ValueError("Polar cache lock owner PID is invalid.")
    if not isinstance(value["hostname"], str) or not value["hostname"]:
        raise ValueError("Polar cache lock owner hostname is invalid.")
    if (
        isinstance(value["acquired_time_ns"], bool)
        or not isinstance(value["acquired_time_ns"], int)
        or value["acquired_time_ns"] < 0
    ):
        raise ValueError("Polar cache lock acquisition time is invalid.")
    return value


def _is_lower_hex(value: Any, *, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _read_lock_bytes(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 4096)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        if sum(len(item) for item in chunks) > 65_536:
            raise ValueError("Polar cache lock metadata is too large.")


def _write_all(descriptor: int, value: bytes) -> None:
    written = 0
    while written < len(value):
        count = os.write(descriptor, value[written:])
        if count <= 0:
            raise OSError("Could not write polar cache lock metadata.")
        written += count
