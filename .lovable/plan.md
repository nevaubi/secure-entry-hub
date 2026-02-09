

## Overhaul: Persistent Browser, Robust Login, Gemini Vision Extraction, and Agent Scratchpad

### Problems Addressed

1. Login fails due to wrong selectors (e.g., `button[type="submit"]` doesn't exist on StockAnalysis)
2. Browser session lost between tool calls (new instance each time)
3. Wrong URL patterns for financial pages (income statement uses `/financials/`, not `/financials/income-statement/`)
4. No vision-based data extraction (JS table scraping is brittle)
5. No scratchpad for the agent to track findings
6. Poor visibility into what the agent is doing

### Architecture

```text
Agent Loop (Claude Opus)
  |
  |-- browse_stockanalysis  -->  Navigate to correct URL, take full-page screenshot
  |
  |-- extract_page_with_vision  -->  Send screenshot to Gemini 3 Flash (via your GEMINI_API_KEY)
  |                                   Returns structured markdown table
  |
  |-- web_search (Perplexity)  -->  Cross-reference values
  |
  |-- note_finding  -->  Write to scratchpad (data_gathered, empty_cells, validation, etc.)
  |
  |-- analyze_excel  -->  Read Excel structure
  |-- update_excel_cell  -->  Write verified values
  |-- save_all_files  -->  Upload back to storage
```

### What Changes

#### 1. `modal-app/agent/browser.py` -- Fix login, correct URLs, add screenshot

**Login fix** (using exact selectors you provided):
- Navigate to `https://stockanalysis.com/login/`
- Fill `input#email` (by id)
- Fill `input#password` (by id)
- Click button using `page.get_by_role("button", name="Log In")` since the button has no `type="submit"`
- Wait for URL to change away from `/login/`
- Add retry (up to 2 attempts) and save screenshot to `/tmp/login_debug.png` on failure

**URL builder fix** (matching exact URLs you provided):
```python
def _build_url(self, ticker, statement_type, period, data_type):
    base = f"https://stockanalysis.com/stocks/{ticker.lower()}/financials"
    
    # Income statement has NO extra path segment
    path_map = {
        "income": "",
        "balance": "/balance-sheet",
        "cashflow": "/cash-flow-statement",
    }
    path = path_map[statement_type]
    
    params = []
    if period == "quarterly":
        params.append("p=quarterly")
    if data_type == "as-reported":
        params.append("type=as-reported")
    
    query = "?" + "&".join(params) if params else ""
    return f"{base}{path}/{query}"
```

**New method**: `screenshot_full_page()` -- returns screenshot bytes and saves to `/tmp/` for debugging.

**Remove**: The JavaScript table extraction logic (replaced by Gemini vision).

**Update `browse_stockanalysis` tool parameters**:
- `statement_type`: enum `["income", "balance", "cashflow"]`
- `period`: enum `["annual", "quarterly"]`
- `data_type`: enum `["standardized", "as-reported"]`

#### 2. `modal-app/agent/orchestrator.py` -- Persistent browser, vision tool, scratchpad, logging

**Persistent browser in AgentContext**:
- Create `StockAnalysisBrowser` once in `__init__`, call `__enter__()` to start Playwright
- Reuse across all `browse_stockanalysis` calls (login persists)
- Close browser in `close_all()`

**New tool: `note_finding`** (scratchpad):
```python
{
    "name": "note_finding",
    "description": "Record a finding or intermediate result to your scratchpad.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["data_gathered", "empty_cells", "validation", "decision", "error"]
            },
            "content": {"type": "string"}
        },
        "required": ["category", "content"]
    }
}
```
- Stored in `context.notes: list[dict]`
- Printed to console as they are recorded

**New tool: `extract_page_with_vision`**:
- Takes the latest screenshot bytes from the browser
- Calls Google Gemini API **directly** using your `GEMINI_API_KEY` (from a Modal secret called `gemini-secret`)
- Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent`
- Sends the screenshot as base64 image with an extraction instruction
- Returns the markdown table result

**Updated `browse_stockanalysis` handler**:
- Uses persistent `context.browser` instead of creating a new instance
- Logs in once on first call, session persists for subsequent calls
- Takes full-page screenshot after navigating
- Returns confirmation with URL visited (no JS table scraping)

**Better logging**:
- Print agent text blocks (reasoning between tool calls)
- Print first 300 chars of each tool result
- Print elapsed time per iteration
- Print all scratchpad notes at the end

**Updated system prompt**: Instructions for new tools and workflow.

#### 3. `modal-app/app.py` -- Add gemini secret

Add `modal.Secret.from_name("gemini-secret")` to the secrets list. This secret should contain `GEMINI_API_KEY`.

### Secrets Setup

You need to create one new Modal secret:

| Secret Name | Variable | Value |
|---|---|---|
| `gemini-secret` | `GEMINI_API_KEY` | Your Google Gemini API key |

Create it in the Modal dashboard under Secrets.

### Files Modified

| File | Changes |
|---|---|
| `modal-app/agent/browser.py` | Fix login with exact selectors (id-based), fix URL builder, add `screenshot_full_page()`, remove JS table extraction, add retry and debug screenshots |
| `modal-app/agent/orchestrator.py` | Persist browser in AgentContext, add `note_finding` tool + scratchpad, add `extract_page_with_vision` tool (Gemini direct API), update `browse_stockanalysis` handler, update system prompt, add logging |
| `modal-app/app.py` | Add `gemini-secret` to secrets list |

### After Deploying

1. Create a Modal secret called `gemini-secret` with `GEMINI_API_KEY=<your key>`
2. `modal deploy app.py`
3. `modal run app.py::test_single_ticker --ticker PLTR`

You will now see:
- Login success/failure with debug screenshots saved to `/tmp/`
- Agent reasoning printed between tool calls
- Scratchpad notes as the agent records findings
- Vision extraction results from Gemini showing actual table data
- A final summary of all notes and results

