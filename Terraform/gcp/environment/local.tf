locals {
  organization_id    = var.organization_id == null ? null : "organizations/${var.organization_id}"
  default_project_id = "work-playpen-env"
  project_id         = coalesce(var.project_id, local.default_project_id)
  default_region     = "europe-west2"
  region             = coalesce(var.region, local.default_region)
  virtual_networks   = ["hub", "spoke-1", "spoke-2"]

  virtual_networks_addresses = {
    "hub"     = "10.1.0.0/24"
    "spoke-2" = "10.1.2.0/24"
    "spoke-1" = "10.1.1.0/24"
  }

  hub_subnet_addresses = {
    "int-1" = "10.1.0.0/27"
    "int-2" = "10.1.0.32/27"
    "int-3" = "10.1.0.64/27"
    "int-4" = "10.1.0.96/27"
  }

  spoke_1_subnet_addresses = {
    "int-1-2" = "10.1.1.0/26"
    "int-3" = "10.1.1.64/27"
    "int-4" = "10.1.1.96/27"
    "pen"   = "10.1.1.128/27"
  }

  spoke_2_subnet_addresses = {
    "int-1" = "10.1.2.0/27"
    "int-2" = "10.1.2.32/27"
    "int-3" = "10.1.2.64/27"
    "int-4" = "10.1.2.96/27"
    "pen"   = "10.1.2.128/27"
  }
}
