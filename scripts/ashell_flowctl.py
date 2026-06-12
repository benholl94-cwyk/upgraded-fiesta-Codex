#!/usr/bin/env python3
"""Flow controller for the mobile a-Shell production environment."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FLOW_PATH = ROOT / "settings" / "mobile-production" / "flows.json"
ENV_PATH = ROOT / "settings" / "mobile-production" / "environment.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"missing {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def flow_registry() -> dict[str, Any]:
    return load_json(FLOW_PATH)


def environment_config() -> dict[str, Any]:
    return load_json(ENV_PATH)


def flows_by_id() -> dict[str, dict[str, Any]]:
    return {flow["id"]: flow for flow in flow_registry().get("flows", [])}


def command_text(command: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in command)


def list_flows() -> int:
    registry = flow_registry()
    print(registry.get("name", "flow registry"))
    for flow in registry.get("flows", []):
        print(f"- {flow['id']} [{flow.get('kind', 'flow')}]: {flow.get('title', '')}")
    return 0


def show_flow(flow_id: str) -> int:
    flow = flows_by_id().get(flow_id)
    if not flow:
        raise SystemExit(f"unknown flow: {flow_id}")
    print(json.dumps(flow, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def plan_flow(flow_id: str) -> int:
    flow = flows_by_id().get(flow_id)
    if not flow:
        raise SystemExit(f"unknown flow: {flow_id}")
    print(f"flow: {flow['id']} — {flow.get('title', '')}")
    for index, step in enumerate(flow.get("steps", []), start=1):
        runnable = "auto" if step.get("runnable") else "manual"
        print(f"{index}. {step['id']} [{runnable}] {command_text(step['command'])}")
        if step.get("reason"):
            print(f"   reason: {step['reason']}")
    return 0


def run_step(step: dict[str, Any]) -> dict[str, Any]:
    if not step.get("runnable"):
        return {"id": step.get("id"), "skipped": True, "reason": step.get("reason", "manual step")}
    done = subprocess.run([str(part) for part in step["command"]], cwd=str(ROOT), text=True, capture_output=True, check=False, timeout=300)
    return {
        "id": step.get("id"),
        "command": step.get("command"),
        "returncode": done.returncode,
        "stdout_tail": done.stdout.strip()[-1600:],
        "stderr_tail": done.stderr.strip()[-1600:],
    }


def run_flow(flow_id: str) -> int:
    flow = flows_by_id().get(flow_id)
    if not flow:
        raise SystemExit(f"unknown flow: {flow_id}")
    results = []
    exit_code = 0
    for step in flow.get("steps", []):
        result = run_step(step)
        results.append(result)
        if result.get("returncode", 0) != 0:
            exit_code = int(result.get("returncode") or 1)
            break
    print(json.dumps({"flow": flow_id, "ok": exit_code == 0, "results": results}, indent=2, ensure_ascii=False, sort_keys=True))
    return exit_code


def graph() -> int:
    env = environment_config()
    registry = flow_registry()
    nodes = []
    for component in env.get("components", []):
        nodes.append({"id": component.get("id"), "kind": component.get("kind"), "required": component.get("required")})
    edges = []
    for flow in registry.get("flows", []):
        for step in flow.get("steps", []):
            edges.append({"flow": flow["id"], "step": step["id"], "command": step.get("command", [])})
    print(json.dumps({"nodes": nodes, "edges": edges, "quality_of_life": registry.get("quality_of_life", {})}, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def shell_help() -> int:
    registry = flow_registry()
    qol = registry.get("quality_of_life", {})
    print("a-Shell command notes")
    for key, value in sorted(qol.items()):
        print(f"- {key}: {value}")
    print("\nUseful commands:")
    print("  ls -la")
    print("  python3 scripts/ashell_flowctl.py list")
    print("  python3 scripts/ashell_flowctl.py run bootstrap")
    print("  python3 scripts/ashell_flowctl.py run verify")
    print("  python3 scripts/ashell_flowctl.py run evidence")
    return 0


def self_test() -> int:
    registry = flow_registry()
    env = environment_config()
    assert registry.get("schema_version")
    assert env.get("schema_version")
    ids = [flow["id"] for flow in registry.get("flows", [])]
    assert len(ids) == len(set(ids))
    for flow in registry.get("flows", []):
        assert flow.get("steps")
        for step in flow["steps"]:
            assert isinstance(step.get("command"), list)
            assert step["command"]
    print("ashell flowctl self-test ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Flow controller for mobile a-Shell operations.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    sub.add_parser("list")
    show = sub.add_parser("show")
    show.add_argument("flow_id")
    plan = sub.add_parser("plan")
    plan.add_argument("flow_id")
    run = sub.add_parser("run")
    run.add_argument("flow_id")
    sub.add_parser("graph")
    sub.add_parser("shell-help")
    args = parser.parse_args(argv)
    if args.command == "self-test":
        return self_test()
    if args.command == "list":
        return list_flows()
    if args.command == "show":
        return show_flow(args.flow_id)
    if args.command == "plan":
        return plan_flow(args.flow_id)
    if args.command == "run":
        return run_flow(args.flow_id)
    if args.command == "graph":
        return graph()
    if args.command == "shell-help":
        return shell_help()
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
