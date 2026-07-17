import logging
import requests
import os
import socket
import time
from urllib.parse import urlparse
from flask import Flask, jsonify, request

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry import trace
from opentelemetry.trace import StatusCode
from opentelemetry._logs import set_logger_provider
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def wait_for_endpoint(url: str, timeout: int = 30, interval: float = 1.0) -> bool:
    parsed = urlparse(url if '://' in url else f'http://{url}')
    host = parsed.hostname
    port = parsed.port or 4317
    if not host:
        logger.warning(f"Invalid OTLP endpoint URL: {url}")
        return False
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            with socket.create_connection((host, port), timeout=interval):
                logger.info(f"OTLP endpoint reachable at {host}:{port}")
                return True
        except OSError:
            logger.debug(f"Waiting for OTLP endpoint {host}:{port}...")
            time.sleep(interval)
    logger.warning(f"OTLP endpoint {host}:{port} was not reachable within {timeout} seconds.")
    return False


# ── OTel setup ────────────────────────────────────────────────────────────────
try:
    resource = Resource.create()

    logger_provider = LoggerProvider(resource=resource)
    tracer_provider = TracerProvider(resource=resource)

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        if wait_for_endpoint(otlp_endpoint, timeout=30):
            otlp_log_exporter = OTLPLogExporter(endpoint=otlp_endpoint, insecure=True, compression=None)
            otlp_span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True, compression=None)

            logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_log_exporter))
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_span_exporter))

            set_logger_provider(logger_provider)
            trace.set_tracer_provider(tracer_provider)

            otel_handler = LoggingHandler(logger_provider=logger_provider)
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.INFO)
            root_logger.addHandler(otel_handler)
            logger.setLevel(logging.INFO)

            tracer = trace.get_tracer(__name__)
            logger.info("OTel logging and tracing initialised successfully")
            logger_provider.force_flush()
        else:
            logger.warning("OTLP exporter disabled because the collector endpoint was not available.")
            tracer = trace.get_tracer(__name__)
    else:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT is not set; telemetry will remain disabled.")
        tracer = trace.get_tracer(__name__)

except Exception as _otel_ex:
    logger.warning(f"OTel initialisation failed, continuing without telemetry: {_otel_ex}")
    tracer = trace.get_tracer(__name__)

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()


@app.route("/weather", methods=["GET"])
def get_temperature():
    logger.info("Fetching temperature by coordinates.")

    latitude = request.args.get("latitude")
    longitude = request.args.get("longitude")

    if not latitude or not longitude:
        return jsonify({"error": "Please provide 'latitude' and 'longitude' as query parameters."}), 400

    with tracer.start_as_current_span("get_weather") as span:
        span.set_attribute("weather.latitude", latitude)
        span.set_attribute("weather.longitude", longitude)
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "current_weather": True,
            }
            logger.info(f"Requesting weather from open-meteo.com: {url} with params={params}")
            response = requests.get(url, params=params, timeout=60)
            logger.debug(f"Weather response status {response.status_code} from {url} for lat={latitude}, lon={longitude}")
            response.raise_for_status()
            data = response.json()

            current = data.get("current_weather", {})
            weathercode = current.get("weathercode", 0)

            span.set_attribute("weather.temperature", current.get("temperature"))
            span.set_attribute("weather.weathercode", weathercode)

            logger.info(f"Fetched weather for lat={latitude}, lon={longitude}: temperature={current.get('temperature')}")

            return jsonify({
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
                "temperature": current.get("temperature"),
                "temperature_unit": "°C",
                "windspeed": current.get("windspeed"),
                "windspeed_unit": "km/h",
                "weathercode": weathercode,
                "time": current.get("time"),
            }), 200

        except requests.exceptions.RequestException as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Error fetching weather: {e}")
            return jsonify({"error": "Failed to fetch weather from open-meteo.com", "details": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
