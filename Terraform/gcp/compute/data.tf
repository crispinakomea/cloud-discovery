data "google_project" "current" {
  project_id = local.project_id
}

data "google_compute_network" "spoke_1_vpc" {
  name = join("-", tolist([
    substr(replace(local.region, "-", ""), 0, 3),
    substr(tostring(data.google_project.current.number), 0, 5),
    "spoke-1",
    "vpc"
  ]))
}

data "google_compute_subnetwork" "spoke_1_int_1_2_subnet" {
  name = join("-", tolist([
    substr(replace(local.region, "-", ""), 0, 3),
    substr(tostring(data.google_project.current.number), 0, 5),
    "spoke-1",
    "int-1-2",
    "snet"
  ]))
  region = local.region
}

