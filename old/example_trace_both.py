"""
Single distributed trace across:
  - Main app (otel_setup.py) — creates root span
  - MCP servers (mcp_tool.py) — receives trace context via HTTP headers, creates child spans

Trace context flows: HTTP W3C Trace Context headers automatically propagate trace_id/span_id.

Usage:
  # Terminal 1: Start add_sub MCP server
  python mcp_tool_instrumented.py add_sub

  # Terminal 2: Start mul_div MCP server
  python mcp_tool_instrumented.py mul_div

  # Terminal 3: Run this script
  python example_trace_both.py
"""

import sys
sys.path.insert(0, r"D:\Code\AI\Agents\Medium\Agent\Observability\Appraoch_new\Free_twin_wd")

from otel_agent.otel_setup import init_otel, get_tracer
import requests
import logging

# Initialize OpenTelemetry
trace_provider, metrics_provider = init_otel("main-app")

# Create a tracer for this module
tracer = get_tracer(__name__)

# Setup logging
logger = logging.getLogger(__name__)

# MCP Server endpoints
ADD_SUB_URL = "http://localhost:8081"
MUL_DIV_URL = "http://localhost:8082"


def call_mcp_with_trace(server_url: str, tool_name: str, params: dict):
    """
    Call an MCP tool via HTTP.

    The HTTP request automatically includes W3C Trace Context headers
    (traceparent, tracestate) via the requests instrumentation.
    MCP server will read these headers and link its spans to this trace.
    """
    url = f"{server_url}/tools/{tool_name}"

    with tracer.start_as_current_span(f"call_mcp_{tool_name}") as span:
        span.set_attribute("mcp.server", server_url)
        span.set_attribute("mcp.tool", tool_name)
        span.set_attribute("mcp.params", str(params))

        logger.info(f"📤 Calling {tool_name} at {server_url}")

        # The requests library will automatically inject traceparent/tracestate headers
        response = requests.post(url, json=params)

        span.set_attribute("http.status_code", response.status_code)
        result = response.json()
        span.set_attribute("mcp.result", str(result))

        logger.info(f"📥 {tool_name} result: {result}")
        return result


def main():
    """
    Root span that calls multiple MCP tools.
    All child spans (HTTP calls to MCP servers) are linked via trace context.
    """
    with tracer.start_as_current_span("main_workflow") as span:
        span.set_attribute("workflow.name", "multi_mcp_trace")

        logger.info("🚀 Starting distributed trace example")

        # Call add tool on add_sub server
        add_result = call_mcp_with_trace(
            ADD_SUB_URL,
            "add",
            {"a": 10, "b": 5}
        )

        # Call subtract tool on add_sub server
        sub_result = call_mcp_with_trace(
            ADD_SUB_URL,
            "subtract",
            {"a": 20, "b": 7}
        )

        # Call multiply tool on mul_div server
        mul_result = call_mcp_with_trace(
            MUL_DIV_URL,
            "multiply",
            {"a": add_result["result"], "b": sub_result["result"]}
        )

        # Call divide tool on mul_div server
        div_result = call_mcp_with_trace(
            MUL_DIV_URL,
            "divide",
            {"a": mul_result["result"], "b": 2}
        )

        logger.info(f"✅ Workflow complete: {div_result}")
        span.set_attribute("workflow.result", str(div_result))

    # ⚠️  IMPORTANT: Flush telemetry before shutdown
    trace_provider.force_flush()
    metrics_provider.force_flush()
    logger.info("📊 Traces exported to Tempo!")


if __name__ == "__main__":
    main()
