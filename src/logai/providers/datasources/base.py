"""Base abstract class for data source implementations."""

from abc import ABC, abstractmethod
from typing import Any


class BaseDataSource(ABC):
    """
    Abstract base class for observability data sources.

    All data source implementations (CloudWatch, Splunk, etc.) must inherit
    from this class and implement the required methods.
    """

    @abstractmethod
    async def list_log_groups(
        self, prefix: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        List available log groups.

        Args:
            prefix: Optional prefix to filter log groups
            limit: Maximum number of log groups to return

        Returns:
            List of log group dictionaries with keys:
            - name: Log group name
            - created: Creation timestamp (milliseconds)
            - stored_bytes: Size in bytes
            - retention_days: Retention period in days (optional)

        Raises:
            DataSourceError: If the operation fails
        """
        pass

    @abstractmethod
    async def fetch_logs(
        self,
        log_group: str,
        start_time: int,
        end_time: int,
        filter_pattern: str | None = None,
        limit: int = 1000,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        Fetch log events from a specific log group.

        Args:
            log_group: Name of the log group
            start_time: Start time (epoch milliseconds)
            end_time: End time (epoch milliseconds)
            filter_pattern: Optional filter pattern (data source specific)
            limit: Maximum number of log events to return
            **kwargs: Additional data source-specific parameters

        Returns:
            List of log event dictionaries with keys:
            - timestamp: Event timestamp (milliseconds)
            - message: Log message
            - log_stream: Log stream name
            - Additional fields may be data source specific

        Raises:
            DataSourceError: If the operation fails
            LogGroupNotFoundError: If the log group doesn't exist
        """
        pass

    @abstractmethod
    async def search_logs(
        self,
        log_group_patterns: list[str],
        search_pattern: str,
        start_time: int,
        end_time: int,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Search for logs across multiple log groups.

        Args:
            log_group_patterns: List of log group name patterns to search
            search_pattern: Search pattern (data source specific)
            start_time: Start time (epoch milliseconds)
            end_time: End time (epoch milliseconds)
            limit: Maximum number of log events to return

        Returns:
            List of log event dictionaries (same format as fetch_logs)

        Raises:
            DataSourceError: If the operation fails
        """
        pass


class DataSourceError(Exception):
    """Base exception for data source errors."""

    pass


class LogGroupNotFoundError(DataSourceError):
    """Raised when a log group is not found."""

    pass


class RateLimitError(DataSourceError):
    """Raised when rate limits are exceeded."""

    pass


class AuthenticationError(DataSourceError):
    """Raised when authentication fails."""

    pass
