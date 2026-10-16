# Sedona schema notes

Only the tables you actually query. Paste column lists from Aqua Data Studio
(the table's Columns tab, or `sp_help 'dbo.table_name'`, which you run
yourself, not the agent). Note anything a newcomer would get wrong.

No data values here: this file is committed.

## Server

| | |
|---|---|
| Engine | Microsoft SQL Server (T-SQL) |
| Database(s) | TODO |
| Default schema | TODO (usually `dbo`) |

## Tables

### TODO_schema.TODO_table

Grain: TODO (one row per ...).

| Column | Type | Meaning | Notes |
|---|---|---|---|
| TODO | | | |

Joins: TODO (e.g. `account_no` to `dbo.accounts.account_no`).

Gotchas: TODO (soft-deleted rows, reversal entries, effective-dated rows, which status codes to exclude).
