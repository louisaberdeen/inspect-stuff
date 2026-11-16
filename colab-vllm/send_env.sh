#!/usr/bin/env bash
# Push secrets from colab-vllm/.env into the PERSISTENT Colab kernel's env, so
# a later `colab exec -f launch_vllm.py` inherits them (colab exec does NOT
# forward your laptop env). The kernel is one process that persists between
# exec calls, so os.environ set here survives to the launch.
#
# Usage: ./send_env.sh        (run before launch_vllm.py)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
[ -f .env ] || { echo "no colab-vllm/.env"; exit 1; }

tmp=$(mktemp /tmp/colab_env.XXXXXX.py)
trap 'rm -f "$tmp"' EXIT
{
  echo "import os"
  # Forward only known keys with a real value. Single-quote the value for
  # Python; HF tokens / model names never contain a single quote.
  # ponytail: assumes no "'" in values — true for tokens and model ids.
  grep -E '^(HF_TOKEN|MODEL|CF_TUNNEL_TOKEN)=.+' .env | while IFS='=' read -r k v; do
    printf "os.environ['%s'] = '%s'\n" "$k" "$v"
  done
  # Mirror HF_TOKEN to the other name huggingface_hub may read, so vLLM's
  # downloads are authenticated regardless of its hub version.
  echo 'if os.environ.get("HF_TOKEN"): os.environ["HUGGING_FACE_HUB_TOKEN"] = os.environ["HF_TOKEN"]'
  echo 'print("kernel env set:", [k for k in ("HF_TOKEN","HUGGING_FACE_HUB_TOKEN","MODEL","CF_TUNNEL_TOKEN") if os.environ.get(k)])'
} > "$tmp"

# `colab` lives in the repo .venv (snap-proof), usually not on PATH; resolve it.
COLAB="$(command -v colab || echo "$(dirname "$0")/../.venv/bin/colab")"
# MUST set REQUEST_TIMEOUT — without it `colab exec` can hang indefinitely.
REQUEST_TIMEOUT="${REQUEST_TIMEOUT:-120}" "$COLAB" exec -s vllm -f "$tmp"
