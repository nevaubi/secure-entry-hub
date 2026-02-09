

## Four Changes to Gemini Vision, Date Logic, Model, and Iterations

### 1. Structured Gemini Screenshot Prompt

**File**: `modal-app/agent/orchestrator.py` (lines 362-409)

Currently the agent passes a freeform `instruction` string to Gemini. Replace this with a hardcoded, structured prompt that ignores whatever the agent sends and instead enforces:

- Extract ONLY the first 4 columns (leftmost) from the financial table in the screenshot
- Output as a precise markdown table with exact headers, row labels, and numeric values
- Emphasize absolute accuracy in all values, labels, and column headers (dates/periods)

The `instruction` parameter from the agent will be ignored — the prompt is fixed at the infrastructure level:

```python
vision_prompt = f"""You are a financial data extraction specialist. Analyze this screenshot of a financial statement table.

TASK: Extract ONLY the first 4 columns from the LEFT side of the table. Start from the leftmost column (row labels) and include the next 3 data columns to the right.

OUTPUT FORMAT: A markdown table with:
- Row 1: Column headers exactly as shown (dates or period labels)
- All subsequent rows: Row labels in column 1, numeric values in columns 2-4
- Reproduce ALL numeric values EXACTLY as displayed (do not round, convert, or abbreviate)
- Reproduce ALL row labels EXACTLY as displayed
- Reproduce ALL column headers/dates EXACTLY as displayed
- If a cell is empty or shows a dash, use an empty cell in the markdown

CRITICAL ACCURACY RULES:
- Do NOT guess or infer any values — only extract what is visually present
- Do NOT skip any rows — include every row visible in the table
- Preserve the exact formatting of numbers (commas, parentheses for negatives, etc.)
- The column headers typically contain dates (e.g., "12/31/2025") or period labels (e.g., "Q4 2025") — reproduce them exactly

Return ONLY the markdown table, nothing else."""
```

### 2. Use Gemini Markdown Table for Date and Period Headers

**File**: `modal-app/agent/orchestrator.py`

Instead of forcing `fiscal_period_end` from the backend, let the agent determine the correct date and period from the Gemini-extracted markdown table. Changes:

- **Remove the `fiscal_period_end` override** in the `insert_new_period_column` handler (lines 454-455). Revert to using whatever the agent passes — since the agent will now get accurate dates from the Gemini table.
- **Update system prompt** (line 240): Tell the agent to use the date from the leftmost data column of the Gemini markdown table as the `date_header`, and derive the `period_header` from it (Q4 YYYY for annual files, specific quarter for quarterly).
- **Update initial user message** (line 635): Remove the instruction to use `fiscal_period_end`. Instead instruct: "Use the date from the first data column of the Gemini-extracted markdown table as your date_header. For annual files, always use 'Q4 YYYY' as the period_header."
- Keep `fiscal_period_end` and `report_date` available in the prompt for general context but explicitly state they are NOT to be used for the column header — the Gemini table is the source of truth.

### 3. Upgrade Gemini Model

**File**: `modal-app/agent/orchestrator.py` (line 377)

Change the API endpoint from:
```
gemini-2.5-flash:generateContent
```
to:
```
gemini-3-flash-preview:generateContent
```

### 4. Reduce Iterations from 15 to 5

**File**: `modal-app/agent/orchestrator.py` (line 640)

Change:
```python
max_file_iterations = 15 if needs_new_column else 10
```
to:
```python
max_file_iterations = 5
```

Also update the system prompt references:
- Line 254: Change "15 max" to "5 max"
- Add stronger urgency language: the agent has only 5 iterations total, so it must browse, extract, and batch-write all cells within that budget. The Gemini markdown table is the primary data source; web_search is only for validation or filling gaps.

### Files Modified

| File | Changes |
|---|---|
| `modal-app/agent/orchestrator.py` | Fixed Gemini prompt, removed fiscal_period_end override for date header, updated model to gemini-3-flash-preview, reduced max iterations to 5, updated prompt language |

### Summary of Data Flow After Changes

```text
1. Agent calls browse_stockanalysis -> screenshot captured
2. Agent calls extract_page_with_vision -> hardcoded structured prompt sent to Gemini 3 Flash
3. Gemini returns markdown table of first 4 columns with exact dates/values
4. Agent reads the leftmost data column date from the markdown table
5. Agent calls insert_new_period_column with that date (annual -> "Q4 YYYY", quarterly -> specific quarter)
6. Agent matches row labels from markdown table to row_map, calls update_excel_cell in batch
7. Agent uses web_search only if needed for validation or missing values
8. All done within 5 iterations max
```

