"""Server-side TTL + optional Redis caching for grocery deal read paths (Issue #389)."""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
import logging
import threading
import time
from typing import Any, Callable, Optional, Tuple

from sqlalchemy import event
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DealCacheService:
    """Thread-safe TTL cache with versioned keys and optional Redis L2 backing."""

    _VERSION_REDIS_KEY = "deals:cache:version"

    def __init__(
        self,
        ttl_seconds: int = 300,
        max_entries: int = 512,
        enabled: bool = True,
        redis_client: Any = None,
    ) -> None:
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        self.enabled = bool(enabled)
        self._lock = threading.RLock()
        self._entries: "OrderedDict[str, Tuple[float, Any]]" = OrderedDict()
        self._version: int = 1
        self._hits: int = 0
        self._misses: int = 0
        self._invalidations: int = 0
        self._redis_client = redis_client

    def _get_redis(self) -> Any:
        """Return injected or lazily connected Redis client if explicitly configured."""
        return self._redis_client

    def attach_redis(self, redis_client: Any) -> None:
        """Attach a Redis client (used for multi-worker/shared deployments or testing)."""
        with self._lock:
            self._redis_client = redis_client

    def build_key(self, namespace: str, **params: Any) -> str:
        """Build a deterministic cache key scoped by namespace and normalized parameters."""
        serialized = json.dumps(params, sort_keys=True, default=str)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]
        return f"deals:v{self._current_version()}:{namespace}:{digest}"

    def _current_version(self) -> int:
        redis_client = self._get_redis()
        if redis_client is not None:
            try:
                raw = redis_client.get(self._VERSION_REDIS_KEY)
                if raw is not None:
                    self._version = int(raw)
            except Exception as exc:
                logger.debug("Redis version read failed, using local version: %s", exc)
        return self._version

    def get(self, key: str) -> Optional[Any]:
        """Fetch a cached payload if present and unexpired."""
        if not self.enabled:
            return None

        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                expires_at, value = entry
                if expires_at > now:
                    self._entries.move_to_end(key)
                    self._hits += 1
                    return value
                del self._entries[key]

        redis_client = self._get_redis()
        if redis_client is not None:
            try:
                payload = redis_client.get(key)
                if payload is not None:
                    decoded = json.loads(payload)
                    with self._lock:
                        self._store_local(key, decoded, now + self.ttl_seconds)
                        self._hits += 1
                    return decoded
            except Exception as exc:
                logger.debug("Redis get failed for %s: %s", key, exc)

        with self._lock:
            self._misses += 1
        return None

    def _store_local(self, key: str, value: Any, expires_at: float) -> None:
        self._entries[key] = (expires_at, value)
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store a value in the local TTL cache (and Redis when serializable)."""
        if not self.enabled:
            return

        ttl = max(1, int(ttl_seconds if ttl_seconds is not None else self.ttl_seconds))
        expires_at = time.monotonic() + ttl
        with self._lock:
            self._store_local(key, value, expires_at)

        redis_client = self._get_redis()
        if redis_client is not None:
            try:
                serialized = json.dumps(value, default=str)
                redis_client.setex(key, ttl, serialized)
            except Exception as exc:
                logger.debug("Redis setex skipped/failed for %s: %s", key, exc)

    async def get_or_set_async(
        self,
        namespace: str,
        loader: Callable[[], Any],
        ttl_seconds: Optional[int] = None,
        **params: Any,
    ) -> Any:
        """Return cached entry for (namespace, params) or await loader() and cache result."""
        if not self.enabled:
            return await loader()

        key = self.build_key(namespace, **params)
        cached = self.get(key)
        if cached is not None:
            return cached

        value = await loader()
        self.set(key, value, ttl_seconds=ttl_seconds)
        return value

    def invalidate_deals(self) -> int:
        """Invalidate all cached deal entries in O(1) via version increment."""
        with self._lock:
            self._entries.clear()
            self._version += 1
            self._invalidations += 1
            new_version = self._version

        redis_client = self._get_redis()
        if redis_client is not None:
            try:
                new_version = int(redis_client.incr(self._VERSION_REDIS_KEY))
                with self._lock:
                    self._version = new_version
            except Exception as exc:
                logger.debug("Redis version bump failed: %s", exc)

        return new_version

    def reset_stats(self) -> None:
        """Clear cache entries and reset hit/miss counters (useful in tests)."""
        with self._lock:
            self._entries.clear()
            self._hits = 0
            self._misses = 0
            self._invalidations = 0

    def get_stats(self) -> dict[str, Any]:
        """Return current cache utilization and hit/miss telemetry."""
        with self._lock:
            now = time.monotonic()
            active = sum(1 for exp, _ in self._entries.values() if exp > now)
            total_requests = self._hits + self._misses
            hit_rate = round((self._hits / total_requests) * 100, 1) if total_requests else 0.0
            return {
                "enabled": self.enabled,
                "ttl_seconds": self.ttl_seconds,
                "version": self._version,
                "entries": active,
                "max_entries": self.max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_pct": hit_rate,
                "invalidations": self._invalidations,
                "redis_attached": self._redis_client is not None,
            }


def _create_default_deal_cache() -> DealCacheService:
    from app.core.config import settings

    ttl = getattr(settings, "DEAL_CACHE_TTL_SECONDS", 300)
    max_entries = getattr(settings, "DEAL_CACHE_MAX_ENTRIES", 512)
    enabled = getattr(settings, "DEAL_CACHE_ENABLED", True)
    return DealCacheService(ttl_seconds=ttl, max_entries=max_entries, enabled=enabled)


deal_cache = _create_default_deal_cache()


def _install_deal_invalidation_hooks() -> None:
    """Automatically invalidate deal_cache whenever Deal, Product, or Store records commit."""
    from app.models.all_models import Deal, Product, Store

    watched_types = (Deal, Product, Store)

    @event.listens_for(Session, "before_commit")
    def _mark_deal_mutation(session: Session) -> None:
        pending = tuple(session.new) + tuple(session.dirty) + tuple(session.deleted)
        if any(isinstance(obj, watched_types) for obj in pending):
            session.info["_invalidate_deal_cache"] = True

    @event.listens_for(Session, "after_commit")
    def _flush_deal_cache(session: Session) -> None:
        if session.info.pop("_invalidate_deal_cache", False):
            deal_cache.invalidate_deals()


_install_deal_invalidation_hooks()
