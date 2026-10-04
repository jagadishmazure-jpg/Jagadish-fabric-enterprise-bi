# ADR 0005: Ship the deploy pipeline switched off

- **Status:** Accepted

## Context

The deploy workflow is real code: OIDC login, Terraform or Bicep, Fabric REST calls, fabric-cicd,
smoke tests, dev -> prod approval. But there is no subscription, Fabric tenant or capacity behind
it yet, and a Fabric capacity bills by the hour as soon as it exists.

## Decision

Every deploy and teardown job is conditioned on the repository variable `DEPLOY_ENABLED ==
'true'`, which is not set. A `preflight` job always runs and writes the gate state to the run
summary, so a reader can see the pipeline exists and why it skipped. Dev pauses its capacity after
the smoke tests by default.

## Consequences

- The deploy path has never run. Validation (Terraform validate and test, tflint, checkov, Bicep
  build) gives confidence in the templates, not in the Fabric REST steps.
- Turning it on is a deliberate change made after the setup checklist in
  [deployment.md](../deployment.md) and the [implementation guide](../implementation-guide.md) is done.
