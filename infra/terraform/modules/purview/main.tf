# Microsoft Purview account for the catalog, lineage, sensitivity labels and scanning. Optional in
# dev (cost); its system-assigned identity gets read access to the landing storage for scans.
resource "azurerm_purview_account" "this" {
  name                        = var.name
  resource_group_name         = var.resource_group_name
  location                    = var.location
  tags                        = var.tags
  public_network_enabled      = var.public_network_enabled
  managed_resource_group_name = var.managed_resource_group_name

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_role_assignment" "scan_reader" {
  for_each             = var.scan_scopes
  scope                = each.value
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_purview_account.this.identity[0].principal_id
  principal_type       = "ServicePrincipal"
}
