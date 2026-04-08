"""
MCP Calculator Servers with OpenTelemetry instrumentation.

Includes:
  - add, subtract (add_sub_server on 8081)
  - solve_steps with LangGraph (mul_div_server on 8082)

Each tool creates OTel child spans, linked to parent trace via W3C Trace Context.

Usage (3 separate terminals):
  Terminal 1 (from Free_twin_wd/):
    python mcp_tool_instrumented.py add_sub

  Terminal 2 (from Free_twin_wd/):
    python mcp_tool_instrumented.py mul_div

  Terminal 3 (from Free_twin_wd/):
    python otel_agent/agent_auto.py
"""

import ast
import operator as op_module
import re
import sys
import logging
from typing import TypedDict
from fastmcp import FastMCP, Context
from langgraph.graph import StateGraph, END
# Add path to find otel_setup
sys.path.insert(0, r"D:\Code\AI\Agents\Medium\Agent\Observability\Appraoch_new\Free_twin_wd")

from otel_agent.otel_setup import init_otel, get_tracer
from opentelemetry import trace
from opentelemetry.propagate import extract as otel_extract

# Initialize OTel
trace_provider, metrics_provider = init_otel(
    "mcp-calculator-server",
    filter_libraries=["fastmcp"],   # drop FastMCP's own root spans — we emit our own
)
tracer = get_tracer(__name__)


def _get_parent_ctx(ctx: Context):
    """Extract W3C trace context (traceparent) from the FastMCP HTTP request headers."""
    try:
        headers = dict(ctx.request_context.request.headers)
        return otel_extract(headers)
    except Exception:
        return None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LangGraph: safe expression evaluator (used by solve_steps tool)
# ---------------------------------------------------------------------------
ALLOWED_OPS = {
    ast.Add:  op_module.add,
    ast.Sub:  op_module.sub,
    ast.Mult: op_module.mul,
    ast.Div:  op_module.truediv,
    ast.Pow:  op_module.pow,
    ast.USub: op_module.neg,
    ast.UAdd: op_module.pos,
}

def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_OPS:
        return ALLOWED_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_OPS:
        return ALLOWED_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")

def _safe_eval(expr: str) -> float:
    """Evaluate a math expression string safely using the AST (no eval())."""
    tree = ast.parse(expr.strip(), mode="eval")
    return _eval_node(tree.body)


# ---------------------------------------------------------------------------
# LangGraph state + nodes
# ---------------------------------------------------------------------------
class MathState(TypedDict):
    expression: str
    tokens: list
    result: float
    steps: list
    error: str


def parse_node(state: MathState) -> dict:
    """Node 1 — tokenize the expression into numbers and operators."""
    with tracer.start_as_current_span("langgraph_parse_node") as span:
        expr = state["expression"]
        tokens = re.findall(r"\d+\.?\d*|[+\-*/^()]", expr)

        span.set_attribute("expression", expr)
        span.set_attribute("token_count", len(tokens))
        span.set_attribute("tokens", str(tokens))

        logger.info(f"[LangGraph] Parse: '{expr}' → {len(tokens)} tokens")

        return {
            "tokens": tokens,
            "steps": [f"[Parse]    '{expr}'  →  tokens: {tokens}"],
        }


def evaluate_node(state: MathState) -> dict:
    """Node 2 — evaluate the expression and record the numeric result."""
    with tracer.start_as_current_span("langgraph_evaluate_node") as span:
        expr = state["expression"]
        steps = state["steps"]

        span.set_attribute("expression", expr)

        try:
            result = _safe_eval(expr)

            span.set_attribute("result", result)
            span.set_attribute("error", "")
            logger.info(f"[LangGraph] Evaluate: '{expr}' = {result}")

            return {
                "result": result,
                "error": "",
                "steps": steps + [f"[Evaluate] '{expr}'  =  {result}"],
            }
        except Exception as exc:
            span.set_attribute("result", 0.0)
            span.set_attribute("error", str(exc))
            span.record_exception(exc)
            logger.error(f"[LangGraph] Evaluate ERROR: {exc}")

            return {
                "result": 0.0,
                "error": str(exc),
                "steps": steps + [f"[Evaluate] ERROR: {exc}"],
            }


