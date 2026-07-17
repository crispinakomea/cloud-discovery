variable "project_id" {
  type     = string
  default  = null
  nullable = true
}

variable "region" {
  type     = string
  default  = null
  nullable = true
}

variable "artifact_registry_repository_id" {
  type     = string
  default  = null
  nullable = true
}

variable "image_tag" {
  type     = string
  default  = null
  nullable = true
}

variable "allow_unauthenticated" {
  type     = bool
  default  = null
  nullable = true
}

variable "restcountries_api_key" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
}

variable "dynatrace_endpoint" {
  type     = string
  default  = null
  nullable = true
}

variable "dynatrace_api_token" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
}

variable "azure_storage_account_name" {
  type     = string
  default  = null
  nullable = true
}

variable "azure_storage_queue_name" {
  type     = string
  default  = null
  nullable = true
}
