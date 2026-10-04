"""A2A agent for the data agent: an agent card plus a JSON-RPC `SendMessage` endpoint.

The card follows the A2A 1.0 shape used by the Jagadish-azure-agent-platform repo (supported
interfaces, skills, and a control-plane extension with owner, side-effect class and allowed
callers), so that platform's directory can register it and its A2A client can call it unchanged:

  request   {"method": "SendMessage", "params": {"message": {"parts": [{"data": {"skill", "input"}}]}}}
  headers   x-tenant-id, x-caller-agent, x-user-subject, traceparent
  response  {"result": {"message": {"role": "ROLE_AGENT", "parts": [{"data": {"skill", "output"}}]}}}

The server re-checks the caller against `allowed_callers` and the tenant on every request (defence
in depth behind the platform's own policy check) and runs the skill as the *end user* named in
x-user-subject, so row-level security follows the person, not the calling agent."""

from __future__ import annotations

import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fabricbi.serve.access import resolve
from fabricbi.serve.mcp_server import DataAgentTools

CONTROL_PLANE_EXT = "urn:agentplatform:control-plane:v1"
AGENT_ID = "fabric-data-agent"
ALLOWED_CALLERS = ("experience-bff", "underwriting-agent", "care-planner", "data-agent")
TENANTS = ("fernhill",)
SKILLS = {
    "ask_sales_question": (
        "Ask a sales or operations question",
        "Plain-language question over the governed gold model; respects the end user's region and role.",
        "ask_data_agent",
        "question",
    ),
    "search_data_docs": (
        "Search data documentation",
        "Retrieval over docs, data product contracts and measure definitions (for RAG grounding).",
        "search_docs",
        "query",
    ),
    "describe_data_asset": (
        "Describe a data asset",
        "Owner, sensitivity label, classified columns and lineage for a table.",
        "describe_asset",
        "asset",
    ),
}


def agent_card(url: str | None = None, eval_score: float | None = None) -> dict:
    url = (url or os.environ.get("A2A_FABRIC_DATA_AGENT_URL") or f"http://{AGENT_ID}.local").rstrip(
        "/"
    ) + "/a2a"
    return {
        "name": "Fabric Data Agent",
        "description": "Governed natural-language analytics over the Fernhill Grocers gold model (sales, freezers, tickets), with row-level security, PII masking and read-only SQL.",
        "version": "0.1.0",
        "provider": {
            "organization": "Fernhill Grocers (fictional demo)",
            "url": "https://github.com/jagadishmazure-jpg",
        },
        "supportedInterfaces": [{"protocolBinding": "JSONRPC", "protocolVersion": "1.0", "url": url}],
        "capabilities": {
            "streaming": False,
            "extensions": [
                {
                    "uri": CONTROL_PLANE_EXT,
                    "description": "Control-plane registration: owner, policy, side effects, eval gate",
                    "params": {
                        "agent_id": AGENT_ID,
                        "owner": "data-platform",
                        "side_effect_class": "read",
                        "skill_side_effects": {s: "read" for s in SKILLS},
                        "allowed_callers": list(ALLOWED_CALLERS),
                        "tenants": list(TENANTS),
                        "eval_score": eval_score if eval_score is not None else 0.0,
                        "stage": "dev",
                        "standin": False,
                        "requires_headers": [
                            "traceparent",
                            "x-tenant-id",
                            "x-caller-agent",
                            "x-user-subject",
                        ],
                        "system_of_record": "Microsoft Fabric OneLake (local stand-in)",
                        "model_deployment": "",
                        "prompt_refs": [],
                        "vendor_style": "",
                    },
                }
            ],
        },
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": [
            {
                "id": sid,
                "name": n,
                "description": f"{d} [side-effect: read]",
                "tags": ["analytics", "fabric"],
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
            }
            for sid, (n, d, _, _) in SKILLS.items()
        ],
    }


class A2AAgent:
    def __init__(self, tools: DataAgentTools) -> None:
        self.tools = tools

    def handle(self, body: dict, headers: dict) -> tuple[int, dict]:
        h = {k.lower(): v for k, v in headers.items()}
        rid = body.get("id")

        def err(code: int, message: str, http: int = 200) -> tuple[int, dict]:
            return http, {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}

        if body.get("method") != "SendMessage":
            return err(-32601, "method not found")
        if h.get("x-tenant-id") not in TENANTS:
            return err(-32003, "tenant not allowed", 403)
        if h.get("x-caller-agent") not in ALLOWED_CALLERS:
            return err(-32003, "caller not allowed", 403)
        parts = body.get("params", {}).get("message", {}).get("parts", [])
        data = parts[0].get("data") if parts else None
        if (
            not isinstance(data, dict)
            or data.get("skill") not in SKILLS
            or not isinstance(data.get("input"), dict)
        ):
            return err(-32602, "expected a data part with skill and input")
        _, _, tool, arg = SKILLS[data["skill"]]
        if arg not in data["input"]:
            return err(-32602, f"input.{arg} is required")
        principal = resolve(h.get("x-user-subject", "anonymous"))
        out = json.loads(json.dumps(getattr(self.tools, tool)(principal, data["input"][arg]), default=str))
        payload = {"skill": data["skill"], "output": out, "traceparent": h.get("traceparent", "")}
        if out.get("status") == "refused":
            payload = {"error": "refused", "detail": out.get("reason")}
        msg = {"messageId": uuid.uuid4().hex, "role": "ROLE_AGENT", "parts": [{"data": payload}]}
        return 200, {"jsonrpc": "2.0", "id": rid, "result": {"message": msg}}


def make_server(agent: A2AAgent, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep test output clean
            pass

        def _send(self, code: int, obj: dict) -> None:
            raw = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path == "/.well-known/agent-card.json":
                self._send(
                    200, agent_card(f"http://{self.server.server_address[0]}:{self.server.server_address[1]}")
                )
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/a2a":
                return self._send(404, {"error": "not found"})
            n = int(self.headers.get("content-length", 0))
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._send(
                    400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
                )
            code, obj = agent.handle(body, dict(self.headers))
            self._send(code, obj)

    return ThreadingHTTPServer((host, port), Handler)


def serve_background(agent: A2AAgent) -> tuple[ThreadingHTTPServer, threading.Thread]:
    srv = make_server(agent)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, t


if __name__ == "__main__":
    from fabricbi.coldpath.lakehouse import Lakehouse
    from fabricbi.paths import lake_root

    port = int(os.environ.get("PORT", "8460"))
    srv = make_server(A2AAgent(DataAgentTools(Lakehouse(lake_root()))), "127.0.0.1", port)
    print(f"fabric-data-agent A2A on http://127.0.0.1:{port} (card at /.well-known/agent-card.json)")
    srv.serve_forever()
