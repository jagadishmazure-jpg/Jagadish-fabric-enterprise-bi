# `contracts/schemas`

Schema contracts checked on every write by `fabricbi.coldpath.contracts`. `compatibility()` classifies a change as breaking, additive or none, and the owning data product's version is bumped to match (`fabricbi.governance.products.bump_for`).

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`gold.agg_daily_sales.yaml`](gold.agg_daily_sales.yaml) | Contract for `gold.agg_daily_sales` |
| [`gold.dim_customer.yaml`](gold.dim_customer.yaml) | Contract for `gold.dim_customer` |
| [`gold.dim_date.yaml`](gold.dim_date.yaml) | Contract for `gold.dim_date` |
| [`gold.dim_product.yaml`](gold.dim_product.yaml) | Contract for `gold.dim_product` |
| [`gold.dim_store.yaml`](gold.dim_store.yaml) | Contract for `gold.dim_store` |
| [`gold.fact_freezer_daily.yaml`](gold.fact_freezer_daily.yaml) | Contract for `gold.fact_freezer_daily` |
| [`gold.fact_sales.yaml`](gold.fact_sales.yaml) | Contract for `gold.fact_sales` |
| [`gold.fact_ticket.yaml`](gold.fact_ticket.yaml) | Contract for `gold.fact_ticket` |
| [`gold.forecast_sales.yaml`](gold.forecast_sales.yaml) | Contract for `gold.forecast_sales` |
| [`gold.serving_sales_daily.yaml`](gold.serving_sales_daily.yaml) | Contract for `gold.serving_sales_daily` |
| [`silver.pos_lines.yaml`](silver.pos_lines.yaml) | Contract for `silver.pos_lines` |
| [`silver.products.yaml`](silver.products.yaml) | Contract for `silver.products` |

Tests: `tests/test_03_contracts_quality.py`. Guide: [cold-path.md](../../docs/cold-path.md).
