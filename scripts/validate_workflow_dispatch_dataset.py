#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "datasets" / "workflow-dispatch.fullstacked.dataset.json"
SCHEMA = "workflow-dispatch.fullstacked.dataset.v1"
MAX_TOP_LEVEL_INPUTS = 25
MAX_INPUT_PAYLOAD_CHARS = 65535


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"json root must be object: {path}")
    return data


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"missing file: {path}") from exc


def validate_command(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        return ["command must be non-empty list"]
    if not all(isinstance(item, str) and item for item in value):
        return ["command entries must be non-empty strings"]
    denied = {"bash", "sh", "sudo", "su", "ssh", "scp", "sftp", "curl", "wget", "nc", "netcat", "socat"}
    if Path(value[0]).name in denied:
        return [f"denied executable in hard scan: {value[0]}"]
    return []


def validate_dataset(dataset: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    findings: list[str] = []
    warnings: list[str] = []
    if dataset.get("schema") != SCHEMA:
        findings.append(f"schema must be {SCHEMA}")
    repo = dataset.get("repository")
    if not isinstance(repo, dict):
        findings.append("repository must be object")
    else:
        if repo.get("default_branch") != "main":
            findings.append("repository.default_branch must be main")
        if repo.get("full_space_repo") is not True:
            findings.append("repository.full_space_repo must be true")
    model = dataset.get("dispatch_model")
    if not isinstance(model, dict):
        findings.append("dispatch_model must be object")
    else:
        semantics = model.get("official_semantics")
        if not isinstance(semantics, dict):
            findings.append("dispatch_model.official_semantics must be object")
        else:
            expected_true = [
                "workflow_dispatch_requires_workflow_on_default_branch",
                "manual_dispatch_supports_api_cli_and_ui",
                "dispatch_body_requires_ref",
                "dispatch_body_supports_inputs",
                "actions_write_permission_required_for_rest_dispatch",
            ]
            for key in expected_true:
                if semantics.get(key) is not True:
                    findings.append(f"official_semantics.{key} must be true")
            if semantics.get("max_top_level_inputs") != MAX_TOP_LEVEL_INPUTS:
                findings.append("official_semantics.max_top_level_inputs must be 25")
            if semantics.get("max_input_payload_characters") != MAX_INPUT_PAYLOAD_CHARS:
                findings.append("official_semantics.max_input_payload_characters must be 65535")
        if model.get("non_fabrication_rule") is None:
            findings.append("dispatch_model.non_fabrication_rule is required")

    targets = dataset.get("workflow_dispatch_targets")
    if not isinstance(targets, list) or not targets:
        findings.append("workflow_dispatch_targets must be non-empty list")
        targets = []
    seen_ids: set[str] = set()
    for target in targets:
        if not isinstance(target, dict):
            findings.append("workflow_dispatch_targets entries must be objects")
            continue
        target_id = target.get("id")
        if not isinstance(target_id, str) or not target_id:
            findings.append("target id must be non-empty string")
        elif target_id in seen_ids:
            findings.append(f"duplicate target id: {target_id}")
        else:
            seen_ids.add(target_id)
        workflow_file = target.get("workflow_file")
        if not isinstance(workflow_file, str) or not workflow_file.endswith((".yml", ".yaml")):
            findings.append(f"{target_id}: workflow_file must be yaml path")
            continue
        workflow_path = ROOT / workflow_file
        if not workflow_path.is_file():
            findings.append(f"{target_id}: workflow file missing: {workflow_file}")
            continue
        text = read_text(workflow_path)
        if target.get("workflow_dispatch_enabled") is True and "workflow_dispatch:" not in text:
            findings.append(f"{target_id}: workflow_dispatch not found in {workflow_file}")
        if target.get("push_trigger_enabled") is True and "push:" not in text:
            findings.append(f"{target_id}: push trigger not found in {workflow_file}")
        inputs = target.get("inputs")
        if not isinstance(inputs, dict):
            findings.append(f"{target_id}: inputs must be object")
        else:
            if len(inputs) > MAX_TOP_LEVEL_INPUTS:
                findings.append(f"{target_id}: too many inputs")
            payload_size = len(json.dumps(inputs, sort_keys=True))
            if payload_size > MAX_INPUT_PAYLOAD_CHARS:
                findings.append(f"{target_id}: inputs payload too large")
        outputs = target.get("expected_runtime_outputs")
        if not isinstance(outputs, list) or not outputs:
            findings.append(f"{target_id}: expected_runtime_outputs must be non-empty list")
        else:
            for output in outputs:
                if not isinstance(output, str) or output.startswith("/") or ".." in Path(output).parts:
                    findings.append(f"{target_id}: invalid output path: {output!r}")
        if target.get("hard_scan_after_dispatch") is not True:
            findings.append(f"{target_id}: hard_scan_after_dispatch must be true")
        if target.get("hard_scan_scope") != "full_space_repo":
            findings.append(f"{target_id}: hard_scan_scope must be full_space_repo")

    matrix = dataset.get("hard_scan_matrix")
    if not isinstance(matrix, list) or not matrix:
        findings.append("hard_scan_matrix must be non-empty list")
        matrix = []
    for item in matrix:
        if not isinstance(item, dict):
            findings.append("hard_scan_matrix entries must be objects")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            findings.append("hard_scan_matrix id must be non-empty string")
        findings.extend(f"{item_id}: {finding}" for finding in validate_command(item.get("command")))
        if item.get("required") is not True:
            warnings.append(f"{item_id}: hard scan item is not required")

    boundaries = dataset.get("execution_boundaries")
    if not isinstance(boundaries, dict):
        findings.append("execution_boundaries must be object")
    else:
        for key in ("secret_read_allowed", "remote_shell_allowed", "destructive_execution_allowed", "arbitrary_shell_allowed"):
            if boundaries.get(key) is not False:
                findings.append(f"execution_boundaries.{key} must be false")
        if boundaries.get("artifact_evidence_required_for_100_percent_proof") is not True:
            findings.append("execution_boundaries.artifact_evidence_required_for_100_percent_proof must be true")

    return not findings, findings, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate workflow-dispatch fullstacked dataset.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    args = parser.parse_args()
    dataset_path = Path(args.dataset)
    if not dataset_path.is_absolute():
        dataset_path = ROOT / dataset_path
    dataset = load_json(dataset_path)
    ok, findings, warnings = validate_dataset(dataset)
    result = {
        "schema": "workflow-dispatch.fullstacked.validation.v1",
        "ok": ok,
        "dataset": str(dataset_path.relative_to(ROOT) if dataset_path.is_relative_to(ROOT) else dataset_path),
        "findings": findings,
        "warnings": warnings,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
