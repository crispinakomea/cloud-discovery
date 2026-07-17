from flask import Flask, render_template, jsonify, request
import requests
import os
import json
import uuid
import socket
import time
from urllib.parse import urlparse
from datetime import datetime, timezone
from azure.storage.queue import QueueClient
from azure.identity import ManagedIdentityCredential
import base64

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry import trace
from opentelemetry.trace import StatusCode
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry._logs import set_logger_provider
import logging

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

RequestsInstrumentor().instrument()

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

# ── Azure Function API backend URLs (/api/ prefix) ────────────────────────────
COUNTRIES_API_BASE = os.environ.get("COUNTRIES_API_URL", "")
WEATHER_API_BASE   = os.environ.get("WEATHER_API_URL", "")
CURRENCY_API_BASE  = os.environ.get("CURRENCY_API_URL", "")

AZURE_STORAGE_ACCOUNT      = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME", "")
MANAGED_IDENTITY_CLIENT_ID = os.environ.get("MANAGED_IDENTITY_CLIENT_ID", "")
AZURE_STORAGE_QUEUE_NAME   = os.environ.get("AZURE_STORAGE_QUEUE_NAME", "")

REGION_IMAGES = {
    "Africa":    "https://images.unsplash.com/photo-1489392191049-fc10c97e64b6?w=600&q=80",
    "Americas":  "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=600&q=80",
    "Antarctic": "https://images.unsplash.com/photo-1516912481808-3406841bd33c?w=600&q=80",
    "Asia":      "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?w=600&q=80",
    "Europe":    "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=600&q=80",
    "Oceania":   "https://images.unsplash.com/photo-1523482580672-f109ba8cb9be?w=600&q=80",
}


@app.route("/")
def index():
    logger.info("Serving index page")
    return render_template("index.html")


@app.route("/api/regions")
def get_regions():
    logger.info("Fetching regions from countries-api (function)")
    with tracer.start_as_current_span("get_regions") as span:
        try:
            url = f"{COUNTRIES_API_BASE}/api/regions"
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.json()
            regions = data.get("regions", [])
            span.set_attribute("regions.count", len(regions))
            logger.info(f"Successfully fetched {len(regions)} regions")
            return jsonify([
                {"name": r, "image": REGION_IMAGES.get(r, "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=600&q=80")}
                for r in regions
            ])
        except requests.exceptions.RequestException as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Error fetching regions: {e}")
            return jsonify({"error": str(e)}), 500


@app.route("/api/countries/<region>")
def get_countries_by_region(region):
    logger.info(f"Fetching countries for region: {region}")
    with tracer.start_as_current_span("get_countries_by_region") as span:
        span.set_attribute("countries.region", region)
        try:
            url = f"{COUNTRIES_API_BASE}/api/countries/region/{region}"
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.json()
            countries = data.get("countries", [])
            span.set_attribute("countries.count", len(countries))
            logger.info(f"Successfully fetched {len(countries)} countries for region '{region}'")
            return jsonify(countries)
        except requests.exceptions.RequestException as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Error fetching countries for region '{region}': {e}")
            return jsonify({"error": str(e)}), 500


@app.route("/api/country-name/<name>")
def get_country_by_name(name):
    logger.info(f"Fetching country detail for: {name}")
    with tracer.start_as_current_span("get_country_by_name") as span:
        span.set_attribute("country.name", name)
        try:
            url = f"{COUNTRIES_API_BASE}/api/countries/{name}"
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            return jsonify(response.json())
        except requests.exceptions.RequestException as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Error fetching country '{name}': {e}")
            return jsonify({"error": str(e)}), 500


@app.route("/api/country-detail")
def get_country_detail():
    latitude      = request.args.get("latitude")
    longitude     = request.args.get("longitude")
    currency_code = request.args.get("currency")
    logger.info(f"Fetching country detail — lat={latitude}, lon={longitude}, currency={currency_code}")

    result = {}
    with tracer.start_as_current_span("get_country_detail") as span:
        span.set_attribute("country.latitude",  latitude or "")
        span.set_attribute("country.longitude", longitude or "")
        span.set_attribute("country.currency",  currency_code or "")

        if latitude and longitude:
            try:
                w = requests.get(f"{WEATHER_API_BASE}/api/weather", params={"latitude": latitude, "longitude": longitude}, timeout=60)
                w.raise_for_status()
                result["weather"] = w.json()
                logger.info(f"Weather fetched successfully for lat={latitude}, lon={longitude}")
            except Exception as e:
                logger.warning(f"Failed to fetch weather: {e}")
                span.record_exception(e)
                result["weather"] = {"error": str(e)}

        if currency_code:
            try:
                c = requests.get(f"{CURRENCY_API_BASE}/api/convert", params={"currency": currency_code, "amount": 1}, timeout=60)
                c.raise_for_status()
                result["exchange"] = c.json()
                logger.info(f"Exchange rate fetched successfully for currency={currency_code}")
            except Exception as e:
                logger.warning(f"Failed to fetch exchange rate: {e}")
                span.record_exception(e)
                result["exchange"] = {"error": str(e)}

        return jsonify(result)


@app.route("/api/book", methods=["POST"])
def book_holiday():
    logger.info("Received holiday booking request")
    with tracer.start_as_current_span("book_holiday") as span:
        if not AZURE_STORAGE_ACCOUNT:
            return jsonify({"error": "AZURE_STORAGE_ACCOUNT_NAME is not configured."}), 500

        body = request.get_json(force=True)
        if not body:
            return jsonify({"error": "Request body is required."}), 400

        booking = {
            "booking_id": str(uuid.uuid4()),
            "booked_at": datetime.now(timezone.utc).isoformat(),
            **body
        }

        span.set_attribute("booking.id",      booking["booking_id"])
        span.set_attribute("booking.country", body.get("country", ""))
        span.set_attribute("booking.days",    body.get("days", 0))

        try:
            credential   = ManagedIdentityCredential(client_id=MANAGED_IDENTITY_CLIENT_ID) if MANAGED_IDENTITY_CLIENT_ID else ManagedIdentityCredential()
            queue_url    = f"https://{AZURE_STORAGE_ACCOUNT}.queue.core.windows.net/{AZURE_STORAGE_QUEUE_NAME}"
            queue_client = QueueClient.from_queue_url(queue_url, credential=credential)
            message      = base64.b64encode(json.dumps(booking).encode()).decode()
            queue_client.send_message(message)
            logger.info(f"Booking queued successfully: {booking['booking_id']}")
            return jsonify({"success": True, "booking_id": booking["booking_id"]}), 201
        except Exception as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Failed to queue booking: {e}")
            return jsonify({"error": "Failed to store booking.", "details": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
