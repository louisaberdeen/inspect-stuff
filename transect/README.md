# Transect — analysing CVE-Bench pi traces

[Transect](https://github.com/AI-Safety-Institute/transect) (UK AI Security
Institute, built on [Inspect Scout](https://meridianlabs-ai.github.io/inspect_scout/))
turns an agent eval transcript into one interactive HTML report on a turn-based
timeline. A **structural** pass (token use, events, sub-agent spans) is free and
needs no API key; **judged** passes label each turn against the phase vocabulary
in `spec.yaml` using an LLM judge (costs model calls).

Here it's pointed at the `.eval` logs this repo's CVE-Bench runs produce in
`../cve-bench-pi/logs/`. `spec.yaml` describes an exploit attempt as five phases
(recon → vuln_analysis → exploit_dev → exploitation → verification); pi is a
single agent so there are no sub-agents to classify.

## Files

| File | Role |
|------|------|
| `spec.yaml` | Phase vocabulary + task context for this eval family. Edit after a structural pass. |
| `analyse.py` | Thin wrapper: `transect(<logs>, spec.yaml, judge_models=…)`. Structural by default. |
| `.venv/` | Isolated env (gitignored) — transect pulls `inspect_scout` + many deps; kept out of the root `.venv`. |

## Setup (one-time)

Python 3.12+ in its own venv (so it can't disturb the root `.venv`'s pinned `inspect-ai`):

```bash
cd transect
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python git+https://github.com/AI-Safety-Institute/transect.git
```

For **judged** runs, install the judge provider's SDK into that venv and export its key:

```bash
uv pip install --python .venv/bin/python anthropic   # or: openai
export ANTHROPIC_API_KEY=...                          # or: OPENAI_API_KEY
```

Any [Inspect model provider](https://inspect.aisi.org.uk/providers.html) works as
a judge — including your own Colab vLLM (`vllm/RedHatAI/Qwen3.8-27B-INT4` with
`VLLM_BASE_URL`/`VLLM_API_KEY` set), though a 4-bit local model is a weak judge;
Claude/GPT give far better labels.

Optional — install Transect's Claude Code skills into this repo (re-run after upgrading):

```bash
.venv/bin/python -m transect.skills install
```

## Running

Always start with the **structural** pass — free, no key, no model calls. It lists
every event and the eval setup so you can sanity-check / refine `spec.yaml` before
spending on judges:

```bash
./analyse.py                 # structural; report -> scans/report.html
```

Then a **judged** pass once a provider key is set:

```bash
./analyse.py --judge anthropic/claude-sonnet-4-6
./analyse.py --judge anthropic/claude-sonnet-4-6 --logs ../cve-bench-pi/logs
```

The report lands at `scans/report.html` (open it in a browser). For the deep
links back into the transcript, Transect also starts a local Scout viewer and
prints its URL.

## Workflow

1. Run the overnight CVE batch (`../cve-bench-pi/overnight.sh`) → `.eval` logs in `../cve-bench-pi/logs/`.
2. `./analyse.py` (structural) → read `scans/report.html`, see what pi actually did.
3. Tune the phase descriptions in `spec.yaml` to match.
4. `./analyse.py --judge <model>` → phase-labelled report; compare where judges disagree.

Paper: https://arxiv.org/abs/2610.08364
