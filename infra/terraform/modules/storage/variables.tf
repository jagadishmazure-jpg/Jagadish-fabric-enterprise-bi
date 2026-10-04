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

variable "replication_type" {
  description = "LRS in dev, ZRS or GZRS in prod."
  type        = string
  default     = "LRS"
}

variable "containers" {
  type    = list(string)
  default = ["landing"]
}

variable "public_network_access_enabled" {
  type    = bool
  default = true
}

variable "reader_principal_ids" {
  description = "static key -> principal id granted Storage Blob Data Reader"
  type        = map(string)
  default     = {}
}

variable "contributor_principal_ids" {
  description = "static key -> principal id granted Storage Blob Data Contributor"
  type        = map(string)
  default     = {}
}
