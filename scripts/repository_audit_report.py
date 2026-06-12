#!/usr/bin/env python3
"""Create a deterministic repository inventory report."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
from pathlib import Path

EXCLUDED_DIRS = {".git", "__pycache__", "node_modules", "vendor", "build", "dist"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run(root: Path, argv: list[str]) -> dict[str, object]:
    try:
        done = subprocess.run(argv, cwd=str(root), text=True, capture_output=True, check=False, timeout=60)
        return {"returncode": done.returncode, "stdout": done.stdout.strip(), "stderr": done.stderr.strip()}
    except Exception as exc:
        return {"returncode": 127, "stdout": "", "stderr": repr(exc)}


def skip(root: Path, path: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in EXCLUDED_DIRS for part in parts)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def line_count(path: Path) -> int | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data:
        return None
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def collect(root: Path) -> dict[str, object]:
    files = []
    directories = []
    for current, dirnames, filenames in os.walk(str(root)):
        current_path = Path(current)
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        if skip(root, current_path):
            continue
        directories.append(current_path.relative_to(root).as_posix() if current_path != root else ".")
        for name in sorted(filenames):
            path = current_path / name
            if skip(root, path):
                continue
            rel = path.relative_to(root).as_posix()
            stat = path.stat()
            files.append({"path": rel, "bytes": stat.st_size, "lines": line_count(path), "sha256": digest(path)})
    py_checks = []
    for row in files:
        if str(row["path"]).endswith(".py"):
            py_checks.append({"path": row["path"], "check": run(root, ["python3", "-m", "py_compile", str(row["path"])])})
    sh_checks = []
    for row in files:
        if str(row["path"]).endswith(".sh"):
            sh_checks.append({"path": row["path"], "check": run(root, ["sh", "-n", str(row["path"])])})
    return {
        "schema_version": "1.0",
        "created_utc": utc_now(),
        "root": str(root),
        "summary": {"directories": len(directories), "files": len(files), "python_checks": len(py_checks), "shell_checks": len(sh_checks)},
        "git": {"head": run(root, ["git", "rev-parse", "--short=12", "HEAD"]), "status": run(root, ["git", "status", "--short"])},
        "directories": directories,
        "files": files,
        "python_checks": py_checks,
        "shell_checks": sh_checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    report = collect(Path(__file__).resolve().parents[1])
    if args.format == "markdown":
        text = "# Repository Audit Report\n\n" + "\n".join(f"- {k}: `{v}`" for k, v in report["summary"].items()) + "\n"
    else:
        text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
