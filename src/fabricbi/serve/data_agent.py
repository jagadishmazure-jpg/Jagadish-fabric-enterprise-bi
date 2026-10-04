"""The Fabric-style data agent: answers business questions over the gold model, safely.

    ask(question, principal)
      1. InputGuard            refuse injection attempts and oversized questions
      2. NL-to-SQL model       question + semantic model -> SQL (mocked Foundry model)
      3. measure permissions   finance-only measures refused for other roles
      4. SqlGuard              read-only, allow-listed, no restricted columns, cost limit, row cap
      5. SecureSession         runs under the caller's RLS / OLS / masking, with a timeout
      6. OutputGuard           PII backstop, row cap
      7. answer                rows + the SQL + measures used + a one-line summary, and telemetry

Every refusal has a machine-readable reason, so callers (MCP clients, A2A agents) can tell a
policy refusal from a failure. In Fabric the equivalent is a data agent item over the Lakehouse
and semantic model; this class keeps the same contract offline."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from fabricbi.coldpath.lakehouse import Lakehouse
from fabricbi.observability.telemetry import Telemetry
from fabricbi.serve.access import Principal, SecureSession, cost_limit, load_policy
from fabricbi.serve.guardrails import InputGuard, OutputGuard, SqlGuard
from fabricbi.serve.nl2sql import CANNOT, MockNl2SqlModel
from fabricbi.serve.semantic import SemanticModel


@dataclass
class Answer:
    status: str  # answered | refused | cannot_answer | error
    reason: str = ""
    sql: str = ""
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    summary: str = ""
    cost: int = 0
    measures: list[str] = field(default_factory=list)
    trace_id: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "reason": self.reason,
            "sql": self.sql,
            "columns": self.columns,
            "rows": [list(r) for r in self.rows],
            "summary": self.summary,
            "estimated_cost": self.cost,
            "measures": self.measures,
            "trace_id": self.trace_id,
        }


def _fmt(v) -> str:
    return f"{v:,.2f}" if isinstance(v, float) else str(v)


class DataAgent:
    def __init__(
        self,
        lake: Lakehouse,
        model: SemanticModel | None = None,
        llm=None,
        telemetry: Telemetry | None = None,
    ) -> None:
        self.lake = lake
        self.model = model or SemanticModel.load()
        self.policy = load_policy()
        self.telemetry = telemetry or Telemetry()
        if llm is None:
            stores = lake.read("gold", "dim_store")
            products = lake.read("gold", "dim_product")
            llm = MockNl2SqlModel(
                self.model, cities=tuple(stores.city), brands=tuple(products.brand.unique())
            )
        self.llm = llm

    def _done(self, a: Answer, t0: float) -> Answer:
        a.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        self.telemetry.add("fabricbi.agent.queries", 1, outcome=a.status, reason=a.reason or "none")
        self.telemetry.record("fabricbi.agent.duration", a.duration_ms, outcome=a.status)
        return a

    def ask(self, question: str, principal: Principal) -> Answer:
        t0 = time.perf_counter()
        trace = uuid.uuid4().hex
        with self.telemetry.span(
            "data_agent.ask", **{"enduser.id": principal.subject, "gen_ai.system": "foundry-mock"}
        ):
            g = InputGuard().check(question)
            if not g.allowed:
                return self._done(Answer("refused", g.reason, trace_id=trace), t0)
            if not principal.roles:
                return self._done(Answer("refused", "no_role", trace_id=trace), t0)
            session = SecureSession(self.lake, principal, self.policy)
            try:
                sql = self.llm.generate(question, session.max_date_key())
                if sql.strip() == CANNOT:
                    return self._done(
                        Answer(
                            "cannot_answer",
                            "no_matching_measure",
                            trace_id=trace,
                            summary="I could not map that question to a measure in the semantic model.",
                        ),
                        t0,
                    )
                used = [m for m in self.model.measures if f'"{m}"' in sql]
                for m in used:
                    need = self.model.measures[m].get("requires_role")
                    if need and not principal.has(need):
                        return self._done(
                            Answer("refused", f"measure_restricted:{m}", sql=sql, trace_id=trace), t0
                        )
                hidden = set() if principal.has("finance") else set(self.policy["ols"]["finance_only"])
                sg = SqlGuard(session.row_counts, hidden, cost_limit(principal, self.policy)).check(sql)
                if not sg.allowed:
                    return self._done(Answer("refused", sg.reason, sql=sql, cost=sg.cost, trace_id=trace), t0)
                try:
                    cols, rows = session.execute(sg.sql)
                except Exception as exc:  # duckdb raises its own error types
                    return self._done(Answer("error", type(exc).__name__, sql=sg.sql, trace_id=trace), t0)
                rows, _ = OutputGuard(principal.has("pii_reader")).clean(rows)
                summary = self._summarise(cols, rows, used)
                return self._done(
                    Answer(
                        "answered",
                        sql=sg.sql,
                        columns=cols,
                        rows=rows,
                        summary=summary,
                        cost=sg.cost,
                        measures=used,
                        trace_id=trace,
                    ),
                    t0,
                )
            finally:
                session.close()

    @staticmethod
    def _summarise(cols: list[str], rows: list[tuple], measures: list[str]) -> str:
        if not rows:
            return "No rows matched (you may not have access to that region)."
        if len(rows) == 1 and len(cols) == len(measures):
            return "; ".join(f"{c}: {_fmt(v)}" for c, v in zip(cols, rows[0], strict=True))
        head = ", ".join(f"{r[0]} {_fmt(r[-1])}" for r in rows[:5])
        more = f" (+{len(rows) - 5} more)" if len(rows) > 5 else ""
        return f"{cols[-1]} by {cols[0]}: {head}{more}"
