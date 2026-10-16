"""Compare two tables on a key and list every break.

    python -m analyst.reconcile --run RUN \\
        --left gk_realized --right silver_positions \\
        --keys "Account=AcctNo,CUSIP" --compare "Quantity=Shares,Cost Basis=Cost" \\
        [--tolerance 0.01] [--aggregate] [--strip-leading-zeros] [--out analysis/breaks.csv]

``--keys`` and ``--compare`` take ``left_col=right_col`` pairs, or a single
name when both sides use it. Tables are looked up by the names
``analyst.profile`` prints. From Python, call ``reconcile()`` with DataFrames.

Break types:
  missing_in_<right>   key only in the left table
  missing_in_<left>    key only in the right table
  value_mismatch       key in both, a compared column differs beyond tolerance
  duplicate_key        key appears more than once on a side (without --aggregate)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from analyst.io import load_all, safe_stdout, slug


def parse_pairs(spec: str) -> list[tuple[str, str]]:
    pairs = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        left, _, right = part.partition("=")
        pairs.append((left.strip(), (right or left).strip()))
    return pairs


def normalize_key(values: pd.Series, strip_leading_zeros: bool = False) -> pd.Series:
    out = values.astype("string").str.strip().str.upper()
    out = out.str.replace(r"^(\d+)\.0$", r"\1", regex=True)
    if strip_leading_zeros:
        out = out.str.replace(r"^0+(?=.)", "", regex=True)
    return out


def _sum_or_missing(values: pd.Series) -> float:
    """Sum, but a group with no values stays missing instead of becoming 0."""
    return values.sum(min_count=1)


def _prepare(df, keys, compare, aggregate, strip_zeros, side):
    frame = pd.DataFrame({f"key_{i}": normalize_key(df[k], strip_zeros) for i, k in enumerate(keys)})
    for i, c in enumerate(compare):
        frame[f"val_{i}"] = df[c].values
    key_cols = [f"key_{i}" for i in range(len(keys))]
    frame = frame.dropna(subset=key_cols)
    if aggregate:
        numeric = {c: _sum_or_missing for c in frame.columns if c.startswith("val_") and pd.api.types.is_numeric_dtype(frame[c])}
        other = {c: "first" for c in frame.columns if c.startswith("val_") and c not in numeric}
        return frame.groupby(key_cols, as_index=False, dropna=False).agg({**numeric, **other}), pd.DataFrame()
    dup_mask = frame.duplicated(key_cols, keep=False)
    dups = frame.loc[dup_mask, key_cols].drop_duplicates().assign(side=side)
    return frame.loc[~dup_mask], dups


def reconcile(
    left: pd.DataFrame,
    right: pd.DataFrame,
    keys: list[tuple[str, str]],
    compare: list[tuple[str, str]],
    left_name: str = "left",
    right_name: str = "right",
    tolerance: float = 0.01,
    aggregate: bool = False,
    strip_leading_zeros: bool = False,
) -> pd.DataFrame:
    """Return one row per break. Columns: the keys, break_type, column, left/right values, difference."""
    key_names = [lk for lk, _ in keys]
    lf, ldup = _prepare(left, [k for k, _ in keys], [c for c, _ in compare], aggregate, strip_leading_zeros, left_name)
    rf, rdup = _prepare(right, [k for _, k in keys], [c for _, c in compare], aggregate, strip_leading_zeros, right_name)
    key_cols = [f"key_{i}" for i in range(len(keys))]
    merged = lf.merge(rf, on=key_cols, how="outer", suffixes=("_l", "_r"), indicator=True)

    lv, rv = f"{left_name}_value", f"{right_name}_value"
    breaks = []

    def row(keys_row, break_type, column=None, a=None, b=None, diff=None):
        out = dict(zip(key_names, keys_row))
        out.update({"break_type": break_type, "column": column, lv: a, rv: b, "difference": diff})
        return out

    for rec in merged[merged["_merge"] == "left_only"].itertuples(index=False):
        breaks.append(row([getattr(rec, k) for k in key_cols], f"missing_in_{right_name}"))
    for rec in merged[merged["_merge"] == "right_only"].itertuples(index=False):
        breaks.append(row([getattr(rec, k) for k in key_cols], f"missing_in_{left_name}"))

    both = merged[merged["_merge"] == "both"]
    for i, (lc, rc) in enumerate(compare):
        a, b = both[f"val_{i}_l"], both[f"val_{i}_r"]
        label = lc if lc == rc else f"{lc} / {rc}"
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            diff = a.astype(float) - b.astype(float)
            differs = (diff.abs() > tolerance) | (a.isna() != b.isna())
        else:
            sa = a.astype("string").str.strip().str.upper()
            sb = b.astype("string").str.strip().str.upper()
            differs = (sa != sb).fillna(sa.isna() != sb.isna()).astype(bool)
            diff = pd.Series(np.nan, index=both.index)
        for idx in both.index[differs.to_numpy()]:
            rec = both.loc[idx]
            d = diff.loc[idx]
            breaks.append(row(
                [rec[k] for k in key_cols], "value_mismatch", label,
                _plain(a.loc[idx]), _plain(b.loc[idx]), None if pd.isna(d) else round(float(d), 6),
            ))

    for dups in (ldup, rdup):
        for rec in dups.itertuples(index=False):
            breaks.append(row([getattr(rec, k) for k in key_cols], f"duplicate_key_in_{rec.side}"))

    columns = key_names + ["break_type", "column", lv, rv, "difference"]
    return pd.DataFrame(breaks, columns=columns)


def _plain(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (np.floating, float)):
        return float(value)
    return value.item() if hasattr(value, "item") else value


def summarize(breaks: pd.DataFrame) -> pd.DataFrame:
    """Count and net difference by break type and column."""
    if breaks.empty:
        return pd.DataFrame(columns=["break_type", "column", "breaks", "net_difference"])
    return (
        breaks.assign(column=breaks["column"].fillna(""))
        .groupby(["break_type", "column"], as_index=False)
        .agg(breaks=("break_type", "size"), net_difference=("difference", lambda d: d.sum(min_count=1)))
        .sort_values("breaks", ascending=False)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile two tables and write the breaks")
    parser.add_argument("--workspace", default="workspace")
    parser.add_argument("--run", required=True, help="run folder from `python -m analyst.run new`")
    parser.add_argument("--left", required=True, help="table name (see profile output)")
    parser.add_argument("--right", required=True)
    parser.add_argument("--keys", required=True, help="'Account=AcctNo,CUSIP'")
    parser.add_argument("--compare", required=True, help="'Quantity=Shares,Cost Basis=Cost'")
    parser.add_argument("--tolerance", type=float, default=0.01)
    parser.add_argument("--aggregate", action="store_true", help="sum numeric columns per key first (lots -> positions)")
    parser.add_argument("--strip-leading-zeros", action="store_true")
    parser.add_argument("--out", default=None, help="CSV path relative to the run folder")
    args = parser.parse_args(argv)
    safe_stdout()

    tables = load_all(args.workspace)
    missing = [n for n in (args.left, args.right) if n not in tables]
    if missing:
        print(f"ERROR: table(s) not found: {missing}. Available: {sorted(tables)}")
        return 1
    breaks = reconcile(
        tables[args.left].df, tables[args.right].df,
        parse_pairs(args.keys), parse_pairs(args.compare),
        left_name=args.left, right_name=args.right, tolerance=args.tolerance,
        aggregate=args.aggregate, strip_leading_zeros=args.strip_leading_zeros,
    )
    run = Path(args.run)
    out = run / (args.out or f"analysis/breaks_{slug(args.left)}_vs_{slug(args.right)}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    breaks.to_csv(out, index=False)
    summary = summarize(breaks)
    summary_path = out.with_name(out.stem + "_summary.csv")
    summary.to_csv(summary_path, index=False)

    print(f"{len(breaks):,} break(s) -> {out}")
    print(summary.to_string(index=False) if not summary.empty else "No breaks.")
    print(f"Summary -> {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
