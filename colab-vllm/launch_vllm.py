"""Runs ON the Colab VM (sent there via `colab exec -s vllm -f launch_vllm.py`).

Fixes the CUDA stack, then starts vLLM + a cloudflared tunnel as BACKGROUND
processes and returns immediately (so it never hits the CLI's 30s timeout).
They keep running because the colab kernel persists between exec calls.
Poll readiness afterwards with status.py.
"""

import os
import sys
import time
import subprocess
import pathlib
import urllib.request

# 4-bit int4 (~15-16GB) fits a 40GB A100; vLLM auto-detects the quant from repo.
# NOT FP8/NVFP4 — the A100 has no FP8 tensor cores and NVFP4 is Blackwell-only.
# For Qwen3.8-27B use RedHatAI/Qwen3.8-27B-INT4 (W4A16, compressed-tensors).
# Override via MODEL (send_env.sh forwards it, or proxmox-pi/run.sh sets it).
MODEL = os.environ.get("MODEL", "RedHatAI/Qwen3.8-27B-INT4")
KEY = "my-secret-token"              # reuse this as VLLM_API_KEY on the laptop
# For gated weights set HF_TOKEN (run.sh passes it through from your laptop env).

# Context window. 8192 is too small for a reasoning model on a multi-step agent
# task (it hits max_tokens mid-tool-call and emits garbage). 32k fits a 4-bit
# 27B's KV cache on a 40GB A100 at batch 1. Must match the bridge provider's
# contextWindow in cve-bench-pi/Dockerfile.
MAX_MODEL_LEN = os.environ.get("MAX_MODEL_LEN", "32768")

# Tool-call parsers are model-specific. hermes is right for Qwen2.5 and DENSE Qwen3
# (qwen3_coder is only for Qwen3-Coder). A wrong parser means the model emits tool
# calls but vLLM strips them (empty output). Override with TOOL_PARSER.
m = MODEL.lower()
PARSER = os.environ.get("TOOL_PARSER") or (
    "llama3_json" if "llama" in m else "mistral" if "mistral" in m else "hermes"
)
SERVE_ARGS = [
    "--tensor-parallel-size", "1",
    "--enable-auto-tool-choice",
    "--tool-call-parser", PARSER,
    # Agent loops re-send a growing transcript every turn; prefix caching reuses
    # the KV for the shared prefix instead of re-prefilling it, so late turns
    # don't crawl. Also shares the system prompt across concurrent agents.
    "--enable-prefix-caching",
    *(["--reasoning-parser", "qwen3"] if "qwen3" in m else []),
]

# 1. Resolve the Colab CUDA-version clash.
#    Installing vLLM upgrades torch (e.g. cu130) but Colab's torchaudio/torchvision
#    are an older CUDA -> import crash. Drop torchaudio (a text model never needs it;
#    transformers skips it when absent) and install the matching torchvision
#    (vLLM's engine DOES need torchvision). Change cu130 to match your torch:
#    python -c "import torch;print(torch.version.cuda)"
torch_ver = subprocess.run(
    ["python", "-c", "import torch;print(torch.__version__.split('+')[0])"],
    capture_output=True, text=True,
).stdout.strip()
subprocess.run(["pip", "uninstall", "-y", "torchaudio"])
subprocess.run(
    ["pip", "install", f"torch=={torch_ver}", "torchvision",
     "--index-url", "https://download.pytorch.org/whl/cu130"]
)

# 1b. Fast weight download. huggingface_hub v1+ downloads via the hf-xet backend
#     by default and IGNORES the old HF_HUB_ENABLE_HF_TRANSFER flag (the
#     hf_transfer package was removed). HF_XET_HIGH_PERFORMANCE=1 is the
#     replacement: it tells hf-xet to saturate the link + all CPU cores, so the
#     ~15 GB weights land fast and it rides out HF throttling. The vLLM Popen
#     below inherits os.environ. (Set HF_HUB_DISABLE_XET=1 to opt out if a link
#     is flaky.)
os.environ["HF_XET_HIGH_PERFORMANCE"] = "1"

# 2. Kill any vLLM/tunnel left running from a previous launch, else the new
#    server can't bind port 8000 ("Address already in use"). pkill returns
#    nonzero when nothing matches — that's fine.
subprocess.run(["pkill", "-f", "vllm.entrypoints.openai.api_server"])
subprocess.run(["pkill", "-f", "cloudflared"])
time.sleep(3)

# 3. vLLM OpenAI-compatible server, backgrounded.
#    Run via `python -m` (the kernel's interpreter) not the bare `vllm` script:
#    pip installs the console script somewhere not on the exec kernel's PATH, so
#    `Popen(["vllm", ...])` fails with FileNotFoundError.
subprocess.Popen(
    [sys.executable, "-m", "vllm.entrypoints.openai.api_server",
     "--model", MODEL, "--host", "0.0.0.0", "--port", "8000",
     "--api-key", KEY, "--max-model-len", MAX_MODEL_LEN, *SERVE_ARGS],
    stdout=open("/content/vllm.log", "w"), stderr=subprocess.STDOUT,
)

# 4. cloudflared NAMED tunnel, backgrounded. Unlike a quick tunnel (random
#    *.trycloudflare.com each launch), a named tunnel always serves the fixed
#    hostname you mapped in the Cloudflare dashboard -> localhost:8000, so
#    VLLM_BASE_URL never changes across VM restarts. The token is self-contained
#    (account+tunnel+secret), so no `cloudflared login`/cert on a blank VM.
#    CF_TUNNEL_TOKEN is pushed into the kernel env by send_env.sh.
CF_TUNNEL_TOKEN = os.environ["CF_TUNNEL_TOKEN"]
cf = "/content/cloudflared"
if not pathlib.Path(cf).exists():
    urllib.request.urlretrieve(
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
        cf,
    )
    os.chmod(cf, 0o755)
subprocess.Popen(
    [cf, "tunnel", "run", "--token", CF_TUNNEL_TOKEN],
    stdout=open("/content/cf.log", "w"), stderr=subprocess.STDOUT,
)

print("launched vLLM + tunnel; now poll with status.py")
