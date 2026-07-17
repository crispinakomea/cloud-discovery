locals {
  default_project_id = "work-playpen-env"
  project_id         = coalesce(var.project_id, local.default_project_id)
  default_region     = "europe-west2"
  region             = coalesce(var.region, local.default_region)
  repository_format  = "DOCKER"
}
