

## Update Premarket Futures to Use Yahoo Finance

### What's Changing

Switch the data source from CNBC to Yahoo Finance's futures page (`https://finance.yahoo.com/markets/commodities/`) and update the database schema to match the richer data available in Yahoo's table.

### New Schema for `recurring_premarket_data`

The Yahoo Finance futures table provides more structured data than CNBC's banner. We'll add columns for symbol, name, market time, volume, and open interest, and remove the `direction` columns (since direction is implicit from the sign of the change value).

**Add columns:**
| Column | Type | Description |
|--------|------|-------------|
| dow_symbol | text | e.g. "YM=F" |
| dow_name | text | e.g. "Mini Dow Jones Indus..." |
| dow_market_time | text | e.g. "11:37AM EST" |
| dow_volume | text | e.g. "95,915" (stored as text to preserve formatting) |
| dow_open_interest | text | e.g. "69,303" |
| sp500_symbol | text | e.g. "ES=F" |
| sp500_name | text | e.g. "E-Mini S&P 500 Mar 26" |
| sp500_market_time | text | e.g. "11:37AM EST" |
| sp500_volume | text | e.g. "1.061M" |
| sp500_open_interest | text | e.g. "1.895M" |
| nas_symbol | text | e.g. "NQ=F" |
| nas_name | text | e.g. "Nasdaq 100 Mar 26" |
| nas_market_time | text | e.g. "11:37AM EST" |
| nas_volume | text | e.g. "448,483" |
| nas_open_interest | text | e.g. "269,452" |

**Remove columns** (direction is now derived from change sign):
- dow_direction
- sp500_direction
- nas_direction
- last_updated (replaced by per-index market_time)

### Edge Function Changes

**File:** `supabase/functions/fetch-premarket-futures/index.ts`

1. Change URL from `https://www.cnbc.com/` to `https://finance.yahoo.com/markets/commodities/`
2. Remove the click action (no button to click -- the futures table is already visible on the page)
3. Update the Gemini prompt to reference Yahoo Finance's futures table with columns: Symbol, Name, Price, Market Time, Change, Change %, Volume, Open Interest
4. Update the tool calling schema to include all new fields (symbol, name, market_time, volume, open_interest per index) and remove direction/last_updated
5. Update the DB insert to match new columns

### Database Migration

Single migration to:
- Add 15 new columns (symbol, name, market_time, volume, open_interest x3 indices)
- Drop 4 old columns (dow_direction, sp500_direction, nas_direction, last_updated)

### No Other Changes Needed

- The pg_cron schedule stays the same (weekday 6 AM CT)
- Config.toml entry already exists
- RLS policies remain unchanged

### Technical Details

**Firecrawl config (simplified -- no click needed):**
```javascript
{
  url: "https://finance.yahoo.com/markets/commodities/",
  actions: [
    { type: "wait", milliseconds: 3000 },
    { type: "screenshot", fullPage: false }
  ],
  formats: ["screenshot"]
}
```

**Gemini extraction tool schema** will request: dow_symbol, dow_name, dow_price, dow_market_time, dow_change, dow_change_pct, dow_volume, dow_open_interest (and same for sp500/nas prefixes).

**Prompt** will instruct Gemini to find the rows for ES=F (S&P 500), YM=F (Dow), and NQ=F (Nasdaq 100) specifically from the Yahoo Finance futures table.
