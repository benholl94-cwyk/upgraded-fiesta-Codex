#!/usr/bin/env python3
"""depo_server_ online/local-user connector.

This module provides two safe directions:
- server: a small JSON HTTP depo endpoint that can receive local-user bundles;
- connect: a local-user outbound client that pushes localhost export state to a
  depo server URL and pulls server state.

It never requires hardcoded secrets. Non-loopback URLs require DEPO_SERVER_TOKEN.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.server
import json
import os
from pathlib import Path
import socket
import sys
import time
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "datasets" / "depo-server.config.json"
REPORT_SCHEMA = "upgraded-fiesta.depo-server.report.v1"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON root must be object: {path}")
    return payload


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    if config.get("schema") != "upgraded-fiesta.depo-server.config.v1":
        raise RuntimeError("invalid depo server config schema")
    return config


def expand_runtime_path(raw: str) -> Path:
    home = os.environ.get("HOME", str(Path.home()))
    expanded = raw.replace("$HOME", home).replace("${HOME}", home).replace("$home", home).replace("${home}", home)
    return Path(os.path.expandvars(os.path.expanduser(expanded))).resolve()


def is_loopback_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return host in {"127.0.0.1", "localhost", "::1"}


def require_token_for_url(url: str, config: dict[str, Any]) -> str | None:
    token = os.environ.get(config["depo_server"]["shared_token_env"], "")
    if not is_loopback_url(url) and not token:
        raise RuntimeError(f"non-loopback depo server URL requires {config['depo_server']['shared_token_env']}")
    return token or None


def base_report(command: str, config: dict[str, Any], ok: bool = True) -> dict[str, Any]:
    return {
        "schema": REPORT_SCHEMA,
        "generated_at_utc": utc_now(),
        "ok": ok,
        "command": command,
        "repository": {
            "full_name": config["repository"]["full_name"],
            "default_branch": config["repository"]["default_branch"],
            "known_main_head": config["repository"]["known_main_head_after_network_capabilities"],
        },
        "depo_server": config["depo_server"],
        "security": config["security"],
    }


def read_localhost_bundle(config: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    bundle_path = expand_runtime_path(config["depo_server"]["localhost_export_bundle"])
    if not bundle_path.is_file():
        return None, {"path": str(bundle_path), "exists": False}
    data = bundle_path.read_bytes()
    return json.loads(data.decode("utf-8")), {"path": str(bundle_path), "exists": True, "bytes": len(data), "sha256": sha256_bytes(data)}


def write_spool(name: str, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    root = expand_runtime_path(config["depo_server"]["spool_root"])
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    path.write_bytes(data)
    return {"path": str(path), "bytes": len(data), "sha256": sha256_bytes(data)}


def http_json(method: str, url: str, payload: dict[str, Any] | None, token: str | None, timeout: int = 10) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, sort_keys=True).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return {"ok": 200 <= response.status < 300, "status": response.status, "body": json.loads(raw.decode("utf-8")) if raw else None}
    except HTTPError as exc:
        raw = exc.read()
        return {"ok": False, "status": exc.code, "body": raw.decode("utf-8", errors="replace")}
    except URLError as exc:
        return {"ok": False, "status": None, "error": str(exc)}


def status(config: dict[str, Any]) -> dict[str, Any]:
    report = base_report("status", config)
    bundle, bundle_meta = read_localhost_bundle(config)
    server_url = os.environ.get(config["depo_server"]["online_url_env"], config["depo_server"]["server_base_url_default"])
    report["local_user"] = {
        "hostname": socket.gethostname(),
        "localhost_bundle": bundle_meta,
        "server_url": server_url,
        "server_url_loopback": is_loopback_url(server_url),
        "has_token": bool(os.environ.get(config["depo_server"]["shared_token_env"], "")),
    }
    report["ok"] = True
    return report


def connect(config: dict[str, Any]) -> dict[str, Any]:
    report = base_report("connect", config)
    server_url = os.environ.get(config["depo_server"]["online_url_env"], config["depo_server"]["server_base_url_default"]).rstrip("/")
    token = require_token_for_url(server_url, config)
    bundle, bundle_meta = read_localhost_bundle(config)
    payload = {
        "schema": "upgraded-fiesta.depo-server.local-user-connect.v1",
        "generated_at_utc": utc_now(),
        "local_user": {"hostname": socket.gethostname()},
        "bundle_meta": bundle_meta,
        "bundle": bundle,
    }
    write_meta = write_spool("last-connect-payload.json", payload, config)
    push = http_json("POST", server_url + config["endpoints"]["push_bundle"], payload, token)
    pull = http_json("GET", server_url + config["endpoints"]["pull_state"], None, token)
    report.update({"server_url": server_url, "payload_spool": write_meta, "push": push, "pull": pull})
    report["ok"] = bool(push.get("ok")) and bool(pull.get("ok"))
    return report


class DepoHandler(http.server.BaseHTTPRequestHandler):
    server_version = "upgraded-fiesta-depo-server/1.0"

    def write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self) -> bool:
        token = self.server.token  # type: ignore[attr-defined]
        if not token:
            return True
        return self.headers.get("Authorization") == f"Bearer {token}"

    def do_GET(self) -> None:  # noqa: N802
        config = self.server.config  # type: ignore[attr-defined]
        if not self.authorized():
            self.write_json(401, {"schema": "upgraded-fiesta.depo-server.error.v1", "ok": False, "error": "unauthorized"})
            return
        if self.path == config["endpoints"]["health"]:
            self.write_json(200, {"schema": "upgraded-fiesta.depo-server.health.v1", "ok": True, "generated_at_utc": utc_now(), "name": config["depo_server"]["name"]})
        elif self.path == config["endpoints"]["pull_state"]:
            self.write_json(200, {"schema": "upgraded-fiesta.depo-server.state.v1", "ok": True, "generated_at_utc": utc_now(), "last_bundle_meta": getattr(self.server, "last_bundle_meta", None)})
        elif self.path == config["endpoints"]["events"]:
            self.write_json(200, {"schema": "upgraded-fiesta.depo-server.events.v1", "ok": True, "events": getattr(self.server, "events", [])[-50:]})
        else:
            self.write_json(404, {"schema": "upgraded-fiesta.depo-server.error.v1", "ok": False, "error": "not_found", "path": self.path})

    def do_POST(self) -> None:  # noqa: N802
        config = self.server.config  # type: ignore[attr-defined]
        if not self.authorized():
            self.write_json(401, {"schema": "upgraded-fiesta.depo-server.error.v1", "ok": False, "error": "unauthorized"})
            return
        if self.path not in {config["endpoints"]["connect"], config["endpoints"]["push_bundle"]}:
            self.write_json(404, {"schema": "upgraded-fiesta.depo-server.error.v1", "ok": False, "error": "not_found", "path": self.path})
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception as exc:
            self.write_json(400, {"schema": "upgraded-fiesta.depo-server.error.v1", "ok": False, "error": str(exc)})
            return
        meta = {"received_at_utc": utc_now(), "bytes": len(raw), "sha256": sha256_bytes(raw), "bundle_meta": payload.get("bundle_meta")}
        self.server.last_bundle_meta = meta  # type: ignore[attr-defined]
        self.server.events.append({"event": "bundle_received", **meta})  # type: ignore[attr-defined]
        self.write_json(200, {"schema": "upgraded-fiesta.depo-server.accept.v1", "ok": True, "meta": meta})

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(json.dumps({"schema": "upgraded-fiesta.depo-server.access.v1", "generated_at_utc": utc_now(), "client": self.client_address[0], "message": fmt % args}, sort_keys=True) + "\n")


def serve(config: dict[str, Any], host: str, port: int) -> int:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        token = os.environ.get(config["depo_server"]["shared_token_env"], "")
        if not token:
            raise RuntimeError(f"non-loopback bind requires {config['depo_server']['shared_token_env']}")
    server = http.server.ThreadingHTTPServer((host, port), DepoHandler)
    server.config = config  # type: ignore[attr-defined]
    server.token = os.environ.get(config["depo_server"]["shared_token_env"], "")  # type: ignore[attr-defined]
    server.events = []  # type: ignore[attr-defined]
    print(json.dumps({"schema": "upgraded-fiesta.depo-server.server.v1", "ok": True, "base_url": f"http://{host}:{port}", "token_required": bool(server.token), "localhost_private": host in {"127.0.0.1", "localhost", "::1"}}, indent=2, sort_keys=True), flush=True)
    server.serve_forever()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="depo_server_ online/local-user connector")
    parser.add_argument("command", choices=["status", "connect", "serve"])
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args(argv)
    try:
        config = load_config()
        if args.command == "status":
            report = status(config)
        elif args.command == "connect":
            report = connect(config)
        else:
            return serve(config, args.host or config["depo_server"]["server_bind_host_default"], args.port or int(config["depo_server"]["server_port_default"]))
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report.get("ok") else 1
    except Exception as exc:
        print(json.dumps({"schema": "upgraded-fiesta.depo-server.error.v1", "generated_at_utc": utc_now(), "ok": False, "error": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
