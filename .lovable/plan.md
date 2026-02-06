

## Fix Modal Deployment Errors

The deployment is failing because of two issues in `modal-app/app.py`:

### Problem 1: FastAPI not included in the container image
The Modal container image (lines 23-32 of `app.py`) lists dependencies explicitly but does not include `fastapi`. Modal used to bundle it automatically, but no longer does.

### Problem 2: Deprecated decorator
The `@modal.web_endpoint` decorator on line 117 has been renamed to `@modal.fastapi_endpoint`. Modal is warning about this and failing.

---

### Changes

**File: `modal-app/app.py`**

1. Add `"fastapi[standard]"` to the `.pip_install(...)` call in the image definition (around line 25).
2. Replace `@modal.web_endpoint(method="POST")` with `@modal.fastapi_endpoint(method="POST")` on line 117.

**File: `modal-app/requirements.txt`**

3. Add `fastapi[standard]>=0.115.0` for documentation purposes.

---

### After the fix

Once I make these changes, you just need to re-run:

```
modal deploy app.py
```

It should deploy cleanly this time, and give you the webhook URL we need for the next step.

