#!/usr/bin/env python3
"""Niche workflow nodes for the a-Shell mobile control-plane."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEV_ROOT = Path.home() / "Documents" / "Developer"
RUN_DIR = DEV_ROOT / "runs"
EXPORT_DIR = DEV_ROOT / "exports"
LOG_DIR = DEV_ROOT / "logs"
FLOW_PATH = ROOT / "settings" / "mobile-production" / "flows.json"
ENV_PATH = ROOT / "settings" / "mobile-production" / "environment.json"


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dirs() -> None:
    for path in (RUN_DIR, EXPORT_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run(argv: list[str], timeout: int = 90) -> dict[str, Any]:
    try:
        done = subprocess.run(argv, cwd=str(ROOT), text=True, capture_output=True, check=False, timeout=timeout)
        return {"command": argv, "returncode": done.returncode, "stdout": done.stdout.strip(), "stderr": done.stderr.strip()}
    except Exception as exc:
        return {"command": argv, "returncode": 127, "stdout": "", "stderr": repr(exc)}


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def git_head_from_files() -> tuple[str, str]:
    directory = ROOT / ".git"
    if not directory.exists():
        return "git-unavailable", "unknown"
    if directory.is_file():
        text = directory.read_text(encoding="utf-8", errors="replace").strip()
        if text.startswith("gitdir:"):
            directory = (ROOT / text.split(":", 1)[1].strip()).resolve()
    head_file = directory / "HEAD"
    if not head_file.exists():
        return "git-unavailable", "unknown"
    head = head_file.read_text(encoding="utf-8", errors="replace").strip()
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        branch = ref.removeprefix("refs/heads/")
        ref_file = directory / ref
        if ref_file.exists():
            return ref_file.read_text(encoding="utf-8", errors="replace").strip()[:12], branch
        return "head-ref-unresolved", branch
    return head[:12], "detached"


def base_status() -> dict[str, Any]:
    head, branch = git_head_from_files()
    status = run(["git", "status", "--short"], timeout=30)
    return {
        "ts_utc": utc_now(),
        "root": str(ROOT),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "head": head,
        "branch": branch,
        "git_status": status["stdout"] or "clean-or-unavailable",
        "bridge_configured": bool(os.environ.get("CODEX_CHAT_BRIDGE_CMD")),
    }


def friction_findings() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if (ROOT / "key.sh").exists():
        findings.append({"id": "local-key-helper", "severity": "warn", "detail": "key.sh exists locally; keep it untracked and do not paste its content."})
    if (ROOT / "manifest. webmanifest").exists():
        findings.append({"id": "spaced-manifest-copy", "severity": "warn", "detail": "manifest. webmanifest exists; expected filename is manifest.webmanifest."})
    if not (ROOT / "manifest.webmanifest").exists():
        findings.append({"id": "missing-manifest", "severity": "error", "detail": "manifest.webmanifest is missing."})
    if not os.environ.get("CODEX_CHAT_BRIDGE_CMD"):
        findings.append({"id": "bridge-local-only", "severity": "info", "detail": "Chat UI is in local monitor mode until CODEX_CHAT_BRIDGE_CMD is set."})
    for name in sorted(path.name for path in ROOT.iterdir() if " " in path.name):
        findings.append({"id": "filename-space", "severity": "warn", "detail": f"Filename contains a space: {name}"})
    return findings


def friction_scan() -> int:
    payload = {"status": base_status(), "findings": friction_findings()}
    print_json(payload)
    ensure_dirs()
    (RUN_DIR / "mobile-friction-scan.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return 1 if any(item["severity"] == "error" for item in payload["findings"]) else 0


def command_center() -> int:
    flows = read_json(FLOW_PATH).get("flows", [])
    print("Pocket Command Center")
    print("1. python3 scripts/ashell_flowctl.py run bootstrap")
    print("2. python3 scripts/ashell_flowctl.py run verify")
    print("3. python3 scripts/ashell_flowctl.py run evidence")
    print("4. python3 scripts/ashell_niche_nodes.py friction-scan")
    print("5. python3 scripts/ashell_niche_nodes.py context-pack")
    print("6. python3 scripts/ashell_production_env.py chat")
    print("7. python3 scripts/ashell_production_env.py serve --port 8001")
    print("8. python3 scripts/ashell_production_env.py monitor --interval 15")
    print("\nRegistered flows:")
    for flow in flows:
        print(f"- {flow['id']}: {flow.get('title', '')}")
    print("\na-Shell note: use ls -la instead of la or Ls.")
    return 0


def context_pack() -> int:
    ensure_dirs()
    target = EXPORT_DIR / f"mobile-context-pack-{stamp()}.json"
    payload = {
        "status": base_status(),
        "environment": read_json(ENV_PATH),
        "flows": read_json(FLOW_PATH),
        "friction": friction_findings(),
        "tree_top_level": sorted(path.name for path in ROOT.iterdir()),
        "validation": run(["sh", "scripts/codex_cloud_setup.sh"], timeout=300),
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print_json({"context_pack": str(target), "size_bytes": target.stat().st_size})
    return 0


def handoff() -> int:
    status = base_status()
    findings = friction_findings()
    next_steps = [
        "python3 scripts/ashell_flowctl.py run verify",
        "python3 scripts/ashell_flowctl.py run evidence",
        "python3 scripts/ashell_niche_nodes.py context-pack",
    ]
    if not status["bridge_configured"]:
        next_steps.append("set CODEX_CHAT_BRIDGE_CMD outside the repository before expecting model-backed chat")
    payload = {"status": status, "findings": findings, "next_steps": next_steps}
    print_json(payload)
    return 0


def alias_notes() -> int:
    print("a-Shell local convenience notes")
    print("- Use: ls -la")
    print("- If your shell supports aliases, define locally outside the repo: alias la='ls -la'")
    print("- Command names are case-sensitive: use ls, not Ls.")
    print("- Inside chat UI, use /clear, /status, /validate, /audit.")
    return 0


def self_test() -> int:
    assert FLOW_PATH.exists()
    assert ENV_PATH.exists()
    assert isinstance(friction_findings(), list)
    ensure_dirs()
    print("ashell niche nodes self-test ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Niche workflow nodes for a-Shell operations.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    sub.add_parser("friction-scan")
    sub.add_parser("command-center")
    sub.add_parser("context-pack")
    sub.add_parser("handoff")
    sub.add_parser("alias-notes")
    args = parser.parse_args(argv)
    if args.command == "self-test":
        return self_test()
    if args.command == "friction-scan":
        return friction_scan()
    if args.command == "command-center":
        return command_center()
    if args.command == "context-pack":
        return context_pack()
    if args.command == "handoff":
        return handoff()
    if args.command == "alias-notes":
        return alias_notes()
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
