# ADR 0001: Bicep and Terraform for the same resources

- **Status:** Accepted

## Context

Teams that buy a Fabric platform split roughly two ways. Azure-only shops often prefer Bicep: ARM
is the source of truth and there is no state file to protect. Teams with a central platform group
usually run Terraform with plan reviews in every pull request. A reference implementation that
only speaks one of them leaves half its readers translating.

## Decision

Write the Azure footprint (Fabric capacity, Event Hubs, IoT Hub, storage, Key Vault, Log
Analytics, Purview, identity) in both `infra/main.bicep` and `infra/terraform`, using
`azurerm` resources only (`azurerm_fabric_capacity` exists, so `azapi` is not needed). Both read
the same per-environment choices: smallest SKUs in dev, zone-redundant storage and Purview in prod.
The deploy workflow takes a `deploy_tool` input. The resource-group budget is the one exception: it exists only in Terraform so far.

## Consequences

- Every infrastructure change is made twice. `terraform test` and `bicep build` both run in CI, so
  a change that only lands in one stack is noticed in review, not caught automatically.
- One environment must be owned by one tool; pointing both at the same resource group would make
  them fight over drift.
- Fabric workspace items are outside both tools (see [ADR 0006](0006-fabric-items-via-rest-and-fabric-cicd.md)).
