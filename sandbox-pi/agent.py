"""pi (the coding agent) runs INSIDE the air-gapped container, reaching the model
over Inspect's sandbox bridge — not the internet.

sandbox_agent_bridge() runs a proxy in the container on bridge.port that speaks the
OpenAI API and relays to Inspect's model over the exec channel (the same control
plane docker uses for exec/read/write). So pi calls http://localhost:<port> and
Inspect forwards to the real model from the host; the container stays network_mode: none.
"""

from inspect_ai.agent import Agent, AgentState, agent, sandbox_agent_bridge
from inspect_ai.model import ChatMessageUser
from inspect_ai.util import sandbox


@agent
def pi_agent() -> Agent:
    async def execute(state: AgentState) -> AgentState:
        async with sandbox_agent_bridge(state, model="inspect") as bridge:
            prompt = "\n\n".join(
                m.text for m in state.messages if isinstance(m, ChatMessageUser)
            )
            # The "vllm" provider is registered in the image (Dockerfile) pointing at
            # the bridge on 127.0.0.1:13131 — pi ignores OPENAI_BASE_URL, so a custom
            # provider is required. bridge.port must stay the default 13131 to match.
            result = await sandbox().exec(
                cmd=[
                    "pi", "--print", "--no-session",
                    "--provider", "vllm", "--model", "inspect",
                    prompt,
                ],
            )
            bridge.state.output.completion = result.stdout
            if not result.success:
                bridge.state.output.completion += f"\n[pi error] {result.stderr}"
            return bridge.state

    return execute
