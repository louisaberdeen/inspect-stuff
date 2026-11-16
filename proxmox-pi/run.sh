#!/usr/bin/env bash
# ./run.sh <hf-dataset-link> <hf-model-link> [extra `inspect eval` args, e.g. --limit 3]
#
# 1. serves the model on the Colab A100 (colab-vllm/), writes its URL into .env
# 2. runs the dataset: known benchmarks via inspect_evals, anything else via
#    task.py (pi inside an offline Proxmox VM)
set -euo pipefail
cd "$(dirname "$0")"
[ $# -ge 2 ] || { sed -n 2,6p "$0"; exit 1; }

# https://huggingface.co/datasets/org/name[/...] -> org/name
DATASET=$(echo "$1" | sed -E 's#^https?://huggingface.co/datasets/##; s#^([^/]+/[^/]+).*#\1#')
MODEL=$(echo "$2" | sed -E 's#^https?://huggingface.co/##; s#^([^/]+/[^/]+).*#\1#')
shift 2
SESSION=vllm
[ -f .env ] || cp .env.example .env
set -a; source .env; set +a   # VLLM_BASE_URL (fixed), CF_TUNNEL_TOKEN, HF_TOKEN

# ---- 1. model on Colab ----
if ! colab sessions 2>/dev/null | grep -qw "$SESSION"; then
  colab new -s "$SESSION" --gpu A100
  REQUEST_TIMEOUT=1800 colab install -s "$SESSION" vllm
fi
# One file = prelude (forward env) + launch_vllm.py, so it doesn't rely on
# kernel state surviving between exec calls. launch_vllm.py kills any stale
# server/tunnel itself, so no pkill here.
LAUNCH=$(mktemp --suffix=.py)
{
  echo "import os"
  echo "os.environ['MODEL'] = '$MODEL'"
  [ -n "${HF_TOKEN:-}" ] && echo "os.environ['HF_TOKEN'] = '$HF_TOKEN'"
  [ -n "${TOOL_PARSER:-}" ] && echo "os.environ['TOOL_PARSER'] = '$TOOL_PARSER'"
  echo "os.environ['CF_TUNNEL_TOKEN'] = '${CF_TUNNEL_TOKEN:?set CF_TUNNEL_TOKEN in proxmox-pi/.env}'"
  cat ../colab-vllm/launch_vllm.py
} > "$LAUNCH"
REQUEST_TIMEOUT=400 colab exec -s "$SESSION" -f "$LAUNCH" --timeout 400
rm -f "$LAUNCH"

echo "waiting for vLLM to load $MODEL (first boot downloads the weights)..."
for _ in $(seq 60); do
  STATUS=$(colab exec -s "$SESSION" -f ../colab-vllm/status.py 2>/dev/null || true)
  echo "$STATUS" | grep -q "vLLM ready: True" && break
  echo "$STATUS" | grep "^last:" || true
  sleep 30
done
# Named tunnel -> fixed VLLM_BASE_URL (already in .env), nothing to scrape/rewrite.
echo "$STATUS" | grep -q "vLLM ready: True" \
  || { echo "vLLM not ready after 30 min — check: colab exec -s $SESSION -f ../colab-vllm/status.py"; exit 1; }
echo "model up at $VLLM_BASE_URL"

# ---- 2. eval ----
# Benchmarks with their own tools/grader run through their inspect_evals task.
# Their LLM judge defaults to gpt-4o; JUDGE overrides it (default: the served model).
JUDGE=${JUDGE:-vllm/$MODEL}
case "$DATASET" in
  ai-safety-institute/AgentHarm)
    inspect eval inspect_evals/agentharm --model "vllm/$MODEL" \
      -T refusal_judge="$JUDGE" -T semantic_judge="$JUDGE" "$@" ;;
  *)
    inspect eval task.py -T dataset="$DATASET" --model "vllm/$MODEL" --max-samples 1 "$@" ;;
esac

echo
echo "Done. The A100 bills until stopped:  colab stop -s $SESSION"
