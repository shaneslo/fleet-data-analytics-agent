---
name: data-explorer
description: Profile the CSV and Excel exports in workspace/data before any analysis. Use first on every question, and again whenever files in workspace/data change.
---

# Data explorer

```
python -m analyst.profile
```

Loads every `.csv`, `.tsv`, `.txt`, `.xlsx`, `.xlsm` (and `.xls` if `xlrd` is
installed) in `workspace/data/`, one table per non-empty sheet, and writes
`workspace/profile.json`. Read the printed summary; open the JSON only for
detail.

## What the loader already handled

- **Banner rows**: the header row is detected; rows above it are skipped.
- **Junk rows**: total/subtotal rows, repeated page headers and footer lines
  are dropped and listed under `dropped_rows` with the reason and source row.
- **Identifiers stay text**: account, CUSIP, lot, ID and code columns, and any
  all-digit column with leading zeros, are never parsed as numbers. In `.xlsx`
  files, cells with a zero-padded number format get their zeros back; legacy
  `.xls` files can't, and the profile warns when that may matter.
- **Numbers**: `1,234.56`, `(1,234.56)`, `$1,234`, `1234.56-` and `12.5%`
  parse (percent signs are stripped, not divided out).
- **Encodings and delimiters**: UTF-8 or Windows-1252; comma, semicolon, tab or pipe.

## Read the summary for

- **Table names** (`<file>` or `<file>__<sheet>`): use these in code.
- **Column kinds**: `identifier`, `numeric`, `datetime`, `text`. `*` means
  values are masked in the profile.
- **Dropped rows**: if a total row was dropped that you needed, or a data row
  was dropped as a total, say so and load the file yourself.
- **WARN lines**: scientific-notation identifiers (digits lost in Excel),
  CUSIPs not 9 characters, identifiers that differ only by leading zeros. These
  break joins; mention them in caveats.
- **Join candidates**: identifier columns whose values overlap across tables,
  even when the names differ (`Account` vs `AcctNo`). A low overlap that rises
  "ignoring leading zeros" means use `strip_leading_zeros=True` when reconciling.

## Rules

- The profile masks account and personal values on purpose. Do not work around
  it by printing raw rows. `--no-mask` exists for the user, not for you.
- If `workspace/data/` is empty, say so and stop. If the user needs Sedona data,
  offer the `sedona-sql` skill.
