"""A local stand-in for OneLake: one folder per item, Parquet per table, plus shortcuts.

Layout under the lake root:

    lh_retail/Tables/<layer>__<table>.parquet   Lakehouse tables (bronze, silver, gold)
    lh_retail/Files/...                          raw landing files copied in by the ingest step
    mirror_opdb/Tables/<table>.parquet           mirrored replica of the operational database
    eh_retail/...                                Eventhouse stand-in (hot-path window output)
    _shortcuts.json                              shortcut name -> target path (internal or external)

Each table write also records a small metadata entry (row count, column types, run id) that the
catalog, freshness SLOs and lineage read. Fabric stores Delta tables; Parquet keeps this offline
and dependency-light, and the table contract is the same."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

LAYERS = ("bronze", "silver", "gold")


@dataclass
class Lakehouse:
    root: Path
    item: str = "lh_retail"

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        (self.root / self.item / "Tables").mkdir(parents=True, exist_ok=True)
        (self.root / self.item / "Files").mkdir(parents=True, exist_ok=True)

    # ---- tables ----
    def table_path(self, layer: str, name: str) -> Path:
        if layer not in LAYERS:
            raise ValueError(f"unknown layer {layer!r}")
        return self.root / self.item / "Tables" / f"{layer}__{name}.parquet"

    def write(
        self, layer: str, name: str, df: pd.DataFrame, run_id: str = "local", logical_time: str = ""
    ) -> Path:
        path = self.table_path(layer, name)
        df.to_parquet(path, index=False)
        meta = self._meta()
        meta[f"{layer}.{name}"] = {
            "rows": len(df),
            "columns": {c: str(t) for c, t in df.dtypes.items()},
            "run_id": run_id,
            "logical_time": logical_time,
        }
        self._meta_path().write_text(json.dumps(meta, indent=1, sort_keys=True))
        return path

    def read(self, layer: str, name: str) -> pd.DataFrame:
        return pd.read_parquet(self.table_path(layer, name))

    def exists(self, layer: str, name: str) -> bool:
        return self.table_path(layer, name).exists()

    def tables(self, layer: str | None = None) -> list[str]:
        out = []
        for p in sorted((self.root / self.item / "Tables").glob("*.parquet")):
            lyr, name = p.stem.split("__", 1)
            if layer is None or lyr == layer:
                out.append(f"{lyr}.{name}")
        return out

    def metadata(self) -> dict:
        return self._meta()

    def _meta_path(self) -> Path:
        return self.root / self.item / "_tables.json"

    def _meta(self) -> dict:
        p = self._meta_path()
        return json.loads(p.read_text()) if p.exists() else {}

    # ---- files ----
    def files_dir(self, *parts: str) -> Path:
        p = self.root / self.item / "Files" / Path(*parts)
        p.mkdir(parents=True, exist_ok=True)
        return p

    # ---- shortcuts ----
    def add_shortcut(self, name: str, target: Path, kind: str = "internal") -> None:
        """Register a OneLake-style shortcut: a name that resolves to data stored elsewhere.

        kind is `internal` (another item in the same lake) or `external` (for example an ADLS Gen2
        container shared with a partner). Reads go through the target; nothing is copied."""
        if kind not in ("internal", "external"):
            raise ValueError("shortcut kind must be internal or external")
        sc = self.shortcuts()
        sc[name] = {"target": str(target), "kind": kind}
        (self.root / "_shortcuts.json").write_text(json.dumps(sc, indent=1, sort_keys=True))

    def shortcuts(self) -> dict:
        p = self.root / "_shortcuts.json"
        return json.loads(p.read_text()) if p.exists() else {}

    def read_shortcut(self, name: str) -> pd.DataFrame:
        sc = self.shortcuts()
        if name not in sc:
            raise KeyError(f"no shortcut named {name!r}")
        return pd.read_parquet(sc[name]["target"])
