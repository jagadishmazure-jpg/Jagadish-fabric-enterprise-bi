# `infra/terraform`: Terraform twin of the Bicep

The same resources as [`../main.bicep`](../main.bicep) with `azurerm` only (`azurerm_fabric_capacity` exists, so no `azapi`). CAF names (`rg-fabricbi-dev-eus2-001`), six required tags, dev and prod tfvars, a partial `azurerm` backend with Entra ID auth, and offline `terraform test` against mocked providers.

**Remote state (one-time).** Create a storage account with shared keys off and a `tfstate` container, give the deploy identity `Storage Blob Data Contributor`, then:

```bash
az group create -n rg-tfstate-shared-eus2-001 -l eastus2
az storage account create -n <unique-name> -g rg-tfstate-shared-eus2-001 --sku Standard_ZRS \
  --min-tls-version TLS1_2 --allow-blob-public-access false --allow-shared-key-access false
az storage container create --account-name <unique-name> -n tfstate --auth-mode login
terraform init -backend-config=envs/dev.backend.hcl \
  -backend-config=resource_group_name=rg-tfstate-shared-eus2-001 -backend-config=storage_account_name=<unique-name>
```

**Validate locally (no Azure needed):** `terraform init -backend=false && terraform validate && terraform test`.

**Trial capacity.** Set `deploy_fabric_capacity = false` to skip the F SKU and publish into a Fabric trial capacity instead.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`.terraform.lock.hcl`](.terraform.lock.hcl) | Provider lock file (committed so CI and local use the same provider builds) |
| [`.tflint.hcl`](.tflint.hcl) | tflint rules (azurerm plugin) |
| [`versions.tf`](versions.tf) | Terraform and provider constraints |
| [`providers.tf`](providers.tf) | azurerm provider with storage via Entra ID |
| [`backend.tf`](backend.tf) | Partial azurerm backend |
| [`variables.tf`](variables.tf) | Inputs with validation (SKUs, admins, emails) |
| [`locals.tf`](locals.tf) | Names and tags |
| [`main.tf`](main.tf) | Resource group, identity, modules, budget |
| [`outputs.tf`](outputs.tf) | Same output names as the Bicep |
| [`envs/`](envs/) | Per-environment tfvars and backend keys |
| [`modules/`](modules/) | Modules |
| [`tests/`](tests/) | Offline plan tests |
