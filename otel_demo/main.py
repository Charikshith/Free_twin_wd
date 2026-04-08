"""
Sample instrumented application demonstrating OpenTelemetry with OTLP.

Requires:
  - OTLP collector running on localhost:4317
  - Run: python main.py
"""

import time
import logging
from otel_setup import init_otel, get_tracer, get_meter

# Initialize OpenTelemetry
trace_provider, metrics_provider = init_otel("sample-app", otlp_endpoint="localhost:4317")
tracer = get_tracer(__name__)
meter = get_meter(__name__)
logger = logging.getLogger(__name__)

# Create metrics
request_counter = meter.create_counter(
    "requests.total",
    description="Total number of requests",
    unit="1",
)

response_time_histogram = meter.create_histogram(
    "response.time",
    description="Response time in seconds",
    unit="s",
)


def simulate_request(endpoint: str, delay: float):
    """Simulate processing a request with tracing and metrics."""
    with tracer.start_as_current_span(f"process-{endpoint}") as span:
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.url", f"/api{endpoint}")
        
        logger.info(f"Processing request to {endpoint}")
        
        # Simulate work
        time.sleep(delay)
        
        # Record metrics
        request_counter.add(1, {"endpoint": endpoint})
        response_time_histogram.record(delay, {"endpoint": endpoint})
        
        logger.info(f"Request completed for {endpoint}")
        
        return {"status": "success", "endpoint": endpoint}


def calculate_fibonacci(n: int) -> int:
    """Calculate Fibonacci with tracing."""
    with tracer.start_as_current_span("fibonacci") as span:
        span.set_attribute("number", n)
        
        if n <= 1:
            return n
        
        logger.debug(f"Calculating fibonacci({n})")
        result = calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2)
        
        return result


def main():
    """Main execution."""
    print("\n=== OpenTelemetry OTLP Sample Application ===\n")
    
    # Test 1: Simple traced request
    logger.info("Starting sample application")
    result = simulate_request("/users", 0.1)
    print(f"[OK] Request result: {result}\n")
    
    # Test 2: Multiple requests
    print("Simulating 3 requests...")
    for i in range(3):
        simulate_request(f"/endpoint-{i}", 0.05 + i * 0.01)
    print("[OK] Requests completed\n")
    
    # Test 3: Nested spans (fibonacci)
    print("Calculating fibonacci(5)...")
    fib_result = calculate_fibonacci(5)
    print(f"[OK] fibonacci(5) = {fib_result}\n")
    
    print("=== Traces and metrics exported to OTLP collector ===\n")
    print("Verify in OTLP backend:")
    print("  - Service: sample-app")
    print("  - Spans: process-/users, fibonacci, etc.")
    print("  - Metrics: requests.total, response.time")
    print("  - Logs: Structured logs with trace context")


if __name__ == "__main__":
    main()
