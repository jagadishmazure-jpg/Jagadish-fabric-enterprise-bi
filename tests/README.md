# `tests`

Offline tests. `conftest.py` runs the whole pipeline once per session on synthetic data in a
temporary folder (about five seconds), and every test reads from that run.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`conftest.py`](conftest.py) | Session fixtures: pipeline run, lake, data agent tools, principals |
| [`test_01_synth.py`](test_01_synth.py) | Generator is deterministic, sources have the planted defects |
| [`test_02_bronze_mirroring.py`](test_02_bronze_mirroring.py) | Bronze idempotency; mirroring CDC, deletes, replay, lag, checkpoints, shortcuts |
| [`test_03_contracts_quality.py`](test_03_contracts_quality.py) | Schema contracts and compatibility, DQ rules, quarantine, redaction |
| [`test_04_gold.py`](test_04_gold.py) | Star schema keys, reconciliation, calendar, freezer summary, lineage |
| [`test_05_hotpath.py`](test_05_hotpath.py) | Alerts, late events, windows, no false alerts, KQL constants match Python |
| [`test_06_lambda_forecast_tickets.py`](test_06_lambda_forecast_tickets.py) | Serving view without double counting, forecast vs naive, ticket harness |
| [`test_07_semantic_agent.py`](test_07_semantic_agent.py) | Semantic model, every golden question and guardrail case, RLS, OLS, masking, sandbox |
| [`test_08_mcp_a2a.py`](test_08_mcp_a2a.py) | MCP over `handle()` and stdio; A2A card, caller and tenant checks, HTTP |
| [`test_09_governance_ops.py`](test_09_governance_ops.py) | Catalog, lineage, labels, data products, vector store, SLOs, telemetry, capacity sizing |
| [`test_10_repo.py`](test_10_repo.py) | Generated files current, Fabric items, eval gates, folder READMEs, no dates, links, workflow gates |
| [`test_11_docs.py`](test_11_docs.py) | Every component guide exists, is indexed and has the required sections; code excerpts are copied from the source; pasted outputs and test counts are current; no placeholders; the implementation guide verifies every step |

Run:

```bash
pytest -q  # 198 tests
pytest -q tests/test_07_semantic_agent.py -k guardrail   # one area
```
