# `fabricbi.ignite`

Offline stand-ins for three Ignite announcements: HorizonDB mirrored into the lake, a Fabric app bound to the semantic model, and a Fabric IQ-style tool with row-level security per caller. Nothing here calls Azure or a Fabric tenant.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`__init__.py`](__init__.py) | Public exports |
| [`horizondb.py`](horizondb.py) | Mock HorizonDB source, change log, and incremental mirror |
| [`schema.sql`](schema.sql) | Logical PostgreSQL schema for `loyalty_redemptions` |
| [`fabric_app.py`](fabric_app.py) | Fabric app pages compiled from the semantic model |
| [`fabric_iq.py`](fabric_iq.py) | `ask_business_question` tool, one caller at a time |

Run: `python -m fabricbi.examples ignite`. Tests: `tests/test_12_ignite.py`. Guide: [ignite-2026.md](../../../docs/ignite-2026.md).
