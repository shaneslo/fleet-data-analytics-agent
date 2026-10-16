# Data sources

What each system's exports mean. The agent reads this before any analysis
that touches these sources, so the more of it is filled in, the fewer wrong
assumptions it makes. Replace every `TODO`. Leave a field blank rather than guess.

Do not put real account numbers, client names or balances in this file: it is
committed. Describe columns and rules, not records.

---

## Gainskeeper

Cost basis / tax-lot system.

| | |
|---|---|
| Exports used | TODO: report names (e.g. realized gain/loss, open lots) and how you run them |
| Grain | TODO: one row per lot? per disposition? per account-security? |
| Date meaning | TODO: trade date or settle date? as-of date of the export? |
| Keys | TODO: account column name and format (leading zeros?), security id (CUSIP? symbol?), lot id |
| Cost basis method | TODO: FIFO / specific ID / average, and where it is recorded |

Columns worth knowing:

| Column | Meaning | Notes |
|---|---|---|
| TODO | | |

Known quirks: TODO (e.g. subtotals per account, wash-sale adjustments shown on a separate line).

---

## Silver

TODO: one line on what Silver is and what it is the book of record for.

| | |
|---|---|
| Exports used | TODO |
| Grain | TODO |
| Date meaning | TODO |
| Keys | TODO |

Columns worth knowing:

| Column | Meaning | Notes |
|---|---|---|
| TODO | | |

Known quirks: TODO

---

## Sedona (upstream ledger)

SQL Server, queried in Aqua Data Studio. Tables and columns are in
[`sedona/schema.md`](sedona/schema.md); trusted queries in [`sedona/queries/`](sedona/queries/).

| | |
|---|---|
| What it is the source of truth for | TODO |
| Date meaning | TODO |
| Keys | TODO |

---

## How the systems relate

- Which system is the reference when they disagree, for which field: TODO
- Key mapping (e.g. Gainskeeper `Account` = Silver `AcctNo` = Sedona `account_no`): TODO
- Expected, explainable differences (timing, corporate actions, pending trades): TODO
- Tolerances that count as a match (shares, dollars): TODO

## Glossary

| Term | Meaning |
|---|---|
| TODO | |
