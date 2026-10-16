# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Modified from the AI Studio "AI Data Analyst" sample's make_chart.py:
# paths are relative to a run folder, tables load through analyst.io so
# identifiers stay text, and numeric axes use thousands separators.
"""Render a PNG chart from a result table in a run folder.

    python -m analyst.chart --run RUN --data analysis/breaks_summary.csv \\
        --type barh --x break_type --y breaks --title "Breaks by type" \\
        --output charts/breaks_by_type.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402

from analyst.io import load_table  # noqa: E402

PALETTE = [
    "#2F5D8A", "#3C9D9B", "#E3A33B", "#C8553D", "#7A6FB0",
    "#5B8E3E", "#B5527F", "#8C8C8C", "#D1793A", "#4A90C2",
]

_thousands = FuncFormatter(lambda v, _: f"{v:,.0f}" if abs(v) >= 1000 or float(v).is_integer() else f"{v:,.2f}")


def style_axes(ax, title, xlabel, ylabel, value_axis="y", whole_numbers=False):
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=11)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis=value_axis, alpha=0.3, linestyle="--")
    axis = ax.yaxis if value_axis == "y" else ax.xaxis
    axis.set_major_formatter(_thousands)
    if whole_numbers:
        axis.set_major_locator(MaxNLocator(integer=True))


def render(df: pd.DataFrame, kind: str, out_path: Path, x=None, y_cols=(), title="", xlabel=None, ylabel=None, top=None):
    y_cols = list(y_cols)
    if top and y_cols:
        df = df.sort_values(y_cols[0], ascending=False).head(top)

    whole = bool(y_cols) and all(
        pd.api.types.is_numeric_dtype(df[c]) and df[c].dropna().map(float.is_integer).all() for c in y_cols
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"figure.autolayout": True, "font.size": 11})
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=130)
    try:
        if kind == "bar":
            ax.bar(df[x].astype(str), df[y_cols[0]], color=PALETTE[0])
            plt.xticks(rotation=45, ha="right")
            style_axes(ax, title, xlabel or x, ylabel or y_cols[0], whole_numbers=whole)
        elif kind == "barh":
            df = df.iloc[::-1]  # largest on top
            ax.barh(df[x].astype(str), df[y_cols[0]], color=PALETTE[0])
            style_axes(ax, title, xlabel or y_cols[0], ylabel or x, value_axis="x", whole_numbers=whole)
        elif kind == "line":
            for i, col in enumerate(y_cols):
                ax.plot(df[x], df[col], marker="o", markersize=4, linewidth=2,
                        color=PALETTE[i % len(PALETTE)], label=col)
            plt.xticks(rotation=45, ha="right")
            style_axes(ax, title, xlabel or x, ylabel or (y_cols[0] if len(y_cols) == 1 else "value"))
            if len(y_cols) > 1:
                ax.legend(frameon=False)
        elif kind == "scatter":
            ax.scatter(df[x], df[y_cols[0]], color=PALETTE[0], alpha=0.6, edgecolors="white")
            style_axes(ax, title, xlabel or x, ylabel or y_cols[0])
        elif kind == "pie":
            labels = df[x].astype(str) if x else df.iloc[:, 0].astype(str)
            values = df[y_cols[0]] if y_cols else df.iloc[:, 1]
            ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90,
                   colors=PALETTE, wedgeprops={"edgecolor": "white"})
            ax.axis("equal")
            if title:
                ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
        elif kind == "heatmap":
            matrix = df.set_index(df.columns[0]).apply(pd.to_numeric, errors="coerce")
            im = ax.imshow(matrix.values, cmap="Blues", aspect="auto")
            ax.set_xticks(range(len(matrix.columns)))
            ax.set_xticklabels(matrix.columns, rotation=45, ha="right")
            ax.set_yticks(range(len(matrix.index)))
            ax.set_yticklabels(matrix.index)
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            if title:
                ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
        else:
            raise ValueError(f"unknown chart type {kind}")
        fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    finally:
        plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a chart from a result table")
    parser.add_argument("--run", required=True, help="run folder")
    parser.add_argument("--data", required=True, help="CSV path relative to the run folder")
    parser.add_argument("--type", required=True, choices=["bar", "barh", "line", "scatter", "pie", "heatmap"])
    parser.add_argument("--x", default=None)
    parser.add_argument("--y", default=None, help="column(s), comma-separated for multi-series line")
    parser.add_argument("--title", default="")
    parser.add_argument("--xlabel", default=None)
    parser.add_argument("--ylabel", default=None)
    parser.add_argument("--top", type=int, default=None, help="keep the top N rows by the first --y column")
    parser.add_argument("--output", required=True, help="PNG path relative to the run folder, under charts/")
    args = parser.parse_args(argv)

    run = Path(args.run)
    data_path = run / args.data
    if not data_path.exists():
        print(f"ERROR: data file not found: {data_path}")
        return 1
    y_cols = [c.strip() for c in args.y.split(",")] if args.y else []
    out_path = run / args.output
    try:
        render(load_table(data_path, clean=False), args.type, out_path, args.x, y_cols,
               args.title, args.xlabel, args.ylabel, args.top)
    except Exception as exc:  # noqa: BLE001 - a failed chart must not stop the report
        print(f"ERROR: failed to render chart: {exc}")
        return 1
    print(f"Chart saved to {out_path.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
