
## Remove All Standardized Excel Files from Agent

### What Changes

Remove the 6 standardized file references from 3 files, reducing the agent from 12 files to 6 (as-reported only).

### 1. `modal-app/agent/orchestrator.py`

**FILE_ORDER (lines 30-36):** Remove the 6 standardized entries, leaving only:
```python
FILE_ORDER = [
    "financials-annual-income",
    "financials-annual-balance",
    "financials-annual-cashflow",
    "financials-quarterly-income",
    "financials-quarterly-balance",
    "financials-quarterly-cashflow",
]
```

**FILE_TO_BROWSE_PARAMS (lines 47-52):** Remove the 6 standardized entries, keeping only the `financials-*` mappings.

**browse_stockanalysis tool schema (line 81):** Change `data_type` enum from `["standardized", "as-reported"]` to just `["as-reported"]`, since the agent will never need to browse standardized pages.

**Docstring (line 5):** Update "12 sequential sub-runs" to "6 sequential sub-runs".

### 2. `modal-app/agent/storage.py`

**BUCKET_MAPPING (lines 20-25):** Remove the 6 standardized bucket entries, keeping only `financials-*` buckets.

**download_all_files docstring (line 113):** Update "12 Excel files" to "6 Excel files".

### 3. `modal-app/agent/browser.py`

No structural changes needed. The `_build_url` and `navigate_to_financials` methods accept `data_type` as a parameter generically -- they will simply never receive `"standardized"` anymore since it's removed from the orchestrator's file list. The code remains backward-compatible if standardized is ever re-added.

### Files Modified

| File | Changes |
|---|---|
| `modal-app/agent/orchestrator.py` | Remove 6 standardized entries from FILE_ORDER and FILE_TO_BROWSE_PARAMS; update tool enum; update docstring |
| `modal-app/agent/storage.py` | Remove 6 standardized entries from BUCKET_MAPPING; update docstring |

### What This Does NOT Touch

- No database changes
- No edge function changes
- The storage buckets themselves remain in place (data is preserved) -- the agent simply stops downloading/processing those files
- The browser module stays generic and unchanged
