# `semantic-model`

The semantic model as YAML: tables, relationships, measures (DAX and SQL forms), synonyms and descriptions. The data agent and the TMDL export both read it.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`retail_sales.yaml`](retail_sales.yaml) | Retail sales model over the gold star schema |

Run: `python -m fabricbi.examples semantic`. Tests: `tests/test_07_semantic_agent.py -k semantic`. Guide: [semantic-model.md](../docs/semantic-model.md).
