# Event Hubs namespace + hubs (live checkouts) and an IoT Hub (freezer sensors). Both feed a Fabric
# Eventstream. Entra ID auth only on Event Hubs (local/SAS auth off). Basic tier allows only the
# $Default consumer group, so the Eventstream consumer group is created on Standard and above.
resource "azurerm_eventhub_namespace" "this" {
  name                          = var.namespace_name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  tags                          = var.tags
  sku                           = var.eventhubs_sku
  capacity                      = var.eventhubs_capacity
  local_authentication_enabled  = false
  minimum_tls_version           = "1.2"
  public_network_access_enabled = var.public_network_access_enabled
}

resource "azurerm_eventhub" "this" {
  for_each          = toset(var.hubs)
  name              = each.value
  namespace_id      = azurerm_eventhub_namespace.this.id
  partition_count   = var.partition_count
  message_retention = var.eventhubs_sku == "Basic" ? 1 : var.message_retention_days
}

resource "azurerm_eventhub_consumer_group" "eventstream" {
  for_each            = var.eventhubs_sku == "Basic" ? toset([]) : toset(var.hubs)
  name                = "fabric-eventstream"
  namespace_name      = azurerm_eventhub_namespace.this.name
  eventhub_name       = azurerm_eventhub.this[each.key].name
  resource_group_name = var.resource_group_name
}

resource "azurerm_iothub" "this" {
  name                          = var.iothub_name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  tags                          = var.tags
  public_network_access_enabled = var.public_network_access_enabled
  min_tls_version               = "1.2"

  sku {
    name     = var.iothub_sku
    capacity = 1
  }

  # Device-to-cloud telemetry stays on the built-in endpoint; the Eventstream reads it with its own
  # consumer group. Free tier (F1) is limited to one hub per subscription.
  fallback_route {
    enabled        = true
    source         = "DeviceMessages"
    endpoint_names = ["events"]
  }
}

resource "azurerm_iothub_consumer_group" "eventstream" {
  name                   = "fabric-eventstream"
  iothub_name            = azurerm_iothub.this.name
  eventhub_endpoint_name = "events"
  resource_group_name    = var.resource_group_name
}

resource "azurerm_role_assignment" "receiver" {
  for_each                         = var.receiver_principal_ids
  scope                            = azurerm_eventhub_namespace.this.id
  role_definition_name             = "Azure Event Hubs Data Receiver"
  principal_id                     = each.value
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_monitor_diagnostic_setting" "eventhubs" {
  name                       = "to-log-analytics"
  target_resource_id         = azurerm_eventhub_namespace.this.id
  log_analytics_workspace_id = var.log_analytics_id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "iothub" {
  name                       = "to-log-analytics"
  target_resource_id         = azurerm_iothub.this.id
  log_analytics_workspace_id = var.log_analytics_id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
