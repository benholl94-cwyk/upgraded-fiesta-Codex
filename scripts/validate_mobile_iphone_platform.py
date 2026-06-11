#!/usr/bin/env python3
"""Validate the mobile iPhone control-plane settings and datasets."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "settings" / "mobile-iphone-platform"
DATASETS = ROOT / "datasets" / "mobile-iphone-platform"

REQUIRED_JSON = {
    SETTINGS / "settings.json": ["schema_version", "platform", "directory_contract", "quality_gates"],
    SETTINGS / "shortcuts.catalog.json": ["schema_version", "shortcuts"],
}

REQUIRED_CSV_COLUMNS = {
    DATASETS / "apps.csv": ["app_id", "role", "required", "primary_data_boundary", "automation_surface", "production_use", "hard_limit"],
    DATASETS / "workflows.csv": ["workflow_id", "name", "trigger", "controller", "executor", "input_dataset", "output_artifact", "required_gate", "rollback"],
    DATASETS / "repositories.csv": ["repo_id", "provider", "remote_url", "default_branch", "local_owner_app", "editor_app", "test_command", "ci_required", "deployable", "notes"],
    DATASETS / "commands.csv": ["command_id", "workflow_id", "run_location", "command", "success_signal", "timeout_seconds", "log_path"],
    DATASETS / "remote-hosts.csv": ["host_id", "purpose", "ssh_alias", "required_auth", "allowed_workflows", "network_requirement", "notes"],
    DATASETS / "deployments.csv": ["deployment_id", "repo_id", "environment", "deploy_controller", "deploy_command", "healthcheck_url", "rollback_command", "approval_required"],
    DATASETS / "backup-policy.csv": ["asset", "source", "backup_target", "frequency", "retention", "verification"],
    DATASETS / "secret-inventory.template.csv": ["secret_id", "system", "owner", "storage_location", "scope", "rotation_days", "last_rotated", "next_rotation", "status"],
    DATASETS / "runbook-checks.csv": ["check_id", "workflow_id", "check", "pass_condition", "fail_action"],
}


def validate_json(path: Path, required_keys: list[str]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in required_keys if key not in data]
    if missing:
        raise SystemExit(f"{path}: missing keys {missing}")
    if path.name == "settings.json":
        forbidden = data["directory_contract"].get("forbidden_patterns", [])
        if not any(".env" in pattern for pattern in forbidden):
            raise SystemExit(f"{path}: .env must be forbidden")
    if path.name == "shortcuts.catalog.json" and not data["shortcuts"]:
        raise SystemExit(f"{path}: shortcuts must not be empty")


def validate_csv(path: Path, required_columns: list[str]) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != required_columns:
            raise SystemExit(f"{path}: expected columns {required_columns}, got {reader.fieldnames}")
        rows = list(reader)
    if not rows:
        raise SystemExit(f"{path}: must contain at least one row")
    for index, row in enumerate(rows, start=2):
        empty = [column for column in required_columns if not row.get(column)]
        if empty:
            raise SystemExit(f"{path}:{index}: empty required values {empty}")


def main() -> None:
    for path, keys in REQUIRED_JSON.items():
        validate_json(path, keys)
    for path, columns in REQUIRED_CSV_COLUMNS.items():
        validate_csv(path, columns)
    print("mobile iPhone platform settings and datasets are valid")


if __name__ == "__main__":
    main()
