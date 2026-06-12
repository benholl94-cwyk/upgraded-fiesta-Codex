#!/usr/bin/env python3
"""Deterministic maintenance engine for the a-Shell mobile ecosystem."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEV_ROOT = Path.home() / "Documents" / "Developer"
RUN_DIR = DEV_ROOT / "runs"
LOG_DIR = DEV_ROOT / "logs"
EXPORT_DIR = DEV_ROOT / "exports"
BACKUP_DIR = DEV_ROOT / "backups"
STATE_PATH = RUN_DIR / "mobile-maintenance-state.json"
FLOWS_PATH = ROOT / "settings" / "mobile-production" / "flows.json"
ENV_PATH = ROOT / "settings" / "mobile-production" / "environment.json"
RULES_PATH = ROOT / "settings" / "mobile-production" / "autofix.rules.json"
REQUIRED_DIRS = [RUN_DIR, LOG_DIR, EXPORT_DIR, BACKUP_DIR]
REQUIRED_FILES = [
    "index.html",
    "styles.css",
    "app.js",
    "manifest.webmanifest",
    "service-worker.js",
    "README.md",
    "AGENTS.md",
    "settings/mobile-production/environment.json",
    "settings/mobile-production/flows.json",
    "settings/mobile-production/autofix.rules.json"
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dirs() -> None:
    for directory in REQUIRED_DIRS:
        directory.mkdir(parents=True, exist_ok=True)


def write_state(payload: dict[str, Any]) -> None:
    ensure_dirs()
    STATE_PATH.write_text(json.dumps({"ts_utc": utc_now(), **payload}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def check_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        return {"id": label, "ok": False, "detail": "missing"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"id": label, "ok": False, "detail": repr(exc)}
    return {"id": label, "ok": bool(data.get("schema_version")), "detail": "loaded"}


def check_required_files() -> dict[str, Any]:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    empty = [path for path in REQUIRED_FILES if (ROOT / path).is_file() and (ROOT / path).stat().st_size == 0]
    return {"id": "required-files", "ok": not missing and not empty, "detail": {"missing": missing, "empty": empty}}


def check_flows() -> dict[str, Any]:
    try:
        data = json.loads(FLOWS_PATH.read_text(encoding="utf-8"))
        ids = [flow.get("id") for flow in data.get("flows", [])]
        ok = bool(ids) and len(ids) == len(set(ids))
        for flow in data.get("flows", []):
            ok = ok and bool(flow.get("steps"))
            for step in flow.get("steps", []):
                ok = ok and isinstance(step.get("command"), list) and bool(step.get("command"))
        return {"id": "flows", "ok": ok, "detail": {"count": len(ids)}}
    except Exception as exc:
        return {"id": "flows", "ok": False, "detail": repr(exc)}


def check_environment() -> dict[str, Any]:
    try:
        data = json.loads(ENV_PATH.read_text(encoding="utf-8"))
        ids = [item.get("id") for item in data.get("components", [])]
        ok = bool(ids) and len(ids) == len(set(ids))
        for item in data.get("components", []):
            ok = ok and isinstance(item.get("command"), list) and bool(item.get("command"))
        return {"id": "environment", "ok": ok, "detail": {"count": len(ids)}}
    except Exception as exc:
        return {"id": "environment", "ok": False, "detail": repr(exc)}


def plan(apply: bool = False) -> dict[str, Any]:
    before_missing_dirs = [str(path) for path in REQUIRED_DIRS if not path.exists()]
    if apply:
        ensure_dirs()
    checks = [
        {"id": "folders", "ok": True, "detail": {"missing_before": before_missing_dirs, "created": bool(apply and before_missing_dirs)}},
        check_json(RULES_PATH, "rules"),
        check_required_files(),
        check_flows(),
        check_environment(),
    ]
    payload = {"mode": "apply" if apply else "plan", "ok": all(item["ok"] for item in checks), "checks": checks}
    write_state(payload)
    return payload


def run_setup() -> dict[str, Any]:
    done = subprocess.run(["sh", "scripts/codex_cloud_setup.sh"], cwd=str(ROOT), text=True, capture_output=True, check=False, timeout=300)
    return {"returncode": done.returncode, "stdout_tail": done.stdout.strip()[-1600:], "stderr_tail": done.stderr.strip()[-1600:]}


def improve() -> int:
    applied = plan(True)
    setup = run_setup()
    payload = {"maintenance": applied, "setup": setup, "ok": applied["ok"] and setup["returncode"] == 0}
    write_state(payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic maintenance engine for a-Shell.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    sub.add_parser("plan")
    sub.add_parser("apply")
    sub.add_parser("improve")
    args = parser.parse_args(argv)
    if args.command == "self-test":
        assert isinstance(plan(False), dict)
        print("ashell maintain self-test ok")
        return 0
    if args.command == "plan":
        print(json.dumps(plan(False), indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "apply":
        payload = plan(True)
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if payload["ok"] else 1
    if args.command == "improve":
        return improve()
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
