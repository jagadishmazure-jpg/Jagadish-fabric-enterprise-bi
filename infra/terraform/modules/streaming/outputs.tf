output "namespace_id" {
  value = azurerm_eventhub_namespace.this.id
}

output "namespace_name" {
  value = azurerm_eventhub_namespace.this.name
}

output "hub_names" {
  value = [for h in azurerm_eventhub.this : h.name]
}

output "iothub_id" {
  value = azurerm_iothub.this.id
}

output "iothub_name" {
  value = azurerm_iothub.this.name
}
