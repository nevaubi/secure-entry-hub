

## Fix Indentation in modal-app/app.py

The `.pip_install()` arguments (lines 26-30) have 5-space indentation (an extra space) instead of the standard 4-space indentation used throughout the rest of the file.

### Change

**File: `modal-app/app.py` (lines 25-31)**

Replace the current indentation:

```python
    .pip_install(
         "anthropic>=0.40.0",
         "openpyxl>=3.1.2", 
         "playwright>=1.40.0",
         "httpx>=0.27.0",
         "fastapi[standard]>=0.115.0",
    )
```

With correct 4-space (8-space from margin) indentation:

```python
    .pip_install(
        "anthropic>=0.40.0",
        "openpyxl>=3.1.2",
        "playwright>=1.40.0",
        "httpx>=0.27.0",
        "fastapi[standard]>=0.115.0",
    )
```

This is a one-line-per-argument fix — just removing the extra leading space on each string argument. After this, re-run `modal deploy app.py`.

