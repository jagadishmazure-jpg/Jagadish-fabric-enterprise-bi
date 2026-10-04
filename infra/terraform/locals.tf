locals {
  n         = module.naming.prefix_for
  tenant_id = data.azurerm_client_config.current.tenant_id

  tags = merge({
    env           = var.environment
    owner         = var.owner
    project       = var.project
    "cost-center" = var.cost_center
    workload      = var.workload
    "managed-by"  = "terraform"
  }, var.extra_tags)

  # Fabric capacity names are lowercase alphanumeric only
  fabric_name = substr(replace("fc${var.workload}${var.environment}${module.naming.region_short}${var.instance}${var.name_suffix}", "/[^a-z0-9]/", ""), 0, 63)
}
