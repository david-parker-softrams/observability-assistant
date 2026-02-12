"""Tests for metrics collection."""

import time

import pytest

from logai.core.metrics import MetricType, MetricsCollector, MetricsTimer


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_initialization(self):
        """Test metrics collector initialization."""
        collector = MetricsCollector()
        assert collector.is_enabled()
        assert len(collector.get_events()) == 0

    def test_increment_counter(self):
        """Test incrementing counter metrics."""
        collector = MetricsCollector()

        # Increment without labels
        collector.increment("test_counter")
        assert collector.get_counter_value("test_counter") == 1.0

        # Increment with value
        collector.increment("test_counter", value=5.0)
        assert collector.get_counter_value("test_counter") == 6.0

    def test_increment_counter_with_labels(self):
        """Test incrementing counters with labels."""
        collector = MetricsCollector()

        # Increment with different labels
        collector.increment("requests", labels={"status": "success"})
        collector.increment("requests", labels={"status": "success"})
        collector.increment("requests", labels={"status": "error"})

        # Total across all labels
        assert collector.get_counter_value("requests") == 3.0

        # Filtered by labels
        assert collector.get_counter_value("requests", labels={"status": "success"}) == 2.0
        assert collector.get_counter_value("requests", labels={"status": "error"}) == 1.0

    def test_record_histogram(self):
        """Test recording histogram metrics."""
        collector = MetricsCollector()

        # Record values
        collector.record_histogram("latency", 1.5)
        collector.record_histogram("latency", 2.0)
        collector.record_histogram("latency", 0.5)

        values = collector.get_histogram_values("latency")
        assert len(values) == 3
        assert 1.5 in values
        assert 2.0 in values
        assert 0.5 in values

    def test_record_histogram_with_labels(self):
        """Test recording histograms with labels."""
        collector = MetricsCollector()

        # Record with labels
        collector.record_histogram("response_time", 100, labels={"endpoint": "/api/logs"})
        collector.record_histogram("response_time", 150, labels={"endpoint": "/api/logs"})
        collector.record_histogram("response_time", 50, labels={"endpoint": "/api/health"})

        # All values
        all_values = collector.get_histogram_values("response_time")
        assert len(all_values) == 3

        # Filtered by labels
        api_values = collector.get_histogram_values(
            "response_time", labels={"endpoint": "/api/logs"}
        )
        assert len(api_values) == 2
        assert 100 in api_values
        assert 150 in api_values

    def test_get_events(self):
        """Test getting all metric events."""
        collector = MetricsCollector()

        collector.increment("counter1")
        collector.record_histogram("histogram1", 1.0)
        collector.increment("counter1")

        events = collector.get_events()
        assert len(events) == 3
        assert events[0].name == "counter1"
        assert events[0].type == MetricType.COUNTER
        assert events[1].name == "histogram1"
        assert events[1].type == MetricType.HISTOGRAM

    def test_clear(self):
        """Test clearing metrics."""
        collector = MetricsCollector()

        collector.increment("test")
        assert len(collector.get_events()) == 1

        collector.clear()
        assert len(collector.get_events()) == 0
        assert collector.get_counter_value("test") == 0.0

    def test_enable_disable(self):
        """Test enabling and disabling metrics collection."""
        collector = MetricsCollector()

        # Initially enabled
        assert collector.is_enabled()
        collector.increment("test")
        assert len(collector.get_events()) == 1

        # Disable
        collector.disable()
        assert not collector.is_enabled()
        collector.increment("test")  # Should not record
        assert len(collector.get_events()) == 1  # Still 1

        # Re-enable
        collector.enable()
        assert collector.is_enabled()
        collector.increment("test")
        assert len(collector.get_events()) == 2

    def test_export_summary(self):
        """Test exporting metric summary."""
        collector = MetricsCollector()

        # Add various metrics
        collector.increment("retry_attempts", labels={"reason": "empty_logs"})
        collector.increment("retry_attempts", labels={"reason": "empty_logs"})
        collector.increment("retry_attempts", labels={"reason": "log_group_not_found"})

        collector.record_histogram("duration", 1.0)
        collector.record_histogram("duration", 2.0)
        collector.record_histogram("duration", 3.0)

        summary = collector.export_summary()

        # Check counters
        assert "counters" in summary
        assert "retry_attempts" in summary["counters"]
        assert summary["counters"]["retry_attempts"]["total"] == 3.0

        # Check histograms
        assert "histograms" in summary
        assert "duration" in summary["histograms"]
        assert summary["histograms"]["duration"]["count"] == 3
        assert summary["histograms"]["duration"]["min"] == 1.0
        assert summary["histograms"]["duration"]["max"] == 3.0
        assert summary["histograms"]["duration"]["avg"] == 2.0

        # Check total events
        assert summary["total_events"] == 6

    def test_multiple_metrics_with_same_name_different_labels(self):
        """Test handling multiple metrics with same name but different labels."""
        collector = MetricsCollector()

        # Add metrics with different label combinations
        collector.increment("requests", labels={"status": "success", "method": "GET"})
        collector.increment("requests", labels={"status": "success", "method": "POST"})
        collector.increment("requests", labels={"status": "error", "method": "GET"})

        # Total
        assert collector.get_counter_value("requests") == 3.0

        # Filtered by partial labels
        assert collector.get_counter_value("requests", labels={"status": "success"}) == 2.0

        # Filtered by full labels
        assert (
            collector.get_counter_value("requests", labels={"status": "success", "method": "GET"})
            == 1.0
        )


class TestMetricsTimer:
    """Tests for MetricsTimer context manager."""

    def test_timer_records_duration(self):
        """Test that timer correctly records duration."""
        collector = MetricsCollector()

        with MetricsTimer(collector, "operation_duration"):
            time.sleep(0.1)  # Sleep for 100ms

        values = collector.get_histogram_values("operation_duration")
        assert len(values) == 1
        # Should be approximately 0.1 seconds (100ms)
        assert 0.09 < values[0] < 0.15  # Allow some variance

    def test_timer_with_labels(self):
        """Test timer with labels."""
        collector = MetricsCollector()

        with MetricsTimer(collector, "task_duration", labels={"task": "fetch_logs"}):
            time.sleep(0.05)

        values = collector.get_histogram_values("task_duration", labels={"task": "fetch_logs"})
        assert len(values) == 1
        assert 0.04 < values[0] < 0.1

    def test_timer_records_even_on_exception(self):
        """Test that timer records duration even when exception occurs."""
        collector = MetricsCollector()

        try:
            with MetricsTimer(collector, "failing_operation"):
                time.sleep(0.05)
                raise ValueError("Test error")
        except ValueError:
            pass  # Expected

        # Duration should still be recorded
        values = collector.get_histogram_values("failing_operation")
        assert len(values) == 1
        assert 0.04 < values[0] < 0.1

    def test_multiple_timers(self):
        """Test multiple timer measurements."""
        collector = MetricsCollector()

        for i in range(3):
            with MetricsTimer(collector, "repeated_operation", labels={"iteration": str(i)}):
                time.sleep(0.02 * (i + 1))  # Increasing sleep time

        # Should have 3 measurements
        values = collector.get_histogram_values("repeated_operation")
        assert len(values) == 3

        # Each should be different
        assert values[0] < values[1] < values[2]
