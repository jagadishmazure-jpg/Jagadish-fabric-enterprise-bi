# prod: sized from docs/cost-estimate.md (assumed load), Standard Event Hubs with a dedicated
# Eventstream consumer group, S1 IoT Hub, zone-redundant storage, Purview on, purge protection on.
environment            = "prod"
location               = "eastus2"
instance               = "001"
deploy_fabric_capacity = true
fabric_sku             = "F4"
fabric_admins          = []
eventhubs_sku          = "Standard"
eventhubs_capacity     = 2
iothub_sku             = "S1"
storage_replication    = "ZRS"
deploy_purview         = true
log_daily_quota_gb     = -1
log_retention_days     = 90
monthly_budget         = 2000
budget_contact_emails  = []
purge_protection       = true
public_network_access  = true
