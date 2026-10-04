# `scripts`

Command-line entry points. All run offline except `publish_fabric_items.py`, which only the deploy workflow calls. Each `--check` mode is a CI step ([deployment.md](../docs/deployment.md)).

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`demo.py`](demo.py) | End-to-end run: pipeline, alerts, serving view, forecast, data agent questions, catalog, SLOs |
| [`run_evals.py`](run_evals.py) | Seven eval suites with gates; `--update-baseline` to accept new results |
| [`export_contracts.py`](export_contracts.py) | Writes the agent card, MCP tool list, semantic model TMDL and KQL database schema; `--check` for CI |
| [`cost_report.py`](cost_report.py) | Writes docs/cost-estimate.md from finops/workloads.yaml; `--check` |
| [`model_card.py`](model_card.py) | Trains the forecast and writes the model card; `--check` |
| [`publish_fabric_items.py`](publish_fabric_items.py) | Publishes fabric/workspace with fabric-cicd (deploy workflow only) |
| [`doc_outputs.py`](doc_outputs.py) | Pastes the real output of `python -m fabricbi.examples <name>` into every marked docs block and checks test-count claims; `--check` for CI |
| [`secrets_scan.py`](secrets_scan.py) | Fails on key-like strings in tracked files |
| [`overlap_check.py`](overlap_check.py) | Checks tracked files for long verbatim overlaps with given reference texts |

Run:

```bash
python scripts/demo.py
python scripts/run_evals.py --out evals-out
python scripts/export_contracts.py --check && python scripts/cost_report.py --check \
  && python scripts/model_card.py --check && python scripts/doc_outputs.py --check
python scripts/secrets_scan.py
```

Tests: `tests/test_10_repo.py::test_generated_files_are_current` runs every `--check`;
`tests/test_11_docs.py` runs `doc_outputs.py --check`.
