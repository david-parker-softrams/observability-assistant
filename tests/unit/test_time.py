"""Tests for time parsing and conversion utilities."""

from datetime import datetime, timedelta, timezone

import pytest

from logai.utils import (
    TimeParseError,
    calculate_time_range,
    format_timestamp,
    parse_epoch_milliseconds,
    parse_iso8601,
    parse_relative_time,
    parse_time,
    time_ago,
    to_cloudwatch_timestamp,
)


class TestParseRelativeTime:
    """Test suite for parse_relative_time function."""

    def test_parse_now(self) -> None:
        """Test parsing 'now'."""
        result = parse_relative_time("now")
        now = datetime.now(timezone.utc)

        # Should be within 1 second of current time
        assert abs((result - now).total_seconds()) < 1

    def test_parse_yesterday(self) -> None:
        """Test parsing 'yesterday'."""
        result = parse_relative_time("yesterday")
        expected = datetime.now(timezone.utc) - timedelta(days=1)

        # Should be within 1 second
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_minutes_ago(self) -> None:
        """Test parsing minutes ago."""
        result = parse_relative_time("30m ago")
        expected = datetime.now(timezone.utc) - timedelta(minutes=30)

        assert abs((result - expected).total_seconds()) < 1

    def test_parse_hours_ago(self) -> None:
        """Test parsing hours ago."""
        result = parse_relative_time("2h ago")
        expected = datetime.now(timezone.utc) - timedelta(hours=2)

        assert abs((result - expected).total_seconds()) < 1

    def test_parse_days_ago(self) -> None:
        """Test parsing days ago."""
        result = parse_relative_time("3d ago")
        expected = datetime.now(timezone.utc) - timedelta(days=3)

        assert abs((result - expected).total_seconds()) < 1

    def test_parse_weeks_ago(self) -> None:
        """Test parsing weeks ago."""
        result = parse_relative_time("1w ago")
        expected = datetime.now(timezone.utc) - timedelta(weeks=1)

        assert abs((result - expected).total_seconds()) < 1

    def test_parse_with_whitespace(self) -> None:
        """Test parsing with extra whitespace."""
        result = parse_relative_time("  5m  ago  ")
        expected = datetime.now(timezone.utc) - timedelta(minutes=5)

        assert abs((result - expected).total_seconds()) < 1

    def test_parse_invalid_format(self) -> None:
        """Test parsing invalid format."""
        with pytest.raises(TimeParseError, match="Invalid relative time format"):
            parse_relative_time("5 minutes ago")

        with pytest.raises(TimeParseError, match="Invalid relative time format"):
            parse_relative_time("tomorrow")

        with pytest.raises(TimeParseError, match="Invalid relative time format"):
            parse_relative_time("ago")


class TestParseISO8601:
    """Test suite for parse_iso8601 function."""

    def test_parse_iso8601_with_z(self) -> None:
        """Test parsing ISO 8601 with Z suffix."""
        result = parse_iso8601("2024-01-15T10:30:00Z")

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 0
        # Check it's UTC (pendulum may use its own timezone class)
        assert result.utcoffset() == timezone.utc.utcoffset(None)

    def test_parse_iso8601_with_timezone(self) -> None:
        """Test parsing ISO 8601 with timezone offset."""
        result = parse_iso8601("2024-01-15T10:30:00+00:00")

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        # Check it's UTC
        assert result.utcoffset() == timezone.utc.utcoffset(None)

    def test_parse_iso8601_with_milliseconds(self) -> None:
        """Test parsing ISO 8601 with milliseconds."""
        result = parse_iso8601("2024-01-15T10:30:00.123Z")

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 0
        assert result.microsecond == 123000

    def test_parse_iso8601_space_separator(self) -> None:
        """Test parsing ISO 8601 with space instead of T."""
        result = parse_iso8601("2024-01-15 10:30:00")

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10

    def test_parse_iso8601_invalid(self) -> None:
        """Test parsing invalid ISO 8601."""
        with pytest.raises(TimeParseError):
            parse_iso8601("not-a-date")

        with pytest.raises(TimeParseError):
            parse_iso8601("2024-13-45")  # Invalid month/day


