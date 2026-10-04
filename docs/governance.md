# Governance: catalog, lineage, labels, access and data products

Microsoft Purview is the governance layer in the target design. Offline, the same ideas are
code that runs on every pipeline execution, so the checks are tested rather than described.

## Catalog

[`governance/catalog.yaml`](../governance/catalog.yaml) lists every asset the pipeline writes
with an owner, a sensitivity label and a description, plus column classifications (email, phone,
person name, free text with personal data) and a short glossary. `Catalog.build` adds technical
metadata recorded by the lake (row counts, column types, run id) and the lineage recorded by the
pipeline.

## Lineage

Lineage is not drawn by hand. Each step records `(process, inputs, outputs)` as it runs, so the
graph always matches the code. It answers:

- upstream: where did `gold.fact_sales` come from?
- downstream and impact: if the POS export changes, which tables and which consumers are hit?
- export: OpenLineage-style run events and a mermaid diagram.

## Sensitivity labels and how they flow

Labels are ordered Public < General < Confidential < Highly Confidential. The rule checked on
every run: **an asset is at least as restricted as its strictest input**, unless it declares a
`declassify` reason in the catalog. Three steps legitimately lower a label, and each says why:

| Asset | Input label | Own label | Declared reason |
|---|---|---|---|
| silver.support_tickets | Highly Confidential | General | personal data is redacted by the silver transform |
| gold.fact_sales | Highly Confidential (dim_customer) | Confidential | holds the customer surrogate key only |
| gold.agg_daily_sales | Confidential | General | aggregated to store, day and category |

A classified column on an asset labelled below Highly Confidential is a finding, and so is an
external share of a product labelled above General.

## Access: RLS, OLS and masking

[`governance/access-policy.yaml`](../governance/access-policy.yaml) is the single policy the data
agent's secure session enforces, and the same rules map onto Power BI roles and OneLake security
when deployed.

| Control | Rule |
|---|---|
| Row-level security | stores, sales, freezers and tickets filtered to the caller's regions; members by home region |
| Object-level security | `dim_product.unit_cost` and `fact_sales.cost_amount` exist only for finance |
| Masking | `dim_customer.email` and `phone` masked unless the caller has `pii_reader` |
| Cost limit | estimated rows scanned per query, per role |

## Data products

Each product in [`contracts/products`](../contracts/products) states its owner, output ports,
schema contracts, sensitivity, freshness and quality service levels, consumers and sharing mode
(internal shortcut, external share). `validate_product` checks completeness and consistency.
`bump_for` gives the next semantic version from a contract change: breaking means major, additive
means minor.

| Product | Owner | Sensitivity | Freshness SLO | Shared externally |
|---|---|---|---|---|
| retail-sales | commercial-analytics | Confidential | 26 h | no |
| store-operations-live | store-operations | General | 15 min | no |
| customer-care-insights | customer-care | General | 48 h | no |
| loyalty-members | loyalty | Highly Confidential | 26 h | no |
| demand-forecast | commercial-analytics | General | 26 h | yes, to a supplier planning partner |
