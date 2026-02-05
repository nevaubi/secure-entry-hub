

## Clean Up Corrupted Database Records

I'll delete the 2 corrupted records from the `companies` table that were created due to multi-line text parsing issues.

---

### Records to Delete

| Ticker (corrupted) | company_id | Issue |
|-------------------|------------|-------|
| `Direct-to-Consumer` | 0 | Fragment from PSKY description |
| `it produces and acquires films` | 0 | Fragment from PSKY description |

Both records have `company_id = 0` and contain text fragments that should have been part of a description field.

---

### Implementation

1. **Delete corrupted records** using a database migration with a DELETE statement targeting records where `company_id = 0`

---

### Technical Details

```text
DELETE FROM companies WHERE company_id = 0;
```

This will remove exactly 2 rows, leaving 3,120 valid company records in the database.

---

### Files to Modify

| File | Change |
|------|--------|
| Database Migration | DELETE statement to remove corrupted records |

