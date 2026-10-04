# `kql`

KQL for the Eventhouse (hot path). Each query starts with `let` constants that a test compares with `fabricbi.hotpath.windows`, so the KQL and the Python reference cannot drift.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`tables.kql`](tables.kql) | Table definitions, retention and the JSON ingestion mapping (also generates the KQL database schema) |
| [`sales_5min.kql`](sales_5min.kql) | Five-minute tumbling windows of sales per store |
| [`freezer_alerts.kql`](freezer_alerts.kql) | Freezer above the warm threshold for consecutive windows |
| [`sensor_offline.kql`](sensor_offline.kql) | Devices silent longer than the offline limit |
| [`sales_spike.kql`](sales_spike.kql) | Store sales far above its rolling baseline |
| [`late_events.kql`](late_events.kql) | Events that arrived after the allowed lateness |
| [`monitoring/`](monitoring/) | Log Analytics queries for platform health |

Run: `python -m fabricbi.examples kql`. Tests: `tests/test_05_hotpath.py -k kql`. Guide: [kql.md](../docs/kql.md).
