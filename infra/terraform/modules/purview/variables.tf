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

variable "name" {
  type = string
}

variable "managed_resource_group_name" {
  type = string
}

variable "public_network_enabled" {
  type    = bool
  default = true
}

variable "scan_scopes" {
  description = "static key -> storage account id the Purview identity may read for scans"
  type        = map(string)
  default     = {}
}
