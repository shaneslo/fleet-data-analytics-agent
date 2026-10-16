"""Write DataFrames to Excel the way the rest of the tooling expects.

Identifiers are written as text (leading zeros survive), dates and numbers get
display formats, the header is frozen with a filter, and any string starting
with '=' is stored as text rather than turning into a live formula.

From a quick-mode script:

    from analyst.xlsx import export
    export(losses, "top_realized_losses")   # -> workspace/exports/top_realized_losses_<time>.xlsx
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from analyst.io import is_identifier_name, slug

EXCEL_MAX_ROWS = 1_048_575


def append_row(sheet, values: list) -> None:
    """Append a row; a string starting with '=' stays text instead of becoming a formula."""
    sheet.append(values)
    if any(isinstance(v, str) and v.startswith("=") for v in values):
        for cell in sheet[sheet.max_row]:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                cell.data_type = "s"


def infer_kinds(df: pd.DataFrame) -> dict[str, str]:
    """Column kinds for a frame that didn't come from analyst.io (e.g. one built in a script)."""
    kinds = {}
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            kinds[col] = "datetime"
        elif pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_bool_dtype(df[col]):
            kinds[col] = "numeric"
        elif is_identifier_name(str(col)):
            kinds[col] = "identifier"
        else:
            kinds[col] = "text"
    return kinds


def _cell(value):
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, "item"):  # numpy scalar
        return value.item()
    return value


def write_table(sheet, df: pd.DataFrame, kinds: dict[str, str] | None = None) -> None:
    """Fill a worksheet with a frame: bold frozen header, filter, formats, sensible widths."""
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    kinds = kinds or infer_kinds(df)
    df = df.head(EXCEL_MAX_ROWS)
    append_row(sheet, [str(c) for c in df.columns])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in df.itertuples(index=False):
        append_row(sheet, [_cell(v) for v in row])
    for j, col in enumerate(df.columns, 1):
        kind = kinds.get(col, "text")
        fmt = {"identifier": "@", "datetime": "yyyy-mm-dd"}.get(kind)
        if kind == "numeric":
            whole = df[col].dropna().map(lambda v: float(v).is_integer()).all()
            fmt = "#,##0" if whole else "#,##0.00"
        if fmt:
            for (cell,) in sheet.iter_rows(min_row=2, min_col=j, max_col=j):
                cell.number_format = fmt
        width = max([len(str(col))] + [len(str(v)) for v in df[col].head(200) if v is not None])
        sheet.column_dimensions[get_column_letter(j)].width = min(max(width + 2, 8), 60)
    sheet.freeze_panes = "A2"
    if len(df.columns):
        sheet.auto_filter.ref = sheet.dimensions


def export(df: pd.DataFrame, name: str, workspace: str | Path = "workspace",
           kinds: dict[str, str] | None = None) -> Path:
    """Save one frame as workspace/exports/<name>_<HHMMSS>.xlsx and return the path."""
    from openpyxl import Workbook

    out_dir = Path(workspace) / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slug(name)[:60]}_{datetime.now():%Y-%m-%d_%H%M%S}.xlsx"
    wb = Workbook()
    write_table(wb.active, df, kinds)
    wb.active.title = slug(name)[:31] or "data"
    wb.save(path)
    print(f"Saved {len(df):,} row(s) to {path.as_posix()}")
    return path
