"""Regression tests for review findings on PR #2."""

import json

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from analyst import io as aio
from analyst import report
from analyst.io import is_sensitive_name, load_file
from analyst.reconcile import reconcile
from analyst.run import new_run


def test_generated_tables_keep_total_rows(tmp_path):
    path = tmp_path / "by_account.csv"
    path.write_text("label,amount\nAcct A,10\nTotal,10\n", encoding="utf-8")
    assert len(load_file(path)[0].df) == 1  # source exports: "Total" is a subtotal row
    assert len(load_file(path, clean=False)[0].df) == 2  # generated tables: it's data


def test_report_includes_total_row_and_grounds_it(workspace):
    run = new_run("q", workspace)
    (run / "analysis" / "by_account.csv").write_text("label,amount\nAcct A,1250.5\nTotal,98765.43\n", encoding="utf-8")
    (run / "findings.json").write_text(json.dumps({
        "title": "t", "answer": "The total is $98,765.43.",
        "findings": [{"headline": "h", "table": "analysis/by_account.csv"}]}), encoding="utf-8")
    assert report.main(["--run", str(run), "--workspace", str(workspace)]) == 0
    md = (run / "report.md").read_text(encoding="utf-8")
    assert "| Total | 98,765.43 |" in md and "Unverified figures" not in md


def test_formula_like_text_stays_text(workspace):
    run = new_run("q", workspace)
    (run / "analysis" / "notes.csv").write_text('note,amount\n"=HYPERLINK(""http://x"")",1\n', encoding="utf-8")
    (run / "findings.json").write_text(json.dumps({"title": "t", "answer": "a", "findings": [{"headline": "h"}]}),
                                       encoding="utf-8")
    report.main(["--run", str(run), "--workspace", str(workspace)])
    cell = load_workbook(run / "report.xlsx")["notes"]["A2"]
    assert cell.data_type == "s" and cell.value == '=HYPERLINK("http://x")'


def test_mixed_asset_and_personal_names_stay_masked():
    assert is_sensitive_name("Fund Client Name")
    assert is_sensitive_name("Security Account Name")
    assert not is_sensitive_name("Security Name")
    assert not is_sensitive_name("Fund Name")


def test_aggregate_keeps_all_missing_group_missing():
    left = pd.DataFrame({"k": ["a", "a"], "qty": [np.nan, np.nan]})
    right = pd.DataFrame({"k": ["a"], "qty": [0.0]})
    breaks = reconcile(left, right, [("k", "k")], [("qty", "qty")], aggregate=True)
    assert list(breaks["break_type"]) == ["value_mismatch"]


def test_legacy_xls_warns_about_lost_padding(tmp_path, monkeypatch):
    monkeypatch.setattr(aio, "_read_xls", lambda p: {"Sheet1": [["Account", "Qty"], ["1234", "1"]]})
    path = tmp_path / "old.xls"
    path.write_bytes(b"")
    [table] = load_file(path)
    assert any("legacy .xls" in w for w in table.warnings)
