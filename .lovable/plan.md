

## Fix: Module path issue with `add_local_dir`

### Root Cause

The `agent/` directory is mounted at `/root/agent` using `add_local_dir("agent", remote_path="/root/agent")`. However, Python needs `/root` to be on `sys.path` for `from agent.orchestrator import run_agent` and the relative imports (`from .browser import ...`) to work.

The `add_local_dir` method copies files but doesn't guarantee the parent directory is on Python's module search path. Modal's working directory and `sys.path` may not include `/root`.

### Fix

Change the remote path to place the `agent` directory somewhere that **is** on Python's default `sys.path` — or explicitly add `/root` to `sys.path` before importing.

The simplest and most reliable approach: copy the `agent` directory into the **app's working directory** by using `remote_path="/root/agent"` but also adding a `sys.path` fix, **or** (better) change the remote path to a location already on `sys.path`.

**Recommended approach:** Use `copy_local_dir` instead, or change the remote path to sit under a known Python path. The cleanest solution is to add `sys.path.insert(0, "/root")` before the import in `process_ticker`.

### What changes

**File: `modal-app/app.py`**

In the `process_ticker` function (around line 65-66), add a `sys.path` fix before the import:

```python
# Before:
import httpx
from agent.orchestrator import run_agent

# After:
import sys
sys.path.insert(0, "/root")
import httpx
from agent.orchestrator import run_agent
```

Apply the same fix in the `webhook` function if it also imports from `agent`.

This ensures that when Python tries to resolve `agent.orchestrator`, it looks in `/root/` and finds `/root/agent/orchestrator.py`, which then correctly resolves the relative imports (`from .browser`, `from .storage`, etc.) within the `agent` package.

### Files modified

| File | Change |
|---|---|
| `modal-app/app.py` | Add `sys.path.insert(0, "/root")` before `from agent.orchestrator import run_agent` in both `process_ticker` and `webhook` functions |

After this change, redeploy with `modal deploy app.py` and re-test with `modal run app.py::test_single_ticker --ticker PLTR`.
