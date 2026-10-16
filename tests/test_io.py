import pandas as pd
import pytest

from analyst.io import (
    find_header_row,
    is_identifier_name,
    is_sensitive_name,
    load_all,
    load_file,
    parse_number,
    table_from_rows,
)


@pytest.mark.parametrize("text,expected", [
    ("1,234.56", 1234.56), ("(1,234.56)", -1234.56), ("$1,234", 1234.0), ("12.5%", 12.5),
    ("1234.56-", -1234.56), ("-7", -7.0), ("", None), ("N/A", None), ("ABC123", None),
])
def test_parse_number(text, expected):
    assert parse_number(text) == expected


@pytest.mark.parametrize("name,expected", [
    ("Account", True), ("AcctNo", True), ("Account Number", True), ("CUSIP", True), ("Security ID", True),
    ("Trans Code", True), ("Account Value", False), ("Cost Basis", False), ("Lot Quantity", False),
    ("Amount Paid", False), ("Quantity", False),
])
def test_identifier_names(name, expected):
    assert is_identifier_name(name) is expected


def test_sensitive_names():
    assert is_sensitive_name("Client Name")
    assert is_sensitive_name("AcctNo")
    assert not is_sensitive_name("Security Name")
    assert not is_sensitive_name("Quantity")


def test_header_found_below_banner_rows():
    rows = [["Big Report"], ["As of 1/1/2026"], [], ["A", "B", "C"], ["1", "2", "3"]]
    assert find_header_row(rows) == 3


def test_messy_workbook(workspace):
    tables = {t.sheet: t for t in load_file(workspace / "data" / "GK Realized.xlsx")}
    t = tables["Realized"]
    df = t.df
    assert t.header_row == 4
    assert list(df["Account"]) == ["00001234", "00005678", "00009999"]  # zero padding restored from the format
    assert list(df["CUSIP"]) == ["037833100", "594918104", "38259P508"]
    assert df["Cost Basis"].tolist() == [1234.56, 2000.0, 900.0]
    assert df["Gain/Loss"].iloc[0] == -45.10
    assert pd.api.types.is_datetime64_any_dtype(df["Trade Date"])
    assert t.column_kinds["Account Value"] == "numeric"
    reasons = [d["reason"] for d in t.dropped]
    assert reasons == ["total/subtotal row", "repeated header", "footer row"]
    assert len(df) == 3


def test_csv_semicolon_cp1252(workspace):
    [t] = load_file(workspace / "data" / "silver_positions.csv")
    assert t.column_kinds["AcctNo"] == "identifier"
    assert t.df["AcctNo"].iloc[0] == "00001234"
    assert t.df["Desc"].iloc[2] == "Treasury Note – 2030"
    assert t.df["Shares"].sum() == 160


def test_leading_zero_clash_is_warned():
    t = table_from_rows([["Account", "Qty"], ["00001234", "1"], ["1234", "2"]], "x", "x.csv")
    assert any("leading zeros" in w for w in t.warnings)


def test_scientific_notation_is_warned():
    t = table_from_rows([["CUSIP", "Qty"], ["1.23457E+11", "1"]], "x", "x.csv")
    assert any("scientific notation" in w for w in t.warnings)


def test_load_all_names_tables(workspace):
    names = set(load_all(workspace))
    assert names == {"gk_realized__realized", "gk_realized__notes", "silver_positions"}
