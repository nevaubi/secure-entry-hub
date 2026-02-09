

## Fix: Replace deprecated `modal.Mount` with `image.add_local_dir()`

### Root Cause

Your installed version of the Modal SDK no longer includes `modal.Mount` — it was deprecated and removed in recent versions. The modern way to include local directories is to use `.add_local_dir()` on the image definition.

### What changes

**File: `modal-app/app.py`**

1. Remove the `agent_mount` line entirely (line 44-45)
2. Add `.add_local_dir("agent", remote_path="/root/agent")` to the image definition chain (after `.run_commands(...)`)
3. Remove `mounts=[agent_mount]` from both `@app.function` decorators, reverting them back to their original form

**Before:**
```python
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(...)
    .run_commands("playwright install chromium", "playwright install-deps chromium")
)

agent_mount = modal.Mount.from_local_dir("agent", remote_path="/root/agent")

@app.function(image=image, secrets=secrets, timeout=600, mounts=[agent_mount])
```

**After:**
```python
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(...)
    .run_commands("playwright install chromium", "playwright install-deps chromium")
    .add_local_dir("agent", remote_path="/root/agent")
)

@app.function(image=image, secrets=secrets, timeout=600)
```

### Files modified

| File | Change |
|---|---|
| `modal-app/app.py` | Move local dir into image definition, remove Mount references |

After this change, redeploy with `modal deploy app.py` and re-test.

