# `infra`

Azure resources for the platform, twice: Bicep here and Terraform in [`terraform/`](terraform). Dev uses the smallest SKUs. Fabric workspace items are not ARM resources and are deployed separately ([deployment.md](../docs/deployment.md)).

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`main.bicep`](main.bicep) | Identity, monitoring, Key Vault, streaming, storage, Fabric capacity and (prod) Purview |
| [`main.parameters.dev.json`](main.parameters.dev.json) | Dev: F2, Basic Event Hubs, F1 IoT Hub, LRS, no Purview |
| [`main.parameters.prod.json`](main.parameters.prod.json) | Prod: F4, Standard Event Hubs, S1 IoT Hub, ZRS, Purview, purge protection |
| [`modules/`](modules/) | Bicep modules |
| [`terraform/`](terraform/) | Terraform twin |
