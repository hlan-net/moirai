import logging
import os
import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
except ModuleNotFoundError:
    FastAPIInstrumentor = None


def _span_exporter():
    """The span exporter chosen by OTEL_TRACES_EXPORTER: none (default), console or otlp.

    Spans used to go to stdout unconditionally, one multi-line JSON object per
    span including every health probe, which buried the application log (#369).
    ``otlp`` sends them over OTLP/HTTP; the exporter reads
    OTEL_EXPORTER_OTLP_ENDPOINT (default http://localhost:4318) itself.
    """
    choice = os.environ.get("OTEL_TRACES_EXPORTER", "none").strip().lower()
    if choice in ("", "none"):
        return None
    if choice == "console":
        return ConsoleSpanExporter()
    if choice == "otlp":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        return OTLPSpanExporter()
    logging.warning(
        "Unknown OTEL_TRACES_EXPORTER %r; spans are not exported. "
        "Use none, console or otlp.",
        choice,
    )
    return None


def configure_telemetry(app=None, service_name="moirai"):
    """
    Configures OpenTelemetry and Structlog.
    If 'app' is provided, it instruments the specific framework (Flask or FastAPI/Starlette).
    """

    # 1. Configure OpenTelemetry
    provider = TracerProvider()
    exporter = _span_exporter()
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Instrument requests library (common to both)
    RequestsInstrumentor().instrument()

    if app:
        # Check if it's Flask
        if hasattr(app, "extensions") or hasattr(app, "url_map"):
            FlaskInstrumentor().instrument_app(app)
        # Check if it's FastAPI/Starlette (ASGI)
        elif hasattr(app, "routes"):
            if FastAPIInstrumentor is None:
                logging.warning(
                    "FastAPI instrumentation unavailable; install "
                    "opentelemetry-instrumentation-fastapi to enable it."
                )
            else:
                FastAPIInstrumentor.instrument_app(app)

    # 2. Configure Structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return trace.get_tracer(service_name)
