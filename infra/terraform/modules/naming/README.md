# `modules/naming`

CAF naming helper: `<type>-<workload>-<env>-<region>-<instance>` (for example `rg-fabricbi-dev-eus2-001`), compressed forms for Key Vault (24 chars, region dropped), container registry and storage (alphanumeric), and an optional suffix for globally unique names. No resources.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`main.tf`](main.tf) | Locals that build the name parts (no resources) |
| [`outputs.tf`](outputs.tf) | Values exported to the caller / the pipeline. |
| [`variables.tf`](variables.tf) | Inputs with types, defaults and validation rules. |
| [`versions.tf`](versions.tf) | Terraform and provider version constraints. |
