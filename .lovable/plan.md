

## Fix: Mount agent to a Python-native path (no more sys.path hacks)

### Why it keeps failing

The `sys.path.insert(0, "/root")` fix only takes effect at runtime inside the function body. But `add_local_dir` places files during image build, and Python's default `sys.path` in Modal's Debian slim image does NOT include `/root`. The error persists because the module resolution still can't find the package.

### The real fix

Instead of fighting `sys.path`, mount the `agent/` directory directly into Python's `site-packages` where it will be found automatically -- no path manipulation needed.

### What changes

**File: `modal-app/app.py`**

1. Change the `add_local_dir` remote path from `/root/agent` to Python's site-packages:

```python
# Before:
.add_local_dir("agent", remote_path="/root/agent")

# After:
.add_local_dir("agent", remote_path="/usr/local/lib/python3.11/site-packages/agent")
```

2. Remove the `sys.path` hack from `process_ticker` (lines 65-66):

```python
# Remove these two lines:
import sys
sys.path.insert(0, "/root")
```

### Why this works

Python's `site-packages` is always on `sys.path` by default. By placing the `agent/` directory there, `from agent.orchestrator import run_agent` and all relative imports (`from .browser import ...`) work immediately with zero path manipulation.

### Files modified

| File | Change |
|---|---|
| `modal-app/app.py` | Change `remote_path` to site-packages, remove `sys.path` hack |

After this change, redeploy with `modal deploy app.py` and re-test with `modal run app.py::test_single_ticker --ticker PLTR`.
