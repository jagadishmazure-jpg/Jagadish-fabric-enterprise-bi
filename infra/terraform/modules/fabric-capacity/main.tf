# Microsoft Fabric capacity (F SKU). The capacity is the only Fabric resource in ARM; workspaces,
# Lakehouses, Eventhouses, notebooks and semantic models are Fabric items created through the
# Fabric REST API (see .github/scripts/deploy.sh and scripts/publish_fabric_items.py).
# Billing is per hour while the capacity is running; pause it when idle.
resource "azurerm_fabric_capacity" "this" {
  name                   = var.name
  resource_group_name    = var.resource_group_name
  location               = var.location
  tags                   = var.tags
  administration_members = var.admin_members

  sku {
    name = var.sku
    tier = "Fabric"
  }
}
