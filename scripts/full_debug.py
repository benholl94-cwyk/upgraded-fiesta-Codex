#!/usr/bin/env python3
"""Deterministic repository debug harness for upgraded-fiesta-Codex."""
from __future__ import annotations

import argparse
import compileall
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"

EXPECTED_FILES = [
    "Cargo.toml", "README.md", "Dockerfile", "docker-compose.yml", "Makefile",
    "config/heavy-metal.json", "config/heavy-metal.toml", "scripts/init-db.sql",
    "scripts/validate_repo.py", "ui/package.json",
]
EXCLUDED_DIRS = {
    ".git", ".cache", ".pytest_cache", ".tmp", ".venv", "backups", "dist",
    "exports", "logs", "node_modules", "reports", "runs", "target", "venv",
    "ui/dist", "ui/node_modules",
}
TEXT_SUFFIXES = {
    ".c", ".css", ".env", ".h", ".html", ".js", ".json", ".jsx", ".lock",
    ".md", ".py", ".rs", ".sh", ".sql", ".toml", ".ts", ".tsx", ".txt",
    ".yaml", ".yml",
}
SECRET_NAME_RE = re.compile(
    r"(^|[/_.-])(key|token|secret|credential|credentials|password|passwd|private|pem|p12|pfx)([/_.-]|$)",
    re.IGNORECASE,
)
SECRET_VALUE_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|passwd|private[_-]?key)\s*[:=]\s*['\"]?([^'\"\s]{8,})"
)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")
HIGH_ENTROPY_RE = re.compile(r"\b[A-Za-z0-9_=-]{40,}\b")
PLACEHOLDER_RE = re.compile(r"(?i)(replace-with|change-me|changeme|dummy|example\.com|placeholder|todo\b|fixme\b)")
SAFE_PLACEHOLDER_PREFIXES = (
    "replace", "replace-with", "change-me", "changeme", "dummy", "example",
    "placeholder", "not-set", "unset", "your-", "<",
)
CONTROL_PATH_RE = re.compile(r"[\x00-\x1f]")


@dataclass
class Finding:
    severity: str
    check: str
    path: str
    message: str


class Audit:
    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self.metrics: dict[str, object] = {}

    def add(self, severity: str, check: str, path: str, message: str) -> None:
        self.findings.append(Finding(severity, check, path, message))

    def error(self, check: str, path: str, message: str) -> None:
        self.add("error", check, path, message)

    def warn(self, check: str, path: str, message: str) -> None:
        self.add("warning", check, path, message)

    @property
    def ok(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def iter_repo_files() -> Iterable[Path]:
    for base, dirs, files in os.walk(ROOT):
        base_path = Path(base)
        rel_base = rel(base_path)
        kept: list[str] = []
        for dirname in dirs:
            candidate = dirname if rel_base == "." else f"{rel_base}/{dirname}"
            if dirname not in EXCLUDED_DIRS and candidate not in EXCLUDED_DIRS:
                kept.append(dirname)
        dirs[:] = kept
        for filename in files:
            yield base_path / filename


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def command_available(name: str) -> bool:
    return shutil.which(name) is not None


def run_command(command: list[str], *, cwd: Path = ROOT, timeout: int = 120) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command, cwd=str(cwd), text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=timeout, check=False,
        )
        return completed.returncode, completed.stdout[-12000:]
    except FileNotFoundError:
        return 127, f"command not found: {command[0]}"
    except subprocess.TimeoutExpired as exc:
        return 124, f"command timed out after {timeout}s: {' '.join(command)}\n{exc.stdout or ''}"


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    import math
    counts = {ch: value.count(ch) for ch in set(value)}
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def is_safe_placeholder(value: str) -> bool:
    cleaned = value.strip().strip('"\'').lower()
    return cleaned.startswith(SAFE_PLACEHOLDER_PREFIXES) or bool(PLACEHOLDER_RE.search(cleaned))


def should_scan_text(path: Path) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    try:
        return b"\0" not in path.read_bytes()[:512]
    except OSError:
        return False


def check_expected_files(audit: Audit) -> None:
    missing, empty = [], []
    for item in EXPECTED_FILES:
        path = ROOT / item
        if not path.is_file():
            missing.append(item)
            audit.error("expected-file", item, "required repository file is missing")
        elif path.stat().st_size == 0:
            empty.append(item)
            audit.error("expected-file", item, "required repository file is empty")
    audit.metrics["expected_missing"] = missing
    audit.metrics["expected_empty"] = empty


