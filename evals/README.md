# `evals`

Golden sets, thresholds and the no-regression baseline for `scripts/run_evals.py`.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`gold/`](gold/) | Golden cases: NL-to-SQL questions with expected answers, guardrail attacks and benign questions, retrieval queries |
| [`thresholds.yaml`](thresholds.yaml) | Absolute floors per metric |
| [`baseline.json`](baseline.json) | Last accepted results; a run may not regress beyond the tolerance. Updated with `--update-baseline` |
