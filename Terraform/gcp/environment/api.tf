resource "google_project_service" "accesscontextmanager_api" {
  project            = local.project_id
  service            = "accesscontextmanager.googleapis.com"
  disable_on_destroy = false
}