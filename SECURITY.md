# Security policy

## Supported versions

Only the `main` branch is maintained. There are no released versions.

## Reporting a vulnerability

Please do not open a public issue with the details.

1. Use GitHub private vulnerability reporting: **Security** tab -> **Report a vulnerability** on [Jagadish-fabric-enterprise-bi](https://github.com/jagadishmazure-jpg/Jagadish-fabric-enterprise-bi/security).
2. If that button is not shown, open an issue titled `Security contact request` with no technical details, and I will reply with a private channel.

I aim to acknowledge a report within 5 working days. This is a portfolio maintained by one person, so there is no formal SLA or bug bounty.

## Scope

This repository is a reference build. It runs offline on synthetic data for a fictional retailer and has never been deployed to Azure or a Fabric tenant. In scope: anything that would be unsafe if deployed as written, for example a data agent guardrail that can be bypassed (write SQL, file or network access, reading a hidden column or another region's rows, unmasked personal data), a role broader than documented, or a secret that could leak through CI. Out of scope: the deterministic mocks themselves.

## What the repo already does

- The data agent runs every query in a fresh sandboxed DuckDB session: views with row-level security, hidden finance columns and masked contact details; external access off and configuration locked; a timeout. SQL is parsed and must be one read-only `SELECT` over allow-listed tables, under a cost limit ([`src/fabricbi/serve/`](src/fabricbi/serve/README.md)). The attack cases are in [`evals/gold/guardrails.jsonl`](evals/gold/guardrails.jsonl) and gate CI.
- Ticket text is redacted before it reaches the model, and model output must match a closed JSON schema ([docs/enrichment.md](docs/enrichment.md)).
- The A2A endpoint only accepts listed tenants and calling agents and applies the end user's permissions.
- No secrets in the repo; a secrets scan runs in CI ([`scripts/secrets_scan.py`](scripts/secrets_scan.py)).
- CI signs in to Azure with OIDC only; runtime uses a managed identity, and SAS and shared keys are turned off ([ADR 0003](docs/adr/0003-oidc-and-managed-identity.md)).
- checkov scans the Terraform on every change, with each skipped check justified in [`.checkov.yaml`](.checkov.yaml).
- The silver step stops the pipeline (`QualityGateError`) when more than 2% of a table's rows fail quality rules, so bad data does not reach gold or the agent.
- Not yet in place: private networking, semantic model RLS roles in TMDL, alert rules, and Key Vault RBAC drift checks in the smoke tests.
- Full status of each control: [`docs/best-practices.md`](docs/best-practices.md).
