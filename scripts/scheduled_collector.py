#!/usr/bin/env python
# coding=utf-8
"""Simple in-container scheduler for bounded News-Collector runs."""
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
COLLECT_ONCE = os.path.join(SCRIPT_DIR, "collect_once.py")
sys.path.insert(0, SCRIPT_DIR)
from core import parse_parallel  # noqa: E402
TZ_NAME = os.environ.get("TZ", "Asia/Shanghai")
TZ = timezone(timedelta(hours=8), "Asia/Shanghai") if TZ_NAME != "UTC" else timezone.utc


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        print(f"[scheduler] invalid {name}={value!r}; using {default}", file=sys.stderr)
        return default


def parse_times(raw: str) -> list[tuple[int, int]]:
    result = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        try:
            hour_text, minute_text = item.split(":", 1)
            hour, minute = int(hour_text), int(minute_text)
        except ValueError as exc:
            raise ValueError(f"invalid time {item!r}; expected HH:MM") from exc
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"invalid time {item!r}; expected HH:MM")
        result.append((hour, minute))
    if not result:
        raise ValueError("at least one schedule time is required")
    return sorted(set(result))


def next_run_after(now: datetime, times: list[tuple[int, int]]) -> datetime:
    today = now.date()
    for hour, minute in times:
        candidate = datetime(today.year, today.month, today.day, hour, minute, tzinfo=TZ)
        if candidate > now:
            return candidate
    hour, minute = times[0]
    tomorrow = today + timedelta(days=1)
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, minute, tzinfo=TZ)


def run_collection(args: argparse.Namespace) -> int:
    cmd = [sys.executable, COLLECT_ONCE, "--parallel", str(args.parallel)]
    if args.core:
        cmd.append("--core")
    if args.source:
        cmd.extend(["--source", args.source])
    if args.force:
        cmd.append("--force")
    if args.vacuum:
        cmd.append("--vacuum")
    print("[scheduler] starting collection", datetime.now(TZ).isoformat(), flush=True)
    completed = subprocess.run(cmd, cwd=PROJECT_DIR)
    print(f"[scheduler] collection exited {completed.returncode}", flush=True)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run News-Collector at configured daily times.")
    parser.add_argument(
        "--times",
        default=os.environ.get("COLLECT_SCHEDULE", "08:30,12:30,18:30,22:30"),
        help="Comma-separated daily times in HH:MM, local TZ.",
    )
    parser.add_argument("--source", default=os.environ.get("COLLECT_SOURCE", ""), help="Optional source ids.")
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
        help="Collector parallelism.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=os.environ.get("COLLECT_FORCE", "").lower() in {"1", "true", "yes"},
        help="Ignore source_state next_run_at. Not recommended for scheduler.",
    )
    parser.add_argument(
        "--vacuum",
        action="store_true",
        default=os.environ.get("COLLECT_VACUUM", "").lower() in {"1", "true", "yes"},
        help="Run VACUUM after scheduled collection.",
    )
    parser.add_argument("--once", action="store_true", help="Run one scheduled-style pass and exit.")
    args = parser.parse_args()

    times = parse_times(args.times)
    print(
        f"[scheduler] enabled times={args.times} tz={TZ_NAME} parallel={args.parallel} "
        f"core={args.core} source={args.source or '-'} force={args.force}",
        flush=True,
    )
    if args.once:
        return run_collection(args)

    while True:
        now = datetime.now(TZ)
        target = next_run_after(now, times)
        sleep_seconds = max(1, int((target - now).total_seconds()))
        print(f"[scheduler] next run at {target.isoformat()} ({sleep_seconds}s)", flush=True)
        time.sleep(sleep_seconds)
        run_collection(args)


if __name__ == "__main__":
    raise SystemExit(main())
