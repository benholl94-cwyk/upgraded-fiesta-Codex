#!/usr/bin/env python3
"""Unified local gate for the a-Shell mobile environment."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def run(argv: list[str], timeout: int = 300) -> dict[str, Any]:
    done = subprocess.run(argv, cwd=str(ROOT), text=True, capture_output=True, check=False, timeout=timeout)
    return {
        "command": argv,
        "returncode": done.returncode,
        "stdout_tail": done.stdout.strip()[-1600:],
        "stderr_tail": done.stderr.strip()[-1600:],
    }


def gate(include_setup: bool) -> int:
    steps = [
        ["python3", "scripts/ashell_maintain.py", "plan"],
        ["python3", "scripts/ashell_flowctl.py", "self-test"],
        ["python3", "scripts/ashell_niche_nodes.py", "self-test"],
        ["python3", "scripts/ashell_production_env.py", "self-test"],
        ["python3", "scripts/ashell_loop_runtime.py", "self-test"],
        ["python3", "scripts/ashell_api_surface.py", "self-test"],
        ["python3", "scripts/ashell_dev_console.py", "--self-test"],
        ["python3", "scripts/ashell_graph_report.py", "self-test"],
        ["python3", "scripts/ashell_readiness_report.py", "self-test"],
        ["python3", "scripts/ashell_task_engine.py", "self-test"],
    ]
    if include_setup:
        steps.append(["sh", "scripts/codex_cloud_setup.sh"])
    results = []
    ok = True
    for step in steps:
        result = run(step)
        results.append(result)
        if result["returncode"] != 0:
            ok = False
            break
    print(json.dumps({"ok": ok, "results": results}, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Unified local gate for a-Shell.")
    parser.add_argument("--with-setup", action="store_true")
    args = parser.parse_args(argv)
    return gate(args.with_setup)


if __name__ == "__main__":
    raise SystemExit(main())
