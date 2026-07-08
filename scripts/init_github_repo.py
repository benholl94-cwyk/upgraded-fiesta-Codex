#!/usr/bin/env python3
"""Idempotent repository initializer for upgraded-fiesta-Codex.

Creates runtime directories, verifies protective ignore policy, and delegates to
scripts/full_debug.py for a complete static diagnostic pass. The script does not
write secrets and does not contact external services.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIRS = ("logs", "runs", "backups", "exports", "reports", "policies")
PROTECTED_PATTERNS = (
    ".env",
    ".env.*.local",
    "*.local.env",
    "*.pem",
    "*.p12",
    "*.pfx",
    "*.secret",
    "*.secrets",
    "logs/",
    "runs/",
    "backups/",
    "exports/",
    ".tmp/",
    ".cache/",
    "target/",
    "node_modules/",
    "ui/node_modules/",
)


def ensure_runtime_dirs() -> list[str]:
    created: list[str] = []
    for dirname in RUNTIME_DIRS:
        path = ROOT / dirname
        if path.exists() and not path.is_dir():
            raise RuntimeError(f"runtime path exists but is not a directory: {dirname}")
        if not path.exists():
            path.mkdir(parents=True)
            created.append(dirname)
    return created


def validate_gitignore() -> list[str]:
    gitignore = ROOT / ".gitignore"
    if not gitignore.is_file():
        raise RuntimeError(".gitignore is missing")
    text = gitignore.read_text(encoding="utf-8")
    missing = [pattern for pattern in PROTECTED_PATTERNS if pattern not in text]
    return missing


def run_full_debug(deep: bool, write_report: bool) -> int:
    command = [sys.executable, str(ROOT / "scripts" / "full_debug.py")]
    if deep:
        command.append("--deep")
    if write_report:
        command.append("--write-report")
    completed = subprocess.run(command, cwd=str(ROOT), text=True, check=False)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize and verify the GitHub repository working tree.")
    parser.add_argument("--deep", action="store_true", help="Forward --deep to scripts/full_debug.py.")
    parser.add_argument("--no-report", action="store_true", help="Do not persist reports/full_debug_report.{json,txt}.")
    args = parser.parse_args(argv)

    created = ensure_runtime_dirs()
    missing_ignores = validate_gitignore()
    status = {
        "schema": "upgraded-fiesta.github-init.v1",
        "root": str(ROOT),
        "created_runtime_dirs": created,
        "protected_ignore_missing": missing_ignores,
    }
    print(json.dumps(status, indent=2, sort_keys=True))
    if missing_ignores:
        return 1
    return run_full_debug(deep=args.deep, write_report=not args.no_report)


if __name__ == "__main__":
    raise SystemExit(main())
