"""HorizonDB-to-Fabric mirroring, offline.

Microsoft Fabric HorizonDB (preview) is serverless PostgreSQL. The Fabric Updates Blog says its
tables are replicated into OneLake by default and converted to Delta, without a separate
integration pipeline. This module keeps that contract on a local stand-in:

* `HorizonSource` is the operational database. Every insert, update and delete is appended to
  `cdc_log` with a monotonic LSN in the same transaction. The posts do not publish the
  change-capture protocol, so the log is a mock, not a claim about PostgreSQL replication.
* `HorizonMirror.sync` reads changes after its checkpoint, applies them in LSN order (upsert by
  `redemption_id`, delete by key), checks the replica against the schema contract, writes Parquet
  (the OneLake stand-in; Fabric writes Delta) and then advances the checkpoint.

A contract failure writes nothing and leaves the checkpoint where it was, so the same change is
retried. Replays are idempotent.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from fabricbi.coldpath.contracts import load, validate

TABLE = "loyalty_redemptions"
COLUMNS = ("redemption_id", "store_id", "region", "member_id", "points", "redeemed_on")
CONTRACT = "mirror.horizondb_loyalty_redemption"

# Fixed rows for the doc example. Dates are day labels, not calendar dates.
DEMO_ROWS = (
    {
        "redemption_id": "R-100",
        "store_id": "S001",
        "region": "West",
        "member_id": "C00010",
        "points": 40,
        "redeemed_on": "D01",
    },
    {
        "redemption_id": "R-101",
        "store_id": "S002",
        "region": "North",
        "member_id": "C00011",
        "points": 15,
        "redeemed_on": "D01",
    },
    {
        "redemption_id": "R-102",
        "store_id": "S003",
        "region": "East",
        "member_id": "C00012",
        "points": 80,
        "redeemed_on": "D02",
    },
    {
        "redemption_id": "R-103",
        "store_id": "S004",
        "region": "South",
        "member_id": "C00013",
        "points": 25,
        "redeemed_on": "D02",
    },
)


class HorizonContractError(ValueError):
    """The replica would break the published schema, so the checkpoint did not move."""

    def __init__(self, violations: list) -> None:
        self.violations = violations
        detail = ", ".join(f"{v.column}:{v.rule}" for v in violations)
        super().__init__(detail or "schema contract failed")


@dataclass
class SyncStats:
    applied: int = 0
    inserts: int = 0
    updates: int = 0
    deletes: int = 0
    from_lsn: int = 0
    to_lsn: int = 0
    rows: int = 0


class HorizonSource:
    """SQLite stand-in for a Fabric HorizonDB table, with a change log."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS loyalty_redemptions (
                redemption_id TEXT PRIMARY KEY,
                store_id TEXT NOT NULL,
                region TEXT NOT NULL,
                member_id TEXT NOT NULL,
                points INTEGER NOT NULL,
                redeemed_on TEXT NOT NULL
            )"""
        )
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS cdc_log (
                lsn INTEGER PRIMARY KEY AUTOINCREMENT,
                op TEXT NOT NULL,
                redemption_id TEXT NOT NULL,
                payload TEXT
            )"""
        )
        self.conn.commit()

    def seed_demo(self) -> None:
        for row in DEMO_ROWS:
            self.insert(row)

    def insert(self, row: dict) -> None:
        values = [row[c] for c in COLUMNS]
        with self.conn:
            self.conn.execute(
                f"INSERT INTO {TABLE} ({', '.join(COLUMNS)}) VALUES ({', '.join('?' for _ in COLUMNS)})",
                values,
            )
            self._log("insert", row["redemption_id"], {c: row[c] for c in COLUMNS})

    def update(self, redemption_id: str, changes: dict) -> None:
        sets = ", ".join(f"{c}=?" for c in changes)
        with self.conn:
            self.conn.execute(
                f"UPDATE {TABLE} SET {sets} WHERE redemption_id=?",
                [*changes.values(), redemption_id],
            )
            row = self._row(redemption_id)
            self._log("update", redemption_id, row)

    def delete(self, redemption_id: str) -> None:
        with self.conn:
            self.conn.execute(f"DELETE FROM {TABLE} WHERE redemption_id=?", [redemption_id])
            self._log("delete", redemption_id, {})

    def _row(self, redemption_id: str) -> dict:
        cur = self.conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM {TABLE} WHERE redemption_id=?", [redemption_id]
        )
        values = cur.fetchone()
        if values is None:
            raise KeyError(redemption_id)
        return dict(zip(COLUMNS, values, strict=True))

    def _log(self, op: str, redemption_id: str, payload: dict) -> None:
        self.conn.execute(
            "INSERT INTO cdc_log (op, redemption_id, payload) VALUES (?,?,?)",
            [op, redemption_id, json.dumps(payload)],
        )

    def changes_after(self, lsn: int) -> list[tuple[int, str, str, dict]]:
        cur = self.conn.execute(
            "SELECT lsn, op, redemption_id, payload FROM cdc_log WHERE lsn > ? ORDER BY lsn",
            [lsn],
        )
        return [(r[0], r[1], r[2], json.loads(r[3])) for r in cur.fetchall()]

    def max_lsn(self) -> int:
        return self.conn.execute("SELECT COALESCE(MAX(lsn), 0) FROM cdc_log").fetchone()[0]

    def table(self) -> pd.DataFrame:
        return pd.read_sql(f"SELECT {', '.join(COLUMNS)} FROM {TABLE} ORDER BY redemption_id", self.conn)

    def close(self) -> None:
        self.conn.close()


