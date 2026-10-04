# `fabricbi.enrich`

Enrichment ([enrichment.md](../../../docs/enrichment.md)).

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`__init__.py`](__init__.py) | Package marker |
| [`forecast.py`](forecast.py) | Gradient-boosted seven-day forecast with a naive baseline backtest |
| [`foundry_mock.py`](foundry_mock.py) | Deterministic stand-in for a Foundry chat deployment |
| [`tickets.py`](tickets.py) | Classification harness: redact, prompt, validate, retry, review |

Run: `python -m fabricbi.examples forecast` and `tickets`. Tests: `tests/test_06_lambda_forecast_tickets.py`. Guide: [enrichment.md](../../../docs/enrichment.md).
