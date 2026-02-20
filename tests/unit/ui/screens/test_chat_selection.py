"""Unit tests for ChatScreen log group selection context injection."""

from unittest.mock import Mock

import pytest
from logai.cache.manager import CacheManager
from logai.core.orchestrator import LLMOrchestrator
from logai.ui.screens.chat import ChatScreen


class TestContextFormatting:
    """Test suite for context formatting methods."""

    def test_format_selected_groups_context_single_group(self):
        """Test context format with single group."""
        # Create mock dependencies
        mock_orchestrator = Mock(spec=LLMOrchestrator)
        mock_cache = Mock(spec=CacheManager)

        # Create ChatScreen instance
        screen = ChatScreen(orchestrator=mock_orchestrator, cache_manager=mock_cache)

        # Format context for single group
        selected_groups = ["/aws/lambda/auth-service"]
        context = screen._format_selected_groups_context(selected_groups)

        # Verify structure
        assert "USER HAS SELECTED THE FOLLOWING LOG GROUPS:" in context
        assert "1 log group(s)" in context
        assert "- /aws/lambda/auth-service" in context
        assert "INSTRUCTIONS:" in context
        assert "Selected groups: /aws/lambda/auth-service" in context

    def test_format_selected_groups_context_multiple_groups(self):
        """Test context format with multiple groups."""
        mock_orchestrator = Mock(spec=LLMOrchestrator)
        mock_cache = Mock(spec=CacheManager)

        screen = ChatScreen(orchestrator=mock_orchestrator, cache_manager=mock_cache)

        # Format context for multiple groups
        selected_groups = [
            "/aws/lambda/auth-service",
            "/aws/lambda/user-service",
            "/aws/lambda/billing",
        ]
        context = screen._format_selected_groups_context(selected_groups)

        # Verify structure
        assert "3 log group(s)" in context
        assert "- /aws/lambda/auth-service" in context
        assert "- /aws/lambda/user-service" in context
        assert "- /aws/lambda/billing" in context

        # Verify comma-separated list at end
        assert (
            "Selected groups: /aws/lambda/auth-service, /aws/lambda/user-service, /aws/lambda/billing"
            in context
        )

    def test_format_selected_groups_context_many_groups(self):
        """Test context format handles many groups correctly."""
        mock_orchestrator = Mock(spec=LLMOrchestrator)
        mock_cache = Mock(spec=CacheManager)

        screen = ChatScreen(orchestrator=mock_orchestrator, cache_manager=mock_cache)

        # Format context for many groups
        selected_groups = [f"/aws/lambda/service-{i:02d}" for i in range(10)]
        context = screen._format_selected_groups_context(selected_groups)

        # Verify count
        assert "10 log group(s)" in context

        # Verify all groups are listed
        for group in selected_groups:
            assert f"- {group}" in context

        # Verify structure is maintained
        assert "USER HAS SELECTED THE FOLLOWING LOG GROUPS:" in context
        assert "INSTRUCTIONS:" in context

    def test_format_selected_groups_context_preserves_order(self):
        """Test that context preserves the order of selected groups."""
        mock_orchestrator = Mock(spec=LLMOrchestrator)
        mock_cache = Mock(spec=CacheManager)

        screen = ChatScreen(orchestrator=mock_orchestrator, cache_manager=mock_cache)

        # Note: get_selected_groups() returns sorted list, so we test with already-sorted input
        selected_groups = ["/aaa/first", "/bbb/second", "/ccc/third"]
        context = screen._format_selected_groups_context(selected_groups)

        # Extract the bulleted list section
        lines = context.split("\n")
        bulleted_lines = [line for line in lines if line.startswith("- ")]

        # Verify order is preserved
        assert bulleted_lines[0] == "- /aaa/first"
        assert bulleted_lines[1] == "- /bbb/second"
        assert bulleted_lines[2] == "- /ccc/third"

    def test_format_selected_groups_context_includes_key_instructions(self):
        """Test that all key instructions are included in context."""
        mock_orchestrator = Mock(spec=LLMOrchestrator)
        mock_cache = Mock(spec=CacheManager)

        screen = ChatScreen(orchestrator=mock_orchestrator, cache_manager=mock_cache)

        selected_groups = ["/aws/lambda/test"]
        context = screen._format_selected_groups_context(selected_groups)

        # Verify all key instructions are present
        assert "these logs" in context.lower()
        assert "selected groups" in context.lower()
        assert "use the above log groups" in context.lower()
        assert "do not need to ask" in context.lower()


class TestSelectionContextEdgeCases:
    """Test edge cases in selection context handling."""

    def test_format_context_with_special_characters_in_names(self):
        """Test that log group names with special characters are handled correctly."""
        mock_orchestrator = Mock(spec=LLMOrchestrator)
        mock_cache = Mock(spec=CacheManager)

        screen = ChatScreen(orchestrator=mock_orchestrator, cache_manager=mock_cache)

        # Groups with special characters
        selected_groups = [
            "/aws/lambda/service-with-dashes",
            "/aws/lambda/service_with_underscores",
            "/aws/lambda/service.with.dots",
        ]
        context = screen._format_selected_groups_context(selected_groups)

        # Verify all groups are present and properly formatted
        for group in selected_groups:
            assert f"- {group}" in context
            assert group in context

    def test_format_context_with_very_long_group_names(self):
        """Test that very long log group names don't break formatting."""
        mock_orchestrator = Mock(spec=LLMOrchestrator)
        mock_cache = Mock(spec=CacheManager)

        screen = ChatScreen(orchestrator=mock_orchestrator, cache_manager=mock_cache)

        # Very long group name
        long_name = "/aws/lambda/" + "very-long-service-name-" * 10
        selected_groups = [long_name]
        context = screen._format_selected_groups_context(selected_groups)

        # Verify context is generated without error and contains the long name
        assert "USER HAS SELECTED THE FOLLOWING LOG GROUPS:" in context
        assert long_name in context

    def test_format_context_empty_list_handled_gracefully(self):
        """Test that empty list doesn't crash (though should not be called with empty list)."""
        mock_orchestrator = Mock(spec=LLMOrchestrator)
        mock_cache = Mock(spec=CacheManager)

        screen = ChatScreen(orchestrator=mock_orchestrator, cache_manager=mock_cache)

        # Empty list (edge case)
        selected_groups = []
        context = screen._format_selected_groups_context(selected_groups)

        # Should generate context with 0 groups
        assert "0 log group(s)" in context
        assert "USER HAS SELECTED THE FOLLOWING LOG GROUPS:" in context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
