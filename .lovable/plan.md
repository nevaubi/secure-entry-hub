

## Fix Kimi K2.5 API Compatibility and Callback URL

### Changes

**1. `modal-app/agent/orchestrator.py`**

- **Line 703**: Increase `max_tokens` from `30000` to `32768` (the max) since thinking tokens consume part of this budget
- **Line 749**: Remove the `reasoning_content` field from assistant messages sent back to the API. This field is not part of the OpenAI-compatible message format and will cause errors. Kimi handles reasoning persistence implicitly through conversation context.

**2. `supabase/functions/backfill-trigger-single/index.ts`**

- **Line 97**: Change `EXTERNAL_SUPABASE_URL` to `SUPABASE_URL` for the callback URL, since `excel-agent-callback` is deployed on Lovable Cloud, not the external storage instance. This fixes the 404 callback error.

### Summary of all changes

| File | Line | Change |
|------|------|--------|
| `orchestrator.py` | 703 | `max_tokens=30000` -> `max_tokens=32768` |
| `orchestrator.py` | 749 | Delete `assistant_msg["reasoning_content"] = ...` line |
| `backfill-trigger-single/index.ts` | 97 | `EXTERNAL_SUPABASE_URL` -> `SUPABASE_URL` |

