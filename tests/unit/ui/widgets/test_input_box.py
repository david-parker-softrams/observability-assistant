"""Unit tests for ChatInput — history navigation and state management.

Coverage:
    - add_to_history(): storage, whitespace filtering, index reset, deque cap
    - Up arrow: first press saves draft, navigates to newest, moves toward oldest
    - Up arrow: boundary — no-op at oldest entry, no-op on empty history
    - Down arrow: moves toward newest entry
    - Down arrow: navigating past newest restores draft and exits browsing mode
    - Down arrow: no-op when not browsing
    - Draft preservation: round-trip through history returns original draft
    - Cursor placement: cursor is at end of text after every navigation step
    - Submission while browsing: resets browse state (via add_to_history)
"""

import pytest
from logai.ui.widgets.input_box import ChatInput
from textual.app import App, ComposeResult


class _TestApp(App):
    """Minimal single-widget app that mounts a ChatInput for testing."""

    def compose(self) -> ComposeResult:
        yield ChatInput()

    async def on_mount(self) -> None:
        """Ensure the input is focused so pilot.press() delivers keys to it."""
        self.query_one(ChatInput).focus()


# ---------------------------------------------------------------------------
# Pure-state tests — no Textual app context required
# ---------------------------------------------------------------------------


class TestAddToHistory:
    """Tests for ChatInput.add_to_history() state management."""

    def test_initial_state(self) -> None:
        """History is empty and index is -1 at construction."""
        widget = ChatInput()
        assert len(widget._history) == 0
        assert widget._history_index == -1
        assert widget._draft == ""

    def test_add_single_message(self) -> None:
        """A non-empty message is appended to the history deque."""
        widget = ChatInput()
        widget.add_to_history("hello")
        assert list(widget._history) == ["hello"]

    def test_add_multiple_messages_oldest_first(self) -> None:
        """Messages are stored oldest-first (index 0 = oldest, -1 = newest)."""
        widget = ChatInput()
        widget.add_to_history("first")
        widget.add_to_history("second")
        widget.add_to_history("third")
        assert list(widget._history) == ["first", "second", "third"]

    def test_whitespace_only_is_ignored(self) -> None:
        """Whitespace-only strings are not added to history."""
        widget = ChatInput()
        widget.add_to_history("   ")
        widget.add_to_history("\t\n")
        widget.add_to_history("")
        assert len(widget._history) == 0

    def test_message_with_surrounding_whitespace_is_stored(self) -> None:
        """A string that has content after strip() is stored as-is."""
        widget = ChatInput()
        widget.add_to_history("  hello  ")
        assert list(widget._history) == ["  hello  "]

    def test_add_resets_history_index_to_minus_one(self) -> None:
        """Calling add_to_history resets _history_index to -1."""
        widget = ChatInput()
        widget.add_to_history("first")
        widget._history_index = 0
        widget._draft = "my draft"
        widget.add_to_history("second")
        assert widget._history_index == -1

    def test_add_clears_draft(self) -> None:
        """Calling add_to_history clears any saved draft."""
        widget = ChatInput()
        widget._draft = "unsent draft"
        widget.add_to_history("submitted message")
        assert widget._draft == ""

    def test_history_maxlen_100_drops_oldest(self) -> None:
        """After 101 submissions the oldest entry is dropped."""
        widget = ChatInput()
        for i in range(101):
            widget.add_to_history(f"message {i}")
        assert len(widget._history) == 100
        assert widget._history[0] == "message 1"  # "message 0" dropped
        assert widget._history[-1] == "message 100"

    def test_history_maxlen_exact_boundary(self) -> None:
        """Exactly 100 messages fill the deque without dropping any."""
        widget = ChatInput()
        for i in range(100):
            widget.add_to_history(f"msg {i}")
        assert len(widget._history) == 100
        assert widget._history[0] == "msg 0"
        assert widget._history[-1] == "msg 99"


class TestSubmitWhileBrowsing:
    """add_to_history() resets browse state as if a submission occurred."""

    def test_exits_browsing_mode(self) -> None:
        """Calling add_to_history while browsing resets _history_index to -1."""
        widget = ChatInput()
        widget.add_to_history("first")
        widget._history_index = 0
        widget._draft = "unsent"
        widget.add_to_history("second")
        assert widget._history_index == -1
        assert widget._draft == ""
        assert list(widget._history) == ["first", "second"]


