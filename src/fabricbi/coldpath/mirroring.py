"""Mirroring simulation: an operational database with a change log, replicated into the lake.

Fabric Mirroring keeps a near-real-time read-only replica of an operational database (Azure SQL,
Cosmos DB, and others) in OneLake by reading its change feed. This module reproduces the contract
on SQLite:

* `OperationalDb` is the source system. Every insert, update and delete is written to `cdc_log`
  with a monotonically increasing log sequence number (LSN) in the same transaction.
* `MirrorReplica.sync()` reads changes after its checkpoint LSN, applies them in LSN order (upsert
  by key, delete by key), writes the replica tables as Parquet and moves the checkpoint.

Replays are idempotent: syncing twice, or re-applying a batch after a crash before the checkpoint
was saved, gives the same replica."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

KEYS = {"stores": "store_id", "customers": "customer_id"}


class OperationalDb:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS cdc_log (lsn INTEGER PRIMARY KEY AUTOINCREMENT, tbl TEXT, op TEXT, k TEXT, payload TEXT)"
        )

    def seed(self, stores: pd.DataFrame, customers: pd.DataFrame) -> None:
        for name, df in (("stores", stores), ("customers", customers)):
            df.head(0).to_sql(name, self.conn, index=False, if_exists="replace")
            for row in df.to_dict("records"):
                self.insert(name, row)
        self.conn.commit()

    def insert(self, table: str, row: dict) -> None:
        cols = ",".join(row)
        qs = ",".join("?" for _ in row)
        with self.conn:
            self.conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({qs})", list(row.values()))
            self._log(table, "insert", row[KEYS[table]], row)

    def update(self, table: str, key: str, changes: dict) -> None:
        sets = ",".join(f"{c}=?" for c in changes)
        with self.conn:
            self.conn.execute(f"UPDATE {table} SET {sets} WHERE {KEYS[table]}=?", [*changes.values(), key])
            row = dict(
                zip(
                    [d[0] for d in self.conn.execute(f"SELECT * FROM {table} LIMIT 0").description],
                    self.conn.execute(f"SELECT * FROM {table} WHERE {KEYS[table]}=?", [key]).fetchone(),
                    strict=True,
                )
            )
            self._log(table, "update", key, row)

    def delete(self, table: str, key: str) -> None:
        with self.conn:
            self.conn.execute(f"DELETE FROM {table} WHERE {KEYS[table]}=?", [key])
            self._log(table, "delete", key, {})

    def _log(self, table: str, op: str, key: str, payload: dict) -> None:
        self.conn.execute(
            "INSERT INTO cdc_log (tbl, op, k, payload) VALUES (?,?,?,?)",
            [table, op, key, json.dumps(payload)],
        )

    def changes_after(self, lsn: int) -> list[tuple[int, str, str, str, dict]]:
        cur = self.conn.execute(
            "SELECT lsn, tbl, op, k, payload FROM cdc_log WHERE lsn > ? ORDER BY lsn", [lsn]
        )
        return [(r[0], r[1], r[2], r[3], json.loads(r[4])) for r in cur.fetchall()]

    def max_lsn(self) -> int:
        return self.conn.execute("SELECT COALESCE(MAX(lsn), 0) FROM cdc_log").fetchone()[0]

    def table(self, name: str) -> pd.DataFrame:
        return pd.read_sql(f"SELECT * FROM {name}", self.conn)

    def close(self) -> None:
        self.conn.close()


@dataclass
class SyncStats:
    applied: int = 0
    inserts: int = 0
    updates: int = 0
    deletes: int = 0
    from_lsn: int = 0
    to_lsn: int = 0
    tables: dict[str, int] = field(default_factory=dict)


class MirrorReplica:
    """Read-only replica of the operational DB under `<lake>/mirror_opdb/Tables`."""

    def __init__(self, lake_root: Path) -> None:
        self.dir = Path(lake_root) / "mirror_opdb" / "Tables"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir.parent / "_checkpoint.json"

    @property
    def checkpoint(self) -> int:
        return json.loads(self.state_path.read_text())["lsn"] if self.state_path.exists() else 0

    def _load(self, table: str) -> dict[str, dict]:
        p = self.dir / f"{table}.parquet"
        if not p.exists():
            return {}
        return {r[KEYS[table]]: r for r in pd.read_parquet(p).to_dict("records")}

    def sync(
        self, db: OperationalDb, max_changes: int | None = None, save_checkpoint: bool = True
    ) -> SyncStats:
        start = self.checkpoint
        changes = db.changes_after(start)
        if max_changes is not None:
            changes = changes[:max_changes]
        stats = SyncStats(from_lsn=start, to_lsn=start)
        state = {t: self._load(t) for t in KEYS}
        for lsn, tbl, op, key, payload in changes:
            if op == "delete":
                state[tbl].pop(key, None)
                stats.deletes += 1
            else:
                state[tbl][key] = payload  # upsert by key: replaying an insert or update is harmless
                stats.inserts += op == "insert"
                stats.updates += op == "update"
            stats.applied += 1
            stats.to_lsn = lsn
        for tbl, rows in state.items():
            df = pd.DataFrame(sorted(rows.values(), key=lambda r: r[KEYS[tbl]]))
            df.to_parquet(self.dir / f"{tbl}.parquet", index=False)
            stats.tables[tbl] = len(df)
        if save_checkpoint:
            self.state_path.write_text(json.dumps({"lsn": stats.to_lsn}))
        return stats

    def lag(self, db: OperationalDb) -> int:
        """Replication lag in change-log entries."""
        return db.max_lsn() - self.checkpoint

    def read(self, table: str) -> pd.DataFrame:
        return pd.read_parquet(self.dir / f"{table}.parquet")

    def path(self, table: str) -> Path:
        return self.dir / f"{table}.parquet"