class HorizonMirror:
    """Read-only replica under `<lake>/mirror_horizondb/Tables`."""

    def __init__(self, lake_root: Path) -> None:
        self.dir = Path(lake_root) / "mirror_horizondb" / "Tables"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir.parent / "_checkpoint.json"
        self.parquet = self.dir / f"{TABLE}.parquet"

    @property
    def checkpoint(self) -> int:
        if not self.state_path.exists():
            return 0
        return int(json.loads(self.state_path.read_text())["lsn"])

    def _load(self) -> dict[str, dict]:
        if not self.parquet.exists():
            return {}
        frame = pd.read_parquet(self.parquet)
        return {r["redemption_id"]: r for r in frame.to_dict("records")}

    def sync(
        self, source: HorizonSource, max_changes: int | None = None, save_checkpoint: bool = True
    ) -> SyncStats:
        start = self.checkpoint
        changes = source.changes_after(start)
        if max_changes is not None:
            changes = changes[:max_changes]
        stats = SyncStats(from_lsn=start, to_lsn=start)
        state = self._load()
        for lsn, op, key, payload in changes:
            if op == "delete":
                state.pop(key, None)
                stats.deletes += 1
            else:
                state[key] = payload
                stats.inserts += op == "insert"
                stats.updates += op == "update"
            stats.applied += 1
            stats.to_lsn = lsn
        frame = _frame(state)
        violations = validate(frame, load(CONTRACT))
        if violations:
            raise HorizonContractError(violations)
        frame.to_parquet(self.parquet, index=False)
        stats.rows = len(frame)
        if save_checkpoint:
            self.state_path.write_text(json.dumps({"lsn": stats.to_lsn}))
        return stats

    def lag(self, source: HorizonSource) -> int:
        """Replication lag in change-log entries."""
        return source.max_lsn() - self.checkpoint

    def read(self) -> pd.DataFrame:
        return pd.read_parquet(self.parquet)


def _frame(state: dict[str, dict]) -> pd.DataFrame:
    rows = [state[k] for k in sorted(state)]
    if not rows:
        return pd.DataFrame({c: pd.Series(dtype="int64" if c == "points" else "object") for c in COLUMNS})
    frame = pd.DataFrame(rows, columns=list(COLUMNS))
    frame["points"] = frame["points"].astype("int64")
    return frame
