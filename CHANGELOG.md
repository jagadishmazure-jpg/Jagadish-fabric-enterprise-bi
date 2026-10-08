# Changelog

Notable changes, newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). There are no versioned releases yet.

## Unreleased

### Added

- Opt-in private networking for Key Vault and Purview in Terraform (`private_networking`, on in `prod.tfvars`) and Bicep (`privateNetworking`): VNet, private-endpoint subnet with an NSG, private DNS zones and private endpoints for the vault and the Purview account and portal, with public network access turned off. Public stays the default. Plan-tested offline, never deployed; a parity test (`test_key_vault_and_purview_private_networking_in_both_tools`) keeps the two tools in step.
- Threat model (`docs/security/threat-model.md`): STRIDE, OWASP Top 10 for LLM Applications and MITRE ATLAS mapped to this repository's components, each row with its control, test evidence and built / planned status.
- SBOM job in CI: an SPDX JSON software bill of materials of the source tree on every run (artifact `sbom.spdx.json`).
- Supply-chain hardening: every GitHub Action pinned to a commit SHA with a version comment, top-level `permissions` on every workflow, a gitleaks job in CI, a CodeQL workflow, `.github/dependabot.yml` and a guard test (`test_workflows_are_hardened`).
- GitHub settings: Dependabot alerts and security updates, private vulnerability reporting and a `main` ruleset (no force-push or deletion; CI required on pull requests).
- Synthetic data domain for the fictional Fernhill Grocers chain, with planted defects and incidents.
- Cold path: idempotent bronze ingest, mirroring with CDC, silver contracts and quarantine, gold star schema.
- Hot path: simulated Event Hubs and IoT Hub stream, event-time windows with lateness, three alert rules, KQL twins.
- Lambda serving view that merges batch history with live windows without double counting.
- Demand forecast with a model card, and a Foundry ticket classification harness (mocked model).
- Semantic model with TMDL export, a governed NL-to-SQL data agent, a vector store, an MCP server and an A2A agent card.
- Purview-style catalog, lineage, sensitivity labels, RLS/OLS, data product contracts, freshness SLOs and a capacity cost estimate.
- Fabric workspace item definitions, Terraform and Bicep for the Azure resources, and GitHub Actions workflows (deploy gated off).
- Eval gates, documentation, six ADRs, `SECURITY.md` and `CONTRIBUTING.md`.
- Component docs for every part of the build (domain, cold and hot paths, Lambda view, enrichment, semantic model, data agent, MCP and A2A, governance, observability, FinOps, KQL, Fabric items, infrastructure, deployment), each with code excerpts and output pasted from real runs, plus `docs/implementation-guide.md`.
- `python -m fabricbi.examples <name>` runs one component, and `scripts/doc_outputs.py` keeps the doc example blocks in sync (checked in CI).
- The pipeline writes its spans and metrics to `<lake>/_telemetry.jsonl`.

### Changed

- The silver step now stops the pipeline with `QualityGateError` when a table quarantines more than 2% of its rows.
- `kql/monitoring/pipeline_failures.kql` reads failures from `Success == false` and `exception.type`.
