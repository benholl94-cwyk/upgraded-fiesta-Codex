#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "audit-valid.debug-streampipe.v1"
DEFAULT_OUTPUT_DIR = ROOT / "reports" / "audit-valid-debug-streampipe"
DEFAULT_ARTIFACTS = [
    "reports/repo-trusted-ops-report.json",
    "reports/ops-route-dry-run-report.json",
    "reports/docker-compose-ops-dry-run.config.yml",
    "reports/docker-compose-ops-dry-run.services.txt",
    "reports/finishline-debug-console.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def read_json_if_possible(path: Path) -> dict[str, Any] | None:
    text = read_text(path)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def artifact_meta(rel_path: str, required: bool) -> dict[str, Any]:
    path = ROOT / rel_path
    exists = path.is_file()
    payload = path.read_bytes() if exists else b""
    json_payload = read_json_if_possible(path) if exists else None
    ok_signal = None
    if isinstance(json_payload, dict) and "ok" in json_payload:
        ok_signal = json_payload.get("ok") is True
    elif exists:
        ok_signal = True
    else:
        ok_signal = False
    return {
        "path": rel_path,
        "required": required,
        "exists": exists,
        "bytes": len(payload) if exists else None,
        "sha256": sha256_bytes(payload) if exists else None,
        "json_object": json_payload is not None,
        "ok_signal": ok_signal,
        "schema": json_payload.get("schema") if isinstance(json_payload, dict) else None,
    }


def build_reels(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reels: list[dict[str, Any]] = []
    for index, artifact in enumerate(artifacts, start=1):
        required = artifact["required"]
        exists = artifact["exists"]
        ok_signal = artifact["ok_signal"]
        decision = "allow" if exists and ok_signal else ("warn" if not required else "deny")
        reels.append({
            "reel": index,
            "id": f"SAFETY_REEL_{index:02d}",
            "artifact": artifact["path"],
            "required": required,
            "decision": decision,
            "exists": exists,
            "ok_signal": ok_signal,
            "audit_valid": bool(exists and ok_signal) if required else bool(exists),
        })
    return reels


def build_report(artifact_paths: list[str]) -> dict[str, Any]:
    required = {
        "reports/repo-trusted-ops-report.json",
        "reports/ops-route-dry-run-report.json",
        "reports/docker-compose-ops-dry-run.config.yml",
        "reports/docker-compose-ops-dry-run.services.txt",
    }
    artifacts = [artifact_meta(path, path in required) for path in artifact_paths]
    reels = build_reels(artifacts)
    required_failures = [reel for reel in reels if reel["required"] and reel["decision"] != "allow"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "ok": not required_failures,
        "self_compiled_safety_reels": True,
        "fullstack_ops_formats": ["json", "jsonl", "markdown", "sarif"],
        "interactive_console": False,
        "runtime_artifact_only": True,
        "remote_execution_performed": False,
        "destructive_execution_performed": False,
        "secret_read_performed": False,
        "required_failures": required_failures,
        "artifacts": artifacts,
        "safety_reels": reels,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, payload: dict[str, Any]) -> None:
    lines = []
    lines.append(json.dumps({"event": "stream_start", "schema": SCHEMA, "generated_at_utc": payload["generated_at_utc"]}, sort_keys=True))
    for artifact in payload["artifacts"]:
        lines.append(json.dumps({"event": "artifact", **artifact}, sort_keys=True))
    for reel in payload["safety_reels"]:
        lines.append(json.dumps({"event": "safety_reel", **reel}, sort_keys=True))
    lines.append(json.dumps({"event": "stream_end", "ok": payload["ok"], "required_failures": len(payload["required_failures"])}, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Audit Valid Debug Streampipe",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        f"OK: `{str(payload['ok']).lower()}`",
        "",
        "## Safety Reels",
        "",
        "| Reel | Artifact | Required | Decision | Exists | OK Signal |",
        "|---:|---|---:|---|---:|---:|",
    ]
    for reel in payload["safety_reels"]:
        lines.append(f"| {reel['reel']} | `{reel['artifact']}` | {reel['required']} | `{reel['decision']}` | {reel['exists']} | {reel['ok_signal']} |")
    lines.extend([
        "",
        "## Boundaries",
        "",
        "- interactive console: false",
        "- runtime artifact only: true",
        "- remote execution performed: false",
        "- destructive execution performed: false",
        "- secret read performed: false",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_sarif(path: Path, payload: dict[str, Any]) -> None:
    results = []
    for failure in payload["required_failures"]:
        results.append({
            "ruleId": "audit-valid-required-artifact",
            "level": "error",
            "message": {"text": f"Required artifact did not pass audit-valid check: {failure['artifact']}"},
            "locations": [{"physicalLocation": {"artifactLocation": {"uri": failure["artifact"]}}}],
        })
    sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "audit-valid-debug-streampipe",
                    "informationUri": "https://github.com/benholl94-cwyk/upgraded-fiesta-Codex",
                    "rules": [{
                        "id": "audit-valid-required-artifact",
                        "shortDescription": {"text": "Required audit artifact must exist and pass its ok signal"},
                    }],
                }
            },
            "results": results,
        }],
    }
    path.write_text(json.dumps(sarif, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate audit-valid debug stream pipe outputs.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--artifact", action="append", default=[])
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    artifact_paths = args.artifact or DEFAULT_ARTIFACTS
    payload = build_report(artifact_paths)
    write_json(output_dir / "audit-valid-debug-streampipe.json", payload)
    write_jsonl(output_dir / "audit-valid-debug-streampipe.jsonl", payload)
    write_markdown(output_dir / "audit-valid-debug-streampipe.md", payload)
    write_sarif(output_dir / "audit-valid-debug-streampipe.sarif", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
