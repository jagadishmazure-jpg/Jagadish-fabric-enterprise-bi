# `fabricbi.domain`

Seeded generator for a fictional grocery chain, Fernhill Grocers: 12 stores in 4 regions, 40 products, 300 loyalty members (one is deleted at the source through the change log), 8 weeks of sales, freezer telemetry and support tickets. Planted defects and incidents give the quality rules, alerts and evals something real to find.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`__init__.py`](__init__.py) | Package marker |
| [`synth.py`](synth.py) | Writes the source systems: POS CSV, catalog JSON, sensor CSV, ticket text, and an SQLite operational database with a change log |

Run: `python -m fabricbi.examples domain`. Tests: `tests/test_01_synth.py`. Guide: [domain.md](../../../docs/domain.md).
