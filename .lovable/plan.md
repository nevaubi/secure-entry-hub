

## Standardized Financial Data Agent — Implementation Plan

### Overview

Create a new Modal app (`modal-app-standardized/`) that mirrors the existing as-reported agent but targets **standardized** data with 8 files (adding ratios), uses only StockAnalysis as the data source, and points to the new external Supabase storage instance.

### 1. Update External Supabase Secrets

The `EXTERNAL_SUPABASE_URL` and `EXTERNAL_SUPABASE_SERVICE_KEY` secrets need to be replaced with the new storage instance credentials. Will use the `add_secret` tool to prompt you to enter the new values.

### 2. New Modal App: `modal-app-standardized/`

**Files to create** (adapted from `modal-app/`):

| File | Changes from Original |
|---|---|
| `app.py` | App name `standardized-excel-agent`, remove `perplexity-secret` from secrets list |
| `agent/__init__.py` | Same |
| `agent/storage.py` | 8 buckets: `standardized-quarterly-income`, `standardized-quarterly-balance`, `standardized-quarterly-cashflows`, `standardized-quarterly-ratios`, `standardized-annual-income`, `standardized-annual-balance`, `standardized-annual-cashflows`, `standardized-annual-ratios` |
| `agent/browser.py` | New `navigate_to_financials()` that: (1) navigates to URL, (2) clicks "Standardized" button, (3) opens number units dropdown → clicks "Raw", (4) opens Data Source dropdown → clicks "Fiscal.ai". Add ratios URL support (`/financials/ratios/`). Ratios page has no number-units dropdown — skip that step for ratios. |
| `agent/orchestrator.py` | 8-file FILE_ORDER (quarterly income/balance/cashflow/ratios, then annual). Remove `web_search` tool entirely. Update `browse_stockanalysis` to accept `data_type: "standardized"` and add `"ratios"` to statement_type enum. Update system prompt to remove web_search references. |
| `agent/updater.py` | Reuse as-is |
| `agent/schema.py` | Reuse as-is |
| `requirements.txt` | Same |

**Key browser flow** (from Puppeteer script analysis):
```text
1. Navigate to stockanalysis.com/stocks/{ticker}/financials/
2. Click "Standardized" button (selector: button.rounded-l-md with text "Standardized")
3. Click number units dropdown (aria: "Millions" or similar) → Click "Raw" option
4. Click Data Source dropdown (aria: "Data Source") → Click "Fiscal.ai" option
5. For period: click "Annual" or "Quarterly" tab button
6. For statement: click nav links "Income Statement" / "Balance Sheet" / "Cash Flow" / "Ratios"
7. For Ratios: skip the number-units dropdown (doesn't exist), but still set Data Source to Fiscal.ai
```

**Important**: Settings (Standardized/Raw/Fiscal.ai) need to be re-applied after each statement/period navigation since the page reloads. The browser will apply these settings after every `navigate_to_financials()` call.

### 3. Edge Functions

**`supabase/functions/trigger-standardized-agent/index.ts`**
- Simple manual trigger: accepts `{ ticker: string }` in request body
- Creates a record in `standardized_processing_runs` table
- Calls Modal webhook with single ticker payload
- No earnings calendar lookup needed

**`supabase/functions/standardized-agent-callback/index.ts`**
- Same pattern as existing `excel-agent-callback`
- Updates `standardized_processing_runs` table on completion/failure

**`supabase/config.toml`** additions:
```toml
[functions.trigger-standardized-agent]
verify_jwt = false

[functions.standardized-agent-callback]
verify_jwt = false
```

### 4. Database Migration

New table `standardized_processing_runs`:
```sql
CREATE TABLE public.standardized_processing_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  started_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ,
  files_updated INTEGER DEFAULT 0,
  data_sources_used TEXT[],
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.standardized_processing_runs ENABLE ROW LEVEL SECURITY;
```

### 5. New Modal Secret Needed

A new `MODAL_WEBHOOK_URL` value will be needed once the standardized Modal app is deployed (it gets a new webhook URL). For now the edge function will accept it as an optional body parameter `modal_endpoint` (same pattern as the existing trigger).

### Files Summary

| Action | File |
|---|---|
| Create | `modal-app-standardized/app.py` |
| Create | `modal-app-standardized/agent/__init__.py` |
| Create | `modal-app-standardized/agent/orchestrator.py` |
| Create | `modal-app-standardized/agent/browser.py` |
| Create | `modal-app-standardized/agent/storage.py` |
| Create | `modal-app-standardized/agent/updater.py` |
| Create | `modal-app-standardized/agent/schema.py` |
| Create | `modal-app-standardized/requirements.txt` |
| Create | `supabase/functions/trigger-standardized-agent/index.ts` |
| Create | `supabase/functions/standardized-agent-callback/index.ts` |
| Modify | `supabase/config.toml` (auto-managed, just noting the entries needed) |
| Migration | New `standardized_processing_runs` table |
| Secrets | Replace `EXTERNAL_SUPABASE_URL` + `EXTERNAL_SUPABASE_SERVICE_KEY` with new values |

