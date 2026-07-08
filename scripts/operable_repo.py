#!/usr/bin/env python3
"""Unified operable repository controller with network capability integration."""
from __future__ import annotations

import argparse
import compileall
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "datasets" / "operable-repo.config.json"
REPORT_SCHEMA = "upgraded-fiesta.operable-repo.report.v1"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    return sha256_bytes(path.read_bytes()) if path.is_file() else None


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON root must be an object: {rel(path)}")
    return payload


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    if config.get("schema") != "upgraded-fiesta.operable-repo.config.v1":
        raise RuntimeError("invalid operable repo config schema")
    return config


def expand_runtime_path(raw: str) -> Path:
    home = os.environ.get("HOME", str(Path.home()))
    expanded = raw.replace("$HOME", home).replace("${HOME}", home).replace("$home", home).replace("${home}", home)
    return Path(os.path.expandvars(os.path.expanduser(expanded))).resolve()


def run_command(argv: list[str], timeout: int = 120) -> dict[str, Any]:
    try:
        completed = subprocess.run(argv, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        return {"argv": argv, "returncode": completed.returncode, "ok": completed.returncode == 0, "output_tail": completed.stdout[-12000:]}
    except FileNotFoundError:
        return {"argv": argv, "returncode": 127, "ok": False, "output_tail": f"command not found: {argv[0]}"}
    except subprocess.TimeoutExpired as exc:
        return {"argv": argv, "returncode": 124, "ok": False, "output_tail": f"timeout after {timeout}s\n{exc.stdout or ''}"}


def base_report(command: str, config: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": REPORT_SCHEMA,
        "generated_at_utc": utc_now(),
        "command": command,
        "ok": True,
        "repository": {
            "full_name": config["repository"]["full_name"],
            "default_branch": config["repository"]["default_branch"],
            "known_main_head": config["repository"]["known_main_head_after_localhost_export"],
        },
        "checks": [],
        "security": config["security"],
    }


def add_check(report: dict[str, Any], name: str, ok: bool, detail: Any, severity: str | None = None) -> None:
    report["checks"].append({"name": name, "ok": ok, "severity": severity or ("info" if ok else "error"), "detail": detail})
    if not ok and (severity or "error") == "error":
        report["ok"] = False


def status_report(config: dict[str, Any]) -> dict[str, Any]:
    report = base_report("status", config)
    required: list[dict[str, Any]] = []
    for raw in config["required_files"]:
        path = ROOT / raw
        required.append({"path": raw, "exists": path.is_file(), "sha256": sha256_file(path), "bytes": path.stat().st_size if path.is_file() else None})
    missing = [item["path"] for item in required if not item["exists"]]
    add_check(report, "required_files", not missing, {"files": required, "missing": missing})
    add_check(report, "python_executable", True, {"executable": sys.executable, "version": sys.version.split()[0]})
    add_check(report, "tool_availability", True, {"python3": shutil.which("python3") is not None, "bash": shutil.which("bash") is not None, "openssl": shutil.which("openssl") is not None}, "info")
    add_check(report, "runtime_export_root", True, {"raw": config["runtime"]["export_root"], "expanded": str(expand_runtime_path(config["runtime"]["export_root"]))})
    return report


def validate_report(config: dict[str, Any]) -> dict[str, Any]:
    report = base_report("validate", config)
    add_check(report, "compile_scripts_directory", compileall.compile_dir(str(ROOT / "scripts"), quiet=1, force=True), {"path": "scripts"})
    for json_path in [
        "datasets/repository-synthesis.dataset.json",
        "datasets/safe-write-edit-ops.policy.json",
        "datasets/localhost-export.config.json",
        "datasets/localhost-export.object.json",
        "datasets/operable-repo.config.json",
        "datasets/network-capabilities.config.json",
        "schemas/safe-write-edit-ops.schema.json",
        "schemas/localhost-export.schema.json",
        "schemas/operable-repo-report.schema.json",
        "schemas/network-capabilities-report.schema.json",
    ]:
        path = ROOT / json_path
        try:
            payload = load_json(path)
            add_check(report, f"json_parse:{json_path}", True, {"schema": payload.get("schema") or payload.get("$schema"), "sha256": sha256_file(path)})
        except Exception as exc:
            add_check(report, f"json_parse:{json_path}", False, {"error": str(exc)})
    for argv in [
        ["python3", "scripts/rebase_guard.py"],
        ["python3", "scripts/safe_write_edit_ops.py", "validate", "--object", "examples/safe-write-edit-ops.object.json"],
        ["python3", "scripts/localhost_export_server.py", "--scheme", "http", "--once"],
        ["python3", "scripts/network_capabilities.py", "status"],
    ]:
        result = run_command(argv, timeout=120)
        add_check(report, "command:" + " ".join(argv), bool(result["ok"]), result)
    return report


def export_report(config: dict[str, Any]) -> dict[str, Any]:
    report = base_report("export", config)
    output_dir = expand_runtime_path(config["runtime"]["export_root"])
    result = run_command(["python3", "scripts/localhost_export_server.py", "--scheme", "http", "--write", "--output-dir", str(output_dir)], timeout=120)
    add_check(report, "localhost_export_write", bool(result["ok"]), result)
    written = []
    for filename in ["export.bundle.json", "export-manifest.json", "export.zip"]:
        path = output_dir / filename
        written.append({"path": str(path), "exists": path.is_file(), "bytes": path.stat().st_size if path.is_file() else None, "sha256": sha256_file(path)})
    add_check(report, "written_runtime_files", all(item["exists"] for item in written), {"output_dir": str(output_dir), "files": written})
    return report


def network_report(config: dict[str, Any], measure: bool) -> dict[str, Any]:
    report = base_report("network", config)
    command = "measure" if measure else "status"
    result = run_command(["python3", "scripts/network_capabilities.py", command], timeout=180)
    add_check(report, f"network_capabilities:{command}", bool(result["ok"]), result)
    return report


def doctor_report(config: dict[str, Any]) -> dict[str, Any]:
    report = base_report("doctor", config)
    subreports = [status_report(config), validate_report(config), export_report(config), network_report(config, measure=True)]
    for item in subreports:
        add_check(report, f"subreport:{item['command']}", bool(item["ok"]), item, "info" if item["ok"] else "error")
    state_root = ROOT / config["runtime"]["state_root"]
    state_root.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    report_path = state_root / "operable-repo.doctor.json"
    report_path.write_text(payload, encoding="utf-8")
    report["runtime_report"] = {"path": rel(report_path), "sha256": sha256_bytes(payload.encode("utf-8")), "bytes": len(payload.encode("utf-8"))}
    return report


def serve(config: dict[str, Any], argv_tail: list[str]) -> int:
    argv = ["python3", "scripts/localhost_export_server.py", "--scheme", "https", "--host", config["runtime"]["localhost_bind_host"], "--port", str(config["runtime"]["localhost_https_port"])] + argv_tail
    os.execvp(argv[0], argv)
    return 127


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Operate upgraded-fiesta-Codex as a machine-readable software repository.")
    parser.add_argument("command", choices=["status", "validate", "export", "doctor", "serve", "network"])
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        config = load_config()
        if args.command == "status":
            report = status_report(config)
        elif args.command == "validate":
            report = validate_report(config)
        elif args.command == "export":
            report = export_report(config)
        elif args.command == "doctor":
            report = doctor_report(config)
        elif args.command == "network":
            report = network_report(config, measure="--measure" in args.args or "measure" in args.args)
        elif args.command == "serve":
            return serve(config, args.args)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report.get("ok") else 1
    except Exception as exc:
        print(json.dumps({"schema": "upgraded-fiesta.operable-repo.error.v1", "generated_at_utc": utc_now(), "ok": False, "error": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
