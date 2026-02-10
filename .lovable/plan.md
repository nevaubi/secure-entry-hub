

## Fix: Stuck "In Progress" Status and Blank Column Uploads

### Problem Summary

Two issues were identified:

1. **Status stuck on "pending/in progress"**: After JPM finished processing on Modal, the callback to update the status in the database was never received. The `excel_processing_runs` record still shows `status: pending` with no `completed_at`. This means the callback from Modal either failed silently or was never sent.

2. **Blank columns uploaded**: When the agent exhausts all 15 iterations without completing a file, the orchestrator still uploads the file (because it was marked as "modified" when the column was inserted, even though no data was filled in).

### Root Causes

**Issue 1 -- Callback never received:**
- The Modal `process_ticker` function sends the callback via `httpx.post`, but if the request fails (wrong URL, timeout, auth issue), the error is silently swallowed (lines 100-116 in `app.py`)
- The `backfill-trigger-single` edge function sets status to `pending` and then relies entirely on the Modal callback to update it -- there is no fallback

**Issue 2 -- Blank files uploaded:**
- In `orchestrator.py` line 725, any file in `context.files_modified` gets uploaded after the sub-loop ends
- A file gets added to `files_modified` when `insert_new_period_column` is called (line 474), even if no data cells are subsequently written
- So if the agent inserts a column but runs out of iterations before filling it, a blank column gets uploaded

### Solution

#### Part 1: Add a timeout-based status check on the frontend (Backfill.tsx)

Since the callback mechanism can fail silently, add a safety net: if a ticker has been in "pending" status for more than 45 minutes (the Modal timeout is 30 min), automatically mark it as "failed" via a direct database update. This gives the user the ability to retry.

Add a "Mark Stale as Failed" button that:
- Finds all rows with `status = 'pending'` where `started_at` is older than 45 minutes
- Updates their status to `failed` with `error_message: 'Timed out -- no callback received'`
- Refreshes the table

Also allow the "Process" button to work on `failed` rows (already works per line 272) so users can retry.

#### Part 2: Track cells written per file in the orchestrator (orchestrator.py)

Add a counter `cells_written` per file. Only upload a file if at least one data cell was actually written (not just column inserted). This prevents blank columns from being uploaded.

In the `handle_tool_call` function for `update_excel_cell`, increment a per-file counter. After the sub-loop, check this counter before uploading.

#### Part 3: Improve callback reliability (app.py)

Add logging when the callback fails so you can debug it. Also add a retry (1 retry with a short delay) for the callback POST.

---

### File Changes

| File | Change |
|---|---|
| `src/pages/Backfill.tsx` | Add "Mark Stale as Failed" button that updates tickers stuck in pending for 45+ minutes to failed status. This allows retry via the Process button. |
| `modal-app/agent/orchestrator.py` | Track `cells_written_count` per file. Only upload if count > 0 (skip upload for files where only a column was inserted but no data written). |
| `modal-app/app.py` | Add error logging and one retry attempt for the callback POST to improve reliability. |

### Technical Details

**Backfill.tsx -- "Mark Stale as Failed" button:**
```
- Query excel_processing_runs for status='pending' AND started_at < (now - 45 min)
- PATCH those records to status='failed', error_message='Timed out - no callback received'
- Refetch runs to update UI
```

**orchestrator.py -- cells_written tracking:**
```
- Add context.cells_written: dict[str, int] = {} to AgentContext
- In handle_tool_call for update_excel_cell, increment context.cells_written[bucket_name]
- At line 725, change condition from "if file_name in context.files_modified" to also check cells_written > 0
- Log a warning when skipping upload due to no cells written
```

**app.py -- callback retry:**
```
- Wrap the httpx.post callback in a retry loop (max 2 attempts, 5s delay)
- Log the exception on failure so it appears in Modal logs for debugging
```