def format_node(state: MathState) -> dict:
    """Node 3 — build the final human-readable answer string."""
    with tracer.start_as_current_span("langgraph_format_node") as span:
        steps = state["steps"]

        if state["error"]:
            summary = f"Could not solve '{state['expression']}': {state['error']}"
            span.set_attribute("error", state["error"])
        else:
            result = state["result"]
            # Show integer when there's no fractional part
            result_str = str(int(result)) if result == int(result) else str(result)
            summary = f"[Format]   Result = {result_str}"
            span.set_attribute("result_formatted", result_str)

        span.set_attribute("expression", state["expression"])
        logger.info(f"[LangGraph] Format: {summary}")

        return {"steps": steps + [summary]}


# Compile the LangGraph workflow once at module load
_solver_graph = (
    StateGraph(MathState)
    .add_node("parse",    parse_node)
    .add_node("evaluate", evaluate_node)
    .add_node("format",   format_node)
    .set_entry_point("parse")
    .add_edge("parse",    "evaluate")
    .add_edge("evaluate", "format")
    .add_edge("format",   END)
    .compile()
)


# ---------------------------------------------------------------------------
# Server 1: Addition & Subtraction  (port 8081)
# ---------------------------------------------------------------------------
add_sub_mcp = FastMCP(name="add_sub_server")


@add_sub_mcp.tool()
def add(a: float, b: float, ctx: Context) -> float:
    """Add two numbers together."""
    parent_ctx = _get_parent_ctx(ctx)
    with tracer.start_as_current_span("add_operation", context=parent_ctx) as span:
        span.set_attribute("operand_a", a)
        span.set_attribute("operand_b", b)
        result = a + b
        span.set_attribute("result", result)
        logger.info(f"✓ add({a}, {b}) = {result}")
        return result


@add_sub_mcp.tool()
def subtract(a: float, b: float, ctx: Context) -> float:
    """Subtract b from a."""
    parent_ctx = _get_parent_ctx(ctx)
    with tracer.start_as_current_span("subtract_operation", context=parent_ctx) as span:
        span.set_attribute("operand_a", a)
        span.set_attribute("operand_b", b)
        result = a - b
        span.set_attribute("result", result)
        logger.info(f"✓ subtract({a}, {b}) = {result}")
        return result


# ---------------------------------------------------------------------------
# Server 2: Multi-step solver with LangGraph  (port 8082)
# ---------------------------------------------------------------------------
mul_div_mcp = FastMCP(name="mul_div_server")


@mul_div_mcp.tool()
def solve_steps(expression: str, ctx: Context) -> str:
    """
    Solve a multi-step arithmetic expression and return a step-by-step breakdown.

    Uses a 3-node LangGraph pipeline:
      parse     → tokenize the expression
      evaluate  → compute the result safely (no eval())
      format    → produce a readable step-by-step answer

    Supports: +  -  *  /  **  parentheses  (e.g. '(3 + 5) * 2 - 4 / 2')
    Returns a newline-separated log of each node's output.
    """
    parent_ctx = _get_parent_ctx(ctx)
    with tracer.start_as_current_span("solve_steps_operation", context=parent_ctx) as span:
        span.set_attribute("expression", expression)

        try:
            initial_state: MathState = {
                "expression": expression,
                "tokens": [],
                "result": 0.0,
                "steps": [],
                "error": "",
            }
            final_state = _solver_graph.invoke(initial_state)
            result_str = "\n".join(final_state["steps"])

            span.set_attribute("result", result_str)
            span.set_attribute("error", final_state.get("error", ""))
            logger.info(f"✓ solve_steps('{expression}') completed")

            return result_str
        except Exception as exc:
            span.set_attribute("error", str(exc))
            logger.error(f"✗ solve_steps('{expression}') → {exc}")
            raise


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "add_sub"

    try:
        if mode == "add_sub":
            logger.info("🚀 Starting Addition & Subtraction MCP server on http://localhost:8081")
            logger.info("   Exporting traces to localhost:4317 (Tempo)")
            add_sub_mcp.run(transport="http", host="0.0.0.0", port=8081)

        elif mode == "mul_div":
            logger.info("🚀 Starting Multi-step Solver MCP server on http://localhost:8082")
            logger.info("   Exporting traces to localhost:4317 (Tempo)")
            logger.info("   LangGraph nodes instrumented with OTel spans")
            mul_div_mcp.run(transport="http", host="0.0.0.0", port=8082)

        else:
            logger.error(f"Unknown mode '{mode}'. Use: add_sub | mul_div")
            sys.exit(1)

    finally:
        # Flush telemetry on shutdown
        trace_provider.force_flush()
        metrics_provider.shutdown()
        logger.info("📊 Traces flushed to Tempo")
