```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                    OPENTELEMETRY (OTLP) ARCHITECTURE DIAGRAM                     ║
╚══════════════════════════════════════════════════════════════════════════════════╝


═══════════════════════════════════════════════════════════════════════════════════
                              YOUR APPLICATION CODE
═══════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              main.py (Your App)                                  │
│                                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  def simulate_request(endpoint, delay):                                  │   │
│  │    ├─ Creates SPAN: "process-{endpoint}"                                │   │
│  │    ├─ Sets attributes: http.method, http.url                             │   │
│  │    ├─ Does work (sleep)                                                  │   │
│  │    ├─ Records METRICS: request_counter++, response_time                 │   │
│  │    └─ Logs: logger.info() → STRUCTURED LOG with trace context          │   │
│  │                                                                           │   │
│  │  def calculate_fibonacci(n):                                             │   │
│  │    ├─ Creates NESTED SPANS (recursive calls)                             │   │
│  │    ├─ Sets attribute: number = n                                         │   │
│  │    └─ Automatically links parent/child spans via trace_id                │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│  Emits 3 types of telemetry:                                                     │
│    1. TRACES  → Spans with parent/child relationships                            │
│    2. METRICS → Counters, histograms, gauges                                     │
│    3. LOGS    → Structured logs with trace_id & span_id embedded                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ (Uses)
                                    ▼


═══════════════════════════════════════════════════════════════════════════════════
                          OPENTELEMETRY SDK LAYER
═══════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────┐
│                        otel_setup.py (Configuration)                             │
│                                                                                   │
│  ┌─ Tracer Provider ────────────────────────────────────────────────────────┐   │
│  │  • Manages all tracers for the application                              │   │
│  │  • Stores resource info: service.name, service.version                  │   │
│  │  • Attaches BatchSpanProcessor → OTLP Exporter                          │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│  ┌─ Meter Provider ─────────────────────────────────────────────────────────┐   │
│  │  • Manages all meters (for metrics collection)                          │   │
│  │  • Stores resource info: service.name, service.version                  │   │
│  │  • Attaches PeriodicExportingMetricReader → OTLP Exporter               │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│  ┌─ Logger Configuration ────────────────────────────────────────────────────┐   │
│  │  • Sets up Python logging (basicConfig)                                 │   │
│  │  • Instruments logging with LoggingInstrumentor                         │   │
│  │  • Embeds trace_id & span_id in log records                             │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│  ┌─ Instrumentation (Optional) ──────────────────────────────────────────────┐   │
│  │  • RequestsInstrumentor: Auto-trace HTTP requests                       │   │
│  │  • FlaskInstrumentor: Auto-trace Flask routes                           │   │
│  │  • (More available: Django, FastAPI, SQLAlchemy, gRPC, etc.)            │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            TRACES (Spans)     METRICS          LOGS


═══════════════════════════════════════════════════════════════════════════════════
                            EXPORTERS (OTLP Protocol)
═══════════════════════════════════════════════════════════════════════════════════

┌──────────────────────────┐   ┌──────────────────────────┐   ┌──────────────────┐
│  OTLP Span Exporter      │   │ OTLP Metric Exporter     │   │ Logging Handler  │
│  (BatchSpanProcessor)    │   │ (PeriodicExporter)       │   │ (Instrumented)   │
│                          │   │                          │   │                  │
│ • Batches spans          │   │ • Periodically exports   │   │ • Embeds trace   │
│ • Sends via gRPC         │   │   metrics                │   │   context        │
│ • Protocol: OTLP         │   │ • Sends via gRPC         │   │ • Sends to       │
│ • Endpoint: :4317        │   │ • Protocol: OTLP         │   │   configured     │
│ • TLS: insecure (dev)    │   │ • Endpoint: :4317        │   │   handler        │
└──────────────────────────┘   └──────────────────────────┘   └──────────────────┘
         │                              │                           │
         └──────────────────────────────┼───────────────────────────┘
                                        │
                    (All via gRPC OTLP Protocol on port 4317)
                                        │
                                        ▼


═══════════════════════════════════════════════════════════════════════════════════
                        OTLP COLLECTOR (localhost:4317)
═══════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────┐
│                      OpenTelemetry Collector (Docker)                            │
│                                                                                   │
│  ┌─ Receivers ─────────────────────────────────────────────────────────────┐   │
│  │  OTLP gRPC Receiver (port 4317)                                         │   │
│  │  ↓                                                                       │   │
│  │  Receives:                                                              │   │
│  │    • Trace Spans (from app)                                             │   │
│  │    • Metrics (from app)                                                 │   │
│  │    • Logs (optional)                                                    │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                              ┌─────▼─────┐                                       │
│                              │ Processors │                                       │
│                              │ • Batching │                                       │
│                              │ • Sampling │                                       │
│                              │ • Filtering│                                       │
│                              └─────┬─────┘                                       │
│                                    │                                             │
│  ┌─ Exporters ────────────────────┼───────────────────────────────────────┐   │
│  │                                │                                       │   │
│  │  ┌──────────────┐   ┌──────────┴──────┐   ┌──────────────────────┐   │   │
│  │  │ Jaeger       │   │ Prometheus       │   │ Elasticsearch/Kibana │   │   │
│  │  │ Exporter     │   │ Exporter         │   │ Exporter             │   │   │
│  │  │ (Traces)     │   │ (Metrics)        │   │ (Logs + Traces)      │   │   │
│  │  └──────────────┘   └──────────────────┘   └──────────────────────┘   │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
              │                        │                          │
              ▼                        ▼                          ▼


═══════════════════════════════════════════════════════════════════════════════════
                              BACKEND SYSTEMS
═══════════════════════════════════════════════════════════════════════════════════

┌──────────────────────────┐  ┌──────────────────────────┐  ┌─────────────────────┐
│     JAEGER (Traces)      │  │   PROMETHEUS (Metrics)   │  │  ELASTICSEARCH/KIBANA│
│                          │  │                          │  │   (Logs + Traces)   │
│ • Stores trace data      │  │ • Time-series database   │  │                     │
│ • Shows span timeline    │  │ • Pull-based metrics     │  │ • Log aggregation   │
│ • Visualizes spans       │  │ • Grafana dashboards     │  │ • Full-text search  │
│ • Latency analysis       │  │ • Alerts based on        │  │ • Pattern analysis  │
│ • Service dependencies   │  │   thresholds             │  │ • Correlation       │
│                          │  │ • Query language: PromQL │  │                     │
│ UI: localhost:16686      │  │ UI: localhost:9090       │  │ UI: localhost:5601  │
└──────────────────────────┘  └──────────────────────────┘  └─────────────────────┘


═══════════════════════════════════════════════════════════════════════════════════
                              DATA FLOW EXAMPLE
═══════════════════════════════════════════════════════════════════════════════════

User calls: main.py → simulate_request("/users", 0.1)

TIME        COMPONENT            ACTION
────────────────────────────────────────────────────────────────────────────────
T0          main.py              1. Call init_otel("sample-app")
                                    ├─ Creates TracerProvider
                                    ├─ Creates MeterProvider
                                    └─ Configures OTLP exporters

T1          main.py              2. Get tracer = get_tracer(__name__)

T2          main.py              3. Enter span context:
                                    with tracer.start_as_current_span("process-/users"):
                                    ├─ Span ID = 0x1234...
                                    ├─ Trace ID = 0x5678...
                                    └─ Start time: T2

T3          main.py              4. Set span attributes:
                                    span.set_attribute("http.method", "GET")

T4          main.py              5. Emit log:
                                    logger.info("Processing request to /users")
                                    └─ Log record includes:
                                       {trace_id: 0x5678..., span_id: 0x1234...}

T5          main.py              6. Simulate work: time.sleep(0.1)

T6          main.py              7. Record metrics:
                                    request_counter.add(1, {"endpoint": "/users"})
                                    response_time_histogram.record(0.1, ...)

T7          main.py              8. Exit span context
                                    ├─ Span end time: T7
                                    └─ Duration = 0.1s

T8          otel_setup.py         9. BatchSpanProcessor flushes span to exporter:
                                    {
                                      trace_id: 0x5678...,
                                      span_id: 0x1234...,
                                      name: "process-/users",
                                      start_time: T2,
                                      end_time: T7,
                                      attributes: {http.method: "GET", http.url: "..."},
                                      duration: 0.1s
                                    }

T9          otel_setup.py         10. OTLP Exporter sends via gRPC to :4317:
                                     POST localhost:4317/opentelemetry.proto.collector.trace.v1.TraceService/Export

T10         OTLP Collector        11. Receives span
                                    └─ Routes to configured exporters

T11         Jaeger Exporter       12. Stores span in Jaeger backend
                                    └─ Queryable at localhost:16686

T12         Prometheus Exporter   13. Stores metric data
                                    └─ Queryable at localhost:9090

────────────────────────────────────────────────────────────────────────────────
Result: Single request traced end-to-end with timing, metadata, and logs!


═══════════════════════════════════════════════════════════════════════════════════
                              KEY CONCEPTS
═══════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────┐
│ SPAN                                                                              │
│ • A unit of work (e.g., function call, HTTP request, database query)            │
│ • Has: trace_id, span_id, name, start_time, end_time, attributes, events       │
│ • Can have parent span (nested)                                                  │
│ Example: Span for "process-/users" with duration 100ms                          │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│ TRACE                                                                             │
│ • Collection of related spans (connected by trace_id)                           │
│ • Shows full request journey through multiple services                          │
│ • Example trace: User request → Service A → Service B → Database (4 spans)     │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│ METRIC                                                                            │
│ • Quantitative measurement (counter, gauge, histogram)                          │
│ • Counter: incrementing value (e.g., requests_total)                            │
│ • Histogram: distribution (e.g., response_time bucketed: <10ms, <50ms, <100ms)│
│ • Gauge: current value (e.g., memory_usage_bytes)                               │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│ LOG                                                                               │
│ • Structured event message with metadata                                        │
│ • Includes: timestamp, level, message, trace_id, span_id                        │
│ • Correlated with spans for context                                             │
│ Example: INFO: Processing request to /users [trace_id: 0x5678...]               │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│ TRACE CONTEXT (W3C Standard)                                                     │
│ • trace_id: Unique ID for entire request journey                                │
│ • span_id: Unique ID for this span                                              │
│ • parent_span_id: ID of parent span (if nested)                                 │
│ • Passed in HTTP headers: traceparent: "version-trace_id-span_id-flags"         │
│ → Enables distributed tracing across services!                                  │
└─────────────────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════════
                            HOW YOUR CODE USES IT
═══════════════════════════════════════════════════════════════════════════════════

STEP 1: INITIALIZATION (otel_setup.py)
  init_otel("sample-app")
    ↓
  Creates:
    • TracerProvider (provides tracers)
    • MeterProvider (provides meters)
    • OTLP Exporters (sends data to :4317)

STEP 2: INSTRUMENTATION (main.py)
  tracer = get_tracer(__name__)
    ↓
  With tracer, you:
    • Create spans: tracer.start_as_current_span("name")
    • Set attributes: span.set_attribute("key", "value")
    • Record events: span.add_event("event_name")

STEP 3: METRICS (main.py)
  meter = get_meter(__name__)
    ↓
  With meter, you:
    • Create counters: meter.create_counter("name")
    • Create histograms: meter.create_histogram("name")
    • Record values: counter.add(1) or histogram.record(value)

STEP 4: LOGGING (main.py)
  logger.info("message")
    ↓
  LoggingInstrumentor automatically:
    • Adds trace_id to log record
    • Adds span_id to log record
    • Formats with timing info

STEP 5: EXPORT (automatic)
  BatchSpanProcessor & PeriodicExportingMetricReader automatically:
    • Batch collected spans/metrics
    • Export via OTLP gRPC to :4317
    • Retry on failure

STEP 6: COLLECTION & STORAGE
  OTLP Collector receives data and routes to backends
    → Jaeger stores traces
    → Prometheus stores metrics
    → Elasticsearch stores logs

STEP 7: VISUALIZATION
  Query in UI:
    • Jaeger: View full trace (all spans, latency breakdown)
    • Prometheus: Query metrics (e.g., requests_total > 100)
    • Kibana: Search logs by trace_id


═══════════════════════════════════════════════════════════════════════════════════
                          COMPARISON: BEFORE vs AFTER OTEL
═══════════════════════════════════════════════════════════════════════════════════

BEFORE (Langfuse approach):
  App → Langfuse SDK (proprietary) → Langfuse Backend → UI
  ❌ Vendor lock-in
  ❌ Single backend option
  ❌ Proprietary protocol

AFTER (OTLP approach):
  App → OpenTelemetry SDK (standard) → OTLP Exporter (CNCF standard)
                                            ↓
                                   OTLP Collector
                                      ↙    ↓    ↘
                                   Jaeger  Prometheus  Elasticsearch
  ✅ Vendor neutral (CNCF standard)
  ✅ Multiple backend options
  ✅ Open protocol (OTLP)
  ✅ Switch backends without changing app code!
```
