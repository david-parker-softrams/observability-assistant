"""Tool for fetching chunks of cached large results."""

import logging
from typing import Any

from logai.core.context.result_cache import ResultCacheManager
from logai.core.tools.base import BaseTool, ToolExecutionError

logger = logging.getLogger(__name__)


class FetchCachedResultTool(BaseTool):
    """
    Tool to fetch chunks of previously cached large query results.

    When a CloudWatch query returns too many results for the context window,
    the results are cached and a summary is provided. This tool allows the
    agent to retrieve specific chunks of those cached results.
    """

    def __init__(self, result_cache: ResultCacheManager) -> None:
        """
        Initialize FetchCachedResultTool.

        Args:
            result_cache: Result cache manager instance
        """
        self.result_cache = result_cache

    @property
    def name(self) -> str:
        """Return tool name."""
        return "fetch_cached_result_chunk"

    @property
    def description(self) -> str:
        """Return tool description."""
        return (
            "Fetch a specific chunk of a previously cached large query result. "
            "Use this when you need to access specific log events from a result "
            "that was too large to fit in context. The cache_id is provided in "
            "the cached result summary. You can filter by text pattern or time range."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        """Return parameter schema."""
        return {
            "type": "object",
            "properties": {
                "cache_id": {
                    "type": "string",
                    "description": "The cache ID from the cached result summary (e.g., 'result_abc123')",
                },
                "offset": {
                    "type": "integer",
                    "description": "Starting index for pagination (0-based, default: 0)",
                    "minimum": 0,
                    "default": 0,
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of events to fetch (default: 100, max: 200)",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 100,
                },
                "filter_pattern": {
                    "type": "string",
                    "description": (
                        "Optional text pattern to filter events (case-insensitive). "
                        "Example: 'ERROR' to find only error messages."
                    ),
                },
                "time_start": {
                    "type": "integer",
                    "description": "Optional start timestamp (epoch milliseconds) to filter events",
                },
                "time_end": {
                    "type": "integer",
                    "description": "Optional end timestamp (epoch milliseconds) to filter events",
                },
            },
            "required": ["cache_id"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        Execute the fetch_cached_result_chunk tool.

        Args:
            **kwargs: Tool parameters

        Returns:
            Dictionary with events and metadata

        Raises:
            ToolExecutionError: If execution fails
        """
        cache_id = kwargs.get("cache_id")

        if not cache_id:
            raise ToolExecutionError(
                message="cache_id parameter is required",
                tool_name=self.name,
                details={"provided_params": list(kwargs.keys())},
            )

        offset = kwargs.get("offset", 0)
        limit = kwargs.get("limit", 100)
        filter_pattern = kwargs.get("filter_pattern")
        time_start = kwargs.get("time_start")
        time_end = kwargs.get("time_end")

        logger.debug(
            f"Tool: fetch_cached_result_chunk called with cache_id={cache_id}, "
            f"offset={offset}, limit={limit}"
        )

        try:
            result = await self.result_cache.fetch_chunk(
                cache_id=cache_id,
                offset=offset,
                limit=limit,
                filter_pattern=filter_pattern,
                time_start=time_start,
                time_end=time_end,
            )

            # Log the result status
            if not result.get("success", False):
                reason = result.get("error", "unknown")
                logger.warning(f"Tool: fetch failed for cache_id={cache_id}, reason: {reason}")
            else:
                logger.debug(
                    f"Tool: fetch succeeded for cache_id={cache_id}, "
                    f"returned {result.get('count', 0)} events"
                )

            return result

        except Exception as e:
            raise ToolExecutionError(
                message=f"Failed to fetch cached result: {str(e)}",
                tool_name=self.name,
                details={
                    "cache_id": cache_id,
                    "offset": offset,
                    "limit": limit,
                },
            ) from e
