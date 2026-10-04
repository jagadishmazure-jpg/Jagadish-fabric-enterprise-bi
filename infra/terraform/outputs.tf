# Names the deploy pipeline reads after apply (same keys as the Bicep outputs).
output "AZURE_RESOURCE_GROUP" {
  value = azurerm_resource_group.this.name
}

output "fabricCapacityName" {
  value = var.deploy_fabric_capacity ? module.fabric[0].name : ""
}

output "eventHubsNamespace" {
  value = module.streaming.namespace_name
}

output "iotHubName" {
  value = module.streaming.iothub_name
}

output "storageAccount" {
  value = module.storage.name
}

output "keyVaultName" {
  value = module.keyvault.name
}

output "logAnalyticsName" {
  value = module.monitoring.log_analytics_name
}

output "purviewAccount" {
  value = var.deploy_purview ? module.purview[0].name : ""
}

output "ingestIdentityClientId" {
  value = azurerm_user_assigned_identity.ingest.client_id
}
