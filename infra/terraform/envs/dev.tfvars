# dev: smallest SKUs. F2 capacity (pause when idle), Basic Event Hubs, free IoT Hub, LRS storage,
# no Purview, 1 GB/day log cap. Set fabric_admins to your UPN before the first apply.
environment            = "dev"
location               = "eastus2"
instance               = "001"
deploy_fabric_capacity = true
fabric_sku             = "F2"
fabric_admins          = []
eventhubs_sku          = "Basic"
eventhubs_capacity     = 1
iothub_sku             = "F1"
storage_replication    = "LRS"
deploy_purview         = false
log_daily_quota_gb     = 1
log_retention_days     = 30
monthly_budget         = 50
budget_contact_emails  = []
purge_protection       = false
public_network_access  = true
