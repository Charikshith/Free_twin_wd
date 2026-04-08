"""
Multi-Agent Calculator — OpenTelemetry distributed tracing.

Three agents in a handoff chain, all captured in ONE trace:

  OrchestratorAgent        ← decides which specialist to use
    ├── AddSubAgent         ← handles add/subtract via MCP add_sub_server
    └── SolverAgent         ← handles complex expressions via MCP mul_div_server

Span hierarchy produced:
  multi-agent-session
    └─ multi-agent-run
       └─ runner.run
          └─ OrchestratorAgent          ← auto by OpenAIAgentsInstrumentor
             ├─ generation              ← LLM decides which agent to call
             ├─ handoff → AddSubAgent   ← auto (handoff span)
             │  └─ AddSubAgent
             │     ├─ generation
             │     └─ add / subtract    ← MCP tool call
             │        └─ mcp-calculator-server  add_operation (same trace_id!) ✅
             └─ handoff → SolverAgent   ← auto (handoff span)
                └─ SolverAgent
                   ├─ generation
                   └─ solve_steps       ← MCP tool call
                      └─ mcp-calculator-server  solve_steps_operation ✅
                         ├─ langgraph_parse_node
                         ├─ langgraph_evaluate_node
                         └─ langgraph_format_node

MCP Servers (start first from Free_twin_wd/):
    python mcp_tool_instrumented.py add_sub   # → localhost:8081
    python mcp_tool_instrumented.py mul_div   # → localhost:8082

Grafana stack:
    cd grafana_stack && docker compose up -d
    Open: http://localhost:3000

Run:
    cd otel_agent && python agent_auto_multiple.py
"""

import asyncio
import logging
import os
import time
from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault("OPENAI_API_KEY", "not-used-routing-to-groq")

# ── 1. OTel bootstrap — MUST be first ────────────────────────────────────────
from otel_setup import init_otel, get_tracer, get_meter

trace_provider, metrics_provider = init_otel("multi-agent-calculator")

tracer = get_tracer("otel_agent.multi_agent")
meter  = get_meter("otel_agent.multi_agent")
logger = logging.getLogger(__name__)

# ── 2. Auto-instrumentation ───────────────────────────────────────────────────
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor

OpenAIAgentsInstrumentor().instrument()

# Inject traceparent into ALL outgoing httpx requests so MCP servers
# receive the correct trace_id.
#
# Why a module-level variable instead of contextvars?
# The MCP client's httpx calls run in a background asyncio task created
# during `async with add_sub_server`.  That task copies the OTel context
# at creation time — it never sees per-question spans created later.
# A plain module-level variable is always read fresh, so the monkey-patch
# picks up whatever trace context we set before each Runner.run() call.
import httpx
from opentelemetry import context as otel_context
from opentelemetry.propagate import inject as otel_inject

_mcp_trace_context = None          # set in run_multi_agent() before each run

_original_send = httpx.AsyncClient.send

async def _send_with_trace(self, request, **kwargs):
    carrier = {}
    otel_inject(carrier, context=_mcp_trace_context)
    for k, v in carrier.items():
        request.headers[k] = v
    return await _original_send(self, request, **kwargs)

httpx.AsyncClient.send = _send_with_trace

# ── 3. Metrics ────────────────────────────────────────────────────────────────
session_counter = meter.create_counter(
    "multi_agent.sessions.total",
    unit="1",
    description="Total multi-agent sessions run",
)
session_duration = meter.create_histogram(
    "multi_agent.session.duration",
    unit="s",
    description="Wall-clock duration of each multi-agent session",
)

# ── 4. LLM client ─────────────────────────────────────────────────────────────
from pydantic import BaseModel
from agents import AsyncOpenAI, OpenAIChatCompletionsModel, Agent, Runner, handoff
from agents import trace as agents_trace
from agents.mcp import MCPServerStreamableHttp


class HandoffReason(BaseModel):
    """Reason the orchestrator is handing off to a specialist."""
    reason: str


def on_handoff(ctx, input: HandoffReason) -> None:
    logger.info(f"[Handoff] reason='{input.reason}'")

client = AsyncOpenAI(
    api_key=os.environ["API_KEY"],
    base_url="https://api.groq.com/openai/v1/",
)
model = OpenAIChatCompletionsModel(
    model="openai/gpt-oss-120b",
    openai_client=client,
)

