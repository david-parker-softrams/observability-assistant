"""Result cache manager for large tool results."""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class CachedResultSummary:
    """Summary of a cached result for context inclusion."""

    cache_id: str
    total_events: int
    time_range: dict[str, Any]
    sample_events: list[dict[str, Any]]
    event_statistics: dict[str, int]
    original_tool: str
    original_query: dict[str, Any]
    cached_at: int
    expires_at: int

    def to_context_dict(self) -> dict[str, Any]:
        """
        Convert to dict suitable for LLM context.

        This is what the agent sees instead of the full result.

        Returns:
            Dictionary suitable for LLM context
        """
        return {
            "cached": True,
            "cache_id": self.cache_id,
            "summary": {
                "total_events": self.total_events,
                "time_range": self.time_range,
                "sample_events": self.sample_events,
                "event_statistics": self.event_statistics,
            },
            "original_query": {
                "tool": self.original_tool,
                "parameters": self.original_query,
            },
            "cache_info": {
                "cached_at": self.cached_at,
                "expires_in_seconds": max(0, self.expires_at - int(time.time())),
            },
            "instructions": (
                "This result was cached because it exceeded the context window limit. "
                "Use fetch_cached_result_chunk(cache_id, offset, limit) to retrieve "
                "specific events. You can also filter by time_range or search_pattern."
            ),
        }


