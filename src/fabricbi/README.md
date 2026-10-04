# `fabricbi`

Offline implementation of the platform. Each subpackage has its own README and a component guide in [`docs/`](../../docs/README.md).

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`__init__.py`](__init__.py) | Version and the fictional company name |
| [`paths.py`](paths.py) | Repository and lake paths |
| [`context.py`](context.py) | Run context: lake, lineage, telemetry, DQ reports |
| [`pipeline.py`](pipeline.py) | `run_all`: sources -> bronze -> mirror -> silver -> gold -> hot path -> serving -> forecast -> tickets |
| [`lambda_view.py`](lambda_view.py) | Joins batch history and today's stream at the batch cut-off ([lambda-view.md](../../docs/lambda-view.md)) |
| [`evals.py`](evals.py) | Eval suites, gates and the baseline regression check |
| [`examples.py`](examples.py) | `python -m fabricbi.examples <name>`: one deterministic example per component; the docs paste their real output |
| [`domain/`](domain/) | Synthetic Fernhill Grocers data |
| [`coldpath/`](coldpath/) | Batch path and medallion layers |
| [`hotpath/`](hotpath/) | Stream and windows |
| [`enrich/`](enrich/) | Forecast and ticket classification |
| [`serve/`](serve/) | Semantic model, data agent, vector store, MCP, A2A |
| [`governance/`](governance/) | Catalog, lineage, labels, products |
| [`observability/`](observability/) | Telemetry and SLOs |
| [`finops/`](finops/) | Capacity sizing |

Run: `python -m fabricbi.examples --list` lists the 18 examples; `python -m fabricbi.examples all`
runs them all on one pipeline run.
