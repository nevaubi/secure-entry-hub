

## Plan: Add "Backfill2" Page for Standardized Agent

### What it does
A new `/backfill2` page with:
1. **Manual trigger** — text input for ticker + "Process" button that calls `trigger-standardized-agent`
2. **Processing runs table** — shows all `standardized_processing_runs` rows with status badges (pending/completed/failed), error messages, files_updated count, timestamps
3. **Auto-refresh** — polls every 10 seconds to show live status updates
4. **Row actions** — mark completed/failed, reset (delete) run, re-trigger

### Files to create/modify

| Action | File | Detail |
|---|---|---|
| Create | `src/pages/Backfill2.tsx` | New page: ticker input + trigger button + runs table with status/error display, polling via `refetchInterval: 10000` |
| Modify | `src/components/TopNavbar.tsx` | Add `{ label: 'Backfill2', to: '/backfill2' }` to navItems |
| Modify | `src/App.tsx` | Add `/backfill2` route wrapped in `ProtectedRoute` |

### Database change needed
The `standardized_processing_runs` table is missing an INSERT policy for authenticated users. The edge function inserts using the service role key so it works, but the UI needs SELECT (already exists) + DELETE (already exists) + UPDATE (already exists). No migration needed — the existing policies cover the UI's needs (it only reads, updates, and deletes).

### UI layout for Backfill2.tsx
- **Card 1: Trigger** — Input field for ticker, "Process" button that invokes `trigger-standardized-agent` edge function
- **Card 2: Summary stats** — Total / Completed / In Progress / Failed counts
- **Card 3: Runs table** — Columns: Ticker, Status, Files Updated, Started At, Completed At, Error, Actions (mark complete/failed/reset/re-trigger)

