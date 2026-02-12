"""Log group manager for pre-loading CloudWatch log groups."""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from logai.providers.datasources.cloudwatch import CloudWatchDataSource


class LogGroupManagerState(Enum):
    """State of the log group manager."""

    UNINITIALIZED = "uninitialized"
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"


@dataclass
class LogGroupInfo:
    """
    Lightweight representation of a CloudWatch log group.

    Stores only essential information to minimize memory footprint.
    """

    name: str
    created: int | None = None  # Epoch milliseconds
    stored_bytes: int = 0
    retention_days: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogGroupInfo":
        """Create LogGroupInfo from CloudWatch API response dict."""
        return cls(
            name=data["name"],
            created=data.get("created"),
            stored_bytes=data.get("stored_bytes", 0),
            retention_days=data.get("retention_days"),
        )


@dataclass
class LogGroupManagerResult:
    """Result of a log group fetch operation."""

    success: bool
    log_groups: list[LogGroupInfo] = field(default_factory=list)
    count: int = 0
    error_message: str | None = None
    duration_ms: int = 0


# Type alias for progress callback
ProgressCallback = Callable[[int, str], None]  # (count, message)

# Type alias for update callbacks (UI notifications)
UpdateCallback = Callable[[], None]  # No parameters - sidebar fetches data itself


