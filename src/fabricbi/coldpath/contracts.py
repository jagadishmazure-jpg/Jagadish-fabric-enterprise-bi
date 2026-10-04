"""Schema contracts: YAML files that say what a table must look like, checked on every write.

A contract (contracts/schemas/<layer>.<table>.yaml) lists columns with a logical type, whether
nulls are allowed, uniqueness, accepted values and numeric ranges, plus the primary key. Two
things use it:

* `validate(df, contract)` returns every violation, so a write can fail before bad data lands.
* `compatibility(old, new)` classifies a contract change as breaking (column removed, type
  changed, nullable column made required, key changed) or additive, which is how a data product
  version bump is decided (major for breaking, minor for additive)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from fabricbi.paths import CONTRACTS_DIR

TYPE_CHECKS = {
    "string": lambda s: pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s),
    "int": pd.api.types.is_integer_dtype,
    "float": lambda s: pd.api.types.is_float_dtype(s) or pd.api.types.is_integer_dtype(s),
    "bool": pd.api.types.is_bool_dtype,
    "date": lambda s: pd.api.types.is_datetime64_any_dtype(s) or pd.api.types.is_object_dtype(s),
    "timestamp": pd.api.types.is_datetime64_any_dtype,
}


@dataclass(frozen=True)
class Violation:
    table: str
    column: str
    rule: str
    detail: str


def load(name: str, base: Path = CONTRACTS_DIR / "schemas") -> dict:
    return yaml.safe_load((base / f"{name}.yaml").read_text())


def all_contracts(base: Path = CONTRACTS_DIR / "schemas") -> dict[str, dict]:
    return {p.stem: yaml.safe_load(p.read_text()) for p in sorted(base.glob("*.yaml"))}


def validate(df: pd.DataFrame, contract: dict) -> list[Violation]:
    t = contract["table"]
    out: list[Violation] = []
    declared = {c["name"]: c for c in contract["columns"]}
    for name, col in declared.items():
        if name not in df.columns:
            out.append(Violation(t, name, "missing_column", "declared in contract, absent in data"))
            continue
        s = df[name]
        if not TYPE_CHECKS[col["type"]](s):
            out.append(Violation(t, name, "type", f"expected {col['type']}, got {s.dtype}"))
        if not col.get("nullable", True) and s.isna().any():
            out.append(Violation(t, name, "not_null", f"{int(s.isna().sum())} null value(s)"))
        if col.get("unique") and s.duplicated().any():
            out.append(Violation(t, name, "unique", f"{int(s.duplicated().sum())} duplicate value(s)"))
        if "accepted_values" in col:
            bad = set(s.dropna().unique()) - set(col["accepted_values"])
            if bad:
                out.append(Violation(t, name, "accepted_values", f"unexpected {sorted(map(str, bad))[:5]}"))
        if "min" in col and (s.dropna() < col["min"]).any():
            out.append(Violation(t, name, "min", f"values below {col['min']}"))
        if "max" in col and (s.dropna() > col["max"]).any():
            out.append(Violation(t, name, "max", f"values above {col['max']}"))
    if not contract.get("allow_extra_columns", False):
        for extra in set(df.columns) - set(declared):
            out.append(Violation(t, extra, "undeclared_column", "present in data, not in contract"))
    key = contract.get("primary_key")
    if key and all(k in df.columns for k in key) and df.duplicated(subset=key).any():
        out.append(Violation(t, ",".join(key), "primary_key", "duplicate key rows"))
    return out


def compatibility(old: dict, new: dict) -> tuple[str, list[str]]:
    """Return ("breaking" | "additive" | "none", reasons)."""
    reasons_b, reasons_a = [], []
    o = {c["name"]: c for c in old["columns"]}
    n = {c["name"]: c for c in new["columns"]}
    for name, col in o.items():
        if name not in n:
            reasons_b.append(f"column {name} removed")
            continue
        if n[name]["type"] != col["type"]:
            reasons_b.append(f"column {name} type {col['type']} -> {n[name]['type']}")
        if col.get("nullable", True) and not n[name].get("nullable", True):
            reasons_b.append(f"column {name} became required")
    for name, col in n.items():
        if name not in o:
            (reasons_a if col.get("nullable", True) else reasons_b).append(
                f"column {name} added" + ("" if col.get("nullable", True) else " as required")
            )
    if old.get("primary_key") != new.get("primary_key"):
        reasons_b.append("primary key changed")
    if reasons_b:
        return "breaking", reasons_b + reasons_a
    return ("additive", reasons_a) if reasons_a else ("none", [])
