

## Plan: Improve Standardized Agent — 4 Changes

### Overview
Four targeted improvements to `modal-app-standardized/`: slim Excel context to 5 columns, increase max tokens + change model, add batch cell update tool, and harden login.

---

### 1. Slim Excel to 5 Leftmost Columns (`schema.py`)

**Current:** `analyze_excel_file_full` reads up to 30 columns, sending all data to Claude.

**Change:** Add a `max_data_cols=5` parameter. In the column loops (lines 87, 102), cap iteration to `min(max_col + 1, 1 + max_data_cols + 1)` — column A (labels) + 5 data columns (B–F). Headers list similarly capped. This gives Claude the most recent 5 periods for temporal context without wasting tokens on old data.

- `format_full_schema_for_llm` needs no changes — it renders whatever `analyze_excel_file_full` returns.
- The `empty_cells` list will also be scoped to these 5 columns, which is correct since the agent only fills column B.

### 2. Model + Max Tokens (`orchestrator.py`)

**Change on line 544:**
- Model: `"claude-sonnet-4-5"` → `"claude-sonnet-4-6"`
- Max tokens: `8192 if iteration == 1 else 6096` → `15000` for all iterations

### 3. Batch Cell Update Tool (`orchestrator.py` + `updater.py`)

**`updater.py`** already has `update_cells_batch` (line 48). No changes needed there.

**`orchestrator.py` changes:**
- Add a new tool definition to `TOOLS` list:
  ```python
  {
      "name": "update_excel_cells_batch",
      "description": "Update multiple cells at once. More efficient than calling update_excel_cell repeatedly.",
      "input_schema": {
          "type": "object",
          "properties": {
              "sheet_name": {"type": "string"},
              "updates": {
                  "type": "array",
                  "items": {
                      "type": "object",
                      "properties": {
                          "cell_ref": {"type": "string"},
                          "value": {"type": ["string", "number"]}
                      },
                      "required": ["cell_ref", "value"]
                  }
              }
          },
          "required": ["sheet_name", "updates"]
      }
  }
  ```
- Add handler in `handle_tool_call` for `"update_excel_cells_batch"` that calls `updater.update_cells_batch()` with the sheet_name injected into each update dict, tracks `cells_written` and `files_modified`.
- Update system prompt (line 208) to mention `update_excel_cells_batch` as the preferred method.

### 4. Robust Login (`browser.py`)

**Changes to `login()` method (lines 41–79):**
- Increase `max_attempts` from 2 → 3
- Add exponential backoff between attempts: `time.sleep(2 ** attempt)` (2s, 4s, 8s)
- Replace `wait_for_load_state("networkidle")` with explicit element waits — wait for a post-login element (e.g., user menu/avatar) using `page.wait_for_selector` with a known logged-in indicator, falling back to URL check
- Add CAPTCHA detection: after clicking login, check for common CAPTCHA selectors (e.g., `iframe[src*="captcha"]`, `.g-recaptcha`). If found, log clearly and fail fast instead of burning retries
- Add `verify_logged_in()` helper that checks URL + looks for a logged-in indicator element, called at the start of `navigate_to_financials` to re-verify session is still valid (not just trusting `self.logged_in` flag)

**Safety:** All changes are additive — existing selectors (`input#email`, `input#password`, button role) are preserved. The backoff and verification are layered on top.

---

### Deployment
All files are in `modal-app-standardized/`. After editing locally, deploy with:
```bash
modal deploy app.py
```

