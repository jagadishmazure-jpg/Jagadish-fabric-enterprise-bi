# `.github/workflows`

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`ci.yml`](ci.yml) | Ruff, generated-file checks, doc output check, secrets scan, pytest, end-to-end demo, eval gate (report uploaded as an artifact), Bicep build. Offline. A `secrets` job runs gitleaks over the full git history. |
| [`codeql.yml`](codeql.yml) | CodeQL for Python and for the workflow files (`actions`), on push, pull request and weekly. Results appear under Security -> Code scanning and do not fail the build. |
| [`infra.yml`](infra.yml) | Terraform fmt, validate and test (mocked providers), tflint, checkov; `plan` only when OIDC variables exist |
| [`deploy.yml`](deploy.yml) | Gated by `DEPLOY_ENABLED`. Dev then prod (reviewer approval), Terraform or Bicep, Fabric workspace + items via REST and fabric-cicd, smoke tests, pause the dev capacity |
| [`teardown.yml`](teardown.yml) | Manual, gated, confirm by typing the environment name |

What each job does, the variables and the failure modes: [deployment.md](../../docs/deployment.md). The deploy gate and OIDC-only login are enforced by `tests/test_10_repo.py::test_workflows_gate_deploy_and_use_oidc`.

**Supply chain.** Every third-party action is pinned to a full commit SHA with the version in a comment, and every workflow starts from `permissions: contents: read`; jobs that need more (OIDC sign-in, CodeQL uploads) ask for it themselves. Dependabot ([`../dependabot.yml`](../dependabot.yml)) proposes weekly grouped updates that move the SHA and the comment together, and `tests/test_10_repo.py::test_workflows_are_hardened` fails CI if an action is left unpinned.

**SBOM.** The `sbom` job in `ci.yml` writes an SPDX JSON bill of materials for the source tree on every run (artifact `sbom.spdx.json`).
