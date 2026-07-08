#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_THRESHOLDS = ROOT / "config" / "ops-activation-thresholds.example.json"
REQUIRED_PHRASE = "USER_ACCEPT_OPS_ACCESS_THRESHOLDS"

DENIED_EVIDENCE_KEYS = {
    "secret",
    "password",
    "token",
    "access_key",
    "private_key",
    "env_value",
    "raw_log",
    "credential",
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing json file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json file: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"json root must be an object: {path}")
    return value


def threshold_ids(thresholds_doc: dict[str, Any]) -> list[str]:
    thresholds = thresholds_doc.get("thresholds")
    if not isinstance(thresholds, list) or not thresholds:
        raise SystemExit("thresholds document must contain a non-empty thresholds list")
    ids: list[str] = []
    for item in thresholds:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise SystemExit("each threshold must be an object with a string id")
        ids.append(item["id"])
    return ids


def inspect_for_denied_evidence(value: Any, path: str, findings: list[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).lower()
            if lowered in DENIED_EVIDENCE_KEYS or any(marker in lowered for marker in DENIED_EVIDENCE_KEYS):
                findings.append(f"denied evidence key present at {path}.{key}")
            inspect_for_denied_evidence(nested, f"{path}.{key}", findings)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            inspect_for_denied_evidence(nested, f"{path}[{index}]", findings)
    elif isinstance(value, str):
        lowered = value.lower()
        forbidden_fragments = [
            "begin openssh",
            "begin rsa",
            "bearer ",
            "authorization:",
            "password=",
            "token=",
            "secret=",
            "api_key=",
        ]
        if any(fragment in lowered for fragment in forbidden_fragments):
            findings.append(f"denied evidence value pattern present at {path}")


def validate_acceptance(thresholds_doc: dict[str, Any], acceptance_doc: dict[str, Any]) -> tuple[bool, list[str]]:
    findings: list[str] = []

    if thresholds_doc.get("schema") != "ops-access.thresholds.v1":
        findings.append("thresholds schema must be ops-access.thresholds.v1")

    if acceptance_doc.get("schema") != "ops-access.user-acceptance.v1":
        findings.append("acceptance schema must be ops-access.user-acceptance.v1")

    if acceptance_doc.get("accept_phrase") != REQUIRED_PHRASE:
        findings.append(f"accept_phrase must be {REQUIRED_PHRASE}")

    if acceptance_doc.get("user_accept") is not True:
        findings.append("top-level user_accept must be true")

    if acceptance_doc.get("remote_activation_requested") is not False:
        findings.append("remote_activation_requested must remain false for repository gate validation")

    accepted = acceptance_doc.get("accepted_thresholds")
    if not isinstance(accepted, dict):
        findings.append("accepted_thresholds must be an object")
        accepted = {}

    for threshold_id in threshold_ids(thresholds_doc):
        if accepted.get(threshold_id) is not True:
            findings.append(f"threshold not explicitly accepted: {threshold_id}")

    evidence = acceptance_doc.get("evidence")
    if evidence is not None:
        inspect_for_denied_evidence(evidence, "evidence", findings)

    return not findings, findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate explicit user acceptance for ops access thresholds.")
    parser.add_argument("--thresholds", default=str(DEFAULT_THRESHOLDS), help="Threshold definition JSON file.")
    parser.add_argument("--acceptance", required=True, help="User acceptance JSON file generated outside Git or in workflow runtime.")
    args = parser.parse_args(argv)

    thresholds_path = Path(args.thresholds)
    acceptance_path = Path(args.acceptance)
    if not thresholds_path.is_absolute():
        thresholds_path = ROOT / thresholds_path
    if not acceptance_path.is_absolute():
        acceptance_path = ROOT / acceptance_path

    thresholds_doc = load_json(thresholds_path)
    acceptance_doc = load_json(acceptance_path)
    ok, findings = validate_acceptance(thresholds_doc, acceptance_doc)

    result = {
        "ok": ok,
        "thresholds": str(thresholds_path.relative_to(ROOT) if thresholds_path.is_relative_to(ROOT) else thresholds_path),
        "acceptance": str(acceptance_path.relative_to(ROOT) if acceptance_path.is_relative_to(ROOT) else acceptance_path),
        "remote_activation_performed": False,
        "findings": findings,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
