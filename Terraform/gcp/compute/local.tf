locals {
  default_project_id                  = "work-playpen-env"
  project_id                          = coalesce(var.project_id, local.default_project_id)
  default_region                      = "europe-west2"
  region                              = coalesce(var.region, local.default_region)
  default_artifact_registry_repository_id = "eur-78085-acr"
  artifact_registry_repository_id     = coalesce(var.artifact_registry_repository_id, local.default_artifact_registry_repository_id)
  default_image_tag                   = "v1.0.0"
  image_tag                           = coalesce(var.image_tag, local.default_image_tag)
  default_allow_unauthenticated       = true
  allow_unauthenticated               = coalesce(var.allow_unauthenticated, local.default_allow_unauthenticated)
  default_restcountries_api_key       = ""
  restcountries_api_key               = coalesce(var.restcountries_api_key, local.default_restcountries_api_key)
  default_dynatrace_endpoint          = "https://bla74750.live.dynatrace.com/api/v2/otlp"
  dynatrace_endpoint                  = coalesce(var.dynatrace_endpoint, local.default_dynatrace_endpoint)
  default_dynatrace_api_token         = ""
  dynatrace_api_token                 = coalesce(var.dynatrace_api_token, local.default_dynatrace_api_token)
  default_azure_storage_account_name  = "mystorageaccount"
  azure_storage_account_name          = coalesce(var.azure_storage_account_name, local.default_azure_storage_account_name)
  default_azure_storage_queue_name    = "myqueue"
  azure_storage_queue_name            = coalesce(var.azure_storage_queue_name, local.default_azure_storage_queue_name)

  otel_collector_standard_image = format(
    "%s-docker.pkg.dev/%s/%s/%s:%s",
    local.region,
    local.project_id,
    local.artifact_registry_repository_id,
    "otel-collector-standard",
    local.image_tag
  )

  otel_collector_dynatrace_image = format(
    "%s-docker.pkg.dev/%s/%s/%s:%s",
    local.region,
    local.project_id,
    local.artifact_registry_repository_id,
    "otel-collector-dynatrace",
    local.image_tag
  )

  holiday_planner_image = format(
    "%s-docker.pkg.dev/%s/%s/%s:%s",
    local.region,
    local.project_id,
    local.artifact_registry_repository_id,
    "holiday-planner-flask",
    local.image_tag
  )

  cloud_run_service_images = {
    "countries-api" = format(
      "%s-docker.pkg.dev/%s/%s/%s:%s",
      local.region,
      local.project_id,
      local.artifact_registry_repository_id,
      "countries-api-flask",
      local.image_tag
    )
    "weather-api" = format(
      "%s-docker.pkg.dev/%s/%s/%s:%s",
      local.region,
      local.project_id,
      local.artifact_registry_repository_id,
      "weather-api-flask",
      local.image_tag
    )
    "currency-api" = format(
      "%s-docker.pkg.dev/%s/%s/%s:%s",
      local.region,
      local.project_id,
      local.artifact_registry_repository_id,
      "currency-api-flask",
      local.image_tag
    )
  }
}
