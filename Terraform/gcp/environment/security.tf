resource "google_access_context_manager_access_policy" "access_policy" {
  count  = local.organization_id == null ? 0 : 1
  parent = local.organization_id
  title  = "Org Access Policy"
}

resource "google_access_context_manager_access_level" "network_access_level" {
  count  = local.organization_id == null ? 0 : 1
  parent = google_access_context_manager_access_policy.access_policy[0].name
  name   = format("%s/accessLevels/%s", google_access_context_manager_access_policy.access_policy[0].name, "network")
  title  = "Network Access Level"

  basic {
    combining_function = "OR"

    conditions {
      ip_subnetworks = values(local.virtual_networks_addresses)
    }
  }
}

resource "google_access_context_manager_service_perimeter" "network_service_perimeter" {
  count  = local.organization_id == null ? 0 : 1
  parent = google_access_context_manager_access_policy.access_policy[0].name
  name   = format("%s/servicePerimeters/%s", google_access_context_manager_access_policy.access_policy[0].name, "network")
  title  = "Network Service Perimeter"

  status {
    resources = [
      format("projects/%s", data.google_project.current.number)
    ]

    restricted_services = [
      "artifactregistry.googleapis.com"
    ]

    access_levels = [
      google_access_context_manager_access_level.network_access_level[0].name
    ]
  }
}
