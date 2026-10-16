---
name: reporting
description: Write findings.json for a run and build report.md and report.xlsx, with every figure checked against the saved tables. Use as the last step of every question.
---

# Reporting

1. Write `RUN/findings.json`:

```json
{
  "title": "Gainskeeper vs Silver, Q3: 14 breaks, $12,400 net",
  "answer": "Two to four sentences that answer the question directly.",
  "findings": [
    {
      "headline": "One sentence with the figure",
      "detail": "What it means and how it was computed.",
      "table": "analysis/breaks_gk_vs_silver_summary.csv",
      "chart": "charts/breaks_by_type.png"
    }
  ],
  "caveats": ["Data limits, assumptions, dropped rows, warnings that matter."],
  "next_steps": ["Concrete follow-ups, e.g. which Sedona query would settle it."]
}
```

`table` and `chart` are optional, but every path you give must exist in the
run folder. Order findings by importance.

2. Build:

```
python -m analyst.report --run RUN
```

This writes `RUN/report.md` (charts embedded, first 20 rows of each table,
data sources and warnings) and `RUN/report.xlsx` (a Summary sheet, a Data used
sheet, and every analysis table in full, with identifiers kept as text).

3. **Fix every `WARN unverified figure`.** The check looks for each number in
your answer, headlines and details in the saved tables and the profile,
allowing for the rounding you show (`$1.3K`, `75%` from `0.75`). Small counts
(12 or less), years, dates and zero-padded identifiers are skipped. When a
figure is flagged, either correct it or save the table it came from, then
rebuild. Don't reword the figure to get around the check.

## Writing

- Lead with the answer, in the business's terms: accounts, positions,
  dollars, dates.
- Give absolute and relative figures together ("$12,400, 0.3% of cost basis").
- Separate what the data shows from what you infer.
- Put dropped rows and data warnings in caveats when they could change the answer.
