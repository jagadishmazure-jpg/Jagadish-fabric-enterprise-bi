# `fabricbi.serve`

Serving layer: semantic model, data agent and its guardrails, vector store, MCP and A2A.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`__init__.py`](__init__.py) | Package marker |
| [`semantic.py`](semantic.py) | Semantic model loader, validation, SQL compiler, TMDL export |
| [`access.py`](access.py) | Principals and the sandboxed DuckDB session with RLS, OLS and masking |
| [`guardrails.py`](guardrails.py) | Input, SQL and output guards |
| [`nl2sql.py`](nl2sql.py) | Mock NL-to-plan model |
| [`data_agent.py`](data_agent.py) | The data agent pipeline |
| [`vector_store.py`](vector_store.py) | TF-IDF vector store with label filtering |
| [`mcp_server.py`](mcp_server.py) | MCP server over stdio |
| [`a2a.py`](a2a.py) | A2A agent card and JSON-RPC endpoint |

Run: `python -m fabricbi.examples data_agent` (also `guardrails`, `semantic`, `vector_store`, `mcp` and `a2a`). Tests: `tests/test_07_semantic_agent.py`, `tests/test_08_mcp_a2a.py`. Guide: [data-agent.md](../../../docs/data-agent.md), plus [semantic-model.md](../../../docs/semantic-model.md) and [agent-interfaces.md](../../../docs/agent-interfaces.md).
