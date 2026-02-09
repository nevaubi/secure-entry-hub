
## Fix: Use `fiscal_period_end` Instead of `report_date` for Column Header

### The Problem

The agent uses `report_date` (the date the company reports earnings) as the column header date. But the correct date is `fiscal_period_end` (the date the fiscal period actually ends). For example, a company might report on 2026-02-05 but the fiscal period ended on 2025-12-31. The column header should say "2025-12-31", not "2026-02-05".

This affects the entire pipeline -- the `fiscal_period_end` is stored in the database but never passed through to the agent.

### Changes Required

The fix touches 3 files across the full data flow:

#### 1. `supabase/functions/trigger-excel-agent/index.ts`

- Add `fiscal_period_end` to the database query `select` clause (line 59)
- Add `fiscal_period_end` to the `EarningsRecord` interface (line 6)
- Add `fiscal_period_end` to the `TickerPayload` interface (line 12)
- Include `fiscal_period_end` in the payload sent to Modal (line 87-91)

#### 2. `modal-app/app.py`

- Add `fiscal_period_end: str` parameter to `process_ticker` (line 48)
- Pass it through to `run_agent` (line 72)
- Add it to the webhook payload extraction (line 154-156)

#### 3. `modal-app/agent/orchestrator.py`

- Add `fiscal_period_end: str` parameter to `run_agent` (line 525)
- Use `fiscal_period_end` instead of `report_date` for the new-column date comparison (line 594)
- Pass `fiscal_period_end` to `build_file_system_prompt` and use it as the `date_header` reference (lines 200-248)
- Update the initial user message to reference `fiscal_period_end` as the target date (line 632)
- Keep `report_date` available for context but make it clear that `fiscal_period_end` is the column date

### Data Flow After Fix

```text
DB (earnings_calendar)
  -> trigger-excel-agent (query fiscal_period_end, send to Modal)
    -> app.py/process_ticker (accept fiscal_period_end, pass to orchestrator)
      -> orchestrator.py/run_agent (use fiscal_period_end for column date comparison + header)
        -> system prompt tells agent: "date_header = fiscal_period_end"
```

### Technical Details

**trigger-excel-agent/index.ts** changes:

```typescript
// Interface updates
interface EarningsRecord {
  ticker: string;
  report_date: string;
  fiscal_period_end: string | null;
  before_after_market: string | null;
}

interface TickerPayload {
  ticker: string;
  report_date: string;
  fiscal_period_end: string | null;
  timing: 'premarket' | 'afterhours';
}

// Query: add fiscal_period_end to select
select=ticker,report_date,fiscal_period_end,before_after_market

// Payload: include fiscal_period_end
const tickerPayloads = earnings.map(e => ({
  ticker: e.ticker,
  report_date: e.report_date,
  fiscal_period_end: e.fiscal_period_end,
  timing: timing,
}));
```

**app.py** changes:

```python
def process_ticker(ticker, report_date, timing, fiscal_period_end=None, callback_url=None):
    result = run_agent(ticker, report_date, timing, fiscal_period_end=fiscal_period_end)

# In webhook:
process_ticker.spawn(
    ticker=t["ticker"],
    report_date=t["report_date"],
    timing=t["timing"],
    fiscal_period_end=t.get("fiscal_period_end"),
    callback_url=callback_url,
)
```

**orchestrator.py** changes:

- `run_agent` signature: add `fiscal_period_end: str | None = None`
- Column comparison: use `fiscal_period_end or report_date` (fallback if null)
- System prompt: reference `fiscal_period_end` as the date for the new column header, not `report_date`
- All prompt text that says "report_date" for column headers changed to "fiscal_period_end"

### Files Modified

| File | Changes |
|---|---|
| `supabase/functions/trigger-excel-agent/index.ts` | Query and pass `fiscal_period_end` to Modal |
| `modal-app/app.py` | Accept and forward `fiscal_period_end` parameter |
| `modal-app/agent/orchestrator.py` | Use `fiscal_period_end` for column date comparison and header instructions |
