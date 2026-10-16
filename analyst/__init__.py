"""Local data-analysis toolkit driven by GitHub Copilot in VS Code.

Modules (each runs as `python -m analyst.<name>`):
    profile    profile every file in workspace/data -> workspace/profile.json
    run        create a run folder for a question
    reconcile  compare two tables on a key and list the breaks
    chart      render a PNG from a result table
    report     build report.md and report.xlsx from a run folder
    sqlcheck   confirm a T-SQL file only reads

From analysis scripts: `from analyst.io import load_all, load_table`.
"""

__version__ = "0.1.0"
