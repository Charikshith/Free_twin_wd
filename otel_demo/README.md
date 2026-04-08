# otel_demo

OpenTelemetry (OTLP) implementation with distributed tracing, metrics, and logging in Python.

## Features
- OpenTelemetry SDK setup with OTLP exporters
- Distributed tracing with spans and trace context
- Metrics collection (counters, histograms)
- Structured logging with trace correlation
- HTTP and Flask instrumentation support
- Sample instrumented application

## Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
uv venv

# Activate
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
uv pip install -r requirements.txt
```

### 2. Start OTLP Collector

You need an OpenTelemetry Collector running on `localhost:4317`. Options:

**Option A: Using Docker**
```bash
docker run -d \
  -p 4317:4317 \
  otel/opentelemetry-collector:latest
```

**Option B: Using Jaeger (includes OTLP support)**
```bash
docker run -d \
  -p 4317:4317 \
  -p 6831:6831/udp \
  -p 16686:16686 \
  jaegertracing/all-in-one:latest
```
Then view traces at: http://localhost:16686

### 3. Run Sample Application

```bash
python main.py
```

Expected output:
```
=== OpenTelemetry OTLP Sample Application ===

✓ Request result: {'status': 'success', 'endpoint': '/users'}

Simulating 3 requests...
✓ Requests completed

Calculating fibonacci(5)...
✓ fibonacci(5) = 5

=== Traces and metrics exported to OTLP collector ===
```

### 4. Verify in Backend

- **Jaeger**: Visit http://localhost:16686
- **Elasticsearch**: Query via Kibana
- **Prometheus**: Scrape metrics from OTLP exporter

## Configuration

### Custom OTLP Endpoint

In `main.py`:
```python
init_otel("app-name", otlp_endpoint="your-host:4317")
```

### Enable Instrumentation

```python
# HTTP requests
init_otel("app-name", enable_requests_instrumentation=True)

# Flask apps
init_otel("app-name", enable_flask_instrumentation=True)
```

## Key Components

| File | Purpose |
|------|---------|
| `otel_setup.py` | Core OTLP configuration and initialization |
| `main.py` | Sample instrumented application |
| `test_otel_setup.py` | Unit tests for OTLP setup |
| `requirements.txt` | Python dependencies |

## Testing

```bash
# Run tests
pytest test_otel_setup.py -v

# Output: 7 passed ✓
```

## Architecture

```
┌─────────────────────────┐
│   Application Code      │
│  (traces, metrics, logs)│
└────────┬────────────────┘
         │ OTLP gRPC (4317)
         ▼
┌─────────────────────────┐
│   OTLP Collector        │
│  (localhost:4317)       │
└────────┬────────────────┘
         │
    ┌────┴────┬──────────┬─────────┐
    ▼         ▼          ▼         ▼
  Jaeger  Zipkin  Prometheus  Elasticsearch
```

## Troubleshooting

### "Connection refused" on localhost:4317
- Start OTLP collector: `docker run -d -p 4317:4317 otel/opentelemetry-collector`

### No traces appearing
- Check collector logs: `docker logs <container-id>`
- Verify app is sending: Add debug prints in `otel_setup.py`

### Metrics not showing
- Ensure metric reader is configured in `otel_setup.py`
- Verify backend supports OTLP metrics format

## Next Steps

1. Integrate with your main application
2. Add custom spans for business logic
3. Create dashboards in your backend (Grafana for Prometheus, Jaeger UI for traces)
4. Set up alerting based on metrics

## Resources

- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)
- [OTLP Protocol](https://opentelemetry.io/docs/specs/otel/protocol/)
- [Jaeger Documentation](https://www.jaegertracing.io/)