class TestParseEpochMilliseconds:
    """Test suite for parse_epoch_milliseconds function."""

    def test_parse_epoch_milliseconds_int(self) -> None:
        """Test parsing epoch milliseconds as int."""
        # 2024-01-15 10:00:00 UTC = 1705312800000
        epoch_ms = 1705312800000
        result = parse_epoch_milliseconds(epoch_ms)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 0
        assert result.second == 0
        assert result.tzinfo == timezone.utc

    def test_parse_epoch_milliseconds_string(self) -> None:
        """Test parsing epoch milliseconds as string."""
        result = parse_epoch_milliseconds("1705312800000")

        assert result.year == 2024
        assert result.month == 1

    def test_parse_epoch_milliseconds_invalid(self) -> None:
        """Test parsing invalid epoch milliseconds."""
        with pytest.raises(TimeParseError):
            parse_epoch_milliseconds("not-a-number")


class TestParseTime:
    """Test suite for parse_time function."""

    def test_parse_time_datetime(self) -> None:
        """Test parsing datetime object."""
        dt = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        result = parse_time(dt)

        assert result == dt

    def test_parse_time_datetime_no_tz(self) -> None:
        """Test parsing datetime without timezone."""
        dt = datetime(2024, 1, 15, 10, 0, 0)
        result = parse_time(dt)

        assert result.tzinfo == timezone.utc
        assert result.year == 2024
        assert result.month == 1

    def test_parse_time_int(self) -> None:
        """Test parsing int (epoch milliseconds)."""
        result = parse_time(1705312800000)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_time_relative(self) -> None:
        """Test parsing relative time string."""
        result = parse_time("1h ago")
        expected = datetime.now(timezone.utc) - timedelta(hours=1)

        assert abs((result - expected).total_seconds()) < 1

    def test_parse_time_epoch_string(self) -> None:
        """Test parsing epoch milliseconds string."""
        result = parse_time("1705312800000")

        assert result.year == 2024
        assert result.month == 1

    def test_parse_time_iso8601(self) -> None:
        """Test parsing ISO 8601 string."""
        result = parse_time("2024-01-15T10:00:00Z")

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10


class TestToCloudWatchTimestamp:
    """Test suite for to_cloudwatch_timestamp function."""

    def test_to_cloudwatch_timestamp_datetime(self) -> None:
        """Test converting datetime to CloudWatch timestamp."""
        dt = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        result = to_cloudwatch_timestamp(dt)

        assert result == 1705312800000

    def test_to_cloudwatch_timestamp_int_milliseconds(self) -> None:
        """Test converting int (already in milliseconds)."""
        # Large number (already in milliseconds)
        result = to_cloudwatch_timestamp(1705312800000)

        assert result == 1705312800000

    def test_to_cloudwatch_timestamp_int_seconds(self) -> None:
        """Test converting int (in seconds)."""
        # Small number (in seconds)
        result = to_cloudwatch_timestamp(1705312800)

        assert result == 1705312800000

    def test_to_cloudwatch_timestamp_string(self) -> None:
        """Test converting string."""
        result = to_cloudwatch_timestamp("2024-01-15T10:00:00Z")

        assert result == 1705312800000


