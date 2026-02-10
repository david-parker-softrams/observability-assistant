"""Tests for SQLite cache store."""

import time
from pathlib import Path

import pytest

from logai.cache.sqlite_store import CacheEntry, SQLiteStore


@pytest.fixture
async def cache_store(tmp_path: Path) -> SQLiteStore:
    """Create a temporary cache store for testing."""
    store = SQLiteStore(tmp_path / "test_cache")
    await store.initialize()
    return store


@pytest.mark.asyncio
class TestSQLiteStore:
    """Test SQLite cache store operations."""

    async def test_initialize_creates_database(self, tmp_path: Path) -> None:
        """Test that initialize creates database file."""
        cache_dir = tmp_path / "cache"
        store = SQLiteStore(cache_dir)
        await store.initialize()

        assert cache_dir.exists()
        assert (cache_dir / "cache.db").exists()

    async def test_set_and_get_entry(self, cache_store: SQLiteStore) -> None:
        """Test storing and retrieving cache entry."""
        entry = CacheEntry(
            id="test123",
            query_type="fetch_logs",
            log_group="/aws/lambda/test",
            start_time=1000,
            end_time=2000,
            payload={"events": [{"message": "test"}]},
            payload_size=100,
            log_count=1,
        )

        # Store entry
        await cache_store.set(entry)

        # Retrieve entry
        retrieved = await cache_store.get("test123")

        assert retrieved is not None
        assert retrieved.id == "test123"
        assert retrieved.query_type == "fetch_logs"
        assert retrieved.log_group == "/aws/lambda/test"
        assert retrieved.payload == {"events": [{"message": "test"}]}

    async def test_get_nonexistent_entry(self, cache_store: SQLiteStore) -> None:
        """Test getting non-existent entry returns None."""
        result = await cache_store.get("nonexistent")
        assert result is None

    async def test_get_expired_entry(self, cache_store: SQLiteStore) -> None:
        """Test that expired entries are not returned."""
        now = int(time.time())
        entry = CacheEntry(
            id="expired",
            query_type="fetch_logs",
            payload={"test": "data"},
            created_at=now - 3600,
            expires_at=now - 1,  # Expired 1 second ago
        )

        await cache_store.set(entry)

        # Should return None because entry is expired
        result = await cache_store.get("expired")
        assert result is None

    async def test_delete_entry(self, cache_store: SQLiteStore) -> None:
        """Test deleting cache entry."""
        entry = CacheEntry(
            id="to_delete",
            query_type="list_log_groups",
            payload={"log_groups": []},
        )

        await cache_store.set(entry)
        await cache_store.delete("to_delete")

        result = await cache_store.get("to_delete")
        assert result is None

    async def test_delete_expired(self, cache_store: SQLiteStore) -> None:
        """Test deleting expired entries."""
        now = int(time.time())

        # Add expired entry
        expired = CacheEntry(
            id="expired1",
            query_type="fetch_logs",
            payload={"test": "data"},
            expires_at=now - 100,
        )
        await cache_store.set(expired)

        # Add valid entry
        valid = CacheEntry(
            id="valid1",
            query_type="fetch_logs",
            payload={"test": "data"},
            expires_at=now + 3600,
        )
        await cache_store.set(valid)

        # Delete expired
        deleted_count = await cache_store.delete_expired()

        assert deleted_count == 1
        assert await cache_store.get("expired1") is None
        assert await cache_store.get("valid1") is not None

    async def test_delete_by_log_group(self, cache_store: SQLiteStore) -> None:
        """Test deleting entries by log group."""
        # Add entries for different log groups
        entry1 = CacheEntry(
            id="entry1",
            query_type="fetch_logs",
            log_group="/aws/lambda/func1",
            payload={"events": []},
        )
        entry2 = CacheEntry(
            id="entry2",
            query_type="fetch_logs",
            log_group="/aws/lambda/func2",
            payload={"events": []},
        )
        entry3 = CacheEntry(
            id="entry3",
            query_type="fetch_logs",
            log_group="/aws/lambda/func1",
            payload={"events": []},
        )

        await cache_store.set(entry1)
        await cache_store.set(entry2)
        await cache_store.set(entry3)

        # Delete func1 entries
        deleted = await cache_store.delete_by_log_group("/aws/lambda/func1")

        assert deleted == 2
        assert await cache_store.get("entry1") is None
        assert await cache_store.get("entry2") is not None
        assert await cache_store.get("entry3") is None

    async def test_clear_all(self, cache_store: SQLiteStore) -> None:
        """Test clearing all cache entries."""
        # Add multiple entries
        for i in range(5):
            entry = CacheEntry(
                id=f"entry{i}",
                query_type="fetch_logs",
                payload={"test": "data"},
            )
            await cache_store.set(entry)

        deleted = await cache_store.clear()

        assert deleted == 5
        assert await cache_store.get_entry_count() == 0

    async def test_get_cache_size(self, cache_store: SQLiteStore) -> None:
        """Test getting total cache size."""
        entry1 = CacheEntry(
            id="size1",
            query_type="fetch_logs",
            payload={"test": "data1"},
            payload_size=1000,
        )
        entry2 = CacheEntry(
            id="size2",
            query_type="fetch_logs",
            payload={"test": "data2"},
            payload_size=2000,
        )

        await cache_store.set(entry1)
        await cache_store.set(entry2)

        size = await cache_store.get_cache_size()
        assert size == 3000

    async def test_get_entry_count(self, cache_store: SQLiteStore) -> None:
        """Test getting entry count."""
        assert await cache_store.get_entry_count() == 0

        # Add entries
        for i in range(3):
            entry = CacheEntry(
                id=f"count{i}",
                query_type="fetch_logs",
                payload={"test": "data"},
            )
            await cache_store.set(entry)

        assert await cache_store.get_entry_count() == 3

    async def test_get_lru_entries(self, cache_store: SQLiteStore) -> None:
        """Test getting least recently used entries."""
        now = int(time.time())

        # Add entries with different access times
        for i in range(5):
            entry = CacheEntry(
                id=f"lru{i}",
                query_type="fetch_logs",
                payload={"test": "data"},
                last_accessed=now - (5 - i) * 100,  # Older entries first
            )
            await cache_store.set(entry)

        # Get 3 LRU entries
        lru = await cache_store.get_lru_entries(3)

        assert len(lru) == 3
        assert "lru0" in lru  # Oldest
        assert "lru1" in lru
        assert "lru2" in lru

    async def test_delete_entries_batch(self, cache_store: SQLiteStore) -> None:
        """Test deleting multiple entries."""
        # Add entries
        for i in range(5):
            entry = CacheEntry(
                id=f"batch{i}",
                query_type="fetch_logs",
                payload={"test": "data"},
            )
            await cache_store.set(entry)

        # Delete some entries
        deleted = await cache_store.delete_entries(["batch0", "batch2", "batch4"])

        assert deleted == 3
        assert await cache_store.get_entry_count() == 2
        assert await cache_store.get("batch1") is not None
        assert await cache_store.get("batch3") is not None

    async def test_hit_count_increment(self, cache_store: SQLiteStore) -> None:
        """Test that hit count is incremented on access."""
        entry = CacheEntry(
            id="hitcount",
            query_type="fetch_logs",
            payload={"test": "data"},
        )

        await cache_store.set(entry)

        # Access multiple times
        result1 = await cache_store.get("hitcount")
        result2 = await cache_store.get("hitcount")
        result3 = await cache_store.get("hitcount")

        assert result3 is not None
        assert result3.hit_count == 3

    async def test_get_statistics(self, cache_store: SQLiteStore) -> None:
        """Test getting cache statistics."""
        now = int(time.time())

        # Add some entries
        entry1 = CacheEntry(
            id="stat1",
            query_type="fetch_logs",
            payload={"events": [{"msg": "test"}]},
            payload_size=1000,
            log_count=10,
        )
        entry2 = CacheEntry(
            id="stat2",
            query_type="fetch_logs",
            payload={"events": []},
            payload_size=500,
            log_count=5,
            expires_at=now - 100,  # Expired
        )

        await cache_store.set(entry1)
        await cache_store.set(entry2)

        # Access entry1 a few times
        await cache_store.get("stat1")
        await cache_store.get("stat1")

        stats = await cache_store.get_statistics()

        assert stats["entry_count"] == 2
        assert stats["total_size_bytes"] == 1500
        assert stats["total_logs"] == 15
        assert stats["total_hits"] == 2
        assert stats["expired_count"] == 1

    async def test_update_existing_entry(self, cache_store: SQLiteStore) -> None:
        """Test updating an existing entry."""
        entry = CacheEntry(
            id="update",
            query_type="fetch_logs",
            payload={"version": 1},
        )

        await cache_store.set(entry)

        # Update with new data
        updated = CacheEntry(
            id="update",
            query_type="fetch_logs",
            payload={"version": 2},
        )

        await cache_store.set(updated)

        result = await cache_store.get("update")
        assert result is not None
        assert result.payload == {"version": 2}
