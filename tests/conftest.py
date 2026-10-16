"""Fixtures that imitate report-style exports. All data here is synthetic."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from openpyxl import Workbook

HEADER = ["Account", "CUSIP", "Security Name", "Trade Date", "Quantity", "Cost Basis", "Gain/Loss", "Account Value"]


def write_gk_workbook(path: Path) -> Path:
    """A Gainskeeper-style export: banner rows, a subtotal, a page-break header, a footer."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Realized"
    ws.append(["Realized Gain/Loss Report"])
    ws.append(["As of 09/30/2026"])
    ws.append([])
    ws.append(HEADER)
    ws.append([1234, "037833100", "Alpha Corp", datetime(2026, 9, 1), 100, "1,234.56", "(45.10)", 5000])
    ws.cell(row=5, column=1).number_format = "00000000"  # zero-padded account stored as a number
    ws.append(["00005678", "594918104", "Beta Inc", datetime(2026, 9, 2), 50, 2000, 12.5, 6000])
    ws.append(["Total Account 00001234", None, None, None, 150, 3234.56, -32.6, None])
    ws.append(HEADER)
    ws.append(["00009999", "38259P508", "Gamma Ltd", "2026-09-03", 10, 900, 1, 100])
    ws.append(["Report generated 10/01/2026"])
    notes = wb.create_sheet("Notes")
    notes.append(["Prepared by", "ops"])
    notes.append(["Run", "nightly"])
    wb.save(path)
    return path


def write_silver_csv(path: Path) -> Path:
    """A Silver-style CSV: semicolon-delimited, cp1252, different column names."""
    rows = [
        "AcctNo;CUSIP;Shares;Cost;Desc",
        "00001234;037833100;100;1234.56;Alpha Corp",
        "00005678;594918104;55;2000.00;Beta Inc",
        "00007777;912828XX1;5;500.00;Treasury Note – 2030",
    ]
    path.write_bytes("\r\n".join(rows).encode("cp1252"))
    return path


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    (ws / "data").mkdir(parents=True)
    write_gk_workbook(ws / "data" / "GK Realized.xlsx")
    write_silver_csv(ws / "data" / "silver_positions.csv")
    return ws
