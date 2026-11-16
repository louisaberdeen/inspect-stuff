"""Runs ON the Colab VM (colab exec -s vllm -f tail.py). Prints the tail of the
vLLM server log — live request/throughput lines. Watch it:
    watch -n5 ./.venv/bin/colab exec -s vllm -f colab-vllm/tail.py
"""
print(open("/content/vllm.log").read()[-4000:] if __import__("os").path.exists("/content/vllm.log") else "(no vllm.log yet)")
