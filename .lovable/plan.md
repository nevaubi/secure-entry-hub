

## Click "Raw" Dropdown Before Screenshot on StockAnalysis

### Problem
StockAnalysis.com may display values in abbreviated form (millions, billions) by default. We need to ensure "Raw" is selected before taking the screenshot so Gemini vision extracts fully written-out numbers.

### Solution
Add a `_select_raw_units` method to `StockAnalysisBrowser` and call it inside `navigate_to_financials` right before the screenshot is taken.

### Changes

**File**: `modal-app/agent/browser.py`

#### 1. Add `_select_raw_units` method (new method after `login`)

```python
def _select_raw_units(self):
    """Click the number-units dropdown and select 'Raw' to show full values."""
    try:
        # Click the dropdown button with title "Change number units"
        dropdown = self.page.locator('button[title="Change number units"]')
        dropdown.wait_for(timeout=5000)
        dropdown.click()
        time.sleep(0.5)  # Let menu open

        # Click the "Raw" option inside the dropdown menu
        raw_btn = self.page.locator('button.active:has-text("Raw"), button:has-text("Raw")')
        raw_btn.first.click()
        time.sleep(0.5)  # Let table re-render

        print("Selected 'Raw' number units")
    except Exception as e:
        print(f"Warning: Could not select Raw units: {e}")
```

#### 2. Call it in `navigate_to_financials` (line 159, after the table wait and sleep)

Insert the call right before the screenshot lines:

```python
time.sleep(1)  # Let any lazy-loaded content settle

# Select "Raw" number format before taking screenshot
self._select_raw_units()

# Take full-page screenshot
screenshot_bytes = self.screenshot_full_page()
```

### Why This Is Safe

- The dropdown and "Raw" button are identified by stable attributes (`title="Change number units"` and button text "Raw")
- Wrapped in try/except so if the dropdown is not found (e.g., already set to Raw, or UI changes), the workflow continues without crashing
- A short sleep after each click ensures the UI updates before the screenshot

### Files Modified

| File | Changes |
|---|---|
| `modal-app/agent/browser.py` | Add `_select_raw_units()` method; call it in `navigate_to_financials` before screenshot |

