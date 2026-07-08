#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "releases" / "v1" / "released-fullworking-system.manifest.json"
SCHEMA = "released-fullworking-system.manifest.v1"


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


def repo_path(raw: str) -> Path:
    path = ROOT / raw
    return path.resolve()


def valid_repo_relative(raw: Any) -> bool:
    if not isinstance(raw, str) or not raw:
        return False
    path = Path(raw)
    return not path.is_absolute() and ".." not in path.parts


def validate_paths(items: Any, label: str) -> list[str]:
    findings: list[str] = []
    if not isinstance(items, list) or not items:
        return [f"{label} must be non-empty list"]
    for item in items:
        if not valid_repo_relative(item):
            findings.append(f"{label}: invalid repo-relative path: {item!r}")
            continue
        if not repo_path(item).is_file():
            findings.append(f"{label}: missing file: {item}")
    return findings


def validate_manifest(manifest: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    findings: list[str] = []
    warnings: list[str] = []

    if manifest.get("schema") != SCHEMA:
        findings.append(f"schema must be {SCHEMA}")
    product = manifest.get("product")
    if not isinstance(product, dict):
        findings.append("product must be object")
    else:
        if product.get("version") != "v1":
            findings.append("product.version must be v1")
        if product.get("enterprise_first_mobile") is not True:
            findings.append("product.enterprise_first_mobile must be true")
        if product.get("default_branch") != "main":
            findings.append("product.default_branch must be main")

    state = manifest.get("release_state")
    if not isinstance(state, dict):
        findings.append("release_state must be object")
    else:
        required_true = [
            "code_contract_complete",
            "formative_documents_complete",
            "machine_objects_complete",
            "workflow_gates_complete",
            "runtime_artifact_proof_required",
        ]
        for key in required_true:
            if state.get(key) is not True:
                findings.append(f"release_state.{key} must be true")
        if state.get("runtime_artifact_proof_currently_embedded") is not False:
            findings.append("release_state.runtime_artifact_proof_currently_embedded must be false in source manifest")
        if state.get("fullworking_runtime_claim_allowed_without_artifact") is not False:
            findings.append("release_state.fullworking_runtime_claim_allowed_without_artifact must be false")

    findings.extend(validate_paths(manifest.get("required_formative_documents"), "required_formative_documents"))
    findings.extend(validate_paths(manifest.get("required_machine_objects"), "required_machine_objects"))
    findings.extend(validate_paths(manifest.get("required_validators"), "required_validators"))
    findings.extend(validate_paths(manifest.get("required_workflows"), "required_workflows"))

    artifacts = manifest.get("required_runtime_artifacts_for_100_percent_fullworking_proof")
    if not isinstance(artifacts, list) or not artifacts:
        findings.append("required_runtime_artifacts_for_100_percent_fullworking_proof must be non-empty list")
    elif not all(isinstance(item, str) and item for item in artifacts):
        findings.append("runtime artifact names must be non-empty strings")

    boundaries = manifest.get("execution_boundaries")
    if not isinstance(boundaries, dict):
        findings.append("execution_boundaries must be object")
    else:
        for key in ("secret_read_allowed", "remote_shell_allowed", "destructive_execution_allowed", "arbitrary_shell_allowed"):
            if boundaries.get(key) is not False:
                findings.append(f"execution_boundaries.{key} must be false")
        if boundaries.get("artifact_evidence_required_for_final_claim") is not True:
            findings.append("execution_boundaries.artifact_evidence_required_for_final_claim must be true")

    return not findings, findings, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate v1 released fullworking system source contract.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path
    manifest = load_json(manifest_path)
    ok, findings, warnings = validate_manifest(manifest)
    result = {
        "schema": "released-fullworking-system.validation.v1",
        "ok": ok,
        "manifest": str(manifest_path.relative_to(ROOT) if manifest_path.is_relative_to(ROOT) else manifest_path),
        "runtime_artifact_proof_required": True,
        "runtime_artifact_proof_embedded": False,
        "findings": findings,
        "warnings": warnings,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
