

## Plan: Add report_date, timing, fiscal_period_end to Backfill2 UI and edge function

### Problem
The Modal webhook expects `report_date` and `timing` per ticker (same as the as-reported agent). The current `trigger-standardized-agent` edge function and Backfill2 UI only send `ticker`, causing `KeyError: 'report_date'`.

### Changes

**1. Update `src/pages/Backfill2.tsx`**
- Add `reportDate` state (date input, default today)
- Add `timing` state (select: "premarket" or "afterhours", default "afterhours")
- Add optional `fiscalPeriodEnd` state (date input, optional)
- Pass all fields in the `trigger-standardized-agent` invocation body: `{ ticker, report_date, timing, fiscal_period_end }`
- Show `report_date` and `timing` columns in the runs table (if the DB table has them — will check)

**2. Update `supabase/functions/trigger-standardized-agent/index.ts`**
- Accept `report_date`, `timing`, `fiscal_period_end` from the request body
- Validate `report_date` and `timing` are present
- Pass them through in the Modal webhook payload: `tickers: [{ ticker, report_date, fiscal_period_end, timing }]`
- Store `report_date` and `timing` in the `standardized_processing_runs` DB record

**3. Database migration (if needed)**
- Check if `standardized_processing_runs` has `report_date` and `timing` columns — if not, add them

### Technical details
- The edge function payload to Modal will match the existing webhook signature: `{ tickers: [{ ticker, report_date, timing, fiscal_period_end }], callback_url }`
- The UI form will have 4 fields in a row: Ticker (text), Report Date (date), Timing (select), Fiscal Period End (date, optional)
- Re-run button in the table will re-use the stored `report_date`/`timing` from the run record

