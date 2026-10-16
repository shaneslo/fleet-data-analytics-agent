---
description: Draft a read-only T-SQL query for Sedona to run in Aqua Data Studio
agent: data-analyst
---

What I need from Sedona: ${input:need:Which records, fields and date range?}

Use the `sedona-sql` skill. Write the query to `workspace/sql/`, run
`python -m analyst.sqlcheck` on it, and tell me exactly what to export and
where to save it.
