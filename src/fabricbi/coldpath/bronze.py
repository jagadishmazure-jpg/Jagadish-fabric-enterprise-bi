"""Bronze: land source files as they arrived, with ingest metadata, and never twice.

This is the Data Factory copy step (or a Fabric copy job) plus the first Lakehouse write. Files
are copied into `Files/landing/<source>/`, read with every column as text (bronze keeps what the
source sent, typing happens in silver) and written with three metadata columns:

  _source_file   file name the row came from
  _batch_id      id of the ingest batch
  _row_hash      hash of the raw row, used to spot exact duplicates downstream

A manifest of content hashes makes ingest idempotent: landing the same file again is a no-op."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

from fabricbi.context import RunContext
from fabricbi.domain.synth import SourceFiles


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _with_meta(df: pd.DataFrame, source: Path, batch: str) -> pd.DataFrame:
    df = df.astype(str)
    df["_row_hash"] = pd.util.hash_pandas_object(df, index=False).astype("uint64").astype(str)
    df["_source_file"] = source.name
    df["_batch_id"] = batch
    return df


class BronzeIngest:
    def __init__(self, ctx: RunContext) -> None:
        self.ctx = ctx
        self.manifest_path = ctx.lake.files_dir("landing") / "_manifest.json"

    def manifest(self) -> dict:
        return json.loads(self.manifest_path.read_text()) if self.manifest_path.exists() else {}

    def land(self, source: str, path: Path) -> bool:
        """Copy one file into the landing zone. Returns False if this exact content was seen before."""
        m = self.manifest()
        digest = _sha(path)
        if digest in m:
            return False
        shutil.copy2(path, self.ctx.lake.files_dir("landing", source) / path.name)
        m[digest] = {"source": source, "file": path.name, "batch": self.ctx.run_id}
        self.manifest_path.write_text(json.dumps(m, indent=1, sort_keys=True))
        return True

    def run(self, src: SourceFiles) -> dict[str, int]:
        ctx, batch = self.ctx, self.ctx.run_id
        with ctx.telemetry.span("bronze.ingest", **{"fabricbi.layer": "bronze"}):
            landed = {
                "pos": self.land("pos", src.pos_csv),
                "catalog": self.land("catalog", src.catalog_json),
                "freezer": self.land("freezer", src.sensor_csv),
                "tickets": self.land("tickets", src.tickets_jsonl),
            }
            if not any(landed.values()) and ctx.lake.exists("bronze", "pos_lines"):
                return {"skipped": 4}
            pos = _with_meta(pd.read_csv(src.pos_csv, dtype=str, keep_default_na=False), src.pos_csv, batch)
            ctx.write("bronze", "pos_lines", pos, ["source.pos_export"], "copy_pos_to_bronze")

            cat = json.loads(src.catalog_json.read_text())["products"]
            catalog = pd.DataFrame(
                {"sku": [p.get("sku", "") for p in cat], "raw_json": [json.dumps(p) for p in cat]}
            )
            catalog = _with_meta(catalog, src.catalog_json, batch)
            ctx.write(
                "bronze", "product_catalog", catalog, ["source.product_catalog"], "copy_catalog_to_bronze"
            )

            fz = _with_meta(pd.read_csv(src.sensor_csv, dtype=str), src.sensor_csv, batch)
            ctx.write("bronze", "freezer_readings", fz, ["source.freezer_history"], "copy_freezer_to_bronze")

            tk = _with_meta(
                pd.read_json(src.tickets_jsonl, lines=True, dtype=False), src.tickets_jsonl, batch
            )
            ctx.write("bronze", "support_tickets", tk, ["source.support_tickets"], "copy_tickets_to_bronze")
        return {
            "pos_lines": len(pos),
            "product_catalog": len(catalog),
            "freezer_readings": len(fz),
            "support_tickets": len(tk),
        }
