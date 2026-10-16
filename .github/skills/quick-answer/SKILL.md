---
name: quick-answer
description: Answer short, ad hoc questions about the exports in workspace/data directly in chat, with follow-ups building on the last answer. Use for "how many", "which", "top N", "show me", "what's the total" questions; switch to the full report workflow only when asked to write it up.
---

# Quick answer

For a question that needs a number or a short list, not a report. Seconds, not
a write-up.

## Steps

1. **Profile only if needed**: `python -m analyst.profile --if-changed`. It
   reprints the stored summary instantly unless a file in `workspace/data/`
   changed. Use it for table and column names.
2. **Write or extend `workspace/scratch.py`** and run it with `python workspace/scratch.py`.
   Start a new question by overwriting the file; for a follow-up ("now only
   account X", "by month instead"), edit the existing script so it builds on
   what is already there.

```python
from analyst.io import load_all

t = {name: tbl.df for name, tbl in load_all("workspace").items()}
gk = t["gk_realized__realized"]

q3 = gk[gk["Trade Date"].between("2026-07-01", "2026-09-30")]
print("rows:", len(q3))
print("realized loss total:", round(q3.loc[q3["Gain/Loss"] < 0, "Gain/Loss"].sum(), 2))
print(q3.groupby("CUSIP")["Gain/Loss"].sum().nsmallest(10).round(2).to_string())
```

3. **Answer in the chat**: the number first, then one line on how it was
   computed (table, filter, date column), e.g.:

   > **$48,210.55** realized loss in Q3 across 212 lots (Gainskeeper realized,
   > trade date Jul 1–Sep 30). Top CUSIP: 594918104 at −$9,870.00.

## Rules

- **State only numbers your script printed in this session.** If you didn't
  compute it, don't say it. Round the way it was printed.
- **Rows go to Excel, not the chat.** If the answer is a list of records
  (lots, accounts, transactions), don't print them into the terminal. Save them
  and give the path:

```python
from analyst.xlsx import export
export(q3.nsmallest(50, "Gain/Loss"), "q3_largest_losses")
```

  Aggregates (counts, sums, top-N by security) are fine to print. Securities
  (CUSIP, ticker, security name) are fine to show; account numbers and personal
  details belong in the Excel file.
- **Say when a filter or assumption could change the answer**: which date
  column, whether dropped total rows matter, whether keys needed leading zeros
  stripped. One line, not a section.
- **Don't open a run folder or build a report** unless the user asks to write
  it up, save it, or send it. Then switch to the full workflow: open a run,
  move the scratch logic into `RUN/analysis.py`, save the tables, and continue
  from the analysis step (skills `analysis` and `reporting`).
- **If the question turns out not to be quick** (two sources disagree and
  the answer needs a reconciliation, or several steps of reasoning), say so in
  one line and offer the full workflow.
