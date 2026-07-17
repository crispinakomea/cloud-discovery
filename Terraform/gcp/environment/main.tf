resource "google_project_service" "compute_api" {
  project            = local.project_id
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}

resource "google_compute_network" "virtual_network" {
  for_each                = local.virtual_networks_addresses
  name                    = join("-", tolist([substr(replace(local.region, "-", ""), 0, 3), substr(tostring(data.google_project.current.number), 0, 5), each.key, "vpc"]))
  auto_create_subnetworks = false

  depends_on = [
    google_project_service.compute_api
  ]
}

resource "google_compute_subnetwork" "hub_subnet" {
  for_each                 = local.hub_subnet_addresses
  name                     = join("-", tolist([substr(replace(local.region, "-", ""), 0, 3), substr(tostring(data.google_project.current.number), 0, 5), "hub", each.key, "snet"]))
  network                  = google_compute_network.virtual_network["hub"].id
  region                   = local.region
  ip_cidr_range            = each.value
  private_ip_google_access = true

  depends_on = [
    google_project_service.compute_api
  ]
}

resource "google_compute_subnetwork" "spoke_1_subnet" {
  for_each                 = local.spoke_1_subnet_addresses
  name                     = join("-", tolist([substr(replace(local.region, "-", ""), 0, 3), substr(tostring(data.google_project.current.number), 0, 5), "spoke-1", each.key, "snet"]))
  network                  = google_compute_network.virtual_network["spoke-1"].id
  region                   = local.region
  ip_cidr_range            = each.value
  private_ip_google_access = true

  depends_on = [
    google_project_service.compute_api
  ]
}

resource "google_compute_subnetwork" "spoke_2_subnet" {
  for_each                 = local.spoke_2_subnet_addresses
  name                     = join("-", tolist([substr(replace(local.region, "-", ""), 0, 3), substr(tostring(data.google_project.current.number), 0, 5), "spoke-2", each.key, "snet"]))
  network                  = google_compute_network.virtual_network["spoke-2"].id
  region                   = local.region
  ip_cidr_range            = each.value
  private_ip_google_access = true

  depends_on = [
    google_project_service.compute_api
  ]
}

resource "google_compute_network_peering" "hub_to_spoke_1_network_peering" {
  name                 = "hub-to-spoke-1"
  network              = google_compute_network.virtual_network["hub"].self_link
  peer_network         = google_compute_network.virtual_network["spoke-1"].self_link
  export_custom_routes = true
  import_custom_routes = true

  depends_on = [
    google_project_service.compute_api
  ]
}

resource "google_compute_network_peering" "spoke_1_to_hub_network_peering" {
  name                 = "spoke-1-to-hub"
  network              = google_compute_network.virtual_network["spoke-1"].self_link
  peer_network         = google_compute_network.virtual_network["hub"].self_link
  export_custom_routes = true
  import_custom_routes = true

  depends_on = [
    google_project_service.compute_api
  ]
}

resource "google_compute_network_peering" "hub_to_spoke_2_network_peering" {
  name                 = "hub-to-spoke-2"
  network              = google_compute_network.virtual_network["hub"].self_link
  peer_network         = google_compute_network.virtual_network["spoke-2"].self_link
  export_custom_routes = true
  import_custom_routes = true

  depends_on = [
    google_project_service.compute_api
  ]
}

resource "google_compute_network_peering" "spoke_2_to_hub_network_peering" {
  name                 = "spoke-2-to-hub"
  network              = google_compute_network.virtual_network["spoke-2"].self_link
  peer_network         = google_compute_network.virtual_network["hub"].self_link
  export_custom_routes = true
  import_custom_routes = true

  depends_on = [
    google_project_service.compute_api
  ]
}
