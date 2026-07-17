resource "google_artifact_registry_repository" "container_registry" {
  location = local.region
  repository_id = join("-", tolist([
    substr(replace(local.region, "-", ""), 0, 3),
    substr(tostring(data.google_project.current.number), 0, 5),
    "acr"
  ]))
  description = "Artifact Registry repository for application container images"
  format      = local.repository_format

  depends_on = [
    google_project_service.artifactregistry_api
  ]
}
