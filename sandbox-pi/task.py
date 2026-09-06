from agent import pi_agent

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.scorer import includes


@task
def repo_eval() -> Task:
    return Task(
        dataset=json_dataset("dataset.json"),
        solver=pi_agent(),
        scorer=includes(),
        sandbox="docker",   # pi + Python + click, network_mode: none
        message_limit=40,   # pi runs a multi-step tool loop per sample
    )
