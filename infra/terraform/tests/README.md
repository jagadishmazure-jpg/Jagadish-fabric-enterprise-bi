# `infra/terraform/tests`

`terraform test` with mocked providers: no credentials, no network.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`plan.tftest.hcl`](plan.tftest.hcl) | Dev uses the smallest SKUs and CAF names with required tags; the trial-capacity switch removes the F SKU; prod adds Purview, a budget with three alerts and F4 |

Run: `terraform -chdir=infra/terraform test` (real result: `Success! 3 passed, 0 failed.`).
