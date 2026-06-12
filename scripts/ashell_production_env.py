#!/usr/bin/env python3
"""Mobile production control-plane for a-Shell.

Stdlib-only orchestration for validation, status, snapshots, backups and the
existing chat/static components. It avoids /tmp and writes state below
~/Documents/Developer.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "settings" / "mobile-production" / "environment.json"
DEV_ROOT = Path.home() / "Documents" / "Developer"
LOG_DIR = DEV_ROOT / "logs"
RUN_DIR = DEV_ROOT / "runs"
EXPORT_DIR = DEV_ROOT / "exports"
BACKUP_DIR = DEV_ROOT / "backups"
STATE_FILE = RUN_DIR / "mobile-production-state.json"
SKIP_DIRS = {".git", "__pycache__", "node_modules", "vendor", "dist", "build"}
SKIP_NAMES = {"key.sh", ".env", "id_ed25519", "id_rsa"}
SKIP_SUFFIXES = (".pyc", ".pem", ".p12", ".key")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S")


def ensure_dirs() -> None:
    for directory in (LOG_DIR, RUN_DIR, EXPORT_DIR, BACKUP_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise SystemExit("missing settings/mobile-production/environment.json")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def write_state(state: dict[str, Any]) -> None:
    ensure_dirs()
    STATE_FILE.write_text(json.dumps({"ts_utc": utc_now(), **state}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def append_log(kind: str, payload: dict[str, Any]) -> None:
    ensure_dirs()
    path = LOG_DIR / f"mobile-production-{dt.datetime.now().strftime('%Y%m%d')}.jsonl"
    record = {"ts_utc": utc_now(), "kind": kind, **payload}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def run(argv: list[str], timeout: int = 180) -> dict[str, Any]:
    try:
        done = subprocess.run(argv, cwd=str(ROOT), text=True, capture_output=True, check=False, timeout=timeout)
        return {"command": argv, "returncode": done.returncode, "stdout": done.stdout.strip(), "stderr": done.stderr.strip()}
    except Exception as exc:
        return {"command": argv, "returncode": 127, "stdout": "", "stderr": repr(exc)}


def git_dir() -> Path | None:
    direct = ROOT / ".git"
    if direct.is_dir():
        return direct
    if direct.is_file():
        text = direct.read_text(encoding="utf-8", errors="replace").strip()
        prefix = "gitdir:"
        if text.startswith(prefix):
            candidate = (ROOT / text[len(prefix):].strip()).resolve()
            if candidate.is_dir():
                return candidate
    return None


def git_metadata() -> dict[str, str]:
    head = run(["git", "rev-parse", "--short=12", "HEAD"], timeout=30)
    branch = run(["git", "branch", "--show-current"], timeout=30)
    status = run(["git", "status", "--short"], timeout=30)
    if head["stdout"] and branch["stdout"]:
        return {"head": head["stdout"], "branch": branch["stdout"], "status": status["stdout"] or "clean"}
    directory = git_dir()
    fallback_head = "git-unavailable"
    fallback_branch = "unknown"
    if directory and (directory / "HEAD").exists():
        head_text = (directory / "HEAD").read_text(encoding="utf-8", errors="replace").strip()
        if head_text.startswith("ref:"):
            ref = head_text.split(":", 1)[1].strip()
            fallback_branch = ref.removeprefix("refs/heads/")
            ref_file = directory / ref
            if ref_file.exists():
                fallback_head = ref_file.read_text(encoding="utf-8", errors="replace").strip()[:12]
        else:
            fallback_head = head_text[:12]
            fallback_branch = "detached"
    return {"head": fallback_head, "branch": fallback_branch, "status": status["stdout"] or "clean-or-unavailable"}


def environment_status() -> dict[str, Any]:
    config = load_config()
    git = git_metadata()
    disk = shutil.disk_usage(str(DEV_ROOT)) if DEV_ROOT.exists() else shutil.disk_usage(str(ROOT))
    state = {
        "root": str(ROOT),
        "mode": config.get("mode"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "git": git,
        "paths": {"logs": str(LOG_DIR), "runs": str(RUN_DIR), "exports": str(EXPORT_DIR), "backups": str(BACKUP_DIR)},
        "disk": {"total": disk.total, "used": disk.used, "free": disk.free},
        "components": [component["id"] for component in config.get("components", [])],
    }
    write_state(state)
    append_log("status", {"head": git["head"], "branch": git["branch"]})
    return state


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def doctor() -> int:
    config = load_config()
    results = []
    exit_code = 0
    for component in config.get("components", []):
        result = run([str(part) for part in component.get("command", [])])
        item = {
            "id": component.get("id"),
            "kind": component.get("kind"),
            "required": bool(component.get("required")),
            "returncode": result["returncode"],
            "stdout_tail": result["stdout"][-1200:],
            "stderr_tail": result["stderr"][-1200:],
        }
        results.append(item)
        if item["required"] and item["returncode"] != 0:
            exit_code = 1
    payload = {"ok": exit_code == 0, "results": results, "status": environment_status()}
    write_state(payload)
    append_log("doctor", {"ok": payload["ok"]})
    print_json(payload)
    return exit_code


def backup() -> int:
    ensure_dirs()
    archive = BACKUP_DIR / f"upgraded-fiesta-mobile-{stamp()}.tar.gz"
    skipped: list[str] = []

    def allowed(path: Path) -> bool:
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts) or path.name in SKIP_NAMES or path.name.endswith(SKIP_SUFFIXES):
            skipped.append(str(rel))
            return False
        return True

    with tarfile.open(archive, "w:gz") as tar:
        for path in sorted(ROOT.rglob("*")):
            if allowed(path):
                tar.add(path, arcname=str(Path("upgraded-fiesta") / path.relative_to(ROOT)))
    payload = {"archive": str(archive), "size_bytes": archive.stat().st_size, "skipped_count": len(set(skipped))}
    write_state({"backup": payload})
    append_log("backup", payload)
    print_json(payload)
    return 0


def snapshot() -> int:
    ensure_dirs()
    target = EXPORT_DIR / f"mobile-production-snapshot-{stamp()}.json"
    payload = {"status": environment_status(), "config": load_config(), "audit": run(["python3", "scripts/repository_audit_report.py", "--format", "json"], timeout=180)}
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print_json({"snapshot": str(target), "size_bytes": target.stat().st_size})
    return 0


def reconcile() -> int:
    ensure_dirs()
    required = [LOG_DIR, RUN_DIR, EXPORT_DIR, BACKUP_DIR, ROOT / "settings" / "mobile-production"]
    for path in required:
        path.mkdir(parents=True, exist_ok=True)
    payload = {"ok": True, "created_or_verified": [str(path) for path in required], "status": environment_status()}
    print_json(payload)
    append_log("reconcile", {"ok": True})
    return 0


def self_test() -> int:
    ensure_dirs()
    config = load_config()
    assert config.get("schema_version")
    assert (ROOT / "scripts" / "ashell_codex_chat.py").is_file()
    assert (ROOT / "scripts" / "mobile_operator.py").is_file()
    write_state({"self_test": True, "status": environment_status()})
    print("ashell production env self-test ok")
    return 0


def monitor(interval: int) -> int:
    print("mobile production monitor: start")
    try:
        while True:
            state = environment_status()
            git = state["git"]
            print(f"{utc_now()} head={git['head']} branch={git['branch']} free={state['disk']['free']}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("mobile production monitor: stop")
        return 0


def launch(script: str, args: list[str]) -> int:
    os.execv(sys.executable, [sys.executable, str(ROOT / "scripts" / script), *args])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mobile production control-plane for a-Shell.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    sub.add_parser("status")
    sub.add_parser("doctor")
    sub.add_parser("backup")
    sub.add_parser("snapshot")
    sub.add_parser("reconcile")
    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--port", type=int, default=8001)
    sub.add_parser("chat")
    monitor_parser = sub.add_parser("monitor")
    monitor_parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args(argv)
    if args.command == "self-test":
        return self_test()
    if args.command == "status":
        print_json(environment_status())
        return 0
    if args.command == "doctor":
        return doctor()
    if args.command == "backup":
        return backup()
    if args.command == "snapshot":
        return snapshot()
    if args.command == "reconcile":
        return reconcile()
    if args.command == "serve":
        return launch("ashell_static_server.py", ["--host", "127.0.0.1", "--port", str(args.port), "--directory", str(ROOT)])
    if args.command == "chat":
        return launch("ashell_codex_chat.py", [])
    if args.command == "monitor":
        return monitor(args.interval)
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
