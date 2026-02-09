

## Focus Agent on Newest Column Only

### The Problem

When a new column is inserted, the agent receives **all empty cells across the entire file** (e.g., J2 from 2016, old periods). The agent then wastes iterations researching ancient financial data instead of focusing on filling the newly inserted column B.

From the screenshots: the agent is searching for "Uber Technologies 2016 2017 2018 annual income statement" and chasing old restructuring charges — completely ignoring the newest column it just inserted.

### Root Cause

Line 625 in `orchestrator.py`:
```python
messages = [{"role": "user", "content": f"...EMPTY CELLS NEEDING DATA ({len(empty_cells)} total):\n{', '.join(empty_cells)..."}]
```

`empty_cells` contains cells from ALL columns (B, C, D, ... J). When `needs_new_column` is true, the agent should ONLY care about column B cells.

### Fix

**In `modal-app/agent/orchestrator.py`** (line 625 area):

When `needs_new_column` is true, filter empty cells to column B only (or omit them entirely since the `row_map` from insertion will guide the agent):

```python
if needs_new_column:
    # Only show column B cells (or none — the insert tool returns row_map)
    filtered_empty = [c for c in empty_cells if c.startswith("B")]
    messages = [{
        "role": "user",
        "content": f"Begin processing {file_name} for {ticker}. "
                   f"Report date: {report_date}, timing: {timing}.\n\n"
                   f"COMPLETE FILE DATA:\n{full_schema}\n\n"
                   f"A NEW COLUMN INSERTION IS REQUIRED. Focus ONLY on the newest period.\n"
                   f"Do NOT fill old/historical empty cells. Only fill column B after insertion."
    }]
else:
    messages = [{
        "role": "user",
        "content": f"Begin processing {file_name} for {ticker}. "
                   f"Report date: {report_date}, timing: {timing}.\n\n"
                   f"COMPLETE FILE DATA:\n{full_schema}\n\n"
                   f"EMPTY CELLS NEEDING DATA ({len(empty_cells)} total):\n"
                   f"{', '.join(empty_cells) if empty_cells else 'None'}"
    }]
```

Also reinforce in the system prompt's `CRITICAL RULES` section:

```text
- When a new column is being inserted, IGNORE all empty cells in columns C, D, E, etc.
  Your ONLY job is to fill the NEW column B with the latest period's data.
  Do NOT research or fill historical data from older periods.
```

### Files Modified

| File | Changes |
|---|---|
| `modal-app/agent/orchestrator.py` | Filter first message to exclude old empty cells when inserting a new column; add explicit instruction to ignore historical columns |

### Why This Works

- The agent no longer sees "J2 is empty" or "F5 is empty" when doing a column insertion
- The system prompt and first message both reinforce: "only fill column B"
- The `insert_new_period_column` tool already returns a `row_map` with exact B-column cell references, so the agent has everything it needs
- Old empty cells in historical columns are preserved for non-insertion runs where the agent has time to validate them properly

