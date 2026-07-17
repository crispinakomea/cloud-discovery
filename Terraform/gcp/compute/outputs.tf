output "cloud_run_service_names" {
  value = concat(
    [for svc in google_cloud_run_v2_service.api : svc.name],
    [google_cloud_run_v2_service.holiday_planner_app.name]
  )
}

output "cloud_run_service_urls" {
  value = merge(
    {
      for name, svc in google_cloud_run_v2_service.api :
      name => svc.uri
    },
    {
      "holiday-planner-app" = google_cloud_run_v2_service.holiday_planner_app.uri
    }
  )
}

output "cloud_run_service_images" {
  value = merge(
    local.cloud_run_service_images,
    {
      "holiday-planner-app" = local.holiday_planner_image
    }
  )
}

output "otel_collector_sidecar_image" {
  value = local.otel_collector_standard_image
}
