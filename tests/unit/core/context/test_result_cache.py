"""Unit tests for ResultCacheManager."""

import asyncio
import json
import time
from pathlib import Path

import pytest
from logai.core.context.result_cache import CachedResultSummary, ResultCacheManager


@pytest.fixture
async def cache_manager(tmp_path: Path) -> ResultCacheManager:
    """Create a result cache manager for testing."""
    manager = ResultCacheManager(cache_dir=tmp_path / "cache", ttl_seconds=3600, max_size_mb=10)
    await manager.initialize()
    return manager


@pytest.fixture
def sample_result() -> dict:
    """Create a sample result with events."""
    return {
        "events": [
            {
                "timestamp": 1707750000000,
                "message": "ERROR: Database connection failed",
            },
            {
                "timestamp": 1707751800000,
                "message": "WARN: High memory usage detected",
            },
            {
                "timestamp": 1707752700000,
                "message": "INFO: Request processed successfully",
            },
            {
                "timestamp": 1707753600000,
                "message": "ERROR: API timeout occurred",
            },
        ]
    }


@pytest.fixture
def large_result() -> dict:
    """Create a large result with many events."""
    return {
        "events": [
            {"timestamp": 1707750000000 + i * 1000, "message": f"Event {i}"} for i in range(1000)
        ]
    }


class TestCachedResultSummary:
    """Tests for CachedResultSummary dataclass."""

    def test_to_context_dict(self) -> None:
        """Test conversion to context dictionary."""
        summary = CachedResultSummary(
            cache_id="result_abc123",
            total_events=100,
            time_range={"start": 1707750000000, "end": 1707753600000, "span_ms": 3600000},
            sample_events=[{"timestamp": 1707750000000, "message": "Test event"}],
            event_statistics={"ERROR": 10, "INFO": 90},
            original_tool="fetch_logs",
            original_query={"log_group": "/aws/lambda/test"},
            cached_at=1707754000,
            expires_at=1707757600,
        )

        context_dict = summary.to_context_dict()

        assert context_dict["cached"] is True
        assert context_dict["cache_id"] == "result_abc123"
        assert context_dict["summary"]["total_events"] == 100
        assert context_dict["summary"]["time_range"]["start"] == 1707750000000
        assert context_dict["summary"]["event_statistics"] == {"ERROR": 10, "INFO": 90}
        assert context_dict["original_query"]["tool"] == "fetch_logs"
        assert "fetch_cached_result_chunk" in context_dict["instructions"]

    def test_to_context_dict_expires_in_seconds(self) -> None:
        """Test expires_in_seconds calculation."""
        now = int(time.time())
        expires_at = now + 1800  # 30 minutes from now

        summary = CachedResultSummary(
            cache_id="result_test",
            total_events=10,
            time_range={},
            sample_events=[],
            event_statistics={},
            original_tool="test_tool",
            original_query={},
            cached_at=now,
            expires_at=expires_at,
        )

        context_dict = summary.to_context_dict()
        expires_in = context_dict["cache_info"]["expires_in_seconds"]

        # Should be approximately 1800 seconds (allow some test execution time)
        assert 1795 <= expires_in <= 1805


