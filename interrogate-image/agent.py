"""Pydantic AI agent, bridged into Inspect, with a bash tool that runs in the
sandbox container — so the model interrogates the container over the bridge.

agent_bridge() redirects the pydantic-ai model calls into Inspect's model layer;
the bash tool delegates to sandbox().exec(), so commands run in the container.
"""

import os

# Pydantic AI builds an OpenAI client that requires OPENAI_API_KEY to exist at
# construction, even though the bridge intercepts the request (OpenAI is never
# called). A placeholder satisfies the constructor.
os.environ.setdefault("OPENAI_API_KEY", "unused-by-bridge")

from pydantic_ai import Agent as PydanticAgent
from pydantic_ai import UsageLimitExceeded
from pydantic_ai.usage import UsageLimits

from inspect_ai.agent import Agent, AgentState, agent, agent_bridge
from inspect_ai.model import get_model, user_prompt
from inspect_ai.model._model import ModelName
from inspect_ai.util import sandbox

MAX_REQUESTS = 8  # loop guard: stop a model that never stops calling tools


def _bridge_model() -> str:
    api = ModelName(get_model()).api
    if api == "anthropic":
        return "anthropic:inspect"
    if api == "google":
        return "google:inspect"
    return "openai:inspect"  # openai/vllm/ollama/groq — all openai-compatible


async def bash(command: str) -> str:
    """Run a bash command inside the sandbox container and return its output.

    Args:
        command: The bash command to execute.
    """
    result = await sandbox().exec(["bash", "-c", command])
    if result.success:
        return result.stdout
    return f"[exit {result.returncode}] {result.stderr}"


@agent
def interrogate_agent() -> Agent:
    async def execute(state: AgentState) -> AgentState:
        async with agent_bridge(state) as bridge:
            pai = PydanticAgent(
                _bridge_model(),
                system_prompt=(
                    "You are inside a container. Use the bash tool to interrogate it, "
                    "then give a short final answer with the result."
                ),
                tools=[bash],
            )
            try:
                result = await pai.run(
                    user_prompt(state.messages).text,
                    usage_limits=UsageLimits(request_limit=MAX_REQUESTS),
                )
                bridge.state.output.completion = str(result.output)
            except UsageLimitExceeded:
                bridge.state.output.completion = (
                    f"(agent stopped: exceeded {MAX_REQUESTS} model requests)"
                )
            return bridge.state

    return execute
