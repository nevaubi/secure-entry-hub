

## Reorder Files: Quarterly First, Then Conditionally Process Annual

### Concept

Reorder `FILE_ORDER` so the 3 quarterly files are processed first. After all 3 quarterly files complete, check what period header the agent actually wrote (e.g., "Q4 2025" vs "Q1 2025"). If the quarter is Q4, continue processing the 3 annual files. Otherwise, skip them entirely.

### Changes

**File**: `modal-app/agent/orchestrator.py`

**1. Reorder FILE_ORDER** (lines 30-37)

```python
FILE_ORDER = [
    "financials-quarterly-income",
    "financials-quarterly-balance",
    "financials-quarterly-cashflow",
    "financials-annual-income",
    "financials-annual-balance",
    "financials-annual-cashflow",
]
```

**2. Track the period header used during quarterly processing**

Add a variable before the file loop (around line 579) to track the quarter:

```python
detected_quarter = None  # Will be set after first quarterly file completes
```

Inside the `insert_new_period_column` tool handler (around line 473), capture the `period_header` the agent passes:

```python
# After the insert call succeeds
if result.get("success"):
    context.files_modified.add(bucket_name)
    # Track the period header for quarterly skip logic
    if "quarterly" in bucket_name:
        context.detected_quarter = tool_input["period_header"]
```

**3. Skip annual files if quarter is not Q4**

Inside the file processing loop (line 581), before processing each file, add:

```python
for file_idx, file_name in enumerate(FILE_ORDER, 1):
    # Skip annual files if the quarterly report was not Q4
    if "annual" in file_name and hasattr(context, 'detected_quarter') and context.detected_quarter:
        if "Q4" not in context.detected_quarter.upper():
            print(f"  Skipping {file_name} -- {context.detected_quarter} report, not Q4/annual")
            context.completed_files.append(file_name)
            context.notes.append({
                "category": "file_skipped",
                "content": f"{file_name}: Skipped -- {context.detected_quarter} report, annual files only updated for Q4.",
                "file": file_name,
                "timestamp": time.time(),
            })
            continue
    # ... rest of existing loop
```

### How It Works

```text
1. Agent processes quarterly-income -> inserts column with e.g. "Q1 2025"
2. detected_quarter = "Q1 2025"
3. Agent processes quarterly-balance and quarterly-cashflow
4. Loop reaches annual-income -> checks detected_quarter
5. "Q4" not in "Q1 2025" -> skip all 3 annual files
6. Done -- only quarterly files were updated

If Q4:
1. Agent processes all 3 quarterly files -> detected_quarter = "Q4 2025"  
2. "Q4" IS in "Q4 2025" -> process all 3 annual files too
3. All 6 files updated
```

### Why This Is Better Than Date-Based Detection

- Uses the agent's actual output (the period header it wrote) rather than computing month differences
- No date parsing or fiscal year assumptions needed
- The agent already determines the correct quarter from the Gemini vision extraction
- Simple string check: does it contain "Q4" or not

### Files Modified

| File | Changes |
|---|---|
| `modal-app/agent/orchestrator.py` | Reorder FILE_ORDER to quarterly-first; track `detected_quarter` from `insert_new_period_column`; skip annual files if quarter is not Q4 |

