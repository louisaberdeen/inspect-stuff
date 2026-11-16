"""Runs ON the Colab VM (colab exec -s vllm -f setup_vllm.py).

Installs vLLM into the KERNEL interpreter (sys.executable), backgrounded — the
download is multi-GB and would blow the exec timeout. Poll with status.py:
it tails /content/pip.log and reports when vllm becomes importable.

`colab install vllm` put nothing on the kernel's path (Python 3.13); this does
it with the same python that launch_vllm.py will use, and logs the real error
if there's no wheel for this Python version.
"""
import sys
import subprocess

subprocess.Popen(
    [sys.executable, "-m", "pip", "install", "vllm"],
    stdout=open("/content/pip.log", "w"), stderr=subprocess.STDOUT,
)
print(f"installing vllm into {sys.executable} -> /content/pip.log; poll with status.py")
