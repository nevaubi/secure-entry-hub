

## Add Manual Status Controls to Backfill Dashboard

### Problem
You cannot manually mark tickers as completed, failed, or reset them for reprocessing. Additionally, the existing "Mark Stale as Failed" button is silently failing because the `excel_processing_runs` table has no UPDATE RLS policy.

### Solution
1. Add an RLS policy allowing authenticated users to update `excel_processing_runs`
2. Add a dropdown menu per row with three manual actions: **Mark Completed**, **Mark Failed**, and **Reset** (deletes the run so it shows "not started" and can be reprocessed)

### Changes

#### 1. Database Migration
Add UPDATE and DELETE policies for authenticated users on `excel_processing_runs`:

```sql
CREATE POLICY "Authenticated users can update processing runs"
  ON public.excel_processing_runs FOR UPDATE
  TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "Authenticated users can delete processing runs"
  ON public.excel_processing_runs FOR DELETE
  TO authenticated USING (true);
```

The DELETE policy is needed for the "Reset" action, which removes the run record entirely so the ticker reverts to "not started" and the Process button becomes available again.

#### 2. UI Changes in `src/pages/Backfill.tsx`

Replace the single "Process" button in each row with a row that includes:
- The existing **Process** button (for not started / failed rows)
- A **dropdown menu** (three-dot icon) with:
  - **Mark Completed** -- updates status to `completed`
  - **Mark Failed** -- updates status to `failed`
  - **Reset** -- deletes the `excel_processing_runs` record so the row goes back to "not started"

The dropdown only appears for rows that have a processing run record (i.e., not "not started").

Add two new mutations:
- `updateStatusMutation`: patches `status` and `completed_at` on the run
- `resetRunMutation`: deletes the run record for that ticker/report_date

### Technical Details

| File | Change |
|---|---|
| Database migration | Add UPDATE and DELETE RLS policies on `excel_processing_runs` |
| `src/pages/Backfill.tsx` | Add dropdown menu with Mark Completed, Mark Failed, Reset actions; add corresponding mutations |

