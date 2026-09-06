"""Runs ON the Colab VM (via `colab exec -s vllm -f status.py`).

Reports whether vLLM has finished booting and prints the public tunnel URL.
Re-run every ~30s after launch until it says `vLLM ready: True`.
"""

import re
import pathlib

vt = pathlib.Path("/content/vllm.log").read_text() if pathlib.Path("/content/vllm.log").exists() else ""
ct = pathlib.Path("/content/cf.log").read_text() if pathlib.Path("/content/cf.log").exists() else ""

print("vLLM ready:", "Application startup complete" in vt)
m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", ct)
print("URL:", (m.group(0) + "/v1") if m else "(tunnel not up yet)")
print("last:", (vt.strip().splitlines() or ["(no output yet)"])[-1][:200])  # progress / errors
