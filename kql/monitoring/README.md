# `kql/monitoring`

Queries over the telemetry in Log Analytics (Azure Monitor).

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`freshness_slo.kql`](freshness_slo.kql) | Freshness per data product against its SLO |
| [`pipeline_failures.kql`](pipeline_failures.kql) | Failed pipeline steps and quarantine spikes |
| [`agent_queries.kql`](agent_queries.kql) | Data agent questions, refusals and latency by caller |
