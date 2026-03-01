

## Plan: Bulk Backfill for ~600 Tickers

### Overview
Add a bulk trigger feature to the Backfill2 page that reads the uploaded Excel file's tickers and fires them to the standardized agent in batches, with progress tracking.

### Approach
Create a new edge function `bulk-trigger-standardized` that accepts an array of `{ticker, report_date, timing}` objects and creates DB records + triggers Modal for each. The UI gets a file upload + "Run All" button.

### Changes

| Action | File | Detail |
|---|---|---|
| Create | `supabase/functions/bulk-trigger-standardized/index.ts` | Accepts `{tickers: [{ticker, report_date, timing},...]}`, creates `standardized_processing_runs` records, calls Modal webhook with all tickers in one batch. Processes in chunks of 10 to avoid timeouts. |
| Modify | `src/pages/Backfill2.tsx` | Add a "Bulk Upload" section: file input accepting `.xlsx`, parse client-side with a lightweight library or just let the edge function handle it. Display parsed tickers in a table before triggering. Add "Run All" button that calls the bulk edge function. Show batch progress. |
| Modify | `supabase/config.toml` | Add `[functions.bulk-trigger-standardized]` with `verify_jwt = false` |

### Technical Details

**Edge function `bulk-trigger-standardized`:**
- Accepts `{ tickers: [{ticker, report_date, timing, fiscal_period_end?}, ...] }`
- Inserts all rows into `standardized_processing_runs` in a single batch POST
- Calls the Modal webhook once with all tickers (Modal already handles `.spawn()` per ticker)
- Returns count of tickers queued

**UI additions to Backfill2.tsx:**
- New card: "Bulk Processing" with a textarea for pasting tickers (one per line) OR a simple comma-separated input
- A "report_date" and "timing" selector shared across all tickers
- "Queue All" button that sends the full list to `bulk-trigger-standardized`
- The existing runs table already auto-refreshes every 10s, so all 600 runs will appear progressively

**Why not file upload?** Parsing Excel client-side requires adding a library like `xlsx`/`sheetjs`. Simpler to let the user paste tickers from the spreadsheet. The tickers are just a flat list.

**Rate limiting consideration:** Modal's `.spawn()` handles concurrent execution. The webhook receives all tickers at once and spawns them. Modal will queue/throttle as needed based on the app's concurrency settings.

### Alternative: Chunked approach
If 600 tickers in one Modal webhook call is too many, we can chunk into batches of 20 and call the edge function multiple times with a delay between batches. The UI would show "Batch 1/30 queued..." progress.

