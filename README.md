# Inspect + Colab GPU + sandboxed agents — what's here

This folder is a learning setup for the **Inspect** eval framework. The goal:
run evals against a model hosted on a free **Google Colab A100**, and give an
agent a **locked-down container** to work in. Two agent styles are built, plus
the scripts to run the GPU model.

Everything here was built and tested step by step. Where something is **not**
proven, this README says so plainly (see "Tested assumptions" at the end).

---

## The pieces

| Folder | What it does |
|--------|--------------|
| `colab-vllm/` | Start a model on a Colab A100 with vLLM, tunnel it out, and drive it all from your laptop terminal. `RUN.md` has the exact commands. |
| `interogate-image/` | An agent that runs **on your laptop** and pokes a sandbox container with the `bash` tool. Simple and reliable. |
| `sandbox-pi/` | The **pi** coding agent running **inside** the container, reaching the model through Inspect's bridge — with **no internet** in the container. |

`inspect_ai/` is the upstream framework checkout; not our code.

---

## How it fits together

1. **Model** lives on the Colab A100 (vLLM). Your laptop reaches it over a
   Cloudflare tunnel. Inspect talks to it like any other model provider.
2. **Sandbox** is a Docker container that runs **on your laptop** (not on
   Colab). It's where the agent's shell commands actually run.
3. Two ways to connect an agent to the container:
   - **Host-driven** (`interogate-image/`): the agent runs on the laptop and
     sends `bash` commands into the container.
   - **In-container** (`sandbox-pi/`): the agent (pi) runs *inside* the
     container and reaches the model through a small proxy Inspect starts in
     the box.

---

## What gives us defense in depth (the security design)

The idea: even if one control fails, another still contains the agent. Layers,
from outer to inner:

1. **Two-stage Docker build.** A "builder" stage has internet and the download
   tools (git, curl, npm). The **final** image copies in only the *results*, so
   it ships **no fetch tools** — nothing for the agent to download or exfiltrate
   with. *Removing the capability, not just the connection.*
2. **`network_mode: none`.** The container has **no internet** at run time. A
   normal (non-privileged) container **cannot turn its own network back on** —
   that needs host privileges the agent doesn't have. So this is enforced by
   Docker, not by trusting the model. (Verified: `curl` to the internet is
   blocked from inside.)
3. **Control plane vs data plane.** Inspect reads and writes the container using
   `docker exec` — the Docker **daemon on the host**, *not* the container's
   network. That's why cutting the container's internet doesn't stop Inspect
   from driving it.
4. **The model bridge uses that same side channel.** In `sandbox-pi/`, the
   agent talks to a proxy on `127.0.0.1:13131` inside the box; Inspect relays
   those calls to the real model **over the exec channel**, not the internet.
   So the agent can use a powerful model **while still having no internet**.
5. **Least privilege on the container** (host-driven version): drop all Linux
   capabilities, no new privileges, a process cap. (Left off the pi version
   because it broke the injected bridge proxy — see below.)

Rule we keep: **never** `privileged`, **never** mount the Docker socket, and
**never** host networking on a box meant to contain an agent.

---

## Status: what works, what doesn't

**Works and verified:**
- Colab A100 provisioned and vLLM served from the laptop terminal.
- Model fits 40 GB using an **AWQ (int4)** quant (`Qwen/Qwen3-32B-AWQ`).
  (Full-size 27B/32B in fp16 does **not** fit; FP8 is a bad fit on A100 — it
  has no FP8 hardware.)
- Air-gap holds: content is baked in at build, internet is blocked at run time.
- `interogate-image/` (host bash agent) scores 100% on its check.
- `sandbox-pi/`: **fully working, scores 100%.** pi runs inside the air-gapped
  container, reaches the model through the bridge (no internet), makes real tool
  calls (reads the file), and answers correctly.

---

## Tested assumptions (what we checked instead of guessing)

- **"pi respects `OPENAI_BASE_URL`."** *Wrong.* Proven with a mock server: pi
  ignored it for built-in providers. Fix: register a **custom provider** via a
  pi extension (`api: openai-completions`, `baseUrl` → the bridge). Baked into
  `sandbox-pi/Dockerfile.multistage`.
- **"`localhost` is fine."** Risky: Node resolves `localhost` to IPv6 first, so
  we use `127.0.0.1` for the bridge.
- **"The hardened container is fine for the bridge."** *Wrong.* The extra
  lockdown flags broke the injected bridge proxy (pi got "connection error").
  Matched the known-good Inspect example instead (kept `network_mode: none`).
- **"`reasoning: true` will make pi answer."** *Wrong.* Tested; still no tool
  call. That ruled the reasoning flag out and pointed us deeper.
- **"pi/the bridge is dropping the tool call."** *Wrong.* We read both sides:
  the bridge forwards `tools` and streams `tool_calls` back; pi sends 4 tools.
  A **direct** call to vLLM (bypassing pi and the bridge) also returned empty
  with no tool call — so the fault was the **model server**.
- **The real cause: wrong vLLM tool-call parser.** `--tool-call-parser
  qwen3_coder` is for Qwen3-**Coder**; dense **Qwen3-32B needs `hermes`**. Wrong
  parser = the model emits tool calls but vLLM strips them → empty output.
  Switched to `hermes` and **verified with a direct curl** (`finish_reason:
  tool_calls`) before re-running. This is what fixed `sandbox-pi`.
- **"27B fp16 fits a 40 GB A100."** *Wrong* (~54 GB). Switched to AWQ int4.

**Reminder:** the Colab A100 keeps billing until you stop it — run
`colab stop -s vllm` when done.
