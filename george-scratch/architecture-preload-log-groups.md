# Architecture Design: Pre-load CloudWatch Log Groups at Startup

**Author:** Sally (Senior Software Architect)  
**Date:** February 12, 2026  
**Version:** 1.0  
**Status:** Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Component Design](#3-component-design)
4. [Data Flow](#4-data-flow)
5. [API Designs](#5-api-designs)
6. [System Prompt Strategy](#6-system-prompt-strategy)
7. [Integration Points](#7-integration-points)
8. [Error Handling](#8-error-handling)
9. [Performance Considerations](#9-performance-considerations)
10. [Implementation Guide](#10-implementation-guide)
11. [Testing Strategy](#11-testing-strategy)
12. [Risks and Trade-offs](#12-risks-and-trade-offs)

---

## 1. Executive Summary

This document describes the architecture for pre-loading all CloudWatch log groups at application startup and providing them to the LLM agent as initial context. The design introduces a new `LogGroupManager` component that handles fetching, caching, and formatting log groups, with clean integration into the existing orchestrator and UI systems.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| State Management | Dedicated `LogGroupManager` service | Single responsibility, testable, reusable |
| Dependency Pattern | Dependency injection (not singleton) | Better testability, explicit dependencies |
| System Prompt Strategy | Tiered approach based on count | Handles both small and large accounts |
| Context Update Mechanism | System message injection | Preserves conversation history, simple implementation |
| Refresh Command | `/refresh` with optional `--prefix` | Short, intuitive, flexible |
| Tool Availability | Keep `list_log_groups` tool | Agent can still do fresh lookups when needed |

---

## 2. System Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              LogAI CLI                                   │
│                            (Entry Point)                                 │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Startup Sequence                                 │
│  ┌──────────────┐    ┌─────────────────────┐    ┌───────────────────┐  │
│  │ Load Config  │───▶│ Initialize Services │───▶│ Pre-load Log      │  │
│  │              │    │                     │    │ Groups            │  │
│  └──────────────┘    └─────────────────────┘    └─────────┬─────────┘  │
└───────────────────────────────────────────────────────────┼─────────────┘
                                                            │
                          ┌─────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       LogGroupManager (NEW)                              │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • fetch_all_log_groups() - Paginated fetch from CloudWatch      │  │
│  │  • format_for_prompt() - Format for system prompt (tiered)       │  │
│  │  • refresh() - Re-fetch and update                               │  │
│  │  • get_log_groups() - Access current list                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  State: log_groups: list[LogGroupInfo], last_refresh: datetime         │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
          ┌──────────────────────┴──────────────────────┐
          │                                             │
          ▼                                             ▼
┌─────────────────────────┐               ┌─────────────────────────┐
│    LLMOrchestrator      │               │      ChatScreen         │
│  (Modified)             │               │     (Modified)          │
│                         │               │                         │
│  • Accepts LogGroupMgr  │               │  • Handles /refresh     │
│  • Enhanced system      │               │  • Shows progress       │
│    prompt with log      │               │  • Updates agent        │
│    group context        │               │    context              │
│  • inject_context()     │               │                         │
│    method for updates   │               │                         │
└─────────────────────────┘               └─────────────────────────┘
```

### 2.2 Component Relationships

```
┌──────────────┐     creates      ┌───────────────────┐
│   cli.py     │─────────────────▶│  LogGroupManager  │
└──────┬───────┘                  └─────────┬─────────┘
       │                                    │
       │ passes                             │ uses
       ▼                                    ▼
┌──────────────────┐              ┌───────────────────┐
│  LLMOrchestrator │◀─────────────│CloudWatchDataSrc  │
└──────┬───────────┘   log groups └───────────────────┘
       │
       │ orchestrator
       ▼
┌──────────────────┐     ref      ┌───────────────────┐
│    LogAIApp      │─────────────▶│  LogGroupManager  │
└──────┬───────────┘              └───────────────────┘
       │
       │ pushes
       ▼
┌──────────────────┐
│   ChatScreen     │────────────▶ Handles /refresh command
└──────────────────┘
```

---

## 3. Component Design

### 3.1 LogGroupManager (New Component)

**Location:** `src/logai/core/log_group_manager.py`

**Purpose:** Central manager for pre-loaded log group data. Responsible for:
- Fetching all log groups with full pagination
- Storing log group metadata in memory
- Formatting log groups for system prompt injection
- Providing refresh capabilities
- Progress callback support for UI feedback

**Design Pattern:** Service class with dependency injection

```python
# src/logai/core/log_group_manager.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from enum import Enum

from logai.providers.datasources.cloudwatch import CloudWatchDataSource


class LogGroupManagerState(Enum):
    """State of the log group manager."""
    UNINITIALIZED = "uninitialized"
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"


@dataclass
class LogGroupInfo:
    """
    Lightweight representation of a CloudWatch log group.
    
    Stores only essential information to minimize memory footprint.
    """
    name: str
    created: int | None = None  # Epoch milliseconds
    stored_bytes: int = 0
    retention_days: int | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogGroupInfo":
        """Create LogGroupInfo from CloudWatch API response dict."""
        return cls(
            name=data["name"],
            created=data.get("created"),
            stored_bytes=data.get("stored_bytes", 0),
            retention_days=data.get("retention_days"),
        )


@dataclass
class LogGroupManagerResult:
    """Result of a log group fetch operation."""
    success: bool
    log_groups: list[LogGroupInfo] = field(default_factory=list)
    count: int = 0
    error_message: str | None = None
    duration_ms: int = 0


# Type alias for progress callback
ProgressCallback = Callable[[int, str], None]  # (count, message)


class LogGroupManager:
    """
    Manages pre-loaded CloudWatch log groups.
    
    This class handles fetching all log groups at startup and provides
    methods for refreshing and formatting the list for LLM consumption.
    
    Example:
        manager = LogGroupManager(datasource)
        await manager.load_all(progress_callback=lambda c, m: print(f"{m}: {c}"))
        prompt_section = manager.format_for_prompt()
    """
    
    # Threshold for switching from full list to summary in prompt
    FULL_LIST_THRESHOLD = 500
    
    # Maximum log groups to sample in summary mode
    SUMMARY_SAMPLE_SIZE = 100
    
    def __init__(self, datasource: CloudWatchDataSource) -> None:
        """
        Initialize LogGroupManager.
        
        Args:
            datasource: CloudWatch data source for API calls
        """
        self.datasource = datasource
        self._log_groups: list[LogGroupInfo] = []
        self._state = LogGroupManagerState.UNINITIALIZED
        self._last_refresh: datetime | None = None
        self._last_error: str | None = None
    
    @property
    def state(self) -> LogGroupManagerState:
        """Get current manager state."""
        return self._state
    
    @property
    def log_groups(self) -> list[LogGroupInfo]:
        """Get current log groups list (read-only copy)."""
        return self._log_groups.copy()
    
    @property
    def count(self) -> int:
        """Get count of loaded log groups."""
        return len(self._log_groups)
    
    @property
    def last_refresh(self) -> datetime | None:
        """Get timestamp of last successful refresh."""
        return self._last_refresh
    
    @property
    def is_ready(self) -> bool:
        """Check if log groups are loaded and ready."""
        return self._state == LogGroupManagerState.READY
    
    async def load_all(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> LogGroupManagerResult:
        """
        Load all log groups from CloudWatch with full pagination.
        
        This method fetches ALL log groups without any limit, handling
        pagination automatically. Progress updates are provided via callback.
        
        Args:
            progress_callback: Optional callback for progress updates.
                              Called with (count, message) during loading.
        
        Returns:
            LogGroupManagerResult with success status and loaded groups
        
        Note:
            This method is safe to call multiple times - it will replace
            the existing list with fresh data.
        """
        import time
        start_time = time.monotonic()
        
        self._state = LogGroupManagerState.LOADING
        self._last_error = None
        
        if progress_callback:
            progress_callback(0, "Starting log group discovery...")
        
        try:
            all_groups: list[LogGroupInfo] = []
            
            # Use the datasource's internal sync method for full pagination
            # We need to bypass the limit parameter to get ALL groups
            loop = asyncio.get_event_loop()
            raw_groups = await loop.run_in_executor(
                None,
                self._fetch_all_log_groups_sync,
                progress_callback,
            )
            
            # Convert to LogGroupInfo objects
            for raw in raw_groups:
                all_groups.append(LogGroupInfo.from_dict(raw))
            
            # Update state
            self._log_groups = all_groups
            self._state = LogGroupManagerState.READY
            self._last_refresh = datetime.now(timezone.utc)
            
            duration_ms = int((time.monotonic() - start_time) * 1000)
            
            if progress_callback:
                progress_callback(len(all_groups), "Log group discovery complete")
            
            return LogGroupManagerResult(
                success=True,
                log_groups=all_groups,
                count=len(all_groups),
                duration_ms=duration_ms,
            )
            
        except Exception as e:
            self._state = LogGroupManagerState.ERROR
            self._last_error = str(e)
            
            duration_ms = int((time.monotonic() - start_time) * 1000)
            
            return LogGroupManagerResult(
                success=False,
                error_message=str(e),
                duration_ms=duration_ms,
            )
    
    def _fetch_all_log_groups_sync(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> list[dict[str, Any]]:
        """
        Synchronous implementation that fetches ALL log groups.
        
        This bypasses the limit parameter in the datasource to get
        complete pagination.
        """
        paginator = self.datasource.client.get_paginator("describe_log_groups")
        log_groups: list[dict[str, Any]] = []
        
        for page in paginator.paginate():
            for lg in page["logGroups"]:
                log_groups.append({
                    "name": lg["logGroupName"],
                    "created": lg.get("creationTime"),
                    "stored_bytes": lg.get("storedBytes", 0),
                    "retention_days": lg.get("retentionInDays"),
                })
            
            # Progress update after each page
            if progress_callback:
                # Use call_soon_threadsafe if we need thread safety
                progress_callback(len(log_groups), f"Loading... ({len(log_groups)} found)")
        
        return log_groups
    
    async def refresh(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> LogGroupManagerResult:
        """
        Refresh the log groups list.
        
        This is an alias for load_all() - it performs a complete refresh
        of all log groups.
        
        Args:
            progress_callback: Optional callback for progress updates
        
        Returns:
            LogGroupManagerResult with refresh results
        """
        return await self.load_all(progress_callback=progress_callback)
    
    def format_for_prompt(self) -> str:
        """
        Format log groups for inclusion in LLM system prompt.
        
        Uses a tiered strategy based on the number of log groups:
        - Small lists (<=500): Include full list with names only
        - Large lists (>500): Include summary with sample and categories
        
        Returns:
            Formatted string for system prompt injection
        """
        if not self._log_groups:
            return self._format_empty_state()
        
        if len(self._log_groups) <= self.FULL_LIST_THRESHOLD:
            return self._format_full_list()
        else:
            return self._format_summary()
    
    def _format_empty_state(self) -> str:
        """Format message when no log groups are loaded."""
        if self._state == LogGroupManagerState.ERROR:
            return f"""## Log Groups Status
            
**Status:** Failed to load log groups at startup
**Error:** {self._last_error}

You should use the `list_log_groups` tool to discover available log groups.
"""
        elif self._state == LogGroupManagerState.UNINITIALIZED:
            return """## Log Groups Status

**Status:** Log groups not yet loaded

Use the `list_log_groups` tool to discover available log groups.
"""
        else:
            return """## Log Groups Status

**Status:** No log groups found in this AWS account/region

The AWS account appears to have no CloudWatch log groups, or you may not have 
permission to list them. Verify your AWS credentials and permissions.
"""
    
    def _format_full_list(self) -> str:
        """Format complete list of log groups for small accounts."""
        # Sort alphabetically for easier scanning
        sorted_groups = sorted(self._log_groups, key=lambda g: g.name)
        
        # Build the list - names only to save tokens
        group_list = "\n".join(f"- {g.name}" for g in sorted_groups)
        
        refresh_time = self._last_refresh.strftime("%Y-%m-%d %H:%M:%S UTC") if self._last_refresh else "Unknown"
        
        return f"""## Available Log Groups

**Total:** {len(self._log_groups)} log groups
**Last Updated:** {refresh_time}

{group_list}

### Usage Instructions
- Use these log group names directly when fetching or searching logs
- This list is your primary reference - no need to call `list_log_groups` unless user requests fresh lookup
- If a log group name doesn't match exactly, suggest the closest match from this list
- User can refresh this list with the `/refresh` command
"""
    
    def _format_summary(self) -> str:
        """Format summary for large accounts with many log groups."""
        # Categorize by common prefixes
        categories = self._categorize_log_groups()
        
        # Get a representative sample
        sample = self._get_representative_sample()
        
        refresh_time = self._last_refresh.strftime("%Y-%m-%d %H:%M:%S UTC") if self._last_refresh else "Unknown"
        
        # Build categories summary
        category_lines = []
        for prefix, count in sorted(categories.items(), key=lambda x: -x[1])[:15]:
            category_lines.append(f"- `{prefix}*`: {count} log groups")
        
        categories_text = "\n".join(category_lines)
        
        # Build sample list
        sample_text = "\n".join(f"- {g.name}" for g in sample)
        
        return f"""## Available Log Groups

**Total:** {len(self._log_groups)} log groups
**Last Updated:** {refresh_time}

### Log Group Categories
{categories_text}

### Sample Log Groups (showing {len(sample)} of {len(self._log_groups)})
{sample_text}

### Usage Instructions
- The full list of {len(self._log_groups)} log groups is available but too large to display
- Use the category prefixes above to understand what's available
- For specific lookups, use `list_log_groups` with a prefix filter
- Common prefixes: `/aws/lambda/`, `/aws/apigateway/`, `/ecs/`, `/aws/rds/`
- User can refresh this list with the `/refresh` command
- When user mentions a service, match it to the appropriate prefix category
"""
    
    def _categorize_log_groups(self) -> dict[str, int]:
        """Categorize log groups by common prefixes."""
        categories: dict[str, int] = {}
        
        # Common AWS prefixes to look for
        known_prefixes = [
            "/aws/lambda/",
            "/aws/apigateway/",
            "/aws/rds/",
            "/aws/eks/",
            "/ecs/",
            "/aws/elasticbeanstalk/",
            "/aws/codebuild/",
            "/aws/batch/",
            "/aws/kinesisfirehose/",
            "/aws/vendedlogs/",
        ]
        
        for group in self._log_groups:
            matched = False
            for prefix in known_prefixes:
                if group.name.startswith(prefix):
                    categories[prefix] = categories.get(prefix, 0) + 1
                    matched = True
                    break
            
            if not matched:
                # Try to extract a meaningful prefix
                parts = group.name.split("/")
                if len(parts) >= 3:
                    prefix = "/".join(parts[:3]) + "/"
                elif len(parts) >= 2:
                    prefix = "/".join(parts[:2]) + "/"
                else:
                    prefix = "(other)"
                categories[prefix] = categories.get(prefix, 0) + 1
        
        return categories
    
    def _get_representative_sample(self) -> list[LogGroupInfo]:
        """Get a representative sample of log groups for display."""
        if len(self._log_groups) <= self.SUMMARY_SAMPLE_SIZE:
            return sorted(self._log_groups, key=lambda g: g.name)
        
        # Get samples from each category to ensure diversity
        categories = self._categorize_log_groups()
        sample: list[LogGroupInfo] = []
        
        # Allocate samples proportionally to category size
        total = len(self._log_groups)
        for prefix, count in sorted(categories.items(), key=lambda x: -x[1]):
            # How many from this category?
            allocation = max(1, int(self.SUMMARY_SAMPLE_SIZE * count / total))
            
            # Get groups matching this prefix
            matching = [g for g in self._log_groups if g.name.startswith(prefix)]
            
            # Take first N (sorted)
            matching.sort(key=lambda g: g.name)
            sample.extend(matching[:allocation])
            
            if len(sample) >= self.SUMMARY_SAMPLE_SIZE:
                break
        
        # Sort final sample
        sample.sort(key=lambda g: g.name)
        return sample[:self.SUMMARY_SAMPLE_SIZE]
    
    def get_log_group_names(self) -> list[str]:
        """Get list of log group names only."""
        return [g.name for g in self._log_groups]
    
    def find_matching_groups(self, pattern: str) -> list[LogGroupInfo]:
        """
        Find log groups matching a pattern (prefix or substring).
        
        Args:
            pattern: Pattern to match (case-insensitive)
        
        Returns:
            List of matching LogGroupInfo objects
        """
        pattern_lower = pattern.lower()
        return [
            g for g in self._log_groups 
            if pattern_lower in g.name.lower()
        ]
    
    def get_stats(self) -> dict[str, Any]:
        """Get statistics about loaded log groups."""
        if not self._log_groups:
            return {
                "count": 0,
                "state": self._state.value,
                "last_refresh": None,
                "total_bytes": 0,
                "categories": {},
            }
        
        return {
            "count": len(self._log_groups),
            "state": self._state.value,
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
            "total_bytes": sum(g.stored_bytes for g in self._log_groups),
            "categories": self._categorize_log_groups(),
        }


# Need to import asyncio at module level
import asyncio
```

### 3.2 LLMOrchestrator Modifications

**Location:** `src/logai/core/orchestrator.py`

**Changes Required:**
1. Accept `LogGroupManager` as optional dependency
2. Modify `_get_system_prompt()` to include log group context
3. Add `inject_context()` method for runtime context updates

```python
# Modified sections of orchestrator.py

class LLMOrchestrator:
    """
    Coordinates LLM interactions with tool execution.
    """

    # Updated system prompt template with placeholder for log groups
    SYSTEM_PROMPT = """You are an expert observability assistant helping DevOps engineers and SREs analyze logs and troubleshoot issues.

## Your Capabilities
You have access to tools to fetch and analyze logs from AWS CloudWatch. Use these tools to help users:
- Find and analyze log entries
- Identify error patterns and root causes
- Correlate events across services
- Provide actionable insights

{log_groups_context}

## Guidelines

### Tool Usage
1. When a user asks about logs, use your pre-loaded log group list as reference
2. Only use the list_log_groups tool if the user explicitly requests a fresh lookup
3. Use appropriate time ranges - start narrow and expand if needed
4. Use filter patterns to reduce data volume when searching for specific issues
5. Fetch logs before attempting analysis

### Response Style
1. Be concise but thorough
2. Highlight important findings (errors, patterns, anomalies)
3. Provide actionable recommendations when possible
4. Use code blocks for log excerpts
5. Summarize large result sets

### Error Handling
1. If a log group doesn't exist in your list, suggest alternatives from the list
2. If no logs found, suggest adjusting time range or filters
3. Explain any limitations clearly

## Self-Direction & Persistence
[... rest of existing prompt ...]

## Context
Current time: {current_time}
"""

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        tool_registry: ToolRegistry,
        sanitizer: LogSanitizer,
        settings: LogAISettings,
        cache: CacheManager | None = None,
        metrics_collector: MetricsCollector | None = None,
        log_group_manager: "LogGroupManager | None" = None,  # NEW
    ):
        """
        Initialize LLM orchestrator.

        Args:
            llm_provider: LLM provider instance
            tool_registry: Tool registry with available tools
            sanitizer: PII sanitizer instance
            settings: Application settings
            cache: Optional cache manager
            metrics_collector: Optional metrics collector for monitoring
            log_group_manager: Optional pre-loaded log group manager  # NEW
        """
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.sanitizer = sanitizer
        self.settings = settings
        self.cache = cache
        self.conversation_history: list[dict[str, Any]] = []
        self.metrics = metrics_collector or MetricsCollector()
        self.log_group_manager = log_group_manager  # NEW

        # Tool call listeners for sidebar integration
        self.tool_call_listeners: list[Callable[[Any], None]] = []
        
        # Runtime context injections (for /refresh updates)
        self._pending_context_injection: str | None = None  # NEW

    def _get_system_prompt(self) -> str:
        """
        Get the system prompt with current context.

        Returns:
            Formatted system prompt including log group context
        """
        now = datetime.now(timezone.utc)
        
        # Get log groups context from manager if available
        if self.log_group_manager and self.log_group_manager.is_ready:
            log_groups_context = self.log_group_manager.format_for_prompt()
        else:
            log_groups_context = """## Log Groups
            
Log groups will be discovered via the `list_log_groups` tool.
Use this tool to find available log groups before querying logs."""
        
        return self.SYSTEM_PROMPT.format(
            current_time=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            log_groups_context=log_groups_context,
        )

    def inject_context_update(self, context_message: str) -> None:
        """
        Inject a context update to be included in the next LLM call.
        
        This is used to update the agent's knowledge mid-conversation,
        such as after a /refresh command updates the log group list.
        
        Args:
            context_message: Message to inject as system context
        """
        self._pending_context_injection = context_message

    def _get_pending_context_injection(self) -> str | None:
        """Get and clear any pending context injection."""
        injection = self._pending_context_injection
        self._pending_context_injection = None
        return injection
    
    # In _chat_complete and _chat_stream, add context injection handling:
    # After building messages list, before LLM call:
    #
    # # Check for pending context injection
    # pending_injection = self._get_pending_context_injection()
    # if pending_injection:
    #     messages.append({
    #         "role": "system", 
    #         "content": pending_injection
    #     })
```

### 3.3 CommandHandler Modifications

**Location:** `src/logai/ui/commands.py`

**Changes Required:**
1. Accept `LogGroupManager` as dependency
2. Add `/refresh` command handler

```python
# Modified sections of commands.py

class CommandHandler:
    """Handles special slash commands in the chat."""

    def __init__(
        self,
        orchestrator: LLMOrchestrator,
        cache_manager: CacheManager,
        settings: LogAISettings,
        chat_screen: "ChatScreen | None" = None,
        log_group_manager: "LogGroupManager | None" = None,  # NEW
    ) -> None:
        """
        Initialize command handler.

        Args:
            orchestrator: LLM orchestrator instance
            cache_manager: Cache manager instance
            settings: Application settings
            chat_screen: Optional reference to chat screen for UI commands
            log_group_manager: Optional log group manager for refresh  # NEW
        """
        self.orchestrator = orchestrator
        self.cache_manager = cache_manager
        self.settings = settings
        self.chat_screen = chat_screen
        self.log_group_manager = log_group_manager  # NEW

    async def handle_command(self, command: str) -> str:
        """
        Handle a special command.

        Args:
            command: Command string (including the /)

        Returns:
            Response message
        """
        command = command.strip()
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/help":
            return self._show_help()
        elif cmd == "/clear":
            return self._clear_history()
        elif cmd == "/refresh":  # NEW
            return await self._refresh_log_groups(args)
        elif cmd == "/cache":
            # ... existing cache handling
            pass
        # ... rest of existing commands

    async def _refresh_log_groups(self, args: str) -> str:  # NEW
        """
        Refresh the pre-loaded log groups list.
        
        Args:
            args: Optional arguments (e.g., "--prefix /aws/lambda/")
        
        Returns:
            Status message
        """
        if not self.log_group_manager:
            return "[red]Error:[/red] Log group manager not initialized."
        
        # Parse optional prefix argument
        prefix = None
        if args:
            if args.startswith("--prefix "):
                prefix = args[9:].strip()
            elif args.startswith("-p "):
                prefix = args[3:].strip()
            else:
                return f"[red]Unknown argument:[/red] {args}\nUsage: /refresh [--prefix <prefix>]"
        
        # Track progress - we'll update via callback
        progress_messages: list[str] = []
        
        def progress_callback(count: int, message: str) -> None:
            progress_messages.append(f"{message}")
        
        # Show initial message
        if self.chat_screen:
            # We'll handle progress display via the chat screen
            pass
        
        # Perform refresh
        result = await self.log_group_manager.refresh(
            progress_callback=progress_callback
        )
        
        if result.success:
            # Calculate diff if we had previous data
            count = result.count
            duration_sec = result.duration_ms / 1000
            
            # Inject context update to orchestrator
            refresh_notice = f"""## Log Groups Updated

The log group list has been refreshed. You now have access to {count} log groups.
Please use this updated list for subsequent queries. The previous list is now outdated.

{self.log_group_manager.format_for_prompt()}
"""
            self.orchestrator.inject_context_update(refresh_notice)
            
            return f"""[green]Log groups refreshed successfully![/green]

[bold]Found:[/bold] {count} log groups
[bold]Duration:[/bold] {duration_sec:.1f}s

The agent's context has been updated with the new list."""
        else:
            return f"""[red]Failed to refresh log groups[/red]

[bold]Error:[/bold] {result.error_message}

The previous log group list (if any) has been preserved."""

    def _show_help(self) -> str:
        """Show help message with available commands."""
        return """[bold]Available Commands:[/bold]

[cyan]/help[/cyan] - Show this help message
[cyan]/clear[/cyan] - Clear conversation history
[cyan]/refresh[/cyan] - Refresh the log groups list from AWS
[cyan]/cache status[/cyan] - Show cache statistics
[cyan]/cache clear[/cyan] - Clear the cache
[cyan]/model[/cyan] - Show current LLM model
[cyan]/config[/cyan] - Show current configuration
[cyan]/tools[/cyan] - Toggle tool calls sidebar
[cyan]/quit[/cyan] or [cyan]/exit[/cyan] - Exit the application (or use Ctrl+C)

[bold]Usage Tips:[/bold]
- Ask questions in natural language about your CloudWatch logs
- The assistant will use tools to fetch and analyze logs for you
- Log groups are pre-loaded at startup - use /refresh to update
- Responses are streamed in real-time
- PII sanitization is enabled by default
"""
```

### 3.4 CLI Modifications

**Location:** `src/logai/cli.py`

**Changes Required:**
1. Initialize `LogGroupManager` after datasource
2. Call `load_all()` during startup
3. Pass manager to orchestrator and app
4. Display progress during loading

```python
# Modified main() function in cli.py

def main() -> int:
    """Main CLI entry point."""
    # ... existing argument parsing and config loading ...

    try:
        # Initialize components
        datasource = CloudWatchDataSource(settings)
        sanitizer = LogSanitizer(enabled=settings.pii_sanitization_enabled)
        cache_manager = CacheManager(settings)

        # Import and register tools
        from logai.core.tools.cloudwatch_tools import (
            FetchLogsTool,
            ListLogGroupsTool,
            SearchLogsTool,
        )

        # Register tools in the registry
        ToolRegistry.register(ListLogGroupsTool(datasource, settings, cache=cache_manager))
        ToolRegistry.register(FetchLogsTool(datasource, sanitizer, settings, cache=cache_manager))
        ToolRegistry.register(SearchLogsTool(datasource, sanitizer, settings, cache=cache_manager))

        # === NEW: Pre-load log groups ===
        from logai.core.log_group_manager import LogGroupManager
        
        log_group_manager = LogGroupManager(datasource)
        
        # Define progress callback for CLI output
        def show_progress(count: int, message: str) -> None:
            # Use carriage return to update in place
            print(f"\r  {message}", end="", flush=True)
        
        print("  Loading log groups from AWS...", end="", flush=True)
        
        # Run async load synchronously
        import asyncio
        result = asyncio.run(log_group_manager.load_all(progress_callback=show_progress))
        
        if result.success:
            print(f"\r✓ Found {result.count} log groups ({result.duration_ms}ms)          ")
        else:
            print(f"\r⚠ Failed to load log groups: {result.error_message}          ")
            print("  Agent will discover log groups via tools")
        # === END NEW ===

        # Initialize LLM provider
        llm_provider = LiteLLMProvider.from_settings(settings)

        # Initialize orchestrator (modified to accept log_group_manager)
        orchestrator = LLMOrchestrator(
            llm_provider=llm_provider,
            tool_registry=ToolRegistry,
            sanitizer=sanitizer,
            settings=settings,
            cache=cache_manager,
            log_group_manager=log_group_manager,  # NEW
        )

        print("✓ All components initialized")
        print("\nStarting TUI...\n")

        # Start TUI (modified to accept log_group_manager)
        app = LogAIApp(orchestrator, cache_manager, log_group_manager)  # MODIFIED
        app.run()

        return 0

    except Exception as e:
        print(f"❌ Failed to initialize: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
```

---

## 4. Data Flow

### 4.1 Startup Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           STARTUP SEQUENCE                                   │
└─────────────────────────────────────────────────────────────────────────────┘

1. User runs: logai --aws-profile myprofile
   │
   ▼
2. CLI loads configuration
   │ - Validates AWS credentials
   │ - Validates LLM API keys
   │
   ▼
3. CLI initializes CloudWatchDataSource
   │ - Creates boto3 client with credentials
   │
   ▼
4. CLI initializes LogGroupManager(datasource)
   │
   ▼
5. CLI calls log_group_manager.load_all()  ──────────────────────────┐
   │                                                                  │
   │  ┌─────────────────────────────────────────────────────────────┐│
   │  │              PAGINATION LOOP (in executor)                  ││
   │  │                                                             ││
   │  │  for page in paginator.paginate():                         ││
   │  │      for log_group in page["logGroups"]:                   ││
   │  │          append to list                                     ││
   │  │      progress_callback(count, "Loading...")                ││
   │  │                                                             ││
   │  └─────────────────────────────────────────────────────────────┘│
   │                                                                  │
   │  User sees: "  Loading log groups from AWS... (150 found)"      │
   │                                                                  │
   ◀──────────────────────────────────────────────────────────────────┘
   │
   ▼
6. CLI displays result:
   │  "✓ Found 234 log groups (1523ms)"
   │
   ▼
7. CLI initializes LLMOrchestrator(log_group_manager=log_group_manager)
   │
   ▼
8. CLI initializes LogAIApp(orchestrator, cache, log_group_manager)
   │
   ▼
9. TUI starts, ChatScreen mounts
   │ - Welcome message shown
   │
   ▼
10. User sends first query
    │
    ▼
11. Orchestrator builds system prompt
    │ - Calls log_group_manager.format_for_prompt()
    │ - Inserts log group list into prompt
    │
    ▼
12. LLM receives full context including available log groups
```

### 4.2 Refresh Command Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           /REFRESH FLOW                                      │
└─────────────────────────────────────────────────────────────────────────────┘

1. User types: /refresh
   │
   ▼
2. ChatScreen.on_input_submitted()
   │ - Detects "/" prefix
   │ - Routes to CommandHandler.handle_command()
   │
   ▼
3. CommandHandler._refresh_log_groups()
   │
   ▼
4. Calls log_group_manager.refresh()  ──────────────────────────────┐
   │                                                                 │
   │  ┌────────────────────────────────────────────────────────────┐│
   │  │                  AWS API CALLS                             ││
   │  │                                                            ││
   │  │  - Paginate through all log groups                        ││
   │  │  - Update internal state                                   ││
   │  │  - Set _last_refresh timestamp                            ││
   │  │                                                            ││
   │  └────────────────────────────────────────────────────────────┘│
   │                                                                 │
   ◀─────────────────────────────────────────────────────────────────┘
   │
   ▼
5. On success:
   │ a. Generate refresh notice with updated list
   │ b. Call orchestrator.inject_context_update(notice)
   │
   ▼
6. Return success message to user:
   │  "✓ Log groups refreshed successfully! Found: 245 log groups"
   │
   ▼
7. User sends next query
   │
   ▼
8. Orchestrator._chat_complete() or _chat_stream()
   │ a. Build messages with system prompt
   │ b. Check for pending injection: _get_pending_context_injection()
   │ c. If injection exists, append as system message
   │
   ▼
9. LLM receives:
   - Original system prompt (with old list in context)
   - Conversation history
   - Injected system message: "Log group list updated. New list: ..."
   │
   ▼
10. LLM uses updated log group information for response
```

### 4.3 Query Flow with Pre-loaded Context

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER QUERY FLOW                                      │
└─────────────────────────────────────────────────────────────────────────────┘

User: "Show me errors from my payment service logs in the last hour"
   │
   ▼
ChatScreen._process_message()
   │
   ▼
Orchestrator.chat_stream()
   │
   ▼
Build messages:
┌────────────────────────────────────────────────────────────────────────────┐
│  messages = [                                                              │
│    {                                                                       │
│      "role": "system",                                                     │
│      "content": "You are an expert observability assistant...\n\n"        │
│                 "## Available Log Groups\n"                                │
│                 "**Total:** 234 log groups\n"                             │
│                 "- /aws/lambda/payment-service\n"                         │
│                 "- /aws/lambda/payment-processor\n"                       │
│                 "- /ecs/payment-api\n"                                    │
│                 "... (full list)\n\n"                                     │
│                 "### Usage Instructions\n"                                │
│                 "- Use these log group names directly..."                 │
│    },                                                                      │
│    {"role": "user", "content": "Show me errors from payment service..."}  │
│  ]                                                                         │
└────────────────────────────────────────────────────────────────────────────┘
   │
   ▼
LLM Response:
   "I can see several payment-related log groups in the list:
    - /aws/lambda/payment-service
    - /aws/lambda/payment-processor  
    - /ecs/payment-api
    
    Let me search for errors in these log groups..."
   │
   ▼
LLM calls: fetch_logs(log_group="/aws/lambda/payment-service", 
                      start_time="1h ago", 
                      filter_pattern="ERROR")
   │
   ▼
Tool executes, returns results
   │
   ▼
LLM analyzes and responds to user

=== KEY BENEFIT ===
LLM did NOT need to call list_log_groups first!
It used the pre-loaded list to identify relevant log groups immediately.
```

---

## 5. API Designs

### 5.1 LogGroupManager API

```python
class LogGroupManager:
    """
    Manager for pre-loaded CloudWatch log groups.
    
    Properties:
        state: LogGroupManagerState - Current state of the manager
        log_groups: list[LogGroupInfo] - Read-only copy of loaded groups
        count: int - Number of loaded log groups
        last_refresh: datetime | None - When groups were last loaded
        is_ready: bool - Whether groups are loaded and ready
    
    Methods:
        async load_all(progress_callback) -> LogGroupManagerResult
        async refresh(progress_callback) -> LogGroupManagerResult
        format_for_prompt() -> str
        get_log_group_names() -> list[str]
        find_matching_groups(pattern) -> list[LogGroupInfo]
        get_stats() -> dict[str, Any]
    """
```

### 5.2 LogGroupInfo Data Class

```python
@dataclass
class LogGroupInfo:
    """
    Lightweight representation of a CloudWatch log group.
    
    Attributes:
        name: str - Log group name (e.g., "/aws/lambda/my-function")
        created: int | None - Creation timestamp in epoch milliseconds
        stored_bytes: int - Total stored bytes (0 if unknown)
        retention_days: int | None - Retention period in days (None = never expire)
    """
    name: str
    created: int | None = None
    stored_bytes: int = 0
    retention_days: int | None = None
```

### 5.3 LogGroupManagerResult Data Class

```python
@dataclass
class LogGroupManagerResult:
    """
    Result of a log group fetch/refresh operation.
    
    Attributes:
        success: bool - Whether the operation succeeded
        log_groups: list[LogGroupInfo] - Loaded log groups (empty on failure)
        count: int - Number of log groups loaded
        error_message: str | None - Error details if success is False
        duration_ms: int - Operation duration in milliseconds
    """
    success: bool
    log_groups: list[LogGroupInfo] = field(default_factory=list)
    count: int = 0
    error_message: str | None = None
    duration_ms: int = 0
```

### 5.4 Orchestrator New Methods

```python
class LLMOrchestrator:
    def inject_context_update(self, context_message: str) -> None:
        """
        Inject a context update to be included in the next LLM call.
        
        The injected message will be added as a system message after the
        main system prompt but before the conversation continues.
        
        Args:
            context_message: Message to inject (typically a context update)
        
        Note:
            Only one injection can be pending at a time. New injections
            overwrite previous pending injections.
        """
        pass
```

### 5.5 Command Handler New Methods

```python
class CommandHandler:
    async def _refresh_log_groups(self, args: str) -> str:
        """
        Handle the /refresh command.
        
        Args:
            args: Command arguments (supports "--prefix <prefix>")
        
        Returns:
            Status message with rich formatting
        
        Side Effects:
            - Refreshes log groups in LogGroupManager
            - Injects context update into orchestrator
        """
        pass
```

---

## 6. System Prompt Strategy

### 6.1 Tiered Approach

The system prompt strategy adapts to the number of log groups to balance context quality with token efficiency.

| Log Group Count | Strategy | Rationale |
|----------------|----------|-----------|
| 0 (error/empty) | Error message + tool instruction | User needs to know something went wrong |
| 1-500 | Full list (names only) | Easily fits in context, provides complete info |
| 501+ | Summary with categories + sample | Too large for full list; categories help navigation |

### 6.2 Full List Format (<=500 groups)

```markdown
## Available Log Groups

**Total:** 234 log groups
**Last Updated:** 2026-02-12 14:30:00 UTC

- /aws/apigateway/my-api
- /aws/lambda/auth-service
- /aws/lambda/payment-processor
- /aws/lambda/user-service
- /ecs/backend-api
- /ecs/frontend-web
... (all 234 groups listed)

### Usage Instructions
- Use these log group names directly when fetching or searching logs
- This list is your primary reference - no need to call `list_log_groups` unless user requests fresh lookup
- If a log group name doesn't match exactly, suggest the closest match from this list
- User can refresh this list with the `/refresh` command
```

### 6.3 Summary Format (>500 groups)

```markdown
## Available Log Groups

**Total:** 2,847 log groups
**Last Updated:** 2026-02-12 14:30:00 UTC

### Log Group Categories
- `/aws/lambda/*`: 1,245 log groups
- `/aws/apigateway/*`: 523 log groups
- `/ecs/*`: 412 log groups
- `/aws/rds/*`: 156 log groups
- `/aws/codebuild/*`: 89 log groups
- `/aws/batch/*`: 67 log groups
... (top 15 categories)

### Sample Log Groups (showing 100 of 2,847)
- /aws/apigateway/payment-api
- /aws/apigateway/user-api
- /aws/lambda/auth-handler
- /aws/lambda/payment-processor
... (100 representative samples)

### Usage Instructions
- The full list of 2,847 log groups is available but too large to display
- Use the category prefixes above to understand what's available
- For specific lookups, use `list_log_groups` with a prefix filter
- Common prefixes: `/aws/lambda/`, `/aws/apigateway/`, `/ecs/`, `/aws/rds/`
- User can refresh this list with the `/refresh` command
- When user mentions a service, match it to the appropriate prefix category
```

### 6.4 Token Estimation

| Scenario | Estimated Tokens | Notes |
|----------|-----------------|-------|
| 50 log groups, full list | ~800 tokens | Average 15 tokens per name + overhead |
| 200 log groups, full list | ~3,200 tokens | Still reasonable for most models |
| 500 log groups, full list | ~8,000 tokens | At threshold, consider switching |
| 1000+ groups, summary | ~2,500 tokens | Categories + 100 samples + instructions |

The 500-group threshold is chosen because:
- Claude/GPT-4 models typically have 100k+ context windows
- 8,000 tokens for log groups leaves ample room for conversation
- Summary mode keeps large accounts manageable while still useful

---

## 7. Integration Points

### 7.1 File Changes Required

| File | Change Type | Description |
|------|-------------|-------------|
| `src/logai/core/log_group_manager.py` | **NEW** | New module with LogGroupManager class |
| `src/logai/core/orchestrator.py` | MODIFY | Accept LogGroupManager, update system prompt, add inject method |
| `src/logai/cli.py` | MODIFY | Initialize LogGroupManager, call load_all(), pass to orchestrator |
| `src/logai/ui/app.py` | MODIFY | Accept and store LogGroupManager reference |
| `src/logai/ui/commands.py` | MODIFY | Accept LogGroupManager, add /refresh handler |
| `src/logai/ui/screens/chat.py` | MODIFY | Pass LogGroupManager to CommandHandler |

### 7.2 Dependency Graph

```
cli.py (entry point)
  │
  ├── Creates: CloudWatchDataSource
  │     │
  │     └── Used by: LogGroupManager (new)
  │                    │
  │                    └── Passed to: LLMOrchestrator
  │                                   LogAIApp
  │
  └── Creates: LLMOrchestrator
        │
        └── Passed to: LogAIApp
                        │
                        └── Creates: ChatScreen
                                      │
                                      └── Creates: CommandHandler
                                                    (receives LogGroupManager)
```

### 7.3 Import Structure

```python
# cli.py
from logai.core.log_group_manager import LogGroupManager

# orchestrator.py
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from logai.core.log_group_manager import LogGroupManager

# commands.py
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from logai.core.log_group_manager import LogGroupManager

# app.py
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from logai.core.log_group_manager import LogGroupManager
```

---

## 8. Error Handling

### 8.1 Error Scenarios and Recovery

| Scenario | Detection | Recovery Strategy | User Impact |
|----------|-----------|------------------|-------------|
| AWS credentials invalid | `ClientError` with `AccessDeniedException` | Skip preload, log warning | See warning, agent uses tools |
| Network timeout during startup | Connection timeout | Skip preload, continue startup | App starts, uses tool fallback |
| Rate limiting during load | `ThrottlingException` | Exponential backoff, up to 3 retries | Slight delay, should succeed |
| Network timeout during refresh | Connection timeout | Keep existing list, show error | Error message, old list preserved |
| Empty account (no log groups) | `count == 0` after successful fetch | Set state to READY with empty list | Informed, can still use tools |
| Partial load (interrupted) | Exception mid-pagination | Keep partial data, set ERROR state | Some groups available |

### 8.2 Error State Transitions

```
                    ┌──────────────┐
                    │UNINITIALIZED │
                    └──────┬───────┘
                           │ load_all()
                           ▼
                    ┌──────────────┐
          ┌────────│   LOADING    │────────┐
          │        └──────────────┘        │
          │                                │
    Exception                          Success
          │                                │
          ▼                                ▼
    ┌──────────────┐               ┌──────────────┐
    │    ERROR     │               │    READY     │
    └──────────────┘               └──────┬───────┘
          │                                │
          │                         refresh()
          │                                │
          └────────────────────────────────┘
                           │
                    ┌──────┴───────┐
                    │              │
              Exception        Success
                    │              │
                    ▼              ▼
             ┌──────────────┐  State stays
             │    ERROR     │  READY with
             └──────────────┘  new data
```

### 8.3 Error Messages

```python
# Startup failure - graceful degradation
"""
⚠ Failed to load log groups: Access denied to CloudWatch Logs
  Agent will discover log groups via tools
"""

# Refresh failure - preserve state
"""
[red]Failed to refresh log groups[/red]

[bold]Error:[/bold] Connection timed out after 30 seconds

The previous log group list (if any) has been preserved.
"""

# Permission error - helpful guidance
"""
[red]Error:[/red] Access denied to CloudWatch Logs

Please verify:
1. Your AWS credentials have the `logs:DescribeLogGroups` permission
2. Your IAM role/user has access to CloudWatch in this region
3. There are no SCPs blocking access

The agent can still attempt to use tools directly.
"""
```

### 8.4 Graceful Degradation

When pre-loading fails, the system should:

1. **Log the error** - Full details for debugging
2. **Continue startup** - Don't block the application
3. **Inform the user** - Brief warning message
4. **Fall back to tools** - Agent can still use `list_log_groups`
5. **Adjust system prompt** - Indicate fallback mode

```python
# System prompt when preload fails
log_groups_context = """## Log Groups Status

**Status:** Failed to pre-load log groups at startup

Use the `list_log_groups` tool to discover available log groups.
The user can try `/refresh` to attempt loading again.
"""
```

---

## 9. Performance Considerations

### 9.1 API Call Analysis

| Account Size | API Calls | Estimated Time | Memory Usage |
|--------------|-----------|----------------|--------------|
| 50 groups | 1 | ~200ms | ~10KB |
| 200 groups | 4 | ~800ms | ~40KB |
| 500 groups | 10 | ~2s | ~100KB |
| 1000 groups | 20 | ~4s | ~200KB |
| 5000 groups | 100 | ~20s | ~1MB |

**Notes:**
- CloudWatch `describe_log_groups` returns max 50 per page
- Each API call has ~200ms latency (network + processing)
- Memory is minimal: ~200 bytes per log group info

### 9.2 Optimization Strategies

#### 9.2.1 Startup Optimization

```python
# Run in executor to not block event loop
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(
    None,  # Use default thread pool
    self._fetch_all_log_groups_sync,
    progress_callback,
)
```

#### 9.2.2 Memory Optimization

```python
@dataclass
class LogGroupInfo:
    """Store only essential fields to minimize memory."""
    name: str  # Required
    created: int | None = None  # Optional, useful for sorting
    stored_bytes: int = 0  # Optional, can be useful
    retention_days: int | None = None  # Optional
    
    # NOT storing: arn, kmsKeyId, logGroupClass, dataProtectionStatus
    # These can be fetched via tool if needed
```

#### 9.2.3 Prompt Token Optimization

```python
def _format_full_list(self) -> str:
    """Use minimal formatting to save tokens."""
    # Names only, no metadata
    group_list = "\n".join(f"- {g.name}" for g in sorted_groups)
    
    # Compact instructions
    # Each instruction is necessary but concise
```

### 9.3 Scalability Limits

| Limit | Value | Mitigation |
|-------|-------|------------|
| Max log groups | Unlimited (AWS limit ~50k) | Summary mode for large accounts |
| Memory ceiling | ~10MB recommended | Names only = ~200 bytes each |
| Startup timeout | 30 seconds | Progress feedback, graceful degradation |
| Refresh timeout | 30 seconds | Preserve old list on failure |

### 9.4 Rate Limiting Handling

CloudWatch API rate limits: ~5 TPS for `describe_log_groups`

```python
# In CloudWatchDataSource - existing retry decorator handles this
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(RateLimitError),
)
async def list_log_groups(...):
    ...
```

For the paginator in LogGroupManager, boto3's built-in retry handles most cases. For very large accounts, consider:

```python
# Add small delay between pages for very large accounts
for page in paginator.paginate():
    # Process page...
    
    if len(log_groups) > 1000:
        # Slow down to avoid rate limits
        await asyncio.sleep(0.1)
```

---

## 10. Implementation Guide

### 10.1 Implementation Order

Follow this order to minimize merge conflicts and enable incremental testing:

```
Phase 1: Core Component (can be tested in isolation)
├── Step 1: Create log_group_manager.py
├── Step 2: Write unit tests for LogGroupManager
└── Step 3: Verify with manual testing

Phase 2: Orchestrator Integration
├── Step 4: Modify orchestrator.py
├── Step 5: Update orchestrator tests
└── Step 6: Test system prompt generation

Phase 3: CLI Integration  
├── Step 7: Modify cli.py
├── Step 8: Test startup flow end-to-end
└── Step 9: Verify graceful degradation

Phase 4: UI/Command Integration
├── Step 10: Modify app.py
├── Step 11: Modify commands.py
├── Step 12: Modify chat.py
└── Step 13: Test /refresh command

Phase 5: Polish and Documentation
├── Step 14: Integration tests
├── Step 15: Update /help text
└── Step 16: Final review
```

### 10.2 Step-by-Step Instructions

#### Step 1: Create LogGroupManager Module

Create new file: `src/logai/core/log_group_manager.py`

```python
"""CloudWatch Log Group Manager for pre-loading log groups."""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from logai.providers.datasources.cloudwatch import CloudWatchDataSource


class LogGroupManagerState(Enum):
    """State of the log group manager."""
    UNINITIALIZED = "uninitialized"
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"


@dataclass
class LogGroupInfo:
    """Lightweight representation of a CloudWatch log group."""
    name: str
    created: int | None = None
    stored_bytes: int = 0
    retention_days: int | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogGroupInfo":
        return cls(
            name=data["name"],
            created=data.get("created"),
            stored_bytes=data.get("stored_bytes", 0),
            retention_days=data.get("retention_days"),
        )


@dataclass
class LogGroupManagerResult:
    """Result of a log group fetch operation."""
    success: bool
    log_groups: list[LogGroupInfo] = field(default_factory=list)
    count: int = 0
    error_message: str | None = None
    duration_ms: int = 0


ProgressCallback = Callable[[int, str], None]


class LogGroupManager:
    """Manages pre-loaded CloudWatch log groups."""
    
    FULL_LIST_THRESHOLD = 500
    SUMMARY_SAMPLE_SIZE = 100
    
    def __init__(self, datasource: CloudWatchDataSource) -> None:
        self.datasource = datasource
        self._log_groups: list[LogGroupInfo] = []
        self._state = LogGroupManagerState.UNINITIALIZED
        self._last_refresh: datetime | None = None
        self._last_error: str | None = None
    
    @property
    def state(self) -> LogGroupManagerState:
        return self._state
    
    @property
    def log_groups(self) -> list[LogGroupInfo]:
        return self._log_groups.copy()
    
    @property
    def count(self) -> int:
        return len(self._log_groups)
    
    @property
    def last_refresh(self) -> datetime | None:
        return self._last_refresh
    
    @property
    def is_ready(self) -> bool:
        return self._state == LogGroupManagerState.READY
    
    async def load_all(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> LogGroupManagerResult:
        """Load all log groups from CloudWatch with full pagination."""
        start_time = time.monotonic()
        
        self._state = LogGroupManagerState.LOADING
        self._last_error = None
        
        if progress_callback:
            progress_callback(0, "Starting log group discovery...")
        
        try:
            loop = asyncio.get_event_loop()
            raw_groups = await loop.run_in_executor(
                None,
                self._fetch_all_log_groups_sync,
                progress_callback,
            )
            
            all_groups = [LogGroupInfo.from_dict(raw) for raw in raw_groups]
            
            self._log_groups = all_groups
            self._state = LogGroupManagerState.READY
            self._last_refresh = datetime.now(timezone.utc)
            
            duration_ms = int((time.monotonic() - start_time) * 1000)
            
            if progress_callback:
                progress_callback(len(all_groups), "Log group discovery complete")
            
            return LogGroupManagerResult(
                success=True,
                log_groups=all_groups,
                count=len(all_groups),
                duration_ms=duration_ms,
            )
            
        except Exception as e:
            self._state = LogGroupManagerState.ERROR
            self._last_error = str(e)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            
            return LogGroupManagerResult(
                success=False,
                error_message=str(e),
                duration_ms=duration_ms,
            )
    
    def _fetch_all_log_groups_sync(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> list[dict[str, Any]]:
        """Synchronous fetch of all log groups with pagination."""
        paginator = self.datasource.client.get_paginator("describe_log_groups")
        log_groups: list[dict[str, Any]] = []
        
        for page in paginator.paginate():
            for lg in page["logGroups"]:
                log_groups.append({
                    "name": lg["logGroupName"],
                    "created": lg.get("creationTime"),
                    "stored_bytes": lg.get("storedBytes", 0),
                    "retention_days": lg.get("retentionInDays"),
                })
            
            if progress_callback:
                progress_callback(len(log_groups), f"Loading... ({len(log_groups)} found)")
        
        return log_groups
    
    async def refresh(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> LogGroupManagerResult:
        """Refresh the log groups list."""
        return await self.load_all(progress_callback=progress_callback)
    
    def format_for_prompt(self) -> str:
        """Format log groups for inclusion in LLM system prompt."""
        if not self._log_groups:
            return self._format_empty_state()
        
        if len(self._log_groups) <= self.FULL_LIST_THRESHOLD:
            return self._format_full_list()
        else:
            return self._format_summary()
    
    def _format_empty_state(self) -> str:
        """Format message when no log groups are loaded."""
        if self._state == LogGroupManagerState.ERROR:
            return f"""## Log Groups Status

**Status:** Failed to load log groups at startup
**Error:** {self._last_error}

You should use the `list_log_groups` tool to discover available log groups."""
        
        elif self._state == LogGroupManagerState.UNINITIALIZED:
            return """## Log Groups Status

**Status:** Log groups not yet loaded

Use the `list_log_groups` tool to discover available log groups."""
        
        else:
            return """## Log Groups Status

**Status:** No log groups found in this AWS account/region

The AWS account appears to have no CloudWatch log groups, or you may not have 
permission to list them. Verify your AWS credentials and permissions."""
    
    def _format_full_list(self) -> str:
        """Format complete list of log groups."""
        sorted_groups = sorted(self._log_groups, key=lambda g: g.name)
        group_list = "\n".join(f"- {g.name}" for g in sorted_groups)
        
        refresh_time = (
            self._last_refresh.strftime("%Y-%m-%d %H:%M:%S UTC") 
            if self._last_refresh else "Unknown"
        )
        
        return f"""## Available Log Groups

**Total:** {len(self._log_groups)} log groups
**Last Updated:** {refresh_time}

{group_list}

### Usage Instructions
- Use these log group names directly when fetching or searching logs
- This list is your primary reference - no need to call `list_log_groups` unless user requests fresh lookup
- If a log group name doesn't match exactly, suggest the closest match from this list
- User can refresh this list with the `/refresh` command"""
    
    def _format_summary(self) -> str:
        """Format summary for large accounts."""
        categories = self._categorize_log_groups()
        sample = self._get_representative_sample()
        
        refresh_time = (
            self._last_refresh.strftime("%Y-%m-%d %H:%M:%S UTC")
            if self._last_refresh else "Unknown"
        )
        
        category_lines = []
        for prefix, count in sorted(categories.items(), key=lambda x: -x[1])[:15]:
            category_lines.append(f"- `{prefix}*`: {count} log groups")
        categories_text = "\n".join(category_lines)
        
        sample_text = "\n".join(f"- {g.name}" for g in sample)
        
        return f"""## Available Log Groups

**Total:** {len(self._log_groups)} log groups
**Last Updated:** {refresh_time}

### Log Group Categories
{categories_text}

### Sample Log Groups (showing {len(sample)} of {len(self._log_groups)})
{sample_text}

### Usage Instructions
- The full list of {len(self._log_groups)} log groups is available but too large to display
- Use the category prefixes above to understand what's available
- For specific lookups, use `list_log_groups` with a prefix filter
- Common prefixes: `/aws/lambda/`, `/aws/apigateway/`, `/ecs/`, `/aws/rds/`
- User can refresh this list with the `/refresh` command
- When user mentions a service, match it to the appropriate prefix category"""
    
    def _categorize_log_groups(self) -> dict[str, int]:
        """Categorize log groups by common prefixes."""
        categories: dict[str, int] = {}
        
        known_prefixes = [
            "/aws/lambda/",
            "/aws/apigateway/",
            "/aws/rds/",
            "/aws/eks/",
            "/ecs/",
            "/aws/elasticbeanstalk/",
            "/aws/codebuild/",
            "/aws/batch/",
            "/aws/kinesisfirehose/",
            "/aws/vendedlogs/",
        ]
        
        for group in self._log_groups:
            matched = False
            for prefix in known_prefixes:
                if group.name.startswith(prefix):
                    categories[prefix] = categories.get(prefix, 0) + 1
                    matched = True
                    break
            
            if not matched:
                parts = group.name.split("/")
                if len(parts) >= 3:
                    prefix = "/".join(parts[:3]) + "/"
                elif len(parts) >= 2:
                    prefix = "/".join(parts[:2]) + "/"
                else:
                    prefix = "(other)"
                categories[prefix] = categories.get(prefix, 0) + 1
        
        return categories
    
    def _get_representative_sample(self) -> list[LogGroupInfo]:
        """Get a representative sample of log groups."""
        if len(self._log_groups) <= self.SUMMARY_SAMPLE_SIZE:
            return sorted(self._log_groups, key=lambda g: g.name)
        
        categories = self._categorize_log_groups()
        sample: list[LogGroupInfo] = []
        
        total = len(self._log_groups)
        for prefix, count in sorted(categories.items(), key=lambda x: -x[1]):
            allocation = max(1, int(self.SUMMARY_SAMPLE_SIZE * count / total))
            matching = [g for g in self._log_groups if g.name.startswith(prefix)]
            matching.sort(key=lambda g: g.name)
            sample.extend(matching[:allocation])
            
            if len(sample) >= self.SUMMARY_SAMPLE_SIZE:
                break
        
        sample.sort(key=lambda g: g.name)
        return sample[:self.SUMMARY_SAMPLE_SIZE]
    
    def get_log_group_names(self) -> list[str]:
        """Get list of log group names only."""
        return [g.name for g in self._log_groups]
    
    def find_matching_groups(self, pattern: str) -> list[LogGroupInfo]:
        """Find log groups matching a pattern."""
        pattern_lower = pattern.lower()
        return [
            g for g in self._log_groups 
            if pattern_lower in g.name.lower()
        ]
    
    def get_stats(self) -> dict[str, Any]:
        """Get statistics about loaded log groups."""
        if not self._log_groups:
            return {
                "count": 0,
                "state": self._state.value,
                "last_refresh": None,
                "total_bytes": 0,
                "categories": {},
            }
        
        return {
            "count": len(self._log_groups),
            "state": self._state.value,
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
            "total_bytes": sum(g.stored_bytes for g in self._log_groups),
            "categories": self._categorize_log_groups(),
        }
```

#### Step 2: Add Module to Package

Update `src/logai/core/__init__.py`:

```python
from logai.core.log_group_manager import (
    LogGroupInfo,
    LogGroupManager,
    LogGroupManagerResult,
    LogGroupManagerState,
)

__all__ = [
    # ... existing exports ...
    "LogGroupInfo",
    "LogGroupManager",
    "LogGroupManagerResult",
    "LogGroupManagerState",
]
```

#### Step 3-4: Modify Orchestrator

See Section 3.2 for full details. Key changes:

1. Add `log_group_manager` parameter to `__init__`
2. Add `_pending_context_injection` attribute
3. Update `SYSTEM_PROMPT` template with `{log_groups_context}` placeholder
4. Modify `_get_system_prompt()` to include log group context
5. Add `inject_context_update()` method
6. Add `_get_pending_context_injection()` method
7. In `_chat_complete()` and `_chat_stream()`, check for and apply pending injection

#### Step 5: Modify CLI

See Section 3.4 for full details. Key changes:

1. Import `LogGroupManager`
2. Create instance after datasource
3. Call `load_all()` with progress callback
4. Display result to user
5. Pass to orchestrator constructor
6. Pass to `LogAIApp` constructor

#### Step 6-8: Modify UI Components

**app.py:**
```python
def __init__(
    self, 
    orchestrator: LLMOrchestrator, 
    cache_manager: CacheManager,
    log_group_manager: "LogGroupManager | None" = None,  # NEW
) -> None:
    # ... existing code ...
    self.log_group_manager = log_group_manager  # NEW
```

**chat.py:**
```python
def __init__(self, orchestrator: LLMOrchestrator, cache_manager: CacheManager) -> None:
    # ... existing code ...
    # Get log_group_manager from app if available
    self.log_group_manager = getattr(self.app, 'log_group_manager', None)
    
    self.command_handler = CommandHandler(
        orchestrator, 
        cache_manager, 
        self.settings, 
        self,
        self.log_group_manager,  # NEW
    )
```

**commands.py:**
See Section 3.3 for full implementation.

### 10.3 Testing Checkpoints

After each phase, verify:

| Phase | Test |
|-------|------|
| Phase 1 | `pytest tests/unit/core/test_log_group_manager.py` |
| Phase 2 | `pytest tests/unit/core/test_orchestrator.py` |
| Phase 3 | Manual: `logai --aws-profile test` - verify startup |
| Phase 4 | Manual: type `/refresh` - verify command works |
| Phase 5 | Full integration: `pytest tests/integration/` |

---

## 11. Testing Strategy

### 11.1 Unit Tests

#### LogGroupManager Tests

```python
# tests/unit/core/test_log_group_manager.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from logai.core.log_group_manager import (
    LogGroupManager,
    LogGroupInfo,
    LogGroupManagerState,
)


@pytest.fixture
def mock_datasource():
    """Create a mock CloudWatch data source."""
    datasource = MagicMock()
    
    # Mock the boto3 client and paginator
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            "logGroups": [
                {"logGroupName": "/aws/lambda/func-1", "storedBytes": 1000},
                {"logGroupName": "/aws/lambda/func-2", "storedBytes": 2000},
            ]
        },
        {
            "logGroups": [
                {"logGroupName": "/ecs/service-1", "storedBytes": 500},
            ]
        },
    ]
    
    datasource.client.get_paginator.return_value = mock_paginator
    return datasource


class TestLogGroupManagerInit:
    def test_initial_state_is_uninitialized(self, mock_datasource):
        manager = LogGroupManager(mock_datasource)
        assert manager.state == LogGroupManagerState.UNINITIALIZED
        assert manager.count == 0
        assert manager.is_ready is False


class TestLogGroupManagerLoadAll:
    @pytest.mark.asyncio
    async def test_load_all_success(self, mock_datasource):
        manager = LogGroupManager(mock_datasource)
        
        result = await manager.load_all()
        
        assert result.success is True
        assert result.count == 3
        assert manager.state == LogGroupManagerState.READY
        assert manager.is_ready is True
        assert manager.last_refresh is not None
    
    @pytest.mark.asyncio
    async def test_load_all_with_progress_callback(self, mock_datasource):
        manager = LogGroupManager(mock_datasource)
        progress_calls = []
        
        def callback(count, msg):
            progress_calls.append((count, msg))
        
        await manager.load_all(progress_callback=callback)
        
        assert len(progress_calls) >= 2  # At least start and end
        assert progress_calls[-1][1] == "Log group discovery complete"
    
    @pytest.mark.asyncio
    async def test_load_all_handles_error(self, mock_datasource):
        mock_datasource.client.get_paginator.side_effect = Exception("AWS Error")
        manager = LogGroupManager(mock_datasource)
        
        result = await manager.load_all()
        
        assert result.success is False
        assert "AWS Error" in result.error_message
        assert manager.state == LogGroupManagerState.ERROR


class TestLogGroupManagerFormatForPrompt:
    @pytest.mark.asyncio
    async def test_format_full_list_under_threshold(self, mock_datasource):
        manager = LogGroupManager(mock_datasource)
        await manager.load_all()
        
        prompt = manager.format_for_prompt()
        
        assert "## Available Log Groups" in prompt
        assert "3 log groups" in prompt
        assert "/aws/lambda/func-1" in prompt
        assert "/ecs/service-1" in prompt
    
    def test_format_empty_state_uninitialized(self, mock_datasource):
        manager = LogGroupManager(mock_datasource)
        
        prompt = manager.format_for_prompt()
        
        assert "not yet loaded" in prompt
        assert "list_log_groups" in prompt
    
    @pytest.mark.asyncio
    async def test_format_summary_over_threshold(self, mock_datasource):
        """Test summary format when over 500 log groups."""
        # Create mock with many log groups
        large_page = {
            "logGroups": [
                {"logGroupName": f"/aws/lambda/func-{i}"}
                for i in range(600)
            ]
        }
        mock_datasource.client.get_paginator.return_value.paginate.return_value = [large_page]
        
        manager = LogGroupManager(mock_datasource)
        await manager.load_all()
        
        prompt = manager.format_for_prompt()
        
        assert "600 log groups" in prompt
        assert "Log Group Categories" in prompt
        assert "Sample Log Groups" in prompt


class TestLogGroupManagerRefresh:
    @pytest.mark.asyncio
    async def test_refresh_updates_data(self, mock_datasource):
        manager = LogGroupManager(mock_datasource)
        
        # Initial load
        await manager.load_all()
        initial_refresh = manager.last_refresh
        
        # Add more log groups
        mock_datasource.client.get_paginator.return_value.paginate.return_value = [
            {"logGroups": [{"logGroupName": "/new/group"}]}
        ]
        
        # Refresh
        import asyncio
        await asyncio.sleep(0.01)  # Small delay to ensure different timestamp
        result = await manager.refresh()
        
        assert result.success is True
        assert result.count == 1
        assert manager.last_refresh > initial_refresh


class TestLogGroupInfo:
    def test_from_dict_with_all_fields(self):
        data = {
            "name": "/aws/lambda/test",
            "created": 1234567890000,
            "stored_bytes": 5000,
            "retention_days": 30,
        }
        
        info = LogGroupInfo.from_dict(data)
        
        assert info.name == "/aws/lambda/test"
        assert info.created == 1234567890000
        assert info.stored_bytes == 5000
        assert info.retention_days == 30
    
    def test_from_dict_with_minimal_fields(self):
        data = {"name": "/test"}
        
        info = LogGroupInfo.from_dict(data)
        
        assert info.name == "/test"
        assert info.created is None
        assert info.stored_bytes == 0
        assert info.retention_days is None
```

#### Orchestrator Tests

```python
# tests/unit/core/test_orchestrator.py (additions)

class TestOrchestratorWithLogGroupManager:
    @pytest.fixture
    def mock_log_group_manager(self):
        manager = MagicMock()
        manager.is_ready = True
        manager.format_for_prompt.return_value = "## Available Log Groups\n- /test/group"
        return manager
    
    def test_system_prompt_includes_log_groups(self, mock_log_group_manager, ...):
        orchestrator = LLMOrchestrator(
            ...,
            log_group_manager=mock_log_group_manager,
        )
        
        prompt = orchestrator._get_system_prompt()
        
        assert "## Available Log Groups" in prompt
        assert "/test/group" in prompt
    
    def test_system_prompt_without_log_group_manager(self, ...):
        orchestrator = LLMOrchestrator(
            ...,
            log_group_manager=None,
        )
        
        prompt = orchestrator._get_system_prompt()
        
        assert "discovered via" in prompt.lower() or "list_log_groups" in prompt
    
    def test_inject_context_update(self, mock_log_group_manager, ...):
        orchestrator = LLMOrchestrator(
            ...,
            log_group_manager=mock_log_group_manager,
        )
        
        orchestrator.inject_context_update("New context here")
        
        # Verify it's retrievable
        injection = orchestrator._get_pending_context_injection()
        assert injection == "New context here"
        
        # Verify it's cleared after retrieval
        injection2 = orchestrator._get_pending_context_injection()
        assert injection2 is None
```

### 11.2 Integration Tests

```python
# tests/integration/test_log_group_preload.py

import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.integration
class TestLogGroupPreloadIntegration:
    """Integration tests for log group pre-loading feature."""
    
    @pytest.fixture
    def mock_aws_environment(self):
        """Set up mock AWS environment."""
        with patch('boto3.client') as mock_client:
            # Configure mock paginator
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [
                {"logGroups": [
                    {"logGroupName": "/aws/lambda/test-function"},
                    {"logGroupName": "/ecs/test-service"},
                ]}
            ]
            mock_client.return_value.get_paginator.return_value = mock_paginator
            yield mock_client
    
    @pytest.mark.asyncio
    async def test_full_startup_flow(self, mock_aws_environment):
        """Test that log groups are loaded during startup."""
        from logai.core.log_group_manager import LogGroupManager
        from logai.providers.datasources.cloudwatch import CloudWatchDataSource
        from logai.config.settings import LogAISettings
        
        # Create settings with mock values
        settings = LogAISettings(
            aws_region="us-east-1",
            aws_profile="test",
        )
        
        # Initialize components
        datasource = CloudWatchDataSource(settings)
        manager = LogGroupManager(datasource)
        
        # Load log groups
        result = await manager.load_all()
        
        # Verify
        assert result.success is True
        assert result.count == 2
        assert manager.is_ready
    
    @pytest.mark.asyncio
    async def test_orchestrator_includes_preloaded_groups(self, mock_aws_environment, ...):
        """Test that orchestrator includes preloaded groups in prompt."""
        # ... setup ...
        
        orchestrator = LLMOrchestrator(
            ...,
            log_group_manager=manager,
        )
        
        prompt = orchestrator._get_system_prompt()
        
        assert "/aws/lambda/test-function" in prompt
        assert "/ecs/test-service" in prompt
```

### 11.3 Manual Testing Checklist

```markdown
## Manual Test Cases

### Startup Tests
- [ ] Start app with valid AWS credentials - log groups load
- [ ] Start app with invalid credentials - graceful degradation
- [ ] Start app with empty AWS account - appropriate message
- [ ] Verify progress display during loading
- [ ] Time startup with ~100 log groups (should be <5s)
- [ ] Time startup with ~1000 log groups (should be <30s)

### System Prompt Tests  
- [ ] First query shows agent using pre-loaded list
- [ ] Agent doesn't call list_log_groups for initial queries
- [ ] Large account shows summary instead of full list

### Refresh Command Tests
- [ ] `/refresh` command updates log groups
- [ ] Agent acknowledges updated context in next response
- [ ] `/refresh` with invalid credentials shows error
- [ ] `/refresh` preserves old list on failure
- [ ] `/help` shows /refresh command

### Edge Cases
- [ ] New log group created, /refresh picks it up
- [ ] Log group deleted, /refresh removes it
- [ ] Network disconnection during startup - graceful degradation
- [ ] Network disconnection during refresh - old list preserved
```

---

## 12. Risks and Trade-offs

### 12.1 Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Token limit exceeded | Low | Medium | Tiered prompt strategy, summary for large accounts |
| Startup delay too long | Medium | Low | Progress feedback, 30s timeout, graceful degradation |
| Stale data after startup | Medium | Low | `/refresh` command, agent can still use tools |
| Memory pressure with 10k+ groups | Low | Low | Lightweight LogGroupInfo, ~200 bytes per group |
| AWS rate limiting | Low | Medium | Existing retry logic, small delays for large accounts |
| Context injection confuses LLM | Low | Medium | Clear formatting, explicit instructions |

### 12.2 Trade-off Analysis

#### Trade-off 1: Full List vs Summary

**Decision:** Tiered approach with 500-group threshold

**Pros:**
- Small accounts get complete information
- Large accounts stay within reasonable token budgets
- Agent can still use tools for specific lookups

**Cons:**
- Large accounts don't have full list in context
- Threshold is somewhat arbitrary

**Alternative considered:** Always use summary
**Why rejected:** Loses precision for small accounts where full list is practical

#### Trade-off 2: Context Injection vs Conversation Reset

**Decision:** Context injection via system message

**Pros:**
- Preserves conversation history
- Non-disruptive to user experience
- Simple implementation

**Cons:**
- Old list still in original system prompt (may cause confusion)
- Relies on LLM following "newer context" instruction

**Alternative considered:** Reset conversation on refresh
**Why rejected:** Poor UX, loses conversation context

#### Trade-off 3: Singleton vs Dependency Injection

**Decision:** Dependency injection

**Pros:**
- Better testability
- Explicit dependencies
- Multiple instances possible if needed

**Cons:**
- More boilerplate to pass through component chain

**Alternative considered:** Singleton pattern like `get_settings()`
**Why rejected:** Harder to test, implicit global state

### 12.3 Future Considerations

1. **Caching to Disk:** Could persist log groups to disk for faster startup
2. **Incremental Updates:** Could track changes instead of full refresh
3. **Multi-Region Support:** Current design is single-region; could expand
4. **Log Group Metadata:** Could include more details (ARN, class, etc.)
5. **Auto-Refresh:** Could periodically refresh in background

### 12.4 Success Metrics

After implementation, measure:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Startup time (100 groups) | <3s | Timer in CLI |
| Startup time (1000 groups) | <15s | Timer in CLI |
| list_log_groups calls reduction | >50% | Compare before/after in logs |
| First query latency | Same or better | User testing |
| Memory usage | <10MB additional | Profile app |

---

## Appendix A: Complete File Diff Summary

### New Files
- `src/logai/core/log_group_manager.py` - Full implementation as shown in Section 10.2

### Modified Files

**`src/logai/core/__init__.py`**
```diff
+ from logai.core.log_group_manager import (
+     LogGroupInfo,
+     LogGroupManager,
+     LogGroupManagerResult,
+     LogGroupManagerState,
+ )
```

**`src/logai/core/orchestrator.py`**
- Add `log_group_manager` parameter to `__init__`
- Add `_pending_context_injection` attribute
- Update `SYSTEM_PROMPT` with `{log_groups_context}` placeholder
- Modify `_get_system_prompt()` 
- Add `inject_context_update()` and `_get_pending_context_injection()` methods
- Update `_chat_complete()` and `_chat_stream()` to check for injections

**`src/logai/cli.py`**
- Import `LogGroupManager`
- Initialize and load log groups after datasource
- Pass to orchestrator and app

**`src/logai/ui/app.py`**
- Add `log_group_manager` parameter to `__init__`

**`src/logai/ui/commands.py`**
- Add `log_group_manager` parameter to `__init__`
- Add `/refresh` command handler
- Update help text

**`src/logai/ui/screens/chat.py`**
- Pass `log_group_manager` to `CommandHandler`

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| Pre-loading | Fetching data at startup before it's requested |
| System Prompt | Initial instructions given to the LLM at conversation start |
| Context Injection | Adding information to LLM context mid-conversation |
| Pagination | Fetching data in chunks/pages from an API |
| Graceful Degradation | Continuing to function with reduced capability on error |
| Token | Unit of text for LLM (roughly 4 characters or 0.75 words) |

---

**Document End**

*Ready for implementation by Jackie. Questions should be directed to Sally via George (TPM).*
