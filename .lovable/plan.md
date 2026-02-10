

## Enforce Hardcoded Gemini Prompt, Update Model, and Emphasize StockAnalysis Data

### Changes

**File**: `modal-app/agent/orchestrator.py`

#### 1. Remove `instruction` parameter from `extract_page_with_vision` tool (lines 76-88)

Replace the tool schema to have no parameters, making it clear the prompt is fixed:

```python
{
    "name": "extract_page_with_vision",
    "description": "Extract financial data from the latest screenshot using a fixed structured prompt. Returns a markdown table of the first 4 columns. No parameters needed -- just call it after browse_stockanalysis.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": []
    }
}
```

#### 2. Remove unused `instruction` variable (line 363)

Delete `instruction = tool_input["instruction"]` since the parameter no longer exists.

#### 3. Update Gemini model and max tokens (line 377, line 412)

- Change model from `gemini-3-flash-preview` to `gemini-3-flash`
- Change `maxOutputTokens` from `8192` to `12000`

```python
# Line 377: URL change
f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent?key={gemini_key}"

# Line 412: Token limit
"maxOutputTokens": 12000,
```

#### 4. Update system prompt to emphasize StockAnalysis as primary source (lines 243-254)

Update the instructions around lines 243-254 to read:

```
3. Call browse_stockanalysis with the parameters above to navigate to the matching page
4. Call extract_page_with_vision (no parameters needed) -- it uses a fixed internal prompt to extract a structured markdown table
5. The Gemini markdown table almost always provides ALL the data you need. Match the extracted data to the row labels from the file/row_map
6. Use update_excel_cell to fill ALL cells in one go -- batch as many calls as possible per iteration
7. When done, respond with "FILE COMPLETE"

IMPORTANT -- FOR NEW COLUMN INSERTION:
- After inserting the column, you get a row_map with exact cell references and labels
- Browse StockAnalysis FIRST, extract data, then batch-fill all cells that correctly match the corresponding row label via the StockAnalysis data
- The StockAnalysis markdown table is almost always sufficient for ALL required values. Only use web_search if specific critical values are clearly missing after extraction.
- Do NOT call web_search by default for validation -- the Gemini-extracted StockAnalysis data is your primary and usually complete source
- Accuracy is critical: you have up to 15 iterations max, but aim to finish in fewer by trusting the StockAnalysis extraction
```

#### 5. Update initial user message to reinforce StockAnalysis primacy (line 668)

Add emphasis in the user message:

```
- The Gemini markdown table is your PRIMARY and almost always COMPLETE data source. It will typically contain ALL the values you need. Use web_search ONLY if specific critical values are clearly missing -- do not use it for routine validation.
```

### Summary

| Change | Before | After |
|---|---|---|
| Tool `instruction` param | Required string | Removed entirely |
| Gemini model | `gemini-3-flash-preview` | `gemini-3-flash` |
| Gemini maxOutputTokens | 8192 | 12000 |
| Max iterations | 15 (unchanged) | 15 (unchanged) |
| StockAnalysis emphasis | "primary source" | "primary and almost always COMPLETE source" |
| `instruction` variable (line 363) | Read from tool_input | Removed |
