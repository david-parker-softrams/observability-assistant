"""Cache manager for orchestrating cache operations."""

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from logai.cache.sqlite_store import CacheEntry, SQLiteStore
from logai.config.settings import LogAISettings


class CacheManager:
    """Manages caching of log data and query results."""

    # Configuration constants
    CACHE_MAX_SIZE_MB = 500  # Maximum cache size
    CACHE_MAX_ENTRIES = 10000  # Maximum number of entries
    CACHE_EVICTION_BATCH = 100  # Entries to evict at once
    CACHE_CLEANUP_INTERVAL = 300  # Seconds between cleanup runs

    def __init__(self, settings: LogAISettings):
        """Initialize cache manager.

        Args:
            settings: Application settings
        """
        self.settings = settings
        cache_dir = Path(settings.cache_dir).expanduser()
        self.store = SQLiteStore(cache_dir)
        self._cleanup_task: asyncio.Task[None] | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize cache manager and start background tasks."""
        if self._initialized:
            return

        await self.store.initialize()

        # Start background cleanup task
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown cache manager and stop background tasks."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        self._initialized = False

    async def get(
        self,
        query_type: str,
        log_group: str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        filter_pattern: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Get cached result if available.

        Args:
            query_type: Type of query (e.g., 'fetch_logs', 'list_log_groups')
            log_group: Log group name
            start_time: Start time in epoch milliseconds
            end_time: End time in epoch milliseconds
            filter_pattern: CloudWatch filter pattern
            **kwargs: Additional query parameters

        Returns:
            Cached result payload if found, None otherwise
        """
        await self.initialize()

        cache_key = self.generate_cache_key(
            query_type=query_type,
            log_group=log_group,
            start_time=start_time,
            end_time=end_time,
            filter_pattern=filter_pattern,
            **kwargs,
        )

        entry = await self.store.get(cache_key)
        return entry.payload if entry else None

    async def set(
        self,
        query_type: str,
        payload: dict[str, Any],
        log_group: str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        filter_pattern: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Cache a query result.

        Args:
            query_type: Type of query
            payload: Result data to cache
            log_group: Log group name
            start_time: Start time in epoch milliseconds
            end_time: End time in epoch milliseconds
            filter_pattern: CloudWatch filter pattern
            **kwargs: Additional query parameters
        """
        await self.initialize()

        cache_key = self.generate_cache_key(
            query_type=query_type,
            log_group=log_group,
            start_time=start_time,
            end_time=end_time,
            filter_pattern=filter_pattern,
            **kwargs,
        )

        # Calculate TTL
        ttl_seconds = self.calculate_ttl(query_type, end_time)
        now = int(time.time())

        # Calculate payload size
        payload_json = json.dumps(payload)
        payload_size = len(payload_json.encode("utf-8"))

        # Get log count from payload
        log_count = 0
        if "events" in payload:
            log_count = len(payload["events"])
        elif "log_groups" in payload:
            log_count = len(payload["log_groups"])

        # Create cache entry
        entry = CacheEntry(
            id=cache_key,
            query_type=query_type,
            log_group=log_group,
            start_time=start_time,
            end_time=end_time,
            filter_pattern=filter_pattern,
            payload=payload,
            payload_size=payload_size,
            log_count=log_count,
            created_at=now,
            expires_at=now + ttl_seconds,
            last_accessed=now,
            hit_count=0,
        )

        # Store entry
        await self.store.set(entry)

        # Check if eviction is needed
        await self.evict_if_needed()

    async def clear(self, log_group: str | None = None) -> int:
        """Clear cache entries.

        Args:
            log_group: If provided, only clear entries for this log group

        Returns:
            Number of entries deleted
        """
        await self.initialize()

        if log_group:
            return await self.store.delete_by_log_group(log_group)
        else:
            return await self.store.clear()

    async def get_statistics(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary of cache statistics
        """
        await self.initialize()
        return await self.store.get_statistics()

    def generate_cache_key(
        self,
        query_type: str,
        log_group: str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        filter_pattern: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate deterministic cache key.

        Normalizes time to minute boundaries for better hit rate.

        Args:
            query_type: Type of query
            log_group: Log group name
            start_time: Start time in epoch milliseconds
            end_time: End time in epoch milliseconds
            filter_pattern: CloudWatch filter pattern
            **kwargs: Additional query parameters

        Returns:
            Cache key (SHA256 hash)
        """
        # Normalize time to minute boundaries for better hit rate
        start_normalized = None
        end_normalized = None

        if start_time is not None:
            start_normalized = (start_time // 60000) * 60000
        if end_time is not None:
            end_normalized = (end_time // 60000) * 60000

        key_parts = {
            "type": query_type,
            "log_group": log_group,
            "start": start_normalized,
            "end": end_normalized,
            "filter": filter_pattern,
            **{k: v for k, v in sorted(kwargs.items())},
        }

        key_string = json.dumps(key_parts, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def calculate_ttl(self, query_type: str, end_time: int | None) -> int:
        """Calculate TTL based on query type and recency.

        Args:
            query_type: Type of query
            end_time: End time in epoch milliseconds

        Returns:
            TTL in seconds
        """
        if query_type == "list_log_groups":
            return 15 * 60  # 15 minutes

        if query_type in ("fetch_logs", "search_logs"):
            if end_time is None:
                return 60  # 1 minute for queries without end time

            now = int(time.time() * 1000)
            age_minutes = (now - end_time) / 60000

            if age_minutes < 5:
                return 60  # 1 minute for very recent data
            else:
                return 24 * 60 * 60  # 24 hours for historical data

        if query_type == "get_log_statistics":
            return 5 * 60  # 5 minutes

        return 60 * 60  # 1 hour default

    async def evict_if_needed(self) -> int:
        """Evict entries if cache exceeds limits.

        Returns:
            Number of entries evicted
        """
        await self.initialize()

        current_size = await self.store.get_cache_size()
        entry_count = await self.store.get_entry_count()

        max_size_bytes = self.CACHE_MAX_SIZE_MB * 1024 * 1024
        target_size_bytes = int(max_size_bytes * 0.9)  # Target 90% of max

        # Check if eviction is needed
        if current_size <= max_size_bytes and entry_count <= self.CACHE_MAX_ENTRIES:
            return 0

        total_evicted = 0

        # First, delete expired entries
        expired_count = await self.store.delete_expired()
        total_evicted += expired_count

        # Check size again
        current_size = await self.store.get_cache_size()
        entry_count = await self.store.get_entry_count()

        # If still over limit, evict by LRU
        while current_size > target_size_bytes or entry_count > self.CACHE_MAX_ENTRIES:
            lru_entries = await self.store.get_lru_entries(self.CACHE_EVICTION_BATCH)
            if not lru_entries:
                break

            evicted = await self.store.delete_entries(lru_entries)
            total_evicted += evicted

            current_size = await self.store.get_cache_size()
            entry_count = await self.store.get_entry_count()

        return total_evicted

    async def _cleanup_loop(self) -> None:
        """Background task to periodically clean up expired entries."""
        while True:
            try:
                await asyncio.sleep(self.CACHE_CLEANUP_INTERVAL)
                await self.store.delete_expired()
                await self.evict_if_needed()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue - don't let cleanup failures kill the task
                logging.error(f"Cache cleanup failed: {e}", exc_info=True)
