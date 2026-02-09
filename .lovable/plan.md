

## File-by-File Processing with Rich Schema and Progress Tracking

### Overview

Restructure the agent to process one Excel file at a time (12 sequential sub-runs), inject the full cell data for only the current file, and track progress via an in-memory scratchpad that gets re-injected each iteration.

### On Upstash Redis

Redis is possible but likely overkill here. The agent runs as a single Modal function call (up to 10 minutes). The in-memory scratchpad already persists across all 30 iterations within that run. Redis would add:
- A new dependency (`upstash-redis`) in the Modal image
- Network latency on every note write
- A new Modal secret (`upstash-secret` with `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN`)
- Complexity for marginal benefit

**What I recommend instead**: Use the existing in-memory scratchpad but re-inject a summary of all notes into every iteration's context. This gives the agent perfect recall without external dependencies. If you later want live monitoring or crash recovery, Redis can be added on top without changing the core logic.

If you DO want Redis (e.g., to monitor from the Lovable dashboard in real-time), I can add it in a follow-up. Just let me know.

---

### Changes

#### 1. Enhanced Schema Extraction (`modal-app/agent/schema.py`)

Replace the current "sample 5 rows, 50 empty cells" approach with a full dump for the current file:

- **All row labels** (column A values for every row)
- **All column headers** (row 1 values)
- **All cell values** in a grid format (row label + each column's value or "EMPTY")
- Cap at 200 rows to avoid context overflow, but most financial statements are under 100 rows

New function: `analyze_excel_file_full(file_path)` returns:
```python
{
    "file_name": "PLTR.xlsx",
    "sheets": [{
        "name": "Sheet1",
        "max_row": 45, "max_col": 12,
        "headers": ["A: Row Label", "B: Q4 2025", "C: Q3 2025", ...],
        "rows": [
            {"row": 2, "label": "Revenue", "cells": {"B": "EMPTY", "C": "1234567890", ...}},
            {"row": 3, "label": "Cost of Revenue", "cells": {"B": "EMPTY", "C": "567890123", ...}},
            ...
        ],
        "empty_cells": ["B2", "B3", "D5", ...]
    }]
}
```

The agent will see exactly which cells are empty and what values already exist, so it can make precise updates.

#### 2. File-by-File Processing Loop (`modal-app/agent/orchestrator.py`)

Replace the single 30-iteration loop with a structured file-by-file approach:

```text
FILE_ORDER = [
    "standardized-annual-income",
    "standardized-annual-balance",
    "standardized-annual-cashflow",
    "standardized-quarterly-income",
    "standardized-quarterly-balance",
    "standardized-quarterly-cashflow",
    "financials-annual-income",
    "financials-annual-balance",
    "financials-annual-cashflow",
    "financials-quarterly-income",
    "financials-quarterly-balance",
    "financials-quarterly-cashflow",
]

for file_name in FILE_ORDER:
    # 1. Build rich schema for ONLY this file
    # 2. Build a focused prompt: "You are working on {file_name}. Here is the full data..."
    # 3. Include scratchpad summary from all previous files
    # 4. Run sub-loop (up to 10 iterations per file)
    # 5. Save file when sub-loop completes
    # 6. Record completion in scratchpad
```

Each sub-run gets:
- A fresh message history (avoids context window bloat from previous files)
- The full cell data for only the current file
- A scratchpad summary carrying forward all notes from previous files
- Up to 10 iterations (total budget: 120 iterations across all 12 files, but most files should finish in 3-5)

#### 3. Scratchpad Re-Injection (`modal-app/agent/orchestrator.py`)

Before each iteration, build a scratchpad summary and inject it into the system prompt or as a prefixed user message:

```python
def build_scratchpad_summary(notes):
    summary = "## YOUR SCRATCHPAD (from previous work)\n"
    for note in notes:
        summary += f"- [{note['category']}] {note['content']}\n"
    return summary
```

This way the agent always "remembers" what it found in previous files and iterations.

#### 4. Updated System Prompt (`modal-app/agent/orchestrator.py`)

The per-file prompt will be more focused:

```
You are updating the file: {file_name} for ticker {ticker}.

Here is the complete data in this file:
{full_schema}

Empty cells that need data: {empty_cells_list}

Your scratchpad from previous work:
{scratchpad_summary}

WORKFLOW:
1. Review the empty cells above
2. Use browse_stockanalysis to navigate to the matching page
3. Use extract_page_with_vision to read the data
4. Use web_search to cross-reference
5. Use note_finding to record validated values
6. Use update_excel_cell to fill ONLY empty cells
7. When done with this file, respond with "FILE COMPLETE"
```

The agent knows exactly which StockAnalysis URL maps to which file:
- `standardized-annual-income` maps to `browse_stockanalysis(statement_type="income", period="annual", data_type="standardized")`
- `financials-quarterly-balance` maps to `browse_stockanalysis(statement_type="balance", period="quarterly", data_type="as-reported")`
- etc.

#### 5. Mapping File Names to StockAnalysis Parameters

Add a helper that maps bucket names to browse parameters:

```python
FILE_TO_BROWSE_PARAMS = {
    "standardized-annual-income": ("income", "annual", "standardized"),
    "standardized-annual-balance": ("balance", "annual", "standardized"),
    "standardized-annual-cashflow": ("cashflow", "annual", "standardized"),
    "standardized-quarterly-income": ("income", "quarterly", "standardized"),
    "standardized-quarterly-balance": ("balance", "quarterly", "standardized"),
    "standardized-quarterly-cashflow": ("cashflow", "quarterly", "standardized"),
    "financials-annual-income": ("income", "annual", "as-reported"),
    "financials-annual-balance": ("balance", "annual", "as-reported"),
    "financials-annual-cashflow": ("cashflow", "annual", "as-reported"),
    "financials-quarterly-income": ("income", "quarterly", "as-reported"),
    "financials-quarterly-balance": ("balance", "quarterly", "as-reported"),
    "financials-quarterly-cashflow": ("cashflow", "quarterly", "as-reported"),
}
```

This is included in the per-file prompt so the agent knows exactly which URL to visit.

---

### Files Modified

| File | Changes |
|---|---|
| `modal-app/agent/schema.py` | Add `analyze_excel_file_full()` that returns all row labels, headers, and cell values |
| `modal-app/agent/orchestrator.py` | Replace single loop with file-by-file processing, add scratchpad re-injection, add `FILE_TO_BROWSE_PARAMS` mapping, update per-file system prompt |

### After Deploying

1. `modal deploy app.py`
2. `modal run app.py::test_single_ticker --ticker PLTR`

You will see:
- "Processing file 1/12: standardized-annual-income" headers
- Full cell data for only the current file in the prompt
- Scratchpad notes carrying forward between files
- Each file saved individually as it completes
- Clear progress: "File complete. 4/12 files processed."