class TestCalculateTimeRange:
    """Test suite for calculate_time_range function."""

    def test_calculate_time_range_both_provided(self) -> None:
        """Test with both start and end times provided."""
        start, end = calculate_time_range(
            start_time="2024-01-15T10:00:00Z", end_time="2024-01-15T11:00:00Z"
        )

        assert start == 1705312800000
        assert end == 1705316400000

    def test_calculate_time_range_only_start(self) -> None:
        """Test with only start time (end defaults to now)."""
        start, end = calculate_time_range(start_time="1h ago")

        now = datetime.now(timezone.utc)
        expected_start = now - timedelta(hours=1)

        # Should be close to expected (within 1 second)
        assert abs(start - to_cloudwatch_timestamp(expected_start)) < 1000
        assert abs(end - to_cloudwatch_timestamp(now)) < 1000

    def test_calculate_time_range_only_end(self) -> None:
        """Test with only end time (start defaults to 1 hour before end)."""
        start, end = calculate_time_range(end_time="2024-01-15T11:00:00Z")

        assert end == 1705316400000
        # Start should be 60 minutes (default) before end
        assert start == 1705316400000 - (60 * 60 * 1000)

    def test_calculate_time_range_defaults(self) -> None:
        """Test with no times provided (defaults to last hour)."""
        start, end = calculate_time_range()

        now = datetime.now(timezone.utc)
        expected_start = now - timedelta(minutes=60)

        # Should be close to expected
        assert abs(start - to_cloudwatch_timestamp(expected_start)) < 1000
        assert abs(end - to_cloudwatch_timestamp(now)) < 1000

    def test_calculate_time_range_custom_default(self) -> None:
        """Test with custom default range."""
        start, end = calculate_time_range(default_range_minutes=30)

        now = datetime.now(timezone.utc)
        expected_start = now - timedelta(minutes=30)

        assert abs(start - to_cloudwatch_timestamp(expected_start)) < 1000

    def test_calculate_time_range_invalid_order(self) -> None:
        """Test with start time after end time."""
        with pytest.raises(ValueError, match="Start time .* cannot be after end time"):
            calculate_time_range(start_time="2024-01-15T11:00:00Z", end_time="2024-01-15T10:00:00Z")


class TestFormatTimestamp:
    """Test suite for format_timestamp function."""

    def test_format_timestamp_default(self) -> None:
        """Test formatting with default format."""
        result = format_timestamp(1705312800000)

        assert result == "2024-01-15 10:00:00 UTC"

    def test_format_timestamp_custom(self) -> None:
        """Test formatting with custom format."""
        result = format_timestamp(1705312800000, format_str="%Y-%m-%d %H:%M")

        assert result == "2024-01-15 10:00"


class TestTimeAgo:
    """Test suite for time_ago function."""

    def test_time_ago_seconds(self) -> None:
        """Test time ago for seconds."""
        now = datetime.now(timezone.utc)
        timestamp = to_cloudwatch_timestamp(now - timedelta(seconds=30))

        result = time_ago(timestamp)

        assert "30 seconds ago" in result or "31 seconds ago" in result

    def test_time_ago_minutes(self) -> None:
        """Test time ago for minutes."""
        now = datetime.now(timezone.utc)
        timestamp = to_cloudwatch_timestamp(now - timedelta(minutes=5))

        result = time_ago(timestamp)

        assert "5 minutes ago" in result or "6 minutes ago" in result

    def test_time_ago_hours(self) -> None:
        """Test time ago for hours."""
        now = datetime.now(timezone.utc)
        timestamp = to_cloudwatch_timestamp(now - timedelta(hours=3))

        result = time_ago(timestamp)

        assert "3 hours ago" in result or "2 hours ago" in result

    def test_time_ago_days(self) -> None:
        """Test time ago for days."""
        now = datetime.now(timezone.utc)
        timestamp = to_cloudwatch_timestamp(now - timedelta(days=2))

        result = time_ago(timestamp)

        assert "2 days ago" in result or "1 day ago" in result

    def test_time_ago_singular(self) -> None:
        """Test singular forms."""
        now = datetime.now(timezone.utc)

        # 1 second ago
        timestamp = to_cloudwatch_timestamp(now - timedelta(seconds=1))
        result = time_ago(timestamp)
        assert "1 second ago" in result

        # 1 minute ago
        timestamp = to_cloudwatch_timestamp(now - timedelta(minutes=1))
        result = time_ago(timestamp)
        assert "1 minute ago" in result
