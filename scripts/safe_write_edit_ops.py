#!/usr/bin/env python3
"""Production-grade safe_write/edit/ops object executor.

The tool is dependency-free and intentionally conservative:
- validates a machine-readable operation object;
- constrains all write targets to a repository-local allowlist;
- blocks credential/runtime/secrets paths;
- requires expected hashes for edits and overwrites;
- writes atomically and emits a JSON audit report.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "datasets" / "safe-write-edit-ops.policy.json"
AUDIT_ROOT = ROOT / "runs" / "safe_write_edit_ops"
BACKUP_ROOT = ROOT / ".tmp" / "safe_write_edit_ops_backups"
SCHEMA = "upgraded-fiesta.safe-write-edit-ops.v1"
CONTROL_RE = re.compile(r"[\x00-\x1f]")


class SafeOpsError(RuntimeError):
    """Raised for deterministic validation or execution failures."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SafeOpsError(f"failed to read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SafeOpsError(f"JSON root must be an object: {path}")
    return payload


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def normalize_repo_path(raw: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise SafeOpsError("path must be a non-empty string")
    if CONTROL_RE.search(raw):
        raise SafeOpsError(f"path contains control characters: {raw!r}")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise SafeOpsError(f"absolute paths are blocked: {raw}")
    if ".." in candidate.parts:
        raise SafeOpsError(f"parent traversal is blocked: {raw}")
    normalized = (ROOT / candidate).resolve()
    try:
        normalized.relative_to(ROOT)
    except ValueError as exc:
        raise SafeOpsError(f"path escapes repository root: {raw}") from exc
    return normalized


def ensure_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema") != SCHEMA:
        raise SafeOpsError(f"policy schema mismatch: expected {SCHEMA}")
    if not isinstance(policy.get("allowed_roots"), list) or not policy["allowed_roots"]:
        raise SafeOpsError("policy.allowed_roots must be a non-empty list")
    if not isinstance(policy.get("denied_globs"), list):
        raise SafeOpsError("policy.denied_globs must be a list")
    limits = policy.get("limits", {})
    if not isinstance(limits, dict):
        raise SafeOpsError("policy.limits must be an object")


def enforce_path_policy(path: Path, policy: dict[str, Any], *, role: str) -> None:
    repo_rel = rel(path)
    allowed = False
    for root in policy["allowed_roots"]:
        root_path = normalize_repo_path(str(root))
        try:
            path.relative_to(root_path)
            allowed = True
            break
        except ValueError:
            if path == root_path:
                allowed = True
                break
    if not allowed:
        raise SafeOpsError(f"{role} path is outside allowed roots: {repo_rel}")

    for pattern in policy.get("denied_globs", []):
        if fnmatch.fnmatch(repo_rel, str(pattern)):
            raise SafeOpsError(f"{role} path matches denied glob {pattern!r}: {repo_rel}")

    max_path_bytes = int(policy.get("limits", {}).get("max_path_bytes", 240))
    if len(repo_rel.encode("utf-8")) > max_path_bytes:
        raise SafeOpsError(f"{role} path exceeds max_path_bytes={max_path_bytes}: {repo_rel}")


def materialize_content(op: dict[str, Any]) -> bytes:
    if "content_utf8" in op:
        content = op["content_utf8"]
        if not isinstance(content, str):
            raise SafeOpsError("content_utf8 must be a string")
        return content.encode("utf-8")
    if "content_json" in op:
        return (json.dumps(op["content_json"], indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    raise SafeOpsError("write/append operations require content_utf8 or content_json")


def ensure_size(data: bytes, policy: dict[str, Any], label: str) -> None:
    max_file_bytes = int(policy.get("limits", {}).get("max_file_bytes", 1048576))
    if len(data) > max_file_bytes:
        raise SafeOpsError(f"{label} exceeds max_file_bytes={max_file_bytes}")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        tmp_path = Path(tmp_name)
        if tmp_path.exists():
            tmp_path.unlink()


def backup_existing(path: Path, operation_id: str) -> str | None:
    if not path.exists():
        return None
    target = BACKUP_ROOT / operation_id / rel(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        shutil.copy2(path, target)
    elif path.is_dir():
        shutil.copytree(path, target, dirs_exist_ok=True)
    return rel(target)


def validate_object(obj: dict[str, Any]) -> None:
    if obj.get("schema") != SCHEMA:
        raise SafeOpsError(f"object schema mismatch: expected {SCHEMA}")
    if not isinstance(obj.get("operation_id"), str) or not obj["operation_id"].strip():
        raise SafeOpsError("operation_id must be a non-empty string")
    if obj.get("mode") not in {"plan", "apply"}:
        raise SafeOpsError("mode must be plan or apply")
    if not isinstance(obj.get("ops"), list) or not obj["ops"]:
        raise SafeOpsError("ops must be a non-empty list")
    if len(obj["ops"]) > 200:
        raise SafeOpsError("ops exceeds hard maximum of 200 operations")
    for index, op in enumerate(obj["ops"]):
        if not isinstance(op, dict):
            raise SafeOpsError(f"ops[{index}] must be an object")
        if op.get("op") not in {"mkdir", "write_file", "append_file", "edit_replace", "copy_file", "quarantine_path"}:
            raise SafeOpsError(f"ops[{index}].op is unsupported: {op.get('op')!r}")
        if "path" not in op and op.get("op") not in {"copy_file"}:
            raise SafeOpsError(f"ops[{index}] requires path")
        if op.get("op") == "copy_file" and ("from_path" not in op or "to_path" not in op):
            raise SafeOpsError(f"ops[{index}] copy_file requires from_path and to_path")


def check_expected_hash(path: Path, expected: str | None, *, required: bool) -> None:
    actual = sha256_file(path)
    if required and not expected:
        raise SafeOpsError(f"expected_sha256 is required for {rel(path)}")
    if expected and actual != expected:
        raise SafeOpsError(f"hash mismatch for {rel(path)}: expected {expected}, actual {actual}")


def plan_or_apply(obj: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    ensure_policy(policy)
    validate_object(obj)

    operation_id = obj["operation_id"]
    apply_mode = obj["mode"] == "apply"
    results: list[dict[str, Any]] = []

    for index, op in enumerate(obj["ops"]):
        kind = op["op"]
        result: dict[str, Any] = {"index": index, "op": kind, "applied": False}

        if kind == "copy_file":
            source = normalize_repo_path(op["from_path"])
            target = normalize_repo_path(op["to_path"])
            enforce_path_policy(source, policy, role="source")
            enforce_path_policy(target, policy, role="target")
            if not source.is_file():
                raise SafeOpsError(f"copy source is not a file: {rel(source)}")
            check_expected_hash(source, op.get("expected_source_sha256"), required=bool(op.get("require_source_hash", False)))
            data = source.read_bytes()
            ensure_size(data, policy, "copy source")
            if target.exists() and not op.get("overwrite", False):
                raise SafeOpsError(f"copy target exists and overwrite=false: {rel(target)}")
            if target.exists():
                check_expected_hash(target, op.get("expected_target_sha256"), required=bool(op.get("require_target_hash", False)))
            before = sha256_file(target)
            backup = None
            if apply_mode:
                backup = backup_existing(target, operation_id)
                atomic_write(target, data)
                result["applied"] = True
            result.update({"path": rel(target), "from_path": rel(source), "before_sha256": before, "after_sha256": sha256_bytes(data), "backup": backup})

        else:
            path = normalize_repo_path(op["path"])
            enforce_path_policy(path, policy, role="target")
            result["path"] = rel(path)

            if kind == "mkdir":
                if path.exists() and not path.is_dir():
                    raise SafeOpsError(f"mkdir target exists and is not a directory: {rel(path)}")
                if apply_mode:
                    path.mkdir(parents=True, exist_ok=True)
                    result["applied"] = True
                result["after_state"] = "directory"

            elif kind == "write_file":
                data = materialize_content(op)
                ensure_size(data, policy, "write content")
                existed = path.exists()
                if existed and not op.get("overwrite", False):
                    raise SafeOpsError(f"write target exists and overwrite=false: {rel(path)}")
                if existed:
                    check_expected_hash(path, op.get("expected_sha256"), required=bool(op.get("require_hash", False)))
                before = sha256_file(path)
                backup = None
                if apply_mode:
                    backup = backup_existing(path, operation_id)
                    atomic_write(path, data)
                    result["applied"] = True
                result.update({"before_sha256": before, "after_sha256": sha256_bytes(data), "backup": backup, "bytes": len(data)})

            elif kind == "append_file":
                data = materialize_content(op)
                ensure_size(data, policy, "append content")
                before_data = path.read_bytes() if path.is_file() else b""
                if path.exists():
                    check_expected_hash(path, op.get("expected_sha256"), required=bool(op.get("require_hash", False)))
                after_data = before_data + data
                ensure_size(after_data, policy, "appended file")
                backup = None
                if apply_mode:
                    backup = backup_existing(path, operation_id)
                    atomic_write(path, after_data)
                    result["applied"] = True
                result.update({"before_sha256": sha256_bytes(before_data) if before_data else None, "after_sha256": sha256_bytes(after_data), "backup": backup, "bytes_added": len(data)})

            elif kind == "edit_replace":
                if not path.is_file():
                    raise SafeOpsError(f"edit target is not a file: {rel(path)}")
                check_expected_hash(path, op.get("expected_sha256"), required=True)
                text = path.read_text(encoding="utf-8")
                replacements = op.get("replacements")
                if not isinstance(replacements, list) or not replacements:
                    raise SafeOpsError("edit_replace requires non-empty replacements list")
                changed = text
                for repl in replacements:
                    if not isinstance(repl, dict) or not isinstance(repl.get("find"), str) or not isinstance(repl.get("replace"), str):
                        raise SafeOpsError("replacement entries require string find and replace")
                    find = repl["find"]
                    count = int(repl.get("count", -1))
                    if find not in changed:
                        raise SafeOpsError(f"edit pattern not found in {rel(path)}: {find[:80]!r}")
                    changed = changed.replace(find, repl["replace"], count if count >= 0 else changed.count(find))
                data = changed.encode("utf-8")
                ensure_size(data, policy, "edited file")
                backup = None
                if apply_mode:
                    backup = backup_existing(path, operation_id)
                    atomic_write(path, data)
                    result["applied"] = True
                result.update({"before_sha256": op.get("expected_sha256"), "after_sha256": sha256_bytes(data), "backup": backup})

            elif kind == "quarantine_path":
                if not path.exists():
                    raise SafeOpsError(f"quarantine target does not exist: {rel(path)}")
                quarantine_root = normalize_repo_path(str(policy.get("quarantine_root", ".tmp/safe_write_edit_ops_quarantine")))
                target = quarantine_root / operation_id / rel(path)
                target.parent.mkdir(parents=True, exist_ok=True)
                before = sha256_file(path)
                if apply_mode:
                    if path.is_dir():
                        shutil.move(str(path), str(target))
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(path), str(target))
                    result["applied"] = True
                result.update({"before_sha256": before, "quarantine_path": rel(target)})

        results.append(result)

    audit = {
        "schema": "upgraded-fiesta.safe-write-edit-ops.audit.v1",
        "operation_id": operation_id,
        "mode": obj["mode"],
        "generated_at_utc": utc_now(),
        "repository_root": str(ROOT),
        "policy_schema": policy.get("schema"),
        "results": results,
        "ok": True,
    }
    if apply_mode:
        AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
        audit_path = AUDIT_ROOT / f"{operation_id}.audit.json"
        audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        audit["audit_path"] = rel(audit_path)
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate, plan, or apply a safe_write/edit/ops object.")
    parser.add_argument("command", choices=["validate", "plan", "apply"], help="Execution command.")
    parser.add_argument("--object", required=True, help="Path to operation object JSON.")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY), help="Path to policy JSON.")
    args = parser.parse_args(argv)

    try:
        obj_path = normalize_repo_path(args.object)
        policy_path = normalize_repo_path(args.policy)
        obj = load_json(obj_path)
        policy = load_json(policy_path)
        ensure_policy(policy)
        validate_object(obj)

        if args.command == "validate":
            report = {"schema": "upgraded-fiesta.safe-write-edit-ops.validation.v1", "ok": True, "object": rel(obj_path), "policy": rel(policy_path)}
        else:
            if args.command == "plan":
                obj = {**obj, "mode": "plan"}
            elif args.command == "apply":
                if obj.get("mode") != "apply":
                    raise SafeOpsError("apply command requires object.mode=apply")
            report = plan_or_apply(obj, policy)

        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report.get("ok") else 1
    except SafeOpsError as exc:
        print(json.dumps({"schema": "upgraded-fiesta.safe-write-edit-ops.error.v1", "ok": False, "error": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
