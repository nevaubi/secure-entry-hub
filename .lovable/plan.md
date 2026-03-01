

## Stop All Cron Jobs and Modal Functionalities

### Current State

**14 active cron jobs** to unschedule:

| Job ID | Name | Function |
|--------|------|----------|
| 3 | fetch-earnings-daily | fetch-earnings-calendar |
| 4 | process-premarket-files | process-earnings-files (premarket) |
| 5 | process-afterhours-files | process-earnings-files (afterhours) |
| 6 | fetch-finviz-news-5am | fetch-finviz-news |
| 7 | fetch-finviz-news-11am | fetch-finviz-news |
| 8 | fetch-finviz-news-4pm | fetch-finviz-news |
| 9 | sync-news-morning | sync-news-external |
| 10 | sync-news-midday | sync-news-external |
| 12 | summarize-news-morning | summarize-news |
| 13 | summarize-news-midday | summarize-news |
| 14 | summarize-news-afternoon | summarize-news |
| 15 | sync-news-afternoon | sync-news-external |
| 16 | fetch-premarket-futures-weekday-morning | fetch-premarket-futures |

**Modal integration**: The `trigger-excel-agent` and `excel-agent-callback` edge functions connect to Modal.com for the agentic Excel pipeline.

### Implementation Steps

1. **Unschedule all 14 cron jobs** via a single SQL statement calling `cron.unschedule()` for each job by name.

2. **Remove Modal references from edge functions**: Update `trigger-excel-agent` to no longer call the Modal webhook (or simply leave it inactive since the cron that triggers it is removed). Same for `excel-agent-callback`.

Since no cron jobs will be firing, the Modal pipeline won't be triggered automatically. The edge functions themselves can remain deployed but dormant -- or I can remove the Modal-specific code from them. Which approach do you prefer, or should I just stop the cron jobs and leave the function code as-is?

### Technical Details

SQL to unschedule all jobs:
```sql
SELECT cron.unschedule('fetch-earnings-daily');
SELECT cron.unschedule('process-premarket-files');
SELECT cron.unschedule('process-afterhours-files');
SELECT cron.unschedule('fetch-finviz-news-5am');
SELECT cron.unschedule('fetch-finviz-news-11am');
SELECT cron.unschedule('fetch-finviz-news-4pm');
SELECT cron.unschedule('sync-news-morning');
SELECT cron.unschedule('sync-news-midday');
SELECT cron.unschedule('summarize-news-morning');
SELECT cron.unschedule('summarize-news-midday');
SELECT cron.unschedule('summarize-news-afternoon');
SELECT cron.unschedule('sync-news-afternoon');
SELECT cron.unschedule('fetch-premarket-futures-weekday-morning');
```

This will be executed as a direct SQL statement (not a migration, since cron jobs contain environment-specific data).

