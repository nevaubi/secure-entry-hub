

## Fix: `ModuleNotFoundError: No module named 'agent'`

### Root Cause

Modal only auto-mounts the single entry file (`app.py`). The `agent/` subdirectory (containing `orchestrator.py`, `browser.py`, etc.) is **not being uploaded** to the Modal container, so Python cannot import it.

### Fix

Add a `modal.Mount` to the `@app.function` decorator in `modal-app/app.py` that includes the `agent/` package.

### Technical Details

**File: `modal-app/app.py`**

1. Add a mount definition after the secrets list (around line 42):

```python
# Mount the agent package so it's available in the container
agent_mount = modal.Mount.from_local_dir("agent", remote_path="/root/agent")
```

2. Update the `@app.function` decorator on line 45 to include the mount:

```python
@app.function(image=image, secrets=secrets, timeout=600, mounts=[agent_mount])
```

3. Apply the same mount to **any other `@app.function`** that imports from `agent` (check `test_single_ticker` and `webhook` if they also call `process_ticker`).

After this change, redeploy with `modal deploy app.py` and re-run the test.
