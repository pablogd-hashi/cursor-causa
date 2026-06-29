"""OpenTelemetry initialisation for the payments service.

Adapted from the reference repo's ``agents/shared/telemetry.py``. The shape is the
same — one idempotent ``init_telemetry()`` that wires a TracerProvider,
MeterProvider and LoggerProvider to the OTel Collector over OTLP/gRPC — but the
smolagents instrumentation is dropped (this is a plain FastAPI service) and two
metric Views are added so the latency histograms have second-scale buckets.

Why the Views matter (non-obvious): the OTel SDK's *default* histogram bucket
boundaries are tuned for millisecond-ish values. Our durations are recorded in
seconds (0.05s … 9s), so with the defaults almost everything would land in the
first bucket and ``histogram_quantile`` would return nonsense. The explicit
boundaries below give the p99 query something to interpolate across.
"""

from __future__ import annotations

import logging
import os

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_initialised = False

# Second-scale bucket boundaries for the request/wait latency histograms.
SECONDS_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]


def init_telemetry(service_name: str, service_version: str = "0.1.0") -> None:
    """Configure OTel exporters for this process. Idempotent."""
    global _initialised
    if _initialised:
        return

    endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"
    )

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
            "deployment.environment": os.environ.get("DEPLOY_ENV", "local"),
        }
    )

    # --- Traces -----------------------------------------------------------
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(tracer_provider)

    # --- Metrics ----------------------------------------------------------
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=True),
        export_interval_millis=10_000,
    )
    views = [
        View(
            instrument_name="payments_request_duration_seconds",
            aggregation=ExplicitBucketHistogramAggregation(SECONDS_BUCKETS),
        ),
        View(
            instrument_name="payments_pool_wait_seconds",
            aggregation=ExplicitBucketHistogramAggregation(SECONDS_BUCKETS),
        ),
    ]
    meter_provider = MeterProvider(
        resource=resource, metric_readers=[metric_reader], views=views
    )
    metrics.set_meter_provider(meter_provider)

    # --- Logs -------------------------------------------------------------
    # Forward application logs to the Collector so they reach Loki. The handler
    # injects trace context, which Grafana's derived-fields config turns into a
    # clickable link from a log line to its Jaeger trace.
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint, insecure=True))
    )
    set_logger_provider(logger_provider)
    otel_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    logging.getLogger("payments").addHandler(otel_handler)
    logging.getLogger("payments").setLevel(logging.INFO)

    logging.getLogger(__name__).info("telemetry initialised: %s", service_name)
    _initialised = True


def get_tracer(name: str | None = None):
    """Convenience accessor for the global tracer."""
    return trace.get_tracer(name or "payments")


def get_meter(name: str | None = None):
    """Convenience accessor for the global meter."""
    return metrics.get_meter(name or "payments")
