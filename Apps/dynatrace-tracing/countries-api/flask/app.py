import logging
import requests
import os
import pycountry
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import Flask, jsonify
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
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RESTCOUNTRIES_BASE_URL = os.getenv("RESTCOUNTRIES_BASE_URL", "https://api.restcountries.com/countries/v5").rstrip("/")
RESTCOUNTRIES_API_KEY = os.getenv("RESTCOUNTRIES_API_KEY", "").strip() or "rc_live_demo"

if RESTCOUNTRIES_API_KEY == "rc_live_demo":
    logger.warning("RESTCOUNTRIES_API_KEY is not set; falling back to demo key 'rc_live_demo'.")


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

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_alpha2_language_code(alpha_3: str) -> str:
    lang = pycountry.languages.get(alpha_3=alpha_3)
    return lang.alpha_2 if lang and hasattr(lang, "alpha_2") else alpha_3[:2]


def restcountries_get(path: str = "", timeout: int = 10, params: dict | None = None) -> requests.Response:
    """GET request to restcountries.com v5 with retry and authentication."""
    path = path.lstrip("/")
    url = f"{RESTCOUNTRIES_BASE_URL}/{path}" if path else RESTCOUNTRIES_BASE_URL
    logger.info(f"Calling Rest Countries API: {url}")
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    response = session.get(
        url,
        timeout=timeout,
        params=params,
        headers={"Authorization": f"Bearer {RESTCOUNTRIES_API_KEY}"},
    )
    logger.debug(f"Rest Countries API response status: {response.status_code} for {url}")
    return response


def extract_v5_objects(payload):
    if isinstance(payload, dict):
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            message = errors[0].get("message") if isinstance(errors[0], dict) else str(errors[0])
            raise ValueError(message or "Unknown Rest Countries API error")

        objects = payload.get("data", {}).get("objects")
        if isinstance(objects, list):
            return objects

    if isinstance(payload, list):
        return payload

    raise ValueError("Unexpected response payload from Rest Countries API")


def restcountries_get_objects(path: str = "", timeout: int = 60, params: dict | None = None, fetch_all: bool = False):
    request_params = dict(params or {})

    if not fetch_all:
        response = restcountries_get(path=path, timeout=timeout, params=request_params)
        response.raise_for_status()
        return extract_v5_objects(response.json())

    all_objects = []
    limit = int(request_params.get("limit", 100))
    offset = int(request_params.get("offset", 0))

    while True:
        request_params["limit"] = limit
        request_params["offset"] = offset
        response = restcountries_get(path=path, timeout=timeout, params=request_params)
        response.raise_for_status()
        payload = response.json()
        objects = extract_v5_objects(payload)
        all_objects.extend(objects)

        meta = payload.get("data", {}).get("meta", {}) if isinstance(payload, dict) else {}
        has_more = bool(meta.get("more")) if isinstance(meta, dict) else False
        if not has_more or not objects:
            break

        offset += limit

    return all_objects


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/countries", methods=["GET"])
def get_all_countries():
    logger.info("Fetching all countries.")
    with tracer.start_as_current_span("get_all_countries") as span:
        try:
            countries = restcountries_get_objects(
                params={
                    "response_fields": "names.common",
                    "limit": 100,
                },
                fetch_all=True,
            )
            country_names = sorted([c.get("names", {}).get("common", "Unknown") for c in countries])
            span.set_attribute("countries.count", len(country_names))
            logger.info(f"Successfully fetched {len(country_names)} countries")
            return jsonify({"count": len(country_names), "countries": country_names}), 200
        except (requests.exceptions.RequestException, ValueError) as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Error fetching countries: {e}")
            return jsonify({"error": "Failed to fetch countries from restcountries.com", "details": str(e)}), 500


@app.route("/regions", methods=["GET"])
def get_all_regions():
    logger.info("Fetching all regions.")
    with tracer.start_as_current_span("get_all_regions") as span:
        try:
            data = restcountries_get_objects(
                params={
                    "response_fields": "region",
                    "limit": 100,
                },
                fetch_all=True,
            )
            regions = sorted(set(c.get("region") for c in data if c.get("region")))
            span.set_attribute("regions.count", len(regions))
            logger.info(f"Successfully fetched {len(regions)} regions")
            return jsonify({"count": len(regions), "regions": regions}), 200
        except (requests.exceptions.RequestException, ValueError) as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Error fetching regions: {e}")
            return jsonify({"error": "Failed to fetch regions", "details": str(e)}), 500


