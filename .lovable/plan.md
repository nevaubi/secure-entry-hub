

## Add February 11 Earnings to Backfill Page

### Step 1: Fetch Feb 11 earnings from EODHD API
Invoke the existing `fetch-earnings-calendar` edge function with `?date=2026-02-11` to pull earnings data for that date and upsert into `earnings_calendar`.

### Step 2: Extend the default date range
Update `src/pages/Backfill.tsx` -- change the default `toDate` state from `'2026-02-10'` to `'2026-02-11'` so the table automatically includes Feb 11 tickers.

That is the only code change needed. The existing pagination, deduplication, and table rendering will handle the new rows automatically.

### Technical Details

**File:** `src/pages/Backfill.tsx`
- Line 43: Change `useState('2026-02-10')` to `useState('2026-02-11')`

**Runtime action:**
- Call `fetch-earnings-calendar?date=2026-02-11` to populate the data before the UI renders it

No new tables, migrations, or edge functions required.
