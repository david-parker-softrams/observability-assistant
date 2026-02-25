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
        """Test conversion to context dictionary with new 5-key structure (Phase 1)."""
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

        # Verify new 5-key structure
        assert context_dict["result_type"] == "cached_preview"
        assert context_dict["full_dataset"]["cache_id"] == "result_abc123"
        assert context_dict["full_dataset"]["total_events"] == 100
        assert context_dict["full_dataset"]["time_range"]["start"] == 1707750000000
        assert context_dict["full_dataset"]["statistics"] == {"ERROR": 10, "INFO": 90}
        assert context_dict["preview_events"] == [
            {"timestamp": 1707750000000, "message": "Test event"}
        ]
        assert context_dict["fetch_more"]["tool"] == "fetch_cached_result_chunk"
        assert "result_abc123" in context_dict["fetch_more"]["example"]
        assert context_dict["fetch_more"]["total_chunks"] == 1  # 100 events / 100 per chunk = 1
        assert "expires_in_seconds" in context_dict

    def test_to_context_dict_expires_in_seconds(self) -> None:
        """Test expires_in_seconds calculation with new structure."""
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
        expires_in = context_dict["expires_in_seconds"]

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


# ---------------------------------------------------------------------------
# Tests for Bug Fixes: MCP Insights result handling & ISO string timestamps
# (Branch: fix/mcp-insights-result-handling)
# ---------------------------------------------------------------------------

# ── Shared fixtures for the new test groups ─────────────────────────────────

MCP_INSIGHTS_RECORDS = [
    {
        "@timestamp": "2026-02-25T13:00:00Z",
        "@message": "INFO hello",
        "@logStream": "stream1",
    },
    {
        "@timestamp": "2026-02-25T13:01:00Z",
        "@message": "ERROR boom",
        "@logStream": "stream2",
    },
    {
        "@timestamp": "2026-02-25T13:02:00Z",
        "@message": "WARN watch out",
        "@logStream": "stream1",
    },
]


# ── Group 1: MCP Insights `results` extraction in cache_result() ─────────────


