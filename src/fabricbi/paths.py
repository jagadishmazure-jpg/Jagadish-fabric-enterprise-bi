"""Repository paths and the local OneLake root.

`FABRICBI_LAKE` overrides where the local lake is written (default `.onelake/` in the repo, which
is git-ignored). Tests always point it at a temporary folder."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KQL_DIR = ROOT / "kql"
SEMANTIC_DIR = ROOT / "semantic-model"
CONTRACTS_DIR = ROOT / "contracts"
GOVERNANCE_DIR = ROOT / "governance"
FINOPS_DIR = ROOT / "finops"
DOCS_DIR = ROOT / "docs"
CONTROL_PLANE_DIR = ROOT / "control-plane"
FABRIC_DIR = ROOT / "fabric"


def lake_root() -> Path:
    return Path(os.environ.get("FABRICBI_LAKE", ROOT / ".onelake"))
