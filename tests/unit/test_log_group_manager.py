"""Unit tests for LogGroupManager."""

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from logai.core.log_group_manager import (
    LogGroupInfo,
    LogGroupManager,
    LogGroupManagerResult,
    LogGroupManagerState,
)


@pytest.fixture
def mock_datasource():
    """Create a mock CloudWatch datasource."""
    datasource = MagicMock()
    datasource.client = MagicMock()
    return datasource


@pytest.fixture
def sample_log_groups() -> list[dict[str, Any]]:
    """Sample log group data."""
    return [
        {
            "name": "/aws/lambda/function-1",
            "created": 1234567890000,
            "stored_bytes": 1024000,
            "retention_days": 7,
        },
        {
            "name": "/aws/lambda/function-2",
            "created": 1234567891000,
            "stored_bytes": 2048000,
            "retention_days": 14,
        },
        {
            "name": "/ecs/my-service",
            "created": 1234567892000,
            "stored_bytes": 512000,
            "retention_days": None,
        },
    ]


class TestLogGroupInfo:
    """Tests for LogGroupInfo data class."""

    def test_from_dict(self):
        """Test creating LogGroupInfo from dict."""
        data = {
            "name": "/aws/lambda/test",
            "created": 1234567890000,
            "stored_bytes": 1024,
            "retention_days": 7,
        }

        info = LogGroupInfo.from_dict(data)

        assert info.name == "/aws/lambda/test"
        assert info.created == 1234567890000
        assert info.stored_bytes == 1024
        assert info.retention_days == 7

    def test_from_dict_missing_optional_fields(self):
        """Test creating LogGroupInfo with missing optional fields."""
        data = {"name": "/aws/lambda/test"}

        info = LogGroupInfo.from_dict(data)

        assert info.name == "/aws/lambda/test"
        assert info.created is None
        assert info.stored_bytes == 0
        assert info.retention_days is None


class TestLogGroupManagerState:
    """Tests for LogGroupManagerState enum."""

    def test_states_exist(self):
        """Test all expected states exist."""
        assert LogGroupManagerState.UNINITIALIZED
        assert LogGroupManagerState.LOADING
        assert LogGroupManagerState.READY
        assert LogGroupManagerState.ERROR


