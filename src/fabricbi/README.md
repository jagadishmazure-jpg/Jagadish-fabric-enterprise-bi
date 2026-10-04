# `fabricbi`

Offline implementation of the platform.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`__init__.py`](__init__.py) | Version and the fictional company name |
| [`paths.py`](paths.py) | Repository and lake paths |
| [`context.py`](context.py) | Run context: lake, lineage, telemetry, DQ reports |
| [`pipeline.py`](pipeline.py) | `run_all`: sources -> bronze -> mirror -> silver -> gold -> hot path -> serving -> forecast -> tickets |
| [`lambda_view.py`](lambda_view.py) | Merges batch history with stream data after the batch watermark |
| [`evals.py`](evals.py) | Eval suites and gates |
| [`domain/`](domain/) | Synthetic Fernhill Grocers data |
| [`coldpath/`](coldpath/) | Batch path and medallion layers |
| [`hotpath/`](hotpath/) | Stream and windows |
| [`enrich/`](enrich/) | Forecast and ticket classification |
| [`serve/`](serve/) | Semantic model, data agent, vector store, MCP, A2A |
| [`governance/`](governance/) | Catalog, lineage, labels, products |
| [`observability/`](observability/) | Telemetry and SLOs |
| [`finops/`](finops/) | Capacity sizing |
