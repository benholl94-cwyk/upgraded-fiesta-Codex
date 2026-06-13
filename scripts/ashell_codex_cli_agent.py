#!/usr/bin/env python3
"""Unified a-Shell Codex CLI agent for interactive repo work."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "settings" / "mobile-production" / "codex-cli-agent.json"
DEV_ROOT = Path.home() / "Documents" / "Developer"
RUN_DIR = DEV_ROOT / "runs"
LOG_DIR = DEV_ROOT / "logs"
STATE_PATH = RUN_DIR / "codex-cli-agent-state.json"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dirs() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def append_log(kind: str, payload: dict[str, Any]) -> None:
    ensure_dirs()
    path = LOG_DIR / f"codex-cli-agent-{dt.datetime.now().strftime('%Y%m%d')}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts_utc": utc_now(), "kind": kind, **payload}, ensure_ascii=False, sort_keys=True) + "\n")


def write_state(payload: dict[str, Any]) -> None:
    ensure_dirs()
    STATE_PATH.write_text(json.dumps({"ts_utc": utc_now(), **payload}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def run_cmd(command: list[str], timeout: int = 600, stdin_text: str | None = None) -> dict[str, Any]:
    try:
        done = subprocess.run([str(part) for part in command], cwd=str(ROOT), text=True, input=stdin_text, capture_output=True, check=False, timeout=timeout)
        return {"command": command, "returncode": done.returncode, "stdout_tail": done.stdout.strip()[-4000:], "stderr_tail": done.stderr.strip()[-4000:]}
    except Exception as exc:
        return {"command": command, "returncode": 127, "stdout_tail": "", "stderr_tail": repr(exc)}


def git_ref() -> dict[str, str]:
    dot = ROOT / ".git"
    if dot.is_file():
        text = dot.read_text(encoding="utf-8", errors="replace").strip()
        if text.startswith("gitdir:"):
            dot = (ROOT / text.split(":", 1)[1].strip()).resolve()
    if not dot.exists():
        return {"head": "git-unavailable", "branch": "unknown"}
    head_file = dot / "HEAD"
    if not head_file.exists():
        return {"head": "git-unavailable", "branch": "unknown"}
    text = head_file.read_text(encoding="utf-8", errors="replace").strip()
    if text.startswith("ref:"):
        ref = text.split(":", 1)[1].strip()
        branch = ref.removeprefix("refs/heads/")
        ref_file = dot / ref
        if ref_file.exists():
            return {"head": ref_file.read_text(encoding="utf-8", errors="replace").strip()[:12], "branch": branch}
        return {"head": "head-ref-unresolved", "branch": branch}
    return {"head": text[:12], "branch": "detached"}


def status_payload() -> dict[str, Any]:
    return {"root": str(ROOT), "git": git_ref(), "bridge_configured": bool(os.environ.get("CODEX_CHAT_BRIDGE_CMD")), "state": str(STATE_PATH)}


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def call_bridge(prompt: str) -> dict[str, Any]:
    bridge = os.environ.get("CODEX_CHAT_BRIDGE_CMD", "").strip()
    context = {"status": status_payload(), "prompt": prompt}
    if not bridge:
        return {"ok": False, "mode": "local-only", "answer": "No bridge command configured. Use /plan or /run for repository tasks."}
    result = run_cmd(shlex.split(bridge), stdin_text=json.dumps(context, ensure_ascii=False))
    return {"ok": result["returncode"] == 0, "mode": "bridge", "result": result}


def task_engine(mode: str, text: str) -> dict[str, Any]:
    return run_cmd(["python3", "scripts/ashell_task_engine.py", mode, *text.split()])


def help_lines() -> list[str]:
    return [
        "/help                 show commands",
        "/status               show agent state",
        "/inventory            create SHA-256 inventory for every repo file",
        "/plan <task>          transform task into an allowlisted plan",
        "/run <task>           execute transformed task and validations",
        "/ask <prompt>         use bridge when configured, otherwise local-only notice",
        "/api-plan             show API target plan",
        "/api-probe            probe explicit API targets",
        "/gate                 run unified local gate",
        "/evidence             create snapshot and backup evidence",
        "/exit                 quit",
    ]


def render_header() -> None:
    info = status_payload()
    print("╭────────────────────────────────────────────╮")
    print("│ upgraded-fiesta · a-Shell Codex CLI Agent  │")
    print("╰────────────────────────────────────────────╯")
    print(f"root   : {info['root']}")
    print(f"head   : {info['git']['head']}  branch: {info['git']['branch']}")
    print(f"bridge : {'configured' if info['bridge_configured'] else 'local-only'}")
    print("type /help")


def handle(line: str) -> bool:
    line = line.strip()
    if not line:
        return True
    append_log("input", {"line": line[:1000]})
    if line in {"/exit", "exit", "quit"}:
        return False
    if line in {"/help", "help", "?"}:
        for item in help_lines():
            print(item)
        return True
    if line == "/status":
        print_json(status_payload())
        return True
    if line == "/inventory":
        print_json(run_cmd(["python3", "scripts/ashell_repo_byte_inventory.py", "generate"]))
        return True
    if line.startswith("/plan "):
        print_json(task_engine("plan", line[len("/plan "):].strip()))
        return True
    if line.startswith("/run "):
        print_json(task_engine("run", line[len("/run "):].strip()))
        return True
    if line.startswith("/ask "):
        print_json(call_bridge(line[len("/ask "):].strip()))
        return True
    if line == "/api-plan":
        print_json(run_cmd(["python3", "scripts/ashell_api_surface.py", "plan"]))
        return True
    if line == "/api-probe":
        print_json(run_cmd(["python3", "scripts/ashell_api_surface.py", "probe"]))
        return True
    if line == "/gate":
        print_json(run_cmd(["python3", "scripts/ashell_gate.py"]))
        return True
    if line == "/evidence":
        print_json(run_cmd(["python3", "scripts/ashell_flowctl.py", "run", "evidence"]))
        return True
    if line.startswith("/"):
        print_json({"ok": False, "detail": "unknown command", "hint": "/help"})
        return True
    print_json(task_engine("plan", line))
    return True


def interactive() -> int:
    ensure_dirs()
    render_header()
    while True:
        try:
            line = input("codex> ")
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print("\ninterrupt")
            continue
        if not handle(line):
            write_state({"last": "exit"})
            return 0


def self_test() -> int:
    assert CONFIG_PATH.exists()
    inv = run_cmd(["python3", "scripts/ashell_repo_byte_inventory.py", "self-test"])
    assert inv["returncode"] == 0
    write_state({"self_test": True})
    print("ashell codex cli agent self-test ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Unified a-Shell Codex CLI agent.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    sub.add_parser("chat")
    sub.add_parser("inventory")
    args = parser.parse_args(argv)
    if args.command == "self-test":
        return self_test()
    if args.command == "chat":
        return interactive()
    if args.command == "inventory":
        print_json(run_cmd(["python3", "scripts/ashell_repo_byte_inventory.py", "generate"]))
        return 0
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
