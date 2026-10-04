# `.github/workflows`

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`ci.yml`](ci.yml) | Ruff, generated-file checks, secrets scan, pytest, end-to-end demo, eval gate (report uploaded as an artifact), Bicep build. Offline. |
| [`infra.yml`](infra.yml) | Terraform fmt, validate and test (mocked providers), tflint, checkov; `plan` only when OIDC variables exist |
| [`deploy.yml`](deploy.yml) | Gated by `DEPLOY_ENABLED`. Dev then prod (reviewer approval), Terraform or Bicep, Fabric workspace + items via REST and fabric-cicd, smoke tests, pause the dev capacity |
| [`teardown.yml`](teardown.yml) | Manual, gated, confirm by typing the environment name |
