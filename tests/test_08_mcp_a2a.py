import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

import pytest

from fabricbi.paths import ROOT
from fabricbi.serve.a2a import A2AAgent, agent_card, serve_background
from fabricbi.serve.mcp_server import TOOLS, McpServer

HDRS = {
    "x-tenant-id": "fernhill",
    "x-caller-agent": "experience-bff",
    "x-user-subject": "west.manager@fernhill.example",
    "traceparent": "00-" + "a" * 32 + "-" + "b" * 16 + "-01",
}


def _send(skill, inp):
    return {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "SendMessage",
        "params": {
            "message": {
                "role": "ROLE_USER",
                "messageId": "m1",
                "parts": [{"data": {"skill": skill, "input": inp}}],
            }
        },
    }


@pytest.fixture
def mcp(tools, who):
    return McpServer(tools, who("exec.viewer"))


def test_mcp_initialize_and_list(mcp):
    r = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert r["result"]["serverInfo"]["name"] == "fabric-data-agent"
    assert mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    names = {
        t["name"] for t in mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    }
    assert names == {
        "ask_data_agent",
        "run_readonly_sql",
        "search_docs",
        "describe_asset",
        "list_data_products",
    }


def test_mcp_tool_call_answers(mcp):
    r = mcp.handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "ask_data_agent", "arguments": {"question": "Net sales by region"}},
        }
    )
    out = r["result"]["structuredContent"]
    assert out["status"] == "answered" and len(out["rows"]) == 4
    assert r["result"]["isError"] is False


def test_mcp_refusal_is_an_error_result(mcp):
    r = mcp.handle(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "run_readonly_sql", "arguments": {"sql": "DELETE FROM fact_sales"}},
        }
    )
    assert r["result"]["isError"] is True


def test_mcp_rejects_unknown_tool_and_extra_args(mcp):
    assert (
        mcp.handle(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "drop_all", "arguments": {}},
            }
        )["error"]["code"]
        == -32602
    )
    bad = mcp.handle(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "search_docs", "arguments": {"query": "x", "path": "/etc"}},
        }
    )
    assert bad["error"]["code"] == -32602
    assert mcp.handle({"jsonrpc": "2.0", "id": 7, "method": "resources/list"})["error"]["code"] == -32601


def test_mcp_tool_schemas_forbid_extra_properties():
    for t in TOOLS:
        assert t["inputSchema"]["type"] == "object"
        assert t["inputSchema"].get("additionalProperties") is False, t["name"]


def test_mcp_over_stdio_subprocess(run):
    env = {
        **os.environ,
        "FABRICBI_LAKE": str(run.ctx.lake_root),
        "FABRICBI_SUBJECT": "north.manager@fernhill.example",
        "PYTHONPATH": str(ROOT / "src"),
    }
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "ask_data_agent", "arguments": {"question": "Net sales by region"}},
        },
    ]
    p = subprocess.run(
        [sys.executable, "-m", "fabricbi.serve.mcp_server"],
        input="\n".join(json.dumps(m) for m in msgs) + "\nnot json\n",
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    lines = [json.loads(x) for x in p.stdout.splitlines()]
    assert len(lines) == 3
    rows = lines[1]["result"]["structuredContent"]["rows"]
    assert [r[0] for r in rows] == ["North"]
    assert lines[2]["error"]["code"] == -32700


def test_agent_card_shape():
    c = agent_card()
    assert c["supportedInterfaces"][0]["protocolBinding"] == "JSONRPC"
    ext = c["capabilities"]["extensions"][0]
    assert ext["uri"] == "urn:agentplatform:control-plane:v1"
    assert ext["params"]["side_effect_class"] == "read"
    assert {s["id"] for s in c["skills"]} == {"ask_sales_question", "search_data_docs", "describe_data_asset"}


def test_a2a_answers_with_end_user_rls(tools):
    code, r = A2AAgent(tools).handle(_send("ask_sales_question", {"question": "Net sales by region"}), HDRS)
    assert code == 200
    out = r["result"]["message"]["parts"][0]["data"]["output"]
    assert [row[0] for row in out["rows"]] == ["West"]


@pytest.mark.parametrize("header,value", [("x-tenant-id", "other"), ("x-caller-agent", "random-agent")])
def test_a2a_refuses_unknown_tenant_or_caller(tools, header, value):
    code, r = A2AAgent(tools).handle(
        _send("ask_sales_question", {"question": "Units"}), {**HDRS, header: value}
    )
    assert code == 403 and r["error"]["code"] == -32003


def test_a2a_validates_skill_and_input(tools):
    a = A2AAgent(tools)
    assert a.handle(_send("drop_tables", {"x": 1}), HDRS)[1]["error"]["code"] == -32602
    assert a.handle(_send("search_data_docs", {"q": "x"}), HDRS)[1]["error"]["code"] == -32602
    assert a.handle({"jsonrpc": "2.0", "id": "2", "method": "GetTask"}, HDRS)[1]["error"]["code"] == -32601


def test_a2a_refusal_is_reported(tools):
    _code, r = A2AAgent(tools).handle(
        _send("ask_sales_question", {"question": "Gross margin by region"}), HDRS
    )
    assert r["result"]["message"]["parts"][0]["data"] == {
        "error": "refused",
        "detail": "measure_restricted:Gross Margin",
    }


def test_a2a_over_http(tools):
    srv, _ = serve_background(A2AAgent(tools))
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        card = json.loads(urllib.request.urlopen(base + "/.well-known/agent-card.json", timeout=10).read())
        assert card["supportedInterfaces"][0]["url"].startswith(base)
        req = urllib.request.Request(
            base + "/a2a",
            data=json.dumps(_send("search_data_docs", {"query": "average basket"})).encode(),
            headers={**HDRS, "content-type": "application/json"},
        )
        out = json.loads(urllib.request.urlopen(req, timeout=10).read())
        assert out["result"]["message"]["parts"][0]["data"]["output"]["results"]
        bad = urllib.request.Request(
            base + "/a2a",
            data=json.dumps(_send("search_data_docs", {"query": "x"})).encode(),
            headers={**HDRS, "x-tenant-id": "nope"},
        )
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(bad, timeout=10)
        assert e.value.code == 403
    finally:
        srv.shutdown()
