#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROUTE_MATRIX = ROOT / "config" / "ops-route-matrix.example.json"
DEFAULT_REPORT = ROOT / "reports" / "ops-route-dry-run-report.json"

ALLOWED_SCHEMA = "ops-access.route-matrix.v1"
SAFE_EXECUTE_MODES = {"safe_execute_allowed"}
PLAN_ONLY_MODES = {"plan_only", "blocked_until_remote_guard", "blocked_until_declared_targets"}
DENIED_EXECUTABLES = {
    "bash",
    "sh",
    "zsh",
    "fish",
    "sudo",
    "su",
    "ssh",
    "scp",
    "sftp",
    "rsync",
    "curl",
    "wget",
    "nc",
    "ncat",
    "netcat",
    "socat",
    "telnet",
    "chmod",
    "chown",
    "rm",
    "dd",
    "mkfs",
    "mount",
    "umount",
    "env",
    "printenv",
}
DOCKER_MUTATION_WORDS = {"up", "down", "rm", "restart", "kill", "prune", "push", "pull", "build", "create", "start", "stop"}
SENSITIVE_ENV_KEYS = ("SECRET", "TOKEN", "KEY", "PASSWORD", "AUTH", "CREDENTIAL")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON file: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return value


def normalize_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def validate_command(route_id: str, command: Any) -> list[str]:
    findings: list[str] = []
    if not isinstance(command, list) or not command:
        return [f"{route_id}: command must be a non-empty list"]

    for index, token in enumerate(command):
        if not isinstance(token, str) or not token.strip():
            findings.append(f"{route_id}: command[{index}] must be a non-empty string")
            continue
        executable = token.strip().split("/")[-1]
        if executable in DENIED_EXECUTABLES:
            findings.append(f"{route_id}: denied executable token: {token}")
        if any(marker in token for marker in (";", "&&", "||", "`", "$(", ">", "<")):
            findings.append(f"{route_id}: shell-control syntax is denied in token {index}")

    if command and command[0] == "docker":
        mutation = [part for part in command if part in DOCKER_MUTATION_WORDS]
        if mutation:
            findings.append(f"{route_id}: docker mutation command is denied: {mutation}")
    return findings


def validate_route_matrix(matrix: dict[str, Any]) -> tuple[bool, list[str]]:
    findings: list[str] = []
    if matrix.get("schema") != ALLOWED_SCHEMA:
        findings.append(f"schema must be {ALLOWED_SCHEMA}")
    if matrix.get("remote_execution_enabled") is not False:
        findings.append("remote_execution_enabled must be false")
    if matrix.get("docker_destructive_execution_enabled") is not False:
        findings.append("docker_destructive_execution_enabled must be false")
    if matrix.get("live_sync_mode") != "report_only":
        findings.append("live_sync_mode must be report_only")

    routes = matrix.get("routes")
    if not isinstance(routes, list) or not routes:
        findings.append("routes must be a non-empty list")
        return False, findings

    seen: set[str] = set()
    for route in routes:
        if not isinstance(route, dict):
            findings.append("each route must be an object")
            continue
        route_id = route.get("id")
        if not isinstance(route_id, str) or not route_id:
            findings.append("route id must be a non-empty string")
            route_id = "<invalid>"
        if route_id in seen:
            findings.append(f"duplicate route id: {route_id}")
        seen.add(route_id)

        mode = route.get("mode")
        if mode not in SAFE_EXECUTE_MODES | PLAN_ONLY_MODES:
            findings.append(f"{route_id}: unsupported mode: {mode}")
        if route.get("destructive") is not False:
            findings.append(f"{route_id}: destructive must be false")
        if route.get("network") not in {"deny", "declared_targets_only"}:
            findings.append(f"{route_id}: unsupported network policy")
        if route.get("docker") not in {"deny", "parse_only"}:
            findings.append(f"{route_id}: unsupported docker policy")
        findings.extend(validate_command(route_id, route.get("command")))
    return not findings, findings


def scrub_environment(env: dict[str, str]) -> dict[str, str]:
    visible: dict[str, str] = {}
    for key, value in env.items():
        if any(marker in key.upper() for marker in SENSITIVE_ENV_KEYS):
            visible[key] = "<redacted>"
        else:
            visible[key] = value
    return visible


