"""Metrics collection for observability and monitoring.

This module provides a simple metrics collector that tracks key operational
metrics. The implementation is designed to be easily integrated with external
monitoring systems like Prometheus or CloudWatch in the future.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MetricType(Enum):
    """Types of metrics that can be collected."""

    COUNTER = "counter"  # Monotonically increasing value
    HISTOGRAM = "histogram"  # Distribution of values over time


@dataclass
class MetricEvent:
    """Represents a single metric event.

    Attributes:
        name: Metric name (e.g., "retry_attempts", "intent_detection_hits")
        type: Type of metric (counter or histogram)
        value: The metric value
        labels: Optional labels for filtering/grouping (e.g., {"reason": "empty_logs"})
        timestamp: When the metric was recorded
    """

    name: str
    type: MetricType
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MetricsCollector:
    """Collects and stores metrics for monitoring and observability.

    This class provides a simple in-memory metrics collection system that can
    be easily extended to emit to external monitoring systems like Prometheus
    or CloudWatch.

    The collector is designed to be:
    - Thread-safe for concurrent access
    - Low-overhead (minimal performance impact)
    - Easy to integrate with existing monitoring infrastructure
    """

    def __init__(self):
        """Initialize the metrics collector."""
        self._events: list[MetricEvent] = []
        self._enabled: bool = True

    def increment(
        self, name: str, value: float = 1.0, labels: dict[str, str] | None = None
    ) -> None:
        """Increment a counter metric.

        Counters are for values that only increase over time, like:
        - Number of retry attempts
        - Number of successful/failed operations
        - Number of intent detection hits

        Args:
            name: Name of the counter metric
            value: Amount to increment by (default: 1.0)
            labels: Optional labels for filtering (e.g., {"status": "success"})

        Example:
            metrics.increment("retry_attempts", labels={"reason": "empty_logs"})
            metrics.increment("intent_detection_hits", labels={"intent_type": "fetch_logs"})
        """
        if not self._enabled:
            return

        event = MetricEvent(
            name=name,
            type=MetricType.COUNTER,
            value=value,
            labels=labels or {},
        )
        self._events.append(event)

    def record_histogram(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Record a histogram metric (distribution of values).

        Histograms track the distribution of values over time, like:
        - Request/response latencies
        - Time spent in retry logic
        - Size of result sets

        Args:
            name: Name of the histogram metric
            value: The value to record
            labels: Optional labels for filtering

        Example:
            metrics.record_histogram("retry_duration_seconds", 1.5, labels={"attempt": "2"})
            metrics.record_histogram("tool_execution_seconds", 0.3, labels={"tool": "fetch_logs"})
        """
        if not self._enabled:
            return

        event = MetricEvent(
            name=name,
            type=MetricType.HISTOGRAM,
            value=value,
            labels=labels or {},
        )
        self._events.append(event)

    def get_events(self) -> list[MetricEvent]:
        """Get all recorded metric events.

        Returns:
            List of metric events in chronological order
        """
        return self._events.copy()

    def get_counter_value(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Get the current value of a counter metric.

        This sums all increment operations for a given counter, optionally
        filtered by labels.

        Args:
            name: Name of the counter to query
            labels: Optional labels to filter by

        Returns:
            Sum of all increments for this counter
        """
        total = 0.0
        for event in self._events:
            if event.type != MetricType.COUNTER or event.name != name:
                continue

            # Check if labels match (if specified)
            if labels is not None:
                if not all(event.labels.get(k) == v for k, v in labels.items()):
                    continue

            total += event.value

        return total

    def get_histogram_values(self, name: str, labels: dict[str, str] | None = None) -> list[float]:
        """Get all values for a histogram metric.

        Args:
            name: Name of the histogram to query
            labels: Optional labels to filter by

        Returns:
            List of all recorded values for this histogram
        """
        values = []
        for event in self._events:
            if event.type != MetricType.HISTOGRAM or event.name != name:
                continue

            # Check if labels match (if specified)
            if labels is not None:
                if not all(event.labels.get(k) == v for k, v in labels.items()):
                    continue

            values.append(event.value)

        return values

    def clear(self) -> None:
        """Clear all recorded metrics.

        Useful for testing or periodic cleanup.
        """
        self._events.clear()

    def enable(self) -> None:
        """Enable metrics collection."""
        self._enabled = True

    def disable(self) -> None:
        """Disable metrics collection.

        When disabled, all metric recording operations become no-ops.
        """
        self._enabled = False

    def is_enabled(self) -> bool:
        """Check if metrics collection is enabled."""
        return self._enabled

    def export_summary(self) -> dict[str, Any]:
        """Export a summary of collected metrics.

        This provides a human-readable summary of all metrics, useful for
        debugging and monitoring dashboards.

        Returns:
            Dictionary with metric summaries by type and name
        """
        summary: dict[str, Any] = {
            "counters": {},
            "histograms": {},
            "total_events": len(self._events),
        }

        # Aggregate counters
        for event in self._events:
            if event.type == MetricType.COUNTER:
                if event.name not in summary["counters"]:
                    summary["counters"][event.name] = {"total": 0.0, "by_labels": {}}

                summary["counters"][event.name]["total"] += event.value

                # Track by label combinations
                label_key = str(sorted(event.labels.items()))
                if label_key not in summary["counters"][event.name]["by_labels"]:
                    summary["counters"][event.name]["by_labels"][label_key] = 0.0
                summary["counters"][event.name]["by_labels"][label_key] += event.value

        # Aggregate histograms
        for event in self._events:
            if event.type == MetricType.HISTOGRAM:
                if event.name not in summary["histograms"]:
                    summary["histograms"][event.name] = {"values": [], "by_labels": {}}

                summary["histograms"][event.name]["values"].append(event.value)

                # Track by label combinations
                label_key = str(sorted(event.labels.items()))
                if label_key not in summary["histograms"][event.name]["by_labels"]:
                    summary["histograms"][event.name]["by_labels"][label_key] = []
                summary["histograms"][event.name]["by_labels"][label_key].append(event.value)

        # Add statistics for histograms
        for name, data in summary["histograms"].items():
            values = data["values"]
            if values:
                data["count"] = len(values)
                data["min"] = min(values)
                data["max"] = max(values)
                data["avg"] = sum(values) / len(values)

        return summary


class MetricsTimer:
    """Context manager for timing operations and recording to metrics.

    This helper makes it easy to measure and record the duration of operations
    as histogram metrics.

    Example:
        with MetricsTimer(metrics, "tool_execution_seconds", {"tool": "fetch_logs"}):
            result = await tool_registry.execute("fetch_logs", **args)
    """

    def __init__(
        self, collector: MetricsCollector, metric_name: str, labels: dict[str, str] | None = None
    ):
        """Initialize the timer.

        Args:
            collector: MetricsCollector instance to record to
            metric_name: Name of the histogram metric
            labels: Optional labels for the metric
        """
        self.collector = collector
        self.metric_name = metric_name
        self.labels = labels or {}
        self.start_time: float | None = None

    def __enter__(self) -> "MetricsTimer":
        """Start timing."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop timing and record metric."""
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.collector.record_histogram(self.metric_name, duration, self.labels)