class ResultCacheManager:
    """
    Manages caching of large tool results outside the context window.

    When a tool result is too large for the context window, this manager:
    1. Stores the full result in SQLite
    2. Generates an intelligent summary
    3. Provides chunk-based retrieval

    Performance targets:
    - Cache storage: <50ms
    - Summary generation: <10ms
    - Chunk retrieval: <100ms
    """

    # Configuration
    DEFAULT_TTL_SECONDS = 3600  # 1 hour
    MAX_SAMPLE_EVENTS = 5
    MAX_CACHE_SIZE_MB = 100

    def __init__(
        self,
        cache_dir: Path,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_size_mb: int = MAX_CACHE_SIZE_MB,
    ):
        """
        Initialize result cache manager.

        Args:
            cache_dir: Directory for cache database
            ttl_seconds: Time-to-live for cached results (seconds)
            max_size_mb: Maximum cache size in MB
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / "result_cache.db"
        self.ttl_seconds = ttl_seconds
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database schema."""
        if self._initialized:
            return

        async with aiosqlite.connect(str(self.db_path)) as db:
            # Create cached results table
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS cached_results (
                    cache_id TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    query_params TEXT NOT NULL,
                    result_data TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    data_size_bytes INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    last_accessed INTEGER NOT NULL,
                    access_count INTEGER DEFAULT 0
                )
            """
            )

            # Create indexes for efficient queries
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cached_results_expires
                ON cached_results(expires_at)
            """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cached_results_created
                ON cached_results(created_at DESC)
            """
            )

            await db.commit()

        self._initialized = True
        logger.debug(f"ResultCacheManager initialized at {self.db_path}")

    def _generate_cache_id(self, tool_name: str, query_params: dict[str, Any]) -> str:
        """
        Generate a unique cache ID for a result.

        Uses hash of tool name + query parameters for deduplication.

        Args:
            tool_name: Name of the tool
            query_params: Query parameters dictionary

        Returns:
            Cache ID string
        """
        content = f"{tool_name}:{json.dumps(query_params, sort_keys=True)}"
        hash_digest = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"result_{hash_digest}"

    def _extract_event_statistics(self, events: list[dict[str, Any]]) -> dict[str, int]:
        """
        Extract statistics from events for the summary.

        Analyzes log levels, error types, and patterns.

        Args:
            events: List of event dictionaries

        Returns:
            Statistics dictionary with counts by log level
        """
        stats: dict[str, int] = {}

        for event in events:
            message = event.get("message", "")

            # Count by log level (heuristic detection)
            message_upper = message.upper()
            if "ERROR" in message_upper or "EXCEPTION" in message_upper:
                stats["ERROR"] = stats.get("ERROR", 0) + 1
            elif "WARN" in message_upper:
                stats["WARN"] = stats.get("WARN", 0) + 1
            elif "INFO" in message_upper:
                stats["INFO"] = stats.get("INFO", 0) + 1
            elif "DEBUG" in message_upper:
                stats["DEBUG"] = stats.get("DEBUG", 0) + 1
            else:
                stats["OTHER"] = stats.get("OTHER", 0) + 1

        return stats

    def _extract_time_range(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Extract time range from events.

        Args:
            events: List of event dictionaries

        Returns:
            Time range dictionary with start, end, and span
        """
        if not events:
            return {"start": None, "end": None}

        timestamps: list[int] = []
        for e in events:
            ts = e.get("timestamp")
            if ts is not None and isinstance(ts, int):
                timestamps.append(ts)

        if not timestamps:
            return {"start": None, "end": None}

        min_ts = min(timestamps)
        max_ts = max(timestamps)

        return {
            "start": min_ts,
            "end": max_ts,
            "span_ms": max_ts - min_ts,
        }

    def _sample_events(
        self, events: list[dict[str, Any]], count: int = MAX_SAMPLE_EVENTS
    ) -> list[dict[str, Any]]:
        """
        Sample representative events for the summary.

        Strategy: Take first, last, and evenly distributed middle samples.
        This gives the agent a sense of the data distribution.

        Args:
            events: List of event dictionaries
            count: Number of samples to return

        Returns:
            List of sampled events
        """
        if len(events) <= count:
            return events

        sampled = []

        # Always include first event
        sampled.append(events[0])

        # Include evenly distributed middle events
        if count > 2:
            step = len(events) // (count - 1)
            for i in range(1, count - 1):
                idx = min(i * step, len(events) - 1)
                if events[idx] not in sampled:
                    sampled.append(events[idx])

        # Always include last event
        if events[-1] not in sampled:
            sampled.append(events[-1])

        return sampled[:count]

    async def cache_result(
        self,
        tool_name: str,
        query_params: dict[str, Any],
        result: dict[str, Any],
    ) -> CachedResultSummary:
        """
        Cache a large tool result and return a summary.

        Args:
            tool_name: Name of the tool that generated the result
            query_params: Parameters passed to the tool
            result: Full result dictionary

        Returns:
            CachedResultSummary for context inclusion
        """
        await self.initialize()

        # Generate cache ID
        cache_id = self._generate_cache_id(tool_name, query_params)

        # Extract events (handle different result formats)
        events = result.get("events", result.get("logs", []))
        if not isinstance(events, list):
            events = []

        # Generate summary components
        event_stats = self._extract_event_statistics(events)
        time_range = self._extract_time_range(events)
        sample_events = self._sample_events(events)

        # Serialize result
        result_json = json.dumps(result)
        data_size = len(result_json.encode("utf-8"))

        now = int(time.time())
        expires_at = now + self.ttl_seconds

        # Store in database
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO cached_results
                (cache_id, tool_name, query_params, result_data, event_count,
                 data_size_bytes, created_at, expires_at, last_accessed, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
                (
                    cache_id,
                    tool_name,
                    json.dumps(query_params),
                    result_json,
                    len(events),
                    data_size,
                    now,
                    expires_at,
                    now,
                ),
            )
            await db.commit()

        logger.info(f"Cached result {cache_id}: {len(events)} events, {data_size} bytes")

        # Enforce cache size limit
        await self._enforce_size_limit()

        return CachedResultSummary(
            cache_id=cache_id,
            total_events=len(events),
            time_range=time_range,
            sample_events=sample_events,
            event_statistics=event_stats,
            original_tool=tool_name,
            original_query=query_params,
            cached_at=now,
            expires_at=expires_at,
        )

    async def fetch_chunk(
        self,
        cache_id: str,
        offset: int = 0,
        limit: int = 100,
        filter_pattern: str | None = None,
        time_start: int | None = None,
        time_end: int | None = None,
    ) -> dict[str, Any]:
        """
        Fetch a chunk of events from a cached result.

        Args:
            cache_id: Cache ID from summary
            offset: Starting index (0-based)
            limit: Number of events to fetch (max 200)
            filter_pattern: Optional text pattern to filter events
            time_start: Optional start timestamp filter (epoch milliseconds)
            time_end: Optional end timestamp filter (epoch milliseconds)

        Returns:
            Dictionary with events and metadata
        """
        await self.initialize()

        # Enforce limit
        limit = min(limit, 200)

        async with aiosqlite.connect(str(self.db_path)) as db:
            # Fetch cached result
            async with db.execute(
                """
                SELECT result_data, event_count, expires_at
                FROM cached_results
                WHERE cache_id = ?
            """,
                (cache_id,),
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                return {
                    "success": False,
                    "error": f"Cache entry '{cache_id}' not found",
                    "hint": "The cached result may have expired. Re-run the original query.",
                }

            result_data, event_count, expires_at = row

            # Check expiration
            if expires_at < int(time.time()):
                await db.execute("DELETE FROM cached_results WHERE cache_id = ?", (cache_id,))
                await db.commit()
                return {
                    "success": False,
                    "error": f"Cache entry '{cache_id}' has expired",
                    "hint": "Re-run the original query to get fresh results.",
                }

            # Update access stats
            await db.execute(
                """
                UPDATE cached_results
                SET last_accessed = ?, access_count = access_count + 1
                WHERE cache_id = ?
            """,
                (int(time.time()), cache_id),
            )
            await db.commit()

        # Parse result
        try:
            result = json.loads(result_data)
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "Failed to parse cached result",
            }

        # Extract events
        events = result.get("events", result.get("logs", []))

        # Apply filters
        filtered_events = events

        if filter_pattern:
            pattern_lower = filter_pattern.lower()
            filtered_events = [
                e for e in filtered_events if pattern_lower in e.get("message", "").lower()
            ]

        if time_start is not None:
            filtered_events = [e for e in filtered_events if e.get("timestamp", 0) >= time_start]

        if time_end is not None:
            filtered_events = [
                e for e in filtered_events if e.get("timestamp", float("inf")) <= time_end
            ]

        # Apply pagination
        total_filtered = len(filtered_events)
        chunk = filtered_events[offset : offset + limit]

        return {
            "success": True,
            "cache_id": cache_id,
            "events": chunk,
            "count": len(chunk),
            "offset": offset,
            "limit": limit,
            "total_filtered": total_filtered,
            "total_cached": event_count,
            "has_more": (offset + len(chunk)) < total_filtered,
            "filters_applied": {
                "pattern": filter_pattern,
                "time_start": time_start,
                "time_end": time_end,
            },
        }

    async def delete_expired(self) -> int:
        """
        Delete all expired cache entries.

        Returns:
            Number of entries deleted
        """
        await self.initialize()

        now = int(time.time())

        async with aiosqlite.connect(str(self.db_path)) as db:
            cursor = await db.execute("DELETE FROM cached_results WHERE expires_at < ?", (now,))
            await db.commit()
            deleted_count = cursor.rowcount or 0

        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} expired cache entries")

        return deleted_count

    async def _enforce_size_limit(self) -> None:
        """Enforce cache size limit by removing oldest entries."""
        await self.initialize()

        async with aiosqlite.connect(str(self.db_path)) as db:
            # Get current size
            async with db.execute(
                "SELECT COALESCE(SUM(data_size_bytes), 0) FROM cached_results"
            ) as cursor:
                row = await cursor.fetchone()
                current_size = row[0] if row else 0

            if current_size <= self.max_size_bytes:
                return

            # Need to free space - remove oldest entries
            target_size = int(self.max_size_bytes * 0.8)  # Free 20%

            async with db.execute(
                """
                SELECT cache_id, data_size_bytes
                FROM cached_results
                ORDER BY last_accessed ASC
            """
            ) as cursor:
                rows = await cursor.fetchall()

            to_delete = []
            freed = 0

            for cache_id, size in rows:
                if current_size - freed <= target_size:
                    break
                to_delete.append(cache_id)
                freed += size

            if to_delete:
                placeholders = ",".join("?" * len(to_delete))
                await db.execute(
                    f"DELETE FROM cached_results WHERE cache_id IN ({placeholders})",
                    to_delete,
                )
                await db.commit()
                logger.info(f"Evicted {len(to_delete)} cached results to enforce size limit")

    async def get_statistics(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        await self.initialize()

        async with aiosqlite.connect(str(self.db_path)) as db:
            async with db.execute(
                """
                SELECT
                    COUNT(*) as entry_count,
                    COALESCE(SUM(data_size_bytes), 0) as total_size,
                    COALESCE(SUM(event_count), 0) as total_events,
                    COALESCE(SUM(access_count), 0) as total_accesses
                FROM cached_results
            """
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            return {
                "entry_count": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0.0,
                "total_events": 0,
                "total_accesses": 0,
                "max_size_mb": self.max_size_bytes / (1024 * 1024),
                "ttl_seconds": self.ttl_seconds,
            }

        return {
            "entry_count": row[0],
            "total_size_bytes": row[1],
            "total_size_mb": round(row[1] / (1024 * 1024), 2),
            "total_events": row[2],
            "total_accesses": row[3],
            "max_size_mb": self.max_size_bytes / (1024 * 1024),
            "ttl_seconds": self.ttl_seconds,
        }
