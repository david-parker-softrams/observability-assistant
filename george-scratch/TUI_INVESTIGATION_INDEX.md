# TUI Investigation Index

**Investigation Date**: February 11, 2026
**Investigator**: Hans, Code Librarian
**Status**: ✅ Complete and Ready for Implementation

---

## 📚 Investigation Documents

### 1. Main Analysis Document
**File**: `TUI_ARCHITECTURE_INVESTIGATION.md` (27 KB, 845 lines)

**What it covers**:
- Complete TUI framework analysis
- Current architecture diagrams
- Tool execution flow documentation
- Command system architecture
- State management strategy
- Layout design options
- Technical challenges and solutions
- Implementation roadmap with phases
- Code structure examples
- Testing strategy

**Best for**:
- Understanding the complete system
- Design review
- Detailed technical explanations
- Reference when implementing

---

### 2. Developer Quick Reference
**File**: `TUI_SIDEBAR_QUICK_REFERENCE.md` (6.3 KB)

**What it covers**:
- One-page cheat sheet
- Exact code to add/modify
- File-by-file changes with line-by-line code
- Implementation checklist
- Testing checklist
- Troubleshooting guide
- Implementation timeline (1-1.5 hours)

**Best for**:
- Implementing the feature
- Following step-by-step instructions
- Copy/paste code snippets
- Troubleshooting during development

---

## 🎯 Quick Summary

### The Ask
Add a **tool calls sidebar** to the TUI that shows recent tool calls and their execution status, toggleable with `/toggle-tools` command.

### Current State
- Textual 0.47.0+ framework
- Single vertical layout (Header → Messages → Input → StatusBar)
- Tool calls tracked in orchestrator but not displayed in UI
- Simple slash command system
- No callback mechanism from orchestrator to UI

### Proposed Solution
- Add right sidebar (25 columns, collapsible)
- Show recent 10 tool calls in tree view
- Toggle with `/toggle-tools` command
- Hide on small terminals automatically
- Use Textual reactive pattern for updates

### Implementation Scope
- **1 new file**: `src/logai/ui/widgets/tool_calls_sidebar.py`
- **4 modified files**: `chat.py`, `app.tcss`, `commands.py`, `orchestrator.py`
- **~300 lines of code**
- **No breaking changes**
- **4-7 hours total** (can ship basic version in 1-2 hours)

### Risk Level
🟢 **LOW** - All changes are additive, backward compatible, and low-risk

---

## 📋 How to Use These Documents

### Scenario 1: Planning & Design Review
1. Read **Main Analysis Document** (TUI_ARCHITECTURE_INVESTIGATION.md)
2. Review proposed layout diagrams
3. Understand technical challenges and solutions
4. Decide on implementation priorities

### Scenario 2: Implementation
1. Open **Quick Reference** (TUI_SIDEBAR_QUICK_REFERENCE.md)
2. Follow "Implementation Order" section step-by-step
3. Copy exact code snippets provided
4. Use testing checklist to verify
5. Reference main document if you need to understand "why"

### Scenario 3: Troubleshooting
1. Check "Troubleshooting" section in Quick Reference
2. If not found, check Technical Challenges section in Main Document
3. Review relevant code examples in Main Document

---

## 🔍 Key Findings at a Glance

| Aspect | Finding |
|--------|---------|
| **Framework** | Textual 0.47.0+ (Python TUI) |
| **Current Layout** | Vertical (Header → Messages → Input → StatusBar) |
| **Tool Tracking** | Orchestrator stores in conversation_history |
| **UI Display** | NOT currently displayed (main gap) |
| **Command System** | Simple if/elif, super easy to extend |
| **State Management** | Minimal, should use ChatScreen class |
| **Architecture Fitness** | ⭐⭐⭐⭐⭐ Excellent, ready for sidebar |

---

## 📝 Implementation Files

### New File to Create
```
src/logai/ui/widgets/tool_calls_sidebar.py
├─ ToolCallsSidebar class
├─ Tree widget display
├─ Reactive tool_calls property
└─ Methods: on_mount, watch_tool_calls, add_tool_call
```

