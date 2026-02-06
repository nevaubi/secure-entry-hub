

## Configure Modal Webhook URL

Store the Modal webhook URL (`https://admin-84170--excel-agent-webhook.modal.run`) as a backend secret so the `trigger-excel-agent` edge function can automatically use it.

### What will happen

1. **Add a new secret** called `MODAL_WEBHOOK_URL` with value `https://admin-84170--excel-agent-webhook.modal.run`
2. No code changes are needed -- the `trigger-excel-agent` function already reads `MODAL_WEBHOOK_URL` from the environment on line 120:
   ```typescript
   const endpoint = modal_endpoint || Deno.env.get('MODAL_WEBHOOK_URL');
   ```

### How it works after configuration

- When the function is called (either manually or on schedule), it will:
  1. Query the `earnings_calendar` table for today's tickers
  2. Create `excel_processing_runs` records with `pending` status
  3. Call the Modal webhook at your URL with the ticker list
  4. Modal processes each ticker and calls back via `excel-agent-callback` to update status

### Testing

After the secret is added, we can test the full pipeline by calling the `trigger-excel-agent` function directly to verify the connection between your backend and Modal is working.

### Technical Details

- **Secret name**: `MODAL_WEBHOOK_URL`
- **Secret value**: `https://admin-84170--excel-agent-webhook.modal.run`
- **Used by**: `supabase/functions/trigger-excel-agent/index.ts` (line 120)
- **No file changes required** -- only a secret needs to be added
