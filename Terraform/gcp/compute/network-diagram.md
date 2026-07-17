# GCP Compute Cloud Run Network Diagram

This diagram is based on Terraform resources in this folder and focuses on Cloud Run traffic flow, OpenTelemetry sidecars, and Dynatrace export.

```mermaid
flowchart LR
  %% External users
  U[End User / Browser]

  subgraph GCP[Google Cloud Project: work-playpen-env]
    direction LR

    subgraph CR[Cloud Run Services]
      direction TB

      HP["holiday-planner-app<br/>Ingress: ALL"]
      C["countries-api<br/>Ingress: INTERNAL_ONLY"]
      W["weather-api<br/>Ingress: INTERNAL_ONLY"]
      X["currency-api<br/>Ingress: INTERNAL_ONLY"]

      HP_OTEL["Dynatrace OTel Collector Sidecar<br/>otel-collector-dynatrace"]
      C_OTEL["Dynatrace OTel Collector Sidecar<br/>otel-collector-dynatrace"]
      W_OTEL["Dynatrace OTel Collector Sidecar<br/>otel-collector-dynatrace"]
      X_OTEL["Dynatrace OTel Collector Sidecar<br/>otel-collector-dynatrace"]
    end

    subgraph VPC["VPC Access - holiday planner only"]
      direction TB
      VPCNET[spoke-1-vpc]
      SUBNET[spoke-1-int-1-2 subnet]
    end

    AR["Artifact Registry<br/>eur-78085-acr"]
    SA["Runtime Service Account<br/>Cloud Run runtime SA"]
  end

  DT["Dynatrace OTLP Endpoint<br/>https://...live.dynatrace.com/api/v2/otlp"]

  %% User entrypoint
  U -->|HTTPS| HP

  %% App-to-app calls
  HP -->|COUNTRIES_API_URL| C
  HP -->|WEATHER_API_URL| W
  HP -->|CURRENCY_API_URL| X

  %% Local OTLP from app containers to sidecars
  HP -->|OTLP gRPC :4317<br/>localhost| HP_OTEL
  C -->|OTLP gRPC :4317<br/>localhost| C_OTEL
  W -->|OTLP gRPC :4317<br/>localhost| W_OTEL
  X -->|OTLP gRPC :4317<br/>localhost| X_OTEL

  %% Sidecar export to Dynatrace
  HP_OTEL -->|OTLP export via DT_ENDPOINT and DT_API_TOKEN| DT
  C_OTEL -->|OTLP export via DT_ENDPOINT and DT_API_TOKEN| DT
  W_OTEL -->|OTLP export via DT_ENDPOINT and DT_API_TOKEN| DT
  X_OTEL -->|OTLP export via DT_ENDPOINT and DT_API_TOKEN| DT

  %% Network attachment for holiday-planner
  HP -->|Egress: ALL_TRAFFIC| VPCNET
  VPCNET --> SUBNET

  %% Image pull and runtime identity
  SA --> HP
  SA --> C
  SA --> W
  SA --> X
  AR --> HP
  AR --> C
  AR --> W
  AR --> X
```

## Notes

- `holiday-planner-app` is internet-facing (`INGRESS_TRAFFIC_ALL`).
- The API services (`countries-api`, `weather-api`, `currency-api`) are internal-only (`INGRESS_TRAFFIC_INTERNAL_ONLY`).
- Each Cloud Run service has two containers: app container + Dynatrace OTel collector sidecar.
- Telemetry path is app container -> localhost:4317 sidecar -> Dynatrace OTLP endpoint.
- Only `holiday-planner-app` currently has explicit VPC egress configured (`ALL_TRAFFIC`) into `spoke-1-vpc` / `spoke-1-int-1-2` subnet.
