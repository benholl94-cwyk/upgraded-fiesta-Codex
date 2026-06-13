#!/usr/bin/env python3
"""Generate and validate production graph reports for the a-Shell environment."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "settings" / "mobile-production" / "production-graph.json"
DATA_DIR = ROOT / "datasets" / "mobile-production"
DEV_ROOT = Path.home() / "Documents" / "Developer"
EXPORT_DIR = DEV_ROOT / "exports"
RUN_DIR = DEV_ROOT / "runs"
STATE_PATH = RUN_DIR / "production-graph-report-state.json"
REQUIRED_DATASETS = [
    DATA_DIR / "requirements.tsv",
    DATA_DIR / "external_targets.tsv",
    DATA_DIR / "runbook_steps.tsv",
]


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
    if not GRAPH_PATH.exists():
        findings.append({"id": "graph", "ok": False, "detail": "missing production graph"})
        ok = False
    else:
        graph = read_json(GRAPH_PATH)
        node_ids = [node.get("id") for node in graph.get("nodes", [])]
        if len(node_ids) != len(set(node_ids)):
            findings.append({"id": "graph-nodes", "ok": False, "detail": "duplicate node ids"})
            ok = False
        edge_missing = []
        node_set = set(node_ids)
        for edge in graph.get("edges", []):
            if edge.get("from") not in node_set or edge.get("to") not in node_set:
                edge_missing.append(edge)
        if edge_missing:
            findings.append({"id": "graph-edges", "ok": False, "detail": edge_missing})
            ok = False
        findings.append({"id": "graph", "ok": True, "detail": {"nodes": len(node_ids), "edges": len(graph.get("edges", []))}})
    for dataset in REQUIRED_DATASETS:
        if not dataset.exists():
            findings.append({"id": dataset.name, "ok": False, "detail": "missing"})
            ok = False
            continue
        rows = read_tsv(dataset)
        findings.append({"id": dataset.name, "ok": bool(rows), "detail": {"rows": len(rows)}})
        ok = ok and bool(rows)
    payload = {"ok": ok, "findings": findings}
    ensure_dirs()
    STATE_PATH.write_text(json.dumps({"ts_utc": utc_now(), **payload}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def mermaid(graph: dict[str, Any]) -> str:
    labels = {node["id"]: node["id"] for node in graph.get("nodes", [])}
    lines = ["flowchart TD"]
    for node in graph.get("nodes", []):
        node_id = node["id"].replace("-", "_")
        label = f"{node['id']}\\n{node.get('type', '')}\\n{node.get('status', '')}"
        lines.append(f"  {node_id}[\"{label}\"]")
    for edge in graph.get("edges", []):
        left = edge["from"].replace("-", "_")
        right = edge["to"].replace("-", "_")
        relation = edge.get("type", "links")
        lines.append(f"  {left} -->|{relation}| {right}")
    return "\n".join(lines) + "\n"


def markdown_report(graph: dict[str, Any], validation: dict[str, Any]) -> str:
    reqs = read_tsv(DATA_DIR / "requirements.tsv")
    runbook = read_tsv(DATA_DIR / "runbook_steps.tsv")
    out = [
        "# Mobile Production Development Graph",
        "",
        f"Generated: {utc_now()}",
        "",
        "## Validation",
        "",
        f"- ok: `{validation['ok']}`",
        "",
        "## Mermaid",
        "",
        "```mermaid",
        mermaid(graph).rstrip(),
        "```",
        "",
        "## Requirements",
        "",
        "| id | requirement | existing | gap | tool | status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in reqs:
        out.append(f"| {row['id']} | {row['requirement']} | {row['existing_component']} | {row['gap']} | {row['completion_tool']} | {row['status']} |")
    out.extend(["", "## Runbook", "", "| id | phase | input | tool | output | verification |", "| --- | --- | --- | --- | --- | --- |"])
    for row in runbook:
        out.append(f"| {row['id']} | {row['phase']} | {row['input']} | {row['tool']} | {row['output']} | {row['verification']} |")
    out.append("")
    return "\n".join(out)


def generate() -> int:
    validation = validate()
    graph = read_json(GRAPH_PATH)
    ensure_dirs()
    base = EXPORT_DIR / f"production-graph-{stamp()}"
    mermaid_path = base.with_suffix(".mmd")
    markdown_path = base.with_suffix(".md")
    json_path = base.with_suffix(".json")
    mermaid_path.write_text(mermaid(graph), encoding="utf-8")
    markdown_path.write_text(markdown_report(graph, validation), encoding="utf-8")
    json_path.write_text(json.dumps({"validation": validation, "graph": graph}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": validation["ok"], "mermaid": str(mermaid_path), "markdown": str(markdown_path), "json": str(json_path)}, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if validation["ok"] else 1


def self_test() -> int:
    payload = validate()
    assert isinstance(payload, dict)
    print("ashell graph report self-test ok")
    return 0 if payload["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate production graph reports.")
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