class LogGroupManager:
    """
    Manages pre-loaded CloudWatch log groups.

    This class handles fetching all log groups at startup and provides
    methods for refreshing and formatting the list for LLM consumption.

    Example:
        manager = LogGroupManager(datasource)
        await manager.load_all(progress_callback=lambda c, m: print(f"{m}: {c}"))
        prompt_section = manager.format_for_prompt()
    """

    # Threshold for switching from full list to summary in prompt
    FULL_LIST_THRESHOLD = 500

    # Maximum log groups to sample in summary mode
    SUMMARY_SAMPLE_SIZE = 100

    def __init__(self, datasource: CloudWatchDataSource) -> None:
        """
        Initialize LogGroupManager.

        Args:
            datasource: CloudWatch data source for API calls
        """
        self.datasource = datasource
        self._log_groups: list[LogGroupInfo] = []
        self._state = LogGroupManagerState.UNINITIALIZED
        self._last_refresh: datetime | None = None
        self._last_error: str | None = None
        # Update callbacks for sidebar notifications
        self._update_callbacks: list[UpdateCallback] = []

    @property
    def state(self) -> LogGroupManagerState:
        """Get current manager state."""
        return self._state

    @property
    def log_groups(self) -> list[LogGroupInfo]:
        """Get current log groups list (read-only copy)."""
        return self._log_groups.copy()

    @property
    def count(self) -> int:
        """Get count of loaded log groups."""
        return len(self._log_groups)

    @property
    def last_refresh(self) -> datetime | None:
        """Get timestamp of last successful refresh."""
        return self._last_refresh

    @property
    def is_ready(self) -> bool:
        """Check if log groups are loaded and ready."""
        return self._state == LogGroupManagerState.READY

    def register_update_callback(self, callback: UpdateCallback) -> None:
        """
        Register a callback to be notified when log groups are updated.

        Args:
            callback: Function to call after successful refresh.
                     Takes no parameters - use get_log_group_names() to fetch data.
        """
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)

    def unregister_update_callback(self, callback: UpdateCallback) -> None:
        """
        Unregister an update callback.

        Args:
            callback: Function to remove from notifications
        """
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)

    def _notify_update(self) -> None:
        """
        Notify all registered callbacks that log groups have been updated.

        Called after successful load_all() or refresh().
        """
        for callback in self._update_callbacks:
            try:
                callback()
            except Exception as e:
                # Log but don't fail - UI callback errors shouldn't break manager
                import logging

                logging.getLogger(__name__).warning(f"Update callback error: {e}", exc_info=True)

    async def load_all(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> LogGroupManagerResult:
        """
        Load all log groups from CloudWatch with full pagination.

        This method fetches ALL log groups without any limit, handling
        pagination automatically. Progress updates are provided via callback.

        Args:
            progress_callback: Optional callback for progress updates.
                              Called with (count, message) during loading.

        Returns:
            LogGroupManagerResult with success status and loaded groups

        Note:
            This method is safe to call multiple times - it will replace
            the existing list with fresh data.
        """
        start_time = time.monotonic()

        self._state = LogGroupManagerState.LOADING
        self._last_error = None

        if progress_callback:
            progress_callback(0, "Starting log group discovery...")

        try:
            all_groups: list[LogGroupInfo] = []

            # Use the datasource's internal sync method for full pagination
            # We need to bypass the limit parameter to get ALL groups
            loop = asyncio.get_event_loop()
            raw_groups = await loop.run_in_executor(
                None,
                self._fetch_all_log_groups_sync,
                progress_callback,
            )

            # Convert to LogGroupInfo objects
            for raw in raw_groups:
                all_groups.append(LogGroupInfo.from_dict(raw))

            # Update state
            self._log_groups = all_groups
            self._state = LogGroupManagerState.READY
            self._last_refresh = datetime.now(timezone.utc)

            duration_ms = int((time.monotonic() - start_time) * 1000)

            if progress_callback:
                progress_callback(len(all_groups), "Log group discovery complete")

            # Notify sidebar callbacks
            self._notify_update()

            return LogGroupManagerResult(
                success=True,
                log_groups=all_groups,
                count=len(all_groups),
                duration_ms=duration_ms,
            )

        except Exception as e:
            self._state = LogGroupManagerState.ERROR
            self._last_error = str(e)

            duration_ms = int((time.monotonic() - start_time) * 1000)

            return LogGroupManagerResult(
                success=False,
                error_message=str(e),
                duration_ms=duration_ms,
            )

    def _fetch_all_log_groups_sync(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> list[dict[str, Any]]:
        """
        Synchronous implementation that fetches ALL log groups.

        This bypasses the limit parameter in the datasource to get
        complete pagination.

        Note:
            This method runs in a thread pool executor, so progress callbacks
            are invoked using thread-safe mechanisms when an event loop is available.
        """
        paginator = self.datasource.client.get_paginator("describe_log_groups")
        log_groups: list[dict[str, Any]] = []

        # Get event loop for thread-safe callback invocation
        loop = None
        if progress_callback:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                pass  # No event loop in this thread

        for page in paginator.paginate():
            for lg in page["logGroups"]:
                log_groups.append(
                    {
                        "name": lg["logGroupName"],
                        "created": lg.get("creationTime"),
                        "stored_bytes": lg.get("storedBytes", 0),
                        "retention_days": lg.get("retentionInDays"),
                    }
                )

            # Thread-safe progress update after each page
            if progress_callback:
                message = f"Loading... ({len(log_groups)} found)"
                if loop and loop.is_running():
                    # Use thread-safe callback invocation when event loop is available
                    loop.call_soon_threadsafe(progress_callback, len(log_groups), message)
                else:
                    # Fallback for CLI usage where callback is simple (e.g., print)
                    progress_callback(len(log_groups), message)

        return log_groups

    async def refresh(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> LogGroupManagerResult:
        """
        Refresh the log groups list.

        This is an alias for load_all() - it performs a complete refresh
        of all log groups.

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            LogGroupManagerResult with refresh results
        """
        return await self.load_all(progress_callback=progress_callback)

    def format_for_prompt(self) -> str:
        """
        Format log groups for inclusion in LLM system prompt.

        Uses a tiered strategy based on the number of log groups:
        - Small lists (<=500): Include full list with names only
        - Large lists (>500): Include summary with sample and categories

        Returns:
            Formatted string for system prompt injection
        """
        if not self._log_groups:
            return self._format_empty_state()

        if len(self._log_groups) <= self.FULL_LIST_THRESHOLD:
            return self._format_full_list()
        else:
            return self._format_summary()

    def _format_empty_state(self) -> str:
        """Format message when no log groups are loaded."""
        if self._state == LogGroupManagerState.ERROR:
            return f"""## Log Groups Status

**Status:** Failed to load log groups at startup
**Error:** {self._last_error}

You should use the `list_log_groups` tool to discover available log groups.
"""
        elif self._state == LogGroupManagerState.UNINITIALIZED:
            return """## Log Groups Status

**Status:** Log groups not yet loaded

Use the `list_log_groups` tool to discover available log groups.
"""
        else:
            return """## Log Groups Status

**Status:** No log groups found in this AWS account/region

The AWS account appears to have no CloudWatch log groups, or you may not have 
permission to list them. Verify your AWS credentials and permissions.
"""

    def _format_full_list(self) -> str:
        """Format complete list of log groups for small accounts."""
        # Sort alphabetically for easier scanning
        sorted_groups = sorted(self._log_groups, key=lambda g: g.name)

        # Build the list - names only to save tokens
        group_list = "\n".join(f"- {g.name}" for g in sorted_groups)

        refresh_time = (
            self._last_refresh.strftime("%Y-%m-%d %H:%M:%S UTC")
            if self._last_refresh
            else "Unknown"
        )

        return f"""## Available Log Groups

**Total:** {len(self._log_groups)} log groups
**Last Updated:** {refresh_time}

{group_list}

### Usage Instructions
- Use these log group names directly when fetching or searching logs
- This list is your primary reference - no need to call `list_log_groups` unless user requests fresh lookup
- If a log group name doesn't match exactly, suggest the closest match from this list
- User can refresh this list with the `/refresh` command
"""

    def _format_summary(self) -> str:
        """Format summary for large accounts with many log groups."""
        # Categorize by common prefixes
        categories = self._categorize_log_groups()

        # Get a representative sample
        sample = self._get_representative_sample()

        refresh_time = (
            self._last_refresh.strftime("%Y-%m-%d %H:%M:%S UTC")
            if self._last_refresh
            else "Unknown"
        )

        # Build categories summary
        category_lines = []
        for prefix, count in sorted(categories.items(), key=lambda x: -x[1])[:15]:
            category_lines.append(f"- `{prefix}*`: {count} log groups")

        categories_text = "\n".join(category_lines)

        # Build sample list
        sample_text = "\n".join(f"- {g.name}" for g in sample)

        return f"""## Available Log Groups

**Total:** {len(self._log_groups)} log groups
**Last Updated:** {refresh_time}

### Log Group Categories
{categories_text}

### Sample Log Groups (showing {len(sample)} of {len(self._log_groups)})
{sample_text}

### Usage Instructions
- The full list of {len(self._log_groups)} log groups is available but too large to display
- Use the category prefixes above to understand what's available
- For specific lookups, use `list_log_groups` with a prefix filter
- Common prefixes: `/aws/lambda/`, `/aws/apigateway/`, `/ecs/`, `/aws/rds/`
- User can refresh this list with the `/refresh` command
- When user mentions a service, match it to the appropriate prefix category
"""

    def _categorize_log_groups(self) -> dict[str, int]:
        """Categorize log groups by common prefixes."""
        categories: dict[str, int] = {}

        # Common AWS prefixes to look for
        known_prefixes = [
            "/aws/lambda/",
            "/aws/apigateway/",
            "/aws/rds/",
            "/aws/eks/",
            "/ecs/",
            "/aws/elasticbeanstalk/",
            "/aws/codebuild/",
            "/aws/batch/",
            "/aws/kinesisfirehose/",
            "/aws/vendedlogs/",
        ]

        for group in self._log_groups:
            matched = False
            for prefix in known_prefixes:
                if group.name.startswith(prefix):
                    categories[prefix] = categories.get(prefix, 0) + 1
                    matched = True
                    break

            if not matched:
                # Try to extract a meaningful prefix
                parts = group.name.split("/")
                if len(parts) >= 3:
                    prefix = "/".join(parts[:3]) + "/"
                elif len(parts) >= 2:
                    prefix = "/".join(parts[:2]) + "/"
                else:
                    prefix = "(other)"
                categories[prefix] = categories.get(prefix, 0) + 1

        return categories

    def _get_representative_sample(self) -> list[LogGroupInfo]:
        """Get a representative sample of log groups for display."""
        if len(self._log_groups) <= self.SUMMARY_SAMPLE_SIZE:
            return sorted(self._log_groups, key=lambda g: g.name)

        # Get samples from each category to ensure diversity
        categories = self._categorize_log_groups()
        sample: list[LogGroupInfo] = []

        # Allocate samples proportionally to category size
        total = len(self._log_groups)
        for prefix, count in sorted(categories.items(), key=lambda x: -x[1]):
            # How many from this category?
            allocation = max(1, int(self.SUMMARY_SAMPLE_SIZE * count / total))

            # Get groups matching this prefix
            matching = [g for g in self._log_groups if g.name.startswith(prefix)]

            # Take first N (sorted)
            matching.sort(key=lambda g: g.name)
            sample.extend(matching[:allocation])

            if len(sample) >= self.SUMMARY_SAMPLE_SIZE:
                break

        # Sort final sample
        sample.sort(key=lambda g: g.name)
        return sample[: self.SUMMARY_SAMPLE_SIZE]

    def get_log_group_names(self) -> list[str]:
        """Get list of log group names only."""
        return [g.name for g in self._log_groups]

    def find_matching_groups(self, pattern: str) -> list[LogGroupInfo]:
        """
        Find log groups matching a pattern (prefix or substring).

        Args:
            pattern: Pattern to match (case-insensitive)

        Returns:
            List of matching LogGroupInfo objects
        """
        pattern_lower = pattern.lower()
        return [g for g in self._log_groups if pattern_lower in g.name.lower()]

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about loaded log groups."""
        if not self._log_groups:
            return {
                "count": 0,
                "state": self._state.value,
                "last_refresh": None,
                "total_bytes": 0,
                "categories": {},
            }

        return {
            "count": len(self._log_groups),
            "state": self._state.value,
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
            "total_bytes": sum(g.stored_bytes for g in self._log_groups),
            "categories": self._categorize_log_groups(),
        }
