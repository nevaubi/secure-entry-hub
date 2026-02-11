

## Integrate Firecrawl Summaries into News Pipeline

### What changes

Modify the existing `fetch-finviz-news` edge function to also scrape and summarize articles using Firecrawl's v2 API, all within the same cron run. No separate function needed.

### Flow after changes

```text
CRON triggers fetch-finviz-news
  |
  v
1. Fetch CSV from all 4 Finviz endpoints (same as today)
2. Upsert articles into each table (same as today)
3. Trim each table to 300 rows (was 200)
4. For each table, find up to 25 articles where summary IS NULL
5. Scrape those articles via Firecrawl v2 (3 in parallel)
6. Store the summary back in the database
```

### Specific changes

**1. Store `FIRECRAWL_API_KEY` as a secret**
Securely store the Firecrawl API key so the edge function can access it.

**2. Database migration -- add `summary` column**
Add a nullable `summary` text column to all 4 rolling news tables:
- `rolling_market_news`
- `rolling_stock_news`
- `rolling_etf_news`
- `rolling_crypto_news`

**3. Update `fetch-finviz-news/index.ts`**

After the existing upsert and trim logic, add a new phase:

- Query each table for up to 25 rows where `summary IS NULL`, ordered by `published_at DESC` (newest first)
- Process them in batches of 3 (parallel), calling Firecrawl v2:
  ```
  POST https://api.firecrawl.dev/v2/scrape
  {
    "url": "<article_url>",
    "onlyMainContent": true,
    "maxAge": 172800000,
    "formats": ["summary"]
  }
  ```
- Extract `data.summary` from each response and update the corresponding row in the database
- Continue until all 25 are processed or the batch is done

**4. Update rolling window from 200 to 300**

Change `MAX_ROWS` constant from 200 to 300.

### Technical details

| Item | Detail |
|---|---|
| New secret | `FIRECRAWL_API_KEY` |
| Migration | `ALTER TABLE ... ADD COLUMN summary text;` on all 4 tables |
| Edge function | Modified `fetch-finviz-news/index.ts` |
| Parallelism | `Promise.all` on chunks of 3 URLs |
| Per-table limit | 25 unsummarized articles per cron run |
| Error handling | If a single scrape fails, log the error and skip that article (don't block others) |

### What stays the same
- Same edge function, same cron schedule (3x weekdays)
- Same CSV parsing and upsert logic
- Same RLS policies (read-only for authenticated users)
- No new frontend changes in this step

