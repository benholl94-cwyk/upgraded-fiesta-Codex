#!/usr/bin/env python3
"""Foreground loop runtime for the mobile a-Shell control plane."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "settings" / "mobile-production" / "loops.json"
DEV_ROOT = Path.home() / "Documents" / "Developer"
RUN_DIR = DEV_ROOT / "runs"
LOG_DIR = DEV_ROOT / "logs"
STATE_PATH = RUN_DIR / "mobile-loop-state.json"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dirs() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def append_log(payload: dict[str, Any]) -> None:
    ensure_dirs()
    path = LOG_DIR / f"mobile-loop-{dt.datetime.now().strftime('%Y%m%d')}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts_utc": utc_now(), **payload}, ensure_ascii=False, sort_keys=True) + "\n")


def write_state(payload: dict[str, Any]) -> None:
    ensure_dirs()
    STATE_PATH.write_text(json.dumps({"ts_utc": utc_now(), **payload}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def run_step(command: list[str], timeout: int = 300) -> dict[str, Any]:
    try:
        done = subprocess.run([str(part) for part in command], cwd=str(ROOT), text=True, capture_output=True, check=False, timeout=timeout)
        return {
            "command": command,
            "returncode": done.returncode,
            "stdout_tail": done.stdout.strip()[-1200:],
            "stderr_tail": done.stderr.strip()[-1200:],
        }
    except Exception as exc:
        return {"command": command, "returncode": 127, "stdout_tail": "", "stderr_tail": repr(exc)}


def enabled_loops(config: dict[str, Any], ids: list[str] | None = None) -> list[dict[str, Any]]:
    loops = config.get("loops", [])
    if ids:
        wanted = set(ids)
        return [loop for loop in loops if loop.get("id") in wanted]
    return [loop for loop in loops if loop.get("enabled_by_default")]


def cycle(ids: list[str] | None = None) -> dict[str, Any]:
    config = load_config()
    results = []
    ok = True
    for loop in enabled_loops(config, ids):
        result = run_step(loop["command"])
        result["id"] = loop.get("id")
        results.append(result)
        append_log({"kind": "step", "id": loop.get("id"), "returncode": result["returncode"]})
        if result["returncode"] != 0:
            ok = False
    payload = {"ok": ok, "results": results}
    write_state(payload)
    return payload


def once(ids: list[str] | None = None) -> int:
    payload = cycle(ids)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


def loop(interval: int, ids: list[str] | None = None) -> int:
    minimum = int(load_config().get("minimum_interval_seconds", 15))
    interval = max(interval, minimum)
    print(f"mobile foreground loop: start interval={interval}")
    try:
        while True:
            payload = cycle(ids)
            print(f"{utc_now()} ok={payload['ok']} steps={len(payload['results'])}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("mobile foreground loop: stop")
        return 0


def status() -> int:
    if STATE_PATH.exists():
        print(STATE_PATH.read_text(encoding="utf-8"))
    else:
        print(json.dumps({"ok": False, "detail": "no loop state yet"}, indent=2))
    return 0


def self_test() -> int:
    config = load_config()
    assert config.get("schema_version")
    assert config.get("loops")
    write_state({"self_test": True, "loop_count": len(config.get("loops", []))})
    print("ashell loop runtime self-test ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Foreground loop runtime for a-Shell.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    once_parser = sub.add_parser("once")
    once_parser.add_argument("ids", nargs="*")
    loop_parser = sub.add_parser("loop")
    loop_parser.add_argument("--interval", type=int, default=60)
    loop_parser.add_argument("ids", nargs="*")
    sub.add_parser("status")
    args = parser.parse_args(argv)
    if args.command == "self-test":
        return self_test()
    if args.command == "once":
        return once(args.ids or None)
    if args.command == "loop":
        return loop(args.interval, args.ids or None)
    if args.command == "status":
        return status()
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
