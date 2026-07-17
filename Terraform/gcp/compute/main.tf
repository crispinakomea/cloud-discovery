resource "google_service_account" "cloud_run_runtime" {
  account_id = join("-", tolist([
    substr(replace(local.region, "-", ""), 0, 3),
    substr(tostring(data.google_project.current.number), 0, 5),
    "cr",
    "rt"
  ]))

  display_name = "Cloud Run Runtime Service Account"
}

resource "google_cloud_run_v2_service" "api" {
  for_each = local.cloud_run_service_images

  name                = each.key
  location            = local.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  deletion_protection = false

  template {
    service_account = google_service_account.cloud_run_runtime.email

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = each.value

      dynamic "env" {
        for_each = merge(
          {
            OTEL_SERVICE_NAME          = format("%s-flask", each.key)
            OTEL_RESOURCE_ATTRIBUTES   = format("service.name=%s-flask,service.version=1.0.0,deployment.environment=production", each.key)
            OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4317"
            OTEL_EXPORTER_OTLP_PROTOCOL = "grpc"
          },
          each.key == "countries-api" ? { RESTCOUNTRIES_API_KEY = local.restcountries_api_key } : {}
        )
        content {
          name  = env.key
          value = env.value
        }
      }

      ports {
        container_port = 80
      }
    }

    containers {
      image = local.otel_collector_dynatrace_image

      env {
        name  = "DT_ENDPOINT"
        value = local.dynatrace_endpoint
      }

      env {
        name  = "DT_API_TOKEN"
        value = local.dynatrace_api_token
      }
    }

    # vpc_access {
    #   egress = "ALL_TRAFFIC"

    #   network_interfaces {
    #     network    = data.google_compute_network.spoke_1_vpc.id
    #     subnetwork = data.google_compute_subnetwork.spoke_1_int_1_2_subnet.id
    #   }
    # }
  }

  depends_on = [
    google_project_service.cloudrun_api,
    google_project_iam_member.cloud_run_runtime_artifact_reader
  ]
}

resource "google_cloud_run_v2_service_iam_member" "api_invoker" {
  for_each = local.allow_unauthenticated ? google_cloud_run_v2_service.api : {}

  project  = local.project_id
  location = each.value.location
  name     = each.value.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service" "holiday_planner_app" {
  name                = "holiday-planner-app"
  location            = local.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.cloud_run_runtime.email

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = local.holiday_planner_image

      env {
        name  = "COUNTRIES_API_URL"
        value = google_cloud_run_v2_service.api["countries-api"].uri
      }

      env {
        name  = "WEATHER_API_URL"
        value = google_cloud_run_v2_service.api["weather-api"].uri
      }

      env {
        name  = "CURRENCY_API_URL"
        value = google_cloud_run_v2_service.api["currency-api"].uri
      }

      env {
        name  = "MANAGED_IDENTITY_CLIENT_ID"
        value = google_service_account.cloud_run_runtime.unique_id
      }

      env {
        name  = "AZURE_STORAGE_ACCOUNT_NAME"
        value = local.azure_storage_account_name
      }

      env {
        name  = "AZURE_STORAGE_QUEUE_NAME"
        value = local.azure_storage_queue_name
      }

      env {
        name  = "OTEL_SERVICE_NAME"
        value = "holiday-planner-flask"
      }

      env {
        name  = "OTEL_RESOURCE_ATTRIBUTES"
        value = "service.name=holiday-planner-flask,service.version=1.0.0,deployment.environment=production"
      }

      env {
        name  = "OTEL_EXPORTER_OTLP_ENDPOINT"
        value = "http://localhost:4317"
      }

      env {
        name  = "OTEL_EXPORTER_OTLP_PROTOCOL"
        value = "grpc"
      }

      ports {
        container_port = 80
      }
    }

    containers {
      image = local.otel_collector_dynatrace_image

      env {
        name  = "DT_ENDPOINT"
        value = local.dynatrace_endpoint
      }

      env {
        name  = "DT_API_TOKEN"
        value = local.dynatrace_api_token
      }
    }

    vpc_access {
      egress = "ALL_TRAFFIC"

      network_interfaces {
        network    = data.google_compute_network.spoke_1_vpc.id
        subnetwork = data.google_compute_subnetwork.spoke_1_int_1_2_subnet.id
      }
    }
  }

  depends_on = [
    google_project_service.cloudrun_api,
    google_project_iam_member.cloud_run_runtime_artifact_reader,
    google_cloud_run_v2_service.api
  ]
}

resource "google_cloud_run_v2_service_iam_member" "holiday_planner_invoker" {
  count = local.allow_unauthenticated ? 1 : 0

  project  = local.project_id
  location = google_cloud_run_v2_service.holiday_planner_app.location
  name     = google_cloud_run_v2_service.holiday_planner_app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
