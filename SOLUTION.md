# Solution Notes

**Duplicate-grant enforcement:** Partial unique index on `(grantee_id, document_id) WHERE revoked_at IS NULL` — handles concurrency at the DB level without application-layer locking.

**Expired vs revoked:** Both stored permanently per spec; `status` is a computed property, not a DB column, to avoid clock-skew drift.

**Revoke auth:** `requestor_id` passed as a query param on `DELETE`; a real system would use JWT claims instead.

**Concurrency:** The partial unique index makes concurrent duplicate-grant races fail with a DB constraint error (surfaced as 409). Advisory locks would add stronger ordering guarantees if needed.

**Tests:** SQLite in-memory for speed; schema prefixes stripped at fixture setup. Add `DATABASE_URL` env var pointing to real PG for true integration coverage.

**Tradeoff:** `GET /grants/summary` uses a left-join aggregate query — fine at seed scale, would need pagination or materialized view at large volume.
