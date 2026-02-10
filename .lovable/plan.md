

## Backfill Dashboard: Fetch Missing Earnings and Trigger Processing

### Overview

Build a protected dashboard page where you can:
1. Fetch historical earnings from EODHD for **Jan 11 - Feb 9, 2026** (the gap period)
2. See all backfill tickers in a table with their processing status
3. Click a button to trigger each ticker one at a time via the existing Modal pipeline

### Step 1: Create a Backfill Edge Function

**File**: `supabase/functions/backfill-earnings/index.ts`

A one-time-use edge function that:
- Accepts `from_date` and `to_date` parameters (defaulting to `2026-01-11` and `2026-02-09`)
- Calls the EODHD API with that date range
- Filters to US tickers, matches against the `companies` table
- Upserts results into `earnings_calendar` (same logic as the daily cron)
- Returns a summary of how many records were inserted

Also add to `supabase/config.toml`:
```toml
[functions.backfill-earnings]
verify_jwt = false
```

### Step 2: Create a Backfill Trigger Edge Function

**File**: `supabase/functions/backfill-trigger-single/index.ts`

A simple edge function that:
- Accepts a single `{ ticker, report_date, fiscal_period_end, timing }` payload
- Creates an `excel_processing_runs` record (if not already exists)
- Calls the Modal webhook with just that one ticker
- Returns success/failure

Also add to `supabase/config.toml`:
```toml
[functions.backfill-trigger-single]
verify_jwt = false
```

### Step 3: Create the Backfill Dashboard Page

**File**: `src/pages/Backfill.tsx`

A protected page with:

**Section 1 -- Fetch Earnings**
- Date range inputs (pre-filled with **Jan 11** and **Feb 9, 2026**)
- "Fetch Earnings" button that calls the `backfill-earnings` edge function
- Shows result count after fetching

**Section 2 -- Ticker Table**
- Queries `earnings_calendar` joined with `excel_processing_runs` for the date range
- Displays a table with columns: Ticker, Report Date, Fiscal Period End, Status (pending/completed/failed/not started)
- Each row has a "Process" button (disabled if already completed)
- Clicking "Process" calls `backfill-trigger-single` for that ticker
- Status updates via polling or manual refresh button

**Section 3 -- Progress Summary**
- Shows counts: Total tickers, Completed, Failed, Remaining

### Step 4: Add Route

**File**: `src/App.tsx` -- Add a protected route `/backfill` pointing to the new Backfill page.

### Step 5: Add Navigation Link

**File**: `src/components/TopNavbar.tsx` -- Add a "Backfill" nav link.

---

### Technical Details

**Database**: No schema changes needed. Uses existing `earnings_calendar` and `excel_processing_runs` tables.

**Edge Functions**:
- `backfill-earnings`: Uses `EODHD_API_TOKEN` and `SUPABASE_SERVICE_ROLE_KEY` (already configured)
- `backfill-trigger-single`: Uses `MODAL_WEBHOOK_SECRET`, `MODAL_WEBHOOK_URL`, and `EXTERNAL_SUPABASE_URL` (already configured)

**Frontend**:
- Uses `@tanstack/react-query` for data fetching
- Uses existing shadcn/ui table, button, input, and badge components
- Polling interval of 10 seconds for status refresh while processing

**Flow**:
```text
[Fetch Earnings Button] --> backfill-earnings edge fn --> EODHD API --> earnings_calendar table
                                                                              |
[Ticker Table loads from DB] <------------------------------------------------+

[Process Button per ticker] --> backfill-trigger-single edge fn --> Modal webhook --> process_ticker
                                                                              |
[Status column updates via polling] <--- excel_processing_runs table <--------+
```

### File Summary

| File | Action |
|---|---|
| `supabase/functions/backfill-earnings/index.ts` | Create -- fetch historical EODHD data for Jan 11 - Feb 9 |
| `supabase/functions/backfill-trigger-single/index.ts` | Create -- trigger one ticker via Modal |
| `supabase/config.toml` | Update -- add both new functions |
| `src/pages/Backfill.tsx` | Create -- dashboard UI with pre-filled dates Jan 11 - Feb 9 |
| `src/App.tsx` | Update -- add /backfill route |
| `src/components/TopNavbar.tsx` | Update -- add nav link |