class TestLogGroupManager:
    """Tests for LogGroupManager class."""

    def test_init(self, mock_datasource):
        """Test manager initialization."""
        manager = LogGroupManager(mock_datasource)

        assert manager.datasource == mock_datasource
        assert manager.state == LogGroupManagerState.UNINITIALIZED
        assert manager.count == 0
        assert manager.last_refresh is None
        assert not manager.is_ready

    @pytest.mark.asyncio
    async def test_load_all_success(self, mock_datasource, sample_log_groups):
        """Test successful loading of log groups."""
        # Mock paginator
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "logGroups": [
                    {
                        "logGroupName": lg["name"],
                        "creationTime": lg["created"],
                        "storedBytes": lg["stored_bytes"],
                        "retentionInDays": lg.get("retention_days"),
                    }
                    for lg in sample_log_groups
                ]
            }
        ]

        mock_datasource.client.get_paginator.return_value = mock_paginator

        manager = LogGroupManager(mock_datasource)

        # Track progress callback invocations
        progress_calls = []

        def progress_callback(count: int, message: str):
            progress_calls.append((count, message))

        result = await manager.load_all(progress_callback=progress_callback)

        assert result.success
        assert result.count == 3
        assert len(result.log_groups) == 3
        assert result.error_message is None
        assert result.duration_ms >= 0  # Duration can be 0 for fast tests

        assert manager.state == LogGroupManagerState.READY
        assert manager.count == 3
        assert manager.is_ready
        assert manager.last_refresh is not None

        # Check progress callbacks were called
        assert len(progress_calls) >= 2  # At least start and complete
        assert progress_calls[0] == (0, "Starting log group discovery...")
        assert progress_calls[-1] == (3, "Log group discovery complete")

    @pytest.mark.asyncio
    async def test_load_all_pagination(self, mock_datasource):
        """Test loading with pagination (multiple pages)."""
        # Mock multiple pages
        page1_groups = [
            {
                "logGroupName": f"/aws/lambda/func-{i}",
                "creationTime": 1234567890000 + i,
                "storedBytes": 1024 * i,
            }
            for i in range(50)
        ]

        page2_groups = [
            {
                "logGroupName": f"/aws/lambda/func-{i}",
                "creationTime": 1234567890000 + i,
                "storedBytes": 1024 * i,
            }
            for i in range(50, 75)
        ]

        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"logGroups": page1_groups},
            {"logGroups": page2_groups},
        ]

        mock_datasource.client.get_paginator.return_value = mock_paginator

        manager = LogGroupManager(mock_datasource)
        result = await manager.load_all()

        assert result.success
        assert result.count == 75
        assert manager.count == 75

    @pytest.mark.asyncio
    async def test_load_all_error(self, mock_datasource):
        """Test load_all with error."""
        # Mock paginator to raise exception
        mock_datasource.client.get_paginator.side_effect = Exception("AWS connection error")

        manager = LogGroupManager(mock_datasource)
        result = await manager.load_all()

        assert not result.success
        assert result.count == 0
        assert result.error_message == "AWS connection error"
        assert manager.state == LogGroupManagerState.ERROR
        assert not manager.is_ready

    @pytest.mark.asyncio
    async def test_refresh(self, mock_datasource, sample_log_groups):
        """Test refresh method (alias for load_all)."""
        # Mock paginator
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "logGroups": [
                    {
                        "logGroupName": lg["name"],
                        "creationTime": lg["created"],
                        "storedBytes": lg["stored_bytes"],
                        "retentionInDays": lg.get("retention_days"),
                    }
                    for lg in sample_log_groups
                ]
            }
        ]

        mock_datasource.client.get_paginator.return_value = mock_paginator

        manager = LogGroupManager(mock_datasource)

        # Initial load
        await manager.load_all()
        first_refresh = manager.last_refresh

        # Wait a moment
        await asyncio.sleep(0.01)

        # Refresh
        result = await manager.refresh()

        assert result.success
        # Type guard: both timestamps should be set after successful load/refresh
        assert first_refresh is not None
        assert manager.last_refresh is not None
        assert manager.last_refresh > first_refresh

    def test_format_for_prompt_empty_uninitialized(self, mock_datasource):
        """Test formatting when uninitialized."""
        manager = LogGroupManager(mock_datasource)
        formatted = manager.format_for_prompt()

        assert "Log groups not yet loaded" in formatted
        assert "list_log_groups" in formatted

    @pytest.mark.asyncio
    async def test_format_for_prompt_empty_error(self, mock_datasource):
        """Test formatting after error."""
        mock_datasource.client.get_paginator.side_effect = Exception("Connection failed")

        manager = LogGroupManager(mock_datasource)
        await manager.load_all()

        formatted = manager.format_for_prompt()

        assert "Failed to load log groups" in formatted
        assert "Connection failed" in formatted

    @pytest.mark.asyncio
    async def test_format_for_prompt_full_list(self, mock_datasource, sample_log_groups):
        """Test formatting with small list (<=500 groups)."""
        # Mock paginator
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "logGroups": [
                    {
                        "logGroupName": lg["name"],
                        "creationTime": lg["created"],
                        "storedBytes": lg["stored_bytes"],
                        "retentionInDays": lg.get("retention_days"),
                    }
                    for lg in sample_log_groups
                ]
            }
        ]

        mock_datasource.client.get_paginator.return_value = mock_paginator

        manager = LogGroupManager(mock_datasource)
        await manager.load_all()

        formatted = manager.format_for_prompt()

        assert "Available Log Groups" in formatted
        assert "Total:** 3 log groups" in formatted
        assert "/aws/lambda/function-1" in formatted
        assert "/aws/lambda/function-2" in formatted
        assert "/ecs/my-service" in formatted
        assert "Usage Instructions" in formatted
        assert "/refresh" in formatted

        # Verify agent instructions are present
        assert "IMPORTANT: When Users Ask to List Log Groups" in formatted
        assert "Acknowledge warmly" in formatted
        assert "Reference the sidebar" in formatted
        assert "Mention /refresh" in formatted
        assert "Offer to help" in formatted
        assert "Example response:" in formatted
        assert "left sidebar" in formatted

    @pytest.mark.asyncio
    async def test_format_for_prompt_summary(self, mock_datasource):
        """Test formatting with large list (>500 groups)."""
        # Create 600 log groups to trigger summary mode
        large_group_list = [
            {
                "logGroupName": f"/aws/lambda/function-{i}",
                "creationTime": 1234567890000 + i,
                "storedBytes": 1024 * i,
            }
            for i in range(600)
        ]

        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"logGroups": large_group_list}]

        mock_datasource.client.get_paginator.return_value = mock_paginator

        manager = LogGroupManager(mock_datasource)
        await manager.load_all()

        formatted = manager.format_for_prompt()

        assert "Available Log Groups" in formatted
        assert "Total:** 600 log groups" in formatted
        assert "Log Group Categories" in formatted
        assert "Sample Log Groups" in formatted
        assert "/aws/lambda/" in formatted
        assert "too large to display" in formatted

        # Verify agent instructions are present
        assert "IMPORTANT: When Users Ask to List Log Groups" in formatted
        assert "Acknowledge warmly" in formatted
        assert "Reference the sidebar" in formatted
        assert "Mention /refresh" in formatted
        assert "Offer to help" in formatted
        assert "Example response:" in formatted
        assert "left sidebar" in formatted

    def test_get_log_group_names(self, mock_datasource):
        """Test getting list of names."""
        manager = LogGroupManager(mock_datasource)
        manager._log_groups = [
            LogGroupInfo(name="/aws/lambda/test1"),
            LogGroupInfo(name="/aws/lambda/test2"),
        ]
        manager._state = LogGroupManagerState.READY

        names = manager.get_log_group_names()

        assert names == ["/aws/lambda/test1", "/aws/lambda/test2"]

    def test_find_matching_groups(self, mock_datasource):
        """Test finding matching groups by pattern."""
        manager = LogGroupManager(mock_datasource)
        manager._log_groups = [
            LogGroupInfo(name="/aws/lambda/payment-service"),
            LogGroupInfo(name="/aws/lambda/auth-service"),
            LogGroupInfo(name="/ecs/payment-api"),
        ]
        manager._state = LogGroupManagerState.READY

        # Test substring match
        matches = manager.find_matching_groups("payment")
        assert len(matches) == 2
        assert matches[0].name == "/aws/lambda/payment-service"
        assert matches[1].name == "/ecs/payment-api"

        # Test case-insensitive
        matches = manager.find_matching_groups("PAYMENT")
        assert len(matches) == 2

        # Test prefix match
        matches = manager.find_matching_groups("/aws/lambda")
        assert len(matches) == 2

        # Test no matches
        matches = manager.find_matching_groups("nonexistent")
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_datasource, sample_log_groups):
        """Test getting statistics."""
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "logGroups": [
                    {
                        "logGroupName": lg["name"],
                        "creationTime": lg["created"],
                        "storedBytes": lg["stored_bytes"],
                        "retentionInDays": lg.get("retention_days"),
                    }
                    for lg in sample_log_groups
                ]
            }
        ]

        mock_datasource.client.get_paginator.return_value = mock_paginator

        manager = LogGroupManager(mock_datasource)
        await manager.load_all()

        stats = manager.get_stats()

        assert stats["count"] == 3
        assert stats["state"] == "ready"
        assert stats["last_refresh"] is not None
        assert stats["total_bytes"] == 1024000 + 2048000 + 512000
        assert "/aws/lambda/" in stats["categories"]
        assert "/ecs/" in stats["categories"]

    def test_get_stats_empty(self, mock_datasource):
        """Test getting stats when empty."""
        manager = LogGroupManager(mock_datasource)

        stats = manager.get_stats()

        assert stats["count"] == 0
        assert stats["state"] == "uninitialized"
        assert stats["last_refresh"] is None
        assert stats["total_bytes"] == 0
        assert stats["categories"] == {}

    def test_categorize_log_groups(self, mock_datasource):
        """Test categorization logic."""
        manager = LogGroupManager(mock_datasource)
        manager._log_groups = [
            LogGroupInfo(name="/aws/lambda/func1"),
            LogGroupInfo(name="/aws/lambda/func2"),
            LogGroupInfo(name="/aws/lambda/func3"),
            LogGroupInfo(name="/ecs/service1"),
            LogGroupInfo(name="/ecs/service2"),
            LogGroupInfo(name="/aws/rds/instance1"),
            LogGroupInfo(name="/custom/app/service"),
        ]
        manager._state = LogGroupManagerState.READY

        categories = manager._categorize_log_groups()

        assert categories["/aws/lambda/"] == 3
        assert categories["/ecs/"] == 2
        assert categories["/aws/rds/"] == 1
        assert categories["/custom/app/"] == 1

    def test_get_representative_sample_small_list(self, mock_datasource):
        """Test sampling when list is already small."""
        manager = LogGroupManager(mock_datasource)
        manager._log_groups = [LogGroupInfo(name=f"/aws/lambda/func-{i}") for i in range(50)]
        manager._state = LogGroupManagerState.READY

        sample = manager._get_representative_sample()

        # Should return all groups when under threshold
        assert len(sample) == 50
        # Should be sorted
        assert sample[0].name < sample[-1].name

    def test_get_representative_sample_large_list(self, mock_datasource):
        """Test sampling when list is large."""
        manager = LogGroupManager(mock_datasource)

        # Create diverse log groups
        log_groups = []
        for i in range(200):
            log_groups.append(LogGroupInfo(name=f"/aws/lambda/func-{i}"))
        for i in range(150):
            log_groups.append(LogGroupInfo(name=f"/ecs/service-{i}"))
        for i in range(50):
            log_groups.append(LogGroupInfo(name=f"/aws/rds/db-{i}"))

        manager._log_groups = log_groups
        manager._state = LogGroupManagerState.READY

        sample = manager._get_representative_sample()

        # Should return approximately SUMMARY_SAMPLE_SIZE (within a few due to rounding)
        assert len(sample) <= manager.SUMMARY_SAMPLE_SIZE
        assert len(sample) >= manager.SUMMARY_SAMPLE_SIZE - 5  # Allow for rounding
        # Should be sorted
        assert sample[0].name < sample[-1].name
        # Should have diversity (multiple prefixes represented)
        prefixes = set()
        for group in sample:
            if group.name.startswith("/aws/lambda/"):
                prefixes.add("/aws/lambda/")
            elif group.name.startswith("/ecs/"):
                prefixes.add("/ecs/")
            elif group.name.startswith("/aws/rds/"):
                prefixes.add("/aws/rds/")
        assert len(prefixes) >= 2  # At least 2 different categories

    def test_log_groups_property_returns_copy(self, mock_datasource):
        """Test that log_groups property returns a copy."""
        manager = LogGroupManager(mock_datasource)
        manager._log_groups = [LogGroupInfo(name="/aws/lambda/test")]
        manager._state = LogGroupManagerState.READY

        groups1 = manager.log_groups
        groups2 = manager.log_groups

        # Should be different objects
        assert groups1 is not groups2
        # But same content
        assert groups1[0].name == groups2[0].name