class TestCacheResultMcpInsightsFormat:
    """Tests for the MCP Insights 'results' key normalisation path in cache_result()."""

    @pytest.mark.asyncio
    async def test_cache_result_mcp_insights_format(
        self, cache_manager: ResultCacheManager
    ) -> None:
        """
        Given a result dict with a 'results' key containing CloudWatch Insights records,
        the summary should reflect the actual number of records and expose normalised
        field names ('timestamp', 'message') rather than the raw '@'-prefixed originals.
        """
        result = {"results": list(MCP_INSIGHTS_RECORDS)}

        summary = await cache_manager.cache_result(
            tool_name="query_cloudwatch_insights",
            query_params={"log_group": "/aws/lambda/test"},
            result=result,
        )

        # Event count must equal the number of records — not 0
        assert summary.total_events == len(MCP_INSIGHTS_RECORDS)

        # At least one sample event must be present
        assert len(summary.sample_events) > 0

        # All sample events must use the normalised 'message' key (no '@message')
        for event in summary.sample_events:
            assert "message" in event, f"'message' key missing from sample event: {event}"
            assert "@message" not in event, f"'@message' key should have been stripped: {event}"

        # All sample events must use the normalised 'timestamp' key (no '@timestamp')
        for event in summary.sample_events:
            assert "timestamp" in event, f"'timestamp' key missing from sample event: {event}"
            assert "@timestamp" not in event, f"'@timestamp' key should have been stripped: {event}"

    @pytest.mark.asyncio
    async def test_cache_result_mcp_insights_normalization(
        self, cache_manager: ResultCacheManager
    ) -> None:
        """
        ALL '@'-prefixed fields must have the '@' stripped; non-'@' fields must
        pass through the normalisation step completely unchanged.
        """
        # Include a field that has NO '@' prefix to verify pass-through
        records = [
            {
                "@timestamp": "2026-02-25T13:00:00Z",
                "@message": "INFO test",
                "@logStream": "stream-x",
                "plain_field": "should-survive",
            }
        ]
        result = {"results": records}

        summary = await cache_manager.cache_result(
            tool_name="query_cloudwatch_insights",
            query_params={"log_group": "/aws/lambda/test"},
            result=result,
        )

        assert len(summary.sample_events) == 1
        event = summary.sample_events[0]

        # '@'-prefixed fields → stripped
        assert "timestamp" in event
        assert "message" in event
        assert "logStream" in event

        # Original '@'-prefixed keys must be gone
        assert "@timestamp" not in event
        assert "@message" not in event
        assert "@logStream" not in event

        # Non-'@' field must be present unchanged
        assert event.get("plain_field") == "should-survive"

    @pytest.mark.asyncio
    async def test_cache_result_mcp_insights_event_count(
        self, cache_manager: ResultCacheManager
    ) -> None:
        """
        The event_count stored in the DB (reflected in total_events) must equal
        the number of records supplied in the 'results' list.
        """
        import aiosqlite

        records = [
            {"@timestamp": f"2026-02-25T13:0{i}:00Z", "@message": f"msg {i}"} for i in range(7)
        ]
        result = {"results": records}

        summary = await cache_manager.cache_result(
            tool_name="query_cloudwatch_insights",
            query_params={"log_group": "/aws/lambda/test", "run": "count-check"},
            result=result,
        )

        # Verify the in-memory summary
        assert summary.total_events == 7

        # Also verify what was persisted to the database
        async with aiosqlite.connect(str(cache_manager.db_path)) as db:
            async with db.execute(
                "SELECT event_count FROM cached_results WHERE cache_id = ?",
                (summary.cache_id,),
            ) as cursor:
                row = await cursor.fetchone()

        assert row is not None, "Cache entry must exist in DB"
        assert row[0] == 7, f"DB event_count should be 7, got {row[0]}"

    @pytest.mark.asyncio
    async def test_cache_result_events_key_takes_precedence(
        self, cache_manager: ResultCacheManager
    ) -> None:
        """
        When both 'events' and 'results' keys exist, the 'events' key must win
        (pre-existing behaviour must be preserved).
        """
        native_events = [
            {"timestamp": 1740488400000, "message": "native event A"},
            {"timestamp": 1740488401000, "message": "native event B"},
        ]
        mcp_records = [
            {"@timestamp": "2026-02-25T13:00:00Z", "@message": "mcp record A"},
            {"@timestamp": "2026-02-25T13:01:00Z", "@message": "mcp record B"},
            {"@timestamp": "2026-02-25T13:02:00Z", "@message": "mcp record C"},
        ]
        result = {"events": native_events, "results": mcp_records}

        summary = await cache_manager.cache_result(
            tool_name="query_cloudwatch_insights",
            query_params={"log_group": "/aws/lambda/test"},
            result=result,
        )

        # 'events' has 2 items, 'results' has 3 — the 'events' key must win
        assert summary.total_events == len(native_events)

        # Sample events should reflect the native (non-'@'-prefixed) data
        for event in summary.sample_events:
            assert "timestamp" in event
            assert "message" in event
            assert "@timestamp" not in event

    @pytest.mark.asyncio
    async def test_cache_result_empty_results_key(self, cache_manager: ResultCacheManager) -> None:
        """
        An empty 'results' list must not crash and must yield total_events == 0.
        """
        result = {"results": []}

        summary = await cache_manager.cache_result(
            tool_name="query_cloudwatch_insights",
            query_params={"log_group": "/aws/lambda/test"},
            result=result,
        )

        assert summary.total_events == 0
        assert summary.sample_events == []
        assert summary.time_range == {"start": None, "end": None}

    @pytest.mark.asyncio
    async def test_cache_result_native_events_format_unchanged(
        self, cache_manager: ResultCacheManager
    ) -> None:
        """
        Regression: plain {"events": [...]} format must continue to work exactly as
        before — the MCP fallback path must not interfere.
        """
        native_result = {
            "events": [
                {"timestamp": 1707750000000, "message": "ERROR: something bad"},
                {"timestamp": 1707751800000, "message": "WARN: heads up"},
                {"timestamp": 1707753600000, "message": "INFO: all good"},
            ]
        }

        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=native_result,
        )

        assert summary.total_events == 3
        assert len(summary.sample_events) == 3

        # All sample events must carry plain (non-'@') keys
        for event in summary.sample_events:
            assert "timestamp" in event
            assert "message" in event

        # Time range must be resolved from integer timestamps
        assert summary.time_range["start"] == 1707750000000
        assert summary.time_range["end"] == 1707753600000
        assert summary.time_range["span_ms"] == 3600000


# ── Group 2: _extract_time_range() with string timestamps ────────────────────


