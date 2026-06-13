#!/usr/bin/env python3
"""Validate and export CLI readiness material."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "settings" / "mobile-production" / "cli-ai-readiness.json"
DATA_DIR = ROOT / "datasets" / "mobile-production"
CAPABILITY_PATH = DATA_DIR / "cli_ai_capabilities.tsv"
RESEARCH_PATH = DATA_DIR / "research_branches.tsv"
DEV_ROOT = Path.home() / "Documents" / "Developer"
EXPORT_DIR = DEV_ROOT / "exports"
RUN_DIR = DEV_ROOT / "runs"
STATE_PATH = RUN_DIR / "cli-readiness-state.json"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S")


def ensure_dirs() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def validate() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    ok = True
    if MODEL_PATH.exists():
        model = read_json(MODEL_PATH)
        findings.append({"id": "model", "ok": bool(model.get("capability_gaps") and model.get("research_branches")), "detail": {"capability_gaps": len(model.get("capability_gaps", [])), "research_branches": len(model.get("research_branches", []))}})
        ok = ok and bool(model.get("capability_gaps") and model.get("research_branches"))
    else:
        findings.append({"id": "model", "ok": False, "detail": "missing"})
        ok = False
    for path in [CAPABILITY_PATH, RESEARCH_PATH]:
        if not path.exists():
            findings.append({"id": path.name, "ok": False, "detail": "missing"})
            ok = False
            continue
        rows = read_tsv(path)
        findings.append({"id": path.name, "ok": bool(rows), "detail": {"rows": len(rows)}})
        ok = ok and bool(rows)
    payload = {"ok": ok, "findings": findings}
    ensure_dirs()
    STATE_PATH.write_text(json.dumps({"ts_utc": utc_now(), **payload}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def markdown(validation: dict[str, Any]) -> str:
    capabilities = read_tsv(CAPABILITY_PATH)
    branches = read_tsv(RESEARCH_PATH)
    lines = [
        "# CLI Readiness Report",
        "",
        f"Generated: {utc_now()}",
        "",
        "## Validation",
        "",
        f"- ok: `{validation['ok']}`",
        "",
        "## Capabilities",
        "",
        "| id | capability | existing | missing | implementation | verification | status |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in capabilities:
        lines.append(f"| {row['id']} | {row['capability']} | {row['existing']} | {row['missing']} | {row['implementation_example']} | `{row['verification']}` | {row['status']} |")
    lines.extend(["", "## Research Branches", "", "| id | branch | unfinished problem | mobile implementation | value |", "| --- | --- | --- | --- | --- |"])
    for row in branches:
        lines.append(f"| {row['id']} | {row['branch']} | {row['unfinished_problem']} | {row['direct_mobile_implementation']} | {row['production_value']} |")
    lines.append("")
    return "\n".join(lines)


def generate() -> int:
    validation = validate()
    ensure_dirs()
    base = EXPORT_DIR / f"cli-readiness-{stamp()}"
    md_path = base.with_suffix(".md")
    json_path = base.with_suffix(".json")
    md_path.write_text(markdown(validation), encoding="utf-8")
    json_path.write_text(json.dumps({"validation": validation, "model": read_json(MODEL_PATH)}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": validation["ok"], "markdown": str(md_path), "json": str(json_path)}, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if validation["ok"] else 1


def self_test() -> int:
    payload = validate()
    print("ashell readiness report self-test ok")
    return 0 if payload["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and export CLI readiness material.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    sub.add_parser("validate")
    sub.add_parser("generate")
    args = parser.parse_args(argv)
    if args.command == "self-test":
        return self_test()
    if args.command == "validate":
        print(json.dumps(validate(), indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "generate":
        return generate()
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
