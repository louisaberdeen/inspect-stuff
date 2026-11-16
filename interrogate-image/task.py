from agent import interrogate_agent

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import includes


@task
def interrogate_image() -> Task:
    return Task(
        dataset=[
            Sample(
                input="You are inside a container. Use bash to inspect the git repo "
                "at /workspace/repo and report the name of its README file (the part "
                "before the extension).",
                target="README",
            )
        ],
        solver=interrogate_agent(),
        scorer=includes(),
        sandbox="docker",     # builds Dockerfile.multistage, runs with network_mode: none
        message_limit=20,     # native loop guard: stop a runaway tool loop
    )
