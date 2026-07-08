#!/usr/bin/env python3
"""Localhost-only export server for upgraded-fiesta-Codex.

Exports selected repository artifacts as machine-readable JSON and ZIP over
https://localhost:9443 by default. It can also write the same export bundle into
$HOME/usr/var/... for local runtime handoff. No TLS key is committed; the
runtime keypair is created under .tmp when OpenSSL is available.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import zipfile
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "datasets" / "localhost-export.config.json"
SCHEMA = "upgraded-fiesta.localhost-export.bundle.v1"
KNOWN_HEAD_COMMIT = "517a27c57ca7634ba2d016bfd4eef0ec50a60545"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_config() -> dict[str, Any]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "upgraded-fiesta.localhost-export.config.v1":
        raise RuntimeError("invalid localhost export config schema")
    return payload


def normalize_repo_path(raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise RuntimeError(f"blocked export path: {raw}")
    resolved = (ROOT / candidate).resolve()
    resolved.relative_to(ROOT)
    return resolved


def expand_runtime_path(raw: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeError("runtime export path must be a non-empty string")
    home = os.environ.get("HOME", str(Path.home()))
    expanded_raw = raw.replace("${home}", home).replace("$home", home).replace("${HOME}", home).replace("$HOME", home)
    expanded = Path(os.path.expandvars(os.path.expanduser(expanded_raw))).resolve()
    if str(expanded) in {"/", home}:
        raise RuntimeError(f"refusing broad runtime export root: {expanded}")
    return expanded


def denied(path: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return pattern
    return None


def read_export_files(config: dict[str, Any]) -> list[dict[str, Any]]:
    export_cfg = config["export"]
    patterns = [str(item) for item in export_cfg["deny_globs"]]
    limit = int(export_cfg["max_file_bytes"])
    files: list[dict[str, Any]] = []
    for raw in export_cfg["include_paths"]:
        path = normalize_repo_path(str(raw))
        repo_rel = rel(path)
        denied_pattern = denied(repo_rel, patterns)
        if denied_pattern:
            raise RuntimeError(f"configured include path is denied by {denied_pattern}: {repo_rel}")
        if not path.is_file():
            raise RuntimeError(f"configured include path is missing or not a file: {repo_rel}")
        data = path.read_bytes()
        if len(data) > limit:
            raise RuntimeError(f"configured include path exceeds max_file_bytes={limit}: {repo_rel}")
        files.append({
            "path": repo_rel,
            "bytes": len(data),
            "sha256": sha256_bytes(data),
            "content_utf8": data.decode("utf-8"),
        })
    return files


def build_bundle(config: dict[str, Any], base_url: str) -> dict[str, Any]:
    export_root = config["export"].get("runtime_output_root", "$HOME/usr/var/upgraded-fiesta-Codex/localhost-export")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "repository": {
            "full_name": config["repository"]["full_name"],
            "default_branch": config["repository"]["default_branch"],
            "known_head_commit": KNOWN_HEAD_COMMIT,
        },
        "runtime_export": {
            "raw_root": export_root,
            "expanded_root": str(expand_runtime_path(str(export_root))),
            "secret_export": False,
        },
        "files": read_export_files(config),
        "endpoints": {
            "health": f"{base_url}{config['export']['health_endpoint']}",
            "json_export": f"{base_url}{config['export']['json_endpoint']}",
            "zip_export": f"{base_url}{config['export']['zip_endpoint']}",
        },
        "security": {
            "localhost_only": True,
            "committed_tls_private_key": False,
            "secret_export": False,
            "runtime_export_under_home_usr_var": True,
        },
    }


def manifest_without_inline_content(bundle: dict[str, Any]) -> dict[str, Any]:
    manifest = {k: v for k, v in bundle.items() if k != "files"}
    manifest["files"] = [{k: f[k] for k in ("path", "bytes", "sha256")} for f in bundle["files"]]
    return manifest


def build_zip(bundle: dict[str, Any]) -> bytes:
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("export-manifest.json", json.dumps(manifest_without_inline_content(bundle), indent=2, sort_keys=True) + "\n")
        for item in bundle["files"]:
            archive.writestr(item["path"], item["content_utf8"])
    return memory.getvalue()


def write_runtime_export(bundle: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_payload = json.dumps(bundle, indent=2, sort_keys=True) + "\n"
    manifest_payload = json.dumps(manifest_without_inline_content(bundle), indent=2, sort_keys=True) + "\n"
    zip_payload = build_zip(bundle)
    bundle_path = output_dir / "export.bundle.json"
    manifest_path = output_dir / "export-manifest.json"
    zip_path = output_dir / "export.zip"
    bundle_path.write_text(bundle_payload, encoding="utf-8")
    manifest_path.write_text(manifest_payload, encoding="utf-8")
    zip_path.write_bytes(zip_payload)
    return {
        "schema": "upgraded-fiesta.localhost-export.runtime-write.v1",
        "ok": True,
        "output_dir": str(output_dir),
        "files": [
            {"path": str(bundle_path), "bytes": len(bundle_payload.encode("utf-8")), "sha256": sha256_bytes(bundle_payload.encode("utf-8"))},
            {"path": str(manifest_path), "bytes": len(manifest_payload.encode("utf-8")), "sha256": sha256_bytes(manifest_payload.encode("utf-8"))},
            {"path": str(zip_path), "bytes": len(zip_payload), "sha256": sha256_bytes(zip_payload)},
        ],
        "secret_export": False,
    }


def json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def ensure_runtime_tls(config: dict[str, Any]) -> tuple[Path, Path]:
    tls_dir = normalize_repo_path(config["localhost"]["tls_runtime_dir"])
    tls_dir.mkdir(parents=True, exist_ok=True)
    cert = tls_dir / "localhost.crt"
    key = tls_dir / "localhost.key"
    if cert.is_file() and key.is_file():
        return cert, key
    openssl = shutil.which("openssl")
    if not openssl:
        raise RuntimeError("openssl command is required to generate runtime-only https://localhost certificate")
    san = ",".join(config["localhost"]["certificate_subject_alt_names"])
    cmd = [
        openssl,
        "req",
        "-x509",
        "-newkey",
        "rsa:3072",
        "-nodes",
        "-sha256",
        "-days",
        "7",
        "-keyout",
        str(key),
        "-out",
        str(cert),
        "-subj",
        "/CN=localhost",
        "-addext",
        f"subjectAltName={san}",
    ]
    completed = subprocess.run(cmd, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=60)
    if completed.returncode != 0:
        raise RuntimeError(f"openssl certificate generation failed: {completed.stderr[-2000:]}")
    return cert, key


class ExportHandler(http.server.BaseHTTPRequestHandler):
    server_version = "upgraded-fiesta-localhost-export/1.1"

    def write_response(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        config = self.server.config  # type: ignore[attr-defined]
        base_url = self.server.base_url  # type: ignore[attr-defined]
        try:
            if parsed.path in {"/", "/index.json"}:
                payload = {
                    "schema": "upgraded-fiesta.localhost-export.index.v1",
                    "ok": True,
                    "base_url": base_url,
                    "health": f"{base_url}{config['export']['health_endpoint']}",
                    "json_export": f"{base_url}{config['export']['json_endpoint']}",
                    "zip_export": f"{base_url}{config['export']['zip_endpoint']}",
                    "home_usr_var_export": str(expand_runtime_path(str(config['export'].get('runtime_output_root')))),
                }
                self.write_response(200, "application/json; charset=utf-8", json_bytes(payload))
            elif parsed.path == config["export"]["health_endpoint"]:
                payload = {
                    "schema": "upgraded-fiesta.localhost-export.health.v1",
                    "ok": True,
                    "generated_at_utc": utc_now(),
                    "repository": config["repository"],
                    "localhost_only": True,
                }
                self.write_response(200, "application/json; charset=utf-8", json_bytes(payload))
            elif parsed.path == config["export"]["json_endpoint"]:
                self.write_response(200, "application/json; charset=utf-8", json_bytes(build_bundle(config, base_url)))
            elif parsed.path == config["export"]["zip_endpoint"]:
                body = build_zip(build_bundle(config, base_url))
                self.write_response(200, "application/zip", body)
            else:
                self.write_response(404, "application/json; charset=utf-8", json_bytes({
                    "schema": "upgraded-fiesta.localhost-export.error.v1",
                    "ok": False,
                    "error": "not_found",
                    "path": parsed.path,
                }))
        except Exception as exc:
            self.write_response(500, "application/json; charset=utf-8", json_bytes({
                "schema": "upgraded-fiesta.localhost-export.error.v1",
                "ok": False,
                "error": str(exc),
            }))

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(json.dumps({
            "schema": "upgraded-fiesta.localhost-export.access.v1",
            "generated_at_utc": utc_now(),
            "client": self.client_address[0],
            "message": fmt % args,
        }, sort_keys=True) + "\n")


def serve(argv: list[str] | None = None) -> int:
    config = load_config()
    default_output = str(config["export"].get("runtime_output_root", "$HOME/usr/var/upgraded-fiesta-Codex/localhost-export"))
    parser = argparse.ArgumentParser(description="Serve or write repository export over localhost/home usr var.")
    parser.add_argument("--host", default=config["localhost"]["bind_host"])
    parser.add_argument("--port", type=int, default=int(config["localhost"]["https_port"]))
    parser.add_argument("--scheme", choices=["https", "http"], default="https")
    parser.add_argument("--once", action="store_true", help="Build bundle once and print JSON instead of serving.")
    parser.add_argument("--write", action="store_true", help="Write JSON/manifest/ZIP export into --output-dir.")
    parser.add_argument("--output-dir", default=default_output, help="Runtime export directory; supports $HOME and $home.")
    args = parser.parse_args(argv)

    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit(json.dumps({
            "schema": "upgraded-fiesta.localhost-export.error.v1",
            "ok": False,
            "error": "non-localhost bind blocked",
            "host": args.host,
        }, indent=2, sort_keys=True))

    base_url = f"{args.scheme}://localhost:{args.port}"
    if args.once or args.write:
        bundle = build_bundle(config, base_url)
        if args.write:
            report = write_runtime_export(bundle, expand_runtime_path(args.output_dir))
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(json.dumps(bundle, indent=2, sort_keys=True))
        return 0

    server = http.server.ThreadingHTTPServer((args.host, args.port), ExportHandler)
    server.config = config  # type: ignore[attr-defined]
    server.base_url = base_url  # type: ignore[attr-defined]
    if args.scheme == "https":
        cert, key = ensure_runtime_tls(config)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=str(cert), keyfile=str(key))
        server.socket = context.wrap_socket(server.socket, server_side=True)

    print(json.dumps({
        "schema": "upgraded-fiesta.localhost-export.server.v1",
        "ok": True,
        "base_url": base_url,
        "bind_host": args.host,
        "port": args.port,
        "scheme": args.scheme,
        "home_usr_var_export": str(expand_runtime_path(args.output_dir)),
        "endpoints": {
            "health": f"{base_url}{config['export']['health_endpoint']}",
            "json_export": f"{base_url}{config['export']['json_endpoint']}",
            "zip_export": f"{base_url}{config['export']['zip_endpoint']}",
        },
        "committed_tls_private_key": False,
    }, indent=2, sort_keys=True), flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(serve())