class TestResultCacheManager:
    """Tests for ResultCacheManager."""

    @pytest.mark.asyncio
    async def test_initialization(self, tmp_path: Path) -> None:
        """Test cache manager initialization."""
        manager = ResultCacheManager(cache_dir=tmp_path / "cache")
        await manager.initialize()

        assert manager.db_path.exists()
        assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_initialization_idempotent(self, cache_manager: ResultCacheManager) -> None:
        """Test that initialize() can be called multiple times safely."""
        await cache_manager.initialize()
        await cache_manager.initialize()
        assert cache_manager._initialized is True

    @pytest.mark.asyncio
    async def test_cache_result_basic(
        self, cache_manager: ResultCacheManager, sample_result: dict
    ) -> None:
        """Test caching a basic result."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=sample_result,
        )

        assert summary.cache_id.startswith("result_")
        assert summary.total_events == 4
        assert summary.original_tool == "fetch_logs"
        assert len(summary.sample_events) <= ResultCacheManager.MAX_SAMPLE_EVENTS

    @pytest.mark.asyncio
    async def test_cache_result_event_statistics(
        self, cache_manager: ResultCacheManager, sample_result: dict
    ) -> None:
        """Test event statistics extraction."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=sample_result,
        )

        stats = summary.event_statistics
        assert stats["ERROR"] == 2  # Two ERROR messages
        assert stats["WARN"] == 1  # One WARN message
        assert stats["INFO"] == 1  # One INFO message

    @pytest.mark.asyncio
    async def test_cache_result_time_range(
        self, cache_manager: ResultCacheManager, sample_result: dict
    ) -> None:
        """Test time range extraction."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=sample_result,
        )

        time_range = summary.time_range
        assert time_range["start"] == 1707750000000
        assert time_range["end"] == 1707753600000
        assert time_range["span_ms"] == 3600000

    @pytest.mark.asyncio
    async def test_cache_result_sample_events(
        self, cache_manager: ResultCacheManager, large_result: dict
    ) -> None:
        """Test event sampling from large result."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=large_result,
        )

        assert len(summary.sample_events) == ResultCacheManager.MAX_SAMPLE_EVENTS
        # Should include first and last events
        assert summary.sample_events[0]["message"] == "Event 0"
        assert summary.sample_events[-1]["message"] == "Event 999"

    @pytest.mark.asyncio
    async def test_cache_result_deduplication(
        self, cache_manager: ResultCacheManager, sample_result: dict
    ) -> None:
        """Test that same query generates same cache_id."""
        params = {"log_group": "/aws/lambda/test", "start_time": "1h"}

        summary1 = await cache_manager.cache_result(
            tool_name="fetch_logs", query_params=params, result=sample_result
        )

        summary2 = await cache_manager.cache_result(
            tool_name="fetch_logs", query_params=params, result=sample_result
        )

        assert summary1.cache_id == summary2.cache_id

    @pytest.mark.asyncio
    async def test_cache_result_different_params_different_id(
        self, cache_manager: ResultCacheManager, sample_result: dict
    ) -> None:
        """Test that different params generate different cache_ids."""
        summary1 = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test1"},
            result=sample_result,
        )

        summary2 = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test2"},
            result=sample_result,
        )

        assert summary1.cache_id != summary2.cache_id

    @pytest.mark.asyncio
    async def test_cache_result_empty_events(self, cache_manager: ResultCacheManager) -> None:
        """Test caching result with no events."""
        result = {"events": []}

        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=result,
        )

        assert summary.total_events == 0
        assert len(summary.sample_events) == 0
        assert summary.time_range == {"start": None, "end": None}

    @pytest.mark.asyncio
    async def test_cache_result_logs_key(self, cache_manager: ResultCacheManager) -> None:
        """Test caching result with 'logs' key instead of 'events'."""
        result = {
            "logs": [
                {"timestamp": 1707750000000, "message": "Test log"},
            ]
        }

        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=result,
        )

        assert summary.total_events == 1

    @pytest.mark.asyncio
    async def test_fetch_chunk_basic(
        self, cache_manager: ResultCacheManager, large_result: dict
    ) -> None:
        """Test fetching a basic chunk."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=large_result,
        )

        chunk = await cache_manager.fetch_chunk(cache_id=summary.cache_id, offset=0, limit=10)

        assert chunk["success"] is True
        assert len(chunk["events"]) == 10
        assert chunk["offset"] == 0
        assert chunk["limit"] == 10
        assert chunk["total_cached"] == 1000
        assert chunk["has_more"] is True

    @pytest.mark.asyncio
    async def test_fetch_chunk_pagination(
        self, cache_manager: ResultCacheManager, large_result: dict
    ) -> None:
        """Test pagination through chunks."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=large_result,
        )

        # Fetch second page
        chunk = await cache_manager.fetch_chunk(cache_id=summary.cache_id, offset=100, limit=100)

        assert chunk["success"] is True
        assert len(chunk["events"]) == 100
        assert chunk["events"][0]["message"] == "Event 100"
        assert chunk["has_more"] is True

    @pytest.mark.asyncio
    async def test_fetch_chunk_last_page(
        self, cache_manager: ResultCacheManager, large_result: dict
    ) -> None:
        """Test fetching last page."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=large_result,
        )

        # Fetch last page
        chunk = await cache_manager.fetch_chunk(cache_id=summary.cache_id, offset=990, limit=20)

        assert chunk["success"] is True
        assert len(chunk["events"]) == 10  # Only 10 events left
        assert chunk["has_more"] is False

    @pytest.mark.asyncio
    async def test_fetch_chunk_limit_enforcement(
        self, cache_manager: ResultCacheManager, large_result: dict
    ) -> None:
        """Test that limit is enforced to max 200."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=large_result,
        )

        chunk = await cache_manager.fetch_chunk(
            cache_id=summary.cache_id,
            offset=0,
            limit=500,  # Request 500
        )

        assert chunk["success"] is True
        assert len(chunk["events"]) == 200  # Should be capped at 200

    @pytest.mark.asyncio
    async def test_fetch_chunk_filter_pattern(
        self, cache_manager: ResultCacheManager, sample_result: dict
    ) -> None:
        """Test filtering by text pattern."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=sample_result,
        )

        chunk = await cache_manager.fetch_chunk(
            cache_id=summary.cache_id, offset=0, limit=100, filter_pattern="ERROR"
        )

        assert chunk["success"] is True
        assert len(chunk["events"]) == 2  # Two ERROR messages
        assert chunk["total_filtered"] == 2
        assert all("ERROR" in e["message"] for e in chunk["events"])

    @pytest.mark.asyncio
    async def test_fetch_chunk_filter_time_range(
        self, cache_manager: ResultCacheManager, sample_result: dict
    ) -> None:
        """Test filtering by time range."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=sample_result,
        )

        # Filter to middle two events
        chunk = await cache_manager.fetch_chunk(
            cache_id=summary.cache_id,
            offset=0,
            limit=100,
            time_start=1707751800000,
            time_end=1707752700000,
        )

        assert chunk["success"] is True
        assert len(chunk["events"]) == 2
        assert chunk["total_filtered"] == 2

    @pytest.mark.asyncio
    async def test_fetch_chunk_not_found(self, cache_manager: ResultCacheManager) -> None:
        """Test fetching non-existent cache entry."""
        chunk = await cache_manager.fetch_chunk(cache_id="result_nonexistent")

        assert chunk["success"] is False
        assert "not found" in chunk["error"]
        assert "hint" in chunk

    @pytest.mark.asyncio
    async def test_fetch_chunk_expired(self, tmp_path: Path, sample_result: dict) -> None:
        """Test fetching expired cache entry."""
        # Create manager with very short TTL
        manager = ResultCacheManager(cache_dir=tmp_path / "cache", ttl_seconds=1)
        await manager.initialize()

        summary = await manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=sample_result,
        )

        # Wait for expiration (need to wait at least 2 seconds for integer epoch timestamps)
        await asyncio.sleep(2.0)

        chunk = await manager.fetch_chunk(cache_id=summary.cache_id)

        assert chunk["success"] is False
        assert "expired" in chunk["error"]
        assert "hint" in chunk

    @pytest.mark.asyncio
    async def test_fetch_chunk_updates_access_stats(
        self, cache_manager: ResultCacheManager, sample_result: dict
    ) -> None:
        """Test that fetch_chunk updates access statistics."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=sample_result,
        )

        # Fetch multiple times
        await cache_manager.fetch_chunk(cache_id=summary.cache_id)
        await cache_manager.fetch_chunk(cache_id=summary.cache_id)

        # Check statistics
        stats = await cache_manager.get_statistics()
        assert stats["total_accesses"] == 2

    @pytest.mark.asyncio
    async def test_delete_expired(self, tmp_path: Path, sample_result: dict) -> None:
        """Test deleting expired entries."""
        manager = ResultCacheManager(cache_dir=tmp_path / "cache", ttl_seconds=1)
        await manager.initialize()

        # Cache multiple results
        await manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test1"},
            result=sample_result,
        )
        await manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test2"},
            result=sample_result,
        )

        # Wait for expiration (need to wait at least 2 seconds for integer epoch timestamps)
        await asyncio.sleep(2.0)

        # Delete expired
        deleted = await manager.delete_expired()

        assert deleted == 2

        # Verify they're gone
        stats = await manager.get_statistics()
        assert stats["entry_count"] == 0

    @pytest.mark.asyncio
    async def test_size_limit_enforcement(self, tmp_path: Path, large_result: dict) -> None:
        """Test cache size limit enforcement."""
        # Create manager with tiny size limit (1MB)
        manager = ResultCacheManager(cache_dir=tmp_path / "cache", max_size_mb=1)
        await manager.initialize()

        # Cache results until we exceed the limit
        for i in range(20):
            await manager.cache_result(
                tool_name="fetch_logs",
                query_params={"log_group": f"/aws/lambda/test{i}"},
                result=large_result,
            )

        # Check that size is under limit
        stats = await manager.get_statistics()
        assert stats["total_size_mb"] <= 1.0

    @pytest.mark.asyncio
    async def test_get_statistics(
        self, cache_manager: ResultCacheManager, sample_result: dict, large_result: dict
    ) -> None:
        """Test get_statistics method."""
        # Cache some results
        await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test1"},
            result=sample_result,
        )
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test2"},
            result=large_result,
        )

        # Fetch once
        await cache_manager.fetch_chunk(cache_id=summary.cache_id)

        stats = await cache_manager.get_statistics()

        assert stats["entry_count"] == 2
        assert stats["total_events"] == 1004  # 4 + 1000
        assert stats["total_size_bytes"] > 0
        assert stats["total_size_mb"] > 0
        assert stats["total_accesses"] == 1
        assert stats["max_size_mb"] == 10
        assert stats["ttl_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_performance_cache_storage(
        self, cache_manager: ResultCacheManager, large_result: dict
    ) -> None:
        """Test that cache storage meets performance target (<50ms)."""
        start = time.time()

        await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=large_result,
        )

        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < 50, f"Cache storage took {elapsed_ms:.2f}ms (target: <50ms)"

    @pytest.mark.asyncio
    async def test_performance_chunk_retrieval(
        self, cache_manager: ResultCacheManager, large_result: dict
    ) -> None:
        """Test that chunk retrieval meets performance target (<100ms)."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=large_result,
        )

        start = time.time()

        await cache_manager.fetch_chunk(cache_id=summary.cache_id, offset=0, limit=100)

        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < 100, f"Chunk retrieval took {elapsed_ms:.2f}ms (target: <100ms)"


