

## Fix Two Critical Bugs in the Pipeline

### Bug 1: Python Indentation Error in Agent Module Files

**The problem:** All 5 files in `modal-app/agent/` have an extra leading space on every single line. Python is whitespace-sensitive, so this will cause an `IndentationError` the moment Modal tries to import and run the agent code.

**Affected files:**
- `modal-app/agent/__init__.py`
- `modal-app/agent/orchestrator.py`
- `modal-app/agent/browser.py`
- `modal-app/agent/schema.py`
- `modal-app/agent/storage.py`
- `modal-app/agent/updater.py`

Note: `modal-app/app.py` does NOT have this issue -- it was already fixed previously.

**The fix:** Remove the single leading space from every line in all 6 files. No logic changes, purely whitespace correction.

---

### Bug 2: `before_after_market` Timing Mismatch

**The problem:** The `trigger-excel-agent` edge function queries the `earnings_calendar` table using `"Before Market"` and `"After Market"` (with spaces), but the EODHD API stores them as `"BeforeMarket"` and `"AfterMarket"` (no spaces). This means the query always returns zero tickers, so the pipeline never runs.

Current values in the database:
- `BeforeMarket`
- `AfterMarket`
- `null` (some records have no timing)

**The fix:** In `supabase/functions/trigger-excel-agent/index.ts`, change line 48 from:

```text
const marketTiming = timing === 'premarket' ? 'Before Market' : 'After Market';
```

to:

```text
const marketTiming = timing === 'premarket' ? 'BeforeMarket' : 'AfterMarket';
```

Additionally, for `afterhours` timing, we should also query for records where `before_after_market` is `null`, since some EODHD records lack this field. Those null-timing records should be treated as after-hours by default. This requires updating the query to use an `or` filter when timing is `afterhours`.

---

### Technical Details

**Files to modify (7 total):**

| File | Change |
|---|---|
| `modal-app/agent/__init__.py` | Remove leading space from every line |
| `modal-app/agent/orchestrator.py` | Remove leading space from every line |
| `modal-app/agent/browser.py` | Remove leading space from every line |
| `modal-app/agent/schema.py` | Remove leading space from every line |
| `modal-app/agent/storage.py` | Remove leading space from every line |
| `modal-app/agent/updater.py` | Remove leading space from every line |
| `supabase/functions/trigger-excel-agent/index.ts` | Fix timing values and add null handling |

**Risk:** Low. The Python files are pure whitespace fixes with no logic changes. The edge function change is a two-value string correction plus a small query enhancement.

**After these fixes:** The pipeline will correctly match tickers from the earnings calendar and the agent code will run without Python syntax errors on Modal.

