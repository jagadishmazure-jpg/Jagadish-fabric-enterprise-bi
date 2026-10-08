# Azure footprint for the Fabric enterprise BI build. Mirrors infra/main.bicep (same resources,
# CAF names and tags). Fabric workspace items are NOT ARM resources; they are published by the
# deploy pipeline through the Fabric REST API / fabric-cicd after this stack is applied.
data "azurerm_client_config" "current" {}

module "naming" {
  source      = "./modules/naming"
  workload    = var.workload
  environment = var.environment
  location    = var.location
  instance    = var.instance
  suffix      = var.name_suffix
}

resource "azurerm_resource_group" "this" {
  name     = module.naming.resource_group
  location = var.location
  tags     = local.tags
}

# One identity for ingestion connections (Eventstream -> Event Hubs, shortcut -> landing storage).
resource "azurerm_user_assigned_identity" "ingest" {
  name                = "${local.n["id"]}-ingest"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = local.tags
}

module "monitoring" {
  source              = "./modules/monitoring"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = local.tags
  log_analytics_name  = module.naming.log_analytics
  app_insights_name   = module.naming.app_insights
  retention_in_days   = var.log_retention_days
  daily_quota_gb      = var.log_daily_quota_gb
}

module "keyvault" {
  source                        = "./modules/keyvault"
  resource_group_name           = azurerm_resource_group.this.name
  location                      = var.location
  tags                          = local.tags
  name                          = module.naming.key_vault
  tenant_id                     = local.tenant_id
  purge_protection_enabled      = var.purge_protection
  public_network_access_enabled = local.kv_purview_public
  secret_reader_principal_ids   = { ingest = azurerm_user_assigned_identity.ingest.principal_id }
}

module "streaming" {
  source                        = "./modules/streaming"
  resource_group_name           = azurerm_resource_group.this.name
  location                      = var.location
  tags                          = local.tags
  namespace_name                = "${local.n["evhns"]}${module.naming.suffix}"
  iothub_name                   = "${local.n["iot"]}${module.naming.suffix}"
  hubs                          = ["pos-events"]
  eventhubs_sku                 = var.eventhubs_sku
  eventhubs_capacity            = var.eventhubs_capacity
  iothub_sku                    = var.iothub_sku
  public_network_access_enabled = var.public_network_access
  receiver_principal_ids        = { ingest = azurerm_user_assigned_identity.ingest.principal_id }
  log_analytics_id              = module.monitoring.log_analytics_id
}

module "storage" {
  source                        = "./modules/storage"
  resource_group_name           = azurerm_resource_group.this.name
  location                      = var.location
  tags                          = local.tags
  name                          = module.naming.storage_account
  replication_type              = var.storage_replication
  containers                    = ["landing", "partner-share"]
  public_network_access_enabled = var.public_network_access
  reader_principal_ids          = { ingest = azurerm_user_assigned_identity.ingest.principal_id }
}

module "fabric" {
  count               = var.deploy_fabric_capacity ? 1 : 0
  source              = "./modules/fabric-capacity"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = local.tags
  name                = local.fabric_name
  sku                 = var.fabric_sku
  admin_members       = var.fabric_admins
}

module "purview" {
  count                       = var.deploy_purview ? 1 : 0
  source                      = "./modules/purview"
  resource_group_name         = azurerm_resource_group.this.name
  location                    = var.location
  tags                        = local.tags
  name                        = "${local.n["pview"]}${module.naming.suffix}"
  managed_resource_group_name = "${module.naming.resource_group}-purview-managed"
  public_network_enabled      = local.kv_purview_public
  scan_scopes                 = { landing = module.storage.id }
}

resource "azurerm_monitor_diagnostic_setting" "keyvault" {
  name                       = "to-log-analytics"
  target_resource_id         = module.keyvault.id
  log_analytics_workspace_id = module.monitoring.log_analytics_id

  enabled_log {
    category_group = "audit"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_consumption_budget_resource_group" "this" {
  count             = length(var.budget_contact_emails) > 0 ? 1 : 0
  name              = local.n["budget"]
  resource_group_id = azurerm_resource_group.this.id
  amount            = var.monthly_budget
  time_grain        = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", plantimestamp())
  }

  dynamic "notification" {
    for_each = toset([50, 80, 100])
    content {
      enabled        = true
      threshold      = notification.value
      operator       = "GreaterThanOrEqualTo"
      threshold_type = notification.value == 100 ? "Forecasted" : "Actual"
      contact_emails = var.budget_contact_emails
    }
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}

# ---- optional private networking for Key Vault and Purview (off by default; not deployed) ----
locals {
  # Private networking forces public access off on the two services it fronts.
  kv_purview_public = var.public_network_access && !var.private_networking
  pe_targets = merge(
    { keyvault = { id = module.keyvault.id, group = "vault", zone = "keyvault" } },
    var.deploy_purview ? {
      purview-account = { id = module.purview[0].id, group = "account", zone = "purview" }
      purview-portal  = { id = module.purview[0].id, group = "portal", zone = "purviewstudio" }
    } : {},
  )
}

module "network" {
  source              = "./modules/private-network"
  count               = var.private_networking ? 1 : 0
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = local.tags
  name                = module.naming.vnet
  dns_zones = {
    keyvault      = "privatelink.vaultcore.azure.net"
    purview       = "privatelink.purview.azure.com"
    purviewstudio = "privatelink.purviewstudio.azure.com"
  }
}

module "private_endpoint" {
  source              = "./modules/private-endpoint"
  for_each            = var.private_networking ? local.pe_targets : {}
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = local.tags
  name                = "pe-${each.key}-${module.naming.base}"
  subnet_id           = module.network[0].pe_subnet_id
  target_resource_id  = each.value.id
  group_id            = each.value.group
  dns_zone_ids        = [module.network[0].zone_ids[each.value.zone]]
}
