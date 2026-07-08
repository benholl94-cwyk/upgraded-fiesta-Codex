#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "config" / "repo-trusted-ops.fullstack.json"
REPORT_SCHEMA = "repo-trusted-ops.report.v1"
ALLOWED_SCHEMA = "repo-trusted-ops.fullstack.v1"
DENIED_EXECUTABLES = {"bash", "sh", "zsh", "fish", "sudo", "su", "ssh", "scp", "sftp", "rsync", "curl", "wget", "nc", "ncat", "netcat", "socat", "telnet"}
DENIED_COMMAND_TOKENS = {";", "&&", "||", "`", "$(", ">", "<"}
ALLOWED_EXTERNAL_HOSTS = {"api.github.com", "github.com"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"json root must be object: {path}")
    return data


def rel_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def validate_command(command: Any) -> list[str]:
    findings: list[str] = []
    if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
        return ["command must be a non-empty argv string list"]
    executable = Path(command[0]).name
    if executable in DENIED_EXECUTABLES:
        findings.append(f"denied executable: {executable}")
    for part in command:
        if part in DENIED_COMMAND_TOKENS:
            findings.append(f"denied shell token: {part}")
        if any(token in part for token in ("$(`", "&&", "||")):
            findings.append(f"denied shell expression in argument: {part}")
    return findings


