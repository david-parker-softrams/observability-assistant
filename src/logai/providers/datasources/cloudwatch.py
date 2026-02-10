"""AWS CloudWatch Logs data source implementation."""

import asyncio
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from logai.config.settings import LogAISettings

from .base import (
    AuthenticationError,
    BaseDataSource,
    DataSourceError,
    LogGroupNotFoundError,
    RateLimitError,
)


class CloudWatchDataSource(BaseDataSource):
    """
    AWS CloudWatch Logs data source implementation.

    Uses boto3 to interact with CloudWatch Logs API. Supports pagination,
    retry logic, and comprehensive error handling.
    """

    def __init__(self, settings: LogAISettings) -> None:
        """
        Initialize CloudWatch data source.

        Args:
            settings: Application settings with AWS credentials
        """
        self.settings = settings

        # Configure boto3 with retry and timeout settings
        self.config = Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=5,
            read_timeout=30,
        )

        # Create CloudWatch Logs client
        # boto3 will use standard credential chain:
        # 1. Explicit credentials (if provided)
        # 2. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        # 3. Shared credential file (~/.aws/credentials)
        # 4. AWS config file (~/.aws/config)
        # 5. IAM role (if running on EC2/ECS/Lambda)
        client_kwargs: dict[str, Any] = {
            "service_name": "logs",
            "region_name": settings.aws_region,
            "config": self.config,
        }

        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        if settings.aws_profile:
            # Use a session with profile
            session = boto3.Session(profile_name=settings.aws_profile)
            self.client = session.client(**client_kwargs)
        else:
            self.client = boto3.client(**client_kwargs)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RateLimitError),
    )
    async def list_log_groups(
        self, prefix: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        List available CloudWatch log groups.

        Args:
            prefix: Optional prefix to filter log groups (e.g., '/aws/lambda/')
            limit: Maximum number of log groups to return (default: 50)

        Returns:
            List of log group dictionaries

        Raises:
            DataSourceError: If the operation fails
            RateLimitError: If rate limits are exceeded
        """
        try:
            # Run boto3 call in executor (it's synchronous)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._list_log_groups_sync, prefix, limit)
            return result
        except RateLimitError:
            raise  # Re-raise for retry
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]

            if error_code == "ThrottlingException":
                raise RateLimitError(f"CloudWatch rate limit exceeded: {error_message}")
            elif error_code == "AccessDeniedException":
                raise AuthenticationError(
                    f"Access denied to CloudWatch Logs: {error_message}. "
                    "Check your AWS credentials and IAM permissions."
                )
            else:
                raise DataSourceError(
                    f"Failed to list log groups: {error_code} - {error_message}"
                ) from e
        except Exception as e:
            raise DataSourceError(f"Failed to list log groups: {str(e)}") from e

    def _list_log_groups_sync(self, prefix: str | None, limit: int) -> list[dict[str, Any]]:
        """Synchronous implementation of list_log_groups for executor."""
        paginator = self.client.get_paginator("describe_log_groups")
        params: dict[str, Any] = {}

        if prefix:
            params["logGroupNamePrefix"] = prefix

        log_groups: list[dict[str, Any]] = []

        for page in paginator.paginate(**params):
            for lg in page["logGroups"]:
                log_groups.append(
                    {
                        "name": lg["logGroupName"],
                        "created": lg.get("creationTime"),
                        "stored_bytes": lg.get("storedBytes", 0),
                        "retention_days": lg.get("retentionInDays"),
                    }
                )
                if len(log_groups) >= limit:
                    return log_groups

        return log_groups

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RateLimitError),
    )
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
        Fetch log events from CloudWatch.

        Warning:
            Logs may contain PII (Personally Identifiable Information).
            Use PII sanitization layer before sending to LLM (Phase 3 integration).

        Args:
            log_group: CloudWatch log group name (e.g., '/aws/lambda/my-function')
            start_time: Start time in epoch milliseconds
            end_time: End time in epoch milliseconds
            filter_pattern: Optional CloudWatch filter pattern
            limit: Maximum number of log events to return (max: 10000)
            **kwargs: Additional parameters:
                - log_stream_prefix: Filter to specific log stream prefix

        Returns:
            List of log event dictionaries

        Raises:
            LogGroupNotFoundError: If the log group doesn't exist
            RateLimitError: If rate limits are exceeded
            DataSourceError: If the operation fails
        """
        try:
            # Run boto3 call in executor (it's synchronous)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._fetch_logs_sync,
                log_group,
                start_time,
                end_time,
                filter_pattern,
                limit,
                kwargs,
            )
            return result
        except (LogGroupNotFoundError, RateLimitError):
            raise  # Re-raise these for retry/handling
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]

            if error_code == "ResourceNotFoundException":
                raise LogGroupNotFoundError(f"Log group not found: {log_group}")
            elif error_code == "ThrottlingException":
                raise RateLimitError(f"CloudWatch rate limit exceeded: {error_message}")
            elif error_code == "AccessDeniedException":
                raise AuthenticationError(
                    f"Access denied to log group '{log_group}': {error_message}"
                )
            elif error_code == "InvalidParameterException":
                raise DataSourceError(
                    f"Invalid parameter: {error_message}. Check your filter pattern syntax."
                ) from e
            else:
                raise DataSourceError(
                    f"Failed to fetch logs: {error_code} - {error_message}"
                ) from e
        except Exception as e:
            raise DataSourceError(f"Failed to fetch logs: {str(e)}") from e

    def _fetch_logs_sync(
        self,
        log_group: str,
        start_time: int,
        end_time: int,
        filter_pattern: str | None,
        limit: int,
        kwargs: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Synchronous implementation of fetch_logs for executor."""
        params: dict[str, Any] = {
            "logGroupName": log_group,
            "startTime": start_time,
            "endTime": end_time,
            "limit": min(limit, 10000),  # CloudWatch API max per request
        }

        if filter_pattern:
            params["filterPattern"] = filter_pattern

        if "log_stream_prefix" in kwargs and kwargs["log_stream_prefix"]:
            params["logStreamNamePrefix"] = kwargs["log_stream_prefix"]

        events: list[dict[str, Any]] = []
        paginator = self.client.get_paginator("filter_log_events")

        for page in paginator.paginate(**params):
            for event in page.get("events", []):
                events.append(
                    {
                        "timestamp": event["timestamp"],
                        "message": event["message"],
                        "log_stream": event["logStreamName"],
                        "event_id": event.get("eventId"),
                    }
                )
                if len(events) >= limit:
                    return events

        return events

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RateLimitError),
    )
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

        This method searches multiple log groups matching the given patterns
        and aggregates results.

        Warning:
            Logs may contain PII (Personally Identifiable Information).
            Use PII sanitization layer before sending to LLM (Phase 3 integration).

        Args:
            log_group_patterns: List of log group name patterns/prefixes
            search_pattern: CloudWatch filter pattern to search for
            start_time: Start time in epoch milliseconds
            end_time: End time in epoch milliseconds
            limit: Maximum total number of log events to return

        Returns:
            List of log event dictionaries from all matching log groups

        Raises:
            RateLimitError: If rate limits are exceeded
            DataSourceError: If the operation fails
        """
        try:
            # First, get all log groups matching the patterns
            all_log_groups: list[str] = []
            for pattern in log_group_patterns:
                groups = await self.list_log_groups(prefix=pattern, limit=100)
                all_log_groups.extend([g["name"] for g in groups])

            if not all_log_groups:
                return []

            # Search each log group and aggregate results
            all_events: list[dict[str, Any]] = []
            per_group_limit = max(
                limit // len(all_log_groups), 10
            )  # Distribute limit across groups

            for log_group in all_log_groups:
                try:
                    events = await self.fetch_logs(
                        log_group=log_group,
                        start_time=start_time,
                        end_time=end_time,
                        filter_pattern=search_pattern,
                        limit=per_group_limit,
                    )
                    all_events.extend(events)

                    if len(all_events) >= limit:
                        break
                except LogGroupNotFoundError:
                    # Log group might have been deleted, skip it
                    continue

            # Sort by timestamp (most recent first) and limit
            all_events.sort(key=lambda e: e["timestamp"], reverse=True)
            return all_events[:limit]

        except RateLimitError:
            raise  # Re-raise for retry
        except Exception as e:
            raise DataSourceError(f"Failed to search logs: {str(e)}") from e

    async def test_connection(self) -> bool:
        """
        Test connection to CloudWatch by attempting to list log groups.

        Returns:
            True if connection is successful

        Raises:
            AuthenticationError: If authentication fails
            DataSourceError: If connection test fails
        """
        try:
            # Try to list log groups (limit to 1 for quick test)
            await self.list_log_groups(limit=1)
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            raise DataSourceError(f"Connection test failed: {str(e)}") from e
