terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project                     = local.project_id
  region                      = local.region
  impersonate_service_account = "deployment-service-account@work-playpen-env.iam.gserviceaccount.com"
}
