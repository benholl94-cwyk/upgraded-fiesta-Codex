#!/usr/bin/env python3
"""Explicit-target API surface mapper for a-Shell."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "settings" / "mobile-production" / "api-surface.catalog.json"
TARGET_TEMPLATE = ROOT / "settings" / "mobile-production" / "api-targets.local.example.json"
DEV_ROOT = Path.home() / "Documents" / "Developer"
POLICY_TARGETS = DEV_ROOT / "policies" / "api-targets.local.json"
RUN_DIR = DEV_ROOT / "runs"
LOG_DIR = DEV_ROOT / "logs"
STATE_PATH = RUN_DIR / "api-surface-state.json"
DEFAULT_TIMEOUT = 8


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dirs() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    POLICY_TARGETS.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(payload: dict[str, Any]) -> None:
    ensure_dirs()
    STATE_PATH.write_text(json.dumps({"ts_utc": utc_now(), **payload}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def family_map() -> dict[str, dict[str, Any]]:
    data = read_json(CATALOG_PATH)
    return {item["id"]: item for item in data.get("families", [])}


def normalize_base(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("base_url must use http or https")
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def join_url(base: str, suffix: str) -> str:
    if suffix.startswith("/"):
        parsed = urllib.parse.urlparse(base)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, suffix, "", "", ""))
    return base.rstrip("/") + "/" + suffix.lstrip("/")


def fetch_head_or_get(url: str) -> dict[str, Any]:
    context = ssl.create_default_context()
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "upgraded-fiesta-a-shell-api-surface/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT, context=context) as response:
            content_type = response.headers.get("content-type", "")
            body = response.read(4096).decode("utf-8", errors="replace")
            return {"url": url, "ok": True, "status": response.status, "content_type": content_type, "sample": body[:500]}
    except urllib.error.HTTPError as exc:
        return {"url": url, "ok": False, "status": exc.code, "content_type": exc.headers.get("content-type", ""), "sample": ""}
    except Exception as exc:
        return {"url": url, "ok": False, "status": 0, "content_type": "", "error": repr(exc), "sample": ""}


def probe_target(target: dict[str, Any]) -> dict[str, Any]:
    base = normalize_base(target["base_url"])
    families = family_map()
    results = []
    for family_id in target.get("families", []):
        family = families.get(family_id)
        if not family:
            results.append({"family": family_id, "ok": False, "detail": "unknown family"})
            continue
        checks = []
        for suffix in family.get("contract_files", []):
            if suffix.startswith("tools/") or suffix.startswith("resources/") or suffix.startswith("prompts/") or suffix.endswith("docs") or suffix.endswith("catalog"):
                checks.append({"path": suffix, "ok": False, "skipped": True, "detail": "requires protocol-specific client or documentation"})
                continue
            checks.append(fetch_head_or_get(join_url(base, suffix)))
        results.append({"family": family_id, "transport": family.get("transport"), "checks": checks})
    return {"id": target.get("id"), "base_url": base, "results": results}


def targets() -> list[dict[str, Any]]:
    if POLICY_TARGETS.exists():
        data = read_json(POLICY_TARGETS)
    else:
        data = read_json(TARGET_TEMPLATE)
    return [item for item in data.get("targets", []) if item.get("enabled")]


def list_catalog() -> int:
    data = read_json(CATALOG_PATH)
    print(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def plan() -> int:
    payload = {"targets_file": str(POLICY_TARGETS), "enabled_targets": targets(), "catalog_families": sorted(family_map())}
    write_state(payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def probe() -> int:
    enabled = targets()
    payload = {"targets": [probe_target(target) for target in enabled]}
    write_state(payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def self_test() -> int:
    assert CATALOG_PATH.exists()
    assert TARGET_TEMPLATE.exists()
    data = read_json(CATALOG_PATH)
    assert data.get("schema_version")
    assert data.get("families")
    write_state({"self_test": True, "family_count": len(data.get("families", []))})
    print("ashell api surface self-test ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explicit-target API surface mapper for a-Shell.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    sub.add_parser("catalog")
    sub.add_parser("plan")
    sub.add_parser("probe")
    args = parser.parse_args(argv)
    if args.command == "self-test":
        return self_test()
    if args.command == "catalog":
        return list_catalog()
    if args.command == "plan":
        return plan()
    if args.command == "probe":
        return probe()
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
