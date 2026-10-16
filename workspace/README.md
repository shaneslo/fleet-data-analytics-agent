# workspace

Everything here except this file is git-ignored.

- `data/`: put exports here (Gainskeeper, Silver, Sedona CSVs from Aqua Data Studio).
  Save straight from the source system; opening and re-saving a CSV in Excel can
  strip leading zeros from account numbers and CUSIPs.
- `profile.json`: written by `python -m analyst.profile`.
- `runs/<date>_<question>/`: one folder per question, with the analysis tables,
  charts, `report.md` and `report.xlsx`.
- `sql/`: queries the agent drafted for you to run in Aqua Data Studio.
