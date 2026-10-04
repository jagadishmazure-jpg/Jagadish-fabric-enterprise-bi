# `contracts/products`

Data product contracts validated by `fabricbi.governance.products`.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`retail-sales.yaml`](retail-sales.yaml) | Sales star schema and daily aggregate (owner: commercial analytics) |
| [`store-operations-live.yaml`](store-operations-live.yaml) | Live store and freezer signals from the Eventhouse (owner: store operations) |
| [`customer-care-insights.yaml`](customer-care-insights.yaml) | Classified support tickets, PII removed (owner: customer care) |
| [`loyalty-members.yaml`](loyalty-members.yaml) | Loyalty member dimension, Highly Confidential, no external sharing (owner: loyalty) |
| [`demand-forecast.yaml`](demand-forecast.yaml) | Seven-day demand forecast per store and category (owner: commercial analytics; shared externally with a supplier planning partner) |

Tests: `tests/test_09_governance_ops.py` (validity, external sharing, version bumps). Guide: [governance.md](../../docs/governance.md).
