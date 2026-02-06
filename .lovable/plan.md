

## Fix: Remove Extra Leading Space from Every Line

The problem is that **every line in `modal-app/app.py` has one extra leading space**. For example:

- Line 1 starts with ` """` instead of `"""`
- Line 15 starts with ` import modal` instead of `import modal`
- Line 20 starts with ` app = modal.App(...)` instead of `app = modal.App(...)`

Python requires top-level statements (imports, class/function definitions, variable assignments) to start at column 0 with no leading whitespace. Right now, everything is shifted one space to the right, causing indentation errors throughout the file.

### What will change

**File: `modal-app/app.py`**

Remove exactly one leading space from every line in the file. This is a whitespace-only change — no logic or content changes. After the fix:

- Top-level code (imports, `app = ...`, `image = ...`, function decorators) will start at column 0
- Function body code will use standard 4-space indentation
- Nested blocks will use 8-space, 12-space, etc. as expected

### After the fix

Re-run:

```
cd modal-app
modal deploy app.py
```

It should deploy without any indentation errors.

