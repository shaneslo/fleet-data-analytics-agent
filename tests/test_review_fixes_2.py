"""Regression tests for the Copilot review on PR #2."""

import json

import pandas as pd
import pytest

from analyst.io import table_from_rows
from analyst.profile import main as profile_main
from analyst.profile import shape
from analyst.reconcile import reconcile
from analyst.sqlcheck import check


def test_leading_zero_warning_has_no_values():
    t = table_from_rows([["Account", "Qty"], ["00001234", "1"], ["1234", "2"]], "x", "x.csv")
    [w] = [w for w in t.warnings if "leading zeros" in w]
    assert "1234" not in w


def test_shape_masks_non_latin_letters():
    assert shape("Zoë Ångström") == "XXX XXXXXXXX"
    assert shape("山田 太郎") == "XX XX"


def test_personal_numeric_and_date_columns_are_masked(tmp_path):
    ws = tmp_path / "ws"
    (ws / "data").mkdir(parents=True)
    (ws / "data" / "clients.csv").write_text(
        "Client Name,Phone,Zip,DOB,Account Value\nAda Lovelace,5551234567,84101,1990-04-01,5000\n", encoding="utf-8")
    profile_main(["--workspace", str(ws)])
    t = json.loads((ws / "profile.json").read_text(encoding="utf-8"))["tables"][0]
    row = t["sample"][0]
    assert row["Phone"] == "9999999999" and row["Zip"] == "99999" and row["DOB"].startswith("9999-99-99")
    assert row["Account Value"] == 5000  # a measure, not personal
    cols = {c["name"]: c for c in t["columns"]}
    assert cols["Phone"]["stats"] == {} and cols["DOB"]["stats"] == {}


def test_masked_profile_drops_previews(workspace):
    profile_main(["--workspace", str(workspace)])
    tables = json.loads((workspace / "profile.json").read_text(encoding="utf-8"))["tables"]
    gk = next(t for t in tables if t["name"] == "gk_realized__realized")
    assert gk["dropped_rows"] and all("preview" not in d for d in gk["dropped_rows"])
    assert "00001234" not in (workspace / "profile.json").read_text(encoding="utf-8")


def test_dedupe_never_repeats_a_name():
    t = table_from_rows([["Account", "Account", "Account_1"], ["1", "2", "3"]], "x", "x.csv")
    assert list(t.df.columns) == ["Account", "Account_1", "Account_1_1"]


def test_lone_trailing_value_is_data_not_footer():
    rows = [["Account", "Qty"], ["00001", "5"], ["00002", ""], ["00003", ""], ["Report generated 10/01/2026"]]
    t = table_from_rows(rows, "x", "x.csv")
    assert list(t.df["Account"]) == ["00001", "00002", "00003"]
    assert [d["reason"] for d in t.dropped] == ["footer row"]


@pytest.mark.parametrize("sql", [
    "SELECT NEXT VALUE FOR dbo.ledger_sequence AS n",
    "dbo.RebuildLedger; SELECT 1;",
    "SELECT 1 AS a\nGO\ndbo.RebuildLedger\nGO\nSELECT 2 AS b",
    "SELECT a FROM [srv].[db]..[t] WHERE a = 1",
])
def test_sql_bypasses_rejected(sql):
    errors, _ = check(sql)
    assert errors, sql


def test_sql_batches_of_reads_pass():
    errors, _ = check("SET NOCOUNT ON;\nGO\n;WITH x AS (SELECT a FROM db..t WHERE a = 1) SELECT a FROM x;")
    assert errors == []


def test_duplicate_key_is_not_also_missing():
    left = pd.DataFrame({"k": ["A", "A", "B"], "q": [1.0, 2.0, 3.0]})
    right = pd.DataFrame({"k": ["A", "B"], "q": [3.0, 3.0]})
    b = reconcile(left, right, [("k", "k")], [("q", "q")], "gk", "silver")
    assert list(b["break_type"]) == ["duplicate_key_in_gk"]


def test_incomplete_keys_are_reported():
    left = pd.DataFrame({"acct": ["1", "2"], "cusip": ["C1", None], "q": [1.0, 2.0]})
    right = pd.DataFrame({"acct": ["1", "2"], "cusip": ["C1", ""], "q": [1.0, 2.0]})
    b = reconcile(left, right, [("acct", "acct"), ("cusip", "cusip")], [("q", "q")], "gk", "silver")
    assert sorted(b["break_type"]) == ["incomplete_key_in_gk", "incomplete_key_in_silver"]
    assert set(b["acct"]) == {"2"}
