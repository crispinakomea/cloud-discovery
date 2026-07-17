FROM otel/opentelemetry-collector-contrib:latest

# Copy your config
COPY otel-config.yaml /etc/otel/config.yaml

# Run the collector with your config
CMD ["--config=/etc/otel/config.yaml"]

EXPOSE 4317 4318