class TestExtractTimeRangeStringTimestamps:
    """Tests for the ISO 8601 string-timestamp handling in _extract_time_range()."""

    def test_extract_time_range_iso_string_timestamps(
        self, cache_manager: ResultCacheManager
    ) -> None:
        """
        Events whose 'timestamp' value is an ISO 8601 string must not crash.
        The method should return start/end as the lexicographically first/last strings.
        """
        events = [
            {"timestamp": "2026-02-25T13:02:00Z", "message": "third"},
            {"timestamp": "2026-02-25T13:00:00Z", "message": "first"},
            {"timestamp": "2026-02-25T13:01:00Z", "message": "second"},
        ]

        time_range = cache_manager._extract_time_range(events)

        assert "start" in time_range
        assert "end" in time_range
        # ISO 8601 timestamps sort lexicographically
        assert time_range["start"] == "2026-02-25T13:00:00Z"
        assert time_range["end"] == "2026-02-25T13:02:00Z"
        # span_ms is NOT expected when timestamps are strings
        assert "span_ms" not in time_range

    def test_extract_time_range_integer_timestamps_unchanged(
        self, cache_manager: ResultCacheManager
    ) -> None:
        """
        Regression: integer epoch-millisecond timestamps must still produce
        start, end, and span_ms exactly as before.
        """
        events = [
            {"timestamp": 1707750000000, "message": "first"},
            {"timestamp": 1707751800000, "message": "middle"},
            {"timestamp": 1707753600000, "message": "last"},
        ]

        time_range = cache_manager._extract_time_range(events)

        assert time_range["start"] == 1707750000000
        assert time_range["end"] == 1707753600000
        assert time_range["span_ms"] == 3600000

    def test_extract_time_range_mixed_timestamps(self, cache_manager: ResultCacheManager) -> None:
        """
        A mix of integer and string timestamps must not crash.
        Integers are preferred; the result must contain start, end, and span_ms.
        """
        events = [
            {"timestamp": 1707750000000, "message": "int event"},
            {"timestamp": "2026-02-25T13:00:00Z", "message": "string event"},
            {"timestamp": 1707753600000, "message": "int event 2"},
        ]

        # Must not raise — that is the primary assertion
        time_range = cache_manager._extract_time_range(events)

        assert "start" in time_range
        assert "end" in time_range
        # Integers take priority, so span_ms must be present
        assert "span_ms" in time_range
        assert time_range["start"] == 1707750000000
        assert time_range["end"] == 1707753600000

    def test_extract_time_range_empty(self, cache_manager: ResultCacheManager) -> None:
        """
        An empty events list must return {"start": None, "end": None} —
        existing behaviour must be preserved.
        """
        time_range = cache_manager._extract_time_range([])

        assert time_range == {"start": None, "end": None}


class TestFetchChunkMcpInsightsRoundTrip:
    """End-to-end round-trip tests: store MCP Insights result → fetch_chunk() returns normalised events."""

    @pytest.mark.asyncio
    async def test_fetch_chunk_returns_normalized_events_for_mcp_insights_format(
        self, cache_manager: ResultCacheManager
    ) -> None:
        """
        End-to-end round-trip through SQLite: cache an MCP Insights result (using the
        'results' key with '@'-prefixed fields) then call fetch_chunk() and verify that
        the returned events carry normalised 'message'/'timestamp' keys — never the raw
        '@message'/'@timestamp' originals.
        """
        result = {
            "results": [
                {
                    "@timestamp": "2026-02-25T13:00:01Z",
                    "@message": "ERROR Boom",
                    "@logStream": "stream1",
                },
                {
                    "@timestamp": "2026-02-25T13:00:02Z",
                    "@message": "INFO OK",
                    "@logStream": "stream1",
                },
            ],
            "status": "Complete",
        }

        # Step 1 – cache the MCP Insights result
        summary = await cache_manager.cache_result(
            tool_name="query_cloudwatch_insights",
            query_params={"log_group": "/aws/lambda/test", "query": "fields @message"},
            result=result,
        )

        # Step 2 – retrieve via fetch_chunk
        chunk = await cache_manager.fetch_chunk(
            cache_id=summary.cache_id,
            offset=0,
            limit=10,
        )

        # Basic success checks
        assert chunk["success"] is True
        assert len(chunk["events"]) == 2

        # Every event must use the normalised 'message' key, never '@message'
        for event in chunk["events"]:
            assert "message" in event, f"'message' key missing from fetched event: {event}"
            assert (
                "@message" not in event
            ), f"'@message' key should have been stripped before storage: {event}"

        # Every event must use the normalised 'timestamp' key, never '@timestamp'
        for event in chunk["events"]:
            assert "timestamp" in event, f"'timestamp' key missing from fetched event: {event}"
            assert (
                "@timestamp" not in event
            ), f"'@timestamp' key should have been stripped before storage: {event}"

        # Spot-check the first event's message value is a plain string
        assert isinstance(chunk["events"][0]["message"], str)
