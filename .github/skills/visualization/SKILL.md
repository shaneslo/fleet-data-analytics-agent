---
name: visualization
description: Render a PNG chart from a saved result table in a run folder. Use for the key findings that a chart makes clearer than a table.
---

# Visualization

```
python -m analyst.chart --run RUN --data analysis/breaks_summary.csv --type barh --x break_type --y breaks --title "Breaks by type" --output charts/breaks_by_type.png
```

| Argument | Notes |
|---|---|
| `--run` | the run folder |
| `--data` | CSV relative to the run folder, usually `analysis/<name>.csv` |
| `--type` | `bar`, `barh`, `line`, `scatter`, `pie`, `heatmap` |
| `--x`, `--y` | columns; `--y` may list several for `line` |
| `--top N` | keep the top N rows by the first `--y` |
| `--title`, `--xlabel`, `--ylabel` | short and plain |
| `--output` | `charts/<name>.png`, relative to the run folder |

## Choosing

- **barh**: comparing categories, especially with long labels (break types,
  accounts, securities). The default choice.
- **line**: a measure over time; x is a date column.
- **bar**: a few short categories, or periods.
- **scatter**: two numeric measures (left value vs right value).
- **heatmap**: a pivot; the CSV's first column is the row label.
- **pie**: only with six or fewer parts of one whole. Usually use `barh` instead.

One idea per chart, two or three charts per question at most. If a chart
fails, continue: a missing chart never blocks the report.
