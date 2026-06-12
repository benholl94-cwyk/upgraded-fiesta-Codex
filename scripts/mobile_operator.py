#!/usr/bin/env python3
"""Mobile operator for the upgraded-fiesta a-Shell control plane."""

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
DEV = HOME / "Documents" / "Developer"
LOGS = DEV / "logs"
RUNS = DEV / "runs"
BACKUPS = DEV / "backups"
POLICIES = DEV / "policies" / "mobile-iphone-platform"
DATASETS = DEV / "datasets" / "mobile-iphone-platform"

REQUIRED_DIRS = [
    DEV / "repos", DEV / "inbox", DEV / "outbox", RUNS, LOGS,
    DEV / "exports", BACKUPS, DEV / "tmp", DEV / "policies", DEV / "datasets"
]

REQUIRED_FILES = [
    "README.md", "index.html", "styles.css", "app.js",
    "manifest.webmanifest", "service-worker.js",
    "scripts/validate_mobile_iphone_platform.py",
    "scripts/ashell_static_server.py",
]

BLOCKED_NAMES = [".env", "id_ed25519", "id_rsa"]
BLOCKED_SUFFIXES = [".pem", ".p12", ".key"]


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def stamp():
    return now().strftime("%Y%m%dT%H%M%SZ")


def day():
    return now().strftime("%Y-%m-%d")


def ensure_dirs():
    for path in REQUIRED_DIRS:
        path.mkdir(parents=True, exist_ok=True)
    POLICIES.mkdir(parents=True, exist_ok=True)
    DATASETS.mkdir(parents=True, exist_ok=True)


def write_log(name, payload):
    ensure_dirs()
    path = LOGS / (name + "-" + stamp() + ".json")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(path))
    return path


def run(argv):
    try:
        done = subprocess.run(argv, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return {"returncode": done.returncode, "stdout": done.stdout.strip(), "stderr": done.stderr.strip()}
    except Exception as exc:
        return {"returncode": 127, "stdout": "", "stderr": repr(exc)}


def validate(_args):
    result = run([sys.executable, "scripts/validate_mobile_iphone_platform.py"])
    print(result["stdout"])
    if result["stderr"]:
        print(result["stderr"], file=sys.stderr)
    return result["returncode"]


def doctor(_args):
    ensure_dirs()
    missing = [item for item in REQUIRED_FILES if not (ROOT / item).exists()]
    payload = {
        "timestamp_utc": now().isoformat(),
        "repo_root": str(ROOT),
        "developer_root": str(DEV),
        "missing_files": missing,
        "python": sys.version.split()[0],
        "lg2_present": shutil.which("lg2") is not None,
        "validation": run([sys.executable, "scripts/validate_mobile_iphone_platform.py"]),
    }
    payload["status"] = "ok" if not missing and payload["validation"]["returncode"] == 0 else "fail"
    write_log("doctor", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "ok" else 1


def audit(_args):
    findings = []
    for root, dirs, files in os.walk(str(ROOT)):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules", ".venv", "venv"}]
        for name in files:
            path = Path(root) / name
            rel = path.relative_to(ROOT).as_posix()
            if name in BLOCKED_NAMES or any(name.endswith(suffix) for suffix in BLOCKED_SUFFIXES):
                findings.append(rel)
    payload = {"timestamp_utc": now().isoformat(), "findings": findings, "status": "ok" if not findings else "blocked"}
    write_log("audit", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not findings else 2


def health(_args):
    ensure_dirs()
    payload = {
        "timestamp_utc": now().isoformat(),
        "repo_root": str(ROOT),
        "developer_root": str(DEV),
        "python": sys.version.split()[0],
        "lg2_present": shutil.which("lg2") is not None,
    }
    path = RUNS / (day() + "-health.json")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(path))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def backup(_args):
    ensure_dirs()
    target = BACKUPS / day()
    target.mkdir(parents=True, exist_ok=True)
    archive = target / ("upgraded-fiesta-control-plane-" + stamp() + ".zip")
    with zipfile.ZipFile(str(archive), "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for base in [LOGS, RUNS, POLICIES, DATASETS]:
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if path.is_file():
                    zf.write(str(path), path.relative_to(DEV).as_posix())
    payload = {"timestamp_utc": now().isoformat(), "archive": str(archive), "status": "ok"}
    write_log("backup", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def runlog(args):
    ensure_dirs()
    path = RUNS / (day() + "-" + args.name + ".md")
    if not path.exists():
        path.write_text("# " + args.name + "\n\nZeitpunkt UTC: " + now().isoformat() + "\nStatus: started\n", encoding="utf-8")
    print(str(path))
    return 0


def serve(args):
    server = ROOT / "scripts" / "ashell_static_server.py"
    os.execv(sys.executable, [sys.executable, str(server), "--host", args.host, "--port", str(args.port), "--directory", str(ROOT)])
    return 0


def self_test(_args):
    print("mobile operator self-test ok")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="upgraded-fiesta mobile operator")
    sub = parser.add_subparsers(dest="cmd")
    sub.required = True
    sub.add_parser("validate").set_defaults(func=validate)
    sub.add_parser("doctor").set_defaults(func=doctor)
    sub.add_parser("audit").set_defaults(func=audit)
    sub.add_parser("health").set_defaults(func=health)
    sub.add_parser("backup").set_defaults(func=backup)
    p = sub.add_parser("runlog")
    p.add_argument("name")
    p.set_defaults(func=runlog)
    p = sub.add_parser("serve")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=serve)
    sub.add_parser("self-test").set_defaults(func=self_test)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
