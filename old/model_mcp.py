"""
Calculator Agent using OpenAI Agents SDK + Langfuse tracing + 2 MCP calculator tools.
Matches your working setup: local Langfuse, custom LLM client, OpenAIAgentsInstrumentor.

MCP Servers (start these first via mcp_tool.py):
  - add_sub_server  → http://localhost:8081/mcp
  - mul_div_server  → http://localhost:8082/mcp

Install:
    pip install openai-agents langfuse mcp openinference-instrumentation-openai-agents

Run:
    python agent.py`````````````````````````````````````````````````````````````````````````````````````````````````````````````````````````````````````    ```````````````````````````````````````````````
"""

import asyncio

# ---------------------------------------------------------------------------
# 1. Configure Langfuse client (matching your working pattern)
# ---------------------------------------------------------------------------
from langfuse import Langfuse

langfuse = Langfuse(
  secret_key="sk-lf-b9e03bf6-30e1-48ae-aeba-9fb755fe62ee",
  public_key="pk-lf-94d5b46a-c6c5-4ae3-938a-00d4c3633ac3",
  host="http://localhost:3000",
  flush_at=1,        # flush immediately after each trace
  flush_interval=1
)

if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")

# ---------------------------------------------------------------------------
# 2. Instrument the OpenAI Agents SDK (matches your working pattern exactly)
# ---------------------------------------------------------------------------
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor
OpenAIAgentsInstrumentor().instrument()

# ---------------------------------------------------------------------------
# 3. Initialize the agent with your custom LLM client
# ---------------------------------------------------------------------------
import os
from dotenv import load_dotenv
from agents import AsyncOpenAI, OpenAIChatCompletionsModel, Agent, Runner, trace
from agents.mcp import MCPServerStreamableHttp
from langfuse import observe

load_dotenv()


client = AsyncOpenAI(api_key=os.environ["API_KEY"], base_url="https://api.groq.com/openai/v1/")
model = OpenAIChatCompletionsModel(model="openai/gpt-oss-120b", openai_client=client)


# ---------------------------------------------------------------------------
# 4. MCP Servers
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# 5. Agent definition
# ---------------------------------------------------------------------------
agent = Agent(
    name="CalculatorAgent",
    instructions=(
        "You are a calculator assistant. "
        "Use the add/subtract tools for addition and subtraction, "
        "and the multiply/divide tools for multiplication and division. "
        "Always use a tool to compute — never calculate mentally."
    ),
    model=model,
    mcp_servers=[add_sub_server, mul_div_server],
)

# ---------------------------------------------------------------------------
# 6. Traced runner — matching your @observe pattern
# ---------------------------------------------------------------------------
@observe(name="calculator-agent-run")
async def run_agent(user_message: str) -> str:
    """Run the calculator agent with full Langfuse tracing."""
    print(f"\n[CalculatorAgent] Running: {user_message}")

    with trace(workflow_name="calculator-agent-run"):
        result = await Runner.run(agent, input=user_message)

    final_output = result.final_output
    print(f"[CalculatorAgent] Result: {final_output}")
    return final_output

# ---------------------------------------------------------------------------
# 7. Entry point
# ---------------------------------------------------------------------------
async def main():
    questions = [
        "What is 42 + 58?",
        "What is 100 - 37?",
        "What is 6 multiplied by 9?",
        "What is 144 divided by 12?",
        "What is (25 + 75) * 4?",   # multi-step: uses both servers
    ]

    async with add_sub_server, mul_div_server:
        # Warm up: list tools once so they're cached for all subsequent runs
        await add_sub_server.list_tools()
        await mul_div_server.list_tools()
        for question in questions:
            print(f"\nUser: {question}")
            response = await run_agent(question)
            print(f"Agent: {response}")

    # Ensure all traces are flushed before exit
    langfuse.flush()

if __name__ == "__main__":
    asyncio.run(main())