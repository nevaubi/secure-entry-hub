

## Increase Iterations to 15 and Switch to Claude Sonnet 4.5

### Changes

**File**: `modal-app/agent/orchestrator.py`

**1. Increase max iterations back to 15** (line 656)

```python
# Change from:
max_file_iterations = 5
# To:
max_file_iterations = 15
```

Also update the system prompt comment/language that references "5 iterations" back to "15 iterations" so the agent knows its budget.

**2. Switch model from Opus to Sonnet** (line 663)

```python
# Change from:
model="claude-opus-4-6"
# To:
model="claude-sonnet-4-5"
```

### Why Sonnet Works Here

- The agent's task is structured: browse a page, extract via Gemini vision, match row labels, and write cells
- Sonnet 4.5 handles tool-calling and structured reasoning well for this type of workflow
- Significantly lower cost and faster response times per iteration
- With 15 iterations available, the agent has ample room even if Sonnet needs an extra pass

### Files Modified

| File | Changes |
|---|---|
| `modal-app/agent/orchestrator.py` | Change `max_file_iterations` from 5 to 15; change model from `claude-opus-4-6` to `claude-sonnet-4-5`; update prompt references to iteration count |
