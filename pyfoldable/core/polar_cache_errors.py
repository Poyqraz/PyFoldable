"""Typed failures shared by polar cache storage and coordination modules."""


class PolarCacheError(RuntimeError):
    """Raised when a filesystem cache operation cannot be completed safely."""


class PolarCacheLockError(PolarCacheError):
    """Raised when per-key process coordination cannot be completed safely."""


class PolarCacheLockTimeoutError(PolarCacheLockError):
    """Raised when a per-key process lock cannot be acquired before its deadline."""
