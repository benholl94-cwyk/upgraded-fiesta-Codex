#!/usr/bin/env python3
"""Localhost-only export server for upgraded-fiesta-Codex.

Exports selected repository artifacts as machine-readable JSON and ZIP over
https://localhost:9443 by default. No TLS key is committed; the runtime keypair is
created under .tmp when OpenSSL is available.
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
import tempfile
import zipfile
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "datasets" / "localhost-export.config.json"
SCHEMA = "upgraded-fiesta.localhost-export.bundle.v1"
KNOWN_HEAD_COMMIT = "26011779db5849559e819690304b69cfe64929ca"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


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
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "repository": {
            "full_name": config["repository"]["full_name"],
            "default_branch": config["repository"]["default_branch"],
            "known_head_commit": KNOWN_HEAD_COMMIT,
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
        },
    }


def build_zip(bundle: dict[str, Any]) -> bytes:
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest = {k: v for k, v in bundle.items() if k != "files"}
        manifest["files"] = [{k: f[k] for k in ("path", "bytes", "sha256")} for f in bundle["files"]]
        archive.writestr("export-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        for item in bundle["files"]:
            archive.writestr(item["path"], item["content_utf8"])
    return memory.getvalue()


def json_bytes(payload: dict[str, Any], status: int = 200) -> bytes:
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
    server_version = "upgraded-fiesta-localhost-export/1.0"

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
    parser = argparse.ArgumentParser(description="Serve repository export over localhost.")
    parser.add_argument("--host", default=config["localhost"]["bind_host"])
    parser.add_argument("--port", type=int, default=int(config["localhost"]["https_port"]))
    parser.add_argument("--scheme", choices=["https", "http"], default="https")
    parser.add_argument("--once", action="store_true", help="Build bundle once and print JSON instead of serving.")
    args = parser.parse_args(argv)

    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit(json.dumps({
            "schema": "upgraded-fiesta.localhost-export.error.v1",
            "ok": False,
            "error": "non-localhost bind blocked",
            "host": args.host,
        }, indent=2, sort_keys=True))

    base_url = f"{args.scheme}://localhost:{args.port}"
    if args.once:
        print(json.dumps(build_bundle(config, base_url), indent=2, sort_keys=True))
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