# ---------------------------------------------------------------------------
# Key-navigation tests — require a running Textual app context.
# asyncio_mode = "auto" in pyproject.toml handles the event loop automatically.
# ---------------------------------------------------------------------------


class TestUpArrowNavigation:
    """Tests for Up-arrow history navigation."""

    async def test_up_on_empty_history_is_noop(self) -> None:
        """Up on empty history does not change the value or index."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.value = "draft"
            await pilot.pause()

            await pilot.press("up")
            await pilot.pause()

            assert widget.value == "draft"
            assert widget._history_index == -1

    async def test_up_navigates_to_newest_entry(self) -> None:
        """First Up press jumps to the newest (rightmost) history entry."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("foo")
            widget.add_to_history("bar")  # newest

            await pilot.press("up")
            await pilot.pause()

            assert widget.value == "bar"

    async def test_up_saves_draft_on_first_press(self) -> None:
        """The current value is saved as _draft before the first Up."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("history entry")
            widget.value = "my unsent draft"
            await pilot.pause()

            await pilot.press("up")
            await pilot.pause()

            assert widget._draft == "my unsent draft"

    async def test_up_moves_toward_older_entries(self) -> None:
        """Successive Up presses traverse history from newest to oldest."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("oldest")
            widget.add_to_history("middle")
            widget.add_to_history("newest")

            await pilot.press("up")
            await pilot.pause()
            assert widget.value == "newest"

            await pilot.press("up")
            await pilot.pause()
            assert widget.value == "middle"

            await pilot.press("up")
            await pilot.pause()
            assert widget.value == "oldest"

    async def test_up_at_oldest_does_not_wrap(self) -> None:
        """Pressing Up when already at the oldest entry is a no-op (no wrap)."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("only")

            await pilot.press("up")  # → "only"
            await pilot.pause()
            assert widget.value == "only"
            index_at_oldest = widget._history_index

            await pilot.press("up")  # should stay on "only"
            await pilot.pause()
            assert widget.value == "only"
            assert widget._history_index == index_at_oldest

    async def test_up_places_cursor_at_end(self) -> None:
        """After Up, cursor_position equals len(value)."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("hello world")

            await pilot.press("up")
            await pilot.pause()

            assert widget.cursor_position == len("hello world")


class TestDownArrowNavigation:
    """Tests for Down-arrow history navigation."""

    async def test_down_when_not_browsing_is_noop(self) -> None:
        """Down while _history_index is -1 does nothing."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("entry")
            widget.value = "current"
            await pilot.pause()

            await pilot.press("down")
            await pilot.pause()

            assert widget.value == "current"
            assert widget._history_index == -1

    async def test_down_navigates_to_newer_entry(self) -> None:
        """Down moves from an older entry toward the newest."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("oldest")
            widget.add_to_history("newest")

            await pilot.press("up")  # → newest
            await pilot.press("up")  # → oldest
            await pilot.press("down")  # → newest
            await pilot.pause()

            assert widget.value == "newest"

    async def test_down_past_newest_restores_draft(self) -> None:
        """Down past the newest entry restores the saved draft text."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("sent message")
            widget.value = "unsent draft"
            await pilot.pause()

            await pilot.press("up")  # save draft, → "sent message"
            await pilot.press("down")  # past newest → restore draft
            await pilot.pause()

            assert widget.value == "unsent draft"

    async def test_down_past_newest_resets_history_index(self) -> None:
        """_history_index is set back to -1 after navigating past newest."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("entry")

            await pilot.press("up")  # start browsing
            await pilot.pause()
            assert widget._history_index == 0

            await pilot.press("down")  # exit browsing
            await pilot.pause()
            assert widget._history_index == -1

    async def test_down_past_newest_further_down_is_noop(self) -> None:
        """Once back at -1, additional Down presses do nothing."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("entry")
            widget.value = "draft"
            await pilot.pause()

            await pilot.press("up")  # start browsing
            await pilot.press("down")  # exit browsing → restore "draft"
            await pilot.pause()
            assert widget.value == "draft"

            await pilot.press("down")  # should be a no-op
            await pilot.pause()
            assert widget.value == "draft"
            assert widget._history_index == -1

    async def test_down_places_cursor_at_end(self) -> None:
        """After Down, cursor_position equals len(value)."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("short")
            widget.add_to_history("longer text here")

            await pilot.press("up")  # → "longer text here"
            await pilot.press("up")  # → "short"
            await pilot.press("down")  # → "longer text here"
            await pilot.pause()

            assert widget.cursor_position == len("longer text here")


