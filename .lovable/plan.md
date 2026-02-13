

## Automated CNBC Premarket Futures Workflow

### Overview
Create a fully automated weekday workflow (6 AM Chicago Time) that:
1. Uses Firecrawl to navigate CNBC, click the "PRE-MKT" tab, and capture a screenshot
2. Sends the screenshot to Gemini 3 Flash Preview with strict structured extraction prompts
3. Parses the extracted futures data (DOW FUT, S&P FUT, NAS FUT) with price, change, percent change, and timestamp
4. Stores results in a new `recurring_premarket_data` table

### Architecture

The workflow integrates three existing project components:
- **Firecrawl** (already configured via FIRECRAWL_API_KEY) — headless browser + screenshot
- **Lovable AI Gateway** (LOVABLE_API_KEY already available) — Gemini 3 Flash Preview for vision extraction
- **pg_cron** (already in use) — weekday morning scheduling at 6 AM CT

### Step 1: Create the `recurring_premarket_data` Table

New table schema to store daily premarket futures snapshots:

| Column | Type | Description |
|--------|------|-------------|
| id | uuid (PK) | Auto-generated |
| captured_at | timestamptz | When the screenshot was taken |
| dow_price | numeric | DOW Futures price |
| dow_change | numeric | DOW change amount |
| dow_change_pct | numeric | DOW change percent |
| dow_direction | text | 'up' or 'down' |
| sp500_price | numeric | S&P 500 Futures price |
| sp500_change | numeric | S&P 500 change amount |
| sp500_change_pct | numeric | S&P 500 change percent |
| sp500_direction | text | 'up' or 'down' |
| nas_price | numeric | Nasdaq Futures price |
| nas_change | numeric | Nasdaq change amount |
| nas_change_pct | numeric | Nasdaq change percent |
| nas_direction | text | 'up' or 'down' |
| last_updated | text | Timestamp from CNBC screenshot (e.g., "LAST | 11:15:31 AM EST") |
| screenshot_url | text | Firecrawl screenshot URL (expires 24h) |
| raw_gemini_response | jsonb | Full LLM extraction response for debugging |
| created_at | timestamptz | Row creation timestamp |

RLS policy: Authenticated users can SELECT only.

### Step 2: Create the `fetch-premarket-futures` Edge Function

**Location**: `supabase/functions/fetch-premarket-futures/index.ts`

**Workflow**:
1. Call Firecrawl scrape API with:
   - URL: `https://www.cnbc.com/`
   - Actions: navigate page, click the PRE-MKT button (`MarketsBannerMenu-activeMarket` class), take screenshot
   - Format: `["screenshot"]`

2. Send the screenshot to Lovable AI Gateway (Gemini 3 Flash Preview) with:
   - **Strict system prompt**: Extract ONLY the three futures indices data visible in premarket banner
   - **Image input**: Base64 or URL from Firecrawl screenshot
   - **Tool calling**: Use structured JSON response format requesting exact fields (dow_price, dow_change, dow_change_pct, dow_direction, sp500_price, sp500_change, sp500_change_pct, sp500_direction, nas_price, nas_change, nas_change_pct, nas_direction, last_updated)
   - **Error handling**: If extraction fails or fields are missing, log and retry once

3. Parse Gemini response and insert into `recurring_premarket_data`:
   - Validate all required numeric fields are present
   - Parse direction from the up/down arrow indicators
   - Extract timestamp from CNBC
   - Store raw response for debugging

4. Return success/failure status with extracted data

**Error Handling**:
- Missing FIRECRAWL_API_KEY or LOVABLE_API_KEY → return 500 with clear error
- Firecrawl timeout/failure → return 500 with error details
- Gemini extraction failure → return 500 with error details
- Missing fields in Gemini response → log warning, insert partial data with nulls, continue

**Configuration**:
- Update `supabase/config.toml` to add:
  ```toml
  [functions.fetch-premarket-futures]
  verify_jwt = false
  ```

### Step 3: Schedule via pg_cron

6:00 AM Chicago Time = 12:00 UTC

Create a cron job to invoke the edge function:
```sql
SELECT cron.schedule(
  'fetch-premarket-futures-weekday-morning',
  '0 12 * * 1-5',  -- 6 AM CT / 12 PM UTC, weekdays only
  $$
  SELECT net.http_post(
    url := 'https://{project-id}.supabase.co/functions/v1/fetch-premarket-futures',
    headers := '{"Content-Type": "application/json", "Authorization": "Bearer {SUPABASE_ANON_KEY}"}'::jsonb,
    body := '{"trigger": "cron"}'::jsonb
  ) AS request_id;
  $$
);
```

### Technical Implementation Details

**Edge Function Features**:
- Use `FIRECRAWL_API_KEY` for browser automation
- Use `LOVABLE_API_KEY` for Gemini gateway calls via `https://ai.gateway.lovable.dev/v1/chat/completions`
- Service role Supabase client for direct table inserts (no RLS restrictions)
- Proper error logging with timestamps for debugging

**Gemini 3 Flash Preview Configuration**:
- Model: `google/gemini-3-flash-preview`
- Tool choice: Use structured function calling to ensure JSON output
- Tool schema: Define extraction function with required fields (dow_price, dow_change, dow_change_pct, dow_direction, sp500_price, sp500_change, sp500_change_pct, sp500_direction, nas_price, nas_change, nas_change_pct, nas_direction, last_updated)

**Firecrawl Screenshot Configuration**:
```javascript
{
  url: "https://www.cnbc.com/",
  actions: [
    { type: "wait", milliseconds: 3000 },
    { type: "click", selector: ".MarketsBannerMenu-activeMarket" },
    { type: "wait", milliseconds: 1500 },
    { type: "screenshot", fullPage: false }
  ],
  formats: ["screenshot"]
}
```

### Files to Create/Modify

1. **Database Migration** — Create `recurring_premarket_data` table with schema above
2. **Edge Function** — `supabase/functions/fetch-premarket-futures/index.ts`
3. **Config Update** — Add function entry to `supabase/config.toml`
4. **Cron Job** — SQL insert to `cron.job` table (via direct SQL execution, not migration)

### Timeline & Dependencies

1. Create table (migration)
2. Create edge function code
3. Deploy function (auto-deployed when code is written)
4. Register cron job (SQL executed after function is live)

### Testing Plan

- Manual function invocation via the backend interface to verify:
  - Firecrawl screenshot successfully captures CNBC PRE-MKT tab
  - Gemini extraction returns valid JSON with all required fields
  - Data inserts successfully into `recurring_premarket_data`
- Verify cron schedule is registered and runs at 6 AM CT on next weekday morning

