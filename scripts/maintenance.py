#!/usr/bin/env python
# coding=utf-8
"""Run News-Collector retention cleanup without collecting news."""
import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
for path in (SCRIPT_DIR, PROJECT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from store import RETENTION_DAYS, init_db, prune, vacuum  # noqa: E402

TZ_NAME = os.environ.get("TZ", "Asia/Shanghai")
TZ = timezone(timedelta(hours=8), "Asia/Shanghai") if TZ_NAME != "UTC" else timezone.utc


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        print(f"[maintenance] invalid {name}={value!r}; using {default}", file=sys.stderr)
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
        raise ValueError("at least one maintenance time is required")
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


def run_maintenance(days: int, do_vacuum: bool) -> int:
    init_db()
    result = prune(days=days)
    print(
        f"[maintenance] retention={days}d removed={result['removed']} "
        f"kept_old={result['kept_old']}",
        flush=True,
    )
    if do_vacuum:
        vacuum()
        print("[maintenance] vacuum=done", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune old runtime data and optionally VACUUM SQLite.")
    parser.add_argument(
        "--days",
        type=int,
        default=_env_int("RETENTION_DAYS", RETENTION_DAYS),
        help="Retention window for news/log/fingerprint data.",
    )
    parser.add_argument(
        "--vacuum",
        action="store_true",
        default=os.environ.get("MAINTENANCE_VACUUM", "1").lower() not in {"0", "false", "no"},
        help="Run VACUUM after prune. Enabled by default.",
    )
    parser.add_argument(
        "--schedule",
        default=os.environ.get("MAINTENANCE_SCHEDULE", "03:30"),
        help="Comma-separated daily maintenance times in HH:MM.",
    )
    parser.add_argument("--loop", action="store_true", help="Run maintenance on a daily schedule.")
    args = parser.parse_args()

    if not args.loop:
        return run_maintenance(args.days, args.vacuum)

    times = parse_times(args.schedule)
    print(
        f"[maintenance] schedule={args.schedule} tz={TZ_NAME} retention={args.days}d "
        f"vacuum={args.vacuum}",
        flush=True,
    )
    while True:
        now = datetime.now(TZ)
        target = next_run_after(now, times)
        sleep_seconds = max(1, int((target - now).total_seconds()))
        print(f"[maintenance] next run at {target.isoformat()} ({sleep_seconds}s)", flush=True)
        time.sleep(sleep_seconds)
        run_maintenance(args.days, args.vacuum)


if __name__ == "__main__":
    raise SystemExit(main())
