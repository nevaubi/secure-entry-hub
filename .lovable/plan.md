

## Sync Rolling Market News to External Supabase

### What gets synced

Only rows where `summary IS NOT NULL`. The following 6 columns are sent (no `id`, no `created_at`):

| Column | Type | Notes |
|---|---|---|
| title | text | NOT NULL |
| source | text | NOT NULL |
| published_at | timestamptz | NOT NULL |
| url | text | NOT NULL, unique constraint (upsert key) |
| category | text | NOT NULL |
| summary | text | NOT NULL (guaranteed by the filter) |

### Exact SQL for the external Supabase table

Run this on the external Supabase project:

```text
CREATE TABLE public.rolling_market_news (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  source text NOT NULL,
  published_at timestamp with time zone NOT NULL,
  url text NOT NULL,
  category text NOT NULL,
  summary text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT rolling_market_news_url_key UNIQUE (url)
);
```

The external table has its own `id` and `created_at` (auto-generated), but the sync payload never sends those -- the external DB fills them in on insert.

### Edge function: `sync-news-external`

1. Query local `rolling_market_news` for all rows where `summary IS NOT NULL` (up to 300)
2. Select only `title, source, published_at, url, category, summary`
3. Create an external Supabase client using existing `EXTERNAL_SUPABASE_URL` and `EXTERNAL_SUPABASE_SERVICE_KEY`
4. Upsert into external `rolling_market_news` in batches of 50, conflict on `url`
5. On conflict, all fields are overwritten (summary may have been updated)
6. Return `{ synced: N, errors: [...] }`

### Config addition

```text
[functions.sync-news-external]
verify_jwt = false
```

### Error handling

- Per-batch errors are logged but don't stop remaining batches
- Function returns a summary of successes and failures

### Secrets

Uses existing secrets -- no new ones needed:
- `EXTERNAL_SUPABASE_URL`
- `EXTERNAL_SUPABASE_SERVICE_KEY`

### Future expansion

Once verified for `rolling_market_news`, extend to the other 3 tables by looping over a config array.

