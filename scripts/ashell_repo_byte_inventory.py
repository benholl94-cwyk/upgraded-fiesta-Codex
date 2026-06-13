#!/usr/bin/env python3
"""Create a SHA-256 byte inventory for every repository file."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEV_ROOT = Path.home() / "Documents" / "Developer"
EXPORT_DIR = DEV_ROOT / "exports"
RUN_DIR = DEV_ROOT / "runs"
STATE_PATH = RUN_DIR / "repo-byte-inventory-state.json"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S")


def ensure_dirs() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(262144), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory() -> dict[str, Any]:
    files = []
    for path in sorted(ROOT.rglob("*")):
        if ".git" in path.parts:
            continue
        if path.is_file():
            rel = str(path.relative_to(ROOT))
            item: dict[str, Any] = {"path": rel}
            try:
                item["size_bytes"] = path.stat().st_size
                item["sha256"] = sha256_file(path)
            except Exception as exc:
                item["error"] = repr(exc)
            files.append(item)
    payload = {"root": str(ROOT), "file_count": len(files), "total_bytes": sum(item.get("size_bytes", 0) for item in files), "files": files}
    ensure_dirs()
    target = EXPORT_DIR / f"repo-byte-inventory-{stamp()}.json"
    target.write_text(json.dumps({"ts_utc": utc_now(), **payload}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    STATE_PATH.write_text(json.dumps({"ts_utc": utc_now(), "export": str(target), "file_count": payload["file_count"], "total_bytes": payload["total_bytes"]}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    payload["export"] = str(target)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Create repository byte inventory.")
    parser.add_argument("command", choices=["self-test", "generate"])
    args = parser.parse_args()
    payload = inventory()
    if args.command == "self-test":
        assert payload["file_count"] > 0
        print("ashell repo byte inventory self-test ok")
        return 0
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
