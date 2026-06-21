"""
Disk cache for API responses.

Wraps ``diskcache.Cache`` with a key-composition helper so that
every API method gets a unique, deterministic cache key from its
method name + normalized arguments.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from diskcache import Cache as _DiskCache

_WEEK_SECONDS = 60 * 60 * 24 * 7


class ResponseCache:
    """Thin wrapper around diskcache for API response caching.

    Keys are SHA-256 hashes of ``{module}.{method}:{json_args}`` so
    there are never filesystem-name collisions regardless of argument
    length or special characters.
    """

    def __init__(
        self,
        directory: str | Path,
        ttl: int = _WEEK_SECONDS,
        size_limit: int = 2**30,
    ):
        """
        Args:
            directory:  Path to the cache directory (created if missing).
            ttl:        Time-to-live in seconds (default 7 days).
            size_limit: Maximum cache size in bytes (default 1 GiB).
        """
        self._cache = _DiskCache(str(directory), size_limit=size_limit)
        self._ttl = ttl

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any | None:
        """Return cached value, or None if missing / expired."""
        try:
            return self._cache.get(key)
        except Exception:
            return None

    def set(self, key: str, value: Any) -> None:
        """Store *value* with the configured TTL."""
        self._cache.set(key, value, expire=self._ttl)

    def clear(self) -> None:
        """Wipe the entire cache."""
        self._cache.clear()

    @property
    def size(self) -> int:
        """Approximate number of cached entries."""
        return len(self._cache)

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def make_key(module: str, method: str, *args: Any, **kwargs: Any) -> str:
        """Deterministic cache key from method name + serialized arguments."""
        raw = f"{module}.{method}:{args!r},{kwargs!r}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def make_key_dict(module: str, method: str, **kwargs: Any) -> str:
        """Convenience wrapper when all arguments are keyword-only."""
        return ResponseCache.make_key(module, method, (), kwargs)
