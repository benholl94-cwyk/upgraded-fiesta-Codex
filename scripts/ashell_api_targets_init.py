#!/usr/bin/env python3
"""Create a local API target file without shell heredoc input."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DEV_ROOT = Path.home() / "Documents" / "Developer"
TARGET_PATH = DEV_ROOT / "policies" / "api-targets.local.json"

DEFAULT_TARGETS = {
    "schema_version": "1.0.0",
    "name": "api-targets-local",
    "targets": [
        {
            "id": "example",
            "base_url": "https://example.com",
            "enabled": True,
            "families": ["openapi_http", "rss_atom_jsonfeed", "oauth_oidc"],
        }
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create ~/Documents/Developer/policies/api-targets.local.json")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing local target file")
    args = parser.parse_args()
    TARGET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if TARGET_PATH.exists() and not args.force:
        print(json.dumps({"ok": True, "changed": False, "path": str(TARGET_PATH), "detail": "already exists"}, indent=2))
        return 0
    TARGET_PATH.write_text(json.dumps(DEFAULT_TARGETS, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "changed": True, "path": str(TARGET_PATH)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
