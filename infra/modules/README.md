# `infra/modules`

Bicep modules called by `../main.bicep`.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`monitoring.bicep`](monitoring.bicep) | Log Analytics (daily cap) and workspace-based Application Insights |
| [`keyvault.bicep`](keyvault.bicep) | Key Vault in RBAC mode and Secrets User for the ingest identity; public network access is a parameter |
| [`streaming.bicep`](streaming.bicep) | Event Hubs namespace (local auth off) with the `pos-events` hub (Eventstream consumer group on Standard and above), IoT Hub with an Eventstream consumer group, diagnostics to Log Analytics |
| [`storage.bicep`](storage.bicep) | ADLS Gen2 landing account, shared keys off, landing container |
| [`fabric.bicep`](fabric.bicep) | Fabric capacity (`Microsoft.Fabric/capacities`) with administrators |
| [`purview.bicep`](purview.bicep) | Microsoft Purview account with a system identity; public network access is a parameter |
| [`network.bicep`](network.bicep) | Only when `privateNetworking` is on: VNet, private-endpoint subnet with an NSG (default rules only, so inbound from outside the VNet is denied), private DNS zones for Key Vault and Purview, linked to the VNet |
| [`private-endpoint.bicep`](private-endpoint.bicep) | One private endpoint with its DNS zone group, called once per target (Key Vault, Purview account, Purview portal) |

Guide: [infrastructure.md](../../docs/infrastructure.md).
