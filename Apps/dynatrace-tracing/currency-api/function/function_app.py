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

@app.route(route="convert", methods=["GET"])
def convert_gbp(req: func.HttpRequest) -> func.HttpResponse:
    logger.info('Converting GBP to target currency.')

    target = req.params.get("currency")
    amount_str = req.params.get("amount", "1")

    if not target:
        return func.HttpResponse(
            json.dumps({"error": "Please provide a 'currency' query parameter (e.g. ?currency=USD)."}),
            status_code=400,
            mimetype="application/json"
        )

    try:
        amount = float(amount_str)
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "'amount' must be a valid number."}),
            status_code=400,
            mimetype="application/json"
        )

    with tracer.start_as_current_span("convert_gbp") as span:
        span.set_attribute("currency.target", target.upper())
        span.set_attribute("currency.amount", amount)

        try:
            url = "https://open.er-api.com/v6/latest/GBP"
            logger.info(f"Requesting exchange rates from open.er-api.com: {url}")
            response = requests.get(url, timeout=60)
            logger.debug(f"Received exchange rate response status {response.status_code} from {url}")
            response.raise_for_status()
            data = response.json()

            rates = data.get("rates", {})
            target_upper = target.upper()

            if target_upper not in rates:
                logger.warning(f"Unsupported currency code requested: {target_upper}")
                return func.HttpResponse(
                    json.dumps({"error": f"Currency code '{target_upper}' is not supported."}),
                    status_code=404,
                    mimetype="application/json"
                )

            rate = rates[target_upper]
            converted = round(amount * rate, 2)

            span.set_attribute("currency.rate", rate)
            span.set_attribute("currency.converted", converted)

            logger.info(f"Converted {amount} GBP to {converted} {target_upper} at rate {rate}")

            return func.HttpResponse(
                json.dumps({
                    "from": "GBP",
                    "to": target_upper,
                    "amount": amount,
                    "rate": rate,
                    "converted": converted,
                    "last_updated": data.get("time_last_update_utc")
                }, indent=2),
                status_code=200,
                mimetype="application/json"
            )
        except requests.exceptions.RequestException as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Error fetching exchange rates: {e}")
            return func.HttpResponse(
                json.dumps({"error": "Failed to fetch exchange rates from open.er-api.com", "details": str(e)}),
                status_code=500,
                mimetype="application/json"
            )
