# Distributed Tracing: Main App + MCP Servers in One Trace

## Files Created

All in `Appraoch_new/Free_twin_wd/`:
- **example_trace_both.py** — Main app that calls MCP servers
- **mcp_tool_instrumented.py** — MCP servers with OTel tracing
- **TRACE_SETUP.md** — This guide

## How It Works

```
Main App (example_trace_both.py)
  │
  ├─ Root Span: "main_workflow"
  │
  ├─ Child Span 1: HTTP POST /tools/add → MCP add_sub_server:8081
  │   │ (W3C Trace Context headers injected automatically)
  │   └─ MCP Server creates: Span "add_operation"
  │
  ├─ Child Span 2: HTTP POST /tools/subtract → MCP add_sub_server:8081
  │   └─ MCP Server creates: Span "subtract_operation"
  │
  └─ Child Span 3: HTTP POST /tools/multiply → MCP mul_div_server:8082
     └─ MCP Server creates: Span "multiply_operation"

All spans share the same trace_id → single distributed trace in Tempo
```

## Prerequisites

```bash
pip install requests opentelemetry-instrumentation-requests
```

## Quick Start

**Step 1: Start Grafana stack** (in `Appraoch_new/grafana_stack`)
```bash
cd Appraoch_new/grafana_stack
docker compose up -d
```

Verify:
```bash
curl http://localhost:3100/ready  # Loki
curl http://localhost:3200/ready  # Tempo
```

**Step 2: Start MCP servers** (2 terminals in `Free_twin_wd/`)

Terminal A:
```bash
python mcp_tool_instrumented.py add_sub
# 🚀 Starting Addition & Subtraction MCP server on http://localhost:8081
```

Terminal B:
```bash
python mcp_tool_instrumented.py mul_div
# 🚀 Starting Multiply & Divide MCP server on http://localhost:8082
```

**Step 3: Run distributed trace example**
```bash
python example_trace_both.py
# 🚀 Starting distributed trace example
# 📤 Calling add at http://localhost:8081
# 📥 add result: {'result': 15}
# ... more calls ...
# ✅ Workflow complete
# 📊 Traces exported to Tempo!
```

**Step 4: View in Grafana**
1. http://localhost:3000 (admin/admin)
2. **Explore** → **Tempo**
3. Search by service: `main-app`
4. Click trace to see full span waterfall

## Key Points

✅ **Single Trace** — All spans linked via W3C Trace Context  
✅ **No HTTP Instrumentation Library** — Built into `requests`  
✅ **Child Spans** — Each MCP tool call shows operation details  
✅ **Error Tracking** — Exceptions captured in spans  

## Files Location

```
D:\Code\AI\Agents\Medium\Agent\Observability\Appraoch_new\Free_twin_wd\
├── example_trace_both.py
├── mcp_tool_instrumented.py
├── TRACE_SETUP.md
├── otel_agent/
│   └── otel_setup.py (already exists)
└── mcp_tool.py (original - don't use for this demo)
```
