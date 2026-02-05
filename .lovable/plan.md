

## Earnings Calendar Cron Job - Phase 1

This plan sets up the foundational infrastructure for fetching daily earnings calendar data and storing matched companies.

---

### Overview

```text
+------------------+     +-----------------------+     +------------------+
|   pg_cron        | --> | fetch-earnings-       | --> | earnings_calendar|
|   (2x daily)     |     | calendar (edge fn)    |     | (new table)      |
+------------------+     +-----------------------+     +------------------+
                                   |
                                   v
                         +-------------------+
                         | EODHD API         |
                         | /calendar/earnings|
                         +-------------------+
```

---

### Components to Create

| Component | Description |
|-----------|-------------|
| **Database Table** | `earnings_calendar` - stores matched earnings reports |
| **Edge Function** | `fetch-earnings-calendar` - calls API, filters, matches, inserts |
| **Cron Jobs** | Two scheduled jobs for 8:15am CT and 5:30pm CT weekdays |
| **Secret** | Store EODHD API token securely |

---

### 1. New Database Table: `earnings_calendar`

This table will log each matched earnings result:

| Column | Type | Description |
|--------|------|-------------|
| `id` | uuid (PK) | Auto-generated unique ID |
| `ticker` | text | Company ticker (matches companies table) |
| `report_date` | date | Date of the earnings report |
| `fiscal_period_end` | date | End date of fiscal period being reported |
| `before_after_market` | text | "BeforeMarket" or "AfterMarket" |
| `actual_eps` | numeric | Actual EPS (nullable) |
| `estimate_eps` | numeric | Estimated EPS (nullable) |
| `difference` | numeric | Difference between actual and estimate |
| `percent_surprise` | numeric | Percentage surprise |
| `fetched_at` | timestamptz | When this record was fetched |
| `created_at` | timestamptz | Record creation timestamp |

RLS Policy: Authenticated users can read records.

---

### 2. Edge Function: `fetch-earnings-calendar`

**Logic Flow:**

1. Get current date in Central Time (America/Chicago)
2. Format date as `YYYY-MM-DD`
3. Call EODHD API with from/to = same date
4. Filter results to only `.US` tickers
5. Strip `.US` suffix and query `companies` table for matches
6. Insert matched records into `earnings_calendar`
7. Return summary (count of matches, skipped, etc.)

**Key Features:**
- Handles timezone correctly (Central Time)
- Filters non-US tickers before database lookup
- Uses batch matching for efficiency
- Logs results for debugging

---

### 3. Cron Jobs (pg_cron)

Enable `pg_cron` and `pg_net` extensions, then schedule:

| Schedule | Description | Cron Expression |
|----------|-------------|-----------------|
| 8:15 AM CT | Morning check (pre-market) | `15 14 * * 1-5` (UTC) |
| 5:30 PM CT | Afternoon check (after-market) | `30 23 * * 1-5` (UTC) |

Note: Central Time is UTC-6 (standard) or UTC-5 (daylight saving). Using UTC-6 for consistency:
- 8:15 AM CT = 14:15 UTC
- 5:30 PM CT = 23:30 UTC

---

### 4. API Token Secret

The EODHD API token (`69843c95ced641.63987594`) will be stored as a secret named `EODHD_API_TOKEN` rather than hardcoded in the function.

---

### Technical Details

**Edge Function Structure:**

```text
supabase/functions/fetch-earnings-calendar/index.ts
```

**Matching Logic:**
- API returns: `GOOG.US` → Extract: `GOOG`
- Check if `GOOG` exists in `companies.ticker`
- Note: API uses `GOOG`, your database has `GOOGL` (both are Alphabet, different share classes)
- Only exact matches will be stored

**Deduplication:**
- Add unique constraint on `(ticker, report_date, before_after_market)` to prevent duplicate entries when cron runs twice daily

---

### Files to Create/Modify

| File | Action |
|------|--------|
| Database Migration | Create `earnings_calendar` table with RLS |
| `supabase/functions/fetch-earnings-calendar/index.ts` | New edge function |
| `supabase/config.toml` | Add function configuration |
| Database Migration | Enable `pg_cron` + `pg_net` extensions |
| Database (via insert tool) | Create cron job schedules |

---

### Execution Order

1. Store EODHD API token as secret
2. Create `earnings_calendar` table with constraints and RLS
3. Enable `pg_cron` and `pg_net` extensions
4. Create edge function
5. Set up cron job schedules
6. Test manually to verify functionality

