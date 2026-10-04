"""MCP server for the data agent (JSON-RPC 2.0 over stdio, Model Context Protocol tool calls).

Tools:
  ask_data_agent      a business question in plain language -> governed answer
  run_readonly_sql    SQL written by the calling agent, held to the same guards and session
  search_docs         vector search over docs, contracts and the semantic model (for RAG)
  describe_asset      catalog entry: owner, label, classified columns, lineage
  list_data_products  the data product contracts and their service levels

The caller's identity comes from the transport, never from tool arguments: for stdio it is
`FABRICBI_SUBJECT` set by the host that launches the server (behind APIM or the MCP gateway in
the integration platform repo it would come from the validated token). Unknown subjects get no
roles, so every data tool refuses.

Run: `FABRICBI_SUBJECT=west.manager@fernhill.example python -m fabricbi.serve.mcp_server`"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fabricbi.coldpath.lakehouse import Lakehouse
from fabricbi.governance.catalog import Catalog
from fabricbi.governance.labels import clearance_for
from fabricbi.governance.lineage import LineageGraph
from fabricbi.governance.products import load_products
from fabricbi.paths import lake_root
from fabricbi.serve.access import Principal, SecureSession, cost_limit, resolve
from fabricbi.serve.data_agent import DataAgent
from fabricbi.serve.guardrails import OutputGuard, SqlGuard
from fabricbi.serve.vector_store import VectorStore

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "fabric-data-agent", "version": "0.1.0"}

TOOLS = [
    {
        "name": "ask_data_agent",
        "description": "Answer a business question about Fernhill Grocers sales, freezers or support tickets from the governed gold model. Returns rows, the SQL that ran and a summary. Results respect the caller's region and role.",
        "inputSchema": {
            "type": "object",
            "properties": {"question": {"type": "string", "maxLength": 400}},
            "required": ["question"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "run_readonly_sql",
        "description": "Run one read-only SELECT against the gold views (fact_sales, dim_store, dim_product, dim_customer, dim_date, agg_daily_sales, fact_freezer_daily, fact_ticket). Refused if it writes, reads files, touches restricted columns or exceeds the cost limit.",
        "inputSchema": {
            "type": "object",
            "properties": {"sql": {"type": "string", "maxLength": 4000}},
            "required": ["sql"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "search_docs",
        "description": "Search the data platform documentation, data product contracts and measure definitions. Use for questions about definitions, ownership, freshness and how the platform works.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "maxLength": 400},
                "k": {"type": "integer", "minimum": 1, "maximum": 8, "default": 3},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "describe_asset",
        "description": "Catalog entry for a table or other asset, e.g. gold.fact_sales: owner, sensitivity label, classified columns, upstream and downstream lineage.",
        "inputSchema": {
            "type": "object",
            "properties": {"asset": {"type": "string"}},
            "required": ["asset"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "list_data_products",
        "description": "List data products with owner, output tables, sensitivity and freshness service level.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
]


class DataAgentTools:
    """Tool implementations shared by the MCP server and the A2A agent."""

    def __init__(self, lake: Lakehouse, lineage: LineageGraph | None = None) -> None:
        self.lake = lake
        self.agent = DataAgent(lake)
        lp = Path(lake.root) / "_lineage.json"
        self.catalog = Catalog.build(
            lineage or (LineageGraph.load(lp) if lp.exists() else LineageGraph()), lake.metadata()
        )
        self._store: VectorStore | None = None

    @property
    def store(self) -> VectorStore:
        if self._store is None:
            self._store = VectorStore.build()
        return self._store

    def ask_data_agent(self, principal: Principal, question: str) -> dict:
        return self.agent.ask(question, principal).to_dict()

    def run_readonly_sql(self, principal: Principal, sql: str) -> dict:
        if not principal.roles:
            return {"status": "refused", "reason": "no_role"}
        s = SecureSession(self.lake, principal, self.agent.policy)
        try:
            hidden = set() if principal.has("finance") else set(self.agent.policy["ols"]["finance_only"])
            g = SqlGuard(s.row_counts, hidden, cost_limit(principal, self.agent.policy)).check(sql)
            if not g.allowed:
                self.agent.telemetry.add("fabricbi.agent.queries", 1, outcome="refused", reason=g.reason)
                return {"status": "refused", "reason": g.reason, "estimated_cost": g.cost}
            try:
                cols, rows = s.execute(g.sql)
            except Exception as exc:
                return {"status": "error", "reason": type(exc).__name__}
            rows, _ = OutputGuard(principal.has("pii_reader")).clean(rows)
            return {
                "status": "answered",
                "sql": g.sql,
                "columns": cols,
                "rows": [list(r) for r in rows],
                "estimated_cost": g.cost,
            }
        finally:
            s.close()

    def search_docs(self, principal: Principal, query: str, k: int = 3) -> dict:
        hits = self.store.search(query, k=k, clearance=clearance_for(principal.roles))
        return {
            "results": [
                {
                    "source": c.source,
                    "heading": c.heading,
                    "score": sc,
                    "label": c.label,
                    "text": c.text[:600],
                }
                for c, sc in hits
            ]
        }

    def describe_asset(self, principal: Principal, asset: str) -> dict:
        if asset not in self.catalog.entries:
            return {"status": "not_found", "matches": self.catalog.search(asset.split(".")[-1])[:5]}
        return self.catalog.describe(asset)

    def list_data_products(self, principal: Principal) -> dict:
        return {
            "products": [
                {
                    "name": p["name"],
                    "version": p["version"],
                    "owner": p["owner"],
                    "sensitivity": p["sensitivity"],
                    "output_ports": p["output_ports"],
                    "freshness_hours": p["slo"]["freshness_hours"],
                }
                for p in load_products().values()
            ]
        }


def _jsonable(o):
    return json.loads(json.dumps(o, default=str))


class McpServer:
    def __init__(self, tools: DataAgentTools, principal: Principal) -> None:
        self.tools = tools
        self.principal = principal
        self.initialized = False

    def handle(self, msg: dict) -> dict | None:
        mid, method = msg.get("id"), msg.get("method")
        if mid is None:  # notification, e.g. notifications/initialized
            if method == "notifications/initialized":
                self.initialized = True
            return None
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": SERVER_INFO,
                    "instructions": "Read-only governed access to the Fernhill gold model. Prefer ask_data_agent; use search_docs for definitions.",
                },
            }
        if method == "ping":
            return {"jsonrpc": "2.0", "id": mid, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
        if method == "tools/call":
            p = msg.get("params", {})
            name, args = p.get("name"), p.get("arguments", {}) or {}
            spec = next((t for t in TOOLS if t["name"] == name), None)
            if spec is None:
                return {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "error": {"code": -32602, "message": f"unknown tool {name}"},
                }
            allowed = set(spec["inputSchema"]["properties"])
            missing = [r for r in spec["inputSchema"].get("required", []) if r not in args]
            if set(args) - allowed or missing:
                return {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "error": {"code": -32602, "message": "invalid arguments"},
                }
            out = _jsonable(getattr(self.tools, name)(self.principal, **args))
            is_err = out.get("status") in ("refused", "error")
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(out)}],
                    "structuredContent": out,
                    "isError": is_err,
                },
            }
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "error": {"code": -32601, "message": f"method not found: {method}"},
        }


def serve_stdio(server: McpServer, stdin=sys.stdin, stdout=sys.stdout) -> None:
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            resp = server.handle(msg)
        if resp is not None:
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()


def main() -> None:
    lake = Lakehouse(lake_root())
    principal = resolve(os.environ.get("FABRICBI_SUBJECT", "anonymous"))
    serve_stdio(McpServer(DataAgentTools(lake), principal))


if __name__ == "__main__":
    main()
