"""CloudWatch-specific LLM tools."""

from typing import Any

from logai.cache.manager import CacheManager
from logai.config.settings import LogAISettings
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.base import BaseTool, ToolExecutionError
from logai.providers.datasources.cloudwatch import CloudWatchDataSource
from logai.utils.time import calculate_time_range


class ListLogGroupsTool(BaseTool):
    """
    Tool to list available CloudWatch log groups.

    Use this tool to discover what log groups exist before querying logs.
    """

    def __init__(
        self,
        datasource: CloudWatchDataSource,
        settings: LogAISettings,
        cache: CacheManager | None = None,
    ) -> None:
        """
        Initialize ListLogGroupsTool.

        Args:
            datasource: CloudWatch data source instance
            settings: Application settings
            cache: Optional cache manager
        """
        self.datasource = datasource
        self.settings = settings
        self.cache = cache

    @property
    def name(self) -> str:
        """Return tool name."""
        return "list_log_groups"

    @property
    def description(self) -> str:
        """Return tool description."""
        return (
            "List available CloudWatch log groups. Use this to discover what log groups "
            "exist before querying logs. You can optionally filter by prefix to narrow "
            "down results (e.g., '/aws/lambda/' to see only Lambda function logs)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        """Return parameter schema."""
        return {
            "type": "object",
            "properties": {
                "prefix": {
                    "type": "string",
                    "description": (
                        "Optional prefix to filter log groups (e.g., '/aws/lambda/', '/ecs/'). "
                        "Leave empty to list all log groups."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of log groups to return (default: 50, max: 100)",
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        Execute the list_log_groups tool.

        Args:
            **kwargs: Tool parameters (prefix, limit)

        Returns:
            Dictionary with log groups and metadata
        """
        prefix = kwargs.get("prefix")
        limit = kwargs.get("limit", 50)

        try:
            # Check cache first
            if self.cache:
                cached = await self.cache.get(
                    query_type="list_log_groups",
                    prefix=prefix,
                    limit=limit,
                )
                if cached:
                    return cached

            # Fetch from CloudWatch
            log_groups = await self.datasource.list_log_groups(prefix=prefix, limit=limit)

            result = {
                "success": True,
                "log_groups": log_groups,
                "count": len(log_groups),
                "prefix": prefix,
            }

            # Store in cache
            if self.cache:
                await self.cache.set(
                    query_type="list_log_groups",
                    payload=result,
                    prefix=prefix,
                    limit=limit,
                )

            return result
        except Exception as e:
            raise ToolExecutionError(
                message=f"Failed to list log groups: {str(e)}",
                tool_name=self.name,
                details={"prefix": prefix, "limit": limit},
            ) from e


class FetchLogsTool(BaseTool):
    """
    Tool to fetch log events from a specific CloudWatch log group.

    Fetches actual log data for analysis. Logs are sanitized to remove PII
    before being returned to the LLM.
    """

    def __init__(
        self,
        datasource: CloudWatchDataSource,
        sanitizer: LogSanitizer,
        settings: LogAISettings,
        cache: CacheManager | None = None,
    ) -> None:
        """
        Initialize FetchLogsTool.

        Args:
            datasource: CloudWatch data source instance
            sanitizer: PII sanitizer instance
            settings: Application settings
            cache: Optional cache manager
        """
        self.datasource = datasource
        self.sanitizer = sanitizer
        self.settings = settings
        self.cache = cache

    @property
    def name(self) -> str:
        """Return tool name."""
        return "fetch_logs"

    @property
    def description(self) -> str:
        """Return tool description."""
        return (
            "Fetch log events from a specific CloudWatch log group. Use this to retrieve "
            "actual log data for analysis. Supports time range filtering and CloudWatch "
            "filter patterns for searching specific content (e.g., 'ERROR', 'Exception')."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        """Return parameter schema."""
        return {
            "type": "object",
            "properties": {
                "log_group": {
                    "type": "string",
                    "description": "The CloudWatch log group name (e.g., '/aws/lambda/my-function')",
                },
                "start_time": {
                    "type": "string",
                    "description": (
                        "Start of time range. Supports ISO 8601 (2024-01-15T10:00:00Z), "
                        "relative ('1h ago', '30m ago', '2d ago', 'yesterday'), or epoch ms"
                    ),
                },
                "end_time": {
                    "type": "string",
                    "description": (
                        "End of time range. Same formats as start_time. Defaults to 'now' if not specified."
                    ),
                },
                "filter_pattern": {
                    "type": "string",
                    "description": (
                        "CloudWatch filter pattern to search for specific content. "
                        "Examples: 'ERROR', '\"Exception\"', '{ $.level = \"error\" }'"
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of log events to return (default: 100, max: 1000)",
                    "minimum": 1,
                    "maximum": 1000,
                },
            },
            "required": ["log_group", "start_time"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        Execute the fetch_logs tool.

        Args:
            **kwargs: Tool parameters (log_group, start_time, end_time, filter_pattern, limit)

        Returns:
            Dictionary with sanitized log events and metadata
        """
        log_group = kwargs.get("log_group")
        start_time_str = kwargs.get("start_time")
        end_time_str = kwargs.get("end_time")
        filter_pattern = kwargs.get("filter_pattern")
        limit = kwargs.get("limit", 100)

        if not log_group:
            raise ToolExecutionError(
                message="log_group parameter is required",
                tool_name=self.name,
                details={"provided_params": list(kwargs.keys())},
            )

        if not start_time_str:
            raise ToolExecutionError(
                message="start_time parameter is required",
                tool_name=self.name,
                details={"provided_params": list(kwargs.keys())},
            )

        try:
            # Parse time range
            start_time, end_time = calculate_time_range(start_time_str, end_time_str)

            # Check cache first
            if self.cache:
                cached = await self.cache.get(
                    query_type="fetch_logs",
                    log_group=log_group,
                    start_time=start_time,
                    end_time=end_time,
                    filter_pattern=filter_pattern,
                    limit=limit,
                )
                if cached:
                    return cached

            # Fetch logs from CloudWatch
            events = await self.datasource.fetch_logs(
                log_group=log_group,
                start_time=start_time,
                end_time=end_time,
                filter_pattern=filter_pattern,
                limit=limit,
            )

            # Sanitize logs before returning to LLM
            sanitized_events, redactions = self.sanitizer.sanitize_log_events(events)

            result = {
                "success": True,
                "log_group": log_group,
                "events": sanitized_events,
                "count": len(sanitized_events),
                "time_range": {
                    "start": start_time,
                    "end": end_time,
                },
                "filter_pattern": filter_pattern,
                "sanitization": {
                    "enabled": self.sanitizer.enabled,
                    "redactions": redactions,
                    "summary": self.sanitizer.get_redaction_summary(redactions),
                },
            }

            # Store in cache
            if self.cache:
                await self.cache.set(
                    query_type="fetch_logs",
                    payload=result,
                    log_group=log_group,
                    start_time=start_time,
                    end_time=end_time,
                    filter_pattern=filter_pattern,
                    limit=limit,
                )

            return result
        except Exception as e:
            raise ToolExecutionError(
                message=f"Failed to fetch logs: {str(e)}",
                tool_name=self.name,
                details={
                    "log_group": log_group,
                    "start_time": start_time_str,
                    "end_time": end_time_str,
                    "filter_pattern": filter_pattern,
                },
            ) from e


class SearchLogsTool(BaseTool):
    """
    Tool to search across multiple CloudWatch log groups.

    Use this for cross-service investigation when you need to find logs
    matching a pattern across multiple log groups.
    """

    def __init__(
        self,
        datasource: CloudWatchDataSource,
        sanitizer: LogSanitizer,
        settings: LogAISettings,
        cache: CacheManager | None = None,
    ) -> None:
        """
        Initialize SearchLogsTool.

        Args:
            datasource: CloudWatch data source instance
            sanitizer: PII sanitizer instance
            settings: Application settings
            cache: Optional cache manager
        """
        self.datasource = datasource
        self.sanitizer = sanitizer
        self.settings = settings
        self.cache = cache

    @property
    def name(self) -> str:
        """Return tool name."""
        return "search_logs"

    @property
    def description(self) -> str:
        """Return tool description."""
        return (
            "Search across multiple CloudWatch log groups for a pattern. Use this for "
            "cross-service investigation when you need to find logs matching a pattern "
            "across multiple services or applications."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        """Return parameter schema."""
        return {
            "type": "object",
            "properties": {
                "log_group_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of log group name patterns/prefixes to search. "
                        "Example: ['/aws/lambda/', '/ecs/'] to search all Lambda and ECS logs"
                    ),
                },
                "search_pattern": {
                    "type": "string",
                    "description": (
                        "CloudWatch filter pattern to search for across log groups. "
                        "Example: 'ERROR', 'timeout', '\"500\"'"
                    ),
                },
                "start_time": {
                    "type": "string",
                    "description": (
                        "Start of time range. Supports ISO 8601, relative ('1h ago'), or epoch ms"
                    ),
                },
                "end_time": {
                    "type": "string",
                    "description": "End of time range (defaults to 'now' if not specified)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum total number of log events to return (default: 100, max: 1000)",
                    "minimum": 1,
                    "maximum": 1000,
                },
            },
            "required": ["log_group_patterns", "search_pattern", "start_time"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        Execute the search_logs tool.

        Args:
            **kwargs: Tool parameters (log_group_patterns, search_pattern, start_time, end_time, limit)

        Returns:
            Dictionary with sanitized log events from all matching log groups
        """
        log_group_patterns = kwargs.get("log_group_patterns", [])
        search_pattern = kwargs.get("search_pattern")
        start_time_str = kwargs.get("start_time")
        end_time_str = kwargs.get("end_time")
        limit = kwargs.get("limit", 100)

        if not log_group_patterns:
            raise ToolExecutionError(
                message="log_group_patterns parameter is required and must not be empty",
                tool_name=self.name,
                details={"provided_params": list(kwargs.keys())},
            )

        if not search_pattern:
            raise ToolExecutionError(
                message="search_pattern parameter is required",
                tool_name=self.name,
                details={"provided_params": list(kwargs.keys())},
            )

        if not start_time_str:
            raise ToolExecutionError(
                message="start_time parameter is required",
                tool_name=self.name,
                details={"provided_params": list(kwargs.keys())},
            )

        try:
            # Parse time range
            start_time, end_time = calculate_time_range(start_time_str, end_time_str)

            # Check cache first
            if self.cache:
                # Convert list to tuple for cache key (lists aren't hashable)
                patterns_key = tuple(sorted(log_group_patterns))
                cached = await self.cache.get(
                    query_type="search_logs",
                    log_group_patterns=patterns_key,
                    search_pattern=search_pattern,
                    start_time=start_time,
                    end_time=end_time,
                    limit=limit,
                )
                if cached:
                    return cached

            # Search logs across multiple groups
            events = await self.datasource.search_logs(
                log_group_patterns=log_group_patterns,
                search_pattern=search_pattern,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )

            # Sanitize logs before returning to LLM
            sanitized_events, redactions = self.sanitizer.sanitize_log_events(events)

            # Group events by log group for better presentation
            events_by_group: dict[str, list[dict[str, Any]]] = {}
            for event in sanitized_events:
                log_stream = event.get("log_stream", "unknown")
                # Extract log group from log stream if possible
                # (log streams often contain log group info)
                group_key = event.get(
                    "log_group", log_stream.split("/")[0] if "/" in log_stream else "unknown"
                )
                if group_key not in events_by_group:
                    events_by_group[group_key] = []
                events_by_group[group_key].append(event)

            result = {
                "success": True,
                "log_group_patterns": log_group_patterns,
                "search_pattern": search_pattern,
                "events": sanitized_events,
                "events_by_group": events_by_group,
                "count": len(sanitized_events),
                "groups_found": len(events_by_group),
                "time_range": {
                    "start": start_time,
                    "end": end_time,
                },
                "sanitization": {
                    "enabled": self.sanitizer.enabled,
                    "redactions": redactions,
                    "summary": self.sanitizer.get_redaction_summary(redactions),
                },
            }

            # Store in cache
            if self.cache:
                patterns_key = tuple(sorted(log_group_patterns))
                await self.cache.set(
                    query_type="search_logs",
                    payload=result,
                    log_group_patterns=patterns_key,
                    search_pattern=search_pattern,
                    start_time=start_time,
                    end_time=end_time,
                    limit=limit,
                )

            return result
        except Exception as e:
            raise ToolExecutionError(
                message=f"Failed to search logs: {str(e)}",
                tool_name=self.name,
                details={
                    "log_group_patterns": log_group_patterns,
                    "search_pattern": search_pattern,
                    "start_time": start_time_str,
                    "end_time": end_time_str,
                },
            ) from e
