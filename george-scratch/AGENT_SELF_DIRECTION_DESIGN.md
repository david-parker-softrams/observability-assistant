# Agent Self-Direction Enhancement - Design Document

**Document Version:** 1.0  
**Date:** February 11, 2026  
**Author:** Sally (Senior Software Architect)  
**Status:** READY FOR REVIEW  
**Estimated Implementation Time:** 8-12 hours

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Analysis](#2-problem-analysis)
3. [Architecture Overview](#3-architecture-overview)
4. [System Prompt Enhancements](#4-system-prompt-enhancements)
5. [Intent Detection Strategy](#5-intent-detection-strategy)
6. [Retry Logic Design](#6-retry-logic-design)
7. [Result Analysis](#7-result-analysis)
8. [Edge Cases & Error Handling](#8-edge-cases--error-handling)
9. [Testing Strategy](#9-testing-strategy)
10. [Implementation Plan](#10-implementation-plan)
11. [Risk Assessment](#11-risk-assessment)
12. [Appendix: Code Examples](#appendix-code-examples)

---

## 1. Executive Summary

### 1.1 Problem Statement

The LogAI agent currently lacks **self-direction capabilities**, causing it to:
- Give up immediately when tool calls return empty results
- State intentions ("I'll check the logs...") without executing the corresponding tool calls
- Exit the conversation loop prematurely when providing text-only responses

### 1.2 Proposed Solution

This design introduces a **three-layer self-direction system**:

1. **Enhanced System Prompt** - Explicit instructions for retry behavior and alternative strategies
2. **Intent Detection** - Identify when agent states intent but doesn't act
3. **Adaptive Retry Logic** - Automatically re-prompt the agent with guidance when results are empty

### 1.3 Key Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Minimal Invasiveness** | Enhance existing orchestrator rather than rebuild |
| **LLM-Native** | Leverage prompt engineering over complex code logic |
| **Configurable** | Allow tuning of retry limits and behavior |
| **Observable** | Log retry attempts for debugging and monitoring |
| **Backward Compatible** | Existing functionality remains unchanged |

---

## 2. Problem Analysis

### 2.1 Root Cause #1: System Prompt Deficiency

**Current State** (orchestrator.py lines 32-64):
```python
SYSTEM_PROMPT = """You are an expert observability assistant...

## Error Handling
1. If a log group doesn't exist, suggest alternatives
2. If no logs found, suggest adjusting time range or filters
3. Explain any limitations clearly
"""
```

**Problem:** The prompt tells the agent what to *say* when encountering empty results, but not what to *do*. It lacks explicit instructions to:
- Automatically retry with different parameters
- Try alternative approaches before responding to the user
- Persist through multiple empty results

### 2.2 Root Cause #2: Premature Loop Exit

**Current State** (orchestrator.py lines 200-207):
```python
# No tool calls - we have the final response
if response.content:
    self.conversation_history.append(
        {"role": "assistant", "content": response.content}
    )
    return response.content
```

**Problem:** The loop exits immediately when the LLM produces any text response, even if:
- The response indicates intent without action ("I'll search for...")
- The previous tool returned empty results that could be retried
- The agent should try alternative approaches

### 2.3 Impact Assessment

| Scenario | Current Behavior | Desired Behavior |
|----------|------------------|------------------|
| Empty log results | Agent apologizes, exits | Agent expands time range, retries |
| Wrong log group | Agent suggests alternatives | Agent tries suggested alternatives |
| Intent without action | Agent states intent, exits | Agent executes the stated intent |
| Narrow filter, no matches | Agent gives up | Agent broadens filter, retries |

---

## 3. Architecture Overview

### 3.1 Enhanced Orchestrator Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            LLMOrchestrator                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    ENHANCED CONVERSATION LOOP                           │ │
│  │                                                                         │ │
│  │   ┌───────────────┐    ┌───────────────┐    ┌───────────────────────┐  │ │
│  │   │ LLM Response  │───>│ Intent        │───>│ Should Continue?      │  │ │
│  │   │ Handler       │    │ Detector      │    │ Decision Engine       │  │ │
│  │   └───────────────┘    └───────────────┘    └───────────────────────┘  │ │
│  │          │                    │                       │                 │ │
│  │          ▼                    ▼                       ▼                 │ │
│  │   ┌───────────────┐    ┌───────────────┐    ┌───────────────────────┐  │ │
│  │   │ Tool Call     │    │ Intent-to-    │    │ Retry Prompt          │  │ │
│  │   │ Executor      │    │ Prompt        │    │ Generator             │  │ │
│  │   └───────────────┘    │ Converter     │    └───────────────────────┘  │ │
│  │          │             └───────────────┘              │                 │ │
│  │          ▼                    │                       ▼                 │ │
│  │   ┌───────────────┐          │              ┌───────────────────────┐  │ │
│  │   │ Result        │<─────────┴─────────────>│ System Message        │  │ │
│  │   │ Analyzer      │                         │ Injector              │  │ │
│  │   └───────────────┘                         └───────────────────────┘  │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **Intent Detector** | Analyze text responses for stated intentions without tool calls |
| **Result Analyzer** | Evaluate tool results for empty/insufficient data |
| **Decision Engine** | Determine if loop should continue or exit |
| **Retry Prompt Generator** | Create guidance messages for retry attempts |
| **System Message Injector** | Add system messages to guide retry behavior |

### 3.3 State Machine

```
                    ┌──────────────┐
                    │   START      │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
              ┌────>│  LLM CALL    │<────────────────────┐
              │     └──────┬───────┘                     │
              │            │                             │
              │            ▼                             │
              │     ┌──────────────┐                     │
              │     │ HAS TOOL     │                     │
              │     │ CALLS?       │                     │
              │     └──────┬───────┘                     │
              │       Yes/ \No                           │
              │          /   \                           │
              │         ▼     ▼                          │
              │  ┌──────────┐ ┌─────────────┐           │
              │  │ EXECUTE  │ │ ANALYZE     │           │
              │  │ TOOLS    │ │ RESPONSE    │           │
              │  └────┬─────┘ └──────┬──────┘           │
              │       │              │                   │
              │       ▼              ▼                   │
              │  ┌──────────┐ ┌─────────────┐           │
              │  │ ANALYZE  │ │ HAS INTENT  │           │
              │  │ RESULTS  │ │ W/O ACTION? │           │
              │  └────┬─────┘ └──────┬──────┘           │
              │       │         Yes/ \No                │
              │       ▼            /   \                │
              │  ┌──────────┐     ▼     ▼               │
              │  │ EMPTY    │ ┌─────┐ ┌──────┐          │
              │  │ RESULTS? │ │RETRY│ │ EXIT │          │
              │  └────┬─────┘ │ w/  │ │      │          │
              │  Yes/ \No     │NUDGE│ └──────┘          │
              │     /   \     └──┬──┘                   │
              │    ▼     ▼       │                      │
              │ ┌─────┐ ┌────┐   │                      │
              │ │RETRY│ │LOOP│   │                      │
              │ │COUNT│ │BACK│───┘                      │
              │ │< 3? │ └────┘                          │
              │ └──┬──┘                                 │
              │Yes/│\No                                 │
              │   /  \                                  │
              │  ▼    ▼                                 │
              │┌────┐ ┌────┐                            │
              ││LOOP│ │EXIT│                            │
              ││BACK│ │    │                            │
              │└──┬─┘ └────┘                            │
              │   │                                     │
              └───┴─────────────────────────────────────┘
```

---

## 4. System Prompt Enhancements

### 4.1 Enhanced System Prompt

**Location:** `src/logai/core/orchestrator.py` (lines 32-64)

**Add the following section after "Error Handling":**

```python
SYSTEM_PROMPT = """You are an expert observability assistant...

## Guidelines
[existing content...]

## Self-Direction & Persistence

### Automatic Retry Behavior
When you encounter empty results or no matches, YOU MUST automatically try alternative approaches before responding to the user:

1. **Empty Log Results**
   - FIRST: Expand the time range (e.g., 1h -> 6h -> 24h -> 7d)
   - SECOND: Broaden or remove the filter pattern
   - THIRD: Try a different log group if available
   - ONLY after trying 2-3 alternatives, report findings to the user

2. **Log Group Not Found**
   - FIRST: List available log groups to find similar names
   - SECOND: Try common prefixes (/aws/lambda/, /ecs/, /aws/apigateway/)
   - THIRD: Ask user for clarification only if no similar groups found

3. **Partial Results**
   - If results seem incomplete, try a broader search
   - If results are truncated, inform user and offer to narrow the search

### Action, Don't Just Describe
- NEVER say "I'll search for..." without immediately calling a tool
- NEVER say "Let me check..." without immediately making the check
- If you state an intention, execute it in the same response with a tool call
- Complete the investigation before providing your analysis

### Minimum Effort Principle
Before giving up on a search:
- You MUST have tried at least 2 different approaches
- You MUST have used at least 2 different parameter combinations
- You SHOULD expand time ranges before concluding "no logs found"

## Context
Current time: {current_time}
Available log groups will be discovered via tools.
"""
```

### 4.2 Rationale for Prompt Changes

| Addition | Purpose |
|----------|---------|
| **Automatic Retry Behavior** | Explicit 3-step escalation paths for common scenarios |
| **Action, Don't Just Describe** | Prevents intent-without-action responses |
| **Minimum Effort Principle** | Establishes baseline for acceptable "giving up" |

---

## 5. Intent Detection Strategy

### 5.1 Intent Detection Module

**New File:** `src/logai/core/intent_detector.py`

```python
"""Intent detection for agent self-direction."""

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
    """Represents a detected intent in agent response."""
    intent_type: IntentType
    confidence: float  # 0.0 to 1.0
    trigger_phrases: list[str]
    suggested_action: str | None = None


class IntentDetector:
    """Detects stated intentions in agent responses."""
    
    # Patterns that indicate intent without action
    INTENT_PATTERNS = [
        # Search/fetch intentions
        (r"\b(i['']?ll|let me|i will|i['']?m going to)\s+(search|look|check|fetch|find|query|examine|investigate)\b", 
         IntentType.SEARCH_LOGS, 0.9),
        
        # Listing intentions
        (r"\b(i['']?ll|let me|i will)\s+(list|show|display|get)\s+(the\s+)?(available\s+)?log\s*groups?\b",
         IntentType.LIST_GROUPS, 0.9),
        
        # Time expansion intentions
        (r"\b(expand|widen|broaden|increase|extend)\s+(the\s+)?time\s*(range|window|period)?\b",
         IntentType.EXPAND_TIME, 0.8),
        
        # Filter change intentions
        (r"\b(try|use)\s+(a\s+)?(different|another|broader|narrower)\s+filter\b",
         IntentType.CHANGE_FILTER, 0.8),
        
        # Analysis intentions (these are OK without tool calls)
        (r"\b(i['']?ll|let me)\s+(analyze|summarize|review)\s+(the\s+)?(results|logs|data)\b",
         IntentType.ANALYZE, 0.5),
    ]
    
    # Patterns that indicate the agent is giving up too easily
    GIVING_UP_PATTERNS = [
        r"\bno\s+(logs?|results?|data|entries)\s+(were\s+)?found\b",
        r"\bcouldn['']?t\s+find\s+any\b",
        r"\bthere\s+(are|were)\s+no\s+(matching\s+)?(logs?|results?)\b",
        r"\bthe\s+search\s+returned\s+(no|zero|empty)\b",
        r"\bunfortunately[,]?\s+(i\s+)?(couldn['']?t|was\s+unable)\b",
    ]
    
    @classmethod
    def detect_intent(cls, response_text: str) -> DetectedIntent | None:
        """
        Detect if response contains stated intent without action.
        
        Args:
            response_text: The agent's text response
            
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
                if intent_type == IntentType.ANALYZE:
                    continue
                    
                return DetectedIntent(
                    intent_type=intent_type,
                    confidence=confidence,
                    trigger_phrases=[str(m) if isinstance(m, str) else ' '.join(m) for m in matches],
                    suggested_action=cls._get_suggested_action(intent_type)
                )
        
        return None
    
    @classmethod
    def detect_premature_giving_up(cls, response_text: str) -> bool:
        """
        Detect if agent is giving up without sufficient effort.
        
        Args:
            response_text: The agent's text response
            
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
        """Get suggested action for an intent type."""
        suggestions = {
            IntentType.SEARCH_LOGS: "Use fetch_logs or search_logs tool",
            IntentType.LIST_GROUPS: "Use list_log_groups tool",
            IntentType.EXPAND_TIME: "Call fetch_logs with expanded start_time",
            IntentType.CHANGE_FILTER: "Call fetch_logs with different filter_pattern",
        }
        return suggestions.get(intent_type, "Execute the stated action")
```

### 5.2 Integration Points

The IntentDetector will be called in the orchestrator's conversation loop when:
1. The LLM returns a text response without tool calls
2. After tool execution returns empty results

---

## 6. Retry Logic Design

### 6.1 Retry Configuration

**Add to settings.py:**

```python
class SelfDirectionSettings(BaseSettings):
    """Settings for agent self-direction behavior."""
    
    # Maximum retry attempts for empty results
    max_retry_attempts: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum number of retry attempts for empty results"
    )
    
    # Enable/disable intent detection
    intent_detection_enabled: bool = Field(
        default=True,
        description="Enable detection of stated intent without action"
    )
    
    # Enable/disable automatic retries
    auto_retry_enabled: bool = Field(
        default=True,
        description="Enable automatic retry on empty results"
    )
    
    # Retry strategies
    time_expansion_factor: float = Field(
        default=4.0,
        description="Factor by which to expand time range on retry (e.g., 1h -> 4h)"
    )
```

### 6.2 Retry State Tracking

**Add to orchestrator.py:**

```python
@dataclass
class RetryState:
    """Tracks retry attempts within a conversation turn."""
    attempts: int = 0
    empty_result_count: int = 0
    strategies_tried: list[str] = field(default_factory=list)
    last_tool_name: str | None = None
    last_tool_args: dict[str, Any] | None = None
    
    def should_retry(self, max_attempts: int) -> bool:
        """Determine if we should attempt a retry."""
        return self.attempts < max_attempts
    
    def record_attempt(self, tool_name: str, args: dict[str, Any], strategy: str) -> None:
        """Record a retry attempt."""
        self.attempts += 1
        self.last_tool_name = tool_name
        self.last_tool_args = args
        self.strategies_tried.append(strategy)
    
    def record_empty_result(self) -> None:
        """Record an empty result."""
        self.empty_result_count += 1
    
    def reset(self) -> None:
        """Reset state for new conversation turn."""
        self.attempts = 0
        self.empty_result_count = 0
        self.strategies_tried.clear()
        self.last_tool_name = None
        self.last_tool_args = None
```

### 6.3 Retry Prompt Generation

**Add to orchestrator.py:**

```python
class RetryPromptGenerator:
    """Generates guidance prompts for retry attempts."""
    
    RETRY_PROMPTS = {
        "empty_logs": """
The previous search returned no results. Before giving up, please try one of these approaches:

1. **Expand Time Range**: If you searched for 1 hour, try 6 hours or 24 hours
2. **Broaden Filter**: Remove or simplify the filter pattern
3. **Different Log Group**: Try a related log group if available

Execute one of these alternatives now. Do not ask the user - try an alternative first.
""",
        
        "log_group_not_found": """
The specified log group was not found. Please:

1. Use list_log_groups to find available log groups
2. Look for similar names or common prefixes
3. Try the closest match

Execute a search now. Do not ask the user until you've tried to find alternatives.
""",
        
        "intent_without_action": """
You stated an intention but did not execute it. Please immediately call the appropriate tool to carry out your stated action. Do not describe what you will do - do it now.
""",
        
        "partial_results": """
The results may be incomplete. Consider:

1. Checking if there are more logs in a broader time range
2. Looking at related log groups for additional context
3. Searching for correlated events

If relevant, expand your search. Otherwise, proceed with your analysis.
""",
    }
    
    @classmethod
    def generate_retry_prompt(
        cls, 
        reason: str, 
        retry_state: RetryState,
        context: dict[str, Any] | None = None
    ) -> str:
        """
        Generate an appropriate retry prompt.
        
        Args:
            reason: The reason for retry (key into RETRY_PROMPTS)
            retry_state: Current retry state
            context: Additional context (e.g., last tool args)
            
        Returns:
            Formatted retry prompt
        """
        base_prompt = cls.RETRY_PROMPTS.get(reason, cls.RETRY_PROMPTS["empty_logs"])
        
        # Add context about previous attempts
        if retry_state.attempts > 0:
            attempt_info = f"\n\nThis is retry attempt {retry_state.attempts + 1}. "
            attempt_info += f"Strategies already tried: {', '.join(retry_state.strategies_tried)}."
            base_prompt += attempt_info
        
        # Add specific suggestions based on last tool call
        if context and retry_state.last_tool_args:
            if "start_time" in retry_state.last_tool_args:
                base_prompt += f"\n\nPrevious time range started at: {retry_state.last_tool_args['start_time']}"
            if "filter_pattern" in retry_state.last_tool_args:
                base_prompt += f"\nPrevious filter: {retry_state.last_tool_args.get('filter_pattern', 'none')}"
        
        return base_prompt
```

### 6.4 Enhanced Conversation Loop

**Modified orchestrator.py `_chat_complete` method:**

```python
async def _chat_complete(self, user_message: str) -> str:
    """
    Process message and return complete response.
    
    Enhanced with self-direction capabilities:
    - Detects intent without action and prompts execution
    - Automatically retries on empty results
    - Tracks retry state across the conversation turn
    """
    # Add user message to history
    self.conversation_history.append({"role": "user", "content": user_message})

    # Prepare messages with system prompt
    messages = [
        {"role": "system", "content": self._get_system_prompt()}
    ] + self.conversation_history

    # Get available tools
    tools = self.tool_registry.to_function_definitions()
    
    # Initialize retry state for this turn
    retry_state = RetryState()

    # Execute conversation loop with tool calling
    iteration = 0
    while iteration < self.MAX_TOOL_ITERATIONS:
        iteration += 1

        try:
            # Get LLM response
            response = await self.llm_provider.chat(
                messages=messages, tools=tools, stream=False
            )

            # Check if LLM wants to use tools
            if response.has_tool_calls():
                # Execute tool calls
                tool_results = await self._execute_tool_calls(response.tool_calls)
                
                # Track tool calls for retry logic
                for tool_call in response.tool_calls:
                    func_info = tool_call.get("function", {})
                    retry_state.last_tool_name = func_info.get("name")
                    try:
                        retry_state.last_tool_args = json.loads(func_info.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        retry_state.last_tool_args = {}

                # Add assistant message with tool calls to history
                assistant_message: dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": response.tool_calls,
                }
                self.conversation_history.append(assistant_message)
                messages.append(assistant_message)

                # Add tool results as separate messages
                for tool_result in tool_results:
                    tool_message: dict[str, Any] = {
                        "role": "tool",
                        "tool_call_id": tool_result["tool_call_id"],
                        "content": json.dumps(tool_result["result"]),
                    }
                    self.conversation_history.append(tool_message)
                    messages.append(tool_message)
                
                # Analyze results for retry logic
                should_retry, retry_reason = self._analyze_tool_results(
                    tool_results, retry_state
                )
                
                if should_retry and retry_state.should_retry(self.settings.max_retry_attempts):
                    # Inject retry guidance
                    retry_prompt = RetryPromptGenerator.generate_retry_prompt(
                        retry_reason, retry_state
                    )
                    retry_message = {
                        "role": "system",
                        "content": retry_prompt
                    }
                    messages.append(retry_message)
                    retry_state.record_attempt(
                        retry_state.last_tool_name or "unknown",
                        retry_state.last_tool_args or {},
                        retry_reason
                    )

                # Continue loop - LLM will process tool results
                continue

            # No tool calls - check for intent without action
            if self.settings.intent_detection_enabled and response.content:
                detected_intent = IntentDetector.detect_intent(response.content)
                
                if detected_intent and detected_intent.confidence >= 0.8:
                    # Agent stated intent but didn't act - prompt to act
                    if retry_state.should_retry(self.settings.max_retry_attempts):
                        nudge_message = {
                            "role": "system",
                            "content": RetryPromptGenerator.generate_retry_prompt(
                                "intent_without_action", retry_state
                            )
                        }
                        messages.append(nudge_message)
                        retry_state.record_attempt(
                            "intent_detection",
                            {},
                            "intent_without_action"
                        )
                        continue
                
                # Check for premature giving up
                if IntentDetector.detect_premature_giving_up(response.content):
                    if retry_state.empty_result_count > 0 and retry_state.should_retry(self.settings.max_retry_attempts):
                        # Agent giving up after empty results - encourage retry
                        nudge_message = {
                            "role": "system",
                            "content": RetryPromptGenerator.generate_retry_prompt(
                                "empty_logs", retry_state
                            )
                        }
                        messages.append(nudge_message)
                        retry_state.record_attempt(
                            "giving_up_prevention",
                            {},
                            "premature_exit"
                        )
                        continue

            # No tool calls and no retry needed - we have the final response
            if response.content:
                self.conversation_history.append(
                    {"role": "assistant", "content": response.content}
                )
                return response.content
            else:
                # Empty response, shouldn't happen but handle gracefully
                error_msg = "Received empty response from LLM"
                self.conversation_history.append({"role": "assistant", "content": error_msg})
                return error_msg

        except LLMProviderError as e:
            raise OrchestratorError(f"LLM provider error: {str(e)}") from e
        except Exception as e:
            raise OrchestratorError(f"Unexpected error during orchestration: {str(e)}") from e

    # Hit max iterations - likely infinite loop
    error_msg = f"Maximum tool iterations ({self.MAX_TOOL_ITERATIONS}) exceeded. The conversation may be stuck in a loop."
    self.conversation_history.append({"role": "assistant", "content": error_msg})
    return error_msg
```

---

## 7. Result Analysis

### 7.1 Result Analyzer

**Add to orchestrator.py:**

```python
def _analyze_tool_results(
    self, 
    tool_results: list[dict[str, Any]], 
    retry_state: RetryState
) -> tuple[bool, str]:
    """
    Analyze tool results to determine if retry is needed.
    
    Args:
        tool_results: Results from tool execution
        retry_state: Current retry state
        
    Returns:
        Tuple of (should_retry, reason)
    """
    for result in tool_results:
        result_data = result.get("result", {})
        
        # Check for error results
        if result_data.get("success") is False:
            error = result_data.get("error", "")
            
            # Log group not found - should retry with list
            if "not found" in error.lower() or "does not exist" in error.lower():
                return True, "log_group_not_found"
        
        # Check for empty results
        if result_data.get("success") is True:
            # Check various empty indicators
            count = result_data.get("count", -1)
            events = result_data.get("events", None)
            log_groups = result_data.get("log_groups", None)
            
            is_empty = False
            
            if count == 0:
                is_empty = True
            elif events is not None and len(events) == 0:
                is_empty = True
            elif log_groups is not None and len(log_groups) == 0:
                is_empty = True
            
            if is_empty:
                retry_state.record_empty_result()
                return True, "empty_logs"
    
    return False, ""
```

### 7.2 Empty Result Detection Heuristics

| Result Type | Empty Indicator | Retry Strategy |
|-------------|-----------------|----------------|
| `fetch_logs` | `count == 0` or `events == []` | Expand time, broaden filter |
| `list_log_groups` | `count == 0` or `log_groups == []` | Try different prefix |
| `search_logs` | `count == 0` or `events == []` | Expand time, different groups |
| Error results | `success == False` | Depends on error type |

---

## 8. Edge Cases & Error Handling

### 8.1 Infinite Loop Prevention

**Multiple safeguards:**

1. **Global Iteration Limit** (existing): `MAX_TOOL_ITERATIONS = 10`
2. **Retry Attempt Limit** (new): `max_retry_attempts = 3` (configurable)
3. **Strategy Tracking**: Track tried strategies to avoid repeating

**Loop Detection Logic:**

```python
def _detect_loop(self, retry_state: RetryState, response: LLMResponse) -> bool:
    """Detect if we're stuck in a loop."""
    # Check if same tool called with same args
    if response.has_tool_calls():
        for tool_call in response.tool_calls:
            func_info = tool_call.get("function", {})
            name = func_info.get("name")
            args = func_info.get("arguments", "{}")
            
            # Same tool and args as last time = potential loop
            if (name == retry_state.last_tool_name and 
                args == json.dumps(retry_state.last_tool_args)):
                return True
    
    return False
```

### 8.2 User Interruption Handling

User messages during retry loops should:
1. **Reset retry state** - User interaction resets the auto-retry counter
2. **Take priority** - User input always takes precedence
3. **Log interruption** - Record that retry was interrupted

```python
def _handle_user_interruption(self, retry_state: RetryState) -> None:
    """Handle user interruption during retry sequence."""
    if retry_state.attempts > 0:
        logger.info(
            "Retry sequence interrupted by user",
            attempts=retry_state.attempts,
            strategies_tried=retry_state.strategies_tried
        )
    retry_state.reset()
```

### 8.3 Error Scenarios

| Scenario | Handling |
|----------|----------|
| LLM refuses to retry | Accept after 3 prompts, return response |
| Tool errors during retry | Count as attempt, suggest different approach |
| Rate limiting | Respect rate limits, don't retry immediately |
| Context window exceeded | Summarize history, continue with condensed context |
| Network errors | Retry with exponential backoff (existing logic) |

### 8.4 Graceful Degradation

When self-direction features fail:
1. **Log the failure** for debugging
2. **Fall back to original behavior** - return response as-is
3. **Don't block the user** - never hang waiting for retries

```python
try:
    # Self-direction logic
    ...
except Exception as e:
    logger.warning(
        "Self-direction feature failed, falling back",
        error=str(e),
        feature="intent_detection"
    )
    # Continue without self-direction
```

---

## 9. Testing Strategy

### 9.1 Unit Tests

**New test file:** `tests/unit/test_intent_detector.py`

```python
class TestIntentDetector:
    """Tests for IntentDetector."""
    
    def test_detect_search_intent(self):
        """Test detection of search intent."""
        response = "I'll search the logs for errors now."
        intent = IntentDetector.detect_intent(response)
        
        assert intent is not None
        assert intent.intent_type == IntentType.SEARCH_LOGS
        assert intent.confidence >= 0.8
    
    def test_detect_list_intent(self):
        """Test detection of list log groups intent."""
        response = "Let me list the available log groups."
        intent = IntentDetector.detect_intent(response)
        
        assert intent is not None
        assert intent.intent_type == IntentType.LIST_GROUPS
    
    def test_no_intent_in_analysis(self):
        """Test that analysis statements don't trigger intent detection."""
        response = "Based on the logs, I can see several errors related to authentication."
        intent = IntentDetector.detect_intent(response)
        
        assert intent is None
    
    def test_detect_premature_giving_up(self):
        """Test detection of giving up patterns."""
        responses = [
            "No logs were found in the specified time range.",
            "I couldn't find any matching entries.",
            "Unfortunately, the search returned no results.",
        ]
        
        for response in responses:
            assert IntentDetector.detect_premature_giving_up(response) is True
    
    def test_no_giving_up_in_success(self):
        """Test that successful responses don't trigger giving up detection."""
        response = "I found 15 error logs in the specified time range."
        assert IntentDetector.detect_premature_giving_up(response) is False
```

**New test file:** `tests/unit/test_retry_logic.py`

```python
class TestRetryState:
    """Tests for RetryState."""
    
    def test_should_retry_under_limit(self):
        """Test retry allowed under limit."""
        state = RetryState(attempts=1)
        assert state.should_retry(max_attempts=3) is True
    
    def test_should_not_retry_at_limit(self):
        """Test retry blocked at limit."""
        state = RetryState(attempts=3)
        assert state.should_retry(max_attempts=3) is False
    
    def test_record_attempt(self):
        """Test recording retry attempts."""
        state = RetryState()
        state.record_attempt("fetch_logs", {"log_group": "/test"}, "empty_logs")
        
        assert state.attempts == 1
        assert state.last_tool_name == "fetch_logs"
        assert "empty_logs" in state.strategies_tried

class TestRetryPromptGenerator:
    """Tests for RetryPromptGenerator."""
    
    def test_generate_empty_logs_prompt(self):
        """Test empty logs retry prompt."""
        state = RetryState()
        prompt = RetryPromptGenerator.generate_retry_prompt("empty_logs", state)
        
        assert "Expand Time Range" in prompt
        assert "Broaden Filter" in prompt
    
    def test_prompt_includes_attempt_count(self):
        """Test that prompts include attempt context."""
        state = RetryState(attempts=2, strategies_tried=["expand_time", "broaden_filter"])
        prompt = RetryPromptGenerator.generate_retry_prompt("empty_logs", state)
        
        assert "attempt 3" in prompt
        assert "expand_time" in prompt


class TestResultAnalysis:
    """Tests for result analysis logic."""
    
    def test_detect_empty_fetch_logs_result(self):
        """Test detection of empty fetch_logs result."""
        orchestrator = create_test_orchestrator()
        state = RetryState()
        
        results = [{"result": {"success": True, "count": 0, "events": []}}]
        should_retry, reason = orchestrator._analyze_tool_results(results, state)
        
        assert should_retry is True
        assert reason == "empty_logs"
    
    def test_detect_log_group_not_found(self):
        """Test detection of log group not found error."""
        orchestrator = create_test_orchestrator()
        state = RetryState()
        
        results = [{"result": {"success": False, "error": "Log group not found"}}]
        should_retry, reason = orchestrator._analyze_tool_results(results, state)
        
        assert should_retry is True
        assert reason == "log_group_not_found"
    
    def test_no_retry_on_success_with_data(self):
        """Test no retry when results have data."""
        orchestrator = create_test_orchestrator()
        state = RetryState()
        
        results = [{"result": {"success": True, "count": 5, "events": [{"msg": "test"}]}}]
        should_retry, reason = orchestrator._analyze_tool_results(results, state)
        
        assert should_retry is False
```

### 9.2 Integration Tests

**New test file:** `tests/integration/test_self_direction.py`

```python
class TestSelfDirectionIntegration:
    """Integration tests for self-direction behavior."""
    
    @pytest.mark.asyncio
    async def test_retry_on_empty_logs(self):
        """Test that agent retries when logs are empty."""
        # Setup mock LLM that returns tool call, then empty result, then expanded search
        mock_provider = create_mock_provider([
            # First: tool call with narrow time range
            LLMResponse(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "function": {"name": "fetch_logs", "arguments": '{"log_group": "/test", "start_time": "1h ago"}'}
                }]
            ),
            # Second: after empty result and retry prompt, expanded time range
            LLMResponse(
                content="",
                tool_calls=[{
                    "id": "call_2", 
                    "function": {"name": "fetch_logs", "arguments": '{"log_group": "/test", "start_time": "24h ago"}'}
                }]
            ),
            # Third: final response with results
            LLMResponse(content="I found 5 errors in the expanded time range.")
        ])
        
        mock_registry = create_mock_registry([
            {"success": True, "count": 0, "events": []},  # First call: empty
            {"success": True, "count": 5, "events": [{"msg": "error"}]},  # Second call: results
        ])
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_provider,
            tool_registry=mock_registry,
            sanitizer=Mock(),
            settings=get_test_settings(),
        )
        
        result = await orchestrator.chat("Find errors in /test")
        
        assert "5 errors" in result
        assert mock_registry.execute.call_count == 2  # Retried once
    
    @pytest.mark.asyncio
    async def test_intent_without_action_triggers_retry(self):
        """Test that stated intent without tool call triggers nudge."""
        mock_provider = create_mock_provider([
            # First: states intent without calling tool
            LLMResponse(content="I'll search the logs for you."),
            # Second: after nudge, actually calls tool
            LLMResponse(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "function": {"name": "fetch_logs", "arguments": '{"log_group": "/test", "start_time": "1h ago"}'}
                }]
            ),
            # Third: final response
            LLMResponse(content="Here are the results...")
        ])
        
        orchestrator = LLMOrchestrator(...)
        result = await orchestrator.chat("Search for errors")
        
        assert mock_provider.chat.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_respects_max_retry_limit(self):
        """Test that retries stop at max limit."""
        mock_provider = create_mock_provider([
            # Always returns tool call with empty results
            LLMResponse(
                content="",
                tool_calls=[{"id": f"call_{i}", "function": {"name": "fetch_logs", "arguments": "{}"}}]
            ) for i in range(10)
        ] + [LLMResponse(content="No logs found after multiple attempts.")])
        
        mock_registry = create_mock_registry([
            {"success": True, "count": 0, "events": []} for _ in range(10)
        ])
        
        settings = get_test_settings()
        settings.max_retry_attempts = 3
        
        orchestrator = LLMOrchestrator(..., settings=settings)
        result = await orchestrator.chat("Find errors")
        
        # Should have tried original + 3 retries = 4 tool calls max
        assert mock_registry.execute.call_count <= 4
```

### 9.3 Scenario Tests

**Test scenarios to cover:**

| Scenario | Expected Behavior |
|----------|-------------------|
| Empty logs, expand time succeeds | Retry with expanded time, return results |
| Empty logs, all retries fail | Return graceful "no logs found" after 3 attempts |
| Log group not found | List groups, suggest alternative, try alternative |
| Intent stated without action | Nudge to execute, agent calls tool |
| Giving up too easily | Nudge to try alternatives |
| Already tried everything | Accept response, don't loop forever |
| User interrupts retry | Reset state, process new message |
| Rate limit during retry | Respect limit, continue after backoff |

---

## 10. Implementation Plan

### 10.1 Phase 1: Foundation (2-3 hours)

**Tasks:**
1. Create `src/logai/core/intent_detector.py` with IntentDetector class
2. Add RetryState dataclass to orchestrator
3. Add SelfDirectionSettings to settings.py
4. Write unit tests for IntentDetector

**Dependencies:** None

**Deliverables:**
- [ ] IntentDetector module with unit tests
- [ ] RetryState dataclass
- [ ] Configuration settings

### 10.2 Phase 2: System Prompt Enhancement (1-2 hours)

**Tasks:**
1. Update SYSTEM_PROMPT in orchestrator.py with self-direction instructions
2. Add documentation for new prompt sections
3. Test prompt effectiveness manually

**Dependencies:** None (can be done in parallel with Phase 1)

**Deliverables:**
- [ ] Enhanced system prompt
- [ ] Manual verification with test queries

### 10.3 Phase 3: Retry Logic Implementation (3-4 hours)

**Tasks:**
1. Implement RetryPromptGenerator class
2. Implement `_analyze_tool_results` method
3. Modify `_chat_complete` to integrate retry logic
4. Modify `_chat_stream` with same logic
5. Write unit tests for retry logic
6. Implement loop detection safeguards

**Dependencies:** Phase 1 (IntentDetector), Phase 2 (prompts)

**Deliverables:**
- [ ] RetryPromptGenerator with unit tests
- [ ] Result analysis with unit tests
- [ ] Modified conversation loops
- [ ] Loop detection logic

### 10.4 Phase 4: Integration & Testing (2-3 hours)

**Tasks:**
1. Write integration tests for end-to-end scenarios
2. Manual testing with various query types
3. Performance testing (ensure no significant latency increase)
4. Documentation updates

**Dependencies:** Phases 1-3

**Deliverables:**
- [ ] Integration test suite
- [ ] Performance benchmarks
- [ ] Updated documentation

### 10.5 Implementation Summary

```
Phase 1: Foundation          ████████████░░░░░░░░  2-3 hrs
Phase 2: System Prompt       ██████░░░░░░░░░░░░░░  1-2 hrs  
Phase 3: Retry Logic         ████████████████░░░░  3-4 hrs
Phase 4: Testing             ████████████░░░░░░░░  2-3 hrs
─────────────────────────────────────────────────────────
Total Estimated:                                   8-12 hrs
```

---

## 11. Risk Assessment

### 11.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Infinite loops from retry logic | Medium | High | Multiple safeguards: iteration limit, retry limit, loop detection |
| LLM ignores retry prompts | Medium | Medium | Fall back to original behavior, tune prompts |
| Increased latency | Low | Medium | Lazy evaluation, only retry when needed |
| Context window overflow | Low | Medium | Track token usage, summarize if needed |
| Different LLM providers behave differently | Medium | Medium | Test with Ollama, Claude, and OpenAI |

### 11.2 Product Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Over-aggressive retrying annoys users | Low | Medium | Configurable limits, respect user interruption |
| Retry logic increases API costs | Medium | Medium | Default limit of 3 retries, configurable |
| Intent detection false positives | Medium | Low | High confidence threshold (0.8+) |
| Breaking existing functionality | Low | High | Comprehensive test suite, feature flags |

### 11.3 Mitigation Strategies

1. **Feature Flags**
   - `auto_retry_enabled: bool` - Can disable entire feature
   - `intent_detection_enabled: bool` - Can disable intent detection separately

2. **Graceful Degradation**
   - All new features wrap in try/except
   - Failure falls back to original behavior
   - Logged for debugging

3. **Monitoring**
   - Log all retry attempts with structured logging
   - Track retry success rate
   - Monitor for infinite loop patterns

4. **User Control**
   - Users can interrupt at any time
   - Configuration to adjust retry limits
   - Clear indication when retrying

---

## Appendix: Code Examples

### A.1 Full Modified Orchestrator (Key Sections)

```python
# src/logai/core/orchestrator.py

from logai.core.intent_detector import IntentDetector
from logai.core.retry import RetryState, RetryPromptGenerator

class LLMOrchestrator:
    """Coordinates LLM interactions with tool execution."""

    MAX_TOOL_ITERATIONS = 10
    
    # Enhanced system prompt
    SYSTEM_PROMPT = """You are an expert observability assistant...
    
    ## Self-Direction & Persistence
    
    ### Automatic Retry Behavior
    When you encounter empty results or no matches, YOU MUST automatically try 
    alternative approaches before responding to the user:
    
    1. **Empty Log Results**
       - FIRST: Expand the time range (e.g., 1h -> 6h -> 24h -> 7d)
       - SECOND: Broaden or remove the filter pattern
       - THIRD: Try a different log group if available
       - ONLY after trying 2-3 alternatives, report findings to the user
    
    [... rest of enhanced prompt ...]
    """
    
    async def _chat_complete(self, user_message: str) -> str:
        # ... initialization ...
        
        retry_state = RetryState()
        
        while iteration < self.MAX_TOOL_ITERATIONS:
            # ... get LLM response ...
            
            if response.has_tool_calls():
                # ... execute tools ...
                
                # NEW: Analyze results for retry
                should_retry, reason = self._analyze_tool_results(results, retry_state)
                if should_retry and retry_state.should_retry(self.settings.max_retry_attempts):
                    messages.append({
                        "role": "system",
                        "content": RetryPromptGenerator.generate_retry_prompt(reason, retry_state)
                    })
                    retry_state.record_attempt(...)
                continue
            
            # NEW: Check for intent without action
            if self.settings.intent_detection_enabled:
                intent = IntentDetector.detect_intent(response.content)
                if intent and intent.confidence >= 0.8:
                    if retry_state.should_retry(self.settings.max_retry_attempts):
                        messages.append({
                            "role": "system", 
                            "content": RetryPromptGenerator.RETRY_PROMPTS["intent_without_action"]
                        })
                        continue
            
            # ... return response ...
```

### A.2 Example Test Fixture

```python
# tests/conftest.py

@pytest.fixture
def self_direction_settings():
    """Create settings with self-direction enabled."""
    return LogAISettings(
        llm_provider="anthropic",
        anthropic_api_key="test-key",
        max_retry_attempts=3,
        intent_detection_enabled=True,
        auto_retry_enabled=True,
    )

@pytest.fixture
def mock_empty_results_provider():
    """Create mock provider that returns empty results first, then data."""
    provider = AsyncMock()
    provider.chat.side_effect = [
        LLMResponse(
            tool_calls=[{"id": "1", "function": {"name": "fetch_logs", "arguments": "{}"}}]
        ),
        LLMResponse(
            tool_calls=[{"id": "2", "function": {"name": "fetch_logs", "arguments": "{}"}}]  
        ),
        LLMResponse(content="Found 5 errors after expanding search."),
    ]
    return provider
```

---

## Document Approval

| Role | Name | Status | Date |
|------|------|--------|------|
| Author | Sally (Architect) | Complete | 2026-02-11 |
| Reviewer | George (TPM) | Pending | - |
| Implementer | Jackie (Engineer) | Pending | - |

---

**End of Design Document**
