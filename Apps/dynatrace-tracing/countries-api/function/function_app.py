import azure.functions as func
import logging
import requests
import json
import os
import socket
import time
from urllib.parse import urlparse
import pycountry
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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

    # Set up OTel logger and tracer providers
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

def get_alpha2_language_code(alpha_3: str) -> str:
    lang = pycountry.languages.get(alpha_3=alpha_3)
    return lang.alpha_2 if lang and hasattr(lang, 'alpha_2') else alpha_3[:2]

def restcountries_get(url: str, timeout: int = 10) -> requests.Response:
    """GET request to restcountries.com with configurable timeout and retries."""
    logger.info(f"Calling Rest Countries API: {url}")
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    response = session.get(url, timeout=timeout)
    logger.debug(f"Rest Countries API response status: {response.status_code} for {url}")
    return response


@app.route(route="countries", methods=["GET"])
def get_all_countries(req: func.HttpRequest) -> func.HttpResponse:
    logger.info('Fetching all countries.')

    with tracer.start_as_current_span("get_all_countries") as span:
        try:
            url = "https://restcountries.com/v3.1/all?fields=name"
            logger.info(f"Requesting all countries from restcountries.com: {url}")
            response = requests.get(url, timeout=60)
            logger.debug(f"Received response status {response.status_code} from restcountries.com for all countries")
            response.raise_for_status()
            countries = response.json()
            country_names = sorted([c.get("name", {}).get("common", "Unknown") for c in countries])
            span.set_attribute("countries.count", len(country_names))
            logger.info(f"Successfully fetched {len(country_names)} countries")
            return func.HttpResponse(
                json.dumps({"count": len(country_names), "countries": country_names}, indent=2),
                status_code=200,
                mimetype="application/json"
            )
        except requests.exceptions.RequestException as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Error fetching countries: {e}")
            return func.HttpResponse(
                json.dumps({"error": "Failed to fetch countries from restcountries.com", "details": str(e)}),
                status_code=500,
                mimetype="application/json"
            )


@app.route(route="countries/region/{region}", methods=["GET"])
def get_countries_by_region(req: func.HttpRequest) -> func.HttpResponse:
    logger.info('Fetching countries by region.')

    region = req.route_params.get("region")

    with tracer.start_as_current_span("get_countries_by_region") as span:
        span.set_attribute("countries.region", region)
        try:
            url = f"https://restcountries.com/v3.1/region/{region}?fields=name,capital,flags,subregion,latlng"
            logger.info(f"Requesting countries for region '{region}' from restcountries.com: {url}")
            response = restcountries_get(url, timeout=60)
            logger.debug(f"Received response status {response.status_code} from restcountries.com for region {region}")
            response.raise_for_status()
            data = response.json()

            country_list = [
                {
                    "name": c.get("name", {}).get("common", "Unknown"),
                    "capital": c.get("capital", ["N/A"])[0] if c.get("capital") else "N/A",
                    "flag": c.get("flags", {}).get("png"),
                    "subregion": c.get("subregion", "")
                }
                for c in sorted(data, key=lambda x: x.get("name", {}).get("common", ""))
            ]

            span.set_attribute("countries.count", len(country_list))
            logger.info(f"Successfully fetched {len(country_list)} countries for region '{region}'")
            return func.HttpResponse(
                json.dumps({"count": len(country_list), "countries": country_list}, indent=2),
                status_code=200,
                mimetype="application/json"
            )
        except requests.exceptions.RequestException as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Error fetching countries for region '{region}': {e}")
            return func.HttpResponse(
                json.dumps({"error": f"Failed to fetch countries for region '{region}'", "details": str(e)}),
                status_code=500,
                mimetype="application/json"
            )


@app.route(route="regions", methods=["GET"])
def get_all_regions(req: func.HttpRequest) -> func.HttpResponse:
    logger.info('Fetching all regions.')

    with tracer.start_as_current_span("get_all_regions") as span:
        try:
            url = "https://restcountries.com/v3.1/all?fields=region"
            logger.info(f"Requesting all regions from restcountries.com: {url}")
            response = restcountries_get(url, timeout=60)
            logger.debug(f"Received response status {response.status_code} from restcountries.com for regions")
            response.raise_for_status()
            data = response.json()
            regions = sorted(set(c.get("region") for c in data if c.get("region")))
            span.set_attribute("regions.count", len(regions))
            logger.info(f"Successfully fetched {len(regions)} regions")
            return func.HttpResponse(
                json.dumps({"count": len(regions), "regions": regions}, indent=2),
                status_code=200,
                mimetype="application/json"
            )
        except requests.exceptions.RequestException as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Error fetching regions: {e}")
            return func.HttpResponse(
                json.dumps({"error": "Failed to fetch regions", "details": str(e)}),
                status_code=500,
                mimetype="application/json"
            )


@app.route(route="countries/{name}", methods=["GET"])
def get_country_by_name(req: func.HttpRequest) -> func.HttpResponse:
    logger.info('Fetching country by name.')

    name = req.route_params.get("name")

    with tracer.start_as_current_span("get_country_by_name") as span:
        span.set_attribute("country.name", name)
        try:
            url = f"https://restcountries.com/v3.1/name/{name}?fields=name,capital,currencies,languages,latlng,flags,region,subregion"
            logger.info(f"Requesting details for country '{name}' from restcountries.com: {url}")
            response = requests.get(url, timeout=60)
            logger.debug(f"Received response status {response.status_code} from restcountries.com for country '{name}'")
            response.raise_for_status()
            countries = response.json()

            country_list = [
                {
                    "name": c.get("name", {}).get("common", "Unknown"),
                    "capital": c.get("capital", ["N/A"])[0] if c.get("capital") else "N/A",
                    "currencies": [{"code": k, "name": v.get("name")} for k, v in c.get("currencies", {}).items()],
                    "languages": [{"code": get_alpha2_language_code(k), "name": v} for k, v in c.get("languages", {}).items()],
                    "latitude": c.get("latlng", [None, None])[0],
                    "longitude": c.get("latlng", [None, None])[1],
                    "region": c.get("region"),
                    "subregion": c.get("subregion"),
                    "flag": {
                        "png": c.get("flags", {}).get("png"),
                        "svg": c.get("flags", {}).get("svg"),
                        "alt": c.get("flags", {}).get("alt")
                    }
                }
                for c in countries
            ]

            span.set_attribute("country.results", len(country_list))
            logger.info(f"Successfully fetched {len(country_list)} country results for '{name}'")
            return func.HttpResponse(
                json.dumps({"count": len(country_list), "countries": country_list}, indent=2),
                status_code=200,
                mimetype="application/json"
            )
        except requests.exceptions.RequestException as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Error fetching country '{name}': {e}")
            return func.HttpResponse(
                json.dumps({"error": f"Failed to fetch country '{name}'", "details": str(e)}),
                status_code=500,
                mimetype="application/json"
            )