def check_workspace(audit: Audit) -> None:
    try:
        cargo = tomllib.loads(read_text(ROOT / "Cargo.toml"))
    except Exception as exc:
        audit.error("cargo-workspace", "Cargo.toml", f"failed to parse workspace TOML: {exc}")
        return
    members = cargo.get("workspace", {}).get("members", [])
    if not isinstance(members, list) or not members:
        audit.error("cargo-workspace", "Cargo.toml", "workspace.members is missing or empty")
        return
    missing_manifests, missing_sources = [], []
    for member in members:
        member_path = ROOT / str(member)
        if not (member_path / "Cargo.toml").is_file():
            missing_manifests.append(str(member))
            audit.error("cargo-workspace", str(member), "workspace member Cargo.toml is missing")
        if not ((member_path / "src/lib.rs").is_file() or (member_path / "src/main.rs").is_file()):
            missing_sources.append(str(member))
            audit.error("cargo-workspace", str(member), "workspace member has neither src/lib.rs nor src/main.rs")
    audit.metrics["workspace_members"] = len(members)
    audit.metrics["workspace_missing_manifests"] = missing_manifests
    audit.metrics["workspace_missing_sources"] = missing_sources


def check_json_toml(audit: Audit) -> None:
    for path in iter_repo_files():
        suffix = path.suffix.lower()
        if suffix == ".json":
            try:
                json.loads(read_text(path))
            except Exception as exc:
                audit.error("json-parse", rel(path), f"invalid JSON: {exc}")
        elif suffix == ".toml":
            try:
                tomllib.loads(read_text(path))
            except Exception as exc:
                audit.error("toml-parse", rel(path), f"invalid TOML: {exc}")


def check_python_compile(audit: Audit) -> None:
    scripts = ROOT / "scripts"
    if not scripts.is_dir():
        audit.error("python-compile", "scripts", "scripts directory is missing")
        return
    if not compileall.compile_dir(str(scripts), quiet=1, force=True):
        audit.error("python-compile", "scripts", "one or more Python files failed bytecode compilation")


def check_shell_scripts(audit: Audit) -> None:
    for path in iter_repo_files():
        if path.suffix.lower() != ".sh":
            continue
        text = read_text(path)
        if "\r\n" in text:
            audit.error("shell-portability", rel(path), "CRLF line endings detected")
        if not text.startswith("#!"):
            audit.warn("shell-portability", rel(path), "shell file has no shebang")
        if "set -euo pipefail" not in text:
            audit.warn("shell-portability", rel(path), "shell file does not enable set -euo pipefail")
        if command_available("bash"):
            code, output = run_command(["bash", "-n", str(path)], timeout=20)
            if code != 0:
                audit.error("shell-syntax", rel(path), output.strip() or "bash -n failed")


def check_paths(audit: Audit) -> None:
    total = 0
    for path in iter_repo_files():
        total += 1
        rp = rel(path)
        if CONTROL_PATH_RE.search(rp):
            audit.error("path-safety", rp, "path contains control characters")
        if rp.startswith("/") or ".." in Path(rp).parts:
            audit.error("path-safety", rp, "path is not repository-relative safe")
        if len(rp.encode("utf-8")) > 240:
            audit.warn("path-safety", rp, "path is long enough to be fragile on mobile filesystems")
    audit.metrics["repo_files_scanned"] = total


def check_secrets_and_placeholders(audit: Audit) -> None:
    sensitive_names, secret_value_hits, placeholder_hits, entropy_hits = [], 0, 0, 0
    for path in iter_repo_files():
        rp = rel(path)
        if SECRET_NAME_RE.search(rp):
            sensitive_names.append(rp)
            audit.warn("secret-name", rp, "sensitive-looking filename is tracked or present in worktree")
        if not should_scan_text(path):
            continue
        try:
            text = read_text(path)
        except UnicodeDecodeError:
            continue
        if PRIVATE_KEY_RE.search(text):
            secret_value_hits += 1
            audit.error("secret-material", rp, "private key material detected")
        for match in SECRET_VALUE_RE.finditer(text):
            key, value = match.group(1), match.group(2)
            if is_safe_placeholder(value):
                continue
            secret_value_hits += 1
            audit.error("secret-material", rp, f"possible hard-coded secret value near {key}")
        for match in HIGH_ENTROPY_RE.finditer(text):
            value = match.group(0)
            if value.startswith(("sha256", "http", "https")) or is_safe_placeholder(value):
                continue
            if shannon_entropy(value) >= 4.5:
                entropy_hits += 1
                audit.warn("entropy-scan", rp, "high-entropy token-like string detected; verify it is not a secret")
                break
        if PLACEHOLDER_RE.search(text):
            placeholder_hits += 1
            audit.warn("placeholder-scan", rp, "placeholder/TODO/example marker detected")
    audit.metrics["sensitive_name_hits"] = sensitive_names
    audit.metrics["secret_value_hits"] = secret_value_hits
    audit.metrics["placeholder_file_hits"] = placeholder_hits
    audit.metrics["entropy_file_hits"] = entropy_hits


