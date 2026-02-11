

## Include Feb 10, 2026 Earnings in Backfill Dashboard

### Change
Update the default `toDate` state in `src/pages/Backfill.tsx` from `'2026-02-09'` to `'2026-02-10'`.

This is a one-line change on line 43:

```
// Before
const [toDate, setToDate] = useState('2026-02-09');

// After
const [toDate, setToDate] = useState('2026-02-10');
```

### Result
74 new tickers from Feb 10 (e.g., CSCO, DDOG, GILD, NET, SPGI, CMG, ENPH, etc.) will appear in the backfill table alongside the existing entries.

### Technical Details

| File | Change |
|---|---|
| `src/pages/Backfill.tsx` line 43 | Change default `toDate` from `'2026-02-09'` to `'2026-02-10'` |

No database or schema changes needed -- the data is already in the `earnings_calendar` table.