# ── 5. MCP servers ────────────────────────────────────────────────────────────
add_sub_server = MCPServerStreamableHttp(
    name="add_sub_server",
    params={"url": "http://localhost:8081/mcp"},
    cache_tools_list=True,
)
mul_div_server = MCPServerStreamableHttp(
    name="mul_div_server",
    params={"url": "http://localhost:8082/mcp"},
    cache_tools_list=True,
)

# ── 6. Agents ─────────────────────────────────────────────────────────────────

# Specialist: addition and subtraction only
add_sub_agent = Agent(
    name="AddSubAgent",
    instructions=(
        "You only handle addition and subtraction. "
        "Always use the add or subtract tool — never calculate mentally. "
        "Return just the numeric result."
    ),
    model=model,
    mcp_servers=[add_sub_server],
)

# Specialist: complex multi-step expressions
solver_agent = Agent(
    name="SolverAgent",
    instructions=(
        "You handle complex arithmetic expressions with multiple operations. "
        "Always use the solve_steps tool — never calculate mentally. "
        "Return the full step-by-step breakdown."
    ),
    model=model,
    mcp_servers=[mul_div_server],
)

# Orchestrator: routes to the right specialist via handoff
# handoff() with input_type=HandoffReason generates a valid JSON schema
# (properties: {reason: ...}) that Groq accepts — bare agent handoffs produce
# an empty schema ("required" with no "properties") which Groq rejects.
orchestrator = Agent(
    name="OrchestratorAgent",
    instructions=(
        "You are a routing orchestrator for a calculator system. "
        "Given a math question, hand off to the correct specialist:\n"
        "  - AddSubAgent  → simple addition or subtraction only\n"
        "  - SolverAgent  → complex expressions with *, /, ** or parentheses\n"
        "Always include a brief reason when handing off. "
        "Never calculate yourself — always hand off."
    ),
    model=model,
    handoffs=[
        handoff(add_sub_agent, on_handoff=on_handoff, input_type=HandoffReason),
        handoff(solver_agent,  on_handoff=on_handoff, input_type=HandoffReason),
    ],
)

# ── 7. Runner ─────────────────────────────────────────────────────────────────
async def run_multi_agent(user_message: str) -> str:
    """
    Run the orchestrator → sub-agent chain with full OTel tracing.

    All handoffs, LLM calls, and MCP tool calls appear as children
    of the 'multi-agent-run' span — same trace_id throughout.
    """
    global _mcp_trace_context
    start = time.perf_counter()

    with tracer.start_as_current_span("multi-agent-run") as span:
        span.set_attribute("workflow.name", "multi-agent-calculator")
        span.set_attribute("agent.input", user_message)
        span.set_attribute("orchestrator", "OrchestratorAgent")

        # Capture this span's context so the httpx monkey-patch can inject
        # the correct traceparent into MCP calls (see comment in section 2).
        _mcp_trace_context = otel_context.get_current()

        logger.info(f"[Orchestrator] Starting: {user_message}")

        with tracer.start_as_current_span("runner.run") as inner:
            inner.set_attribute("entry.agent", "OrchestratorAgent")

            with agents_trace(workflow_name="multi-agent-calculator"):
                result = await Runner.run(orchestrator, input=user_message)

        elapsed = time.perf_counter() - start
        final_output = result.final_output

        span.set_attribute("agent.output", final_output)
        span.set_attribute("duration_seconds", round(elapsed, 3))

        session_counter.add(1, {"workflow": "multi-agent-calculator"})
        session_duration.record(elapsed, {"workflow": "multi-agent-calculator"})

        logger.info(f"[Orchestrator] Done ({elapsed:.3f}s): {final_output}")

    return final_output


# ── 8. Entry point ────────────────────────────────────────────────────────────
async def main():
    questions = [
        # "What is 42 + 58?",                      # → AddSubAgent → add tool
        "What is 100 - 37?",                      # → AddSubAgent → subtract tool
        "Solve step by step: (3 + 5) * 2 - 4 / 2",  # → SolverAgent → solve_steps tool
    ]

    async with add_sub_server, mul_div_server:
        await add_sub_server.list_tools()
        await mul_div_server.list_tools()

        for question in questions:
            print(f"\n{'─'*60}")
            print(f"User:  {question}")
            response = await run_multi_agent(question)
            print(f"Agent: {response}")

    trace_provider.force_flush()
    metrics_provider.shutdown()
    print(f"\n{'─'*60}")
    print("Traces exported → open Grafana: http://localhost:3000")


if __name__ == "__main__":
    asyncio.run(main())
