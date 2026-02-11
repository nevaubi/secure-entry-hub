
## Goal
Ensure `rolling_crypto_news` (and the other news tables) reliably receive summaries so `sync-news-external` can sync them. Do it in a way that is production-ready, resilient to partial failures (403s, timeouts), and quick to ship.

## What’s happening (based on code + logs)
### Observed behavior
- `fetch-finviz-news` successfully fetches and upserts crypto rows (logs show `Parsed 100 rows for rolling_crypto_news` and fetch results include `upserted: 100`).
- But summaries are not being written for crypto (your audit showed `with_summary = 0`), and the logs show summarization only starts for:
  - `rolling_market_news`
  - `rolling_stock_news`
- There are **no logs** showing summarization starting for `rolling_etf_news` or `rolling_crypto_news`.

### Most likely root cause
The summarization phase is coupled to the fetch phase in a single backend function invocation. Summarization is slow and can fail on many URLs (403s like NYT). As a result, the function is likely **hitting an execution-time ceiling** or otherwise ending before it reaches ETF/crypto summarization.

Even if there isn’t an explicit “timeout” log, serverless runtimes commonly terminate long-running requests without a clean error path that you can reliably log from inside the function.

### Why the crypto schema you pasted is not the blocker
That schema has `summary text not null`. If that were the schema in the environment doing the *initial upsert*, the Phase-1 upsert (which does not include `summary`) would fail. But logs show crypto upserts succeed. So the “no crypto summaries” issue is not caused by that schema definition being enforced on the writer side of Phase 1.

## Safest, most production-ready, quick fix (recommended)
### Decouple “fetch” from “summarize” into two separate backend functions
This removes the single biggest reliability risk: one long-running job doing too much.

#### A) Keep `fetch-finviz-news` focused on ingestion only
- Fetch CSV from Finviz
- Upsert rows (without summary)
- Trim to rolling window
- Return results
- **No Firecrawl calls in this function**

Result: ingestion becomes fast and consistent.

#### B) Create a new backend function: `summarize-news`
- Loops over the same 4 tables.
- For each table, selects the newest `N` rows where `summary is null`.
- Summarizes in small chunks (you already do 3 at a time; we can keep that).
- Writes the summary back.
- Captures failures but **never stops** the entire run for a few bad URLs.

Key robustness improvements in this function:
- **Per-URL timeout** using `AbortController` so a single stuck scrape doesn’t block progress.
- **Smaller per-table limits** (e.g., 10–15) so the function finishes quickly and can be run frequently.
- **Continue-on-error** at every level (already mostly present, but we’ll make it explicit and log summary stats at the end).

#### C) Schedule summarization separately (weekday, after fetch)
You already have fetch running at 5:00 / 11:00 / 16:00 Chicago time.

Add `summarize-news` schedules, e.g.:
- 5:10 AM CT weekdays
- 11:10 AM CT weekdays
- 4:10 PM CT weekdays

Optionally add a “catch-up” schedule every 30 minutes on weekdays during market hours for extra resilience. Because the summarizer is idempotent (`where summary is null`), repeated runs are safe.

## “Quickest possible patch” option (less robust, but minimal changes)
If you need a one-file hotfix:
1. Reorder summarization phase so crypto is first (crypto → etf → stock → market), so at least crypto gets processed before time runs out.
2. Reduce `SUMMARY_LIMIT` for market/stock/etf so they don’t consume the entire runtime.
3. Add an overall time budget check and stop cleanly with logs.

This is quick, but still couples fetch + summarize, so it’s less production-safe than decoupling.

## Database/schema considerations (minimal)
No schema changes are strictly required to fix the issue.

Optional (nice-to-have for production ops, not required for “quick fix”):
- Add `summary_updated_at timestamptz`
- Add `summary_error text` and/or `summary_attempts int`
This makes it easier to detect repeated failures and avoid re-trying the same blocked domains forever.

## Verification plan
1. Manually trigger `fetch-finviz-news` and confirm crypto rows appear (already true).
2. Manually trigger `summarize-news` and confirm:
   - `rolling_crypto_news` gets non-null summaries for at least a few rows.
3. Manually trigger `sync-news-external` and verify crypto now syncs > 0.
4. Watch logs for:
   - “Summarizing X articles for rolling_crypto_news”
   - Final per-table success/error counts.

## Rollout/rollback
- Deploying `summarize-news` is additive and low-risk.
- If anything goes wrong, you can disable the summarization cron(s) without affecting ingestion or syncing.

## Open questions (only if you want maximum safety)
1. Should we **exclude known-blocked domains** (e.g., `nytimes.com`) from summarization to reduce wasted retries and runtime?
2. Do you want summaries to be strictly required for syncing, or should sync fall back to syncing even when summary is null (less strict but increases coverage)?
