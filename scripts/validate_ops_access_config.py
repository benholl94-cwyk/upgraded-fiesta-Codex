#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config" / "ops-command-manifest.example.json"

ALLOWED_SCHEMA = "ops-access.manifest.v1"
ALLOWED_NETWORK_POLICIES = {"deny", "declared_targets_only"}
REQUIRED_OPERATION_FIELDS = {
    "description",
    "command",
    "working_directory",
    "timeout_seconds",
    "output_limit_bytes",
    "network",
    "audit_required",
    "redaction_required",
}
DENIED_COMMAND_TOKENS = {
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
DENIED_TEXT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\.env(?:\.|$|/)",
        r"id_rsa",
        r"id_ed25519",
        r"private[_-]?key",
        r"authorization",
        r"bearer\s+",
        r"api[_-]?key",
        r"access[_-]?token",
        r"refresh[_-]?token",
        r"password",
        r"secret",
        r"/etc/shadow",
        r"/etc/passwd",
        r"/root(?:/|$)",
        r"/var/run/docker\.sock",
        r"[;&|`$<>]",
    )
]


def fail(message: str, findings: list[str]) -> None:
    findings.append(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing manifest: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("manifest root must be a JSON object")
    return value


def validate_command(operation_name: str, command: Any, findings: list[str]) -> None:
    if not isinstance(command, list) or not command:
        fail(f"{operation_name}: command must be a non-empty list", findings)
        return

    for index, token in enumerate(command):
        if not isinstance(token, str) or not token.strip():
            fail(f"{operation_name}: command[{index}] must be a non-empty string", findings)
            continue

        normalized = token.strip().split("/")[-1]
        if normalized in DENIED_COMMAND_TOKENS:
            fail(f"{operation_name}: denied executable token: {token}", findings)

        for pattern in DENIED_TEXT_PATTERNS:
            if pattern.search(token):
                fail(f"{operation_name}: denied text pattern in command token {index}", findings)
                break


def validate_manifest(manifest: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    findings: list[str] = []
    warnings: list[str] = []

    if manifest.get("schema") != ALLOWED_SCHEMA:
        fail(f"schema must be {ALLOWED_SCHEMA}", findings)

    default_timeout = manifest.get("default_timeout_seconds")
    if not isinstance(default_timeout, int) or not 1 <= default_timeout <= 600:
        fail("default_timeout_seconds must be an integer between 1 and 600", findings)

    default_limit = manifest.get("default_output_limit_bytes")
    if not isinstance(default_limit, int) or not 1 <= default_limit <= 2_000_000:
        fail("default_output_limit_bytes must be an integer between 1 and 2000000", findings)

    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        fail("profiles must be a non-empty object", findings)
    else:
        for profile_name, profile in profiles.items():
            if not isinstance(profile_name, str) or not profile_name:
                fail("profile name must be a non-empty string", findings)
            if not isinstance(profile, dict):
                fail(f"{profile_name}: profile must be an object", findings)
                continue
            if profile.get("remote_execution_enabled") is not False:
                fail(f"{profile_name}: remote_execution_enabled must default to false", findings)
            if profile.get("network_policy") not in ALLOWED_NETWORK_POLICIES:
                fail(f"{profile_name}: unsupported network_policy", findings)

    operations = manifest.get("operations")
    if not isinstance(operations, dict) or not operations:
        fail("operations must be a non-empty object", findings)
    else:
        for operation_name, operation in operations.items():
            if not isinstance(operation_name, str) or not re.fullmatch(r"[a-z][a-z0-9_.-]{2,80}", operation_name):
                fail(f"invalid operation name: {operation_name!r}", findings)
            if not isinstance(operation, dict):
                fail(f"{operation_name}: operation must be an object", findings)
                continue

            missing = sorted(REQUIRED_OPERATION_FIELDS - set(operation))
            if missing:
                fail(f"{operation_name}: missing fields: {', '.join(missing)}", findings)

            validate_command(operation_name, operation.get("command"), findings)

            working_directory = operation.get("working_directory")
            if working_directory != ".":
                fail(f"{operation_name}: working_directory must be '.' in repository manifest", findings)

            timeout = operation.get("timeout_seconds")
            if not isinstance(timeout, int) or not 1 <= timeout <= 600:
                fail(f"{operation_name}: timeout_seconds must be between 1 and 600", findings)

            output_limit = operation.get("output_limit_bytes")
            if not isinstance(output_limit, int) or not 1 <= output_limit <= 2_000_000:
                fail(f"{operation_name}: output_limit_bytes must be between 1 and 2000000", findings)

            if operation.get("network") not in ALLOWED_NETWORK_POLICIES:
                fail(f"{operation_name}: unsupported network policy", findings)

            if operation.get("audit_required") is not True:
                fail(f"{operation_name}: audit_required must be true", findings)

            if operation.get("redaction_required") is not True:
                fail(f"{operation_name}: redaction_required must be true", findings)

            if operation.get("network") == "declared_targets_only" and not operation.get("allowed_targets_file"):
                fail(f"{operation_name}: declared target operations require allowed_targets_file", findings)

            if operation.get("disabled_until_remote_guard_installed") is True:
                warnings.append(f"{operation_name}: reserved operation is intentionally disabled until remote guard installation")

    denied_capabilities = manifest.get("denied_capabilities")
    if not isinstance(denied_capabilities, list) or "unrestricted_shell" not in denied_capabilities:
        fail("denied_capabilities must include unrestricted_shell", findings)

    audit = manifest.get("audit")
    if not isinstance(audit, dict):
        fail("audit must be an object", findings)
    else:
        if audit.get("format") != "jsonl":
            fail("audit.format must be jsonl", findings)
        required_fields = audit.get("required_fields")
        if not isinstance(required_fields, list) or "operation" not in required_fields or "decision" not in required_fields:
            fail("audit.required_fields must include operation and decision", findings)

    return not findings, findings, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate fail-closed operations access manifest.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Path to ops access manifest JSON.")
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path

    manifest = load_json(manifest_path)
    ok, findings, warnings = validate_manifest(manifest)
    result = {
        "ok": ok,
        "manifest": str(manifest_path.relative_to(ROOT) if manifest_path.is_relative_to(ROOT) else manifest_path),
        "findings": findings,
        "warnings": warnings,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
