

## Fetch Feb 10 Earnings from EODHD API

### Change
Update the `fetch-earnings-calendar` edge function to accept an optional `date` query parameter. When provided, it fetches earnings for that specific date instead of today. Then call it with `date=2026-02-10` to backfill the missing tickers (including HOOD).

### What will happen
1. The function calls the EODHD API for `2026-02-10`
2. Filters to US tickers, matches against the `companies` table
3. Upserts into `earnings_calendar` (existing records like CSCO won't be duplicated thanks to the unique constraint)
4. Any missing tickers like HOOD will be added

### Technical Details

| File | Change |
|---|---|
| `supabase/functions/fetch-earnings-calendar/index.ts` | Accept optional `date` query param; fall back to Central Time date if not provided |

```typescript
// Add after line 48, replace the currentDate logic:
const url = new URL(req.url);
const dateParam = url.searchParams.get('date');
const currentDate = dateParam || getCentralTimeDate();
```

After deploying, the function will be called with `?date=2026-02-10` to fetch and insert the missing earnings data. The dashboard will then show all tickers that reported on Feb 10, including HOOD.
