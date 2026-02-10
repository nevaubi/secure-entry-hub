

## Increase Modal Function Timeout

### Problem
The `process_ticker` function in `modal-app/app.py` has `timeout=600` (10 minutes), which is not enough for the full agent workflow.

### Solution
Increase the timeout on line 47 of `modal-app/app.py`. Modal supports up to 86,400 seconds (24 hours) on paid plans.

**Recommended value**: `1800` (30 minutes) -- enough for 6 files with 15 iterations each, with buffer.

### Change

**File**: `modal-app/app.py` (line 47)

| Before | After |
|---|---|
| `@app.function(image=image, secrets=secrets, timeout=600)` | `@app.function(image=image, secrets=secrets, timeout=1800)` |

After updating, redeploy with `modal deploy app.py`.

