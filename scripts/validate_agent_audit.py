#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = ROOT / "config" / "agent-objectives.audit.json"
DEFAULT_ROUTES = ROOT / "config" / "ops-route-matrix.example.json"

ALLOWED_SCHEMA = "hm-agent.objectives.audit.v1"
ALLOWED_DECISIONS = {
    "allow_local",
    "parse_only",
    "blocked_until_reviewed_guard",
    "blocked_until_declared_targets",
}
ID_PATTERN = re.compile(r"^A[0-9]{2}_[A-Z0-9_]+$")


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"json root must be an object: {path}")
    return data


def validate_agent_audit(audit: dict[str, Any], routes: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    findings: list[str] = []
    warnings: list[str] = []

    if audit.get("schema") != ALLOWED_SCHEMA:
        findings.append(f"schema must be {ALLOWED_SCHEMA}")
    if audit.get("agent_component") != "hm-agent":
        findings.append("agent_component must be hm-agent")
    if audit.get("remote_execution_performed") is not False:
        findings.append("remote_execution_performed must be false")
    if audit.get("destructive_execution_performed") is not False:
        findings.append("destructive_execution_performed must be false")

    required_fields = audit.get("required_objective_fields")
    if not isinstance(required_fields, list) or not required_fields:
        findings.append("required_objective_fields must be a non-empty list")
        required_fields = []

    route_ids = set()
    route_list = routes.get("routes")
    if isinstance(route_list, list):
        for route in route_list:
            if isinstance(route, dict) and isinstance(route.get("id"), str):
                route_ids.add(route["id"])
    else:
        findings.append("route matrix must contain routes list")

    objectives = audit.get("objectives")
    if not isinstance(objectives, list) or not objectives:
        findings.append("objectives must be a non-empty list")
        objectives = []

    seen_ids: set[str] = set()
    seen_routes: set[str] = set()
    for index, objective in enumerate(objectives):
        if not isinstance(objective, dict):
            findings.append(f"objective[{index}] must be an object")
            continue

        missing = [field for field in required_fields if field not in objective]
        if missing:
            findings.append(f"objective[{index}] missing fields: {', '.join(missing)}")

        objective_id = objective.get("id")
        if not isinstance(objective_id, str) or not ID_PATTERN.match(objective_id):
            findings.append(f"objective[{index}] invalid id: {objective_id!r}")
        elif objective_id in seen_ids:
            findings.append(f"duplicate objective id: {objective_id}")
        elif objective_id:
            seen_ids.add(objective_id)

        route_id = objective.get("route_id")
        if not isinstance(route_id, str):
            findings.append(f"{objective_id or index}: route_id must be a string")
        else:
            seen_routes.add(route_id)
            if route_id not in route_ids:
                findings.append(f"{objective_id or index}: route_id not found in route matrix: {route_id}")

        decision = objective.get("decision")
        if decision not in ALLOWED_DECISIONS:
            findings.append(f"{objective_id or index}: unsupported decision: {decision}")

        for boolean_field in ("evidence_required", "remote", "destructive"):
            if not isinstance(objective.get(boolean_field), bool):
                findings.append(f"{objective_id or index}: {boolean_field} must be boolean")

        if objective.get("remote") is not False:
            findings.append(f"{objective_id or index}: remote must be false")
        if objective.get("destructive") is not False:
            findings.append(f"{objective_id or index}: destructive must be false")

        evidence_path = objective.get("evidence_path")
        if not isinstance(evidence_path, str) or not evidence_path.strip():
            findings.append(f"{objective_id or index}: evidence_path must be a non-empty string")
        elif evidence_path.startswith("/") or ".." in Path(evidence_path).parts:
            findings.append(f"{objective_id or index}: evidence_path must be repository-relative")

        metric = objective.get("success_metric")
        if not isinstance(metric, str) or not metric.strip():
            findings.append(f"{objective_id or index}: success_metric must be non-empty")

    missing_route_objectives = sorted(route_ids - seen_routes)
    if missing_route_objectives:
        warnings.append("routes without objective mapping: " + ", ".join(missing_route_objectives))

    return not findings, findings, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate hm-agent objective audit data.")
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT))
    parser.add_argument("--routes", default=str(DEFAULT_ROUTES))
    args = parser.parse_args()

    audit_path = Path(args.audit)
    route_path = Path(args.routes)
    if not audit_path.is_absolute():
        audit_path = ROOT / audit_path
    if not route_path.is_absolute():
        route_path = ROOT / route_path

    audit = load_json(audit_path)
    routes = load_json(route_path)
    ok, findings, warnings = validate_agent_audit(audit, routes)
    result = {
        "ok": ok,
        "audit": str(audit_path.relative_to(ROOT) if audit_path.is_relative_to(ROOT) else audit_path),
        "routes": str(route_path.relative_to(ROOT) if route_path.is_relative_to(ROOT) else route_path),
        "findings": findings,
        "warnings": warnings,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
