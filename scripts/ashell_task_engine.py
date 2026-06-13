#!/usr/bin/env python3
"""Adaptive task transmutation engine for the mobile a-Shell environment."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "settings" / "mobile-production" / "task-engine.json"
INTENTS_PATH = ROOT / "datasets" / "mobile-production" / "task_intents.tsv"
DEV_ROOT = Path.home() / "Documents" / "Developer"
RUN_DIR = DEV_ROOT / "runs"
LOG_DIR = DEV_ROOT / "logs"
EXPORT_DIR = DEV_ROOT / "exports"
STATE_PATH = RUN_DIR / "mobile-task-engine-state.json"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S")


def ensure_dirs() -> None:
    for path in (RUN_DIR, LOG_DIR, EXPORT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_intents() -> list[dict[str, str]]:
    with INTENTS_PATH.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def append_log(kind: str, payload: dict[str, Any]) -> None:
    ensure_dirs()
    log_path = LOG_DIR / f"mobile-task-engine-{dt.datetime.now().strftime('%Y%m%d')}.jsonl"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts_utc": utc_now(), "kind": kind, **payload}, ensure_ascii=False, sort_keys=True) + "\n")


def write_state(payload: dict[str, Any]) -> None:
    ensure_dirs()
    STATE_PATH.write_text(json.dumps({"ts_utc": utc_now(), **payload}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def tokenize(text: str) -> list[str]:
    chars = []
    for char in text.lower():
        if char.isalnum() or char in {"-", "_"}:
            chars.append(char)
        else:
            chars.append(" ")
    return [part for part in "".join(chars).split() if part]


def split_commands(value: str) -> list[list[str]]:
    commands: list[list[str]] = []
    for raw in value.split(";"):
        raw = raw.strip()
        if raw:
            commands.append(raw.split())
    return commands


def score_intents(task_text: str) -> list[dict[str, Any]]:
    tokens = set(tokenize(task_text))
    results = []
    for intent in read_intents():
        keywords = set(tokenize(intent.get("keywords", "")))
        overlap = sorted(tokens & keywords)
        score = len(overlap)
        if score:
            results.append({"intent": intent, "score": score, "matched": overlap})
    results.sort(key=lambda item: (-item["score"], item["intent"]["id"]))
    return results


def context_snapshot() -> dict[str, Any]:
    head = "unknown"
    branch = "unknown"
    dot = ROOT / ".git"
    if dot.exists():
        if dot.is_file():
            text = dot.read_text(encoding="utf-8", errors="replace").strip()
            if text.startswith("gitdir:"):
                dot = (ROOT / text.split(":", 1)[1].strip()).resolve()
        head_file = dot / "HEAD"
        if head_file.exists():
            text = head_file.read_text(encoding="utf-8", errors="replace").strip()
            if text.startswith("ref:"):
                ref = text.split(":", 1)[1].strip()
                branch = ref.removeprefix("refs/heads/")
                ref_file = dot / ref
                if ref_file.exists():
                    head = ref_file.read_text(encoding="utf-8", errors="replace").strip()[:12]
            else:
                head = text[:12]
                branch = "detached"
    return {"root": str(ROOT), "head": head, "branch": branch}


def synthesize_plan(task_text: str, limit: int = 4) -> dict[str, Any]:
    config = read_json(CONFIG_PATH)
    scored = score_intents(task_text)
    chosen = scored[:limit]
    steps = []
    for item in chosen:
        intent = item["intent"]
        for command in split_commands(intent.get("commands", "")):
            steps.append({
                "intent_id": intent["id"],
                "label": intent["label"],
                "command": command,
                "mode": intent.get("mode", "read"),
                "matched": item["matched"],
            })
    validation_steps = []
    seen = set()
    for item in chosen:
        intent = item["intent"]
        for command in split_commands(intent.get("validation", "")):
            key = tuple(command)
            if key not in seen:
                validation_steps.append({"intent_id": intent["id"], "command": command})
                seen.add(key)
    plan = {
        "task": task_text,
        "config": config.get("name"),
        "context": context_snapshot(),
        "intents": [{"id": item["intent"]["id"], "label": item["intent"]["label"], "score": item["score"], "matched": item["matched"]} for item in chosen],
        "steps": steps,
        "validation_steps": validation_steps,
        "fallback": "plan-only" if not steps else "none",
    }
    return plan


def run_command(command: list[str], timeout: int = 300) -> dict[str, Any]:
    try:
        done = subprocess.run([str(part) for part in command], cwd=str(ROOT), text=True, capture_output=True, check=False, timeout=timeout)
        return {"command": command, "returncode": done.returncode, "stdout_tail": done.stdout.strip()[-2000:], "stderr_tail": done.stderr.strip()[-2000:]}
    except Exception as exc:
        return {"command": command, "returncode": 127, "stdout_tail": "", "stderr_tail": repr(exc)}


def export_report(payload: dict[str, Any]) -> str:
    ensure_dirs()
    path = EXPORT_DIR / f"mobile-task-report-{stamp()}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def execute(task_text: str, dry_run: bool = False) -> dict[str, Any]:
    plan = synthesize_plan(task_text)
    append_log("plan", {"task": task_text, "intent_count": len(plan["intents"]), "step_count": len(plan["steps"])})
    results = []
    ok = True
    if not dry_run:
        for step in plan["steps"]:
            result = run_command(step["command"])
            result["intent_id"] = step["intent_id"]
            results.append(result)
            append_log("step", {"intent_id": step["intent_id"], "returncode": result["returncode"]})
            if result["returncode"] != 0:
                ok = False
                break
        if ok:
            for step in plan["validation_steps"]:
                result = run_command(step["command"])
                result["intent_id"] = step["intent_id"]
                result["validation"] = True
                results.append(result)
                append_log("validation", {"intent_id": step["intent_id"], "returncode": result["returncode"]})
                if result["returncode"] != 0:
                    ok = False
                    break
    payload = {"ok": ok, "dry_run": dry_run, "plan": plan, "results": results}
    payload["export"] = export_report(payload)
    write_state(payload)
    return payload


def interactive() -> int:
    print("mobile task engine: type a task, /exit to quit")
    while True:
        try:
            text = input("task> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print("\ninterrupt")
            continue
        if text in {"/exit", "exit", "quit"}:
            return 0
        if not text:
            continue
        payload = execute(text, dry_run=False)
        print(json.dumps({"ok": payload["ok"], "export": payload["export"], "intents": payload["plan"]["intents"]}, indent=2, ensure_ascii=False, sort_keys=True))


def validate_assets() -> dict[str, Any]:
    findings = []
    ok = True
    for path in [CONFIG_PATH, INTENTS_PATH]:
        exists = path.exists()
        findings.append({"path": str(path.relative_to(ROOT)), "ok": exists})
        ok = ok and exists
    if INTENTS_PATH.exists():
        intents = read_intents()
        ids = [item["id"] for item in intents]
        unique = len(ids) == len(set(ids))
        findings.append({"path": "task_intents.tsv", "ok": bool(intents) and unique, "rows": len(intents), "unique_ids": unique})
        ok = ok and bool(intents) and unique
    return {"ok": ok, "findings": findings}


def self_test() -> int:
    assets = validate_assets()
    plan = synthesize_plan("generate graph report and run gate")
    assert plan["steps"]
    print("ashell task engine self-test ok")
    return 0 if assets["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adaptive task transmutation engine for a-Shell.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    sub.add_parser("validate")
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("task", nargs="+")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("task", nargs="+")
    sub.add_parser("interactive")
    args = parser.parse_args(argv)
    if args.command == "self-test":
        return self_test()
    if args.command == "validate":
        print(json.dumps(validate_assets(), indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "plan":
        payload = execute(" ".join(args.task), dry_run=True)
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "run":
        payload = execute(" ".join(args.task), dry_run=False)
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if payload["ok"] else 1
    if args.command == "interactive":
        return interactive()
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
