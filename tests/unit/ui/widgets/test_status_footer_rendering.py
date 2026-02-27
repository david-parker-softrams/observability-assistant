"""Unit tests for StatusFooter rendering methods."""

import pytest
from logai.ui.widgets.status_footer import StatusFooter
from rich.text import Text


class TestRenderStatusInfo:
    """Test suite for _render_status_info() method."""

    def test_render_status_info_ready_state(self):
        """Test rendering when status is 'Ready'."""
        footer = StatusFooter()
        footer.status = "Ready"
        footer.cache_hits = 0
        footer.cache_misses = 0

        result = footer._render_status_info()

        assert isinstance(result, Text)
        assert "Ready" in result.plain
        assert "Cache: 0/0" in result.plain

    def test_render_status_info_active_state(self):
        """Test rendering when status is active (not 'Ready')."""
        footer = StatusFooter()
        footer.status = "Thinking..."
        footer.cache_hits = 0
        footer.cache_misses = 0

        result = footer._render_status_info()

        assert isinstance(result, Text)
        assert "Thinking..." in result.plain
        # Should have spinner character
        assert len(result.plain) > len("Thinking...")

    def test_render_status_info_with_cache_stats(self):
        """Test rendering with cache statistics."""
        footer = StatusFooter()
        footer.status = "Ready"
        footer.cache_hits = 7
        footer.cache_misses = 3

        result = footer._render_status_info()

        assert isinstance(result, Text)
        assert "Cache: 7/10" in result.plain
        assert "70%" in result.plain

    def test_render_status_info_cache_100_percent(self):
        """Test rendering when cache hit rate is 100%."""
        footer = StatusFooter()
        footer.status = "Ready"
        footer.cache_hits = 10
        footer.cache_misses = 0

        result = footer._render_status_info()

        assert "Cache: 10/10" in result.plain
        assert "100%" in result.plain

    def test_render_status_info_cache_0_percent(self):
        """Test rendering when cache hit rate is 0%."""
        footer = StatusFooter()
        footer.status = "Ready"
        footer.cache_hits = 0
        footer.cache_misses = 10

        result = footer._render_status_info()

        assert "Cache: 0/10" in result.plain
        assert "0%" in result.plain

    def test_render_status_info_empty_status(self):
        """Test rendering when status is empty."""
        footer = StatusFooter()
        footer.status = ""
        footer.cache_hits = 5
        footer.cache_misses = 5

        result = footer._render_status_info()

        assert isinstance(result, Text)
        # Should still show cache stats
        assert "Cache: 5/10" in result.plain

    def test_render_status_info_long_status(self):
        """Test rendering with a long status message."""
        footer = StatusFooter()
        footer.status = "Running tool: fetch_cloudwatch_logs with complex parameters..."
        footer.cache_hits = 0
        footer.cache_misses = 0

        result = footer._render_status_info()

        assert "Running tool:" in result.plain
        assert "fetch_cloudwatch_logs" in result.plain


