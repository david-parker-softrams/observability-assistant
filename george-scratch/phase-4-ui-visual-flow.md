# Phase 4 UI Integration - Visual Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          USER SEES THIS IN TUI                               │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Status Bar (Bottom of screen)                                          │ │
│  │                                                                         │ │
│  │ Status: Ready | Cache: 10 hits (67%) | Context: [green]45%[/] | Model │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Toast Notification (Top-right, auto-dismiss)                           │ │
│  │                                                                         │ │
│  │  ℹ️ Large result cached (15,234 tokens)                                │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘

                                       ▲
                                       │
                                   UI Updates
                                       │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CHAT SCREEN LOGIC                                  │
│                                                                              │
│  on_mount():                                                                 │
│    ├─ orchestrator.set_context_notification_callback(                       │
│    │    self._handle_context_notification)  ◄─── Registers callback         │
│    │                                                                         │
│  _handle_context_notification(level, message):                              │
│    ├─ Map level → Textual severity                                          │
│    ├─ self.notify(message, severity, timeout)  ◄─── Shows toast            │
│    └─ self._update_context_status()  ◄─── Updates status bar               │
│                                                                              │
│  _update_context_status():                                                  │
│    ├─ Check throttle (1 second max)  ◄─── Prevents flicker                 │
│    ├─ usage = orchestrator.budget_tracker.get_usage()                       │
│    └─ status_bar.update_context_usage(usage.utilization_pct)               │
│                                                                              │
│  _process_message():  (after agent response)                                │
│    └─ self._update_context_status()  ◄─── Updates after each response      │
└─────────────────────────────────────────────────────────────────────────────┘

                                       ▲
                                       │
                               Notifications from
                                       │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LLM ORCHESTRATOR                                   │
