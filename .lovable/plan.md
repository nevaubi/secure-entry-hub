

## Change GOOGL to GOOG in Earnings Calendar

### What's happening
- The `companies` table already has the ticker as **GOOG**
- The `earnings_calendar` table has it as **GOOGL** (from the EODHD API data)
- The dashboard displays `GOOGL` because it reads from `earnings_calendar`

### Fix
Update the `earnings_calendar` record to use `GOOG` instead of `GOOGL`:

```sql
UPDATE earnings_calendar SET ticker = 'GOOG' WHERE ticker = 'GOOGL';
```

This is a simple data update -- no schema changes or code changes needed. The dashboard will immediately show `GOOG` after the update since it reads directly from this table.

### Risk
None -- there are no foreign key constraints between `earnings_calendar` and `companies`, and no `excel_processing_runs` records exist for either `GOOGL` or `GOOG`, so nothing else to update.

