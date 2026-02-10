

## Fix: Callback Not Reaching Dashboard + Extend Iteration/Token Limits

### Root Cause of Stuck Status

The callback URL constructed in `backfill-trigger-single` (line 97) uses `SUPABASE_URL`, which inside Lovable Cloud resolves to an **internal** address (e.g., `http://supabase-kong:8000`). Modal, running externally, cannot reach this URL. The `httpx.post` call silently fails, so the `excel_processing_runs` record is never updated.

**Fix**: Use `EXTERNAL_SUPABASE_URL` (which is already configured as `https://auth.deltasage.ai`) for the callback URL, since Modal needs to reach the publicly-accessible endpoint.

### Changes

#### 1. Fix callback URL in `backfill-trigger-single` (line 97)

**File**: `supabase/functions/backfill-trigger-single/index.ts`

Change the callback URL from:
```
callback_url: `${supabaseUrl}/functions/v1/excel-agent-callback`
```
To:
```
callback_url: `${Deno.env.get('EXTERNAL_SUPABASE_URL')}/functions/v1/excel-agent-callback`
```

This ensures Modal can actually reach the callback endpoint.

#### 2. Extend max iterations from 15 to 18

**File**: `modal-app/agent/orchestrator.py` (line 669)

Change `max_file_iterations = 15` to `max_file_iterations = 18`.

Also update the user prompt on line 664 that references "15 iterations" to say "18 iterations".

This is safe -- the Modal timeout is 1800s (30 min), and each iteration takes roughly 10-30 seconds. With 6 files at 18 iterations max, worst case is ~108 iterations, well within the timeout.

#### 3. Increase Gemini Vision max output tokens from 15k to 18k

**File**: `modal-app/agent/orchestrator.py` (line 407)

Change `"maxOutputTokens": 15000` to `"maxOutputTokens": 18000`.

Gemini 2.5 Flash supports up to 65,536 output tokens, so 18k is well within limits. This gives more room for large financial tables with many rows.

#### 4. Fix NFLX and UAL stuck records

After deploying the callback fix, manually mark the two stuck records as completed (or use the "Mark Stale as Failed" button since they are older than 45 minutes, then retry if needed).

### File Summary

| File | Change |
|---|---|
| `supabase/functions/backfill-trigger-single/index.ts` | Use `EXTERNAL_SUPABASE_URL` for the callback URL so Modal can reach it |
| `modal-app/agent/orchestrator.py` | Increase `max_file_iterations` from 15 to 18; increase Gemini `maxOutputTokens` from 15000 to 18000; update prompt text |

