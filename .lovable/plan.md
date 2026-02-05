

## Step 1: Connect to External Storage and Access Excel Files

This plan focuses on building the infrastructure to connect to your external Supabase storage and access the 12 Excel files per ticker when earnings are detected.

---

### Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                         Current Lovable Cloud                            │
├─────────────────────────────────────────────────────────────────────────┤
│  earnings_calendar table                                                 │
│  (populated daily at 5 AM CT)                                           │
│           │                                                              │
│           ▼                                                              │
│  ┌─────────────────────────────────┐                                    │
│  │  process-earnings-files         │  ◄── NEW Edge Function             │
│  │  (separate cron job)            │      Runs after earnings fetch     │
│  └─────────────────────────────────┘                                    │
│           │                                                              │
└───────────┼─────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    External Supabase Project                             │
├─────────────────────────────────────────────────────────────────────────┤
│  Storage Buckets (12 total):                                            │
│  ┌────────────────────────────┐  ┌────────────────────────────┐        │
│  │  As Reported               │  │  Standardized              │        │
│  │  ├── income-stmt-quarterly │  │  ├── income-stmt-quarterly │        │
│  │  ├── income-stmt-annual    │  │  ├── income-stmt-annual    │        │
│  │  ├── balance-sheet-quarterly│ │  ├── balance-sheet-quarterly│       │
│  │  ├── balance-sheet-annual  │  │  ├── balance-sheet-annual  │        │
│  │  ├── cash-flow-quarterly   │  │  ├── cash-flow-quarterly   │        │
│  │  └── cash-flow-annual      │  │  └── cash-flow-annual      │        │
│  └────────────────────────────┘  └────────────────────────────┘        │
│                                                                          │
│  Each bucket contains: {TICKER}.xlsx files                              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### What You'll Need to Provide

Before implementation, I'll need you to add two secrets for your external Supabase project:

| Secret Name | Description |
|-------------|-------------|
| `EXTERNAL_SUPABASE_URL` | The URL of your external Supabase project (e.g., `https://xxxxx.supabase.co`) |
| `EXTERNAL_SUPABASE_SERVICE_KEY` | The service role key for the external project (found in Project Settings → API) |

---

### Implementation Steps

1. **Store External Supabase Credentials**
   - Add `EXTERNAL_SUPABASE_URL` secret
   - Add `EXTERNAL_SUPABASE_SERVICE_KEY` secret

2. **Create New Edge Function: `process-earnings-files`**
   - Query `earnings_calendar` for today's tickers
   - For each ticker, attempt to access all 12 Excel files from the external storage
   - Log which files exist and which are missing
   - Return a summary of accessible files

3. **Create Tracking Table: `earnings_file_processing`**
   - Track processing status per ticker per day
   - Columns: ticker, report_date, file_type, status, processed_at, error_message

4. **Schedule Separate Cron Job**
   - Run at 5:30 AM CT (30 minutes after earnings fetch)
   - This gives time for the earnings data to be populated first

---

### Storage Bucket Naming Clarification

Please confirm your bucket naming structure. I'm assuming 12 separate buckets like:
- `as-reported-income-stmt-quarterly`
- `as-reported-income-stmt-annual`
- `standardized-balance-sheet-quarterly`
- etc.

Or are they organized differently (e.g., two buckets with subfolders)?

---

### Technical Details

**Edge Function Logic (Phase 1 - Read Only):**
```typescript
// Create client for external Supabase
const externalSupabase = createClient(
  Deno.env.get('EXTERNAL_SUPABASE_URL')!,
  Deno.env.get('EXTERNAL_SUPABASE_SERVICE_KEY')!
);

// For each ticker with earnings today
for (const ticker of tickersWithEarnings) {
  const buckets = [
    'as-reported-income-stmt-quarterly',
    'as-reported-income-stmt-annual',
    // ... all 12 buckets
  ];
  
  for (const bucket of buckets) {
    const { data, error } = await externalSupabase.storage
      .from(bucket)
      .download(`${ticker}.xlsx`);
    
    // Log file accessibility status
  }
}
```

**New Table Schema:**
```sql
CREATE TABLE earnings_file_processing (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  report_date DATE NOT NULL,
  bucket_name TEXT NOT NULL,
  file_exists BOOLEAN DEFAULT false,
  processed_at TIMESTAMPTZ,
  status TEXT DEFAULT 'pending',
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(ticker, report_date, bucket_name)
);
```

---

### Next Steps After This Phase

Once we confirm the file access works:
1. Choose a data source for financial statement updates
2. Implement Excel file parsing and modification
3. Add file upload back to storage after updates

