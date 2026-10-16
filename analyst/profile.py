"""Profile every table under workspace/data and write workspace/profile.json.

    python -m analyst.profile [--workspace workspace] [--no-mask]

The profile is what the agent reads instead of raw rows. Values in account and
personal columns (names, addresses, tax IDs) are shown only as their shape,
e.g. 00012345 -> 99999999, unless --no-mask is given.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from itertools import combinations
from pathlib import Path

import pandas as pd

from analyst.io import LoadedTable, is_sensitive_name, load_all, name_tokens, safe_stdout

# Different systems name the same key differently.
_KEY_SYNONYMS = {
    "acct": "account", "acctno": "account", "accountno": "account", "accountnumber": "account",
    "acctnumber": "account", "acctnbr": "account", "accountid": "account",
    "cusipnumber": "cusip", "cusipno": "cusip", "securityid": "security", "secid": "security",
    "ticker": "symbol", "sym": "symbol", "lotnumber": "lot", "lotno": "lot", "lotid": "lot",
}

JOIN_OVERLAP_MIN = 0.3
MAX_DISTINCT_FOR_OVERLAP = 2_000_000


def shape(value) -> str:
    """'AB-00123' -> 'XX-99999'. Keeps format, drops content."""
    return re.sub(r"[A-Za-z]", "X", re.sub(r"\d", "9", str(value)))


def _num(value):
    if value is None or pd.isna(value):
        return None
    value = float(value)
    return int(value) if value.is_integer() and abs(value) < 1e15 else round(value, 6)


def _column_profile(series: pd.Series, kind: str, masked: bool) -> dict:
    n = len(series)
    missing = int(series.isna().sum())
    info = {
        "name": series.name,
        "kind": kind,
        "missing": missing,
        "missing_pct": round(missing / n, 4) if n else 0.0,
        "distinct": int(series.nunique(dropna=True)),
        "masked": masked,
    }
    present = series.dropna()
    if present.empty:
        info["stats"] = {}
    elif kind == "numeric":
        info["stats"] = {
            "min": _num(present.min()), "max": _num(present.max()), "sum": _num(present.sum()),
            "mean": _num(present.mean()), "median": _num(present.median()),
            "std": _num(present.std()) if len(present) > 1 else None,
            "negatives": int((present < 0).sum()), "zeros": int((present == 0).sum()),
        }
    elif kind == "datetime":
        info["stats"] = {"min": str(present.min().date()), "max": str(present.max().date())}
    elif masked:
        shapes = present.astype(str).map(shape).value_counts().head(3)
        info["stats"] = {"shapes": {k: int(v) for k, v in shapes.items()}}
    else:
        top = present.astype(str).str.slice(0, 60).value_counts().head(10)
        info["stats"] = {"top_values": {k: int(v) for k, v in top.items()}}
    return info


def should_mask(column: str, kind: str, mask: bool) -> bool:
    """Mask account and personal values; numeric totals and dates stay visible."""
    return mask and kind in ("identifier", "text") and is_sensitive_name(column)


def _sample(table: LoadedTable, mask: bool, rows: int = 5) -> list[dict]:
    sample = table.df.head(rows).copy()
    for col in sample.columns:
        kind = table.column_kinds[col]
        if should_mask(col, kind, mask):
            sample[col] = sample[col].map(lambda v: None if pd.isna(v) else shape(v))
        elif kind == "datetime":
            sample[col] = sample[col].map(lambda v: None if pd.isna(v) else str(v.date()))
        elif kind == "numeric":
            sample[col] = sample[col].map(_num)
        else:
            sample[col] = sample[col].map(lambda v: None if pd.isna(v) else str(v)[:60])
    return sample.to_dict(orient="records")


def profile_table(table: LoadedTable, mask: bool = True) -> dict:
    df = table.df
    return {
        "name": table.name,
        "source": table.source,
        "sheet": table.sheet,
        "header_row": table.header_row,
        "rows": len(df),
        "columns_count": len(df.columns),
        "duplicate_rows": int(df.duplicated().sum()),
        "dropped_rows": table.dropped,
        "warnings": table.warnings,
        "columns": [
            _column_profile(df[c], table.column_kinds[c], should_mask(c, table.column_kinds[c], mask))
            for c in df.columns
        ],
        "sample": _sample(table, mask),
    }


def _key_name(column: str) -> str:
    joined = "".join(name_tokens(column))
    return _KEY_SYNONYMS.get(joined, joined)


def join_candidates(tables: dict[str, LoadedTable]) -> list[dict]:
    """Identifier columns in different tables whose values overlap."""
    columns = []
    for t in tables.values():
        for col, kind in t.column_kinds.items():
            if kind != "identifier":
                continue
            values = t.df[col].dropna().astype(str).str.strip().str.upper()
            if 0 < values.nunique() <= MAX_DISTINCT_FOR_OVERLAP:
                columns.append((t.name, col, set(values), set(values.str.lstrip("0"))))

    found = []
    for (ta, ca, va, za), (tb, cb, vb, zb) in combinations(columns, 2):
        if ta == tb:
            continue
        smaller = min(len(va), len(vb))
        exact = len(va & vb) / smaller
        unpadded = len(za & zb) / min(len(za), len(zb))
        if max(exact, unpadded) < JOIN_OVERLAP_MIN:
            continue
        found.append({
            "left": f"{ta}.{ca}",
            "right": f"{tb}.{cb}",
            "overlap": round(exact, 3),
            "overlap_ignoring_leading_zeros": round(unpadded, 3),
            "same_name": _key_name(ca) == _key_name(cb),
        })
    return sorted(found, key=lambda f: -max(f["overlap"], f["overlap_ignoring_leading_zeros"]))


def build_profile(workspace: str | Path = "workspace", mask: bool = True) -> dict:
    tables = load_all(workspace)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "workspace": str(workspace),
        "masked": mask,
        "tables": [profile_table(t, mask) for t in tables.values()],
        "join_candidates": join_candidates(tables),
    }


def summarize(profile: dict) -> str:
    lines = [f"{len(profile['tables'])} table(s) in {profile['workspace']}/data"]
    for t in profile["tables"]:
        where = t["source"] + (f" [{t['sheet']}]" if t["sheet"] else "")
        lines.append(f"\n## {t['name']}  ({where}; {t['rows']:,} rows x {t['columns_count']} cols; header row {t['header_row']})")
        lines.append("   " + ", ".join(f"{c['name']}:{c['kind']}" + ("*" if c["masked"] else "") for c in t["columns"]))
        if t["duplicate_rows"]:
            lines.append(f"   duplicate rows: {t['duplicate_rows']}")
        if t["dropped_rows"]:
            reasons: dict[str, int] = {}
            for d in t["dropped_rows"]:
                reasons[d["reason"]] = reasons.get(d["reason"], 0) + 1
            lines.append("   dropped: " + ", ".join(f"{n} {r}" for r, n in reasons.items()))
        for w in t["warnings"]:
            lines.append(f"   WARN {w}")
    if profile["join_candidates"]:
        lines.append("\nJoin candidates (identifier values that overlap across tables):")
        for j in profile["join_candidates"][:15]:
            note = ""
            if j["overlap_ignoring_leading_zeros"] > j["overlap"]:
                note = f" (ignoring leading zeros: {j['overlap_ignoring_leading_zeros']:.0%})"
            lines.append(f"   {j['left']} <-> {j['right']}: {j['overlap']:.0%}{note}")
    if profile["masked"]:
        lines.append("\n* = masked column (values shown as shape only)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", default="workspace")
    parser.add_argument("--no-mask", action="store_true", help="show raw values in samples and top values")
    args = parser.parse_args(argv)
    safe_stdout()

    profile = build_profile(args.workspace, mask=not args.no_mask)
    if not profile["tables"]:
        print(f"No CSV or Excel files found in {Path(args.workspace) / 'data'}. Add exports there and re-run.")
        return 1
    out = Path(args.workspace) / "profile.json"
    out.write_text(json.dumps(profile, indent=2, default=str), encoding="utf-8")
    print(summarize(profile))
    print(f"\nProfile saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
