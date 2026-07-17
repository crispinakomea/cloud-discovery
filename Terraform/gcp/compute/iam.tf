resource "google_project_iam_member" "cloud_run_runtime_artifact_reader" {
  project = local.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.cloud_run_runtime.email}"
}
