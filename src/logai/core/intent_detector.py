"""Intent detection for agent self-direction.

This module provides intent detection capabilities to identify when the agent
states an intention without executing the corresponding action. This is a key
component of the self-direction system that helps the agent be more proactive.
"""

import re
from dataclasses import dataclass
from enum import Enum


class IntentType(Enum):
    """Types of detected intents."""

    SEARCH_LOGS = "search_logs"
    LIST_GROUPS = "list_groups"
    EXPAND_TIME = "expand_time"
    CHANGE_FILTER = "change_filter"
    ANALYZE = "analyze"
    NONE = "none"


@dataclass
class DetectedIntent:
    """Represents a detected intent in agent response.

    Attributes:
        intent_type: The type of intent detected
        confidence: Confidence score from 0.0 to 1.0
        trigger_phrases: List of phrases that triggered the detection
        suggested_action: Optional suggested action to take
    """

    intent_type: IntentType
    confidence: float  # 0.0 to 1.0
    trigger_phrases: list[str]
    suggested_action: str | None = None


class IntentDetector:
    """Detects stated intentions in agent responses.

    The IntentDetector analyzes text responses from the agent to identify
    cases where the agent states what it will do without actually doing it.
    This helps the orchestrator prompt the agent to take action instead of
    just describing what it plans to do.
    """

    # Patterns that indicate intent without action
    # Each tuple is: (pattern, intent_type, confidence_score)
    INTENT_PATTERNS = [
        # Search/fetch intentions
        (
            r"\b(i['']?ll|let me|i will|i['']?m going to)\s+(search|look|check|fetch|find|query|examine|investigate)\b",
            IntentType.SEARCH_LOGS,
            0.9,
        ),
        # Listing intentions
        (
            r"\b(i['']?ll|let me|i will)\s+(list|show|display|get)\s+(the\s+)?(available\s+)?log\s*groups?\b",
            IntentType.LIST_GROUPS,
            0.9,
        ),
        # Time expansion intentions
        (
            r"\b(expand|widen|broaden|increase|extend)\s+(the\s+)?time\s*(range|window|period)?\b",
            IntentType.EXPAND_TIME,
            0.8,
        ),
        # Filter change intentions
        (
            r"\b(try|use)\s+(a\s+)?(different|another|broader|narrower)\s+filter\b",
            IntentType.CHANGE_FILTER,
            0.8,
        ),
        # Analysis intentions (these are OK without tool calls)
        (
            r"\b(i['']?ll|let me)\s+(analyze|summarize|review)\s+(the\s+)?(results|logs|data)\b",
            IntentType.ANALYZE,
            0.5,
        ),
    ]

    # Patterns that indicate the agent is giving up too easily
    GIVING_UP_PATTERNS = [
        r"\bno\s+(logs?|results?|data|entries)\s+(were\s+)?found\b",
        r"\b(could\s*n[''']?t|could\s+not)\s+find\s+any\b",
        r"\bthere\s+(are|were)\s+no\s+(matching\s+)?(logs?|results?)\b",
        r"\bthe\s+search\s+returned\s+(no|zero|empty)\b",
        r"\bunfortunately[,]?\s+(i\s+)?((could\s*n[''']?t|could\s+not)|was\s+unable)\b",
    ]

    @classmethod
    def detect_intent(cls, response_text: str) -> DetectedIntent | None:
        """Detect if response contains stated intent without action.

        This method analyzes the agent's text response to identify patterns
        that suggest the agent is stating what it will do without actually
        calling the appropriate tool to do it.

        Args:
            response_text: The agent's text response to analyze

        Returns:
            DetectedIntent if intent found, None otherwise
        """
        if not response_text:
            return None

        text_lower = response_text.lower()

        for pattern, intent_type, confidence in cls.INTENT_PATTERNS:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                # Skip ANALYZE intents - those don't need tool calls
                # Analysis is something the agent can do on already-retrieved data
                if intent_type == IntentType.ANALYZE:
                    continue

                return DetectedIntent(
                    intent_type=intent_type,
                    confidence=confidence,
                    trigger_phrases=[
                        str(m) if isinstance(m, str) else " ".join(m) for m in matches
                    ],
                    suggested_action=cls._get_suggested_action(intent_type),
                )

        return None

    @classmethod
    def detect_premature_giving_up(cls, response_text: str) -> bool:
        """Detect if agent is giving up without sufficient effort.

        This method identifies patterns in the agent's response that suggest
        it is giving up on a task without trying alternative approaches.

        Args:
            response_text: The agent's text response to analyze

        Returns:
            True if agent appears to be giving up prematurely
        """
        if not response_text:
            return False

        text_lower = response_text.lower()

        for pattern in cls.GIVING_UP_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True

        return False

    @classmethod
    def _get_suggested_action(cls, intent_type: IntentType) -> str:
        """Get suggested action for an intent type.

        Args:
            intent_type: The type of intent detected

        Returns:
            Human-readable suggestion for what action to take
        """
        suggestions = {
            IntentType.SEARCH_LOGS: "Use fetch_logs or search_logs tool",
            IntentType.LIST_GROUPS: "Use list_log_groups tool",
            IntentType.EXPAND_TIME: "Call fetch_logs with expanded start_time",
            IntentType.CHANGE_FILTER: "Call fetch_logs with different filter_pattern",
        }
        return suggestions.get(intent_type, "Execute the stated action")
