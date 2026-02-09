

## Fix Column Insertion: Styling + Data Population

### Problem 1: Missing Header Styling

`openpyxl`'s `sheet.insert_cols(2)` creates a blank column with no formatting. The new B1/B2 cells have plain text while the original headers (now shifted to C) keep their dark background + white text.

**Fix in `modal-app/agent/updater.py`**: After inserting the column, copy the cell style (font, fill, alignment, border) from column C (the shifted original) to the new column B for header rows.

```python
from copy import copy

# After insert_cols(2), copy formatting from C1/C2 to B1/B2
for row in [1, 2]:
    source_cell = sheet.cell(row=row, column=3)  # Old header, now shifted to C
    target_cell = sheet.cell(row=row, column=2)   # New header in B
    target_cell.font = copy(source_cell.font)
    target_cell.fill = copy(source_cell.fill)
    target_cell.alignment = copy(source_cell.alignment)
    target_cell.border = copy(source_cell.border)
    target_cell.number_format = source_cell.number_format
```

### Problem 2: No Data in New Column

The agent has only 10 iterations per file. The current workflow requires it to:
1. Call `insert_new_period_column` (1 iteration)
2. Call `browse_stockanalysis` (1 iteration)
3. Call `extract_page_with_vision` (1 iteration)
4. Call `web_search` for cross-referencing (1 iteration)
5. Call `update_excel_cell` for each of 30-50 cells (multiple iterations, each iteration can batch a few tool calls)

This is tight. Additionally, the agent may be confused about what to do after the insertion since the schema it was given at the start no longer matches (columns shifted).

**Fixes:**

**A. Increase per-file iteration budget** (`modal-app/agent/orchestrator.py`)
- Change `max_file_iterations` from 10 to 15 for files needing column insertion

**B. Re-analyze file after column insertion** (`modal-app/agent/orchestrator.py`)
- After `insert_new_period_column` succeeds, re-run `analyze_excel_file_full` on the modified workbook and return the updated schema as part of the tool result
- This way the agent sees the new column B with EMPTY cells and knows exactly which cells to fill

**C. Include row labels in insertion result** (`modal-app/agent/updater.py`)
- The `insert_new_period_column` return value should include which row labels map to which row numbers, so the agent can match StockAnalysis data to the correct cells without re-analyzing

Updated `insert_new_period_column` return:
```python
{
    "success": True,
    "data_rows": [3, 4, 5, ...],
    "row_map": [
        {"row": 3, "label": "Total Assets", "cell": "B3"},
        {"row": 4, "label": "Current Assets", "cell": "B4"},
        ...
    ],
    "message": "New column B inserted. Fill these cells: B3 (Total Assets), B4 (Current Assets), ..."
}
```

This gives the agent a direct mapping of cell references to financial line items, so after extracting data from StockAnalysis it can immediately populate cells without guessing.

**D. Simplify prompt for insertion case** (`modal-app/agent/orchestrator.py`)
- When a new column is needed, streamline the workflow instructions: browse once, extract once, then batch-fill all cells
- Remove the dual-source validation requirement for the insertion case (it slows things down and the agent runs out of iterations)

### Files Modified

| File | Changes |
|---|---|
| `modal-app/agent/updater.py` | Copy header styling from adjacent column after insertion; include row labels + cell refs in return value |
| `modal-app/agent/orchestrator.py` | Increase iteration budget for insertion files (10 to 15); return updated schema after insertion; simplify insertion workflow prompt |

### Technical Details

**Styling copy approach**: Uses `copy()` from Python's `copy` module on openpyxl style objects (Font, PatternFill, Alignment, Border). These are immutable-like objects in openpyxl that must be copied rather than assigned by reference.

**Row map in insertion result**: Scans column A for labels and column C (shifted data) for non-empty values. Only includes rows where C has data, paired with their A-column label. This gives the agent ~30-50 entries like `{"row": 3, "label": "Total Assets", "cell": "B3"}`.

**Iteration budget**: Files needing insertion get 15 iterations. Files with just empty cells keep 10. This accounts for the extra browse + extract + fill cycle.
