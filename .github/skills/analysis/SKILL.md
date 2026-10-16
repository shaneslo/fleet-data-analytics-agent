---
name: analysis
description: Write and run the pandas analysis for a question, including reconciling two sources (Gainskeeper, Silver, Sedona exports). Use after profiling, inside a run folder.
---

# Analysis

Write one script, `RUN/analysis.py`, that computes everything the answer needs
and saves each result table you will cite to `RUN/analysis/<name>.csv`.

```python
from pathlib import Path

import pandas as pd

from analyst.io import load_all

RUN = Path("workspace/runs/<run folder>")
tables = {name: t.df for name, t in load_all("workspace").items()}
gk = tables["gk_realized__realized"]  # names come from the profile summary

# ... compute ...
result.to_csv(RUN / "analysis" / "cost_basis_by_account.csv", index=False)
print(result.head(20).to_string())  # aggregates only
```

Run it with `python RUN/analysis.py`. If it fails, read the traceback, fix the
script, run it again.

## Loading

- `load_all("workspace")` returns every table already cleaned and typed (see
  the `data-explorer` skill). Do not re-read source files with `pd.read_csv` or
  `pd.read_excel`: you would lose the identifier handling.
- `analyst.io.load_table(path, sheet=None)` loads a single file, e.g. a CSV you
  saved earlier in the run.

## Reconciling two sources

Use `analyst.reconcile` rather than hand-written merges. From the command line:

```
python -m analyst.reconcile --run RUN --left gk_realized__realized --right silver_positions --keys "Account=AcctNo,CUSIP" --compare "Quantity=Shares,Cost Basis=Cost"
```

or from Python:

```python
from analyst.reconcile import reconcile, summarize
breaks = reconcile(gk, silver, keys=[("Account", "AcctNo"), ("CUSIP", "CUSIP")],
                   compare=[("Quantity", "Shares"), ("Cost Basis", "Cost")],
                   left_name="gk", right_name="silver", tolerance=0.01)
```

- `--keys` / `--compare` take `left=right` pairs, or one name when both sides match.
- `--aggregate` (`aggregate=True`) sums numeric columns per key first: use it
  when one side is lots and the other is positions. Without it, keys that repeat
  are reported as `duplicate_key_in_<side>` and left out of the comparison on
  both sides.
- Rows with a blank key column are reported as `incomplete_key_in_<side>`,
  never dropped silently. Count them in the findings.
- `--strip-leading-zeros` when the profile showed the overlap rises once
  leading zeros are ignored.
- `--tolerance` is absolute (default 0.01). Pick it to match the precision of
  the field: share quantities, currency, and prices differ.
- Output: `RUN/analysis/breaks_<left>_vs_<right>.csv` (one row per break) and
  `..._summary.csv` (count and net difference by break type and column).

Then explain the breaks: group them by likely cause, quantify each group, and
look for patterns (one account, one security, one date, one transaction type).
Check `context/sources.md` for known differences between systems before
calling something an error.

## Other patterns

- Filter to the period the question asks about, and state the date column used
  (trade vs settle vs as-of) in the findings.
- Time series: `df.set_index(date_col).resample("ME")[value].sum()`.
- Top-N: sort, then `.head(n)`; save the full table and let the report trim it.
- Modelling (forecasts, clustering) only if the question asks for it; it needs
  the optional `ml` extra, so ask before installing.

## Rules

- Every figure you will state must be in a saved CSV. Save the small summary
  tables as well as the detail.
- Print aggregates, counts and shapes. Do not print raw rows that contain
  account numbers or personal data.
- State how you handled missing values, duplicates and dropped rows.