def validate_profile(profile: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    findings: list[str] = []
    warnings: list[str] = []
    if profile.get("schema") != ALLOWED_SCHEMA:
        findings.append(f"schema must be {ALLOWED_SCHEMA}")
    runtime = profile.get("runtime_policy")
    if not isinstance(runtime, dict):
        findings.append("runtime_policy must be object")
        runtime = {}
    required_false = [
        "secret_read_allowed",
        "remote_execution_allowed",
        "destructive_execution_allowed",
        "arbitrary_shell_allowed",
    ]
    for key in required_false:
        if runtime.get(key) is not False:
            findings.append(f"runtime_policy.{key} must be false")
    if runtime.get("declared_targets_only") is not True:
        findings.append("runtime_policy.declared_targets_only must be true")
    if runtime.get("live_datetime_required") is not True:
        findings.append("runtime_policy.live_datetime_required must be true")

    local_sets = profile.get("local_fullstack_sets")
    if not isinstance(local_sets, list) or not local_sets:
        findings.append("local_fullstack_sets must be non-empty list")
        local_sets = []
    seen_ids: set[str] = set()
    for entry in local_sets:
        if not isinstance(entry, dict):
            findings.append("local_fullstack_sets entries must be objects")
            continue
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            findings.append("local set id must be non-empty string")
        elif entry_id in seen_ids:
            findings.append(f"duplicate local set id: {entry_id}")
        else:
            seen_ids.add(entry_id)
        findings.extend(f"{entry_id}: {item}" for item in validate_command(entry.get("command")))

    external_sets = profile.get("external_fullstack_sets")
    if not isinstance(external_sets, list):
        findings.append("external_fullstack_sets must be list")
        external_sets = []
    for entry in external_sets:
        if not isinstance(entry, dict):
            findings.append("external_fullstack_sets entries must be objects")
            continue
        if entry.get("kind") == "https_json_probe":
            url = entry.get("url", "")
            if not isinstance(url, str) or not url.startswith("https://"):
                findings.append(f"{entry.get('id')}: https_json_probe requires https url")
            host = url.split("/")[2] if url.startswith("https://") and len(url.split("/")) > 2 else ""
            if host not in ALLOWED_EXTERNAL_HOSTS:
                findings.append(f"{entry.get('id')}: external host not allowed: {host}")
        elif entry.get("kind") == "repo_file_presence":
            path = entry.get("path")
            if not isinstance(path, str) or not path:
                findings.append(f"{entry.get('id')}: path must be non-empty string")
        else:
            warnings.append(f"{entry.get('id')}: unsupported external kind treated as non-executable")
    return not findings, findings, warnings


def run_command(command: list[str], extra_env: dict[str, str] | None = None, timeout: int = 120) -> dict[str, Any]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    try:
        completed = subprocess.run(command, cwd=str(ROOT), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        output = completed.stdout or ""
        return {
            "argv": command,
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "output_tail": output[-4000:],
        }
    except FileNotFoundError:
        return {"argv": command, "ok": False, "returncode": 127, "output_tail": f"command not found: {command[0]}"}
    except subprocess.TimeoutExpired as exc:
        return {"argv": command, "ok": False, "returncode": 124, "output_tail": f"timeout after {timeout}s\n{exc.stdout or ''}"}


def probe_https_json(entry: dict[str, Any]) -> dict[str, Any]:
    url = entry["url"]
    timeout = int(entry.get("timeout_seconds", 10))
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "repo-trusted-ops/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(200000)
            parsed = json.loads(raw.decode("utf-8")) if raw else None
            return {"ok": response.status == entry.get("expected_status", 200), "status": response.status, "json_object": isinstance(parsed, dict)}
    except HTTPError as exc:
        return {"ok": False, "status": exc.code, "error": str(exc)}
    except URLError as exc:
        return {"ok": False, "status": None, "error": str(exc)}
    except json.JSONDecodeError as exc:
        return {"ok": False, "status": None, "error": f"invalid json: {exc}"}


def evaluate_external(entry: dict[str, Any], *, probe_external: bool) -> dict[str, Any]:
    kind = entry.get("kind")
    result: dict[str, Any] = {"id": entry.get("id"), "kind": kind, "required": bool(entry.get("required")), "probed": False}
    if kind == "repo_file_presence":
        path = ROOT / str(entry.get("path", ""))
        result.update({"ok": path.is_file(), "path": rel_path(path), "exists": path.is_file()})
        return result
    if kind == "https_json_probe":
        if not probe_external:
            result.update({"ok": not bool(entry.get("required")), "skipped_reason": "external_probe_not_requested"})
            return result
        probe = probe_https_json(entry)
        result.update(probe)
        result["probed"] = True
        return result
    result.update({"ok": not bool(entry.get("required")), "skipped_reason": "unsupported_external_kind"})
    return result


def build_report(profile: dict[str, Any], *, execute_local: bool, probe_external: bool) -> dict[str, Any]:
    ok, findings, warnings = validate_profile(profile)
    local_results: list[dict[str, Any]] = []
    external_results: list[dict[str, Any]] = []

    if ok and execute_local:
        for entry in profile.get("local_fullstack_sets", []):
            command = entry["command"]
            command_findings = validate_command(command)
            if command_findings:
                local_results.append({"id": entry.get("id"), "ok": False, "findings": command_findings})
                continue
            timeout = 180 if entry.get("required") else 120
            result = run_command(command, extra_env=entry.get("environment"), timeout=timeout)
            result.update({"id": entry.get("id"), "kind": entry.get("kind"), "required": bool(entry.get("required"))})
            local_results.append(result)
    elif ok:
        for entry in profile.get("local_fullstack_sets", []):
            local_results.append({"id": entry.get("id"), "kind": entry.get("kind"), "required": bool(entry.get("required")), "ok": True, "skipped_reason": "local_execution_not_requested"})

    if ok:
        for entry in profile.get("external_fullstack_sets", []):
            external_results.append(evaluate_external(entry, probe_external=probe_external))

    required_failures = [item for item in local_results + external_results if item.get("required") and not item.get("ok")]
    report_ok = ok and not required_failures
    return {
        "schema": REPORT_SCHEMA,
        "generated_at_utc": utc_now(),
        "ok": report_ok,
        "profile_schema_ok": ok,
        "execute_local": execute_local,
        "probe_external": probe_external,
        "repository": profile.get("repository", {}),
        "runtime_policy": profile.get("runtime_policy", {}),
        "findings": findings,
        "warnings": warnings,
        "required_failures": required_failures,
        "local_results": local_results,
        "external_results": external_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run repo-trusted local/external operational fullstack checks.")
    parser.add_argument("command", choices=["validate", "report"])
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--execute-local", action="store_true")
    parser.add_argument("--probe-external", action="store_true")
    parser.add_argument("--write-report", default=None)
    args = parser.parse_args(argv)

    profile_path = Path(args.profile)
    if not profile_path.is_absolute():
        profile_path = ROOT / profile_path
    profile = load_json(profile_path)
    if args.command == "validate":
        ok, findings, warnings = validate_profile(profile)
        result = {"schema": REPORT_SCHEMA, "generated_at_utc": utc_now(), "ok": ok, "profile": rel_path(profile_path), "findings": findings, "warnings": warnings}
    else:
        result = build_report(profile, execute_local=args.execute_local, probe_external=args.probe_external)

    if args.write_report:
        out = Path(args.write_report)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
