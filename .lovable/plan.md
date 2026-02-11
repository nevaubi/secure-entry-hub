
## Set Up 3 Daily Cron Jobs for sync-news-external

### Goal
Schedule `sync-news-external` to run 3 times daily on weekdays at:
- 5:30 AM Central Time
- 11:30 AM Central Time  
- 4:00 PM Central Time

This gives the `fetch-finviz-news` function (which runs at 5 AM, 11 AM, 4 PM) 30 minutes to complete before syncing.

### Approach

**1. Cron Expressions for Chicago Time**

The cron jobs need to run on weekdays (Monday-Friday) only. Using standard 5-field cron format adjusted for Chicago timezone (UTC-6 / UTC-5 during DST):

| Time | Cron Expression | Details |
|---|---|---|
| 5:30 AM Chicago | `30 5 * * 1-5` | Every weekday at 05:30 UTC |
| 11:30 AM Chicago | `30 11 * * 1-5` | Every weekday at 11:30 UTC |
| 4:00 PM Chicago | `0 16 * * 1-5` | Every weekday at 16:00 UTC |

**Note**: Supabase stores times in UTC. Chicago Central Time is UTC-6 (EST) or UTC-5 (EDT). We need to convert:
- 5:30 AM CT → 11:30 UTC or 12:30 UTC (depending on DST)
- 11:30 AM CT → 17:30 UTC or 18:30 UTC (depending on DST)
- 4:00 PM CT → 22:00 UTC or 23:00 UTC (depending on DST)

For simplicity and to avoid DST complexity, we'll use the UTC-6 offsets (standard winter times):
- 5:30 AM CT = 11:30 UTC
- 11:30 AM CT = 17:30 UTC
- 4:00 PM CT = 22:00 UTC

**2. SQL Migration with 3 Cron Jobs**

Create a new migration file that:
- Enables `pg_cron` extension (if not already enabled)
- Creates 3 separate `cron.schedule()` calls, each posting to the `sync-news-external` function

Each call will:
- Use the project's full function URL: `https://wbwyumlaiwnqetqavnph.supabase.co/functions/v1/sync-news-external`
- Include the anon key in the Authorization header
- Send a POST request with empty JSON body

**3. Error Handling**

- Cron jobs will silently log failures to the database; monitor logs via the backend analytics tool
- If a sync fails, the next scheduled run will attempt again (idempotent due to URL-based upsert key)

### Implementation Steps

1. **Create migration SQL** with 3 cron.schedule calls for the specified times
2. **Execute via migration tool** - user approval required
3. **Verify** by checking that the cron jobs appear in the pg_cron catalog

### Technical Details

| Item | Value |
|---|---|
| Extension | `pg_cron` (must be enabled) |
| Job Count | 3 (one per sync time) |
| Frequency | Weekdays only (Mon-Fri) |
| Error Handling | Logged to cron_job_run_details table |
| Idempotency | Yes - upserts on URL prevent duplicates |
| Retries | Manual if needed; scheduled jobs don't auto-retry |

