#!/usr/bin/env python
# coding=utf-8
"""Run one collector pass with repo defaults for manual or scheduled jobs."""
import argparse
import os
import subprocess
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
COLLECTOR = os.path.join(PROJECT_DIR, "multi_source_news.py")
sys.path.insert(0, SCRIPT_DIR)
from core import parse_parallel  # noqa: E402


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        print(f"[collect_once] invalid {name}={value!r}; using {default}", file=sys.stderr)
        return default


def build_command(args: argparse.Namespace) -> list[str]:
    cmd = [sys.executable, COLLECTOR, "--parallel", str(args.parallel), "--prune"]
    if args.core:
        cmd.append("--core")
    if args.source:
        cmd.extend(["--source", args.source])
    if args.force:
        cmd.append("--force")
    if args.vacuum:
        cmd.append("--vacuum")
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one News-Collector pass.")
    parser.add_argument(
        "--source",
        default=os.environ.get("COLLECT_SOURCE", ""),
        help="Comma-separated source ids. Overrides --core.",
    )
    parser.add_argument(
        "--core",
        action="store_true",
        default=os.environ.get("COLLECT_CORE", "").lower() in {"1", "true", "yes"},
        help="Collect core sources only.",
    )
    parser.add_argument(
        "--parallel",
        type=parse_parallel,
        default=parse_parallel(os.environ.get("COLLECT_PARALLEL", "8")),
        help="Collector parallelism. Defaults to COLLECT_PARALLEL or 8.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=os.environ.get("COLLECT_FORCE", "").lower() in {"1", "true", "yes"},
        help="Ignore source_state next_run_at. Use for explicit manual refreshes.",
    )
    parser.add_argument(
        "--vacuum",
        action="store_true",
        default=os.environ.get("COLLECT_VACUUM", "").lower() in {"1", "true", "yes"},
        help="Run VACUUM after collection.",
    )
    args = parser.parse_args()

    cmd = build_command(args)
    print("[collect_once] " + " ".join(cmd), flush=True)
    completed = subprocess.run(cmd, cwd=PROJECT_DIR)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
