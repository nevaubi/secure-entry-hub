

## New Column Insertion for Earnings Updates

### The Problem

The current agent only fills empty cells. But the Excel files (like the ZM example) have **no empty cells** — they're fully populated through the most recent quarter. When a company reports new earnings, the agent needs to **insert a new leftmost data column** with the new period's data.

### How It Should Work

Using ZM as an example, if the current leftmost data is:

```text
Col B: 2025-10-31 / Q3 2026
```

And ZM reports Q4 2026 earnings (date 2026-01-31), the agent must:

1. Insert a new column B, shifting everything right
2. Set B1 = `2026-01-31`, B2 = `Q4 2026`
3. Fill B3+ with new financial data for every row that has data in adjacent columns (C, D, etc.)

### Changes

#### 1. `modal-app/agent/updater.py` -- Add column insertion

Add an `insert_column` method to `ExcelUpdater`:

- Uses `openpyxl`'s `sheet.insert_cols(2)` to insert a blank column at position B (column 2), shifting all existing data right
- Sets the header values (row 1: date, row 2: fiscal period) in the new column
- Returns a list of "data rows" -- row numbers where adjacent columns (now column C after the shift) have values, so the agent knows which cells to populate

New tool-facing method:
```python
def insert_new_period_column(self, sheet_name, date_header, period_header):
    # 1. Insert blank column at B (index 2)
    # 2. Set B1 = date_header (e.g., "2026-01-31")
    # 3. Set B2 = period_header (e.g., "Q4 2026")
    # 4. Scan column C (the old data) to find which rows have values
    # 5. Return list of rows needing data (e.g., [3, 4, 5, 6, ...])
```

#### 2. `modal-app/agent/orchestrator.py` -- Add `insert_column` tool + update workflow

**New tool definition**: `insert_new_period_column`
```python
{
    "name": "insert_new_period_column",
    "description": "Insert a new column B into the current Excel file for a new fiscal period. Shifts all existing data right. Sets the date and period headers. Returns which rows need data.",
    "input_schema": {
        "properties": {
            "sheet_name": {"type": "string"},
            "date_header": {"type": "string", "description": "e.g. '2026-01-31'"},
            "period_header": {"type": "string", "description": "e.g. 'Q4 2026'"}
        },
        "required": ["sheet_name", "date_header", "period_header"]
    }
}
```

**Updated tool handler**: Calls `updater.insert_new_period_column()` and returns the list of rows needing data.

**Updated system prompt**: The workflow changes to:

```text
WORKFLOW:
1. Look at the file data. Check if a new column needs to be inserted:
   - Compare the report_date with the leftmost date column (B1)
   - If the report_date is newer than B1, insert a new column
   - If B1 is already the report_date, just fill any empty cells
2. If inserting: call insert_new_period_column with the correct date and fiscal period
3. Browse StockAnalysis to get the latest financial data
4. Use vision extraction and web search to gather and validate values
5. Use update_excel_cell to fill the new column's cells (B3, B4, B5, etc.)
6. When done, respond with "FILE COMPLETE"
```

The agent will use the `report_date` and `timing` parameters (already passed into `run_agent`) plus the existing file headers to determine the correct fiscal period label. For example:
- ZM's fiscal year ends January 31, so Q4 2026 ends on 2026-01-31
- The agent sees B1 = `2025-10-31` (Q3 2026) and report_date = `2026-01-31`, so it knows to insert Q4 2026

#### 3. `modal-app/agent/schema.py` -- Detect "needs new column" state

Update `analyze_excel_file_full` to also return:
- `leftmost_date`: The value in B1 (the most recent period date currently in the file)
- `leftmost_period`: The value in B2 (e.g., "Q3 2026")
- `data_rows`: List of row numbers where column B has data (indicating which rows are active financial line items)

This gives the agent clear signals about whether a new column insertion is needed.

### Files Modified

| File | Changes |
|---|---|
| `modal-app/agent/updater.py` | Add `insert_new_period_column()` method that inserts column B, sets headers, and returns rows needing data |
| `modal-app/agent/orchestrator.py` | Add `insert_new_period_column` tool definition and handler, update system prompt workflow to check for new column insertion before filling cells |
| `modal-app/agent/schema.py` | Add `leftmost_date`, `leftmost_period`, and `data_rows` to the full analysis output |

### Edge Cases Handled

- **File already has the current period**: Agent sees B1 matches report_date, skips insertion, just fills empty cells in column B
- **Multiple sheets**: Each sheet gets its own column insertion (most files have only one sheet)
- **Rows without data in adjacent columns**: These are spacer/separator rows and will not get data in the new column
- **Annual vs quarterly files**: The date and period headers differ (annual uses full year dates, quarterly uses quarter labels) -- the agent determines the correct values based on the file type and report_date

