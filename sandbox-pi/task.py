from agent import pi_agent

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.scorer import includes
from inspect_ai.solver import system_message


@task
def repo_eval() -> Task:
    return Task(
        dataset=json_dataset("dataset.json"),
        solver=pi_agent(),
        scorer=includes(),
        sandbox="docker",   # pi + Python + click, network_mode: none
        message_limit=40,   # pi runs a multi-step tool loop per sample
    )


@task
def cvebench(
    challenges: str | list[str] | None = None,
    variants: str | list[str] = "one_day",
) -> Task:
    """CVE-Bench driven by the pi harness instead of the Claude Code CLI.

    Reuses cve-bench's dataset + grader as-is; only the solver is swapped for
    pi_agent(). Run from inside the cve-bench clone's uv env so `cvebench` and
    inspect_cyber are importable, e.g.:

        cd cve-bench && uv run inspect eval ../sandbox-pi/task.py@cvebench \\
            --model vllm/<model> -T challenges='["CVE-2024-2624"]'

    The dataset carries each sample's agent+target sandbox (so no sandbox= here);
    pi runs in the default `agent` (kali) container and reaches `target`.
    """
    # Lazy import: only needed for this task, and only resolvable inside the
    # cve-bench venv — keeps repo_eval() usable without cve-bench installed.
    from cvebench import cvebench as cb
    from cvebench.prompts import build_system_message
    from cvebench.utils import check_exploit

    vs = [variants] if isinstance(variants, str) else (variants or cb.EVAL_VARIANTS)
    return Task(
        dataset=cb.get_dataset(challenges, cb.CHALLENGES_DIR, vs),
        # system_message() injects cve-bench's pentester/verify framing; pi_agent
        # now folds system turns into its prompt. agentInternet=False (air-gapped).
        solver=[system_message(build_system_message(False)), pi_agent()],
        scorer=check_exploit(
            cb.STORE_KEY_ATTACK_SUCCESSFUL,
            cb.check_target_server_for_exploit_success,
        ),
    )
