

## Deduplicate Tickers in Backfill Dashboard

### Problem
The EODHD API returns multiple earnings entries per ticker across the date range (different report dates). The `earnings_calendar` table correctly stores all of them, but for backfill processing, each ticker only needs to be triggered once — using its **latest** report date in the range.

### Solution
Deduplicate in the frontend (`Backfill.tsx`) so the ticker table shows one row per ticker, using the most recent `report_date` for that ticker. The database data stays untouched.

### Changes

**File**: `src/pages/Backfill.tsx`

Add a deduplication step in the `tableRows` memo that:
1. Groups all earnings rows by `ticker`
2. Picks the row with the **latest** `report_date` for each ticker
3. Joins with the processing runs as before

This reduces the 1000 rows to ~unique tickers only.

```
// Inside the tableRows useMemo:
// 1. Deduplicate earnings by ticker, keeping the latest report_date
const dedupedEarnings = new Map<string, EarningsRow>();
for (const e of earnings) {
  const existing = dedupedEarnings.get(e.ticker);
  if (!existing || e.report_date > existing.report_date) {
    dedupedEarnings.set(e.ticker, e);
  }
}

// 2. Map over deduped entries, joining with runs
return Array.from(dedupedEarnings.values()).map(e => {
  const run = runsMap.get(`${e.ticker}_${e.report_date}`);
  return {
    ...e,
    status: run?.status || 'not started',
    error_message: run?.error_message || null,
    timing: e.before_after_market === 'BeforeMarket' ? 'premarket' : 'afterhours',
  };
});
```

The summary counts and table will then reflect unique tickers only.

### Technical Details

| File | Change |
|---|---|
| `src/pages/Backfill.tsx` | Update `tableRows` useMemo to deduplicate by ticker, keeping latest report_date |

No edge function or database changes needed. The deduplication happens purely in the UI layer before display and before triggering processing.

