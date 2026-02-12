"""Integration tests for log group pre-loading feature.

These tests verify the end-to-end functionality of automatic log group
loading at startup and the /refresh command.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, Mock, MagicMock, patch
from datetime import datetime, timezone

from logai.core.log_group_manager import (
    LogGroupManager,
    LogGroupManagerState,
    LogGroupInfo,
    LogGroupManagerResult,
)
from logai.core.orchestrator import LLMOrchestrator
from logai.config.settings import LogAISettings
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.registry import ToolRegistry
from logai.providers.llm.base import LLMResponse


class TestPaginationIntegration:
    """Test pagination handling with AWS CloudWatch API."""

    @pytest.mark.asyncio
    async def test_pagination_150_log_groups_across_3_pages(self):
        """Test fetching 150 log groups across 3 pages (50 each)."""
        # Create mock CloudWatch data source
        mock_datasource = Mock()
        
        # Create 3 pages of log groups (50, 50, 50)
        page1 = {
            "logGroups": [
                {
                    "logGroupName": f"/aws/lambda/function-{i:03d}",
                    "creationTime": 1234567890000 + i,
                    "storedBytes": 1024 * i,
                    "retentionInDays": 7,
                }
                for i in range(1, 51)
            ]
        }
        
        page2 = {
            "logGroups": [
                {
                    "logGroupName": f"/aws/lambda/function-{i:03d}",
                    "creationTime": 1234567890000 + i,
                    "storedBytes": 1024 * i,
                    "retentionInDays": 7,
                }
                for i in range(51, 101)
            ]
        }
        
        page3 = {
            "logGroups": [
                {
                    "logGroupName": f"/aws/lambda/function-{i:03d}",
                    "creationTime": 1234567890000 + i,
                    "storedBytes": 1024 * i,
                    "retentionInDays": 7,
                }
                for i in range(101, 151)
            ]
        }
        
        # Mock paginator
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [page1, page2, page3]
        
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client
        
        # Track progress callbacks
        progress_updates = []
        
        def progress_callback(count, message):
            progress_updates.append({"count": count, "message": message})
        
        # Create manager and load
        manager = LogGroupManager(mock_datasource)
        result = await manager.load_all(progress_callback=progress_callback)
        
        # Verify result
        assert result.success is True
        assert result.count == 150
        assert result.error_message is None
        assert len(result.log_groups) == 150
        
        # Verify all groups loaded
        assert manager.count == 150
        assert manager.state == LogGroupManagerState.READY
        assert manager.is_ready is True
        
        # Verify group names are correct
        names = manager.get_log_group_names()
        assert "/aws/lambda/function-001" in names
        assert "/aws/lambda/function-050" in names
        assert "/aws/lambda/function-100" in names
        assert "/aws/lambda/function-150" in names
        
        # Verify progress callbacks were made
        assert len(progress_updates) > 0
        assert progress_updates[0]["message"] == "Starting log group discovery..."
        assert progress_updates[-1]["message"] == "Log group discovery complete"
        assert progress_updates[-1]["count"] == 150
        
    @pytest.mark.asyncio
    async def test_pagination_with_nexttoken_mechanism(self):
        """Verify nextToken is used correctly for pagination."""
        mock_datasource = Mock()
        
        # Create 2 pages to simulate pagination
        page1 = {
            "logGroups": [
                {"logGroupName": f"/aws/ecs/service-{i}", "creationTime": 1234567890000}
                for i in range(50)
            ],
        }
        
        page2 = {
            "logGroups": [
                {"logGroupName": f"/aws/ecs/service-{i}", "creationTime": 1234567890000}
                for i in range(50, 80)
            ],
        }
        
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [page1, page2]
        
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client
        
        manager = LogGroupManager(mock_datasource)
        result = await manager.load_all()
        
        # Verify paginator was called
        mock_client.get_paginator.assert_called_once_with("describe_log_groups")
        mock_paginator.paginate.assert_called_once()
        
        # Verify all pages were processed
        assert result.count == 80
        assert manager.count == 80


class TestTieredFormatting:
    """Test tiered formatting strategy for system prompts."""

    @pytest.mark.asyncio
    async def test_format_full_list_for_50_groups(self):
        """Test full list formatting for 50 log groups."""
        mock_datasource = Mock()
        
        # Create 50 log groups
        page = {
            "logGroups": [
                {
                    "logGroupName": f"/aws/lambda/function-{i:02d}",
                    "creationTime": 1234567890000,
                    "storedBytes": 1024,
                }
                for i in range(50)
            ]
        }
        
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [page]
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client
        
        manager = LogGroupManager(mock_datasource)
        await manager.load_all()
        
        formatted = manager.format_for_prompt()
        
        # Should use full list format
        assert "## Available Log Groups" in formatted
        assert "**Total:** 50 log groups" in formatted
        assert "**Last Updated:**" in formatted
        
        # Should list all groups
        for i in range(50):
            assert f"/aws/lambda/function-{i:02d}" in formatted
        
        # Should have usage instructions
        assert "Usage Instructions" in formatted
        assert "no need to call `list_log_groups`" in formatted
        assert "`/refresh` command" in formatted
        
    @pytest.mark.asyncio
    async def test_format_summary_for_600_groups(self):
        """Test summary formatting for 600 log groups."""
        mock_datasource = Mock()
        
        # Create 600 diverse log groups
        log_groups = []
        for i in range(200):
            log_groups.append({
                "logGroupName": f"/aws/lambda/function-{i:03d}",
                "creationTime": 1234567890000,
            })
        for i in range(200):
            log_groups.append({
                "logGroupName": f"/aws/apigateway/api-{i:03d}",
                "creationTime": 1234567890000,
            })
        for i in range(200):
            log_groups.append({
                "logGroupName": f"/ecs/service-{i:03d}",
                "creationTime": 1234567890000,
            })
        
        # Split into pages
        pages = []
        for i in range(0, 600, 50):
            pages.append({"logGroups": log_groups[i:i+50]})
        
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = pages
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client
        
        manager = LogGroupManager(mock_datasource)
        await manager.load_all()
        
        formatted = manager.format_for_prompt()
        
        # Should use summary format
        assert "## Available Log Groups" in formatted
        assert "**Total:** 600 log groups" in formatted
        
        # Should have categories
        assert "Log Group Categories" in formatted
        assert "/aws/lambda/" in formatted
        assert "/aws/apigateway/" in formatted
        assert "/ecs/" in formatted
        
        # Should have sample (not all groups)
        assert "Sample Log Groups" in formatted
        assert "showing" in formatted and "of 600" in formatted
        
        # Should NOT list all 600 groups
        lines_with_groups = [line for line in formatted.split("\n") if line.strip().startswith("- /")]
        assert len(lines_with_groups) < 600
        assert len(lines_with_groups) <= manager.SUMMARY_SAMPLE_SIZE + 20  # Categories + sample


class TestErrorHandling:
    """Test error handling and graceful degradation."""

    @pytest.mark.asyncio
    async def test_aws_connection_error_graceful_degradation(self):
        """Test graceful degradation when AWS connection fails."""
        mock_datasource = Mock()
        
        # Mock paginator to raise connection error
        mock_client = MagicMock()
        mock_client.get_paginator.side_effect = Exception("Unable to connect to AWS CloudWatch")
        mock_datasource.client = mock_client
        
        manager = LogGroupManager(mock_datasource)
        result = await manager.load_all()
        
        # Should fail gracefully
        assert result.success is False
        assert result.error_message == "Unable to connect to AWS CloudWatch"
        assert result.count == 0
        
        # Manager should be in error state
        assert manager.state == LogGroupManagerState.ERROR
        assert manager.is_ready is False
        assert manager.count == 0
        
        # Format should show error state
        formatted = manager.format_for_prompt()
        assert "Failed to load log groups" in formatted
        assert "Unable to connect to AWS CloudWatch" in formatted
        assert "`list_log_groups` tool" in formatted
        
    @pytest.mark.asyncio
    async def test_permission_denied_error(self):
        """Test handling of AWS permission denied errors."""
        mock_datasource = Mock()
        
        mock_client = MagicMock()
        mock_client.get_paginator.side_effect = Exception(
            "AccessDeniedException: User is not authorized to perform: logs:DescribeLogGroups"
        )
        mock_datasource.client = mock_client
        
        manager = LogGroupManager(mock_datasource)
        result = await manager.load_all()
        
        assert result.success is False
        assert "AccessDeniedException" in result.error_message
        assert manager.state == LogGroupManagerState.ERROR
        
        formatted = manager.format_for_prompt()
        assert "Failed to load log groups" in formatted
        assert "AccessDeniedException" in formatted
        
    @pytest.mark.asyncio
    async def test_timeout_fallback_behavior(self):
        """Test behavior when operation times out."""
        mock_datasource = Mock()
        
        mock_client = MagicMock()
        mock_client.get_paginator.side_effect = asyncio.TimeoutError("Operation timed out")
        mock_datasource.client = mock_client
        
        manager = LogGroupManager(mock_datasource)
        result = await manager.load_all()
        
        assert result.success is False
        assert "Operation timed out" in result.error_message
        assert manager.state == LogGroupManagerState.ERROR


class TestStartupFlowIntegration:
    """Test the full startup flow with orchestrator integration."""

    @pytest.mark.asyncio
    async def test_startup_flow_end_to_end(self):
        """Test complete startup sequence with log groups loaded before orchestrator init."""
        # 1. Mock datasource
        mock_datasource = Mock()
        page = {
            "logGroups": [
                {"logGroupName": f"/aws/lambda/service-{i}", "creationTime": 1234567890000}
                for i in range(25)
            ]
        }
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [page]
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client
        
        # 2. Create log group manager and load
        manager = LogGroupManager(mock_datasource)
        load_result = await manager.load_all()
        
        assert load_result.success is True
        assert manager.count == 25
        assert manager.is_ready is True
        
        # 3. Create orchestrator with log group manager
        mock_llm = AsyncMock()
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_sanitizer = Mock(spec=LogSanitizer)
        mock_settings = Mock(spec=LogAISettings)
        mock_settings.max_tool_iterations = 10
        mock_settings.auto_retry_enabled = True
        mock_settings.intent_detection_enabled = True
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=mock_settings,
            log_group_manager=manager,
        )
        
        # 4. Verify system prompt includes log groups
        system_prompt = orchestrator._get_system_prompt()
        
        assert "## Available Log Groups" in system_prompt
        assert "**Total:** 25 log groups" in system_prompt
        for i in range(25):
            assert f"/aws/lambda/service-{i}" in system_prompt
        
        # 5. Verify orchestrator has reference to manager
        assert orchestrator.log_group_manager is manager
        
    @pytest.mark.asyncio
    async def test_orchestrator_works_without_log_group_manager(self):
        """Test backward compatibility - orchestrator works without manager."""
        mock_llm = AsyncMock()
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_sanitizer = Mock(spec=LogSanitizer)
        mock_settings = Mock(spec=LogAISettings)
        mock_settings.max_tool_iterations = 10
        mock_settings.auto_retry_enabled = True
        mock_settings.intent_detection_enabled = True
        
        # Create orchestrator without log group manager
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=mock_settings,
            log_group_manager=None,
        )
        
        system_prompt = orchestrator._get_system_prompt()
        
        # Should have fallback message
        assert "Log groups will be discovered via the `list_log_groups` tool" in system_prompt


class TestRefreshCommand:
    """Test the /refresh command functionality."""

    @pytest.mark.asyncio
    async def test_refresh_updates_log_groups(self):
        """Test that refresh updates the log group list."""
        mock_datasource = Mock()
        
        # Initial load: 50 groups
        initial_page = {
            "logGroups": [
                {"logGroupName": f"/aws/lambda/initial-{i}", "creationTime": 1234567890000}
                for i in range(50)
            ]
        }
        
        # After refresh: 60 groups (10 new)
        refreshed_pages = {
            "logGroups": [
                {"logGroupName": f"/aws/lambda/initial-{i}", "creationTime": 1234567890000}
                for i in range(50)
            ] + [
                {"logGroupName": f"/aws/lambda/new-{i}", "creationTime": 1234567890000}
                for i in range(10)
            ]
        }
        
        mock_paginator = MagicMock()
        # First call returns 50, second call returns 60
        mock_paginator.paginate.side_effect = [[initial_page], [refreshed_pages]]
        
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client
        
        # Initial load
        manager = LogGroupManager(mock_datasource)
        initial_result = await manager.load_all()
        
        assert initial_result.count == 50
        initial_names = set(manager.get_log_group_names())
        assert len(initial_names) == 50
        
        # Refresh
        refresh_result = await manager.refresh()
        
        assert refresh_result.success is True
        assert refresh_result.count == 60
        
        refreshed_names = set(manager.get_log_group_names())
        assert len(refreshed_names) == 60
        
        # Verify new groups are present
        for i in range(10):
            assert f"/aws/lambda/new-{i}" in refreshed_names
        
    @pytest.mark.asyncio
    async def test_refresh_updates_orchestrator_context(self):
        """Test that refresh injects updated context into orchestrator."""
        # Setup
        mock_datasource = Mock()
        page = {"logGroups": [{"logGroupName": "/aws/lambda/test", "creationTime": 1234567890000}]}
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [page]
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client
        
        manager = LogGroupManager(mock_datasource)
        await manager.load_all()
        
        # Create orchestrator
        mock_llm = AsyncMock()
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_sanitizer = Mock(spec=LogSanitizer)
        mock_settings = Mock(spec=LogAISettings)
        mock_settings.max_tool_iterations = 10
        mock_settings.auto_retry_enabled = True
        mock_settings.intent_detection_enabled = True
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=mock_settings,
            log_group_manager=manager,
        )
        
        # Simulate refresh with updated log groups
        updated_page = {
            "logGroups": [
                {"logGroupName": "/aws/lambda/test", "creationTime": 1234567890000},
                {"logGroupName": "/aws/lambda/new-service", "creationTime": 1234567890000},
            ]
        }
        mock_paginator.paginate.return_value = [updated_page]
        
        await manager.refresh()
        
        # Inject context update into orchestrator
        refresh_notice = f"""## Log Groups Updated

