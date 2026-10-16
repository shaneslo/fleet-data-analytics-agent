import pytest

from analyst.sqlcheck import check, main

GOOD = """
-- Lots opened in Q3; don't DELETE anything
DECLARE @start date = '2026-07-01';
WITH lots AS (
    SELECT l.account_no, l.cusip, l.quantity
    FROM dbo.tax_lots AS l
    WHERE l.open_date >= @start
)
SELECT account_no, cusip, SUM(quantity) AS quantity
INTO #q3
FROM lots
GROUP BY account_no, cusip;
SELECT * FROM #q3 WHERE quantity <> 0;
"""


def test_good_query_passes():
    errors, warnings = check(GOOD)
    assert errors == []
    assert any("SELECT *" in w for w in warnings)


@pytest.mark.parametrize("sql", [
    "UPDATE dbo.t SET x = 1 WHERE id = 2",
    "DELETE FROM dbo.t WHERE 1=1",
    "SELECT a INTO dbo.copy FROM dbo.t WHERE a > 1",
    "EXEC sp_who",
    "SELECT 1; EXEC('DROP TABLE x')",
    "SELECT a FROM [srv].[db].[dbo].[t] WHERE a = 1",
    "SELECT a FROM OPENQUERY(srv, 'select 1') WHERE a = 1",
    "/* nested /* comment */ */ TRUNCATE TABLE dbo.t",
])
def test_writes_are_rejected(sql):
    errors, _ = check(sql)
    assert errors, sql


def test_keywords_in_strings_and_brackets_are_ignored():
    errors, _ = check("SELECT [Update Date], 'please DELETE' AS note FROM dbo.t WHERE x = 'it''s EXEC'")
    assert errors == []


def test_nolock_warns():
    _, warnings = check("SELECT a FROM dbo.t WITH (NOLOCK) WHERE a = 1")
    assert any("NOLOCK" in w for w in warnings)


def test_cli(tmp_path):
    ok, bad = tmp_path / "ok.sql", tmp_path / "bad.sql"
    ok.write_text("SELECT a FROM dbo.t WHERE a = 1")
    bad.write_text("DROP TABLE dbo.t")
    assert main([str(ok)]) == 0
    assert main([str(ok), str(bad)]) == 1