def run_safe_command(command: list[str], timeout: int, output_limit: int) -> dict[str, Any]:
    started = time.monotonic()
    env = os.environ.copy()
    env.setdefault("POSTGRES_PASSWORD", "OPS_DRY_RUN_COMPOSE_PARSER_ONLY")
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        stdout = completed.stdout[:output_limit]
        stderr = completed.stderr[:output_limit]
        truncated = len(completed.stdout) > output_limit or len(completed.stderr) > output_limit
        return {
            "exit_code": completed.returncode,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "stdout_preview": stdout,
            "stderr_preview": stderr,
            "truncated": truncated,
        }
    except FileNotFoundError as exc:
        return {
            "exit_code": 127,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "stdout_preview": "",
            "stderr_preview": str(exc),
            "truncated": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "exit_code": 124,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "stdout_preview": (exc.stdout or "")[:output_limit] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[:output_limit] if isinstance(exc.stderr, str) else "timeout expired",
            "truncated": True,
        }


def build_report(matrix: dict[str, Any], execute_safe: bool) -> dict[str, Any]:
    ok, findings = validate_route_matrix(matrix)
    routes = matrix.get("routes", []) if isinstance(matrix.get("routes"), list) else []
    route_results: list[dict[str, Any]] = []

    default_timeout = int(matrix.get("default_timeout_seconds", 120))
    default_limit = int(matrix.get("default_output_limit_bytes", 200000))

    for route in routes:
        if not isinstance(route, dict):
            continue
        command = route.get("command") if isinstance(route.get("command"), list) else []
        mode = route.get("mode")
        route_id = route.get("id", "<invalid>")
        command_findings = validate_command(str(route_id), command)
        decision = "planned_not_executed"
        execution: dict[str, Any] | None = None

        if command_findings:
            decision = "blocked_by_validator"
        elif mode in PLAN_ONLY_MODES:
            decision = "plan_only"
        elif execute_safe and mode in SAFE_EXECUTE_MODES:
            decision = "executed_safe_local"
            execution = run_safe_command(command, default_timeout, default_limit)
        elif mode in SAFE_EXECUTE_MODES:
            decision = "safe_execution_available_not_requested"

        route_results.append({
            "id": route_id,
            "operation": route.get("operation"),
            "criticality": route.get("criticality"),
            "mode": mode,
            "decision": decision,
            "destructive": route.get("destructive"),
            "network": route.get("network"),
            "docker": route.get("docker"),
            "command": command,
            "findings": command_findings,
            "execution": execution,
        })

    return {
        "schema": "ops-access.route-dry-run-report.v1",
        "generated_at": utc_now(),
        "ok": ok and all(not result["findings"] for result in route_results),
        "remote_execution_performed": False,
        "docker_destructive_execution_performed": False,
        "live_sync_mode": matrix.get("live_sync_mode"),
        "execute_safe_requested": execute_safe,
        "matrix_findings": findings,
        "routes": route_results,
        "environment": scrub_environment({
            "GITHUB_ACTIONS": os.environ.get("GITHUB_ACTIONS", ""),
            "RUNNER_OS": os.environ.get("RUNNER_OS", ""),
            "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        }),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run operations route safety dry-runs and report-only live sync.")
    parser.add_argument("--route-matrix", default=str(DEFAULT_ROUTE_MATRIX), help="Route matrix JSON file.")
    parser.add_argument("--write-report", default=None, help="Write JSON report path.")
    parser.add_argument("--execute-safe", action="store_true", help="Execute only routes marked safe_execute_allowed.")
    parser.add_argument("--validate-only", action="store_true", help="Validate route matrix and exit without report file.")
    args = parser.parse_args(argv)

    matrix_path = normalize_path(args.route_matrix)
    matrix = load_json(matrix_path)
    ok, findings = validate_route_matrix(matrix)
    if args.validate_only:
        print(json.dumps({
            "ok": ok,
            "route_matrix": str(matrix_path.relative_to(ROOT) if matrix_path.is_relative_to(ROOT) else matrix_path),
            "findings": findings,
            "remote_execution_performed": False,
            "docker_destructive_execution_performed": False,
        }, indent=2, sort_keys=True))
        return 0 if ok else 1

    report = build_report(matrix, execute_safe=args.execute_safe)
    print(json.dumps(report, indent=2, sort_keys=True))

    report_path = normalize_path(args.write_report) if args.write_report else DEFAULT_REPORT
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
