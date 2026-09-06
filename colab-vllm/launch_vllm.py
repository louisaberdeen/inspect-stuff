"""Runs ON the Colab VM (sent there via `colab exec -s vllm -f launch_vllm.py`).

Fixes the CUDA stack, then starts vLLM + a cloudflared tunnel as BACKGROUND
processes and returns immediately (so it never hits the CLI's 30s timeout).
They keep running because the colab kernel persists between exec calls.
Poll readiness afterwards with status.py.
"""

import os
import subprocess
import pathlib
import urllib.request

# AWQ int4 (~16GB) fits a 40GB A100; vLLM auto-detects the quant from the repo.
# NOT FP8 — the A100 has no FP8 tensor cores (falls back/errors). Swap to
# QuantTrio/Qwen3.6-27B-AWQ for the smaller 27B.
MODEL = "Qwen/Qwen3-32B-AWQ"
KEY = "my-secret-token"              # reuse this as VLLM_API_KEY on the laptop
# For gated weights: os.environ["HF_TOKEN"] = "hf_..."

# Model-specific serve flags (edit these per model; parsers are model-specific).
SERVE_ARGS = [
    "--tensor-parallel-size", "1",
    "--enable-auto-tool-choice",
    # hermes is the parser for DENSE Qwen3 (qwen3_coder is only for Qwen3-Coder).
    # Wrong parser -> the model emits tool calls but vLLM strips them (empty output).
    "--tool-call-parser", "hermes",
    "--reasoning-parser", "qwen3",
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

# 2. vLLM OpenAI-compatible server, backgrounded.
subprocess.Popen(
    ["vllm", "serve", MODEL, "--host", "0.0.0.0", "--port", "8000",
     "--api-key", KEY, "--max-model-len", "8192", *SERVE_ARGS],
    stdout=open("/content/vllm.log", "w"), stderr=subprocess.STDOUT,
)

# 3. cloudflared quick tunnel (no signup), backgrounded.
cf = "/content/cloudflared"
if not pathlib.Path(cf).exists():
    urllib.request.urlretrieve(
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
        cf,
    )
    os.chmod(cf, 0o755)
subprocess.Popen(
    [cf, "tunnel", "--url", "http://localhost:8000"],
    stdout=open("/content/cf.log", "w"), stderr=subprocess.STDOUT,
)

print("launched vLLM + tunnel; now poll with status.py")