@app.route("/countries/region/<region>", methods=["GET"])
def get_countries_by_region(region):
    logger.info(f"Fetching countries for region '{region}'.")
    with tracer.start_as_current_span("get_countries_by_region") as span:
        span.set_attribute("countries.region", region)
        try:
            data = restcountries_get_objects(
                path=f"region/{region}",
                timeout=60,
                params={
                    "response_fields": "names.common,capitals,flag.url_png,subregion,coordinates.lat,coordinates.lng",
                    "limit": 100,
                },
                fetch_all=True,
            )
            country_list = [
                {
                    "name": c.get("names", {}).get("common", "Unknown"),
                    "capital": c.get("capitals", [{}])[0].get("name", "N/A") if c.get("capitals") else "N/A",
                    "flag": c.get("flag", {}).get("url_png"),
                    "subregion": c.get("subregion", ""),
                }
                for c in sorted(data, key=lambda x: x.get("names", {}).get("common", ""))
            ]
            span.set_attribute("countries.count", len(country_list))
            logger.info(f"Successfully fetched {len(country_list)} countries for region '{region}'")
            return jsonify({"count": len(country_list), "countries": country_list}), 200
        except (requests.exceptions.RequestException, ValueError) as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Error fetching countries for region '{region}': {e}")
            return jsonify({"error": f"Failed to fetch countries for region '{region}'", "details": str(e)}), 500


@app.route("/countries/<name>", methods=["GET"])
def get_country_by_name(name):
    logger.info(f"Fetching country by name '{name}'.")
    with tracer.start_as_current_span("get_country_by_name") as span:
        span.set_attribute("country.name", name)
        try:
            countries = restcountries_get_objects(
                path=f"names.common/{name}",
                timeout=60,
                params={
                    "response_fields": "names.common,capitals,currencies,languages,coordinates.lat,coordinates.lng,flag.url_png,flag.url_svg,flag.description,region,subregion",
                    "limit": 100,
                },
                fetch_all=True,
            )

            def map_languages(country):
                raw_languages = country.get("languages") or []
                if isinstance(raw_languages, dict):
                    return [
                        {"code": get_alpha2_language_code(k), "name": v}
                        for k, v in raw_languages.items()
                    ]

                languages = []
                if isinstance(raw_languages, list):
                    for lang in raw_languages:
                        if not isinstance(lang, dict):
                            continue
                        alpha_3 = lang.get("iso_639_3") or lang.get("iso639_3") or ""
                        alpha_2 = lang.get("iso_639_1") or lang.get("iso639_1")
                        code = alpha_2 or (get_alpha2_language_code(alpha_3) if alpha_3 else None)
                        name_value = lang.get("name") or lang.get("english") or lang.get("native")
                        if code and name_value:
                            languages.append({"code": code, "name": name_value})
                return languages

            def map_currencies(country):
                raw_currencies = country.get("currencies") or {}
                if isinstance(raw_currencies, dict):
                    return [
                        {"code": k, "name": v.get("name") if isinstance(v, dict) else str(v)}
                        for k, v in raw_currencies.items()
                    ]

                currencies = []
                if isinstance(raw_currencies, list):
                    for cur in raw_currencies:
                        if not isinstance(cur, dict):
                            continue
                        code = cur.get("code") or cur.get("iso_4217")
                        name_value = cur.get("name")
                        if code:
                            currencies.append({"code": code, "name": name_value})
                return currencies

            country_list = [
                {
                    "name": c.get("names", {}).get("common", "Unknown"),
                    "capital": c.get("capitals", [{}])[0].get("name", "N/A") if c.get("capitals") else "N/A",
                    "currencies": map_currencies(c),
                    "languages": map_languages(c),
                    "latitude": c.get("coordinates", {}).get("lat"),
                    "longitude": c.get("coordinates", {}).get("lng"),
                    "region": c.get("region"),
                    "subregion": c.get("subregion"),
                    "flag": {
                        "png": c.get("flag", {}).get("url_png"),
                        "svg": c.get("flag", {}).get("url_svg"),
                        "alt": c.get("flag", {}).get("description"),
                    },
                }
                for c in countries
            ]
            span.set_attribute("country.results", len(country_list))
            logger.info(f"Successfully fetched {len(country_list)} results for '{name}'")
            return jsonify({"count": len(country_list), "countries": country_list}), 200
        except (requests.exceptions.RequestException, ValueError) as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Error fetching country '{name}': {e}")
            return jsonify({"error": f"Failed to fetch country '{name}'", "details": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