@pytest.mark.asyncio
async def test_corrupted_cache_data_auto_cleanup(cache_manager: ResultCacheManager) -> None:
    """Test that corrupted JSON in cache is detected and cleaned up."""
    # Manually insert corrupted JSON into database
    import aiosqlite

    cache_id = "corrupted_test"
    async with aiosqlite.connect(str(cache_manager.db_path)) as db:
        await db.execute(
            """INSERT INTO cached_results
            (cache_id, tool_name, query_params, result_data, event_count, data_size_bytes,
             created_at, expires_at, last_accessed, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cache_id,
                "query_cloudwatch",
                "{}",
                "{invalid json this is corrupted}",  # Corrupted JSON
                100,
                1000,
                int(time.time()),
                int(time.time()) + 3600,
                int(time.time()),
                0,
            ),
        )
        await db.commit()

    # Try to fetch - should return error and auto-delete
    result = await cache_manager.fetch_chunk(cache_id)

    assert result["success"] is False
    assert "corrupted" in result["error"].lower()
    assert "hint" in result
    assert "action_required" in result

    # Verify the corrupted entry was deleted
    async with aiosqlite.connect(str(cache_manager.db_path)) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM cached_results WHERE cache_id = ?", (cache_id,)
        ) as cursor:
            row = await cursor.fetchone()
            count = row[0] if row else 0

    assert count == 0, "Corrupted entry should be deleted"


@pytest.mark.asyncio
async def test_validate_and_clean_cache(cache_manager: ResultCacheManager) -> None:
    """Test validation method finds and cleans corrupted entries."""
    import aiosqlite

    # Insert one good entry and one corrupted entry
    async with aiosqlite.connect(str(cache_manager.db_path)) as db:
        # Good entry
        await db.execute(
            """INSERT INTO cached_results
            (cache_id, tool_name, query_params, result_data, event_count, data_size_bytes,
             created_at, expires_at, last_accessed, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "good_cache",
                "query_cloudwatch",
                "{}",
                '{"events": [], "count": 0}',  # Valid JSON
                0,
                100,
                int(time.time()),
                int(time.time()) + 3600,
                int(time.time()),
                0,
            ),
        )

        # Corrupted entry
        await db.execute(
            """INSERT INTO cached_results
            (cache_id, tool_name, query_params, result_data, event_count, data_size_bytes,
             created_at, expires_at, last_accessed, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "bad_cache",
                "query_cloudwatch",
                "{}",
                "{this is not valid json}",  # Corrupted
                100,
                1000,
                int(time.time()),
                int(time.time()) + 3600,
                int(time.time()),
                0,
            ),
        )
        await db.commit()

    # Run validation
    result = await cache_manager.validate_and_clean_cache()

    assert result["total_entries"] == 2
    assert result["corrupted_count"] == 1
    assert "bad_cache" in result["corrupted_ids"]
    assert result["corruption_rate"] == 0.5

    # Verify only good entry remains
    async with aiosqlite.connect(str(cache_manager.db_path)) as db:
        async with db.execute("SELECT cache_id FROM cached_results") as cursor:
            remaining = [row[0] async for row in cursor]

    assert remaining == ["good_cache"]


@pytest.mark.asyncio
async def test_cache_result_validation_prevents_bad_data(cache_manager: ResultCacheManager) -> None:
    """Test that trying to cache invalid data raises an error."""

    # Create an object that can't be serialized to JSON
    class UnserializableObject:
        pass

    bad_result = {
        "events": [],
        "count": 1,
        "bad_object": UnserializableObject(),  # Can't serialize this
    }

    with pytest.raises(ValueError, match="Cannot cache result"):
        await cache_manager.cache_result(
            tool_name="query_cloudwatch",
            query_params={},
            result=bad_result,
        )