class TestRenderContextInfo:
    """Test suite for _render_context_info() method."""

    def test_render_context_info_basic(self):
        """Test basic context info rendering."""
        footer = StatusFooter(model="qwen3:32b")
        footer.context_utilization = 50.0
        footer.context_used_tokens = 0
        footer.context_total_tokens = 0

        result = footer._render_context_info()

        assert isinstance(result, Text)
        assert "Context:" in result.plain
        assert "50%" in result.plain
        assert "qwen3:32b" in result.plain

    def test_render_context_info_with_token_counts(self):
        """Test context info rendering with token counts."""
        footer = StatusFooter(model="qwen3:32b")
        footer.context_utilization = 75.0
        footer.context_used_tokens = 24000
        footer.context_total_tokens = 32000

        result = footer._render_context_info()

        assert "24.0K/32K" in result.plain
        assert "75%" in result.plain
        assert "qwen3:32b" in result.plain

    def test_render_context_info_green_color_low_utilization(self):
        """Test green color coding for utilization < 71%."""
        footer = StatusFooter()
        footer.context_utilization = 50.0
        footer.context_used_tokens = 0
        footer.context_total_tokens = 0

        result = footer._render_context_info()

        # Check that green style is applied (by checking spans)
        styles = [str(span.style) for span in result.spans]
        assert any("green" in style for style in styles)
        # Should not have prefix
        assert "(!)" not in result.plain
        assert "(!!)" not in result.plain

    def test_render_context_info_yellow_color_medium_utilization(self):
        """Test yellow color coding for 71% <= utilization < 86%."""
        footer = StatusFooter()
        footer.context_utilization = 75.0
        footer.context_used_tokens = 0
        footer.context_total_tokens = 0

        result = footer._render_context_info()

        # Check that yellow style is applied
        styles = [str(span.style) for span in result.spans]
        assert any("yellow" in style for style in styles)
        # Should not have prefix
        assert "(!)" not in result.plain
        assert "(!!)" not in result.plain

    def test_render_context_info_red_color_high_utilization(self):
        """Test red color coding for 86% <= utilization < 95%."""
        footer = StatusFooter()
        footer.context_utilization = 90.0
        footer.context_used_tokens = 0
        footer.context_total_tokens = 0

        result = footer._render_context_info()

        # Check that red style is applied
        styles = [str(span.style) for span in result.spans]
        assert any("red" in style for style in styles)
        # Should have single exclamation prefix
        assert "(!) " in result.plain

    def test_render_context_info_red_bold_critical_utilization(self):
        """Test red bold color coding for utilization >= 95%."""
        footer = StatusFooter()
        footer.context_utilization = 97.0
        footer.context_used_tokens = 0
        footer.context_total_tokens = 0

        result = footer._render_context_info()

        # Check that red bold style is applied
        styles = [str(span.style) for span in result.spans]
        assert any("red" in style and "bold" in style for style in styles)
        # Should have double exclamation prefix
        assert "(!!)" in result.plain

    def test_render_context_info_boundary_71_percent(self):
        """Test color coding at exactly 71% boundary."""
        footer = StatusFooter()
        footer.context_utilization = 71.0

        result = footer._render_context_info()

        # At exactly 71%, should be yellow
        styles = [str(span.style) for span in result.spans]
        assert any("yellow" in style for style in styles)

    def test_render_context_info_boundary_85_percent(self):
        """Test color coding at exactly 85% — the boundary where red/warning color activates."""
        footer = StatusFooter()
        footer.context_utilization = 85.0

        result = footer._render_context_info()

        # At exactly 85%, should be red (boundary is >= 85)
        styles = [str(span.style) for span in result.spans]
        assert any("red" in style for style in styles)
        assert "(!) " in result.plain

    def test_render_context_info_boundary_84_percent(self):
        """Test color coding at exactly 84% — just below the red/warning boundary."""
        footer = StatusFooter()
        footer.context_utilization = 84.0

        result = footer._render_context_info()

        # At exactly 84%, should be yellow (just below the >= 85 red threshold)
        styles = [str(span.style) for span in result.spans]
        assert any("yellow" in style for style in styles)
        assert "(!) " not in result.plain
        assert "(!!)" not in result.plain

    def test_render_context_info_boundary_95_percent(self):
        """Test color coding at exactly 95% boundary."""
        footer = StatusFooter()
        footer.context_utilization = 95.0

        result = footer._render_context_info()

        # At exactly 95%, should be red bold
        styles = [str(span.style) for span in result.spans]
        assert any("red" in style and "bold" in style for style in styles)
        assert "(!!)" in result.plain

    def test_render_context_info_zero_utilization(self):
        """Test rendering with 0% context utilization."""
        footer = StatusFooter(model="test-model")
        footer.context_utilization = 0.0
        footer.context_used_tokens = 0
        footer.context_total_tokens = 32000

        result = footer._render_context_info()

        assert "0.0K/32K" in result.plain or "0%" in result.plain
        assert "test-model" in result.plain

    def test_render_context_info_100_percent_utilization(self):
        """Test rendering with 100% context utilization."""
        footer = StatusFooter(model="test-model")
        footer.context_utilization = 100.0
        footer.context_used_tokens = 32000
        footer.context_total_tokens = 32000

        result = footer._render_context_info()

        assert "(!!)" in result.plain  # Should have critical warning
        assert "100%" in result.plain

    def test_render_context_info_different_models(self):
        """Test rendering with different model names."""
        models = ["qwen3:32b", "gpt-4", "claude-3-opus", "llama3:70b"]

        for model in models:
            footer = StatusFooter(model=model)
            footer.context_utilization = 50.0

            result = footer._render_context_info()

            assert model in result.plain


class TestContentUpdates:
    """Test suite for content updates when reactive properties change."""

    def test_status_change_triggers_update(self):
        """Test that changing status triggers proper updates."""
        footer = StatusFooter()
        initial_status = footer.status

        footer.status = "New Status"

        assert footer.status == "New Status"
        assert footer.status != initial_status

    def test_cache_hits_change_triggers_update(self):
        """Test that changing cache_hits triggers proper updates."""
        footer = StatusFooter()

        footer.cache_hits = 5

        assert footer.cache_hits == 5

    def test_cache_misses_change_triggers_update(self):
        """Test that changing cache_misses triggers proper updates."""
        footer = StatusFooter()

        footer.cache_misses = 3

        assert footer.cache_misses == 3

    def test_model_change_triggers_update(self):
        """Test that changing model triggers proper updates."""
        footer = StatusFooter()

        footer.model = "new-model"

        assert footer.model == "new-model"

    def test_context_utilization_change_triggers_update(self):
        """Test that changing context_utilization triggers proper updates."""
        footer = StatusFooter()

        footer.context_utilization = 85.5

        assert footer.context_utilization == 85.5

    def test_multiple_property_changes(self):
        """Test multiple property changes work correctly."""
        footer = StatusFooter()

        footer.status = "Thinking"
        footer.cache_hits = 10
        footer.cache_misses = 2
        footer.context_utilization = 75.0
        footer.model = "qwen3:32b"

        assert footer.status == "Thinking"
        assert footer.cache_hits == 10
        assert footer.cache_misses == 2
        assert footer.context_utilization == 75.0
        assert footer.model == "qwen3:32b"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
