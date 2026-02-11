

## Global Context: Automated Rolling News Pipeline

### Overview
Create an automated news ingestion system that fetches articles from 4 Finviz API endpoints, stores them in 4 separate database tables, and maintains a rolling window of ~200 articles per category. Runs 3 times per weekday.

### What gets built

**1. Store the Finviz API auth token as a secret**
The auth token will be securely stored as `FINVIZ_AUTH_TOKEN` -- never hardcoded.

**2. Four new database tables**

All four tables share a similar schema. `rolling_market_news` has no `ticker` column; the other three do.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid (PK) | Auto-generated |
| `title` | text | Article headline |
| `source` | text | Publisher name |
| `published_at` | timestamptz | From the CSV `Date` field |
| `url` | text | Unique constraint -- prevents duplicates on re-fetch |
| `category` | text | e.g. "Market", "Stock", etc. |
| `ticker` | text | Comma-separated tickers (stock/etf/crypto tables only) |
| `created_at` | timestamptz | When we ingested it |

RLS: Read-only for authenticated users.

**3. One edge function: `fetch-finviz-news`**

A single function that:
- Reads the `FINVIZ_AUTH_TOKEN` secret
- Calls all 4 Finviz endpoints
- Parses each CSV response
- Upserts into the corresponding table (using `url` as the unique key so re-runs don't create duplicates)
- Trims each table to the newest 200 rows, deleting older ones

**4. Three cron jobs (weekdays only)**

All three call the same edge function. Scheduled at:

| Time (Chicago) | UTC (CST / winter) | Purpose |
|---|---|---|
| 5:00 AM | 11:00 UTC | Pre-market news sweep |
| 11:00 AM | 17:00 UTC | Midday refresh |
| 4:00 PM | 22:00 UTC | End-of-day refresh |

Cron expressions (weekdays only):
- `0 11 * * 1-5` (5 AM CT)
- `0 17 * * 1-5` (11 AM CT)
- `0 22 * * 1-5` (4 PM CT)

### Data flow

```text
CRON (3x weekdays: 5am / 11am / 4pm CT)
  |
  v
fetch-finviz-news (edge function)
  |
  +---> GET /news_export.ashx?c=1  --> parse CSV --> upsert rolling_market_news (keep 200)
  +---> GET /news_export.ashx?v=3  --> parse CSV --> upsert rolling_stock_news  (keep 200)
  +---> GET /news_export.ashx?v=4  --> parse CSV --> upsert rolling_etf_news    (keep 200)
  +---> GET /news_export.ashx?v=5  --> parse CSV --> upsert rolling_crypto_news (keep 200)
```

### Technical Details

| Item | Detail |
|---|---|
| New secret | `FINVIZ_AUTH_TOKEN` |
| New edge function | `supabase/functions/fetch-finviz-news/index.ts` |
| New config entry | `[functions.fetch-finviz-news]` with `verify_jwt = false` |
| Database migration | 4 new tables with unique constraint on `url`, RLS policies |
| Cron jobs | 3 `pg_cron` schedules via SQL insert (not migration) |

### CSV parsing
The Finviz CSVs use standard quoted-CSV format. The edge function will include a lightweight inline CSV parser to handle quoted fields containing commas.

### Rolling window
After each upsert, the function deletes all rows except the 200 most recent (by `published_at`) in each table. Since upserts use `url` uniqueness, running 3x/day won't create duplicates -- it will just refresh the window and catch new articles.

