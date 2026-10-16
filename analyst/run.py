"""Create or find a run folder. Each question gets its own folder, so earlier
answers stay on disk next to the files that produced them.

    python -m analyst.run new "Why doesn't Gainskeeper cost basis match Silver for Q3?"
    python -m analyst.run latest

A run folder holds: question.txt, analysis/ (result tables), charts/,
findings.json (written by the agent), report.md and report.xlsx.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from analyst.io import slug


def new_run(question: str, workspace: str | Path = "workspace") -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    base = Path(workspace) / "runs" / f"{stamp}_{slug(question)[:40].strip('_')}"
    run, n = base, 1
    while run.exists():
        n += 1
        run = base.with_name(f"{base.name}_{n}")
    (run / "analysis").mkdir(parents=True)
    (run / "charts").mkdir()
    (run / "question.txt").write_text(question.strip() + "\n", encoding="utf-8")
    return run


def latest_run(workspace: str | Path = "workspace") -> Path | None:
    runs = Path(workspace) / "runs"
    folders = sorted((p for p in runs.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime) if runs.is_dir() else []
    return folders[-1] if folders else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or find a run folder")
    parser.add_argument("--workspace", default="workspace")
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new", help="create a run folder for a question")
    new.add_argument("question")
    sub.add_parser("latest", help="print the most recent run folder")
    args = parser.parse_args(argv)

    if args.command == "new":
        print(new_run(args.question, args.workspace).as_posix())
        return 0
    run = latest_run(args.workspace)
    if run is None:
        print("No runs yet.")
        return 1
    print(run.as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
