"""
Tests for OpenTelemetry OTLP setup and initialization.
"""

import pytest
import logging
from unittest.mock import patch, MagicMock
from otel_setup import init_otel, get_tracer, get_meter


class TestOtelInitialization:
    """Test OTLP initialization with traces, metrics, and logging."""
    
    def test_init_otel_returns_providers(self):
        """Test that init_otel returns trace and metrics providers."""
        trace_provider, metrics_provider = init_otel("test-service")
        
        assert trace_provider is not None
        assert metrics_provider is not None
    
    def test_tracer_can_be_retrieved_after_init(self):
        """Test that a tracer can be retrieved after initialization."""
        init_otel("test-service")
        tracer = get_tracer("test-tracer")
        
        assert tracer is not None
    
    def test_meter_can_be_retrieved_after_init(self):
        """Test that a meter can be retrieved after initialization."""
        init_otel("test-service")
        meter = get_meter("test-meter")
        
        assert meter is not None
    
    def test_tracer_creates_span(self):
        """Test that tracer can create a span."""
        init_otel("test-service")
        tracer = get_tracer("test-tracer")
        
        with tracer.start_as_current_span("test-span") as span:
            assert span is not None
            assert span.name == "test-span"
    
    def test_custom_endpoint_configuration(self):
        """Test that custom OTLP endpoint is configured."""
        custom_endpoint = "custom-host:4317"
        trace_provider, metrics_provider = init_otel(
            "test-service",
            otlp_endpoint=custom_endpoint
        )
        
        assert trace_provider is not None
        assert metrics_provider is not None
    
    def test_logging_is_configured(self):
        """Test that logging is configured after init_otel."""
        init_otel("test-service")
        logger = logging.getLogger("test-logger")
        
        # Should be able to log without errors
        logger.info("Test message")
    
    def test_service_name_in_resource(self):
        """Test that service name is included in resource."""
        service_name = "my-service"
        trace_provider, _ = init_otel(service_name)
        
        resource = trace_provider.resource
        assert resource.attributes["service.name"] == service_name


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
