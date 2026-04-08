"""
OpenTelemetry setup with OTLP exporters for traces, metrics, and logging.
"""

import logging
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.logging import LoggingInstrumentor

try:
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False


def init_otel(
    service_name: str,
    otlp_endpoint: str = "localhost:4317",
    enable_requests_instrumentation: bool = True,
    enable_flask_instrumentation: bool = False,
):
    """
    Initialize OpenTelemetry with OTLP exporters for traces and metrics.
    
    Args:
        service_name: Name of the service for resource identification
        otlp_endpoint: OTLP collector endpoint (default: localhost:4317)
        enable_requests_instrumentation: Enable HTTP requests instrumentation
        enable_flask_instrumentation: Enable Flask instrumentation (if using Flask)
    """
    
    # Resource: identifies the service
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
    })

    # ===== Traces Setup =====
    trace_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(trace_provider)
    
    # ===== Metrics Setup =====
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
    )
    metrics_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(metrics_provider)
    
    # ===== Logging Setup =====
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Instrument logging to emit trace context
    LoggingInstrumentor().instrument(set_logging_format=True)
    
    # ===== Instrumentation =====
    if enable_requests_instrumentation:
        RequestsInstrumentor().instrument()
    
    if enable_flask_instrumentation:
        if HAS_FLASK:
            FlaskInstrumentor().instrument()
        else:
            print("[OpenTelemetry] Flask instrumentation requested but Flask not installed")
    
    print(f"[OpenTelemetry] Initialized {service_name}")
    print(f"[OpenTelemetry] OTLP Exporter: {otlp_endpoint}")
    
    return trace_provider, metrics_provider


def get_tracer(name: str):
    """Get a tracer by name."""
    return trace.get_tracer(name)


def get_meter(name: str):
    """Get a meter by name."""
    return metrics.get_meter(name)