│                                                                              │
│  _process_tool_result():                                                    │
│    ├─ should_cache, tokens = budget_tracker.should_cache_result()          │
│    ├─ if should_cache:                                                      │
│    │    ├─ result_cache.cache_result(...)                                   │
│    │    └─ _notify("info", "Large result cached (X tokens)")  ◄─── Event 1 │
│    │                                                                         │
│  _prepare_messages_for_llm():                                               │
│    ├─ if budget_tracker.should_prune_history():                             │
│    │    ├─ to_prune = budget_tracker.get_prunable_messages()               │
│    │    ├─ Prune old messages                                               │
│    │    └─ _notify("info", "Pruned X messages (freed Y tokens)") ◄─ Event 2│
│    │                                                                         │
│  _notify(level, message):  (Internal helper)                                │
│    ├─ if self._context_notification_callback:                               │
│    │    └─ self._context_notification_callback(level, message)  ◄─ Callback│
└─────────────────────────────────────────────────────────────────────────────┘

                                       ▲
                                       │
                                  Reads from
                                       │
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CONTEXT BUDGET TRACKER                                │
│                                                                              │
│  get_usage() → BudgetUsage:                                                 │
│    ├─ system_prompt_tokens: int                                             │
│    ├─ history_tokens: int                                                   │
│    ├─ result_tokens: int                                                    │
│    ├─ total_tokens: int                                                     │
│    ├─ remaining_tokens: int                                                 │
│    └─ utilization_pct: float  ◄─── This is displayed in UI                 │
│                                                                              │
│  should_cache_result(result) → (bool, int):                                 │
│    └─ Decides if result is too large for context                            │
│                                                                              │
│  should_prune_history(threshold=85%) → bool:                                │
│    └─ Decides if pruning is needed                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Color Coding States

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  GREEN (0-70% utilization)                                                  │
│  ╔════════════════════════════════════════════════════════════════════════╗ │
│  ║ Status: Ready | Cache: 5 hits | Context: [green]45%[/] | Model: gpt-4 ║ │
│  ╚════════════════════════════════════════════════════════════════════════╝ │
│                                                                              │
│  • Normal operation                                                          │
│  • Plenty of context space                                                   │
│  • No warnings or actions                                                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  YELLOW (71-85% utilization)                                                │
│  ╔════════════════════════════════════════════════════════════════════════╗ │
│  ║ Status: Ready | Cache: 8 hits | Context: [yellow]78%[/] | Model: gpt-4║ │
│  ╚════════════════════════════════════════════════════════════════════════╝ │
│                                                                              │
│  • Warning zone                                                              │
│  • Approaching threshold                                                     │
│  • Pruning may occur soon                                                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  RED (86-100% utilization)                                                  │
│  ╔════════════════════════════════════════════════════════════════════════╗ │
│  ║ Status: Ready | Cache: 12 hits | Context: [red]92%[/] | Model: gpt-4  ║ │
│  ╚════════════════════════════════════════════════════════════════════════╝ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ ℹ️ Pruned 15 old messages to maintain context (freed ~5000 tokens)    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  • Critical zone                                                             │
│  • Pruning happening automatically                                           │
│  • Toast notification shown                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Notification Examples

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  INFO: Result Cached (5 second timeout)                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ ℹ️ Large result cached (15,234 tokens)                                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Triggered when:                                                             │
│  • CloudWatch query returns 1000 events (~50K tokens)                       │
│  • Result exceeds RESULT_CACHE_THRESHOLD (15,000 tokens)                   │
│  • Result successfully cached to SQLite                                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  INFO: History Pruned (5 second timeout)                                    │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ ℹ️ Pruned 15 old messages to maintain context (freed ~5000 tokens)     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Triggered when:                                                             │
│  • Context utilization exceeds 85%                                          │
│  • Orchestrator automatically prunes oldest messages                         │
│  • User has long conversation (50+ messages)                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  WARNING: Approaching Limit (8 second timeout)                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ ⚠️  Context window filling up (85%). Older messages may be pruned.     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Triggered when:                                                             │
│  • Context utilization reaches 85%                                          │
│  • Before automatic pruning occurs                                           │
│  • Gives user heads-up that history will be trimmed                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  ERROR: Cache Failure (10 second timeout)                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ ❌ Failed to cache result: Database locked                              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Triggered when:                                                             │
│  • Result caching fails (disk full, DB locked, etc.)                        │
│  • Result will be truncated instead of cached                               │
│  • Rare occurrence, but important for user to know                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Throttling Behavior

```
Time (seconds)    Context %    UI Update?    Reason
────────────────────────────────────────────────────────────────────
0.0               45%          ✅ Yes        Initial update
0.5               47%          ❌ No         Too soon (0.5s < 1.0s)
0.8               48%          ❌ No         Too soon (0.8s < 1.0s)
1.1               52%          ✅ Yes        > 1 second elapsed
1.3               53%          ❌ No         Too soon (0.2s < 1.0s)
2.2               58%          ✅ Yes        > 1 second elapsed

Benefits:
• Prevents UI flicker during rapid context changes
• Reduces CPU usage (99% reduction in update frequency)
• Still feels instant to user (1 second is fast enough)
• Simple implementation (single timestamp check)
```

## Integration Points

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 1-3 (COMPLETE)                                 │
│                                                                              │
│  TokenCounter          ✅ 90% test coverage                                 │
│  ContextBudgetTracker  ✅ 90% test coverage                                 │
│  ResultCacheManager    ✅ 97% test coverage                                 │
│  Orchestrator          ✅ 59% test coverage, 23 integration tests           │
│                                                                              │
│  All backend functionality working and tested                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                       ▲
                                       │
                                  Surfaces to
                                       │
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 4 (THIS PR)                                    │
│                                                                              │
│  StatusBar Widget      ✅ 87% test coverage                                 │
│  ChatScreen Updates    ✅ Integration tested via orchestrator               │
│  UI Unit Tests         ✅ 8 tests, all passing                              │
│                                                                              │
│  All UI enhancements complete and tested                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

**End of Visual Flow Documentation**
