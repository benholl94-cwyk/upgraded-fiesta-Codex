#!/usr/bin/env python3
"""Non-destructive rebase/build guard for the one-repo control plane.

The guard validates that the repository-synthesis dataset reflects the post-merge
state and that no destructive source-repository overwrite mode is enabled.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "datasets" / "repository-synthesis.dataset.json"
REQUIRED_COMPONENTS = {
    "scripts/full_debug.py",
    "scripts/init_github_repo.py",
    "scripts/rebase_guard.py",
    ".github/workflows/full-debug.yml",
    "docs/full-debug-runbook.md",
    "docs/one-repo-synthesis-audit.md",
    "docs/rebase-build-audit.md",
    "Makefile",
}
FORBIDDEN_TRUE_FLAGS = (
    "destructive_overwrite_performed",
    "secrets_copied",
    "source_repositories_deleted_or_archived",
)


def fail(message: str) -> int:
    print(json.dumps({"ok": False, "error": message}, indent=2, sort_keys=True))
    return 1


def load_dataset() -> dict[str, Any]:
    if not DATASET.is_file():
        raise FileNotFoundError(f"missing dataset: {DATASET.relative_to(ROOT)}")
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("dataset root must be an object")
    return payload


def main() -> int:
    try:
        data = load_dataset()
    except Exception as exc:
        return fail(str(exc))

    errors: list[str] = []
    if data.get("schema") != "upgraded-fiesta.repository-synthesis.v1":
        errors.append("unexpected dataset schema")

    audit = data.get("audit_status", {})
    if not isinstance(audit, dict):
        errors.append("audit_status must be an object")
    else:
        for flag in FORBIDDEN_TRUE_FLAGS:
            if audit.get(flag) is True:
                errors.append(f"forbidden audit flag is true: {flag}")

    cleanup = data.get("rest_order_cleanup", {})
    if not isinstance(cleanup, dict):
        errors.append("rest_order_cleanup must be an object")
    else:
        open_prs = cleanup.get("open_pull_requests_found")
        if open_prs not in ([], None):
            errors.append(f"open_pull_requests_found must be empty after cleanup, got: {open_prs}")
        if cleanup.get("active_pull_request") not in (None, 0, "none"):
            errors.append("active_pull_request must be null/none after merge")

    components = set(data.get("validated_target_components", []))
    missing_components = sorted(REQUIRED_COMPONENTS - components)
    for component in missing_components:
        errors.append(f"dataset missing validated component: {component}")
    for component in REQUIRED_COMPONENTS:
        if not (ROOT / component).is_file():
            errors.append(f"required component file missing: {component}")

    result = {
        "schema": "upgraded-fiesta.rebase-guard.v1",
        "ok": not errors,
        "checked_dataset": DATASET.relative_to(ROOT).as_posix(),
        "required_components": sorted(REQUIRED_COMPONENTS),
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
