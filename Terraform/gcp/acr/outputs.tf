output "artifact_registry_repository_id" {
  value = google_artifact_registry_repository.container_registry.repository_id
}

output "artifact_registry_repository_url" {
  value = format(
    "%s-docker.pkg.dev/%s/%s",
    local.region,
    local.project_id,
    google_artifact_registry_repository.container_registry.repository_id
  )
}