def check_mobile_constraints(audit: Audit) -> None:
    for path in iter_repo_files():
        if path.suffix.lower() not in {".sh", ".md", ".toml", ".yml", ".yaml"}:
            continue
        try:
            text = read_text(path)
        except UnicodeDecodeError:
            continue
        rp = rel(path)
        if " && " in text and "a-Shell" in text:
            audit.warn("mobile-shell", rp, "a-Shell-facing text contains shell chaining with &&")
        if "docker compose" in text and ("iPhone" in text or "a-Shell" in text):
            audit.warn("mobile-shell", rp, "mobile-facing text references docker compose; ensure cloud/non-mobile boundary is explicit")


def check_runtime_layout(audit: Audit) -> None:
    for dirname in ("logs", "runs", "backups", "exports", "reports"):
        path = ROOT / dirname
        if path.exists() and not path.is_dir():
            audit.error("runtime-layout", dirname, "runtime path exists but is not a directory")
    gitignore = ROOT / ".gitignore"
    if not gitignore.is_file():
        audit.error("gitignore", ".gitignore", ".gitignore is missing")
        return
    text = read_text(gitignore)
    for pattern in ("logs/", "runs/", "backups/", "exports/", ".env"):
        if pattern not in text:
            audit.warn("gitignore", ".gitignore", f"missing protective ignore pattern: {pattern}")


def check_external_tools(audit: Audit, deep: bool) -> None:
    required, optional = ["python3"], ["cargo", "npm", "docker"]
    availability = {name: command_available(name) for name in required + optional}
    audit.metrics["tool_availability"] = availability
    for name in required:
        if not availability[name]:
            audit.error("tool-availability", name, "required command not found")
    for name in optional:
        if not availability[name]:
            audit.warn("tool-availability", name, "optional command not found; deep check step will be skipped")
    if not deep:
        return
    if availability.get("cargo"):
        for command in (["cargo", "fmt", "--all", "--", "--check"], ["cargo", "check", "--workspace"], ["cargo", "test", "--workspace"]):
            code, output = run_command(list(command), timeout=300)
            if code != 0:
                audit.error("deep-cargo", " ".join(command), output.strip() or "cargo command failed")
    if availability.get("npm") and (ROOT / "ui/package.json").is_file():
        code, output = run_command(["npm", "install", "--package-lock=false", "--no-audit", "--no-fund"], cwd=ROOT / "ui", timeout=300)
        if code != 0:
            audit.error("deep-npm", "ui", output.strip() or "npm install failed")
        else:
            code, output = run_command(["npm", "run", "build"], cwd=ROOT / "ui", timeout=300)
            if code != 0:
                audit.error("deep-npm", "ui", output.strip() or "npm run build failed")
    if availability.get("docker"):
        code, output = run_command(["docker", "compose", "config"], timeout=120)
        if code != 0:
            audit.warn("deep-docker", "docker-compose.yml", output.strip() or "docker compose config failed")


def build_report(audit: Audit, args: argparse.Namespace) -> dict[str, object]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for finding in audit.findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return {
        "schema": "upgraded-fiesta.full-debug.v1",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "root": str(ROOT),
        "mode": "deep" if args.deep else "static",
        "ok": audit.ok,
        "counts": counts,
        "metrics": audit.metrics,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "executable": sys.executable,
        },
        "findings": [asdict(finding) for finding in audit.findings],
    }


def write_reports(report: dict[str, object]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_payload = json.dumps(report, indent=2, sort_keys=True)
    (REPORT_DIR / "full_debug_report.json").write_text(json_payload + "\n", encoding="utf-8")
    lines = [
        "Full Debug Report",
        f"schema: {report['schema']}",
        f"generated_at_utc: {report['generated_at_utc']}",
        f"mode: {report['mode']}",
        f"ok: {report['ok']}",
        f"counts: {json.dumps(report['counts'], sort_keys=True)}",
        "", "Findings:",
    ]
    for finding in report["findings"]:  # type: ignore[index]
        lines.append(f"- [{finding['severity']}] {finding['check']} {finding['path']}: {finding['message']}")
    lines.extend(["", f"json_sha256: {hashlib.sha256(json_payload.encode('utf-8')).hexdigest()}"])
    (REPORT_DIR / "full_debug_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic full repository debug checks.")
    parser.add_argument("--deep", action="store_true", help="Run cargo/npm/docker checks when tools are available.")
    parser.add_argument("--write-report", action="store_true", help="Write reports/full_debug_report.{json,txt}.")
    args = parser.parse_args(argv)
    audit = Audit()
    for check in (
        check_expected_files, check_workspace, check_json_toml, check_python_compile,
        check_shell_scripts, check_paths, check_secrets_and_placeholders,
        check_mobile_constraints, check_runtime_layout,
    ):
        check(audit)
    check_external_tools(audit, args.deep)
    report = build_report(audit, args)
    if args.write_report:
        write_reports(report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if audit.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
