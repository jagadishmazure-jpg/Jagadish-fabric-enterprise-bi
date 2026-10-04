"""Row-level data quality rules with a quarantine, and a gate on the quarantine rate.

Silver transforms call `apply_rules(df, rules)`. Rows that break a rule are not dropped silently:
they go to a quarantine table with the rule name, so a data steward can see what was rejected and
why. `DqReport.passed(max_quarantine_rate)` is the gate the pipeline checks before it publishes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

Rule = tuple[str, Callable[[pd.DataFrame], pd.Series]]  # (name, mask of GOOD rows)


def not_null(col: str) -> Rule:
    return (f"not_null:{col}", lambda df: df[col].notna() & (df[col].astype(str) != ""))


def in_range(col: str, lo: float | None = None, hi: float | None = None) -> Rule:
    def check(df: pd.DataFrame) -> pd.Series:
        s = pd.to_numeric(df[col], errors="coerce")
        ok = s.notna()
        if lo is not None:
            ok &= s >= lo
        if hi is not None:
            ok &= s <= hi
        return ok

    return (f"range:{col}", check)


def references(col: str, valid: set, name: str) -> Rule:
    return (f"fk:{col}->{name}", lambda df: df[col].isin(valid))


def accepted(col: str, values: set) -> Rule:
    return (f"accepted:{col}", lambda df: df[col].isin(values))


@dataclass
class DqReport:
    table: str
    rows_in: int
    rows_out: int
    quarantined: int
    by_rule: dict[str, int] = field(default_factory=dict)

    @property
    def quarantine_rate(self) -> float:
        return self.quarantined / self.rows_in if self.rows_in else 0.0

    def passed(self, max_quarantine_rate: float = 0.02) -> bool:
        return self.quarantine_rate <= max_quarantine_rate


def apply_rules(
    df: pd.DataFrame, rules: list[Rule], table: str
) -> tuple[pd.DataFrame, pd.DataFrame, DqReport]:
    """Split df into (good, quarantine) and report counts per rule (first failing rule wins)."""
    reason = pd.Series([""] * len(df), index=df.index, dtype="object")
    by_rule: dict[str, int] = {}
    for name, check in rules:
        bad = ~check(df).fillna(False).astype(bool) & (reason == "")
        reason[bad] = name
        if bad.any():
            by_rule[name] = int(bad.sum())
    good = df[reason == ""].copy()
    quarantine = df[reason != ""].copy()
    quarantine["_dq_rule"] = reason[reason != ""]
    rep = DqReport(
        table=table, rows_in=len(df), rows_out=len(good), quarantined=len(quarantine), by_rule=by_rule
    )
    return good, quarantine, rep
