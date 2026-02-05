

## Create Companies Table with 3,200+ Stock Tickers

I'll create a `companies` table in your backend database that matches your CSV schema exactly, using the ticker as the primary identifier.

---

### Database Schema

| Column | Type | Constraints |
|--------|------|-------------|
| `ticker` | `TEXT` | **PRIMARY KEY** |
| `company_id` | `INTEGER` | NOT NULL |
| `name` | `TEXT` | NOT NULL |
| `cik` | `INTEGER` | (SEC identifier) |
| `exchange` | `TEXT` | (NYSE, Nasdaq, etc.) |
| `sector` | `TEXT` | (Industry sector) |
| `description` | `TEXT` | (Company description) |
| `year_founded` | `INTEGER` | |
| `logo_url` | `TEXT` | |
| `created_at` | `TIMESTAMPTZ` | DEFAULT now() |

---

### Data Import Strategy

Since we have ~3,200 rows, the most reliable approach is:

1. **Create the table structure** using a database migration
2. **Batch insert the data** using SQL INSERT statements (I'll split into manageable chunks of ~100-200 rows each to avoid timeouts)

---

### Security

- **Row Level Security (RLS)** will be enabled with a policy allowing only authenticated users (you) to read the data
- No public access to this table

---

### Implementation Steps

1. Create the `companies` table with the schema above
2. Enable RLS with a read policy for authenticated users
3. Insert all 3,124 company records in batches
4. Update the TypeScript types automatically

---

### Files to Create/Modify

| Action | Description |
|--------|-------------|
| Database Migration | Create `companies` table with proper schema and RLS |
| Data Insert | Batch insert all 3,124 rows from your CSV |
| Types (auto) | TypeScript types will auto-update |

---

### Technical Details

```text
┌─────────────────────────────────────────────────────────┐
│                    companies table                       │
├─────────────────────────────────────────────────────────┤
│ ticker (PK)    │ TEXT    │ e.g., "NVDA", "AAPL"        │
│ company_id     │ INTEGER │ Original ID from CSV         │
│ name           │ TEXT    │ Full company name            │
│ cik            │ INTEGER │ SEC Central Index Key        │
│ exchange       │ TEXT    │ NYSE, Nasdaq, NASDAQ         │
│ sector         │ TEXT    │ Industry sector              │
│ description    │ TEXT    │ Company business description │
│ year_founded   │ INTEGER │ e.g., 1993, 1976             │
│ logo_url       │ TEXT    │ URL to company logo          │
│ created_at     │ TIMESTAMP│ Auto-generated              │
└─────────────────────────────────────────────────────────┘
```

**RLS Policy:**
- `SELECT` allowed for authenticated users only
- No `INSERT`, `UPDATE`, or `DELETE` from client (you can manage via backend tools if needed)