class TestDraftPreservation:
    """Draft text is faithfully saved and restored across navigation."""

    async def test_empty_draft_is_preserved(self) -> None:
        """An empty input value is preserved as the draft (empty string)."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("entry")
            # Input starts empty by default

            await pilot.press("up")  # saves "" as draft
            await pilot.press("down")  # restores ""
            await pilot.pause()

            assert widget.value == ""

    async def test_draft_saved_only_on_first_up(self) -> None:
        """_draft is captured on the first Up press and not overwritten later."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("a")
            widget.add_to_history("b")
            widget.add_to_history("c")
            widget.value = "original draft"
            await pilot.pause()

            await pilot.press("up")  # saves "original draft", → "c"
            await pilot.press("up")  # → "b"
            await pilot.press("up")  # → "a"
            await pilot.pause()

            assert widget._draft == "original draft"

    async def test_full_round_trip(self) -> None:
        """Navigate all the way back, then all the way forward to draft."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("foo")
            widget.add_to_history("bar")
            widget.add_to_history("baz")
            widget.value = "my draft"
            await pilot.pause()

            # Navigate backward through all history
            await pilot.press("up")  # → "baz"
            await pilot.press("up")  # → "bar"
            await pilot.press("up")  # → "foo"
            await pilot.press("up")  # no-op (oldest)
            await pilot.pause()
            assert widget.value == "foo"

            # Navigate forward back to draft
            await pilot.press("down")  # → "bar"
            await pilot.press("down")  # → "baz"
            await pilot.press("down")  # → restore draft
            await pilot.pause()
            assert widget.value == "my draft"
            assert widget._history_index == -1

    async def test_acceptance_criteria_ac1_up_no_wrap(self) -> None:
        """AC1: foo/bar/baz sent → Up x4 shows baz, bar, foo, foo (no wrap)."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("foo")
            widget.add_to_history("bar")
            widget.add_to_history("baz")

            await pilot.press("up")
            await pilot.pause()
            assert widget.value == "baz"

            await pilot.press("up")
            await pilot.pause()
            assert widget.value == "bar"

            await pilot.press("up")
            await pilot.pause()
            assert widget.value == "foo"

            await pilot.press("up")  # no-op at oldest
            await pilot.pause()
            assert widget.value == "foo"

    async def test_acceptance_criteria_ac2_down_restores_empty_draft(self) -> None:
        """AC2: From foo → Down x3 shows bar, baz, then restores empty draft."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("foo")
            widget.add_to_history("bar")
            widget.add_to_history("baz")

            await pilot.press("up")  # → baz
            await pilot.press("up")  # → bar
            await pilot.press("up")  # → foo

            await pilot.press("down")  # → bar
            await pilot.pause()
            assert widget.value == "bar"

            await pilot.press("down")  # → baz
            await pilot.pause()
            assert widget.value == "baz"

            await pilot.press("down")  # restore empty draft
            await pilot.pause()
            assert widget.value == ""
            assert widget._history_index == -1

    async def test_acceptance_criteria_ac3_typed_draft_restored(self) -> None:
        """AC3: type "draft", Up to baz, Down twice → restores "draft"."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("foo")
            widget.add_to_history("bar")
            widget.add_to_history("baz")
            widget.value = "draft"
            await pilot.pause()

            await pilot.press("up")  # → "baz", saves "draft"
            await pilot.pause()
            assert widget.value == "baz"

            await pilot.press("down")  # past newest → restore "draft"
            await pilot.pause()
            assert widget.value == "draft"

    async def test_submit_resets_browse_and_next_up_starts_from_newest(self) -> None:
        """After submission (add_to_history), next Up starts from newest entry."""
        async with _TestApp().run_test() as pilot:
            widget = pilot.app.query_one(ChatInput)
            widget.add_to_history("alpha")
            widget.add_to_history("beta")

            await pilot.press("up")  # → "beta"
            await pilot.press("up")  # → "alpha"

            # Simulate submission: reset state and append new entry
            widget.add_to_history("gamma")
            assert widget._history_index == -1

            await pilot.press("up")  # → "gamma" (newest)
            await pilot.pause()
            assert widget.value == "gamma"
