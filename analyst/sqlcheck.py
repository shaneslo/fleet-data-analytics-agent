"""Check that a T-SQL file only reads.

    python -m analyst.sqlcheck workspace/sql/q3_lots.sql [more.sql ...]

Fails (exit 1) on anything that writes, changes schema or permissions, runs
dynamic SQL or stored procedures, or reaches other servers. ``SELECT ... INTO
#temp`` is allowed because temp tables live in tempdb and vanish with the
session. Comments and string literals are ignored, so ``-- don't DELETE``
does not trip it.

Warnings (exit 0): ``SELECT *``, no WHERE/TOP on a query, NOLOCK hints.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

FORBIDDEN = {
    "INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE", "DROP", "ALTER", "CREATE",
    "EXEC", "EXECUTE", "GRANT", "REVOKE", "DENY", "BACKUP", "RESTORE", "DBCC",
    "SHUTDOWN", "KILL", "OPENROWSET", "OPENDATASOURCE", "OPENQUERY", "BULK",
    "WAITFOR", "RECONFIGURE", "WRITETEXT", "UPDATETEXT", "SP_EXECUTESQL",
}
# What a read-only statement may begin with. Anything else at the start of a batch
# could be an implicit procedure call: SQL Server runs `dbo.Proc` without EXEC there.
ALLOWED_STARTS = {"SELECT", "WITH", "DECLARE", "SET", "USE", "IF", "ELSE", "BEGIN", "END", "PRINT"}
_PROC_PREFIX = re.compile(r"\b(SP|XP)_\w+", re.I)


def strip_sql(sql: str) -> str:
    """Remove comments, string literals and [bracketed identifiers]."""
    out, i, n = [], 0, len(sql)
    while i < n:
        two = sql[i:i + 2]
        if two == "--":
            j = sql.find("\n", i)
            i = n if j == -1 else j
        elif two == "/*":
            depth, i = 1, i + 2
            while i < n and depth:
                if sql[i:i + 2] == "/*":
                    depth, i = depth + 1, i + 2
                elif sql[i:i + 2] == "*/":
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
            out.append(" ")
        elif sql[i] in "'[\"":
            close = {"'": "'", "[": "]", '"': '"'}[sql[i]]
            j = i + 1
            while j < n:
                if sql[j] == close:
                    if close != "]" and sql[j + 1:j + 2] == close:
                        j += 2  # escaped quote
                        continue
                    if close == "]" and sql[j + 1:j + 2] == "]":
                        j += 2
                        continue
                    break
                j += 1
            out.append(" x " if sql[i] in "[\"" else " '' ")
            i = j + 1
        else:
            out.append(sql[i])
            i += 1
    return "".join(out)


def statement_starts(code: str) -> list[str]:
    """First word of every batch (split on GO lines) and of every ';'-separated statement."""
    starts = []
    for batch in re.split(r"^\s*GO\b[^\n]*$", code, flags=re.IGNORECASE | re.MULTILINE):
        for statement in batch.split(";"):
            m = re.match(r"\s*([A-Za-z_@#][\w@#$]*|\()", statement)
            if m:
                starts.append(m.group(1))
    return starts


def check(sql: str) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for one SQL text."""
    errors, warnings = [], []
    code = strip_sql(sql)
    words = re.findall(r"[A-Za-z_@#][\w@#$]*", code)
    upper = [w.upper() for w in words]

    for w in sorted(set(upper) & FORBIDDEN):
        errors.append(f"'{w}' is not allowed: queries for Sedona must only read")
    if re.search(r"\bNEXT\s+VALUE\s+FOR\b", code, re.IGNORECASE):
        errors.append("'NEXT VALUE FOR' advances a sequence; it is not read-only")
    for start in statement_starts(code):
        if start.upper() not in ALLOWED_STARTS and start != "(":
            errors.append(
                f"statement starts with '{start}': only {', '.join(sorted(ALLOWED_STARTS))} may start a "
                "statement (a bare procedure name at the start of a batch runs it)"
            )
    for m in _PROC_PREFIX.finditer(code):
        errors.append(f"system procedure '{m.group(0)}' is not allowed")
    for idx, w in enumerate(upper):
        if w == "INTO":
            target = words[idx + 1] if idx + 1 < len(words) else ""
            if not target.startswith("#"):
                errors.append(f"'INTO {target}' writes to a permanent table; use a CTE or INTO #temp")
    if re.search(r"\w+\s*\.\s*\w*\s*\.\s*\w*\s*\.\s*\w+", code):  # srv.db.schema.t, srv.db..t
        errors.append("four-part name (linked server) is not allowed")

    if re.search(r"\bSELECT\s+(TOP\s*\(?\s*\d+\s*\)?\s+)?\*", code, re.I):
        warnings.append("SELECT * : list the columns so the export has a stable shape")
    if "NOLOCK" in upper or ("READ" in upper and "UNCOMMITTED" in upper):
        warnings.append("NOLOCK / READ UNCOMMITTED can return rows mid-transaction; ledger totals may not tie")
    if "SELECT" in upper and "WHERE" not in upper and "TOP" not in upper:
        warnings.append("no WHERE or TOP: this may pull the whole table")
    if "SELECT" not in upper:
        errors.append("no SELECT found")
    return sorted(set(errors)), warnings


def main(argv: list[str] | None = None) -> int:
    paths = argv if argv is not None else sys.argv[1:]
    if not paths:
        print(__doc__)
        return 2
    failed = False
    for p in paths:
        path = Path(p)
        if not path.exists():
            print(f"{p}: ERROR file not found")
            failed = True
            continue
        errors, warnings = check(path.read_text(encoding="utf-8-sig"))
        for e in errors:
            print(f"{p}: ERROR {e}")
        for w in warnings:
            print(f"{p}: WARN {w}")
        if not errors:
            print(f"{p}: OK read-only")
        failed |= bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
