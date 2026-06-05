"""In-memory TTL cache shared across all modules in a single process."""

import time
import threading
from typing import Any

# TTL constants (seconds)
QUOTE_TTL = 60
TECHNICALS_TTL = 300
NEWS_TTL = 900
FUNDAMENTALS_TTL = 3600
SCREENER_TTL = 1800
INSTITUTIONAL_TTL = 21600   # 6 hours
ANALYST_TTL = 3600
VALIDATION_TTL = 600
CORRELATION_TTL = 3600


class Cache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        with self._lock:
            self._store[key] = (value, time.time() + ttl)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, int]:
        with self._lock:
            now = time.time()
            valid = sum(1 for _, (_, exp) in self._store.items() if exp > now)
            return {
                "total_entries": len(self._store),
                "valid_entries": valid,
                "expired_entries": len(self._store) - valid,
                "hits": self._hits,
                "misses": self._misses,
            }


# Module-level singleton — one cache instance shared across all imports
_cache = Cache()


def get(key: str) -> Any | None:
    return _cache.get(key)


def set(key: str, value: Any, ttl: int = 300) -> None:
    _cache.set(key, value, ttl)


def invalidate(key: str) -> None:
    _cache.invalidate(key)


def invalidate_prefix(prefix: str) -> None:
    _cache.invalidate_prefix(prefix)


def clear() -> None:
    _cache.clear()


def stats() -> dict[str, int]:
    return _cache.stats()
