"""Tests for cache manager."""

import asyncio
import time
from pathlib import Path

import pytest

from logai.cache.manager import CacheManager
from logai.cache.sqlite_store import CacheEntry
from logai.config.settings import LogAISettings


@pytest.fixture
def settings(tmp_path: Path) -> LogAISettings:
    """Create test settings with temporary cache directory."""
    return LogAISettings(
        anthropic_api_key="test-key",
        cache_dir=str(tmp_path / "cache"),
    )


@pytest.fixture
async def cache_manager(settings: LogAISettings) -> CacheManager:
    """Create cache manager for testing."""
    manager = CacheManager(settings)
    await manager.initialize()
    yield manager
    await manager.shutdown()


@pytest.mark.asyncio
class TestCacheManager:
    """Test cache manager functionality."""

    async def test_initialize_creates_store(self, settings: LogAISettings) -> None:
        """Test that initialization creates store and starts cleanup task."""
        manager = CacheManager(settings)
        await manager.initialize()

        assert manager._initialized
        assert manager._cleanup_task is not None

        await manager.shutdown()

    async def test_set_and_get(self, cache_manager: CacheManager) -> None:
        """Test storing and retrieving cached data."""
        payload = {"events": [{"message": "test log"}], "count": 1}

        await cache_manager.set(
            query_type="fetch_logs",
            payload=payload,
            log_group="/aws/lambda/test",
            start_time=1000,
            end_time=2000,
        )

        result = await cache_manager.get(
            query_type="fetch_logs",
            log_group="/aws/lambda/test",
            start_time=1000,
            end_time=2000,
        )

        assert result == payload

    async def test_get_miss_returns_none(self, cache_manager: CacheManager) -> None:
        """Test cache miss returns None."""
        result = await cache_manager.get(
            query_type="fetch_logs",
            log_group="/aws/lambda/nonexistent",
            start_time=1000,
            end_time=2000,
        )

        assert result is None

    async def test_cache_key_generation(self, cache_manager: CacheManager) -> None:
        """Test cache key generation is deterministic."""
        key1 = cache_manager.generate_cache_key(
            query_type="fetch_logs",
            log_group="/aws/lambda/test",
            start_time=1000,
            end_time=2000,
            filter_pattern="ERROR",
        )

        key2 = cache_manager.generate_cache_key(
            query_type="fetch_logs",
            log_group="/aws/lambda/test",
            start_time=1000,
            end_time=2000,
            filter_pattern="ERROR",
        )

        assert key1 == key2

    async def test_cache_key_time_normalization(self, cache_manager: CacheManager) -> None:
        """Test that cache keys are normalized to minute boundaries."""
        # These timestamps are within the same minute (60000 ms)
        key1 = cache_manager.generate_cache_key(
            query_type="fetch_logs",
            log_group="/aws/lambda/test",
            start_time=60000,  # 1:00:00
            end_time=120000,  # 2:00:00
        )

        key2 = cache_manager.generate_cache_key(
            query_type="fetch_logs",
            log_group="/aws/lambda/test",
            start_time=60999,  # 1:00:00.999 - same minute
            end_time=120999,  # 2:00:00.999 - same minute
        )

        assert key1 == key2

    async def test_cache_key_different_params(self, cache_manager: CacheManager) -> None:
        """Test that different parameters generate different keys."""
        key1 = cache_manager.generate_cache_key(
            query_type="fetch_logs",
            log_group="/aws/lambda/test1",
            start_time=1000,
            end_time=2000,
        )

        key2 = cache_manager.generate_cache_key(
            query_type="fetch_logs",
            log_group="/aws/lambda/test2",  # Different log group
            start_time=1000,
            end_time=2000,
        )

        assert key1 != key2

    async def test_calculate_ttl_list_log_groups(self, cache_manager: CacheManager) -> None:
        """Test TTL calculation for list_log_groups."""
        ttl = cache_manager.calculate_ttl("list_log_groups", None)
        assert ttl == 15 * 60  # 15 minutes

    async def test_calculate_ttl_recent_logs(self, cache_manager: CacheManager) -> None:
        """Test TTL for recent log data (< 5 minutes old)."""
        now = int(time.time() * 1000)
        recent_end_time = now - (2 * 60 * 1000)  # 2 minutes ago

        ttl = cache_manager.calculate_ttl("fetch_logs", recent_end_time)
        assert ttl == 60  # 1 minute for recent data

    async def test_calculate_ttl_historical_logs(self, cache_manager: CacheManager) -> None:
        """Test TTL for historical log data (> 5 minutes old)."""
        now = int(time.time() * 1000)
        old_end_time = now - (10 * 60 * 1000)  # 10 minutes ago

        ttl = cache_manager.calculate_ttl("fetch_logs", old_end_time)
        assert ttl == 24 * 60 * 60  # 24 hours for historical data

    async def test_calculate_ttl_statistics(self, cache_manager: CacheManager) -> None:
        """Test TTL for statistics queries."""
        ttl = cache_manager.calculate_ttl("get_log_statistics", int(time.time() * 1000))
        assert ttl == 5 * 60  # 5 minutes

    async def test_clear_all(self, cache_manager: CacheManager) -> None:
        """Test clearing all cache entries."""
        # Add multiple entries
        for i in range(3):
            await cache_manager.set(
                query_type="fetch_logs",
                payload={"events": []},
                log_group=f"/aws/lambda/func{i}",
                start_time=1000,
                end_time=2000,
            )

        deleted = await cache_manager.clear()
        assert deleted == 3

        stats = await cache_manager.get_statistics()
        assert stats["entry_count"] == 0

    async def test_clear_by_log_group(self, cache_manager: CacheManager) -> None:
        """Test clearing cache for specific log group."""
        # Add entries for different log groups
        await cache_manager.set(
            query_type="fetch_logs",
            payload={"events": []},
            log_group="/aws/lambda/func1",
            start_time=1000,
            end_time=2000,
        )

        await cache_manager.set(
            query_type="fetch_logs",
            payload={"events": []},
            log_group="/aws/lambda/func2",
            start_time=1000,
            end_time=2000,
        )

        # Clear only func1
        deleted = await cache_manager.clear(log_group="/aws/lambda/func1")
        assert deleted == 1

        # Verify func2 still exists
        result = await cache_manager.get(
            query_type="fetch_logs",
            log_group="/aws/lambda/func2",
            start_time=1000,
            end_time=2000,
        )
        assert result is not None

    async def test_get_statistics(self, cache_manager: CacheManager) -> None:
        """Test retrieving cache statistics."""
        # Add some data
        await cache_manager.set(
            query_type="fetch_logs",
            payload={"events": [{"msg": "test"}]},
            log_group="/aws/lambda/test",
            start_time=1000,
            end_time=2000,
        )

        stats = await cache_manager.get_statistics()

        assert "entry_count" in stats
        assert "total_size_bytes" in stats
        assert "total_size_mb" in stats
        assert stats["entry_count"] >= 1

    async def test_eviction_by_size(self, cache_manager: CacheManager) -> None:
        """Test that cache evicts entries when size limit is exceeded."""
        # Temporarily reduce max size for testing
        original_max = cache_manager.CACHE_MAX_SIZE_MB
        cache_manager.CACHE_MAX_SIZE_MB = 1  # 1 MB

        try:
            # Add entries until we exceed limit
            # Each entry is roughly 1MB
            large_payload = {"events": [{"message": "x" * 10000}] * 100}

            for i in range(3):
                await cache_manager.set(
                    query_type="fetch_logs",
                    payload=large_payload,
                    log_group=f"/aws/lambda/func{i}",
                    start_time=1000 + i * 1000,  # Different times for different keys
                    end_time=2000 + i * 1000,
                )

            # Should have triggered eviction
            stats = await cache_manager.get_statistics()
            size_mb = stats["total_size_mb"]

            # Size should be below limit due to eviction
            assert size_mb <= cache_manager.CACHE_MAX_SIZE_MB

        finally:
            cache_manager.CACHE_MAX_SIZE_MB = original_max

    async def test_eviction_by_entry_count(self, cache_manager: CacheManager) -> None:
        """Test that cache evicts entries when entry count limit is exceeded."""
        # Temporarily reduce max entries for testing
        original_max = cache_manager.CACHE_MAX_ENTRIES
        cache_manager.CACHE_MAX_ENTRIES = 5

        try:
            # Add more entries than limit
            for i in range(10):
                await cache_manager.set(
                    query_type="fetch_logs",
                    payload={"events": []},
                    log_group=f"/aws/lambda/func{i}",
                    start_time=1000 + i * 1000,
                    end_time=2000 + i * 1000,
                )

            # Should have triggered eviction
            stats = await cache_manager.get_statistics()
            assert stats["entry_count"] <= cache_manager.CACHE_MAX_ENTRIES

        finally:
            cache_manager.CACHE_MAX_ENTRIES = original_max

    async def test_lru_eviction_order(self, cache_manager: CacheManager) -> None:
        """Test that LRU eviction removes entries when limit is exceeded."""
        original_max = cache_manager.CACHE_MAX_ENTRIES
        original_batch = cache_manager.CACHE_EVICTION_BATCH
        cache_manager.CACHE_MAX_ENTRIES = 5
        cache_manager.CACHE_EVICTION_BATCH = 1  # Evict one at a time for predictable behavior

        try:
            # Add 5 entries (at limit)
            for i in range(5):
                await cache_manager.set(
                    query_type="fetch_logs",
                    payload={"events": []},
                    log_group="/aws/lambda/test",
                    start_time=1000 + i * 100000,
                    end_time=2000 + i * 100000,
                )

            stats = await cache_manager.get_statistics()
            assert stats["entry_count"] == 5

            # Add one more entry, should trigger eviction
            await cache_manager.set(
                query_type="fetch_logs",
                payload={"events": []},
                log_group="/aws/lambda/test",
                start_time=1000 + 5 * 100000,
                end_time=2000 + 5 * 100000,
            )

            # Should have evicted to stay within limit
            stats = await cache_manager.get_statistics()
            assert stats["entry_count"] <= cache_manager.CACHE_MAX_ENTRIES

        finally:
            cache_manager.CACHE_MAX_ENTRIES = original_max
            cache_manager.CACHE_EVICTION_BATCH = original_batch

    async def test_shutdown_cancels_cleanup_task(self, settings: LogAISettings) -> None:
        """Test that shutdown properly cancels the cleanup task."""
        manager = CacheManager(settings)
        await manager.initialize()

        assert manager._cleanup_task is not None
        assert not manager._cleanup_task.done()

        await manager.shutdown()

        assert manager._cleanup_task is None or manager._cleanup_task.done()

    async def test_cleanup_loop_removes_expired(self, settings: LogAISettings) -> None:
        """Test that cleanup loop periodically removes expired entries."""
        # Use very short cleanup interval for testing
        manager = CacheManager(settings)
        manager.CACHE_CLEANUP_INTERVAL = 0.1  # 100ms

        await manager.initialize()

        try:
            # Add an expired entry
            now = int(time.time())
            await manager.store.set(
                CacheEntry(  # type: ignore
                    id="expired_test",
                    query_type="fetch_logs",
                    payload={"test": "data"},
                    created_at=now - 3600,
                    expires_at=now - 1,
                )
            )

            # Wait for cleanup to run
            await asyncio.sleep(0.2)

            # Expired entry should be gone
            result = await manager.store.get("expired_test")
            assert result is None

        finally:
            await manager.shutdown()
