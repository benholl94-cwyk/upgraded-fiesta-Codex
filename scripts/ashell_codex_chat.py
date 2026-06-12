#!/usr/bin/env python3
"""a-Shell interactive repository chat and monitor for upgraded-fiesta."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEV_ROOT = Path.home() / "Documents" / "Developer"
LOG_DIR = DEV_ROOT / "logs"
RUN_DIR = DEV_ROOT / "runs"
DEFAULT_MODEL = "gpt-4.1"
MODEL_ENV = "OPENAI_MODEL"
SAFE_COMMAND_PREFIXES = ("pwd", "ls", "cat", "head", "tail", "python3 -m py_compile", "python3 scripts/", "sh scripts/", "lg2 pull", "lg2 status", "lg2 diff")
BLOCKED_COMMAND_RE = re.compile(r"(^|\s)(rm|rmdir|mv|cp|chmod|chown|dd|mkfs|kill|pkill|curl|wget|ssh|scp|nc|python\s+-c)\b|[|;&`$<>]", re.I)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)


def log_event(kind: str, payload: dict[str, Any]) -> None:
    ensure_dirs()
    path = LOG_DIR / f"ashell-codex-chat-{dt.datetime.now().strftime('%Y%m%d')}.jsonl"
    record = {"ts_utc": now(), "kind": kind, **payload}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_monitor(state: dict[str, Any]) -> None:
    ensure_dirs()
    path = RUN_DIR / "ashell-codex-chat-last.json"
    path.write_text(json.dumps({"ts_utc": now(), **state}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def color(text: str, code: str) -> str:
    if os.environ.get("NO_COLOR"):
        return text
    return f"\033[{code}m{text}\033[0m"


def run_cmd(argv: list[str], timeout: int = 45) -> dict[str, Any]:
    try:
        done = subprocess.run(argv, cwd=str(ROOT), text=True, capture_output=True, check=False, timeout=timeout)
        return {"returncode": done.returncode, "stdout": done.stdout.strip(), "stderr": done.stderr.strip()}
    except Exception as exc:
        return {"returncode": 127, "stdout": "", "stderr": repr(exc)}


def shell_text(command: str, timeout: int = 90) -> dict[str, Any]:
    try:
        done = subprocess.run(command, cwd=str(ROOT), shell=True, text=True, capture_output=True, check=False, timeout=timeout)
        return {"returncode": done.returncode, "stdout": done.stdout.strip(), "stderr": done.stderr.strip()}
    except Exception as exc:
        return {"returncode": 127, "stdout": "", "stderr": repr(exc)}


def command_allowed(command: str) -> bool:
    stripped = command.strip()
    if not stripped or BLOCKED_COMMAND_RE.search(stripped):
        return False
    return any(stripped == prefix or stripped.startswith(prefix + " ") for prefix in SAFE_COMMAND_PREFIXES)


def repo_status() -> dict[str, Any]:
    git_head = run_cmd(["git", "rev-parse", "--short=12", "HEAD"])
    git_branch = run_cmd(["git", "branch", "--show-current"])
    git_status = run_cmd(["git", "status", "--short"])
    return {
        "root": str(ROOT),
        "python": sys.version.split()[0],
        "model": os.environ.get(MODEL_ENV, DEFAULT_MODEL),
        "git_head": git_head.get("stdout") or "git-unavailable",
        "git_branch": git_branch.get("stdout") or "unknown",
        "git_status": git_status.get("stdout") or "clean-or-unavailable",
    }


def local_answer(prompt: str) -> str:
    status = repo_status()
    return "Local monitor mode. API bridge is not configured in this file. Prompt logged; status: " + json.dumps(status, ensure_ascii=False, sort_keys=True)


def banner() -> None:
    status = repo_status()
    print(color("╭────────────────────────────────────────────╮", "36"))
    print(color("│ upgraded-fiesta · a-Shell Codex Chat       │", "36"))
    print(color("╰────────────────────────────────────────────╯", "36"))
    print(f"root   : {status['root']}")
    print(f"head   : {status['git_head']}  branch: {status['git_branch']}")
    print(f"model  : {status['model']}")
    print("type /help for commands")
    print()


def print_help() -> None:
    print(textwrap.dedent("""
    Commands:
      /help                 show this help
      /status               show live repository state
      /audit                generate live repository audit markdown
      /validate             run sh scripts/codex_cloud_setup.sh
      /run <safe command>   run an allowlisted local command
      /clear                redraw the interface
      /exit                 quit
    """).strip())


def show_result(title: str, result: dict[str, Any]) -> None:
    ok = result.get("returncode") == 0
    print(color(f"[{title}] exit={result.get('returncode')}", "32" if ok else "31"))
    if result.get("stdout"):
        print(result["stdout"])
    if result.get("stderr"):
        print(color(result["stderr"], "33"))


def handle_command(line: str) -> bool:
    if line in {"/exit", "/quit"}:
        return False
    if line == "/help":
        print_help()
    elif line == "/clear":
        print("\033[2J\033[H", end="")
        banner()
    elif line == "/status":
        status = repo_status()
        write_monitor(status)
        print(json.dumps(status, indent=2, ensure_ascii=False, sort_keys=True))
    elif line == "/audit":
        show_result("audit", run_cmd(["python3", "scripts/repository_audit_report.py", "--format", "markdown"], timeout=90))
    elif line == "/validate":
        show_result("validate", run_cmd(["sh", "scripts/codex_cloud_setup.sh"], timeout=180))
    elif line.startswith("/run "):
        command = line[5:].strip()
        if not command_allowed(command):
            print(color("blocked: command is outside the explicit allowlist", "31"))
        else:
            result = shell_text(command)
            log_event("run", {"command": command, "returncode": result.get("returncode")})
            show_result("run", result)
    else:
        print(color("unknown command; use /help", "33"))
    return True


def chat_loop() -> int:
    ensure_dirs()
    banner()
    log_event("start", repo_status())
    while True:
        try:
            line = input(color("codex> ", "35")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.startswith("/"):
            if not handle_command(line):
                break
            continue
        log_event("user", {"chars": len(line)})
        print(color("assistant:", "32"))
        print(local_answer(line))
        write_monitor({"last_prompt_chars": len(line), **repo_status()})
    log_event("stop", repo_status())
    return 0


def self_test() -> int:
    ensure_dirs()
    status = repo_status()
    write_monitor({"self_test": True, **status})
    assert ROOT.exists()
    assert (ROOT / "AGENTS.md").exists()
    assert (ROOT / "README.md").exists()
    print("ashell codex chat self-test ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Interactive a-Shell repository chat and monitor.")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    return chat_loop()


if __name__ == "__main__":
    raise SystemExit(main())
