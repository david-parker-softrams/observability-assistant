"""SQLite-based cache store for log data and query results."""

import json
import time
from pathlib import Path
from typing import Any

import aiosqlite


class CacheEntry:
    """Represents a cache entry."""

    def __init__(
        self,
        id: str,
        query_type: str,
        payload: dict[str, Any],
        log_group: str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        filter_pattern: str | None = None,
        payload_size: int = 0,
        log_count: int = 0,
        created_at: int | None = None,
        expires_at: int | None = None,
        last_accessed: int | None = None,
        hit_count: int = 0,
    ):
        """Initialize cache entry."""
        self.id = id
        self.query_type = query_type
        self.log_group = log_group
        self.start_time = start_time
        self.end_time = end_time
        self.filter_pattern = filter_pattern
        self.payload = payload
        self.payload_size = payload_size
        self.log_count = log_count
        self.created_at = created_at or int(time.time())
        self.expires_at = expires_at or (self.created_at + 3600)  # Default 1 hour
        self.last_accessed = last_accessed or self.created_at
        self.hit_count = hit_count


class SQLiteStore:
    """SQLite-based cache store."""

    def __init__(self, cache_dir: Path):
        """Initialize SQLite store.

        Args:
            cache_dir: Directory for cache database
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / "cache.db"
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database schema."""
        if self._initialized:
            return

        async with aiosqlite.connect(str(self.db_path)) as db:
            # Create cache entries table
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    id TEXT PRIMARY KEY,
                    query_type TEXT NOT NULL,
                    log_group TEXT,
                    start_time INTEGER,
                    end_time INTEGER,
                    filter_pattern TEXT,
                    payload TEXT NOT NULL,
                    payload_size INTEGER,
                    log_count INTEGER,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    last_accessed INTEGER NOT NULL,
                    hit_count INTEGER DEFAULT 0
                )
                """
            )

            # Create indexes
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_log_group_time
                ON cache_entries(log_group, start_time, end_time)
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_expires_at
                ON cache_entries(expires_at)
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_last_accessed
                ON cache_entries(last_accessed)
                """
            )

            # Create cache statistics table
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_stats (
                    stat_key TEXT PRIMARY KEY,
                    stat_value INTEGER
                )
                """
            )

            await db.commit()

        self._initialized = True

    async def get(self, key: str) -> CacheEntry | None:
        """Retrieve a cache entry by key.

        Args:
            key: Cache key

        Returns:
            Cache entry if found and not expired, None otherwise
        """
        await self.initialize()

        async with aiosqlite.connect(str(self.db_path)) as db:
            async with db.execute(
                """
                SELECT id, query_type, log_group, start_time, end_time,
                       filter_pattern, payload, payload_size, log_count,
                       created_at, expires_at, last_accessed, hit_count
                FROM cache_entries
                WHERE id = ?
                """,
                (key,),
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                return None

            # Check if expired
            now = int(time.time())
            if row[10] < now:  # expires_at < now
                # Delete expired entry
                await db.execute("DELETE FROM cache_entries WHERE id = ?", (key,))
                await db.commit()
                return None

            # Update last accessed and hit count
            await db.execute(
                """
                UPDATE cache_entries
                SET last_accessed = ?, hit_count = hit_count + 1
                WHERE id = ?
                """,
                (now, key),
            )
            await db.commit()

            # Parse payload
            try:
                payload = json.loads(row[6])
            except json.JSONDecodeError:
                # If cache DB gets corrupted, don't crash - just skip the entry
                # Log warning and delete corrupted entry
                await db.execute("DELETE FROM cache_entries WHERE id = ?", (key,))
                await db.commit()
                return None

            return CacheEntry(
                id=row[0],
                query_type=row[1],
                log_group=row[2],
                start_time=row[3],
                end_time=row[4],
                filter_pattern=row[5],
                payload=payload,
                payload_size=row[7],
                log_count=row[8],
                created_at=row[9],
                expires_at=row[10],
                last_accessed=now,
                hit_count=row[12] + 1,
            )

    async def set(self, entry: CacheEntry) -> None:
        """Store a cache entry.

        Args:
            entry: Cache entry to store
        """
        await self.initialize()

        payload_json = json.dumps(entry.payload)

        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO cache_entries
                (id, query_type, log_group, start_time, end_time, filter_pattern,
                 payload, payload_size, log_count, created_at, expires_at,
                 last_accessed, hit_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.query_type,
                    entry.log_group,
                    entry.start_time,
                    entry.end_time,
                    entry.filter_pattern,
                    payload_json,
                    entry.payload_size,
                    entry.log_count,
                    entry.created_at,
                    entry.expires_at,
                    entry.last_accessed,
                    entry.hit_count,
                ),
            )
            await db.commit()

    async def delete(self, key: str) -> None:
        """Delete a cache entry by key.

        Args:
            key: Cache key
        """
        await self.initialize()

        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute("DELETE FROM cache_entries WHERE id = ?", (key,))
            await db.commit()

    async def delete_expired(self) -> int:
        """Delete all expired cache entries.

        Returns:
            Number of entries deleted
        """
        await self.initialize()

        now = int(time.time())

        async with aiosqlite.connect(str(self.db_path)) as db:
            cursor = await db.execute("DELETE FROM cache_entries WHERE expires_at < ?", (now,))
            await db.commit()
            result = cursor.rowcount
            return int(result) if result is not None else 0

    async def delete_by_log_group(self, log_group: str) -> int:
        """Delete all entries for a specific log group.

        Args:
            log_group: Log group name

        Returns:
            Number of entries deleted
        """
        await self.initialize()

        async with aiosqlite.connect(str(self.db_path)) as db:
            cursor = await db.execute("DELETE FROM cache_entries WHERE log_group = ?", (log_group,))
            await db.commit()
            result = cursor.rowcount
            return int(result) if result is not None else 0

    async def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries deleted
        """
        await self.initialize()

        async with aiosqlite.connect(str(self.db_path)) as db:
            cursor = await db.execute("DELETE FROM cache_entries")
            await db.commit()
            result = cursor.rowcount
            return int(result) if result is not None else 0

    async def get_cache_size(self) -> int:
        """Get total cache size in bytes.

        Returns:
            Total size of all payloads in bytes
        """
        await self.initialize()

        async with aiosqlite.connect(str(self.db_path)) as db:
            async with db.execute(
                "SELECT COALESCE(SUM(payload_size), 0) FROM cache_entries"
            ) as cursor:
                row = await cursor.fetchone()
                return int(row[0]) if row else 0

    async def get_entry_count(self) -> int:
        """Get total number of cache entries.

        Returns:
            Number of cache entries
        """
        await self.initialize()

        async with aiosqlite.connect(str(self.db_path)) as db:
            async with db.execute("SELECT COUNT(*) FROM cache_entries") as cursor:
                row = await cursor.fetchone()
                return int(row[0]) if row else 0

    async def get_lru_entries(self, limit: int = 100) -> list[str]:
        """Get least recently used entries.

        Args:
            limit: Number of entries to return

        Returns:
            List of cache entry IDs
        """
        await self.initialize()

        async with aiosqlite.connect(str(self.db_path)) as db:
            async with db.execute(
                """
                SELECT id FROM cache_entries
                ORDER BY last_accessed ASC
                LIMIT ?
                """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def delete_entries(self, entry_ids: list[str]) -> int:
        """Delete multiple cache entries by ID.

        Args:
            entry_ids: List of cache entry IDs to delete

        Returns:
            Number of entries deleted
        """
        if not entry_ids:
            return 0

        await self.initialize()

        placeholders = ",".join("?" * len(entry_ids))
        async with aiosqlite.connect(str(self.db_path)) as db:
            cursor = await db.execute(
                f"DELETE FROM cache_entries WHERE id IN ({placeholders})", entry_ids
            )
            await db.commit()
            result = cursor.rowcount
            return int(result) if result is not None else 0

    async def get_statistics(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary of cache statistics
        """
        await self.initialize()

        async with aiosqlite.connect(str(self.db_path)) as db:
            # Get entry count
            async with db.execute("SELECT COUNT(*) FROM cache_entries") as cursor:
                row = await cursor.fetchone()
                entry_count = row[0] if row else 0

            # Get total size
            async with db.execute(
                "SELECT COALESCE(SUM(payload_size), 0) FROM cache_entries"
            ) as cursor:
                row = await cursor.fetchone()
                total_size = row[0] if row else 0

            # Get total log count
            async with db.execute(
                "SELECT COALESCE(SUM(log_count), 0) FROM cache_entries"
            ) as cursor:
                row = await cursor.fetchone()
                total_logs = row[0] if row else 0

            # Get total hits
            async with db.execute(
                "SELECT COALESCE(SUM(hit_count), 0) FROM cache_entries"
            ) as cursor:
                row = await cursor.fetchone()
                total_hits = row[0] if row else 0

            # Get expired count
            now = int(time.time())
            async with db.execute(
                "SELECT COUNT(*) FROM cache_entries WHERE expires_at < ?", (now,)
            ) as cursor:
                row = await cursor.fetchone()
                expired_count = row[0] if row else 0

            return {
                "entry_count": entry_count,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "total_logs": total_logs,
                "total_hits": total_hits,
                "expired_count": expired_count,
                "db_path": str(self.db_path),
            }
