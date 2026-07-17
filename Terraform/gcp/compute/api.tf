resource "google_project_service" "cloudrun_api" {
  project            = local.project_id
  service            = "run.googleapis.com"
  disable_on_destroy = false
}
