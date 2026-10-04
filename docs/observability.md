# Observability and reliability

## Telemetry

[`observability/telemetry.py`](../src/fabricbi/observability/telemetry.py) records spans and
metrics with OpenTelemetry names, without the SDK as a dependency. Once deployed, the Azure Monitor
OpenTelemetry distro sends the same records to Application Insights and Log Analytics.

| Signal | Name | Attributes |
|---|---|---|
| span per pipeline step | `bronze.ingest`, `silver.build`, `gold.build`, `mirroring.sync`, `enrich.tickets`, `enrich.forecast`, `hotpath.eventstream`, `data_agent.ask` | `fabricbi.layer`, `db.system`, `gen_ai.system`, `enduser.id` |
| counter | `fabricbi.rows.written` | table, layer |
| counter | `fabricbi.rows.quarantined` | table |
| counter | `fabricbi.hotpath.late_events` | |
| counter | `fabricbi.agent.queries` | outcome, reason |
| histogram | `fabricbi.step.duration`, `fabricbi.agent.duration` | step, outcome |

## Freshness SLOs and error budgets

Each data product has a freshness limit. A product is `ok` under 80% of the limit, `warning` up to
it and `breach` beyond it or if it never published. Over a series of checks the error budget (1%
of checks for a 99% target) shows how much room is left before the SLO is missed. The same rule is
written as a Log Analytics query in [`kql/monitoring/freshness_slo.kql`](../kql/monitoring/freshness_slo.kql)
for an Azure Monitor scheduled alert.

## Alerting (written, not deployed)

| Query | Alert |
|---|---|
| [`freshness_slo.kql`](../kql/monitoring/freshness_slo.kql) | a data product is in breach |
| [`pipeline_failures.kql`](../kql/monitoring/pipeline_failures.kql) | a pipeline step failed or a quality gate failed |
| [`agent_queries.kql`](../kql/monitoring/agent_queries.kql) | refusal mix per day (attacks vs false refusals) |

## Reliability measures in the code

- Idempotent ingest (content-hash manifest) and idempotent mirroring (upsert by key, checkpoint after apply).
- Contracts checked before every gold write, so a bad build fails instead of publishing.
- Late events are routed, not merged into published windows; the cold path catches them up.
- Each alert fires once per incident and clears on recovery.
- The data agent has a per-query timeout and a cost limit, and fails closed (refusal with a reason).
