"""Runs ON the Colab VM (via `colab exec -s vllm -f status.py`).

Reports vLLM install + boot progress and whether the named tunnel connected.
Re-run every ~30s: first until `vllm installed: True`, then until
`vLLM ready: True`. The public URL is fixed (vllm.<your-domain>, set once in
cve-bench-pi/.env), so there's nothing to scrape here.
"""

import os
import re
import sys
import pathlib
import importlib.util


def tail(p, n=1, width=200):
    t = pathlib.Path(p).read_text() if pathlib.Path(p).exists() else ""
    lines = t.strip().splitlines() or ["(no output yet)"]
    return t, [ln[:width] for ln in lines[-n:]]


installed = importlib.util.find_spec("vllm") is not None
print("kernel python:", sys.executable)
print("vllm installed:", installed)
# Not installed yet: report pip progress and stop. Don't raise SystemExit — in
# the IPython kernel that prints a scary "An exception has occurred" traceback.
if not installed:
    _, last = tail("/content/pip.log", n=3)
    print("pip.log:", *last, sep="\n  ")
    print("-> vllm not installed yet. Run: colab install -s vllm vllm  (then setup_vllm.py if still False)")
else:
    vt, vlast = tail("/content/vllm.log", n=4)
    ct, _ = tail("/content/cf.log")
    # Model being served: the MODEL env (pushed by send_env.sh), else the --model
    # arg vLLM logged, else launch_vllm.py's default.
    served = os.environ.get("MODEL")
    if not served:
        m2 = re.search(r"--model[=\s]+([\w./-]+)", vt)
        served = m2.group(1) if m2 else "(launch_vllm.py default)"
    print("model:", served)
    print("vLLM ready:", "Application startup complete" in vt)
    # Named tunnel: cloudflared logs "Registered tunnel connection" once connected.
    # The hostname is fixed in the dashboard (VLLM_BASE_URL on the laptop).
    print("tunnel connected:", "Registered tunnel connection" in ct)
    print("last %d lines:" % len(vlast), *vlast, sep="\n  ")
