import json

from analyst.profile import main, shape


def test_shape():
    assert shape("AB-00123") == "XX-99999"


def test_profile_masks_accounts_and_finds_join(workspace, capsys):
    assert main(["--workspace", str(workspace)]) == 0
    profile = json.loads((workspace / "profile.json").read_text(encoding="utf-8"))
    gk = next(t for t in profile["tables"] if t["name"] == "gk_realized__realized")
    account = next(c for c in gk["columns"] if c["name"] == "Account")
    assert account["masked"] and "top_values" not in account["stats"]
    assert all(row["Account"] == "99999999" for row in gk["sample"])
    assert gk["sample"][0]["CUSIP"] == "037833100"  # securities are public, not masked
    assert gk["sample"][0]["Account Value"] == 5000  # a numeric total is not personal data
    pairs = {(j["left"], j["right"]) for j in profile["join_candidates"]}
    assert ("gk_realized__realized.Account", "silver_positions.AcctNo") in pairs
    out = capsys.readouterr().out
    assert "00001234" not in out and "Join candidates" in out


def test_profile_no_mask(workspace):
    main(["--workspace", str(workspace), "--no-mask"])
    profile = json.loads((workspace / "profile.json").read_text(encoding="utf-8"))
    gk = next(t for t in profile["tables"] if t["name"] == "gk_realized__realized")
    assert gk["sample"][0]["Account"] == "00001234"


def test_profile_empty_workspace(tmp_path):
    assert main(["--workspace", str(tmp_path)]) == 1
