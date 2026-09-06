# Colab A100 + vLLM → Inspect — run order

All commands run from YOUR laptop terminal. The `colab` CLI drives a remote VM.

## One-time setup
```bash
uv tool install google-colab-cli
pip install inspect-ai openai

# Auth (opens a browser once) — the 4 scopes are required
gcloud auth application-default login \
  --scopes=openid,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/colaboratory

colab whoami   # verify

# If colab crashes with: AttributeError ... 'jupyter_kernel_client' has no attribute 'KernelClient'
uv tool install --force google-colab-cli --with "jupyter-kernel-client==0.15.0"
```

## Start the VM + vLLM (keep this session alive while you eval)
```bash
colab new -s vllm --gpu A100
REQUEST_TIMEOUT=1800 colab install -s vllm vllm        # multi-GB; needs the long timeout

REQUEST_TIMEOUT=400  colab exec -s vllm -f launch_vllm.py

# poll until "vLLM ready: True" (first boot downloads ~15GB weights, 1-3 min)
colab exec -s vllm -f status.py
```
Copy the `URL:` it prints (e.g. `https://xxxx.trycloudflare.com/v1`).

## Interface it into Inspect
Put these in your Inspect project's `.env` (URL from status.py, key from launch_vllm.py):
```
VLLM_BASE_URL=https://xxxx.trycloudflare.com/v1
VLLM_API_KEY=my-secret-token
INSPECT_EVAL_MODEL=vllm/Qwen/Qwen2.5-7B-Instruct
```
Sanity check, then run any eval:
```bash
curl $VLLM_BASE_URL/models -H "Authorization: Bearer my-secret-token"
inspect eval your_task.py --model vllm/Qwen/Qwen2.5-7B-Instruct --max-connections 16
```
The model name after `vllm/` must match MODEL in launch_vllm.py exactly.

## When done (IMPORTANT — the A100 bills until you stop it)
```bash
colab stop -s vllm
```
The tunnel URL dies with the session; on next start, re-run launch_vllm.py and
update VLLM_BASE_URL.

## Handy
```bash
colab sessions            # list live VMs
colab status -s vllm      # hardware + IDLE/BUSY
colab exec -s vllm -f status.py   # re-check the server / get the URL again
```
