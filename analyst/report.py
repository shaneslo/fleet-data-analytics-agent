"""Assemble a run folder into report.md and report.xlsx.

    python -m analyst.report --run RUN [--strict]

Reads <run>/findings.json (written by the agent; schema below), every CSV in
<run>/analysis/, the PNGs in <run>/charts/, and workspace/profile.json.

findings.json:
    {
      "title": "short title",
      "answer": "2-4 sentences that answer the question directly",
      "findings": [
        {"headline": "...", "detail": "...",
         "table": "analysis/<name>.csv",   # optional
         "chart": "charts/<name>.png"}     # optional
      ],
      "caveats": ["..."],
      "next_steps": ["..."]
    }

Grounding check: every figure written in the answer, headlines and details
must appear in an analysis table or the data profile (allowing for the
rounding shown). Figures that don't are listed under "Unverified figures" in
the report; with --strict the command fails instead.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from analyst.io import LoadedTable, load_file, numeric_values, slug
from analyst.xlsx import append_row, write_table

MD_TABLE_ROWS = 20

_DATE_TEXT_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")
_CODE_RE = re.compile(r"`[^`]*`")
_FIGURE_RE = re.compile(
    r"(?<![\w.])\(?[-−]?\$?"
    r"(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?P<dec>\.\d+)?\)?"
    r"\s?(?P<unit>%|percent\b|bn\b|billion\b|million\b|thousand\b|[kKmMbB]\b)?"
)
_MULTIPLIERS = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "bn": 1e9, "billion": 1e9}


class FindingsError(ValueError):
    pass


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------

def load_findings(run: Path) -> dict | None:
    path = run / "findings.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FindingsError(f"findings.json is not valid JSON: {exc}") from exc
    problems = []
    for key in ("title", "answer", "findings"):
        if not data.get(key):
            problems.append(f"missing '{key}'")
    for i, f in enumerate(data.get("findings") or [], 1):
        if not isinstance(f, dict) or not f.get("headline"):
            problems.append(f"finding {i} has no 'headline'")
            continue
        for ref in ("table", "chart"):
            if f.get(ref) and not (run / f[ref]).exists():
                problems.append(f"finding {i}: {ref} '{f[ref]}' does not exist in the run folder")
    if problems:
        raise FindingsError("findings.json: " + "; ".join(problems))
    data.setdefault("caveats", [])
    data.setdefault("next_steps", [])
    return data


def load_analysis(run: Path) -> dict[str, LoadedTable]:
    tables = {}
    for path in sorted((run / "analysis").glob("*.csv")):
        loaded = load_file(path, clean=False)
        if loaded:
            tables[f"analysis/{path.name}"] = loaded[0]
    return tables


def load_profile(workspace: Path) -> dict | None:
    path = workspace / "profile.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# --------------------------------------------------------------------------
# Grounding check
# --------------------------------------------------------------------------

def known_values(tables: dict[str, LoadedTable], profile: dict | None) -> tuple[np.ndarray, set[str]]:
    """Numbers a figure may legitimately come from, and identifier strings to ignore."""
    chunks = [numeric_values(t.df) for t in tables.values()]
    counts = [len(t.df) for t in tables.values()]
    identifiers: set[str] = set()
    for t in tables.values():
        for col, kind in t.column_kinds.items():
            if kind == "identifier":
                identifiers.update(t.df[col].dropna().astype(str))
    if profile:
        for t in profile.get("tables", []):
            counts += [t.get("rows", 0), t.get("duplicate_rows", 0), len(t.get("dropped_rows", []))]
            for c in t.get("columns", []):
                counts += [c.get("missing", 0), c.get("distinct", 0)]
                for k, v in (c.get("stats") or {}).items():
                    if isinstance(v, (int, float)):
                        chunks.append(np.array([v], dtype=float))
                    elif isinstance(v, dict) and k == "top_values":
                        counts += list(v.values())
    chunks.append(np.array(counts, dtype=float))
    values = np.abs(np.concatenate(chunks)) if chunks else np.array([], dtype=float)
    return values[np.isfinite(values)], identifiers


def extract_figures(text: str) -> list[dict]:
    text = _CODE_RE.sub(" ", _DATE_TEXT_RE.sub(" ", text))
    figures = []
    for m in _FIGURE_RE.finditer(text):
        whole, dec = m.group("int"), m.group("dec") or ""
        unit = (m.group("unit") or "").lower()
        raw = m.group(0).strip()
        if whole.startswith("0") and len(whole) > 1 and not dec:
            continue  # zero-padded: an identifier, not a quantity
        number = float(whole.replace(",", "") + dec)
        if not unit and not dec and "," not in whole and (number <= 12 or 1900 <= number <= 2100):
            continue  # small counts and years are not worth checking
        figures.append({
            "text": raw, "number": number, "decimals": len(dec) - 1 if dec else 0,
            "percent": unit in ("%", "percent"), "multiplier": _MULTIPLIERS.get(unit, 1.0),
        })
    return figures


def is_grounded(figure: dict, values: np.ndarray, identifiers: set[str]) -> bool:
    if figure["text"].strip("()$-−%") in identifiers:
        return True
    if values.size == 0:
        return False
    m = figure["multiplier"]
    target = figure["number"] * m
    tol = 0.5 * 10 ** (-figure["decimals"]) * m + 1e-9
    if m > 1:
        tol = max(tol, abs(target) * 0.005)
    candidates = [values]
    if figure["percent"]:
        candidates.append(values * 100)
    return any(bool(np.any(np.abs(c - target) <= tol)) for c in candidates)


def unverified_figures(findings: dict, values: np.ndarray, identifiers: set[str]) -> list[dict]:
    texts = [("answer", findings.get("answer", ""))]
    for i, f in enumerate(findings.get("findings", []), 1):
        texts.append((f"finding {i}", f"{f.get('headline', '')} {f.get('detail', '')}"))
    out = []
    for where, text in texts:
        for fig in extract_figures(text):
            if not is_grounded(fig, values, identifiers):
                out.append({"where": where, "figure": fig["text"]})
    return out


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def _fmt(value) -> str:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat() if value == value.normalize() else str(value)
    if isinstance(value, (float, np.floating)):
        return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"
    if isinstance(value, (int, np.integer)):
        return f"{value:,}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown_table(df: pd.DataFrame, limit: int = MD_TABLE_ROWS) -> str:
    head = df.head(limit)
    lines = ["| " + " | ".join(_fmt(c) for c in head.columns) + " |",
             "|" + "|".join("---" for _ in head.columns) + "|"]
    for row in head.itertuples(index=False):
        lines.append("| " + " | ".join(_fmt(v) for v in row) + " |")
    return "\n".join(lines)


def _sheet_names(paths: list[str]) -> dict[str, str]:
    names, used = {}, {"summary", "data used"}
    for p in paths:
        base = slug(Path(p).stem)[:28] or "table"
        name, n = base, 1
        while name.lower() in used:
            n += 1
            name = f"{base[:26]}_{n}"
        used.add(name.lower())
        names[p] = name
    return names


def render_markdown(run, question, findings, tables, profile, unverified, sheets) -> str:
    title = findings["title"] if findings else f"Analysis tables: {question}"
    out = [f"# {title}", "", f"**Question:** {question}", "",
           f"*Generated {datetime.now():%Y-%m-%d %H:%M} · run `{run.name}` · full tables in `report.xlsx`*", ""]
    if not findings:
        out += ["> **No findings.json in this run.** This report lists the analysis tables only; "
                "nobody has written the narrative yet.", ""]
    else:
        out += ["## Answer", "", findings["answer"], "", "## Findings", ""]
        for i, f in enumerate(findings["findings"], 1):
            out += [f"### {i}. {f['headline']}", ""]
            if f.get("detail"):
                out += [f["detail"], ""]
            if f.get("chart"):
                out += [f"![{f['headline']}]({Path(f['chart']).as_posix()})", ""]
            if f.get("table") and f["table"] in tables:
                df = tables[f["table"]].df
                out += [markdown_table(df), ""]
                more = f" (first {MD_TABLE_ROWS} of {len(df):,} rows)" if len(df) > MD_TABLE_ROWS else ""
                out += [f"*Source: `{f['table']}`{more}; sheet `{sheets[f['table']]}` in report.xlsx.*", ""]
        if findings["caveats"]:
            out += ["## Caveats", ""] + [f"- {c}" for c in findings["caveats"]] + [""]
        if findings["next_steps"]:
            out += ["## Next steps", ""] + [f"- {s}" for s in findings["next_steps"]] + [""]

    referenced = {f.get("table") for f in (findings or {}).get("findings", [])}
    others = [p for p in tables if p not in referenced]
    if others:
        out += ["## Other analysis tables", ""]
        for p in others:
            df = tables[p].df
            out += [f"### `{p}` ({len(df):,} rows)", "", markdown_table(df), ""]

    if profile:
        out += ["## Data used", "", "| table | source | rows | dropped rows | warnings |", "|---|---|---|---|---|"]
        for t in profile.get("tables", []):
            src = t["source"] + (f" [{t['sheet']}]" if t.get("sheet") else "")
            out.append(f"| {t['name']} | {src} | {t['rows']:,} | {len(t['dropped_rows'])} | {len(t['warnings'])} |")
        out.append("")
        warned = [(t["name"], w) for t in profile.get("tables", []) for w in t["warnings"]]
        if warned:
            out += ["Data warnings:", ""] + [f"- **{n}:** {w}" for n, w in warned] + [""]

    if unverified:
        out += ["## Unverified figures", "",
                "These figures appear in the text but were not found in any analysis table or the data profile. "
                "Check them before relying on this report.", ""]
        out += [f"- {u['where']}: **{u['figure']}**" for u in unverified] + [""]
    return "\n".join(out)


def write_excel(path: Path, question, findings, tables, profile, unverified, sheets) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    bold = Font(bold=True)
    rows = [("Question", question)]
    if findings:
        rows += [("Title", findings["title"]), ("Answer", findings["answer"])]
        rows += [(f"Finding {i}", f"{f['headline']}. {f.get('detail', '')}".strip())
                 for i, f in enumerate(findings["findings"], 1)]
        rows += [("Caveat", c) for c in findings["caveats"]]
        rows += [("Next step", s) for s in findings["next_steps"]]
    else:
        rows.append(("Note", "No findings.json in this run; tables only."))
    rows += [("Unverified figure", f"{u['where']}: {u['figure']}") for u in unverified]
    for label, text in rows:
        append_row(ws, [label, text])
        ws.cell(ws.max_row, 1).font = bold
        ws.cell(ws.max_row, 2).alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 110

    if profile:
        du = wb.create_sheet("Data used")
        du.append(["table", "source", "sheet", "rows", "dropped rows", "warnings"])
        for t in profile.get("tables", []):
            append_row(du, [t["name"], t["source"], t.get("sheet"), t["rows"],
                                   len(t["dropped_rows"]), "; ".join(t["warnings"])])
        for cell in du[1]:
            cell.font = bold

    for p, table in tables.items():
        write_table(wb.create_sheet(sheets[p]), table.df, table.column_kinds)
    wb.save(path)


def build(run: Path, workspace: Path, strict: bool = False) -> tuple[int, list[dict]]:
    question_file = run / "question.txt"
    question = question_file.read_text(encoding="utf-8").strip() if question_file.exists() else "(question not recorded)"
    findings = load_findings(run)
    tables = load_analysis(run)
    profile = load_profile(workspace)
    unverified: list[dict] = []
    if findings:
        values, identifiers = known_values(tables, profile)
        unverified = unverified_figures(findings, values, identifiers)
    if strict and unverified:
        return 2, unverified
    sheets = _sheet_names(list(tables))
    (run / "report.md").write_text(
        render_markdown(run, question, findings, tables, profile, unverified, sheets), encoding="utf-8")
    write_excel(run / "report.xlsx", question, findings, tables, profile, unverified, sheets)
    return (0 if findings else 1), unverified


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build report.md and report.xlsx for a run")
    parser.add_argument("--run", required=True)
    parser.add_argument("--workspace", default="workspace")
    parser.add_argument("--strict", action="store_true", help="fail instead of listing unverified figures")
    args = parser.parse_args(argv)
    run = Path(args.run)
    if not run.is_dir():
        print(f"ERROR: run folder not found: {run}")
        return 1
    try:
        status, unverified = build(run, Path(args.workspace), args.strict)
    except FindingsError as exc:
        print(f"ERROR: {exc}")
        return 1
    for u in unverified:
        print(f"WARN unverified figure in {u['where']}: {u['figure']}")
    if status == 2:
        print("ERROR: unverified figures (--strict). Fix findings.json or save the table the figure comes from.")
        return 1
    if status == 1:
        print("WARN no findings.json: wrote a tables-only report.")
    print(f"Report saved to {(run / 'report.md').as_posix()} and {(run / 'report.xlsx').as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
