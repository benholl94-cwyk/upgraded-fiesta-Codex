#!/usr/bin/env python3
"""Modern single-line interactive dev console for a-Shell."""

from __future__ import annotations

import datetime as dt
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "settings" / "mobile-production" / "dev-console.json"
DEV_ROOT = Path.home() / "Documents" / "Developer"
RUN_DIR = DEV_ROOT / "runs"
LOG_DIR = DEV_ROOT / "logs"
STATE_PATH = RUN_DIR / "dev-console-state.json"
MAX_LINES = 10


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dirs() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def command_map() -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in load_config().get("commands", [])}


def append_log(kind: str, payload: dict[str, Any]) -> None:
    ensure_dirs()
    path = LOG_DIR / f"dev-console-{dt.datetime.now().strftime('%Y%m%d')}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts_utc": utc_now(), "kind": kind, **payload}, ensure_ascii=False, sort_keys=True) + "\n")


def write_state(payload: dict[str, Any]) -> None:
    ensure_dirs()
    STATE_PATH.write_text(json.dumps({"ts_utc": utc_now(), **payload}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def git_ref() -> tuple[str, str]:
    dot = ROOT / ".git"
    if dot.is_file():
        text = dot.read_text(encoding="utf-8", errors="replace").strip()
        if text.startswith("gitdir:"):
            dot = (ROOT / text.split(":", 1)[1].strip()).resolve()
    if not dot.exists():
        return "git-unavailable", "unknown"
    head_file = dot / "HEAD"
    if not head_file.exists():
        return "git-unavailable", "unknown"
    text = head_file.read_text(encoding="utf-8", errors="replace").strip()
    if text.startswith("ref:"):
        ref = text.split(":", 1)[1].strip()
        branch = ref.removeprefix("refs/heads/")
        ref_file = dot / ref
        if ref_file.exists():
            return ref_file.read_text(encoding="utf-8", errors="replace").strip()[:12], branch
        return "head-ref-unresolved", branch
    return text[:12], "detached"


def quick_findings() -> list[str]:
    findings: list[str] = []
    if (ROOT / "manifest. webmanifest").exists():
        findings.append("spaced manifest copy detected")
    if (ROOT / "key.sh").exists():
        findings.append("local key helper present")
    if not os.environ.get("CODEX_CHAT_BRIDGE_CMD"):
        findings.append("bridge local-only")
    return findings


def ansi_clear() -> str:
    return "\033[2J\033[H" if sys.stdout.isatty() else ""


def render(title: str, task: str, lines: list[str], status: str = "ready") -> None:
    head, branch = git_ref()
    findings = quick_findings()
    print(ansi_clear(), end="")
    print("╭────────────────────────────────────────────╮")
    print("│ upgraded-fiesta · Mobile Dev Console       │")
    print("╰────────────────────────────────────────────╯")
    print(f"root   : {ROOT}")
    print(f"head   : {head}  branch: {branch}")
    print(f"status : {status}  task: {task or 'none'}")
    if findings:
        print("issues : " + "; ".join(findings[:3]))
    print("─" * 48)
    print(title or "Live task monitor")
    shown = lines[-MAX_LINES:] if lines else ["no output yet"]
    for line in shown:
        print("  " + line[:180])
    print("─" * 48)
    print("commands: /help /status /gate /api-plan /api-probe /loop-once /maintain /friction /evidence /ls /fix-manifest /clear /exit")


def run_stream(command: list[str], label: str) -> int:
    lines: list[str] = []
    append_log("task-start", {"label": label, "command": command})
    render("Live task monitor", label, lines, "running")
    process = subprocess.Popen(command, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert process.stdout is not None
    for raw in process.stdout:
        line = raw.rstrip("\n")
        lines.append(line)
        render("Live task monitor", label, lines, "running")
    returncode = process.wait()
    lines.append(f"exit={returncode}")
    render("Live task monitor", label, lines, "ok" if returncode == 0 else "failed")
    append_log("task-end", {"label": label, "command": command, "returncode": returncode, "tail": lines[-MAX_LINES:]})
    write_state({"last_task": label, "returncode": returncode, "tail": lines[-MAX_LINES:]})
    return returncode


def help_text() -> list[str]:
    commands = command_map()
    lines = ["single-line console; every mapped task runs from repo root"]
    for key in sorted(commands):
        lines.append(f"{key} — {commands[key].get('title', '')}")
    lines.extend([
        "/ls — show top-level files",
        "/fix-manifest — move spaced manifest copy to quarantine if canonical manifest exists",
        "plain text — if bridge is unset, stored as local prompt note",
    ])
    return lines


def list_files() -> list[str]:
    return sorted(path.name for path in ROOT.iterdir())


def fix_manifest() -> list[str]:
    bad = ROOT / "manifest. webmanifest"
    good = ROOT / "manifest.webmanifest"
    if not bad.exists():
        return ["no spaced manifest copy found"]
    if not good.exists():
        return ["cannot fix: canonical manifest.webmanifest is missing"]
    target_dir = DEV_ROOT / "quarantine" / "upgraded-fiesta"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"manifest-spaced-{dt.datetime.now().strftime('%Y%m%dT%H%M%S')}.webmanifest"
    bad.replace(target)
    append_log("fix", {"id": "spaced-manifest", "target": str(target)})
    return [f"moved manifest. webmanifest to {target}"]


def local_prompt_note(text: str) -> list[str]:
    append_log("prompt", {"text": text[:800]})
    return ["bridge is local-only; prompt logged as operator note", "set CODEX_CHAT_BRIDGE_CMD outside repo for model-backed answers"]


def handle(command: str) -> bool:
    command = command.strip()
    if not command:
        return True
    mapped = command_map()
    if command in {"/exit", "exit", "quit"}:
        return False
    if command in {"/clear", "clear"}:
        render("Live task monitor", "clear", ["screen cleared"], "ready")
        return True
    if command in {"/help", "help", "?"}:
        render("Help", "help", help_text(), "ready")
        return True
    if command in {"/ls", "ls", "Ls"}:
        note = "Use lowercase ls in shell; /ls works inside console."
        render("Files", "ls", [note, *list_files()], "ready")
        return True
    if command in {"/fix-manifest"}:
        render("Fix", "fix-manifest", fix_manifest(), "ready")
        return True
    if command in mapped:
        run_stream([str(part) for part in mapped[command]["exec"]], command)
        return True
    if command.startswith("/"):
        render("Unknown command", command, ["unknown command", "use /help"], "failed")
        return True
    render("Prompt", "note", local_prompt_note(command), "ready")
    return True


def self_test() -> int:
    assert CONFIG_PATH.exists()
    assert command_map()
    ensure_dirs()
    write_state({"self_test": True, "commands": sorted(command_map())})
    print("ashell dev console self-test ok")
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        return self_test()
    ensure_dirs()
    render("Live task monitor", "startup", ["console ready", "type /help"], "ready")
    while True:
        try:
            command = input("dev> ")
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print("\ninterrupt")
            continue
        if not handle(command):
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
