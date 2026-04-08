# OTel Tracing Guide — Agent + MCP Tools

A quick reference for adding distributed tracing to a new agent and MCP tool server so everything shows up in **one unified trace** in Grafana.

---

## How it works

```
Your Agent (agent_auto.py)
    │  injects traceparent header via HTTPXClientInstrumentor
    ▼
MCP Tool Server (mcp_tool_instrumented.py)
    │  extracts traceparent from request via FastMCP Context
    ▼
Grafana / Tempo  ← single trace, all spans linked
```

---

## Prerequisites

```bash
pip install opentelemetry-api opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-grpc \
    opentelemetry-instrumentation-logging \
    opentelemetry-instrumentation-httpx \
    opentelemetry-exporter-prometheus \
    prometheus_client \
    openinference-instrumentation-openai-agents
```

Start the Grafana stack first:
```bash
cd grafana_stack && docker compose up -d
```

---

## Part 1 — Agent (`your_agent.py`)

### Step 1: Initialize OTel FIRST (before any other imports)

```python
from otel_setup import init_otel, get_tracer, get_meter

trace_provider, metrics_provider = init_otel("your-service-name")
tracer = get_tracer(__name__)
meter  = get_meter(__name__)
```

> **Why first?** The global TracerProvider must be set before any SDK or instrumentor imports. If you import agents SDK before this, auto-instrumentation won't attach correctly.

---

### Step 2: Add auto-instrumentation

```python
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

OpenAIAgentsInstrumentor().instrument()   # captures LLM calls, tool calls automatically
HTTPXClientInstrumentor().instrument()    # injects traceparent into MCP HTTP requests
```

> **Why HTTPXClientInstrumentor?** The OpenAI Agents SDK uses `httpx` internally to call MCP servers. This instrumentor silently injects the `traceparent` header into every httpx request so the MCP server can link its spans to your trace.

---

### Step 3: Wrap everything in a root span

```python
async def main():
    # Wrap MCP server setup inside a span — otherwise connection calls
    # (GET/POST/DELETE) appear as separate root traces in Grafana
    with tracer.start_as_current_span("agent-session") as span:
        span.set_attribute("question.count", len(questions))

        async with your_mcp_server:
            await your_mcp_server.list_tools()   # happens inside the span ✅

            for question in questions:
                await run_agent(question)

    # Always flush before exit
    trace_provider.force_flush()
    metrics_provider.shutdown()
```

---

### Step 4: Create manual spans for your workflow

```python
async def run_agent(user_message: str) -> str:
    with tracer.start_as_current_span("agent-run") as span:
        span.set_attribute("agent.input", user_message)

        with tracer.start_as_current_span("runner.run"):
            # agents_trace links OpenAI Agents SDK auto-spans to your OTel span
            with agents_trace(workflow_name="agent-run"):
                result = await Runner.run(agent, input=user_message)

        span.set_attribute("agent.output", result.final_output)

    return result.final_output
```

---

### Step 5: Add metrics (optional)

```python
run_counter = meter.create_counter("agent.runs.total", unit="1")
run_duration = meter.create_histogram("agent.run.duration", unit="s")

# Inside your run function:
run_counter.add(1, {"agent": "MyAgent"})
run_duration.record(elapsed, {"agent": "MyAgent"})
```

---

## Part 2 — MCP Tool Server (`your_mcp_tool.py`)

### Step 1: Initialize OTel and filter FastMCP's built-in spans

```python
from otel_setup import init_otel, get_tracer
from opentelemetry.propagate import extract as otel_extract
from fastmcp import FastMCP, Context

# filter_libraries=["fastmcp"] drops FastMCP's own root spans (they are noise).
# Our custom spans below replace them with more meaningful information.
trace_provider, metrics_provider = init_otel(
    "your-mcp-service-name",
    filter_libraries=["fastmcp"],
)
tracer = get_tracer(__name__)
```

---

### Step 2: Add a helper to extract trace context from each request

```python
def _get_parent_ctx(ctx: Context):
    """Extract W3C traceparent from the incoming HTTP request headers."""
    try:
        headers = dict(ctx.request_context.request.headers)
        return otel_extract(headers)
    except Exception:
        return None
```

> **Why this?** FastMCP doesn't automatically read the `traceparent` header. This helper does it manually so your tool spans become children of the agent's trace — same `trace_id`.

---

### Step 3: Add `ctx: Context` to every tool and use the parent context

```python
mcp = FastMCP(name="my-server")

@mcp.tool()
def my_tool(input: str, ctx: Context) -> str:
    """Your tool description."""
    parent_ctx = _get_parent_ctx(ctx)   # extract traceparent from request

    with tracer.start_as_current_span("my_tool_operation", context=parent_ctx) as span:
        span.set_attribute("input", input)

        # your logic here
        result = do_something(input)

        span.set_attribute("result", result)
        return result
```

> **Key:** `context=parent_ctx` links this span to the agent's trace. Without it, the MCP server creates a separate trace with a different `trace_id`.

---

### Step 4: Create child spans for internal steps (e.g. LangGraph nodes)

```python
def my_langgraph_node(state):
    with tracer.start_as_current_span("node_name") as span:
        span.set_attribute("input", state["expression"])

        result = do_work(state)

        span.set_attribute("result", str(result))
        return result
```

Child spans are automatically nested under the parent tool span — no extra wiring needed.

---

### Step 5: Flush on shutdown

```python
if __name__ == "__main__":
    try:
        mcp.run(transport="http", host="0.0.0.0", port=8081)
    finally:
        trace_provider.force_flush()
        metrics_provider.shutdown()
```

---

## What you get in Grafana

```
agent-session
  └─ agent-run
     └─ runner.run
        └─ CalculatorAgent          ← auto by OpenAIAgentsInstrumentor
           ├─ generation            ← LLM call
           ├─ my_tool               ← tool call
           └─ generation            ← LLM response

mcp-service  my_tool_operation      ← same trace_id as above ✅
  ├─ node_1
  ├─ node_2
  └─ node_3
```

---

## Common mistakes

| Mistake | Fix |
|---------|-----|
| `init_otel()` called after SDK imports | Always call it first, before any agents/MCP imports |
| Forgot `HTTPXClientInstrumentor` on agent side | MCP server won't receive `traceparent` → separate traces |
| Forgot `ctx: Context` param on MCP tool | `_get_parent_ctx` has no request to read from |
| Forgot `context=parent_ctx` in `start_as_current_span` | Span starts a new root trace instead of linking |
| MCP setup (`async with`) outside any span | Connection calls appear as root traces in Grafana |
| Forgot `force_flush()` before exit | Last batch of spans never reaches Tempo |
