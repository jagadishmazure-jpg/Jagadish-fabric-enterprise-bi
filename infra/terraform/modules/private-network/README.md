# `modules/private-network`

Optional private networking: a VNet with a private-endpoint subnet behind an NSG (default rules), plus private DNS zones linked to the VNet. The root stack calls it only when `private_networking = true`. Written and plan-tested offline; not deployed.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`main.tf`](main.tf) | VNet, private-endpoint subnet, NSG and association, private DNS zones and VNet links. |
| [`outputs.tf`](outputs.tf) | Subnet id, NSG name and zone ids for the private endpoints. |
| [`variables.tf`](variables.tf) | Inputs with types and defaults. |
| [`versions.tf`](versions.tf) | Terraform and provider version constraints. |
