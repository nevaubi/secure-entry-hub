

## Expand Premarket Futures to 9 Instruments + Single-Row Overwrite

### What's Changing

Two updates to the existing premarket futures workflow:

1. **Single-row overwrite**: Instead of inserting a new row each run, the function will upsert a single row so the table always contains only the most recent data.
2. **6 new instruments**: Add Gold (GC=F), Silver (SI=F), Crude Oil (CL=F), 10-Year T-Note (ZN=F), 5-Year T-Note (ZF=F), and 2-Year T-Note (ZT=F) -- bringing the total to 9 futures tracked.

### Database Migration

Add columns for 6 new instruments (same pattern as existing: symbol, name, price, market_time, change, change_pct, volume, open_interest per instrument):

| Prefix | Symbol | Description |
|--------|--------|-------------|
| gold_ | GC=F | Gold Futures |
| silver_ | SI=F | Silver Futures |
| crude_ | CL=F | Crude Oil Futures |
| tnote10_ | ZN=F | 10-Year T-Note Futures |
| tnote5_ | ZF=F | 5-Year T-Note Futures |
| tnote2_ | ZT=F | 2-Year T-Note Futures |

Each gets 8 columns: `_symbol`, `_name`, `_price`, `_market_time`, `_change`, `_change_pct`, `_volume`, `_open_interest` -- 48 new columns total.

Also add a unique constraint on the `id` column (already PK) so we can use Supabase upsert with `onConflict`.

### Single-Row Strategy

To keep only 1 row, the function will:
1. Delete all existing rows from the table
2. Insert the fresh row

This avoids needing a special unique constraint beyond the PK. Simple and clean.

### Edge Function Changes

**File:** `supabase/functions/fetch-premarket-futures/index.ts`

1. Update Gemini system prompt to list all 9 target symbols: ES=F, YM=F, NQ=F, GC=F, SI=F, CL=F, ZN=F, ZF=F, ZT=F
2. Expand the tool calling schema to include all 72 fields (9 instruments x 8 fields each)
3. Change DB operation from `.insert()` to: first `.delete().neq('id', '00000000-0000-0000-0000-000000000000')` (deletes all rows), then `.insert()` the fresh data
4. Update the user prompt to mention all 9 futures

### Screenshot Considerations

The Yahoo Finance futures page shows all these instruments on the same page (visible in the screenshot), so no changes needed to Firecrawl configuration. The existing wait + screenshot approach captures them all.

### No Other Changes

- pg_cron schedule stays the same
- RLS policies unchanged
- Config.toml unchanged

### Technical Details

**New Gemini tool schema fields** (in addition to existing dow/sp500/nas):
```
gold_symbol, gold_name, gold_price, gold_market_time, gold_change, gold_change_pct, gold_volume, gold_open_interest
silver_symbol, silver_name, silver_price, silver_market_time, silver_change, silver_change_pct, silver_volume, silver_open_interest
crude_symbol, crude_name, crude_price, crude_market_time, crude_change, crude_change_pct, crude_volume, crude_open_interest
tnote10_symbol, tnote10_name, tnote10_price, tnote10_market_time, tnote10_change, tnote10_change_pct, tnote10_volume, tnote10_open_interest
tnote5_symbol, tnote5_name, tnote5_price, tnote5_market_time, tnote5_change, tnote5_change_pct, tnote5_volume, tnote5_open_interest
tnote2_symbol, tnote2_name, tnote2_price, tnote2_market_time, tnote2_change, tnote2_change_pct, tnote2_volume, tnote2_open_interest
```

**DB operation** (delete-then-insert pattern):
```typescript
// Delete all existing rows
await supabase.from("recurring_premarket_data").delete().neq("id", "00000000-0000-0000-0000-000000000000");

// Insert fresh row with all 9 instruments
const { data, error } = await supabase.from("recurring_premarket_data").insert({ ... }).select().single();
```

### Files to Modify

1. **Database Migration** -- Add 48 new columns (6 instruments x 8 fields each)
2. **Edge Function** -- `supabase/functions/fetch-premarket-futures/index.ts` (update prompt, schema, and DB logic)

