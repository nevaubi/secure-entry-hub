

## Fix: Add `public/` to storage download URL path

### Root Cause

All 12 downloads fail with HTTP 400 because the download URL is missing the `public/` path segment. The buckets on your external storage (`auth.deltasage.ai`) are public buckets.

**Current URL built by code:**
```
{EXTERNAL_SUPABASE_URL}/storage/v1/object/financials-annual-income/PLTR.xlsx
```

**Correct URL (matches your working example):**
```
{EXTERNAL_SUPABASE_URL}/storage/v1/object/public/financials-annual-income/PLTR.xlsx
```

### What changes

**File: `modal-app/agent/storage.py`**

1. **Line 56** (download URL): Add `public/` to the path

```python
# Before:
url = f"{self.supabase_url}/storage/v1/object/{bucket}/{file_path}"

# After:
url = f"{self.supabase_url}/storage/v1/object/public/{bucket}/{file_path}"
```

2. **Line 87** (upload URL): Keep using the authenticated endpoint (uploads require auth, no `public/` needed) -- no change needed here.

### Also verify

Make sure the `EXTERNAL_SUPABASE_URL` Modal secret is set to `https://auth.deltasage.ai` (matching the base domain from your working URL). If it's currently set to something else (like a `.supabase.co` URL), that would also cause failures.

### Files modified

| File | Change |
|---|---|
| `modal-app/agent/storage.py` | Add `public/` to download URL path on line 56 |

After this change, redeploy with `modal deploy app.py` and re-test with `modal run app.py::test_single_ticker --ticker PLTR`.

