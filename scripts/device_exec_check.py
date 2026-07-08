#!/usr/bin/env python3
"""Real local /exec checker for user-device repository runtime.

This script reports actual execution state from the environment where it runs.
It does not attempt privilege escalation, does not run sudo, and does not execute
arbitrary user commands. Root is reported only if the current process already has
UID/EUID 0.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
from pathlib import Path
import socket
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "datasets" / "device-exec.config.json"
REPORT_SCHEMA = "upgraded-fiesta.device-exec.report.v1"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    return sha256_bytes(path.read_bytes()) if path.is_file() else None


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON root must be object: {path}")
    return payload


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    if config.get("schema") != "upgraded-fiesta.device-exec.config.v1":
        raise RuntimeError("invalid device exec config schema")
    return config


def expand_runtime_path(raw: str) -> Path:
    home = os.environ.get("HOME", str(Path.home()))
    expanded = raw.replace("$HOME", home).replace("${HOME}", home).replace("$home", home).replace("${home}", home)
    return Path(os.path.expandvars(os.path.expanduser(expanded))).resolve()


def run_command(argv: list[str], timeout: int = 5) -> dict[str, Any]:
    try:
        completed = subprocess.run(argv, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        return {"argv": argv, "returncode": completed.returncode, "ok": completed.returncode == 0, "output_tail": completed.stdout[-4000:]}
    except FileNotFoundError:
        return {"argv": argv, "returncode": 127, "ok": False, "output_tail": f"command not found: {argv[0]}"}
    except subprocess.TimeoutExpired as exc:
        return {"argv": argv, "returncode": 124, "ok": False, "output_tail": f"timeout after {timeout}s\n{exc.stdout or ''}"}


def id_state() -> dict[str, Any]:
    getuid = getattr(os, "getuid", None)
    geteuid = getattr(os, "geteuid", None)
    getgid = getattr(os, "getgid", None)
    getegid = getattr(os, "getegid", None)
    uid = getuid() if callable(getuid) else None
    euid = geteuid() if callable(geteuid) else uid
    gid = getgid() if callable(getgid) else None
    egid = getegid() if callable(getegid) else gid
    return {
        "uid": uid,
        "euid": euid,
        "gid": gid,
        "egid": egid,
        "is_root_uid": uid == 0,
        "is_root_euid": euid == 0,
        "root_confirmed": uid == 0 or euid == 0,
        "uid_api_available": callable(getuid),
        "euid_api_available": callable(geteuid),
    }


def writable_probe(path: Path) -> dict[str, Any]:
    probe_dir = path if path.is_dir() else path.parent
    probe_dir.mkdir(parents=True, exist_ok=True)
    probe_file = probe_dir / ".device_exec_write_probe.json"
    payload = json.dumps({"schema": "upgraded-fiesta.device-exec.write-probe.v1", "generated_at_utc": utc_now()}, sort_keys=True).encode("utf-8") + b"\n"
    try:
        probe_file.write_bytes(payload)
        read_back = probe_file.read_bytes()
        probe_file.unlink()
        return {"path": str(probe_dir), "ok": read_back == payload, "bytes": len(payload), "sha256": sha256_bytes(payload)}
    except Exception as exc:
        return {"path": str(probe_dir), "ok": False, "error": str(exc)}


def repo_git_state() -> dict[str, Any]:
    return {
        "root": str(ROOT),
        "root_exists": ROOT.is_dir(),
        "git_dir_exists": (ROOT / ".git").exists(),
        "remote_origin": run_command(["git", "remote", "get-url", "origin"], timeout=5),
        "rev_parse_head": run_command(["git", "rev-parse", "HEAD"], timeout=5),
        "status_short": run_command(["git", "status", "--short"], timeout=5),
    }


def repository_report(config: dict[str, Any]) -> dict[str, Any]:
    repo = config["repository"]
    return {
        "full_name": repo["full_name"],
        "default_branch": repo["default_branch"],
        "historical_anchors": repo.get("historical_anchors", {
            "after_depo_server_commit": repo.get("known_main_head_after_depo_server"),
            "semantics": "historical audit anchor, not current branch head assertion",
        }),
    }


def build_report(command: str, config: dict[str, Any], write: bool) -> dict[str, Any]:
    runtime_root = ROOT / config["runtime"]["state_root"]
    export_bundle = expand_runtime_path(config["runtime"]["localhost_export_bundle"])
    id_info = id_state()
    report = {
        "schema": REPORT_SCHEMA,
        "generated_at_utc": utc_now(),
        "ok": True,
        "command": command,
        "repository": repository_report(config),
        "device_exec": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "cwd": os.getcwd(),
            "repo_root": str(ROOT),
            "runtime_state_root": str(runtime_root),
            "workspace_writable": writable_probe(ROOT),
            "runtime_state_writable": writable_probe(runtime_root),
            "localhost_export_bundle": {
                "path": str(export_bundle),
                "exists": export_bundle.is_file(),
                "bytes": export_bundle.stat().st_size if export_bundle.is_file() else None,
                "sha256": sha256_file(export_bundle),
            },
            "git": repo_git_state(),
        },
        "root_check": {
            **id_info,
            "root_required_for_repo_operability": config["root_policy"]["root_required_for_repo_operability"],
            "root_escalation_supported": config["root_policy"]["root_escalation_supported"],
            "root_escalation_attempted": False,
            "sudo_executed": False,
        },
        "security": config["security"],
    }
    if write:
        runtime_root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(report, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        path = runtime_root / "device-exec.report.json"
        path.write_bytes(payload)
        report["runtime_report"] = {"path": str(path), "bytes": len(payload), "sha256": sha256_bytes(payload)}
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check real local repository /exec and root state without privilege escalation.")
    parser.add_argument("command", choices=["status", "doctor"])
    args = parser.parse_args(argv)
    try:
        config = load_config()
        report = build_report(args.command, config, write=args.command == "doctor")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report.get("ok") else 1
    except Exception as exc:
        print(json.dumps({"schema": "upgraded-fiesta.device-exec.error.v1", "generated_at_utc": utc_now(), "ok": False, "error": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
