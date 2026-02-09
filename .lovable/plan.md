

## Fix Column B Styling and Date Header

Two distinct issues to fix:

### Issue 1: Styling — New Column B Cells Have No Formatting

**Root cause**: The `update_cell` method in `updater.py` (line 40) just does `sheet[cell_ref] = value` with no formatting. The `insert_new_period_column` method copies styling for rows 1-2 (headers), but data cells written via `update_excel_cell` get no styling at all. That is why column B has plain numbers without commas, bold, colors, etc.

**Fix**: After setting a cell value in column B, copy the formatting (font, fill, alignment, border, number_format) from column C of the same row (which is the shifted original data and has the correct styling).

**File**: `modal-app/agent/updater.py`

In `update_cell` (around line 39-41), after setting the value, check if the cell is in column B (column index 2). If so, copy formatting from column C (column index 3) of the same row — exactly like the header styling copy already done in `insert_new_period_column`.

```python
from openpyxl.utils import column_index_from_string

def update_cell(self, sheet_name, cell_ref, value):
    # ... existing code to set value ...
    sheet[cell_ref] = value
    
    # Auto-copy formatting from adjacent column C if writing to column B
    cell = sheet[cell_ref]
    if cell.column == 2:  # Column B
        source = sheet.cell(row=cell.row, column=3)  # Column C
        cell.font = copy(source.font)
        cell.fill = copy(source.fill)
        cell.alignment = copy(source.alignment)
        cell.border = copy(source.border)
        cell.number_format = source.number_format
```

This ensures every data cell in the new column B automatically inherits the same styling as the adjacent historical data.

### Issue 2: Date Header Still Using report_date

**Root cause**: The instructions tell the agent to use `fiscal_period_end` as the `date_header`, but the agent still chose `2026-02-09` (the report_date). The agent has free choice over what string it passes to `insert_new_period_column`, and it ignored the instruction.

**Fix**: Remove the agent's ability to choose the wrong date. Override the `date_header` in the `insert_new_period_column` tool handler (in `orchestrator.py`) so the correct date is forced regardless of what the agent passes.

**File**: `modal-app/agent/orchestrator.py`

In the `handle_tool_call` function, in the `insert_new_period_column` branch (around line 442-460):

```python
elif tool_name == "insert_new_period_column":
    bucket_name = context.current_file
    # ... existing checks ...
    
    # Force the correct fiscal_period_end date as date_header
    # (override whatever the agent passed — it may use report_date by mistake)
    correct_date = context.fiscal_period_end or tool_input["date_header"]
    
    result = updater.insert_new_period_column(
        tool_input["sheet_name"],
        correct_date,          # forced correct date
        tool_input["period_header"]
    )
```

This requires storing `fiscal_period_end` on the `AgentContext` so the tool handler can access it.

In the `AgentContext.__init__` (around line 281), add:
```python
self.fiscal_period_end: str | None = None
```

In `run_agent` (around line 551), set it:
```python
context = AgentContext(ticker, work_dir, files)
context.fiscal_period_end = fiscal_period_end
```

### Files Modified

| File | Changes |
|---|---|
| `modal-app/agent/updater.py` | Auto-copy formatting from column C when writing to column B |
| `modal-app/agent/orchestrator.py` | Store `fiscal_period_end` on AgentContext; override `date_header` in tool handler to force correct date |

### Why This Approach

- **Styling**: Handled at the infrastructure level so the agent never needs to worry about formatting. Every cell it writes to column B automatically looks like the rest of the file.
- **Date**: Hardcoded override removes the possibility of the agent using the wrong date, regardless of what it "decides" to pass. The instructions remain as guidance, but the code enforces correctness.
