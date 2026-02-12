"""Time parsing and conversion utilities for CloudWatch timestamps."""

import re
from datetime import UTC, datetime, timedelta

import pendulum
from dateutil import parser as dateutil_parser


class TimeParseError(Exception):
    """Raised when time parsing fails."""

    pass


def parse_relative_time(relative_str: str) -> datetime:
    """
    Parse relative time strings like '1h ago', '30m ago', '2d ago'.

    Supported formats:
    - '1h ago', '2h ago' - hours ago
    - '30m ago', '45m ago' - minutes ago
    - '1d ago', '2d ago' - days ago
    - '1w ago' - weeks ago
    - 'now' - current time
    - 'yesterday' - 24 hours ago

    Args:
        relative_str: Relative time string

    Returns:
        datetime object in UTC

    Raises:
        TimeParseError: If the format is not recognized
    """
    # Get current time once at the start for consistency
    now = datetime.now(UTC)

    relative_str = relative_str.strip().lower()

    # Handle special cases
    if relative_str == "now":
        return now

    if relative_str == "yesterday":
        return now - timedelta(days=1)

    # Parse relative time pattern: "5m ago", "2h ago", "1d ago", "1w ago"
    pattern = r"^(\d+)\s*([mhdw])\s*ago$"
    match = re.match(pattern, relative_str)

    if not match:
        raise TimeParseError(
            f"Invalid relative time format: '{relative_str}'. "
            "Expected formats: '1h ago', '30m ago', '2d ago', 'yesterday', 'now'"
        )

    amount = int(match.group(1))
    unit = match.group(2)

    if unit == "m":
        return now - timedelta(minutes=amount)
    elif unit == "h":
        return now - timedelta(hours=amount)
    elif unit == "d":
        return now - timedelta(days=amount)
    elif unit == "w":
        return now - timedelta(weeks=amount)
    else:
        raise TimeParseError(f"Unknown time unit: {unit}")


def parse_iso8601(iso_str: str) -> datetime:
    """
    Parse ISO 8601 timestamp string.

    Supports various ISO 8601 formats:
    - 2024-01-15T10:00:00Z
    - 2024-01-15T10:00:00+00:00
    - 2024-01-15T10:00:00.123Z
    - 2024-01-15 10:00:00

    Args:
        iso_str: ISO 8601 timestamp string

    Returns:
        datetime object in UTC

    Raises:
        TimeParseError: If parsing fails
    """
    try:
        # Try pendulum first (better ISO 8601 support)
        dt = pendulum.parse(iso_str)
        if dt is None:
            raise TimeParseError(f"Failed to parse ISO 8601 timestamp: {iso_str}")

        # Convert to standard datetime in UTC
        # pendulum returns a DateTime object, convert to standard datetime
        if isinstance(dt, pendulum.DateTime):
            # Convert pendulum DateTime to stdlib datetime in UTC
            # Use timestamp() to get a consistent conversion
            return datetime.fromtimestamp(dt.timestamp(), tz=UTC)
        # Handle cases where pendulum returns Date or Time objects
        raise TimeParseError(f"Unexpected pendulum parse result type for: {iso_str}")
    except Exception as e:
        # Fallback to dateutil parser
        try:
            parsed_dt = dateutil_parser.parse(iso_str)
            # Ensure UTC timezone
            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=UTC)
            else:
                parsed_dt = parsed_dt.astimezone(UTC)
            return parsed_dt
        except Exception:
            raise TimeParseError(f"Failed to parse ISO 8601 timestamp: {iso_str}") from e


def parse_epoch_milliseconds(epoch_ms: int | str) -> datetime:
    """
    Parse epoch milliseconds to datetime.

    Args:
        epoch_ms: Epoch milliseconds (int or string)

    Returns:
        datetime object in UTC

    Raises:
        TimeParseError: If parsing fails
    """
    try:
        ms = int(epoch_ms) if isinstance(epoch_ms, str) else epoch_ms
        # CloudWatch uses milliseconds
        return datetime.fromtimestamp(ms / 1000.0, tz=UTC)
    except (ValueError, OSError) as e:
        raise TimeParseError(f"Failed to parse epoch milliseconds: {epoch_ms}") from e


