"""Guardrails around the data agent, one per layer.

    question  ->  InputGuard   length cap, prompt-injection patterns
    SQL       ->  SqlGuard     one read-only SELECT, allow-listed tables only, no table or system
                               functions, no restricted columns, estimated cost under the caller's
                               limit, row cap enforced by rewriting LIMIT
    rows      ->  OutputGuard  personal data masked again as a backstop, row cap

The secure session (see access.py) is the layer under all of these: even SQL that passed every
check only sees the caller's rows and columns, with file and network access switched off."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

MAX_QUESTION_CHARS = 400
MAX_ROWS = 200
INJECTION_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"ignore (all |any )?(previous|prior|above) (instructions|rules)",
        r"disregard (the )?(system|previous) (prompt|instructions)",
        r"you are now",
        r"reveal (the |your )?(system prompt|instructions)",
        r"\brun (this|the following) sql\b",
        r"\b(drop|truncate|delete from|insert into|alter table|update \w+ set)\b",
    )
]
DENY_STATEMENTS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Command,
    exp.Copy,
    exp.Pragma,
    exp.Set,
    exp.Attach,
    exp.Detach,
    exp.Merge,
    exp.TruncateTable,
    exp.Use,
)
DENY_FUNCTION_PREFIXES = (
    "read_",
    "glob",
    "getenv",
    "current_setting",
    "query",
    "sniff_",
    "duckdb_",
    "pragma_",
    "sqlite_",
    "parquet_",
    "iceberg_",
    "delta_",
    "http",
    "load",
    "install",
    "system",
    "shell",
    "pg_",
    "which_secret",
    "list_files",
)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"\b\d{3}-\d{3,4}-\d{4}\b")


@dataclass
class GuardResult:
    allowed: bool
    reason: str = ""
    sql: str = ""
    cost: int = 0


class InputGuard:
    def check(self, question: str) -> GuardResult:
        if not question.strip():
            return GuardResult(False, "empty_question")
        if len(question) > MAX_QUESTION_CHARS:
            return GuardResult(False, "question_too_long")
        for p in INJECTION_PATTERNS:
            if p.search(question):
                return GuardResult(False, "prompt_injection")
        return GuardResult(True)


def _fname(f: exp.Expression) -> str:
    return (f.name if isinstance(f, exp.Anonymous) else f.sql_name()).lower()


class SqlGuard:
    def __init__(
        self, tables: dict[str, int], hidden_columns: set[str], cost_limit: int, max_rows: int = MAX_ROWS
    ) -> None:
        self.tables = tables  # allowed table -> row count
        self.hidden = hidden_columns  # {"table.column"}
        self.cost_limit = cost_limit
        self.max_rows = max_rows

    def check(self, sql: str) -> GuardResult:
        try:
            stmts = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
        except sqlglot.errors.ParseError:
            return GuardResult(False, "unparseable_sql")
        if len(stmts) != 1:
            return GuardResult(False, "multiple_statements")
        tree = stmts[0]
        if not isinstance(tree, exp.Select | exp.SetOperation) or any(tree.find_all(*DENY_STATEMENTS)):
            return GuardResult(False, "not_read_only")
        if any(tree.find_all(exp.Into)):
            return GuardResult(False, "not_read_only")
        for f in tree.find_all(exp.Func):
            name = _fname(f)
            if name.startswith(DENY_FUNCTION_PREFIXES):
                return GuardResult(False, f"function_not_allowed:{name}")
        ctes = {c.alias_or_name for c in tree.find_all(exp.CTE)}
        alias_to_table: dict[str, str] = {}
        rows = []
        for t in tree.find_all(exp.Table):
            if not isinstance(t.this, exp.Identifier):
                return GuardResult(False, "table_function_not_allowed")
            if t.catalog or (t.db and t.db != "main"):
                return GuardResult(False, f"schema_not_allowed:{t.db or t.catalog}")
            if t.name in ctes:
                continue
            if t.name not in self.tables:
                return GuardResult(False, f"table_not_allowed:{t.name}")
            alias_to_table[t.alias_or_name] = t.name
            rows.append(self.tables[t.name])
        referenced = set(alias_to_table.values())
        for c in tree.find_all(exp.Column):
            owner = alias_to_table.get(c.table) if c.table else None
            candidates = [owner] if owner else referenced
            for t in candidates:
                if f"{t}.{c.name}" in self.hidden:
                    return GuardResult(False, f"column_restricted:{t}.{c.name}")
        cross = any(
            j.args.get("kind") == "CROSS" or (j.args.get("on") is None and not j.args.get("using"))
            for j in tree.find_all(exp.Join)
        )
        cost = math.prod(rows) if cross else sum(rows)
        if cost > self.cost_limit:
            return GuardResult(False, "query_cost_limit", cost=cost)
        limit = tree.args.get("limit")
        if isinstance(tree, exp.Select):
            current = int(limit.expression.name) if limit is not None and limit.expression.is_int else None
            if current is None or current > self.max_rows:
                tree = tree.limit(self.max_rows)
            out = tree.sql(dialect="duckdb")
        else:
            out = f"SELECT * FROM ({tree.sql(dialect='duckdb')}) AS q LIMIT {self.max_rows}"
        return GuardResult(True, sql=out, cost=cost)


class OutputGuard:
    def __init__(self, unmask_pii: bool, max_rows: int = MAX_ROWS) -> None:
        self.unmask = unmask_pii
        self.max_rows = max_rows

    def clean(self, rows: list[tuple]) -> tuple[list[tuple], int]:
        masked = 0
        out = []
        for r in rows[: self.max_rows]:
            new = []
            for v in r:
                if isinstance(v, str) and not self.unmask and (EMAIL.search(v) or PHONE.search(v)):
                    v = PHONE.sub("***-****-****", EMAIL.sub("[email]", v))
                    masked += 1
                new.append(v)
            out.append(tuple(new))
        return out, masked
