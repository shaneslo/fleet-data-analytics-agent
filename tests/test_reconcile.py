import pandas as pd

from analyst.io import load_all
from analyst.reconcile import main, parse_pairs, reconcile, summarize


def test_parse_pairs():
    assert parse_pairs("Account=AcctNo, CUSIP") == [("Account", "AcctNo"), ("CUSIP", "CUSIP")]


def _frames():
    left = pd.DataFrame({"acct": ["001", "002", "003", "003"], "qty": [10.0, 20.0, 5.0, 5.0]})
    right = pd.DataFrame({"account": ["1", "002", "004"], "shares": [10.0, 20.004, 7.0]})
    return left, right


def test_breaks_with_duplicates_flagged():
    left, right = _frames()
    b = reconcile(left, right, [("acct", "account")], [("qty", "shares")], "gk", "silver")
    kinds = sorted(b["break_type"])
    assert kinds == ["duplicate_key_in_gk", "missing_in_gk", "missing_in_gk", "missing_in_silver"]


def test_aggregate_and_strip_zeros():
    left, right = _frames()
    b = reconcile(left, right, [("acct", "account")], [("qty", "shares")], "gk", "silver",
                  aggregate=True, strip_leading_zeros=True)
    assert set(zip(b["acct"], b["break_type"])) == {("3", "missing_in_silver"), ("4", "missing_in_gk")}


def test_tolerance():
    left, right = _frames()
    b = reconcile(left, right, [("acct", "account")], [("qty", "shares")], tolerance=0.001, strip_leading_zeros=True)
    mism = b[b["break_type"] == "value_mismatch"]
    assert list(mism["acct"]) == ["2"] and round(mism["difference"].iloc[0], 3) == -0.004


def test_text_compare():
    left = pd.DataFrame({"k": ["a", "b"], "s": ["x", "y"]})
    right = pd.DataFrame({"k": ["A", "B"], "s": ["X ", "z"]})
    b = reconcile(left, right, [("k", "k")], [("s", "s")])
    assert list(b["k"]) == ["B"]


def test_summary_counts():
    left, right = _frames()
    s = summarize(reconcile(left, right, [("acct", "account")], [("qty", "shares")]))
    assert s["breaks"].sum() == 4
    missing = s[s["break_type"].str.startswith("missing")]
    assert missing["net_difference"].isna().all()  # no value to difference, so blank rather than 0


def test_cli_on_fixture(workspace, tmp_path, capsys):
    tables = load_all(workspace)
    assert {"gk_realized__realized", "silver_positions"} <= set(tables)
    run = tmp_path / "run"
    code = main(["--workspace", str(workspace), "--run", str(run),
                 "--left", "gk_realized__realized", "--right", "silver_positions",
                 "--keys", "Account=AcctNo,CUSIP", "--compare", "Quantity=Shares,Cost Basis=Cost"])
    assert code == 0
    breaks = pd.read_csv(run / "analysis" / "breaks_gk_realized_realized_vs_silver_positions.csv", dtype=str)
    got = set(zip(breaks["Account"], breaks["break_type"], breaks["column"].fillna("")))
    assert got == {
        ("00005678", "value_mismatch", "Quantity / Shares"),
        ("00009999", "missing_in_silver_positions", ""),
        ("00007777", "missing_in_gk_realized__realized", ""),
    }
