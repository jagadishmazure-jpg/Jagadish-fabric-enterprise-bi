"""Data product contracts (contracts/products/*.yaml): what a team publishes and promises.

A product names its owner, output ports (the tables or Eventhouse outputs consumers read), the
schema contracts that must hold, a sensitivity label, service levels (freshness, quality), its
consumers and how it may be shared (internal OneLake shortcut, external share). `validate_product`
checks the contract is complete and internally consistent; `health` combines freshness and the
quality gate into one status per product."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from fabricbi.governance.labels import LABELS
from fabricbi.paths import CONTRACTS_DIR

REQUIRED = (
    "name",
    "version",
    "domain",
    "owner",
    "description",
    "output_ports",
    "schema_contracts",
    "sensitivity",
    "slo",
    "consumers",
    "sharing",
)
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def load_products(base: Path = CONTRACTS_DIR / "products") -> dict[str, dict]:
    return {p.stem: yaml.safe_load(p.read_text()) for p in sorted(base.glob("*.yaml"))}


def validate_product(p: dict, schema_names: set[str]) -> list[str]:
    errs = [f"missing {k}" for k in REQUIRED if k not in p]
    if errs:
        return errs
    if not SEMVER.match(str(p["version"])):
        errs.append("version must be semver")
    if p["sensitivity"] not in LABELS:
        errs.append(f"unknown sensitivity {p['sensitivity']}")
    for s in p["schema_contracts"]:
        if s not in schema_names:
            errs.append(f"schema contract {s} not found")
        if s not in p["output_ports"]:
            errs.append(f"schema contract {s} is not an output port")
    if not p["consumers"]:
        errs.append("a product needs at least one consumer")
    if p["slo"].get("freshness_hours", 0) <= 0:
        errs.append("freshness_hours must be positive")
    return errs


def consumers_by_asset(products: dict[str, dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for p in products.values():
        for port in p["output_ports"]:
            out.setdefault(port, []).extend(p["consumers"])
    return out


def bump_for(change: str, version: str) -> str:
    """Next version for a contract change classified by coldpath.contracts.compatibility."""
    major, minor, patch = (int(x) for x in version.split("."))
    if change == "breaking":
        return f"{major + 1}.0.0"
    if change == "additive":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"