def parse_time(time_str: str | int | datetime) -> datetime:
    """
    Parse time string in various formats to datetime.

    Supports:
    - Relative times: "1h ago", "30m ago", "2d ago", "yesterday", "now"
    - ISO 8601: "2024-01-15T10:00:00Z"
    - Epoch milliseconds: 1705314000000 (int or str)
    - datetime objects (returned as-is, ensured to be UTC)

    Args:
        time_str: Time in various formats

    Returns:
        datetime object in UTC

    Raises:
        TimeParseError: If parsing fails
    """
    # Already a datetime
    if isinstance(time_str, datetime):
        # Ensure UTC timezone
        if time_str.tzinfo is None:
            return time_str.replace(tzinfo=UTC)
        return time_str.astimezone(UTC)

    # Try epoch milliseconds (int)
    if isinstance(time_str, int):
        return parse_epoch_milliseconds(time_str)

    # String parsing
    time_str = time_str.strip()

    # Try relative time first (most common for log queries)
    if "ago" in time_str.lower() or time_str.lower() in ("now", "yesterday"):
        return parse_relative_time(time_str)

    # Try epoch milliseconds (string of digits)
    if time_str.isdigit():
        return parse_epoch_milliseconds(time_str)

    # Try ISO 8601
    return parse_iso8601(time_str)


def to_cloudwatch_timestamp(dt: datetime | str | int) -> int:
    """
    Convert datetime to CloudWatch timestamp (epoch milliseconds).

    Args:
        dt: datetime object, time string, or epoch milliseconds

    Returns:
        Epoch milliseconds (int)

    Raises:
        TimeParseError: If conversion fails
    """
    if isinstance(dt, int):
        # Assume already in milliseconds if > 10^10 (year 2286)
        if dt > 10_000_000_000:
            return dt
        # Otherwise assume seconds, convert to milliseconds
        return dt * 1000

    # Parse to datetime if string
    if isinstance(dt, str):
        dt = parse_time(dt)

    # Convert datetime to milliseconds
    return int(dt.timestamp() * 1000)


def calculate_time_range(
    start_time: str | int | datetime | None = None,
    end_time: str | int | datetime | None = None,
    default_range_minutes: int = 60,
) -> tuple[int, int]:
    """
    Calculate start and end timestamps for CloudWatch queries.

    If start_time is None, defaults to default_range_minutes ago.
    If end_time is None, defaults to now.

    Args:
        start_time: Start time in various formats
        end_time: End time in various formats
        default_range_minutes: Default time range in minutes if start_time is None

    Returns:
        Tuple of (start_timestamp_ms, end_timestamp_ms)

    Raises:
        TimeParseError: If parsing fails
        ValueError: If start_time is after end_time
    """
    # Calculate end time (defaults to now)
    if end_time is None:
        end_dt = datetime.now(UTC)
    else:
        end_dt = parse_time(end_time)

    # Calculate start time (defaults to default_range_minutes ago)
    if start_time is None:
        start_dt = end_dt - timedelta(minutes=default_range_minutes)
    else:
        start_dt = parse_time(start_time)

    # Validate time range
    if start_dt > end_dt:
        raise ValueError(
            f"Start time ({start_dt.isoformat()}) cannot be after end time ({end_dt.isoformat()})"
        )

    return to_cloudwatch_timestamp(start_dt), to_cloudwatch_timestamp(end_dt)


def format_timestamp(timestamp_ms: int, format_str: str = "%Y-%m-%d %H:%M:%S UTC") -> str:
    """
    Format CloudWatch timestamp (epoch milliseconds) to human-readable string.

    Args:
        timestamp_ms: Epoch milliseconds
        format_str: strftime format string

    Returns:
        Formatted timestamp string
    """
    dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=UTC)
    return dt.strftime(format_str)


def time_ago(timestamp_ms: int) -> str:
    """
    Convert timestamp to human-readable 'time ago' format.

    Examples:
    - "2 minutes ago"
    - "1 hour ago"
    - "3 days ago"

    Args:
        timestamp_ms: Epoch milliseconds

    Returns:
        Human-readable time ago string
    """
    dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=UTC)
    now = datetime.now(UTC)
    delta = now - dt

    seconds = int(delta.total_seconds())

    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''} ago"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    days = hours // 24
    if days < 7:
        return f"{days} day{'s' if days != 1 else ''} ago"

    weeks = days // 7
    if weeks < 4:
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"

    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"

    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"
