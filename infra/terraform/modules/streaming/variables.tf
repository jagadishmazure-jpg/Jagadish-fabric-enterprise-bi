variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "namespace_name" {
  type = string
}

variable "iothub_name" {
  type = string
}

variable "hubs" {
  description = "Event hubs to create in the namespace."
  type        = list(string)
  default     = ["pos-events"]
}

variable "eventhubs_sku" {
  description = "Basic (dev), Standard or Premium."
  type        = string
  default     = "Basic"
  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.eventhubs_sku)
    error_message = "eventhubs_sku must be Basic, Standard or Premium."
  }
}

variable "eventhubs_capacity" {
  description = "Throughput units (Basic/Standard) or processing units (Premium)."
  type        = number
  default     = 1
}

variable "partition_count" {
  type    = number
  default = 2
}

variable "message_retention_days" {
  type    = number
  default = 1
}

variable "iothub_sku" {
  description = "F1 (free, one per subscription), B1, S1, ..."
  type        = string
  default     = "F1"
}

variable "public_network_access_enabled" {
  type    = bool
  default = true
}

variable "receiver_principal_ids" {
  description = "static key -> principal id granted Azure Event Hubs Data Receiver on the namespace"
  type        = map(string)
  default     = {}
}

variable "log_analytics_id" {
  type = string
}