### Files to Modify
```
src/logai/ui/screens/chat.py
├─ Add sidebar imports
├─ Add _show_tools_sidebar state
├─ Add _toggle_tools_sidebar method
├─ Add _on_tool_call callback
└─ Register callback in on_mount

src/logai/ui/styles/app.tcss
├─ Add ToolCallsSidebar CSS rules
├─ Set width: 25
├─ Set styling (colors, borders, padding)
└─ Add Tree widget styling

src/logai/ui/commands.py
├─ Add /toggle-tools elif clause
├─ Add help text for new command
└─ Wire up to _toggle_tools_sidebar method

src/logai/core/orchestrator.py (optional but recommended)
├─ Add tool_listeners list
├─ Add register_tool_listener method
├─ Add _notify_tool_call method
└─ Call _notify_tool_call in _execute_tool_calls
```

---

## ⏱️ Implementation Timeline

| Phase | Duration | What |
|-------|----------|------|
| **Phase 1** | 1-2 hrs | Basic sidebar widget + mount/unmount |
| **Phase 2** | 1-2 hrs | Connect to orchestrator with callbacks |
| **Phase 3** | 1-2 hrs | Polish, responsive, testing, persistence |
| **Total** | 4-7 hrs | Production-ready feature |

*Can ship Phase 1 alone in 1-2 hours for quick MVP*

---

## 🚀 Getting Started

### For George (TPM)
1. Read "The Ask" section above
2. Review layout diagram in Main Document (Section 5)
3. Review "Readiness Assessment" (Section 8)
4. Assign to developer with link to Quick Reference

### For Developer (Jackie or other)
1. Read Quick Reference first (it's only 6 KB)
2. Start with "Implementation Order" section
3. Copy code snippets and apply to files
4. Use "Testing Checklist" to validate
5. Reference Main Document for details

### For QA
1. Use "Testing Checklist" from Quick Reference
2. Test on different terminal widths
3. Verify no crashes on toggle
4. Check sidebar updates in real-time

---

## 🎓 Key Technical Insights

### Textual Patterns Used
- **Reactive properties**: `@reactive[type]` for auto-updating UI
- **Mount/Remove pattern**: Dynamic widget lifecycle (not show/hide)
- **CSS layout**: `width: 1fr` (flexible) and `width: N` (fixed)
- **Callback pattern**: Observer pattern for cross-module communication
- **Container nesting**: Horizontal/Vertical for layout

### Challenges Addressed
1. **Tool visibility**: Use callback/observer pattern
2. **Dynamic layout**: Mount/remove widgets dynamically
3. **Responsive design**: Check terminal width, hide on small screens
4. **Async safety**: Use Textual reactive for thread-safe updates
5. **Layout math**: Fixed sidebar + flexible messages = no overflow

---

## 📞 Questions for George

Before implementation, consider:

1. **Default state**: Sidebar visible by default or hidden?
2. **Persistence**: Save sidebar state across sessions?
3. **Resize**: Should sidebar be resizable? (advanced)
4. **Filtering**: Should users filter tool calls? (advanced)
5. **Timeline**: When is this needed?

---

## ✨ Success Criteria

After implementation:
- [ ] App starts without sidebar visible
- [ ] `/toggle-tools` shows sidebar on right side
- [ ] Sidebar updates when tools are executed
- [ ] Multiple tool calls appear in tree view
- [ ] Sidebar hides on terminals < 100 characters
- [ ] No crashes or errors
- [ ] All tests pass

---

## 📚 References

- **Textual Docs**: https://textual.textualize.io/
- **Current Code**: `src/logai/ui/` directory
- **Tool Execution**: `src/logai/core/orchestrator.py`

---

## Navigation

- **Start here** → This file (TUI_INVESTIGATION_INDEX.md)
- **For planning** → TUI_ARCHITECTURE_INVESTIGATION.md (Main Document)
- **For implementation** → TUI_SIDEBAR_QUICK_REFERENCE.md (Developer Guide)

---

**Status**: ✅ Investigation Complete
**Awaiting**: George's direction on implementation priorities
**Ready**: Yes, all materials prepared for immediate implementation
