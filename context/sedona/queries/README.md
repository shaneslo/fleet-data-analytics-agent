# Trusted Sedona queries

Queries you have run and trust. The agent starts from these before writing new
SQL. One query per `.sql` file, with the header the `sedona-sql` skill uses:

```sql
-- Purpose: ...
-- Export as: workspace/data/sedona_<name>.csv
-- Expected columns: ...
```

Check a query before saving it here: `python -m analyst.sqlcheck context/sedona/queries/<name>.sql`.
CI runs the same check on every file in this folder.
