#!/usr/bin/env python3
"""Analyse CVE-Bench pi traces with Transect. Structural (free) by default.

  ./analyse.py                                  # newest log, structural pass
  ./analyse.py --judge anthropic/claude-sonnet-4-6
  ./analyse.py ../cve-bench-pi/logs/foo.eval --sample CVE-2024-37388-one_day
"""
import os
import sys

# Re-exec under this dir's venv (which has transect) if we're not already there,
# so `./analyse.py` works regardless of the interpreter it was launched with.
_VENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "python")
if os.path.abspath(sys.executable) != os.path.abspath(_VENV) and os.path.exists(_VENV):
    os.execv(_VENV, [_VENV, os.path.abspath(__file__), *sys.argv[1:]])

import argparse
import glob
from transect import transect

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOGS = os.path.join(HERE, "..", "cve-bench-pi", "logs")


def newest_eval(path: str) -> str:
    if os.path.isfile(path):
        return path
    evals = sorted(glob.glob(os.path.join(path, "*.eval")), key=os.path.getmtime)
    if not evals:
        sys.exit(f"no .eval logs found in {path}")
    return evals[-1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="?", default=DEFAULT_LOGS,
                    help="an .eval file, or a dir (its newest .eval is used). Default: ../cve-bench-pi/logs")
    ap.add_argument("--judge", default=None,
                    help="judge model (e.g. anthropic/claude-sonnet-4-6). Omit for the free structural pass.")
    ap.add_argument("--sample", default=None,
                    help="sample id — required when the log holds several (transect scans one per run).")
    ap.add_argument("--spec", default=os.path.join(HERE, "spec.yaml"))
    ap.add_argument("--no-open", action="store_true",
                    help="don't start the Scout viewer / open a browser (headless).")
    args = ap.parse_args()

    log = newest_eval(args.logs)
    print(f"transect: log={log}  judge={args.judge or '(structural only, $0)'}  sample={args.sample or '(auto)'}")
    transect(
        log, args.spec,
        judge_models=args.judge,
        sample=args.sample,
        viewer=not args.no_open,
        open_report=not args.no_open,
    )


if __name__ == "__main__":
    main()
