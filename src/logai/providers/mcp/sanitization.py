"""Post-processing pipeline for MCP tool results.

Applies PII sanitization to log-containing MCP results before they reach
the LLM.  Metrics and alarms results pass through unchanged.

Key design note — format differences
--------------------------------------
Native tools return events under the ``"events"`` key with ``"message"``
and ``"timestamp"`` fields.  CloudWatch Logs Insights results (returned by
the MCP server) use the ``"results"`` key with ``"@message"`` and
``"@timestamp"`` fields.  This module handles both formats.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from logai.core.sanitizer import LogSanitizer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Processing strategy constants
# ---------------------------------------------------------------------------
_STRATEGY_SANITIZE = "sanitize"
_STRATEGY_PASSTHROUGH = "passthrough"

# Map MCP tool names to processing strategies.
# Tools not present in this map default to "passthrough" (unknown tools are
# treated conservatively — no data modification).
_TOOL_STRATEGIES: dict[str, str] = {
    # Logs Insights query lifecycle
    "execute_log_insights_query": _STRATEGY_SANITIZE,  # Returns log data synchronously
    "get_logs_insight_query_results": _STRATEGY_SANITIZE,  # Returns log data (async fallback)
    "cancel_logs_insight_query": _STRATEGY_PASSTHROUGH,  # Returns status only
    # Log group discovery — metadata, no PII in log events
    "describe_log_groups": _STRATEGY_PASSTHROUGH,
    # Anomaly / pattern analysis — may include log samples
    "analyze_log_group": _STRATEGY_SANITIZE,
    # Metrics tools — numeric data, no log events
    "get_metric_data": _STRATEGY_PASSTHROUGH,
    "get_metric_metadata": _STRATEGY_PASSTHROUGH,
    "analyze_metric": _STRATEGY_PASSTHROUGH,
    # Alarms tools — alarm state, no log events
    "get_active_alarms": _STRATEGY_PASSTHROUGH,
    "get_alarm_history": _STRATEGY_PASSTHROUGH,
    "get_recommended_metric_alarms": _STRATEGY_PASSTHROUGH,
}


class ResultProcessor:
    """
    Post-processing pipeline for MCP tool results.

    Applies sanitization and format normalisation to raw MCP server responses
    before they reach the LLM.

    Sanitization is skipped gracefully when:
    - No ``LogSanitizer`` was supplied.
    - ``sanitizer.enabled`` is ``False``.
    - The tool's strategy mapping is ``"passthrough"``.
    """

    def __init__(
        self,
        sanitizer: LogSanitizer | None = None,
    ) -> None:
        """
        Initialise the result processor.

        Args:
            sanitizer: Optional ``LogSanitizer`` instance.  When ``None`` or
                       when ``sanitizer.enabled`` is ``False``, no sanitization
                       is applied.
        """
        self._sanitizer = sanitizer

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process(self, tool_name: str, result: Any) -> dict[str, Any]:
        """
        Process a raw MCP tool result.

        Args:
            tool_name: Name of the MCP tool that produced the result.
            result: Raw result returned by ``MCPClientManager.call_tool()``.
                    Expected to be a dict, but we defensively handle non-dict
                    values by wrapping them.

        Returns:
            Processed result dict with sanitization applied where appropriate.
        """
        # Ensure we always work with a dict.
        if not isinstance(result, dict):
            result = {"raw_text": str(result)}

        strategy = _TOOL_STRATEGIES.get(tool_name, _STRATEGY_PASSTHROUGH)

        if (
            strategy == _STRATEGY_SANITIZE
            and self._sanitizer is not None
            and self._sanitizer.enabled
        ):
            result = self._apply_sanitization(tool_name, result)
            logger.debug("Sanitization applied to MCP tool result: %s", tool_name)
        else:
            logger.debug(
                "MCP result passthrough (tool=%s, strategy=%s, sanitizer_enabled=%s)",
                tool_name,
                strategy,
                self._sanitizer.enabled if self._sanitizer else False,
            )

        return cast(dict[str, Any], result)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_sanitization(self, tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
        """
        Apply PII sanitization to log-containing result dicts.

        Handles four result formats:

        **Insights format** (``get_logs_insight_query_results``)::

            {
                "results": [
                    {"@message": "...", "@timestamp": "...", ...},
                    ...
                ]
            }

        **Events format** (native tools)::

            {
                "events": [
                    {"message": "...", "timestamp": "...", ...},
                    ...
                ]
            }

        **Anomalies format** (``analyze_log_group``)::

            {
                "anomalies": [
                    {"description": "...", "logSamples": [...], ...},
                    ...
                ]
            }

        **Patterns format** (``analyze_log_group``)::

            {
                "patterns": [
                    {"patternString": "...", "logSamples": [...], ...},
                    ...
                ]
            }

        All formats are sanitized in-place (on a shallow copy of the result
        dict) and a ``"sanitization"`` summary dict is injected.

        Args:
            tool_name: Name of the tool (used for logging only).
            result: Raw result dict from the MCP server.

        Returns:
            A new dict with sanitized content and a ``"sanitization"`` summary.
        """
        # Work on a shallow copy so we don't mutate the caller's dict.
        result = dict(result)

        # We accumulate redactions across *both* formats so that the final
        # ``"sanitization"`` key is written exactly once with the merged totals.
        # Writing it inside each block would cause the second block to silently
        # overwrite the first block's redaction counts.
        all_redactions: dict[str, int] = {}
        any_sanitized = False

        # ---- Insights query results: list of field-value dicts ----
        insights_results: list[dict[str, Any]] = result.get("results", [])
        if insights_results and isinstance(insights_results, list):
            sanitized_records: list[dict[str, Any]] = []

            for record in insights_results:
                sanitized_record: dict[str, Any] = {}
                for key, value in record.items():
                    if isinstance(value, str):
                        san = self._sanitizer.sanitize(value)  # type: ignore[union-attr]
                        sanitized_record[key] = san.sanitized_text
                        for pattern_name, count in san.redactions.items():
                            all_redactions[pattern_name] = (
                                all_redactions.get(pattern_name, 0) + count
                            )
                    else:
                        sanitized_record[key] = value
                sanitized_records.append(sanitized_record)

            result["results"] = sanitized_records
            any_sanitized = True

        # ---- Events format: list of event dicts with "message" key ----
        events: list[dict[str, Any]] = result.get("events", [])
        if events and isinstance(events, list):
            sanitized_events, event_redactions = self._sanitizer.sanitize_log_events(events)  # type: ignore[union-attr]
            result["events"] = sanitized_events
            for pattern_name, count in event_redactions.items():
                all_redactions[pattern_name] = all_redactions.get(pattern_name, 0) + count
            any_sanitized = True

        # ---- Anomalies format: list of anomaly dicts from analyze_log_group ----
        # Each anomaly may carry a "logSamples" list (sanitized via sanitize_log_events)
        # and a "description" string (sanitized via sanitize).
        anomalies: list[dict[str, Any]] = result.get("anomalies", [])
        if anomalies and isinstance(anomalies, list):
            sanitized_anomalies: list[dict[str, Any]] = []
            for anomaly in anomalies:
                sanitized_anomaly = dict(anomaly)
                if isinstance(sanitized_anomaly.get("logSamples"), list):
                    sanitized_samples, sample_redactions = self._sanitizer.sanitize_log_events(  # type: ignore[union-attr]
                        sanitized_anomaly["logSamples"]
                    )
                    sanitized_anomaly["logSamples"] = sanitized_samples
                    for pattern_name, count in sample_redactions.items():
                        all_redactions[pattern_name] = all_redactions.get(pattern_name, 0) + count
                if isinstance(sanitized_anomaly.get("description"), str):
                    san = self._sanitizer.sanitize(sanitized_anomaly["description"])  # type: ignore[union-attr]
                    sanitized_anomaly["description"] = san.sanitized_text
                    for pattern_name, count in san.redactions.items():
                        all_redactions[pattern_name] = all_redactions.get(pattern_name, 0) + count
                sanitized_anomalies.append(sanitized_anomaly)
            result["anomalies"] = sanitized_anomalies
            any_sanitized = True

        # ---- Patterns format: list of pattern dicts from analyze_log_group ----
        # Each pattern may carry a "logSamples" list (sanitized via sanitize_log_events)
        # and a "patternString" string (sanitized via sanitize).
        patterns: list[dict[str, Any]] = result.get("patterns", [])
        if patterns and isinstance(patterns, list):
            sanitized_patterns: list[dict[str, Any]] = []
            for pattern in patterns:
                sanitized_pattern = dict(pattern)
                if isinstance(sanitized_pattern.get("logSamples"), list):
                    sanitized_samples, sample_redactions = self._sanitizer.sanitize_log_events(  # type: ignore[union-attr]
                        sanitized_pattern["logSamples"]
                    )
                    sanitized_pattern["logSamples"] = sanitized_samples
                    for pattern_name, count in sample_redactions.items():
                        all_redactions[pattern_name] = all_redactions.get(pattern_name, 0) + count
                if isinstance(sanitized_pattern.get("patternString"), str):
                    san = self._sanitizer.sanitize(sanitized_pattern["patternString"])  # type: ignore[union-attr]
                    sanitized_pattern["patternString"] = san.sanitized_text
                    for pattern_name, count in san.redactions.items():
                        all_redactions[pattern_name] = all_redactions.get(pattern_name, 0) + count
                sanitized_patterns.append(sanitized_pattern)
            result["patterns"] = sanitized_patterns
            any_sanitized = True

        # Write the sanitization summary once, with merged redaction counts.
        if any_sanitized:
            result["sanitization"] = {
                "enabled": True,
                "redactions": all_redactions,
                "summary": self._sanitizer.get_redaction_summary(all_redactions),  # type: ignore[union-attr]
            }

        return result
