# Colab A100 + vLLM — launch the model

Serves an open model on a Colab A100 (vLLM + cloudflared tunnel) for Inspect to
reach via `VLLM_BASE_URL`. All commands run from YOUR laptop; the `colab` CLI
drives the remote VM. For the full benchmark pipeline see
`../cve-bench-pi/README.md`.

## Files here

| File | Role |
|------|------|
| `launch_vllm.py` | Runs on the VM: fixes the CUDA stack, kills stale servers, starts vLLM + a cloudflared tunnel (backgrounded). Serves `MODEL` (default `RedHatAI/Qwen3.8-27B-INT4`). |
| `status.py` | Runs on the VM: reports vLLM install/boot state + the tunnel URL. |
| `setup_vllm.py` | Runs on the VM: installs vLLM into the kernel interpreter (if `colab install` didn't). |
| `diag.py` | Runs on the VM: shows which python has vLLM. |
| `send_env.sh` | Laptop: pushes `MODEL` / `HF_TOKEN` / `CF_TUNNEL_TOKEN` from `.env` into the persistent Colab kernel (colab exec doesn't forward env). |
| `.env` | `HF_TOKEN` (gated weights) + `CF_TUNNEL_TOKEN` (named tunnel) + optional `MODEL` (gitignored). |

## One-time setup

### Cloudflare named tunnel (stable endpoint, done once)

Gives a fixed public hostname so the endpoint address survives every VM restart
(a quick tunnel would hand out a random `*.trycloudflare.com` each launch). In
the [Zero Trust dashboard](https://one.dash.cloudflare.com) → Networks → Tunnels
→ Create a tunnel → **Cloudflared**, name it `vllm`, copy the `--token eyJ…`
string into `colab-vllm/.env` as `CF_TUNNEL_TOKEN`, then under **Public Hostname**
add `vllm.<your-domain>` → service `http://localhost:8000`. Set
`VLLM_BASE_URL=https://vllm.<your-domain>/v1` once in `../cve-bench-pi/.env` — it
never changes again. The token is self-contained, so it works on a blank VM.

### Tooling

```bash
uv tool install google-colab-cli
gcloud auth application-default login \
  --scopes=openid,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/colaboratory
colab whoami
# If colab crashes with: AttributeError ... 'jupyter_kernel_client' has no attribute 'KernelClient'
uv tool install --force google-colab-cli --with "jupyter-kernel-client==0.15.0"
```

## Start the VM + vLLM

```bash
colab new -s vllm --gpu A100
REQUEST_TIMEOUT=1800 colab install -s vllm vllm     # multi-GB; needs the long timeout

colab exec -s vllm -f diag.py                       # confirm "vllm importable here: True"
# if not importable (Colab is on Python 3.13 — wheel may be missing):
colab exec -s vllm -f setup_vllm.py                 # installs into the kernel python; poll status.py

./send_env.sh                                       # push MODEL + HF_TOKEN + CF_TUNNEL_TOKEN to the kernel
REQUEST_TIMEOUT=400 colab exec -s vllm -f launch_vllm.py
colab exec -s vllm -f status.py                     # poll until "vLLM ready: True"
```

The endpoint is the fixed `https://vllm.<your-domain>/v1` you set once in
`../cve-bench-pi/.env` — nothing to copy each launch. Key = `my-secret-token`
(set in `launch_vllm.py`). First boot downloads the weights (~15 GB): fast
because `launch_vllm.py` sets `HF_XET_HIGH_PERFORMANCE=1` (the hf-xet backend
saturates the link and rides out HF throttling). `status.py` reports
`tunnel connected: True` once cloudflared registers.

## Choosing the model

Set `MODEL` in `.env` (pushed by `send_env.sh`) — no code edit needed — and pass
the matching `vllm/<MODEL>` to `cve-bench-pi/run.sh`. Default is
`RedHatAI/Qwen3.8-27B-INT4` (4-bit, fits a 40 GB A100). The tool-call parser is
auto-picked (`hermes` for Qwen); override with `TOOL_PARSER` for other families.

## When done (IMPORTANT — the A100 bills until you stop it)

```bash
colab stop -s vllm
```

The VM dies with the session, but the hostname is fixed: on next start just
re-run `send_env.sh` + `launch_vllm.py` — `VLLM_BASE_URL` stays as-is.

## Handy

```bash
colab sessions                      # list live VMs
colab status -s vllm                # hardware + IDLE/BUSY
colab exec -s vllm -f status.py     # re-check the server / get the URL again
```

## Known fixes (baked into the scripts)

- **`vllm` not on PATH** → `launch_vllm.py` runs it as `python -m vllm.entrypoints.openai.api_server`.
- **`Address already in use`** → `launch_vllm.py` kills stale vLLM/cloudflared before starting.
- **CUDA version clash** (Colab torchaudio/torchvision vs vLLM's torch) → `launch_vllm.py` drops torchaudio and reinstalls a matching torchvision.
- **`CF_TUNNEL_TOKEN` KeyError in `launch_vllm.py`** → the token wasn't pushed to the kernel; run `./send_env.sh` before `launch_vllm.py`.
- **`tunnel connected: False` stays** → bad/revoked token, or the dashboard Public Hostname isn't mapped to `http://localhost:8000`; check `/content/cf.log` on the VM.
- **Weight download errors mid-way / hf-xet issues** → a very flaky link can trip it; set `HF_HUB_DISABLE_XET=1` (or drop `HF_XET_HIGH_PERFORMANCE` in `launch_vllm.py`) to fall back to the normal downloader.
