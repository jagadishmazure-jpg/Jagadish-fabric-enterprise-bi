"""Generate the checked-in contracts from code, or check they are current (CI).

    python scripts/export_contracts.py          # write
    python scripts/export_contracts.py --check  # exit 1 if anything is stale

Writes:
  control-plane/agent-card.json        A2A card (eval score from evals/baseline.json)
  control-plane/mcp-tools.json         MCP tool definitions
  fabric/workspace/sm_retail_sales.SemanticModel/definition/**.tmdl   TMDL from the semantic model
  fabric/workspace/kqldb_retail.KQLDatabase/DatabaseSchema.kql        from kql/tables.kql"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fabricbi.serve.a2a import agent_card  # noqa: E402
from fabricbi.serve.mcp_server import TOOLS  # noqa: E402
from fabricbi.serve.semantic import SemanticModel  # noqa: E402

SM_DIR = ROOT / "fabric" / "workspace" / "sm_retail_sales.SemanticModel"
KQLDB = ROOT / "fabric" / "workspace" / "kqldb_retail.KQLDatabase" / "DatabaseSchema.kql"


def expected() -> dict[Path, str]:
    baseline = json.loads((ROOT / "evals" / "baseline.json").read_text())
    out = {
        ROOT / "control-plane" / "agent-card.json": json.dumps(
            agent_card(eval_score=baseline["nl2sql_execution_accuracy"]), indent=2, sort_keys=True
        )
        + "\n",
        ROOT / "control-plane" / "mcp-tools.json": json.dumps(
            {"server": "fabric-data-agent", "tools": TOOLS}, indent=2, sort_keys=True
        )
        + "\n",
        KQLDB: "// Generated from kql/tables.kql by scripts/export_contracts.py. Do not edit.\n"
        + (ROOT / "kql" / "tables.kql").read_text(),
    }
    for rel, text in SemanticModel.load().to_tmdl().items():
        out[SM_DIR / rel] = text.rstrip("\n") + "\n"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    stale = []
    for path, text in expected().items():
        if a.check:
            if not path.exists() or path.read_text() != text:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    if stale:
        print("stale generated files:\n  " + "\n  ".join(stale))
        return 1
    print("contracts", "current" if a.check else "written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
