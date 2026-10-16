---
name: sedona-sql
description: Draft read-only T-SQL for Sedona (the upstream ledger, SQL Server, queried in Aqua Data Studio) and hand it to the user to run and export. Use when the question needs ledger data that is not already in workspace/data.
---

# Sedona SQL

You never connect to Sedona. You write a query, check it, and the user runs
it in Aqua Data Studio and exports the result into `workspace/data/`.

## Before writing

Read `context/sedona/schema.md` (tables, columns, keys, gotchas) and look in
`context/sedona/queries/` for a trusted query that already does most of the
job. Prefer adapting a trusted query to writing from scratch. If the schema
file does not cover the tables you need, ask the user rather than guessing
table or column names.

## Writing

Save to `workspace/sql/<short_name>.sql`:

```sql
-- Purpose: Q3 tax lots for reconciliation against Gainskeeper
-- Export as: workspace/data/sedona_q3_lots.csv
-- Expected columns: account_no, cusip, lot_id, open_date, quantity, cost_basis
DECLARE @start date = '2026-07-01';
DECLARE @end   date = '2026-09-30';

SELECT
    CAST(l.account_no AS varchar(20)) AS account_no,
    l.cusip,
    l.lot_id,
    l.open_date,
    l.quantity,
    l.cost_basis
FROM dbo.tax_lots AS l
WHERE l.open_date BETWEEN @start AND @end
ORDER BY l.account_no, l.cusip, l.lot_id;
```

- T-SQL (SQL Server). Parameters as `DECLARE`s at the top.
- Read only: `SELECT`, CTEs, and `SELECT ... INTO #temp` are fine. Nothing that
  writes, creates, executes procedures or dynamic SQL, or reaches linked servers.
- List columns explicitly and alias them in `snake_case`; the aliases become
  the export's headers. Cast identifiers to `varchar` so exports keep leading zeros.
- Always filter (date range, accounts) or `TOP`. Add `ORDER BY` so exports are stable.
- No `NOLOCK` unless the user says their team uses it: dirty reads can make
  ledger totals not tie.

## Check, then hand off

```
python -m analyst.sqlcheck workspace/sql/<short_name>.sql
```

Fix every ERROR. Then tell the user:

1. the file to open in Aqua Data Studio and the parameters to confirm;
2. to export the result grid **directly to CSV** at
   `workspace/data/sedona_<short_name>.csv`, without opening and re-saving
   it in Excel (Excel strips leading zeros and turns long numbers into
   scientific notation);
3. that you will re-profile once the file is there.

When a query proves useful, suggest the user save it to
`context/sedona/queries/` so it becomes a trusted starting point.
