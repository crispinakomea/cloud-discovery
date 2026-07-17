FROM ghcr.io/dynatrace/dynatrace-otel-collector/dynatrace-otel-collector:0.48.0

# Copy your config
COPY otel-config.yaml /etc/otelcol/otel-collector-config.yaml

# Run the collector with your config
CMD ["--config=/etc/otelcol/otel-collector-config.yaml"]

EXPOSE 4317 4318
