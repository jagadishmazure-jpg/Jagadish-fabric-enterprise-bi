# Offline plan tests: mocked providers, no Azure credentials, nothing created.
#   terraform init -backend=false && terraform test
mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      tenant_id       = "00000000-0000-0000-0000-000000000001"
      subscription_id = "00000000-0000-0000-0000-000000000002"
      object_id       = "00000000-0000-0000-0000-000000000003"
    }
  }
}

run "dev_smallest_skus" {
  command = plan

  variables {
    environment   = "dev"
    fabric_admins = ["admin@fernhill.example"]
  }

  assert {
    condition     = azurerm_resource_group.this.name == "rg-fabricbi-dev-eus2-001"
    error_message = "resource group must follow the CAF pattern"
  }

  assert {
    condition     = alltrue([for k in ["env", "owner", "project", "cost-center", "workload", "managed-by"] : contains(keys(azurerm_resource_group.this.tags), k)])
    error_message = "required tags missing"
  }

  assert {
    condition     = module.fabric[0].sku == "F2" && local.fabric_name == "fcfabricbideveus2001"
    error_message = "dev uses the smallest Fabric SKU with a lowercase alphanumeric name"
  }

  assert {
    condition     = length(module.purview) == 0 && length(azurerm_consumption_budget_resource_group.this) == 0
    error_message = "dev skips Purview, and the budget needs contact emails"
  }

  assert {
    condition     = var.eventhubs_sku == "Basic" && var.iothub_sku == "F1" && var.storage_replication == "LRS"
    error_message = "dev must stay on the smallest SKUs"
  }

  assert {
    condition     = length(module.network) == 0 && length(module.private_endpoint) == 0 && local.kv_purview_public
    error_message = "private networking is opt-in; dev keeps public endpoints for a cheap demo"
  }
}

run "trial_capacity_instead_of_f_sku" {
  command = plan

  variables {
    environment            = "dev"
    deploy_fabric_capacity = false
  }

  assert {
    condition     = length(module.fabric) == 0 && output.fabricCapacityName == ""
    error_message = "with a trial capacity no F SKU is created"
  }
}

run "prod_hardened" {
  command = plan

  variables {
    environment           = "prod"
    fabric_sku            = "F4"
    fabric_admins         = ["admin@fernhill.example"]
    eventhubs_sku         = "Standard"
    iothub_sku            = "S1"
    storage_replication   = "ZRS"
    deploy_purview        = true
    purge_protection      = true
    budget_contact_emails = ["finops@fernhill.example"]
  }

  assert {
    condition     = length(module.purview) == 1 && length(azurerm_consumption_budget_resource_group.this) == 1
    error_message = "prod adds Purview and a budget"
  }

  assert {
    condition     = length(azurerm_consumption_budget_resource_group.this[0].notification) == 3
    error_message = "budget alerts at 50, 80 and 100 percent"
  }

  assert {
    condition     = module.fabric[0].sku == "F4"
    error_message = "prod capacity follows the sizing estimate"
  }
}

run "private_key_vault_and_purview" {
  command = plan

  variables {
    environment            = "prod"
    deploy_fabric_capacity = false
    deploy_purview         = true
    private_networking     = true
  }

  assert {
    condition     = length(module.private_endpoint) == 3 && !local.kv_purview_public
    error_message = "private networking adds endpoints for Key Vault, Purview account and Purview portal and turns their public access off"
  }

  assert {
    condition     = startswith(module.network[0].nsg_name, "nsg-")
    error_message = "the private-endpoint subnet sits behind an NSG"
  }
}

run "private_key_vault_without_purview" {
  command = plan

  variables {
    environment            = "dev"
    deploy_fabric_capacity = false
    private_networking     = true
  }

  assert {
    condition     = length(module.private_endpoint) == 1
    error_message = "without Purview only the Key Vault endpoint is created"
  }
}
