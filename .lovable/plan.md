

## Implementation Plan: Two Daily File Processing Crons

### Overview

This plan adds two separate cron jobs to process Excel files for tickers reporting earnings, while leaving the existing 5:00 AM CT earnings fetch cron untouched.

---

### Schedule Summary

| Cron Job | Central Time | UTC (Cron Expression) | Purpose |
|----------|--------------|----------------------|---------|
| `fetch-earnings-daily` | 5:00 AM CT | `0 11 * * 1-5` | Existing - Populates earnings_calendar |
| `process-premarket-files` | 8:15 AM CT | `15 14 * * 1-5` | NEW - Process BeforeMarket tickers |
| `process-afterhours-files` | 5:30 PM CT | `30 23 * * 1-5` | NEW - Process AfterMarket + null tickers |

---

### Architecture

```text
5:00 AM CT - fetch-earnings-daily (EXISTING - NO CHANGES)
     │
     ▼
 earnings_calendar table populated
     │
     ├────────────────────────────────────────────┐
     │                                            │
     ▼                                            ▼
8:15 AM CT                                   5:30 PM CT
process-earnings-files                       process-earnings-files
  (timing = 'premarket')                       (timing = 'afterhours')
     │                                            │
     ▼                                            ▼
Filter: before_after_market                  Filter: before_after_market
  = 'BeforeMarket'                             IN ('AfterMarket', NULL)
     │                                            │
     └────────────┬───────────────────────────────┘
                  │
                  ▼
        For each ticker:
        Access 12 Excel files from external storage
        Log results to earnings_file_processing table
```

---

### Implementation Steps

#### Step 1: Create Database Table

Create `earnings_file_processing` table to track file access status.

```sql
CREATE TABLE earnings_file_processing (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  report_date DATE NOT NULL,
  bucket_name TEXT NOT NULL,
  file_exists BOOLEAN DEFAULT false,
  file_size_bytes INTEGER,
  processed_at TIMESTAMPTZ,
  status TEXT DEFAULT 'pending',
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(ticker, report_date, bucket_name)
);

ALTER TABLE earnings_file_processing ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can view processing status"
  ON earnings_file_processing FOR SELECT
  TO authenticated USING (true);
```

---

#### Step 2: Create Edge Function

Create `process-earnings-files` function with a `timing` parameter:

| Parameter | Values | Filters |
|-----------|--------|---------|
| `timing` | `'premarket'` | `before_after_market = 'BeforeMarket'` |
| `timing` | `'afterhours'` | `before_after_market IN ('AfterMarket') OR IS NULL` |
| `date` | `'YYYY-MM-DD'` | Override date (optional, for testing) |
| `ticker` | `'AAPL'` | Process single ticker (optional, for testing) |

**Storage Buckets to Check (12 total):**
- `financials-annual-income`
- `financials-quarterly-income`
- `financials-annual-balance`
- `financials-quarterly-balance`
- `financials-annual-cashflow`
- `financials-quarterly-cashflow`
- `standardized-annual-income`
- `standardized-quarterly-income`
- `standardized-annual-balance`
- `standardized-quarterly-balance`
- `standardized-annual-cashflow`
- `standardized-quarterly-cashflow`

---

#### Step 3: Schedule Two Cron Jobs

**Pre-Market Cron (8:15 AM CT = 14:15 UTC):**
```sql
SELECT cron.schedule(
  'process-premarket-files',
  '15 14 * * 1-5',
  $$
  SELECT net.http_post(
    url := 'https://wbwyumlaiwnqetqavnph.supabase.co/functions/v1/process-earnings-files',
    headers := '{"Content-Type": "application/json", "Authorization": "Bearer ..."}'::jsonb,
    body := '{"timing": "premarket"}'::jsonb
  ) AS request_id;
  $$
);
```

**After-Hours Cron (5:30 PM CT = 23:30 UTC):**
```sql
SELECT cron.schedule(
  'process-afterhours-files',
  '30 23 * * 1-5',
  $$
  SELECT net.http_post(
    url := 'https://wbwyumlaiwnqetqavnph.supabase.co/functions/v1/process-earnings-files',
    headers := '{"Content-Type": "application/json", "Authorization": "Bearer ..."}'::jsonb,
    body := '{"timing": "afterhours"}'::jsonb
  ) AS request_id;
  $$
);
```

---

#### Step 4: Update config.toml

Add configuration for the new Edge Function:

```toml
[functions.process-earnings-files]
verify_jwt = false
```

---

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `supabase/functions/process-earnings-files/index.ts` | Create | Edge Function with timing-based filtering |
| `supabase/config.toml` | Modify | Add function configuration |
| Database migration | Create | Add tracking table |
| SQL insert | Execute | Schedule both cron jobs |

---

### Edge Function Logic Summary

```text
1. Parse request body for timing parameter
2. Get current date in Central Time (or use override)
3. Query earnings_calendar with appropriate filter:
   - premarket: WHERE before_after_market = 'BeforeMarket'
   - afterhours: WHERE before_after_market = 'AfterMarket' OR before_after_market IS NULL
4. For each ticker found:
   a. Connect to external Supabase using EXTERNAL_SUPABASE_URL and EXTERNAL_SUPABASE_SERVICE_KEY
   b. Loop through 12 storage buckets
   c. Attempt to download {TICKER}.xlsx from each bucket
   d. Record file existence, size, or error
   e. Upsert results to earnings_file_processing table
5. Return summary of processed tickers and file accessibility
```

---

### Testing Strategy

After implementation:
1. Manually call the function with `{"timing": "premarket", "ticker": "AAPL"}` to test a single ticker
2. Verify file access works with external storage
3. Check `earnings_file_processing` table for correct logging
4. Monitor the scheduled cron jobs over a few days

