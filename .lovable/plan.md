

## Fix: Feb 10 Earnings Not Showing (Row Limit Hit)

### Problem
The query fetching earnings from the database has a **default limit of 1,000 rows**, but there are **3,273 rows** in the Jan 11 - Feb 10 date range. Since results are sorted by date ascending, rows are cut off around Jan 29 and everything after (including all Feb 10 tickers) is silently dropped.

Additionally, there are **many duplicate rows** in the `earnings_calendar` table (e.g., 351 rows for Feb 10 when only ~74 unique tickers exist). This inflates the row count and makes the 1,000-row limit hit even sooner.

### Solution (two parts)

**Part 1 -- Fix the query in `Backfill.tsx` to handle >1,000 rows**

In the earnings query (around line 52), add pagination to fetch all rows, or -- since the dashboard already deduplicates on the frontend -- simply fetch with a higher limit to ensure all data comes through.

```typescript
// In the queryFn, add explicit pagination:
const allData: EarningsRow[] = [];
let offset = 0;
const batchSize = 1000;
let hasMore = true;
while (hasMore) {
  const { data, error } = await supabase
    .from('earnings_calendar')
    .select('ticker, report_date, fiscal_period_end, before_after_market')
    .gte('report_date', fromDate)
    .lte('report_date', toDate)
    .order('report_date', { ascending: true })
    .order('ticker', { ascending: true })
    .range(offset, offset + batchSize - 1);
  if (error) throw error;
  allData.push(...(data || []));
  hasMore = (data?.length || 0) === batchSize;
  offset += batchSize;
}
return allData;
```

**Part 2 -- Clean up duplicate records (recommended)**

Run a SQL cleanup to remove the ~2,400 duplicate rows. This reduces data volume and prevents future limit issues. Duplicates share the same `ticker`, `report_date`, and `before_after_market` (all null). We keep one row per combination:

```sql
DELETE FROM earnings_calendar
WHERE id NOT IN (
  SELECT DISTINCT ON (ticker, report_date, COALESCE(before_after_market, ''))
    id FROM earnings_calendar
  ORDER BY ticker, report_date, COALESCE(before_after_market, ''), created_at ASC
);
```

### Technical Details

| File | Change |
|---|---|
| `src/pages/Backfill.tsx` | Replace single query with paginated loop using `.range()` in the earnings `queryFn` |
| Database (SQL migration) | Remove duplicate `earnings_calendar` rows, keeping the earliest `created_at` per unique combination |

### Result
After these changes, all 23 reporting dates (Jan 12 through Feb 10) will appear on the backfill dashboard, including HOOD and the other ~74 Feb 10 tickers.
