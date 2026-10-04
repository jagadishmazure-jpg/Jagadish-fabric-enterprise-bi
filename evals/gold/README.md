# `evals/gold`

Golden cases, one JSON object per line. Written by hand; small on purpose, so each case is readable.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`nl2sql.jsonl`](nl2sql.jsonl) | Business questions, the principal asking, and the expected result or refusal |
| [`guardrails.jsonl`](guardrails.jsonl) | Injection, write, exfiltration and restricted-column attempts plus benign questions that must not be refused |
| [`retrieval.jsonl`](retrieval.jsonl) | Questions and the document that must appear in the top 3 |

Sizes: 22 NL-to-SQL questions, 22 guardrail cases (18 attacks, 4 benign), 10 retrieval queries.
