# ADR 0003: OIDC for the pipeline, managed identity at runtime, no keys

- **Status:** Accepted

## Context

A data platform collects credentials quickly: Event Hubs SAS keys, storage account keys, IoT Hub
connection strings, a service principal secret for the pipeline. Each is a long-lived secret that
can leak and has to be rotated.

## Decision

- GitHub Actions signs in with OpenID Connect federated credentials, one identity per environment.
  No client secret exists.
- Runtime access uses a user-assigned managed identity (`id-...-ingest`) with data-plane roles:
  Azure Event Hubs Data Receiver, Storage Blob Data Contributor, Key Vault Secrets User.
- Local (key) auth is turned off where the resource allows it: Event Hubs `local_authentication_enabled =
  false`, storage `shared_access_key_enabled = false`, Key Vault in RBAC mode. The smoke tests in
  `.github/scripts/deploy.sh` fail the deploy if an Event Hubs namespace allows SAS keys or a
  storage account allows shared keys (Key Vault RBAC mode is enforced by the templates only).
- Offline, the data agent and MCP server identify the caller by a principal name that maps to a
  role in `governance/principals.yaml`; in Fabric that mapping comes from Entra groups.

## Consequences

- Devices still need credentials to send to IoT Hub (X.509 or per-device keys); those are outside
  this repo and would be handled by Device Provisioning Service.
- The Fabric tenant must allow service principals to call Fabric APIs, which some organisations
  restrict. The deployment guide lists it as a setup step.
