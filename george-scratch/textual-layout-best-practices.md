# Textual Framework Best Practices - CSS Layout

## Lesson Learned: Avoid Multiple Docked Elements

**Date Discovered**: February 18, 2026
**Issue**: Time frame selector buttons and header not rendering despite existing in widget tree
**Root Cause**: Multiple `dock: top` elements in same container

---

## The Problem

When multiple widgets in the same container use `dock: top`, Textual's layout engine may not render them correctly. In our case:

```python
# Three elements all using dock: top
#preview-header { dock: top; }       # ❌ Not rendering
#timeframe-controls { dock: top; }   # ❌ Not rendering
#selection-controls { dock: top; }   # ✅ Only this one rendered
```

**Symptoms**:
- Widgets exist in the widget tree (confirmed via debug logs)
- `query_one()` finds the widgets successfully
- But widgets are not visible in the UI
- No error messages or warnings
- Layout calculation fails silently

---

## The Solution

Use natural vertical layout instead of docking:

### ❌ Don't Do This
```css
LogPreviewScreen {
    align: center middle;
}

#preview-container {
    width: 90%;
    height: 85%;
    padding: 1;
}

#header {
    dock: top;
    height: 3;
}

#controls {
    dock: top;
    height: 3;
}

#footer {
    dock: bottom;
    height: 3;
}
```

### ✅ Do This Instead
```css
LogPreviewScreen {
    align: center middle;
}

#preview-container {
    width: 90%;
    height: 85%;
    layout: vertical;  /* ← Add this */
    padding: 0;        /* ← Reduce padding to avoid spacing issues */
}

#header {
    /* dock: top; ← Remove this */
    height: 3;
    width: 100%;       /* ← Ensure full width */
}

#controls {
    /* dock: top; ← Remove this */
    height: 3;
    width: 100%;
}

#content {
    height: 1fr;       /* ← Flexible height takes remaining space */
    overflow: auto;    /* ← Allow scrolling if needed */
}

#footer {
    /* dock: bottom; ← Remove this */
    height: 3;
    width: 100%;
}
```

---

## When Is Docking Acceptable?

Docking is fine for **simple layouts** with only 1-2 docked elements:

### ✅ Good Use Case: Single Header
```css
#container {
    layout: vertical;
}

#header {
    dock: top;    /* OK - only one docked element */
    height: 3;
}

#content {
    height: 1fr;  /* Takes remaining space */
}
```

### ✅ Good Use Case: Header + Footer
```css
#container {
    layout: vertical;
}

#header {
    dock: top;     /* OK - max 2 docked elements */
    height: 3;
}

#footer {
    dock: bottom;  /* OK - different dock direction */
    height: 3;
}

#content {
    height: 1fr;
}
```

### ❌ Bad Use Case: Multiple Same-Direction Docks
```css
#container {
    layout: vertical;
}

#header { dock: top; }     /* ❌ Multiple */
#controls { dock: top; }   /* ❌ same-direction */
#toolbar { dock: top; }    /* ❌ docks */

/* This will cause layout issues! */
```

---

## Alternative Patterns

### Pattern 1: Explicit Containers
Instead of docking, create explicit container hierarchy:

```python
def compose(self) -> ComposeResult:
    with Container(id="main"):
        # Top section
        with Container(id="top-section"):
            yield Static("Header", id="header")
            yield Horizontal(id="controls")

        # Content section
        yield VerticalScroll(id="content")

        # Bottom section
        with Container(id="bottom-section"):
            yield Horizontal(id="actions")
```

```css
#main {
    layout: vertical;
}

#top-section {
    height: auto;
    layout: vertical;
}

#content {
    height: 1fr;
    overflow: auto;
}

#bottom-section {
    height: auto;
}
```

### Pattern 2: Grid Layout
For more complex layouts, use Grid:

```python
def compose(self) -> ComposeResult:
    with Container(id="main"):
        yield Static("Header", id="header")
        yield Static("Sidebar", id="sidebar")
        yield VerticalScroll(id="content")
        yield Static("Footer", id="footer")
```

```css
#main {
    layout: grid;
    grid-size: 2 3;  /* 2 columns, 3 rows */
    grid-rows: 3 1fr 3;
    grid-columns: 20 1fr;
}

#header {
    column-span: 2;  /* Spans both columns */
}

#sidebar {
    row-span: 1;
}

#content {
    row-span: 1;
}

#footer {
    column-span: 2;
}
```

---

## Debugging Tips

If widgets aren't rendering:

1. **Check if they exist in the tree**:
   ```python
   # Add debug logging
   logger.debug(f"Widget exists: {self.query_one('#my-widget')}")
   ```

2. **Check CSS layout**:
   - Are multiple elements using the same dock direction?
   - Does the container have `layout: vertical` or `layout: horizontal`?
   - Is container height sufficient for all children?

3. **Check padding and margins**:
   - Excessive padding can push elements off-screen
   - Try `padding: 0` to see if elements appear

4. **Use Textual DevTools**:
   ```bash
   textual console  # In one terminal
   # Run your app in another terminal
   ```

5. **Inspect computed styles**:
   ```python
   widget = self.query_one("#my-widget")
   logger.debug(f"Widget styles: {widget.styles}")
   ```

---

## Summary

**Golden Rule**: When in doubt, use `layout: vertical` (or `horizontal`) instead of docking.

**Docking Guidelines**:
- ✅ Use for 1-2 simple elements (header/footer)
- ❌ Avoid for 3+ elements in same direction
- ❌ Avoid when elements need complex interactions
- ✅ Prefer explicit containers and natural flow

**Testing Checklist**:
- [ ] All widgets visible in UI
- [ ] Layout works with different terminal sizes
- [ ] Scrolling works if content overflows
- [ ] No unexpected whitespace or gaps
- [ ] Elements stack in expected order

---

## References

- **Textual Documentation**: https://textual.textualize.io/guide/layout/
- **Related Issue**: observability-assistant commit `8a594e2`
- **Investigation Notes**: `george-scratch/session-notes-2026-02-18.md`

---

**Last Updated**: February 18, 2026
**Status**: Verified and tested
