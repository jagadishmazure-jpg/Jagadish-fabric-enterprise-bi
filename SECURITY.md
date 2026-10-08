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
- No secrets in the repo; a secrets scan of the working tree ([`scripts/secrets_scan.py`](scripts/secrets_scan.py)) and gitleaks over the full git history run in CI.
- CI signs in to Azure with OIDC only; runtime uses a managed identity, and SAS and shared keys are turned off ([ADR 0003](docs/adr/0003-oidc-and-managed-identity.md)).
- checkov scans the Terraform on every change, with each skipped check justified in [`.checkov.yaml`](.checkov.yaml).
- The silver step stops the pipeline (`QualityGateError`) when more than 2% of a table's rows fail quality rules, so bad data does not reach gold or the agent.
- Built but not deployed: an opt-in private networking option for Key Vault and Purview (private endpoints, private DNS, NSG, public access off) in Terraform and Bicep.
- Not yet in place: private networking for Event Hubs, IoT Hub, storage and Fabric, semantic model RLS roles in TMDL, alert rules, and Key Vault RBAC drift checks in the smoke tests.
- **Threat model:** [`docs/security/threat-model.md`](docs/security/threat-model.md) maps STRIDE, the OWASP Top 10 for LLM Applications and MITRE ATLAS techniques to this repository's real components, with the control, the test that proves it and whether it is built, written but not deployed, or planned.
- **Supply chain:** every third-party GitHub Action is pinned to a full commit SHA with its version in a comment, and every workflow starts from read-only `permissions`. Dependabot proposes weekly, grouped updates ([`.github/dependabot.yml`](.github/dependabot.yml)); CodeQL scans the Python code and the workflow files ([`codeql.yml`](.github/workflows/codeql.yml)); gitleaks scans the full git history in CI. A test (`test_workflows_are_hardened`) fails if an action is left unpinned or a workflow loses its `permissions` block.
- **SBOM:** the `sbom` job in [`ci.yml`](.github/workflows/ci.yml) builds an SPDX JSON software bill of materials from the lockfiles and manifests on every run and keeps it as the `sbom.spdx.json` build artifact. The repository ships no container image, so there is no image scan or provenance step.
- **Known scanner false positives** are listed by fingerprint in [`.gitleaksignore`](.gitleaksignore), each with the reason (for example a public Azure built-in role ID); none is a credential.
- **GitHub settings:** secret scanning with push protection, Dependabot alerts and security updates, private vulnerability reporting, and a ruleset on `main` that blocks force-pushes and branch deletion and requires the CI checks before a pull request can merge. The maintainer (repository admin) can still push directly to `main`, so for direct pushes the checks run after the push rather than before it.
- Full status of each control: [`docs/best-practices.md`](docs/best-practices.md).
