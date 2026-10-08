# `infra/terraform/modules`

Modules used by the root stack.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`naming/`](naming/) | CAF names, no resources |
| [`monitoring/`](monitoring/) | Log Analytics and Application Insights |
| [`keyvault/`](keyvault/) | Key Vault in RBAC mode |
| [`streaming/`](streaming/) | Event Hubs and IoT Hub |
| [`storage/`](storage/) | ADLS Gen2 landing storage |
| [`fabric-capacity/`](fabric-capacity/) | Fabric capacity |
| [`purview/`](purview/) | Purview account |
| [`private-network/`](private-network/) | Only when `private_networking = true`: VNet, private-endpoint subnet with an NSG, private DNS zones linked to the VNet |
| [`private-endpoint/`](private-endpoint/) | Private endpoints with DNS zone groups for Key Vault and the Purview account and portal |

Guide: [infrastructure.md](../../../docs/infrastructure.md).
