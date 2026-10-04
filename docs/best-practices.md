# Best practices: what is implemented and what is planned

A checklist of data platform, governance and agentic AI practices for this repo. Each row links to
the code and says honestly whether it is implemented, written but not deployed, or planned.
Nothing here has been deployed to Azure or Fabric.

**How to read the status column**

- **Implemented**: the code is in this repo and runs in the offline tests or in CI.
- **Written, not deployed**: the infrastructure, Fabric item or workflow code exists and passes
  validation (`bicep build`, `terraform validate` and `terraform test`, tflint, checkov, item
  structure tests), but it has never run against a real subscription or Fabric tenant.
- **Planned**: not in the repo yet. The note says what is missing.

## Data engineering

| Practice | What this repo does | Status | Where |
|---|---|---|---|
| **Medallion layers** | Bronze is an exact copy plus load metadata; silver applies contracts, types, dedup and redaction; gold is a star schema with conformed dimensions. | Implemented (local); notebooks written, not deployed | [`coldpath/`](../src/fabricbi/coldpath/README.md), [cold-path.md](cold-path.md), [`fabric/workspace`](../fabric/workspace/README.md) |
| **Idempotent ingest** | A manifest of file hashes makes bronze loads replay-safe; the mirror applies CDC from a checkpointed log sequence number, so re-running a sync changes nothing. | Implemented | [`bronze.py`](../src/fabricbi/coldpath/bronze.py), [`mirroring.py`](../src/fabricbi/coldpath/mirroring.py) |
| **Schema contracts** | Every silver and gold table has a YAML contract (types, keys, nullability, labels). Writes are validated, and a compatibility check rejects breaking changes without a major version bump. | Implemented | [`contracts/`](../contracts/README.md), [`contracts.py`](../src/fabricbi/coldpath/contracts.py) |
| **Data quality and quarantine** | Rule-based checks per table; failing rows go to a quarantine table with the reason instead of being dropped silently; the DQ report is part of the run output. | Implemented | [`quality.py`](../src/fabricbi/coldpath/quality.py) |
| **Hot and cold paths (Lambda)** | Streaming windows with watermark and allowed lateness feed real-time alerts; the batch path owns history; the serving view takes batch for closed days and stream only after the batch watermark, so nothing is counted twice. | Implemented | [`hotpath/`](../src/fabricbi/hotpath/README.md), [`lambda_view.py`](../src/fabricbi/lambda_view.py), [hot-path.md](hot-path.md) |
| **KQL parity** | The KQL files and the Python reference share constants, and a test fails if they drift. | Implemented (Python side); KQL not executed | [`kql/`](../kql/README.md) |

## Governance and security

| Practice | What this repo does | Status | Where |
|---|---|---|---|
| **Catalog and lineage** | A Purview-style catalog built from the contracts, with owners, glossary terms and labels; column-aware lineage recorded by every write; a check that fails on unowned or unlabelled assets. | Implemented (local); Purview account written, not deployed | [`governance/`](../src/fabricbi/governance/README.md), [governance.md](governance.md) |
| **Sensitivity labels** | Labels per column (Public, General, Confidential, Highly Confidential) propagate down lineage; the catalog check fails if a derived table carries a lower label than its inputs without a recorded declassify reason. | Implemented | [`labels.py`](../src/fabricbi/governance/labels.py) |
| **Row- and object-level security** | Region managers see only their region; finance sees margin; others do not. Enforced in views the data agent queries, not in the prompt. | Implemented (DuckDB views); Fabric roles planned | [`access.py`](../src/fabricbi/serve/access.py), [`governance/access-policy.yaml`](../governance/access-policy.yaml) |
| **PII handling** | Ticket text is redacted in silver; customer email and phone are masked unless the caller is cleared; the loyalty data product is restricted. | Implemented | [`silver.py`](../src/fabricbi/coldpath/silver.py), [`access.py`](../src/fabricbi/serve/access.py) |
| **Data products** | Five data products with owners, output ports, SLOs, consumers and semantic versions; a breaking schema change lists the consumers to notify. | Implemented | [`contracts/products`](../contracts/products/README.md), [`products.py`](../src/fabricbi/governance/products.py) |
| **Identity, no keys** | OIDC in CI; a managed identity with data-plane roles at runtime; SAS and shared keys off; Key Vault in RBAC mode. | Written, not deployed | [ADR 0003](adr/0003-oidc-and-managed-identity.md), [`infra/terraform`](../infra/terraform/README.md) |
| **Networking** | Public endpoints with Entra auth in both environments. No private endpoints or managed private endpoints yet. | Planned | [`infra/terraform/envs`](../infra/terraform/envs/README.md) |
| **Secrets in the repo** | A secrets scan runs in CI. | Implemented | [`scripts/secrets_scan.py`](../scripts/secrets_scan.py) |

