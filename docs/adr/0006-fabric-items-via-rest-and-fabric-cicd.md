# ADR 0006: Fabric items through the Fabric REST API and fabric-cicd, not ARM

- **Status:** Accepted

## Context

The Fabric capacity is an Azure resource (`Microsoft.Fabric/capacities`), but the workspace and
everything in it (Lakehouse, Eventhouse, KQL database, notebooks, semantic models) live in the
Fabric service and are managed through the Fabric REST API, not Azure Resource Manager. Options
considered: Fabric Git integration with manual sync per workspace, the Fabric Terraform provider,
or REST plus the fabric-cicd library.

## Decision

Keep item definitions as files in `fabric/workspace/` in the format Fabric Git integration writes
(a `.platform` file plus the item definition). The deploy job creates or finds the workspace with
the REST API, assigns it to the capacity, and publishes the folder with fabric-cicd, using
`parameter.yml` to swap environment-specific values. Generated parts (the semantic model TMDL, the
KQL database schema) are written from the same Python definitions the offline tests use, and CI
fails if they are stale.

## Consequences

- Infrastructure and items have separate tools and separate failure modes; the pipeline runs them
  in order and smoke-tests both.
- The pipeline identity needs Fabric API access granted by a tenant admin, not just Azure RBAC.
- The Fabric Terraform provider would let one tool own both layers; it can be revisited if a client
  already uses it.
