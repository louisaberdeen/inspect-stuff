"""Runs ON the Colab VM (colab exec -s vllm -f diag.py). Locates vLLM / python."""
import sys, subprocess, glob, importlib.util

print("kernel python:", sys.executable, sys.version.split()[0])
print("vllm importable here:", importlib.util.find_spec("vllm") is not None)

# pip view of vllm in the kernel interpreter
r = subprocess.run([sys.executable, "-m", "pip", "show", "vllm"],
                   capture_output=True, text=True)
print("pip show vllm (kernel):", (r.stdout or r.stderr).strip().splitlines()[:3])

# which other pythons on the box have vllm installed
print("--- other interpreters ---")
for py in sorted(set(glob.glob("/usr/bin/python3*") + glob.glob("/usr/local/bin/python3*"))):
    try:
        out = subprocess.run([py, "-c", "import vllm,sys;print(vllm.__version__)"],
                             capture_output=True, text=True, timeout=30)
        print(py, "->", (out.stdout.strip() or out.stderr.strip().splitlines()[-1:]))
    except Exception as e:
        print(py, "-> err", e)
