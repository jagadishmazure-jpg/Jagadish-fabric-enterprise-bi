"""Who is asking, and what they may see: principals and the secure query session.

`SecureSession` is the sandbox every data agent query runs in. It is a fresh in-memory DuckDB
database per caller:

1. the gold tables are loaded into a hidden `base` schema;
2. one view per table is created in `main` with the caller's row-level filter (region), with
   finance-only columns removed (object-level security) and with personal data masked unless the
   caller holds `pii_reader`;
3. external access (files, HTTP, extensions) is switched off and the configuration is locked, so
   even a query that slipped past the SQL guard could not read the lake directly or undo the
   settings.

Only the `main` views are on the guard's allow-list, so the agent never touches `base`."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import yaml

from fabricbi.coldpath.lakehouse import Lakehouse
from fabricbi.paths import GOVERNANCE_DIR

AGENT_TABLES = (
    "fact_sales",
    "fact_freezer_daily",
    "fact_ticket",
    "agg_daily_sales",
    "dim_store",
    "dim_product",
    "dim_customer",
    "dim_date",
)
ALL_REGIONS = ("North", "South", "East", "West")


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()

    @property
    def all_regions(self) -> tuple[str, ...]:
        return ALL_REGIONS if "*" in self.regions else tuple(r for r in self.regions if r in ALL_REGIONS)

    def has(self, role: str) -> bool:
        return role in self.roles


def load_policy(path: Path = GOVERNANCE_DIR / "access-policy.yaml") -> dict:
    return yaml.safe_load(path.read_text())


def resolve(subject: str, path: Path = GOVERNANCE_DIR / "principals.yaml") -> Principal:
    """Identity stand-in for Entra ID group claims. Unknown subjects get no roles and no regions."""
    spec = yaml.safe_load(path.read_text())
    p = spec["principals"].get(subject, spec["default"])
    return Principal(subject, tuple(p["roles"]), tuple(p["regions"]))


def cost_limit(principal: Principal, policy: dict) -> int:
    limits = [policy["roles"][r]["query_cost_limit"] for r in principal.roles if r in policy["roles"]]
    return max(limits, default=0)


def _mask_expr(col: str, kind: str) -> str:
    if kind == "email":
        return f"CASE WHEN {col} = '' THEN '' ELSE left({col}, 1) || '***@' || split_part({col}, '@', 2) END AS {col}"
    return f"CASE WHEN {col} = '' THEN '' ELSE '***-****-' || right({col}, 4) END AS {col}"


@dataclass
class SecureSession:
    lake: Lakehouse
    principal: Principal
    policy: dict = field(default_factory=load_policy)
    timeout_s: float = 5.0

    def __post_init__(self) -> None:
        self.conn = duckdb.connect(":memory:")
        self.row_counts: dict[str, int] = {}
        self.columns: dict[str, list[str]] = {}
        self.conn.execute("CREATE SCHEMA base")
        regions = ", ".join(f"'{r}'" for r in self.principal.all_regions) or "NULL"
        hidden = set() if self.principal.has("finance") else set(self.policy["ols"]["finance_only"])
        masks = {} if self.principal.has("pii_reader") else self.policy["masking"]
        present = [t for t in AGENT_TABLES if self.lake.exists("gold", t)]
        for t in present:
            path = str(self.lake.table_path("gold", t)).replace("'", "''")
            self.conn.execute(f"CREATE TABLE base.{t} AS SELECT * FROM read_parquet('{path}')")
        for t in present:
            cols = [r[0] for r in self.conn.execute(f"DESCRIBE base.{t}").fetchall()]
            exprs = []
            for c in cols:
                fq = f"{t}.{c}"
                if fq in hidden:
                    continue
                exprs.append(_mask_expr(c, masks[fq]) if fq in masks else c)
            where = self.policy["rls"]["tables"].get(t)
            cond = f" WHERE {where.format(regions=regions)}" if where else ""
            self.conn.execute(f"CREATE VIEW main.{t} AS SELECT {', '.join(exprs)} FROM base.{t}{cond}")
            self.row_counts[t] = self.conn.execute(f"SELECT COUNT(*) FROM base.{t}").fetchone()[0]
            self.columns[t] = [c for c in cols if f"{t}.{c}" not in hidden]
        # lock the sandbox: no file/network access, no settings changes from here on
        self.conn.execute("SET enable_external_access = false")
        self.conn.execute("SET lock_configuration = true")

    @property
    def tables(self) -> list[str]:
        return list(self.row_counts)

    def max_date_key(self) -> int | None:
        if "fact_sales" not in self.row_counts:
            return None
        return self.conn.execute("SELECT MAX(date_key) FROM base.fact_sales").fetchone()[0]

    def execute(self, sql: str) -> tuple[list[str], list[tuple]]:
        timer = threading.Timer(self.timeout_s, self.conn.interrupt)
        timer.start()
        try:
            cur = self.conn.execute(sql)
            cols = [d[0] for d in cur.description]
            return cols, cur.fetchall()
        finally:
            timer.cancel()

    def close(self) -> None:
        self.conn.close()