## Agentic AI on data

| Practice | What this repo does | Status | Where |
|---|---|---|---|
| **Grounded NL-to-SQL** | The data agent only sees the semantic model's tables and measures; the model returns a plan that is compiled to SQL, or `CANNOT_ANSWER`. | Implemented (mock model) | [`nl2sql.py`](../src/fabricbi/serve/nl2sql.py), [data-agent.md](data-agent.md) |
| **Guardrails in layers** | Input guard (injection, out of scope), SQL guard (single read-only SELECT, allow-listed tables, no file or system functions, LIMIT enforced), sandboxed session (external access off, config locked, timeout), cost limit from the plan, output guard. | Implemented | [`guardrails.py`](../src/fabricbi/serve/guardrails.py), [`access.py`](../src/fabricbi/serve/access.py) |
| **Tool interfaces** | MCP server (stdio JSON-RPC, five tools) and an A2A agent card with the control-plane extension used by the agent platform repo. | Implemented | [`mcp_server.py`](../src/fabricbi/serve/mcp_server.py), [`a2a.py`](../src/fabricbi/serve/a2a.py), [`control-plane/`](../control-plane/README.md) |
| **RAG over governed docs** | Vector store over docs, data product contracts and measure definitions, filtered by the caller's label clearance. | Implemented (TF-IDF stand-in) | [`vector_store.py`](../src/fabricbi/serve/vector_store.py) |
| **LLM enrichment harness** | Redaction before the model, schema-validated JSON, one retry on malformed output, steered answers routed to review. | Implemented (mock Foundry model) | [`enrich/`](../src/fabricbi/enrich/README.md), [enrichment.md](enrichment.md) |
| **Eval gates** | Seven suites with floors and a no-regression baseline; CI fails on regression. | Implemented | [`evals/`](../evals/README.md), [ADR 0004](adr/0004-eval-gates-block-the-build.md) |

## Operations

| Practice | What this repo does | Status | Where |
|---|---|---|---|
| **Observability** | OpenTelemetry-style metrics and spans per pipeline step, freshness SLOs per data product with error budgets, and KQL for Log Analytics. | Implemented (local); alert rules planned | [`observability/`](../src/fabricbi/observability/README.md), [observability.md](observability.md), [`kql/monitoring`](../kql/monitoring/README.md) |
| **FinOps** | Capacity unit estimate per workload, SKU choice with headroom, pay-as-you-go vs reserved, pause schedule, budget alerts in the IaC. All figures are labelled estimates. | Implemented (estimate); budget written, not deployed | [cost-estimate.md](cost-estimate.md), [`finops/`](../finops/README.md) |
| **ML lifecycle** | Time-based backtest against a naive baseline, a model card regenerated from a real run. No registry, scheduled retrain or drift monitor. | Implemented (training, card); MLOps planned | [`forecast.py`](../src/fabricbi/enrich/forecast.py), [model card](model-card-demand-forecast.md) |
| **CI/CD** | Lint, tests, eval gate, generated-file checks, IaC checks on every push; dev -> prod deploy with approval, gated off. | Implemented (CI); deploy written, not deployed | [deployment.md](deployment.md), [ADR 0005](adr/0005-deploy-gated-off.md) |
| **Disaster recovery** | OneLake keeps data in the capacity's region; prod storage is zone-redundant and Key Vault has purge protection. No second region or restore drill. | Planned | [`infra/`](../infra/README.md) |

## Known gaps, in priority order

- Run on a real Fabric capacity: execute the notebooks, the KQL and the semantic model, and compare
  the results with the local reference.
- Real data agent model: swap the mock for a Foundry deployment and grow the golden question set.
- Private networking: managed private endpoints from Fabric to storage and Key Vault, private
  endpoints for Event Hubs and Purview.
- Fabric workspace roles and semantic model RLS roles generated from the access policy.
- Alert rules on the monitoring KQL, a forecast drift monitor, and a DR plan.

Related: [architecture decisions](adr/README.md) · [deployment pipeline](deployment.md) · [security policy](../SECURITY.md) · [contributing](../CONTRIBUTING.md)
