import azure.functions as func
import logging
import requests
import json
import os
import socket
import time
from urllib.parse import urlparse

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


# Configure OTel resource attributes (reads OTEL_SERVICE_NAME / OTEL_RESOURCE_ATTRIBUTES env vars)
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
            logging.getLogger().addHandler(otel_handler)
            logger.setLevel(logging.INFO)

            tracer = trace.get_tracer(__name__)
            logger.info("OTel logging and tracing initialised successfully")
        else:
            logger.warning("OTLP exporter disabled because the collector endpoint was not available.")
            tracer = trace.get_tracer(__name__)
    else:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT is not set; telemetry will remain disabled.")
        tracer = trace.get_tracer(__name__)

except Exception as _otel_ex:
    logger.warning(f"OTel initialisation failed, continuing without telemetry: {_otel_ex}")
    tracer = trace.get_tracer(__name__)


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="weather")
def get_temperature(req: func.HttpRequest) -> func.HttpResponse:
    logger.info('Fetching temperature by coordinates.')

    latitude = req.params.get("latitude")
    longitude = req.params.get("longitude")

    if not latitude or not longitude:
        return func.HttpResponse(
            json.dumps({"error": "Please provide 'latitude' and 'longitude' as query parameters."}),
            status_code=400,
            mimetype="application/json"
        )

    with tracer.start_as_current_span("get_weather") as span:
        span.set_attribute("weather.latitude", latitude)
        span.set_attribute("weather.longitude", longitude)

        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "current_weather": True
            }
            logger.info(f"Requesting weather from open-meteo.com: {url} with params={params}")
            response = requests.get(
                url,
                params=params,
                timeout=60
            )
            logger.debug(f"Received weather response status {response.status_code} from {url} for latitude={latitude}, longitude={longitude}")
            response.raise_for_status()
            data = response.json()

            current = data.get("current_weather", {})
            weathercode = current.get("weathercode", 0)

            span.set_attribute("weather.temperature", current.get("temperature"))
            span.set_attribute("weather.weathercode", weathercode)

            logger.info(f"Successfully fetched weather for lat={latitude}, lon={longitude}: temperature={current.get('temperature')}")

            return func.HttpResponse(
                json.dumps({
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "temperature": current.get("temperature"),
                    "temperature_unit": "°C",
                    "windspeed": current.get("windspeed"),
                    "windspeed_unit": "km/h",
                    "weathercode": weathercode,
                    "time": current.get("time")
                }, indent=2),
                status_code=200,
                mimetype="application/json"
            )
        except requests.exceptions.RequestException as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Error fetching weather: {e}")
            return func.HttpResponse(
                json.dumps({"error": "Failed to fetch weather from open-meteo.com", "details": str(e)}),
                status_code=500,
                mimetype="application/json"
            )