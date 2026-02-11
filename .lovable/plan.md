

## Fix Kimi K2.5 API Formatting Errors

### Issues Found

Two formatting errors in `modal-app/agent/orchestrator.py` that will cause API failures:

---

### 1. `thinking` parameter has wrong type (line 707)

**Current (WRONG):**
```python
thinking=True,
```

**Correct:**
```python
thinking={"type": "enabled"},
```

The Kimi K2.5 API docs explicitly state this parameter is an **object**, not a boolean. Valid values are `{"type": "enabled"}` or `{"type": "disabled"}`. Passing `True` will likely cause a 400 error or be silently ignored.

---

### 2. `reasoning_content` must ALWAYS be present in assistant tool-call messages (lines 748-749)

**Current (WRONG):** Only includes `reasoning_content` conditionally:
```python
if hasattr(msg, "reasoning_content") and msg.reasoning_content:
    assistant_msg["reasoning_content"] = msg.reasoning_content
```

**Correct:** Always include it, even as empty string:
```python
assistant_msg["reasoning_content"] = getattr(msg, "reasoning_content", "") or ""
```

The Kimi API returns a 400 error (`"thinking is enabled but reasoning_content is missing in assistant tool call message"`) if any assistant message with tool_calls is missing the `reasoning_content` field during multi-step tool calling. This is a well-documented issue confirmed across multiple integration projects (Goose, OpenCode).

---

### Changes

**File: `modal-app/agent/orchestrator.py`**

| Line | Change |
|------|--------|
| 707 | Change `thinking=True` to `thinking={"type": "enabled"}` |
| 748-749 | Replace conditional reasoning_content with always-present: `assistant_msg["reasoning_content"] = getattr(msg, "reasoning_content", "") or ""` |

### Impact
- These are the only two changes needed
- Both are single-line fixes
- Without these fixes, multi-step tool calling will fail on the second iteration when the API validates the conversation history

