"""
MCP Calculator Server using FastMCP with HTTP transport.

Two MCP servers:
  - add_sub_server  → port 8081
  - mul_div_server  → port 8082  (also hosts the LangGraph multi-step solver)

Install:
    pip install fastmcp langgraph

Run both servers (in separate terminals):
    python mcp_tool.py add_sub
    python mcp_tool.py mul_div
"""

import ast
import operator as op_module
import re
import sys
from typing import TypedDict

from fastmcp import FastMCP
from langgraph.graph import StateGraph, END

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
    expr = state["expression"]
    tokens = re.findall(r"\d+\.?\d*|[+\-*/^()]", expr)
    return {
        "tokens": tokens,
        "steps": [f"[Parse]    '{expr}'  →  tokens: {tokens}"],
    }


def evaluate_node(state: MathState) -> dict:
    """Node 2 — evaluate the expression and record the numeric result."""
    expr = state["expression"]
    steps = state["steps"]
    try:
        result = _safe_eval(expr)
        return {
            "result": result,
            "error": "",
            "steps": steps + [f"[Evaluate] '{expr}'  =  {result}"],
        }
    except Exception as exc:
        return {
            "result": 0.0,
            "error": str(exc),
            "steps": steps + [f"[Evaluate] ERROR: {exc}"],
        }


def format_node(state: MathState) -> dict:
    """Node 3 — build the final human-readable answer string."""
    steps = state["steps"]
    if state["error"]:
        summary = f"Could not solve '{state['expression']}': {state['error']}"
    else:
        result = state["result"]
        # Show integer when there's no fractional part
        result_str = str(int(result)) if result == int(result) else str(result)
        summary = f"[Format]   Result = {result_str}"
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
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b

@add_sub_mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b


# ---------------------------------------------------------------------------
# Server 2: Multiply & Divide  (port 8082)
# ---------------------------------------------------------------------------
mul_div_mcp = FastMCP(name="mul_div_server")

# @mul_div_mcp.tool()
# def multiply(a: float, b: float) -> float:
#     """Multiply two numbers together."""
#     return a * b

# @mul_div_mcp.tool()
# def divide(a: float, b: float) -> float:
#     """Divide a by b. Raises an error if b is zero."""
#     if b == 0:
#         raise ValueError("Cannot divide by zero.")
#     return a / b


@mul_div_mcp.tool()
def solve_steps(expression: str) -> str:
    """
    Solve a multi-step arithmetic expression and return a step-by-step breakdown.

    Uses a 3-node LangGraph pipeline:
      parse     → tokenize the expression
      evaluate  → compute the result safely (no eval())
      format    → produce a readable step-by-step answer

    Supports: +  -  *  /  **  parentheses  (e.g. '(3 + 5) * 2 - 4 / 2')
    Returns a newline-separated log of each node's output.
    """
    initial_state: MathState = {
        "expression": expression,
        "tokens": [],
        "result": 0.0,
        "steps": [],
        "error": "",
    }
    final_state = _solver_graph.invoke(initial_state)
    return "\n".join(final_state["steps"])


# ---------------------------------------------------------------------------
# Entry point — pick which server to run via CLI arg
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "add_sub"

    if mode == "add_sub":
        print("Starting Addition & Subtraction MCP server on http://localhost:8081")
        add_sub_mcp.run(transport="http", host="0.0.0.0", port=8081)
    elif mode == "mul_div":
        print("Starting Multiply & Divide MCP server on http://localhost:8082")
        mul_div_mcp.run(transport="http", host="0.0.0.0", port=8082)
    else:
        print(f"Unknown mode '{mode}'. Use: add_sub | mul_div")
        sys.exit(1)

# python mcp_tool.py add_sub   # → localhost:8081
# python mcp_tool.py mul_div   # → localhost:8082  (multiply, divide, solve_steps)