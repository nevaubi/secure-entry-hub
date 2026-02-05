

## Update Cron Schedule: Single Daily Run at 5:00 AM CT

This change simplifies the earnings fetch schedule from two daily runs to one early-morning run.

---

### Current State

| Job Name | Schedule (UTC) | Central Time |
|----------|---------------|--------------|
| `fetch-earnings-morning` | `15 14 * * 1-5` | 8:15 AM CT |
| `fetch-earnings-afternoon` | `30 23 * * 1-5` | 5:30 PM CT |

---

### New Schedule

| Job Name | Schedule (UTC) | Central Time |
|----------|---------------|--------------|
| `fetch-earnings-daily` | `0 11 * * 1-5` | 5:00 AM CT |

**Time Conversion:** 5:00 AM Central Time = 11:00 UTC (using CST/UTC-6)

---

### Implementation Steps

1. **Delete existing cron jobs** - Remove both `fetch-earnings-morning` and `fetch-earnings-afternoon` from `cron.job`

2. **Create new single cron job** - Add `fetch-earnings-daily` scheduled for 5:00 AM CT (11:00 UTC) on weekdays

---

### SQL Operations

```sql
-- Remove old jobs
SELECT cron.unschedule('fetch-earnings-morning');
SELECT cron.unschedule('fetch-earnings-afternoon');

-- Create new single daily job at 5:00 AM CT (11:00 UTC)
SELECT cron.schedule(
  'fetch-earnings-daily',
  '0 11 * * 1-5',
  -- HTTP POST to edge function
);
```

---

### Benefits

- Simpler schedule to manage
- Single source of truth for daily earnings data
- Early run ensures data is ready before market opens (9:30 AM ET / 8:30 AM CT)