The log group list has been refreshed. You now have access to {manager.count} log groups.

{manager.format_for_prompt()}
"""
        orchestrator.inject_context_update(refresh_notice)
        
        # Verify pending injection
        pending = orchestrator._get_pending_context_injection()
        assert pending is not None
        assert "Log Groups Updated" in pending
        assert f"{manager.count} log groups" in pending


class TestPerformanceAndScaling:
    """Test performance characteristics with different scales."""

    @pytest.mark.asyncio
    async def test_handles_1000_log_groups_efficiently(self):
        """Test that manager can handle 1000 log groups."""
        mock_datasource = Mock()
        
        # Create 1000 log groups across 20 pages
        pages = []
        for page_num in range(20):
            page = {
                "logGroups": [
                    {
                        "logGroupName": f"/aws/lambda/fn-{page_num * 50 + i:04d}",
                        "creationTime": 1234567890000,
                        "storedBytes": 1024 * 1024,
                    }
                    for i in range(50)
                ]
            }
            pages.append(page)
        
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = pages
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client
        
        manager = LogGroupManager(mock_datasource)
        
        # Measure load time
        import time
        start = time.monotonic()
        result = await manager.load_all()
        duration = time.monotonic() - start
        
        assert result.success is True
        assert result.count == 1000
        
        # Should complete reasonably quickly (< 5 seconds for mock data)
        assert duration < 5.0
        
        # Should use summary format
        formatted = manager.format_for_prompt()
        assert "Log Group Categories" in formatted
        assert "Sample Log Groups" in formatted
        
    @pytest.mark.asyncio
    async def test_memory_efficiency_with_large_dataset(self):
        """Test memory efficiency with large number of log groups."""
        mock_datasource = Mock()
        
        # Create 5000 log groups
        pages = []
        for page_num in range(100):  # 100 pages of 50
            page = {
                "logGroups": [
                    {
                        "logGroupName": f"/aws/service/group-{page_num * 50 + i:05d}",
                        "creationTime": 1234567890000,
                        "storedBytes": 1024,
                    }
                    for i in range(50)
                ]
            }
            pages.append(page)
        
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = pages
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client
        
        manager = LogGroupManager(mock_datasource)
        result = await manager.load_all()
        
        assert result.count == 5000
        
        # Get sample - should be limited
        formatted = manager.format_for_prompt()
        sample_lines = [l for l in formatted.split("\n") if l.strip().startswith("- /")]
        
        # Sample should be much smaller than total
        assert len(sample_lines) <= manager.SUMMARY_SAMPLE_SIZE + 20


class TestRegressionScenarios:
    """Test that existing functionality still works."""

    @pytest.mark.asyncio
    async def test_existing_list_log_groups_tool_still_works(self):
        """Verify that the list_log_groups tool can still be called if needed."""
        # This tests backward compatibility
        mock_datasource = Mock()
        page = {"logGroups": [{"logGroupName": "/test", "creationTime": 1234567890000}]}
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [page]
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client
        
        manager = LogGroupManager(mock_datasource)
        await manager.load_all()
        
        # Manager should provide find functionality
        matches = manager.find_matching_groups("test")
        assert len(matches) == 1
        assert matches[0].name == "/test"
        
    @pytest.mark.asyncio
    async def test_orchestrator_conversation_still_works(self):
        """Test that normal orchestrator conversations work with log group manager."""
        mock_datasource = Mock()
        page = {"logGroups": [{"logGroupName": "/aws/lambda/api", "creationTime": 1234567890000}]}
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [page]
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client
        
        manager = LogGroupManager(mock_datasource)
        await manager.load_all()
        
        # Create orchestrator
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = LLMResponse(
            content="I can see the /aws/lambda/api log group is available.",
            finish_reason="stop",
        )
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_sanitizer = Mock(spec=LogSanitizer)
        mock_settings = Mock(spec=LogAISettings)
        mock_settings.max_tool_iterations = 10
        mock_settings.auto_retry_enabled = True
        mock_settings.intent_detection_enabled = True
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=mock_settings,
            log_group_manager=manager,
        )
        
        # Send a query
        response = await orchestrator.chat("What log groups do you have?")
        
        # Should work normally
        assert "log group" in response.lower()
