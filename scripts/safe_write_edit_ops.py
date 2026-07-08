#!/usr/bin/env python3
"""Dependency-free safe_write/edit/ops executor for repository-local changes."""
from __future__ import annotations
import argparse, datetime as dt, fnmatch, hashlib, json, os, re, shutil, sys, tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "upgraded-fiesta.safe-write-edit-ops.v1"
DEFAULT_POLICY = "datasets/safe-write-edit-ops.policy.json"
AUDIT_ROOT = ROOT / "runs" / "safe_write_edit_ops"
BACKUP_ROOT = ROOT / ".tmp" / "safe_write_edit_ops_backups"
CONTROL_RE = re.compile(r"[\x00-\x1f]")

class SafeOpsError(RuntimeError): pass

def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str | None:
    return sha256_bytes(path.read_bytes()) if path.is_file() else None

def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()

def normalize_repo_path(raw: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise SafeOpsError("path must be a non-empty string")
    if CONTROL_RE.search(raw):
        raise SafeOpsError(f"path contains control characters: {raw!r}")
    candidate = Path(raw)
    if candidate.is_absolute():
        try:
            candidate.resolve().relative_to(ROOT)
        except ValueError as exc:
            raise SafeOpsError(f"absolute path escapes repository root: {raw}") from exc
        return candidate.resolve()
    if ".." in candidate.parts:
        raise SafeOpsError(f"parent traversal is blocked: {raw}")
    resolved = (ROOT / candidate).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise SafeOpsError(f"path escapes repository root: {raw}") from exc
    return resolved

def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SafeOpsError(f"failed to read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SafeOpsError(f"JSON root must be an object: {path}")
    return payload

def ensure_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema") != SCHEMA:
        raise SafeOpsError(f"policy schema mismatch: expected {SCHEMA}")
    if not isinstance(policy.get("allowed_roots"), list) or not policy["allowed_roots"]:
        raise SafeOpsError("policy.allowed_roots must be a non-empty list")
    if not isinstance(policy.get("denied_globs"), list):
        raise SafeOpsError("policy.denied_globs must be a list")
    if not isinstance(policy.get("limits", {}), dict):
        raise SafeOpsError("policy.limits must be an object")

def enforce_path_policy(path: Path, policy: dict[str, Any], *, role: str) -> None:
    repo_rel = rel(path)
    allowed = False
    for root in policy["allowed_roots"]:
        root_path = normalize_repo_path(str(root))
        try:
            path.relative_to(root_path); allowed = True; break
        except ValueError:
            if path == root_path:
                allowed = True; break
    if not allowed:
        raise SafeOpsError(f"{role} path is outside allowed roots: {repo_rel}")
    for pattern in policy.get("denied_globs", []):
        if fnmatch.fnmatch(repo_rel, str(pattern)):
            raise SafeOpsError(f"{role} path matches denied glob {pattern!r}: {repo_rel}")
    max_path_bytes = int(policy.get("limits", {}).get("max_path_bytes", 240))
    if len(repo_rel.encode("utf-8")) > max_path_bytes:
        raise SafeOpsError(f"{role} path exceeds max_path_bytes={max_path_bytes}: {repo_rel}")

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
    supported = {"mkdir", "write_file", "append_file", "edit_replace", "copy_file", "quarantine_path"}
    for index, op in enumerate(obj["ops"]):
        if not isinstance(op, dict):
            raise SafeOpsError(f"ops[{index}] must be an object")
        if op.get("op") not in supported:
            raise SafeOpsError(f"ops[{index}].op is unsupported: {op.get('op')!r}")
        if op.get("op") == "copy_file":
            if "from_path" not in op or "to_path" not in op:
                raise SafeOpsError(f"ops[{index}] copy_file requires from_path and to_path")
        elif "path" not in op:
            raise SafeOpsError(f"ops[{index}] requires path")

def content_bytes(op: dict[str, Any]) -> bytes:
    if "content_utf8" in op:
        if not isinstance(op["content_utf8"], str):
            raise SafeOpsError("content_utf8 must be a string")
        return op["content_utf8"].encode("utf-8")
    if "content_json" in op:
        return (json.dumps(op["content_json"], indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    raise SafeOpsError("operation requires content_utf8 or content_json")

def ensure_size(data: bytes, policy: dict[str, Any], label: str) -> None:
    limit = int(policy.get("limits", {}).get("max_file_bytes", 1048576))
    if len(data) > limit:
        raise SafeOpsError(f"{label} exceeds max_file_bytes={limit}")

def check_hash(path: Path, expected: str | None, *, required: bool) -> None:
    actual = sha256_file(path)
    if required and not expected:
        raise SafeOpsError(f"expected sha256 required for {rel(path)}")
    if expected and actual != expected:
        raise SafeOpsError(f"hash mismatch for {rel(path)}: expected {expected}, actual {actual}")

def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        tmp = Path(tmp_name)
        if tmp.exists(): tmp.unlink()

def backup_existing(path: Path, operation_id: str) -> str | None:
    if not path.exists(): return None
    target = BACKUP_ROOT / operation_id / rel(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if path.is_dir(): shutil.copytree(path, target, dirs_exist_ok=True)
    else: shutil.copy2(path, target)
    return rel(target)

def execute(obj: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    ensure_policy(policy); validate_object(obj)
    apply_mode = obj["mode"] == "apply"
    operation_id = obj["operation_id"]
    results: list[dict[str, Any]] = []
    for index, op in enumerate(obj["ops"]):
        kind = op["op"]; result: dict[str, Any] = {"index": index, "op": kind, "applied": False}
        if kind == "copy_file":
            source = normalize_repo_path(op["from_path"]); target = normalize_repo_path(op["to_path"])
            enforce_path_policy(source, policy, role="source"); enforce_path_policy(target, policy, role="target")
            if not source.is_file(): raise SafeOpsError(f"copy source is not a file: {rel(source)}")
            check_hash(source, op.get("expected_source_sha256"), required=bool(op.get("require_source_hash", False)))
            data = source.read_bytes(); ensure_size(data, policy, "copy source")
            if target.exists() and not op.get("overwrite", False): raise SafeOpsError(f"copy target exists and overwrite=false: {rel(target)}")
            if target.exists(): check_hash(target, op.get("expected_target_sha256"), required=bool(op.get("require_target_hash", False)))
            before = sha256_file(target); backup = None
            if apply_mode:
                backup = backup_existing(target, operation_id); atomic_write(target, data); result["applied"] = True
            result.update({"from_path": rel(source), "path": rel(target), "before_sha256": before, "after_sha256": sha256_bytes(data), "backup": backup})
        else:
            path = normalize_repo_path(op["path"]); enforce_path_policy(path, policy, role="target"); result["path"] = rel(path)
            if kind == "mkdir":
                if path.exists() and not path.is_dir(): raise SafeOpsError(f"mkdir target exists and is not a directory: {rel(path)}")
                if apply_mode: path.mkdir(parents=True, exist_ok=True); result["applied"] = True
                result["after_state"] = "directory"
            elif kind == "write_file":
                data = content_bytes(op); ensure_size(data, policy, "write content")
                if path.exists() and not op.get("overwrite", False): raise SafeOpsError(f"write target exists and overwrite=false: {rel(path)}")
                if path.exists(): check_hash(path, op.get("expected_sha256"), required=bool(op.get("require_hash", False)))
                before = sha256_file(path); backup = None
                if apply_mode: backup = backup_existing(path, operation_id); atomic_write(path, data); result["applied"] = True
                result.update({"before_sha256": before, "after_sha256": sha256_bytes(data), "backup": backup, "bytes": len(data)})
            elif kind == "append_file":
                data = content_bytes(op); ensure_size(data, policy, "append content")
                before_data = path.read_bytes() if path.is_file() else b""
                if path.exists(): check_hash(path, op.get("expected_sha256"), required=bool(op.get("require_hash", False)))
                after = before_data + data; ensure_size(after, policy, "appended file")
                backup = None
                if apply_mode: backup = backup_existing(path, operation_id); atomic_write(path, after); result["applied"] = True
                result.update({"before_sha256": sha256_bytes(before_data) if before_data else None, "after_sha256": sha256_bytes(after), "backup": backup, "bytes_added": len(data)})
            elif kind == "edit_replace":
                if not path.is_file(): raise SafeOpsError(f"edit target is not a file: {rel(path)}")
                check_hash(path, op.get("expected_sha256"), required=True)
                text = path.read_text(encoding="utf-8")
                replacements = op.get("replacements")
                if not isinstance(replacements, list) or not replacements: raise SafeOpsError("edit_replace requires replacements")
                changed = text
                for repl in replacements:
                    if not isinstance(repl, dict) or not isinstance(repl.get("find"), str) or not isinstance(repl.get("replace"), str):
                        raise SafeOpsError("replacement requires string find and replace")
                    count = int(repl.get("count", -1)); find = repl["find"]
                    if find not in changed: raise SafeOpsError(f"edit pattern not found in {rel(path)}: {find[:80]!r}")
                    changed = changed.replace(find, repl["replace"], count if count >= 0 else changed.count(find))
                data = changed.encode("utf-8"); ensure_size(data, policy, "edited file"); backup = None
                if apply_mode: backup = backup_existing(path, operation_id); atomic_write(path, data); result["applied"] = True
                result.update({"before_sha256": op.get("expected_sha256"), "after_sha256": sha256_bytes(data), "backup": backup})
            elif kind == "quarantine_path":
                if not path.exists(): raise SafeOpsError(f"quarantine target does not exist: {rel(path)}")
                quarantine_root = normalize_repo_path(str(policy.get("quarantine_root", ".tmp/safe_write_edit_ops_quarantine")))
                target = quarantine_root / operation_id / rel(path); before = sha256_file(path)
                if apply_mode:
                    target.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(path), str(target)); result["applied"] = True
                result.update({"before_sha256": before, "quarantine_path": rel(target)})
        results.append(result)
    audit = {"schema": "upgraded-fiesta.safe-write-edit-ops.audit.v1", "operation_id": operation_id, "mode": obj["mode"], "generated_at_utc": utc_now(), "repository_root": str(ROOT), "policy_schema": policy.get("schema"), "results": results, "ok": True}
    if apply_mode:
        AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
        audit_path = AUDIT_ROOT / f"{operation_id}.audit.json"
        audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        audit["audit_path"] = rel(audit_path)
    return audit

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate, plan, or apply a safe_write/edit/ops object.")
    parser.add_argument("command", choices=["validate", "plan", "apply"])
    parser.add_argument("--object", required=True)
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    args = parser.parse_args(argv)
    try:
        obj_path = normalize_repo_path(args.object); policy_path = normalize_repo_path(args.policy)
        obj = load_json(obj_path); policy = load_json(policy_path); ensure_policy(policy); validate_object(obj)
        if args.command == "validate":
            report = {"schema": "upgraded-fiesta.safe-write-edit-ops.validation.v1", "ok": True, "object": rel(obj_path), "policy": rel(policy_path)}
        else:
            obj = {**obj, "mode": "plan"} if args.command == "plan" else obj
            if args.command == "apply" and obj.get("mode") != "apply":
                raise SafeOpsError("apply command requires object.mode=apply")
            report = execute(obj, policy)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report.get("ok") else 1
    except SafeOpsError as exc:
        print(json.dumps({"schema": "upgraded-fiesta.safe-write-edit-ops.error.v1", "ok": False, "error": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1

if __name__ == "__main__": raise SystemExit(main())
