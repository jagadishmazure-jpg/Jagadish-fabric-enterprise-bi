# `modules/private-endpoint`

One private endpoint plus its private DNS zone group, used for Key Vault (`vault`) and Purview (`account`, `portal`) when `private_networking = true`. Not deployed.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`main.tf`](main.tf) | The private endpoint and its DNS zone group. |
| [`outputs.tf`](outputs.tf) | The private endpoint id. |
| [`variables.tf`](variables.tf) | Inputs with types and defaults. |
| [`versions.tf`](versions.tf) | Terraform and provider version constraints. |
