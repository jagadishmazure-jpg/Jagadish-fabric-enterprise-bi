# ADR 0004: Eval gates block the build

- **Status:** Accepted

## Context

The parts of this platform that are easiest to break quietly are not the ones unit tests notice:
the data agent answering a question with plausible but wrong SQL, a guardrail that starts letting
a write through or refusing harmless questions, retrieval that stops finding the right definition,
an anomaly rule that drops an alert, a forecast that no longer beats the naive baseline.

## Decision

`scripts/run_evals.py` runs seven suites against golden sets in `evals/gold/` and the planted
incidents in the synthetic data, and compares the results with `evals/thresholds.yaml` (absolute
floors) and `evals/baseline.json` (no regression beyond a small tolerance). CI fails if any gate
fails, and uploads the report as an artifact. Moving the baseline is an explicit
`--update-baseline` run that shows up in the pull request diff.

## Consequences

- Golden sets are small (tens of cases) and written by the author, so a pass means "no known
  regression", not "accurate on real questions". Growing them with real user questions is the first
  job after a pilot.
- The NL-to-SQL model is a mock, so its accuracy number measures the harness (guardrails, RLS,
  execution, comparison), not a language model. With a real model the same gate applies.
