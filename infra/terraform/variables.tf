# ---- naming / tagging ----
variable "workload" {
  type    = string
  default = "fabricbi"
}

variable "environment" {
  description = "dev | test | prod"
  type        = string
}

variable "location" {
  type    = string
  default = "eastus2"
}

variable "instance" {
  type    = string
  default = "001"
}

variable "name_suffix" {
  description = "Optional suffix for globally unique names (set when forking)."
  type        = string
  default     = ""
}

variable "owner" {
  type    = string
  default = "jagadish.meduri"
}

variable "project" {
  type    = string
  default = "fabric-enterprise-bi"
}

variable "cost_center" {
  type    = string
  default = "portfolio"
}

variable "extra_tags" {
  type    = map(string)
  default = {}
}

# ---- Fabric ----
variable "deploy_fabric_capacity" {
  description = "Create an F-SKU capacity. Set false to use a Fabric trial capacity instead (no Azure charge)."
  type        = bool
  default     = true
}

variable "fabric_sku" {
  type    = string
  default = "F2"
}

variable "fabric_admins" {
  description = "Capacity administrators (UPNs or object ids). Required when deploy_fabric_capacity is true."
  type        = list(string)
  default     = []
}

# ---- streaming ----
variable "eventhubs_sku" {
  type    = string
  default = "Basic"
}

variable "eventhubs_capacity" {
  type    = number
  default = 1
}

variable "iothub_sku" {
  description = "F1 is free but limited to one per subscription; use B1 if one already exists."
  type        = string
  default     = "F1"
}

# ---- storage / data ----
variable "storage_replication" {
  type    = string
  default = "LRS"
}

variable "deploy_purview" {
  description = "Create a Microsoft Purview account (off in dev to keep cost down)."
  type        = bool
  default     = false
}

# ---- monitoring / cost ----
variable "log_daily_quota_gb" {
  description = "Log Analytics daily ingestion cap (GB). -1 = no cap."
  type        = number
  default     = 1
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "monthly_budget" {
  description = "Resource-group budget in the billing currency; alerts at 50%, 80% and 100%."
  type        = number
  default     = 50
}

variable "budget_contact_emails" {
  description = "Who gets budget alerts. Empty = no budget resource."
  type        = list(string)
  default     = []
}

# ---- security ----
variable "purge_protection" {
  type    = bool
  default = false
}

variable "public_network_access" {
  description = "Public endpoints with Entra ID auth in dev; prod turns this off and adds private endpoints (planned)."
  type        = bool
  default     = true
}
