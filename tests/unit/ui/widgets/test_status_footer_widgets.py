"""Unit tests for StatusFooter widget composition and structure."""

import pytest
from logai.ui.widgets.status_footer import ClickableContextLabel, StatusFooter
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static


class StatusFooterTestApp(App):
    """Test app to mount StatusFooter widget."""

    def __init__(self, model: str = "test-model"):
        super().__init__()
        self.model = model

    def compose(self) -> ComposeResult:
        yield StatusFooter(model=self.model)


class TestStatusFooterWidgetComposition:
    """Test suite for StatusFooter widget composition."""

    @pytest.mark.asyncio
    async def test_compose_yields_three_widgets(self):
        """Verify compose() yields exactly 3 widgets in correct order."""
        app = StatusFooterTestApp()
        async with app.run_test() as _pilot:
            footer = app.query_one(StatusFooter)

            # Get all direct children of the footer
            children = list(footer.children)

            # Should have exactly 3 direct children
            assert len(children) == 3, f"Expected 3 children, got {len(children)}"

    @pytest.mark.asyncio
    async def test_compose_correct_widget_types(self):
        """Verify correct widget types are created (Horizontal, Static, ClickableContextLabel)."""
        app = StatusFooterTestApp()
        async with app.run_test() as _pilot:
            footer = app.query_one(StatusFooter)
            children = list(footer.children)

            # First widget should be Horizontal container (keyboard shortcuts)
            assert isinstance(
                children[0], Horizontal
            ), f"First widget should be Horizontal, got {type(children[0])}"

            # Second widget should be Static (non-clickable status info)
            assert isinstance(
                children[1], Static
            ), f"Second widget should be Static, got {type(children[1])}"
            assert not isinstance(
                children[1], ClickableContextLabel
            ), "Second widget should NOT be ClickableContextLabel"

            # Third widget should be ClickableContextLabel (clickable context info)
            assert isinstance(
                children[2], ClickableContextLabel
            ), f"Third widget should be ClickableContextLabel, got {type(children[2])}"

    @pytest.mark.asyncio
    async def test_compose_correct_widget_ids(self):
        """Verify correct IDs are set on the widgets."""
        app = StatusFooterTestApp()
        async with app.run_test() as _pilot:
            footer = app.query_one(StatusFooter)

            # Query for status-info widget (non-clickable)
            status_widget = footer.query_one("#status-info", Static)
            assert status_widget is not None
            assert status_widget.id == "status-info"

            # Query for context-clickable widget
            context_widget = footer.query_one("#context-clickable", ClickableContextLabel)
            assert context_widget is not None
            assert context_widget.id == "context-clickable"

    @pytest.mark.asyncio
    async def test_horizontal_container_exists(self):
        """Verify Horizontal container for keyboard shortcuts exists."""
        app = StatusFooterTestApp()
        async with app.run_test() as _pilot:
            footer = app.query_one(StatusFooter)

            # Should be able to query for Horizontal container
            horizontal = footer.query_one(Horizontal)
            assert horizontal is not None

    @pytest.mark.asyncio
    async def test_widget_mounting_succeeds(self):
        """Verify all three widgets mount successfully."""
        app = StatusFooterTestApp()
        async with app.run_test() as _pilot:
            footer = app.query_one(StatusFooter)

            # All widgets should be mounted
            assert footer.is_mounted

            # Check each child
            for child in footer.children:
                assert child.is_mounted, f"Child {child} is not mounted"

    @pytest.mark.asyncio
    async def test_model_parameter_passed_correctly(self):
        """Verify model parameter is set correctly during initialization."""
        test_model = "qwen3:32b"
        app = StatusFooterTestApp(model=test_model)
        async with app.run_test() as _pilot:
            footer = app.query_one(StatusFooter)

            assert footer.model == test_model

    @pytest.mark.asyncio
    async def test_default_model_value(self):
        """Verify default model value when not specified."""
        app = StatusFooterTestApp()
        async with app.run_test() as _pilot:
            _footer = app.query_one(StatusFooter)

            # Default should be "test-model" from our test app, but the StatusFooter
            # class itself defaults to "Unknown"
            footer_default = StatusFooter()
            assert footer_default.model == "Unknown"


class TestClickableContextLabelWidget:
    """Test suite for ClickableContextLabel widget."""

    @pytest.mark.asyncio
    async def test_clickable_context_label_can_focus(self):
        """Verify ClickableContextLabel has correct focus settings."""
        label = ClickableContextLabel("Test Content")

        # Should have can_focus set to False (as per design)
        assert label.can_focus is False

    @pytest.mark.asyncio
    async def test_clickable_context_label_has_default_css(self):
        """Verify ClickableContextLabel has default CSS defined."""
        # Check that DEFAULT_CSS is defined
        assert hasattr(ClickableContextLabel, "DEFAULT_CSS")
        assert ClickableContextLabel.DEFAULT_CSS is not None

        # Check that hover styles are defined
        css = ClickableContextLabel.DEFAULT_CSS
        assert "&:hover" in css or ":hover" in css

    @pytest.mark.asyncio
    async def test_clickable_context_label_initialization(self):
        """Verify ClickableContextLabel initializes correctly."""
        test_content = "Context: 50% | model"
        label = ClickableContextLabel(test_content)

        # Should initialize without error
        assert label is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
