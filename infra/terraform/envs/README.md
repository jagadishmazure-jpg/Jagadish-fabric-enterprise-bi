# `infra/terraform/envs`

Per-environment values. Both environments currently use public endpoints with Entra auth; private networking is planned.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`dev.tfvars`](dev.tfvars) | Smallest SKUs, no Purview, 1 GB/day log cap |
| [`prod.tfvars`](prod.tfvars) | F4, Standard Event Hubs, S1 IoT Hub, ZRS, Purview, purge protection, budget (created once `budget_contact_emails` is set) |
| [`dev.backend.hcl`](dev.backend.hcl) | State key for dev |
| [`prod.backend.hcl`](prod.backend.hcl) | State key for prod |
