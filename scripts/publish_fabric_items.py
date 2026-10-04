"""Publish the Fabric workspace items in fabric/workspace with fabric-cicd (deploy pipeline only).

    python scripts/publish_fabric_items.py --workspace-id <guid> --environment dev

Needs `pip install fabric-cicd azure-identity` and an Azure CLI login (the pipeline's OIDC
login). Never run by tests or CI; the import is inside main() so the repo installs without it."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITEM_TYPES = ["Lakehouse", "Eventhouse", "KQLDatabase", "Notebook", "SemanticModel"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace-id", required=True)
    ap.add_argument("--environment", choices=["dev", "prod"], required=True)
    a = ap.parse_args(argv)
    from azure.identity import AzureCliCredential
    from fabric_cicd import FabricWorkspace, publish_all_items, unpublish_all_orphan_items

    ws = FabricWorkspace(
        workspace_id=a.workspace_id,
        environment=a.environment,
        repository_directory=str(ROOT / "fabric" / "workspace"),
        item_type_in_scope=ITEM_TYPES,
        token_credential=AzureCliCredential(),
    )
    publish_all_items(ws)
    unpublish_all_orphan_items(ws)
    print(f"published {', '.join(ITEM_TYPES)} to workspace {a.workspace_id} ({a.environment})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
