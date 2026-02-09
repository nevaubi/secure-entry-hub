

## Emphasize Cell Writing After Data Gathering

### What Changes

Two small text additions in `modal-app/agent/orchestrator.py` — no logic changes, just clearer instructions.

### 1. Update the initial user message for new column insertion (line 629)

Add a clear reminder at the end of the message:

```
Once you have gathered the financial values, you MUST call update_excel_cell for EVERY data row in column B.
Use FULL absolute numbers (e.g., 394328000000 not 394.3B or 394,328).
Match each value to the correct row label carefully before inserting.
Do NOT stop after extracting data — the job is not done until every cell is written.
```

### 2. Add to CRITICAL RULES in the system prompt (around line 268)

Add one rule reinforcing the write-back requirement:

```
- After gathering financial data, you MUST call update_excel_cell for every target row.
  Do NOT stop after browsing or extracting — the file is not complete until cells are written.
  Always use fully written-out absolute numbers (e.g., 394328000000 not 394.3B).
  Carefully match each value to its corresponding row label before writing.
```

### Files Modified

| File | Change |
|---|---|
| `modal-app/agent/orchestrator.py` | Add write-back emphasis to initial message (line 629) and CRITICAL RULES section (line 268) |

### Why This Is Enough

- The agent already has the tools and the row_map — it just needs a clear nudge to actually use them
- No workflow restriction or rigid step sequence — the agent retains flexibility in how it gathers data
- The emphasis on full numbers and row-label matching addresses accuracy concerns

