# fleet-data-analytics-agent

A local data analyst for GitHub Copilot in VS Code. Point it at Excel/CSV
exports (Gainskeeper, Silver) and Sedona query results, ask a question, and it
profiles the data, runs the analysis in Python on your machine, and writes a
Markdown and Excel report in which every figure is checked against a saved table.

Nothing here calls an outside API. Copilot is the only model involved;
the data stays in `workspace/` on your machine, and the agent sees profiles,
aggregates and masked samples rather than raw account-level rows.

## Setup (Windows, PowerShell)

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest -q      # should pass
```

Optional extras: `".[xls]"` to read legacy `.xls` files, `".[ml]"` for
scikit-learn. On macOS/Linux use `python3 -m venv .venv` and `.venv/bin/python`.

In VS Code, select `.venv` as the Python interpreter, open Copilot Chat in
**Agent** mode, and pick the **data-analyst** agent.

## Use

1. Put exports in `workspace/data/`. Save them straight from the source system;
   re-saving a CSV in Excel can strip leading zeros from account numbers and CUSIPs.
2. In Copilot Chat:
   - **Quick questions**: `/ask` or just ask ("how many accounts hold
     594918104?", "top 10 realized losses in Q3"). The answer comes back in
     chat; follow-ups build on it, and lists of rows land in
     `workspace/exports/*.xlsx`. Say "write this up" to turn it into a report.
   - **Reports**: `/analyze` and the question. Read
     `workspace/runs/<date>_<question>/report.md` (or `report.xlsx`).

For ledger data, run `/sedona-query`. The agent writes a read-only T-SQL file
to `workspace/sql/`, checks it, and tells you what to run in Aqua Data Studio
and where to save the export. It never connects to Sedona itself.

## Teach it your data

The agent is only as good as `context/`:

- `context/sources.md`: what Gainskeeper, Silver and Sedona columns mean, how
  each system keys and dates records, which one wins when they disagree.
- `context/sedona/schema.md`: the Sedona tables and columns you actually use.
- `context/sedona/queries/`: queries you trust. CI checks they are read-only.

These files are committed, so describe columns and rules; never paste real
account numbers, client names or balances.

## What is where

| Path | |
|---|---|
| `.github/copilot-instructions.md` | workflow and ground rules Copilot follows in this repo |
| `.github/agents/data-analyst.agent.md` | the custom agent |
| `.github/prompts/` | `/ask`, `/analyze`, `/sedona-query` |
| `.github/skills/` | quick-answer, data-explorer, analysis, visualization, reporting, sedona-sql |
| `analyst/` | the Python tooling the skills call (`python -m analyst.<module>`) |
| `context/` | your knowledge of the sources |
| `workspace/` | data and outputs (git-ignored) |

### The tooling

| Command | Does |
|---|---|
| `python -m analyst.profile [--if-changed]` | loads every export (header detection, total/footer rows dropped, identifiers kept as text, `(1,234.56)` negatives) and writes `workspace/profile.json` with masked samples and join candidates |
| `python -m analyst.run new "<question>"` | creates a run folder |
| `python -m analyst.reconcile ...` | compares two tables on a key; writes every break and a summary |
| `python -m analyst.chart ...` | renders a PNG from a result table |
| `python -m analyst.report --run RUN` | builds `report.md` and `report.xlsx`; flags figures it cannot find in the saved tables |
| `python -m analyst.sqlcheck file.sql` | fails on anything in a query that is not read-only |
| `analyst.xlsx.export(df, name)` | (from Python) saves rows to `workspace/exports/` with identifiers kept as text |

## Before using real data

Confirm that your company's Copilot policy covers this data. Masking keeps raw
account and personal values out of the profile, but the agent writes and runs
code against the full data, and anything it prints is sent to Copilot.

## Origin

Started from Google AI Studio's "AI Data Analyst" sample (Gemini Managed
Agents). The pipeline shape (profile → analysis tables → charts → report)
and the chart script come from it (`analyst/chart.py` keeps its Apache-2.0
header). The Gemini web app itself was removed; it is in git history before
this change if it is ever needed.
