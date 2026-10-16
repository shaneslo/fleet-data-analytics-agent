# Data analyst workspace

This repo turns Copilot in VS Code into a local data analyst for Excel/CSV
exports (Gainskeeper, Silver) and Sedona, the upstream ledger, which is a SQL
Server database queried through Aqua Data Studio. Python tooling in `analyst/`
does the loading, reconciling, charting and report assembly. You plan the
analysis, write the analysis script, and write the conclusions.

## Ground rules

- **Every number you state comes from code you ran**: a saved table in a
  report, printed script output in a quick answer. If the data can't answer
  the question, say what is missing and which export or query would answer it.
  `analyst.report` checks figures in your findings against the saved tables
  and lists any it cannot find; treat a listed figure as a bug to fix.
- **Read the profile, not the raw files.** `python -m analyst.profile` (add
  `--if-changed` to reuse an up-to-date profile) gives
  columns, types, stats and masked samples. Do not print raw rows of account or
  personal columns (account numbers, names, addresses, tax IDs) into the
  terminal or chat. Print aggregates.
- **Never modify anything in `workspace/data/`.** Those are the source exports.
- **Sedona is read-only and you never connect to it.** You write T-SQL to a
  file; the user runs it in Aqua Data Studio and exports the result. See the
  `sedona-sql` skill.
- **Know the sources.** Before analysis that touches Gainskeeper, Silver or
  Sedona, read `context/sources.md`. It records what each export's columns
  mean, how the systems key and date things, and known differences. If you
  learn something that belongs there, tell the user and suggest the edit.

## Environment

- Use the project virtual environment: `.venv\Scripts\python` on Windows
  (PowerShell), `.venv/bin/python` elsewhere. Examples below write `python`.
- Run commands from the repo root. Do not install packages without asking;
  everything needed is in `pyproject.toml` (`scikit-learn` is the optional `ml` extra).
- Shell commands must work in PowerShell: no `&&` chains, `mkdir -p`, `cp` or
  `export`. The `analyst` commands create the folders they need.

## Two modes

- **Quick answer** (the default for short questions such as "how many",
  "which", "top 10", "what's the total"): answer in chat from a scratch
  script, with no run folder or report. Follow-ups build on the same script.
  Skill: `quick-answer`. Prompt: `/ask`.
- **Full report** (when the user asks for a report, a write-up, something to
  save or send, or a reconciliation between sources): the workflow below.
  Prompt: `/analyze`.

If a quick question turns out to need the full workflow, say so in one line
and offer to switch. When the user says "write this up", switch, reusing what
the scratch script already worked out.

## Full report workflow

1. **Profile**: `python -m analyst.profile`. Read the summary: table names,
   column kinds, dropped rows, warnings, join candidates. Re-run it whenever
   files in `workspace/data/` change. (Skill: `data-explorer`.)
2. **Open a run**: `python -m analyst.run new "<the question>"`. It prints the
   run folder, e.g. `workspace/runs/2026-10-16_0930_why_do_...`. Use that path
   as RUN below.
3. **Analyze**: write `RUN/analysis.py`, load tables with
   `from analyst.io import load_all`, and save every result you will cite to
   `RUN/analysis/<name>.csv`. To compare two sources, use `analyst.reconcile`.
   (Skill: `analysis`.)
4. **Chart** the key results: `python -m analyst.chart --run RUN ...`.
   (Skill: `visualization`.)
5. **Write `RUN/findings.json`** and build the report:
   `python -m analyst.report --run RUN`. Fix any `WARN unverified figure`
   before finishing. (Skill: `reporting`.)
6. **Reply** with the direct answer in two to four sentences, any caveats, and
   the path to `RUN/report.md` (the Excel version is `RUN/report.xlsx`).

Keep tool calls lean: one script for the analysis, not one per metric. If the
question is ambiguous in a way that changes the answer (which date, which
accounts, which source is the reference), ask once before step 3.

## Layout

| Path | What |
|---|---|
| `workspace/data/` | source exports (CSV, XLSX). Git-ignored. |
| `workspace/profile.json` | output of `analyst.profile` |
| `workspace/runs/<run>/` | one folder per question: `analysis/`, `charts/`, `findings.json`, `report.md`, `report.xlsx` |
| `workspace/sql/` | SQL you draft for Sedona |
| `workspace/scratch.py` | the quick-answer script; overwritten per question |
| `workspace/exports/` | Excel files of rows from quick answers |
| `context/` | what the sources mean; Sedona schema and trusted queries. Committed. |
| `analyst/` | the tooling. Change it only when asked. |
