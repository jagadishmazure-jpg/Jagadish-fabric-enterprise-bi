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
  description = "3-63 lowercase letters and digits."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9]{2,62}$", var.name))
    error_message = "Fabric capacity names are 3-63 lowercase letters/digits, starting with a letter."
  }
}

variable "sku" {
  description = "F2 (dev) up to F2048."
  type        = string
  default     = "F2"
  validation {
    condition     = contains(["F2", "F4", "F8", "F16", "F32", "F64", "F128", "F256", "F512", "F1024", "F2048"], var.sku)
    error_message = "sku must be an F SKU from F2 to F2048."
  }
}

variable "admin_members" {
  description = "User principal names or object ids of capacity administrators."
  type        = list(string)
  validation {
    condition     = length(var.admin_members) > 0
    error_message = "Set fabric_admins (at least one capacity administrator) or deploy_fabric_capacity = false."
  }
}
